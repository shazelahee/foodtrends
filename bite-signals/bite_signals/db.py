"""Database functions: SQLite by default; optional persistent PostgreSQL via DATABASE_URL.
All SQL writes are transactional and duplicate-safe.
"""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json

import pandas as pd
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, Float,
                        String, Text, UniqueConstraint, select, func, desc, and_)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from .config import database_url, WATCHLIST

metadata = MetaData()
topics = Table("topics", metadata,
    Column("name", String(200), primary_key=True),
    Column("display_name", String(200), nullable=False),
    Column("created_at", String(40), nullable=False))
observations = Table("observations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fingerprint", String(64), unique=True, nullable=False),
    Column("topic", String(200), nullable=False),
    Column("source", String(70), nullable=False),
    Column("platform", String(40), nullable=False),
    Column("metric", String(80), nullable=False),
    Column("geo", String(30), nullable=False),
    Column("date", String(12), nullable=False),
    Column("value", Float, nullable=False),
    Column("unit", String(80), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("batch_id", String(80), nullable=False),
    Column("evidence", String(30), nullable=False),
    Column("notes", Text, nullable=False, default=""),
    Column("created_at", String(40), nullable=False))
articles = Table("articles", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("topic", String(200), nullable=False),
    Column("geo", String(30), nullable=False),
    Column("feed", String(60), nullable=False),
    Column("title", Text, nullable=False),
    Column("publisher", String(200), nullable=False),
    Column("published_at", String(40), nullable=False),
    Column("url", Text, nullable=False),
    Column("captured_at", String(40), nullable=False),
    UniqueConstraint("topic", "geo", "url", name="uq_articles_topic_geo_url"))
social_texts = Table("social_texts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fingerprint", String(64), unique=True, nullable=False),
    Column("topic", String(200), nullable=False),
    Column("platform", String(40), nullable=False),
    Column("geo", String(30), nullable=False),
    Column("date", String(12), nullable=False),
    Column("text", Text, nullable=False),
    Column("source_url", Text, nullable=False),
    Column("batch_id", String(80), nullable=False),
    Column("created_at", String(40), nullable=False))
refreshes = Table("refreshes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("topic", String(200), nullable=False),
    Column("geo", String(30), nullable=False),
    Column("source", String(70), nullable=False),
    Column("status", String(20), nullable=False),
    Column("added", Integer, nullable=False),
    Column("message", Text, nullable=False),
    Column("attempted_at", String(40), nullable=False))


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_topic(s):
    return " ".join(str(s).split()).strip().casefold()[:200]


def fingerprint(row):
    fields = [row.get(k) for k in ("topic", "source", "platform", "metric", "geo", "date", "source_url", "batch_id")]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=4)
def get_engine(url=None):
    url = url or database_url()
    opts = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        opts["connect_args"] = {"check_same_thread": False, "timeout": 15}
    return create_engine(url, **opts)


def initialize(engine=None):
    engine = engine or get_engine()
    metadata.create_all(engine)
    with engine.begin() as con:
        for t in WATCHLIST:
            _insert_ignore(con, topics, {"name": norm_topic(t), "display_name": t, "created_at": now_iso()})
    return engine


def _insert_ignore(con, table, values):
    stmt = postgres_insert(table).values(**values) if con.engine.dialect.name == "postgresql" else sqlite_insert(table).values(**values)
    result = con.execute(stmt.on_conflict_do_nothing())
    return result.rowcount or 0


def add_topic(topic, engine=None):
    topic = " ".join(topic.split())[:200]
    if not topic:
        raise ValueError("Enter a food or drink to search.")
    engine = engine or get_engine()
    with engine.begin() as con:
        _insert_ignore(con, topics, {"name": norm_topic(topic), "display_name": topic, "created_at": now_iso()})
    return norm_topic(topic)


def list_topics(engine=None):
    engine = engine or get_engine()
    with engine.connect() as con:
        return [dict(r) for r in con.execute(select(topics).order_by(topics.c.display_name)).mappings()]


def save_observations(rows, engine=None):
    engine = engine or get_engine()
    count = 0
    with engine.begin() as con:
        for row in rows:
            payload = dict(row)
            payload["topic"] = norm_topic(payload["topic"])
            payload.setdefault("created_at", now_iso())
            payload.setdefault("notes", "")
            payload["fingerprint"] = fingerprint(payload)
            count += _insert_ignore(con, observations, payload)
    return count


def save_articles(rows, engine=None):
    engine = engine or get_engine()
    count = 0
    with engine.begin() as con:
        for row in rows:
            payload = dict(row)
            payload["topic"] = norm_topic(payload["topic"])
            payload.setdefault("captured_at", now_iso())
            count += _insert_ignore(con, articles, payload)
    return count


def log_refresh(topic, geo, source, status, added, message="", engine=None):
    engine = engine or get_engine()
    with engine.begin() as con:
        con.execute(refreshes.insert().values(topic=norm_topic(topic), geo=geo, source=source,
            status=status, added=added, message=message[:1500], attempted_at=now_iso()))


def latest_refresh(topic, geo, source, engine=None):
    engine = engine or get_engine()
    with engine.connect() as con:
        row = con.execute(select(refreshes).where(and_(refreshes.c.topic == norm_topic(topic),
            refreshes.c.geo == geo, refreshes.c.source == source)).order_by(desc(refreshes.c.id)).limit(1)).mappings().first()
        return dict(row) if row else None


def _frame(table, filters=(), order=None, limit=None, engine=None):
    engine = engine or get_engine()
    stmt = select(table)
    for condition in filters:
        stmt = stmt.where(condition)
    if order is not None:
        stmt = stmt.order_by(order)
    if limit:
        stmt = stmt.limit(limit)
    with engine.connect() as con:
        return pd.DataFrame([dict(r) for r in con.execute(stmt).mappings().all()], columns=[c.name for c in table.columns])


def get_observations(topic=None, geo=None, source=None, metric=None, engine=None):
    conditions = []
    if topic: conditions.append(observations.c.topic == norm_topic(topic))
    if geo: conditions.append(observations.c.geo == geo)
    if source: conditions.append(observations.c.source == source)
    if metric: conditions.append(observations.c.metric == metric)
    return _frame(observations, conditions, observations.c.date, engine=engine)


def get_articles(topic=None, geo=None, engine=None):
    conditions = []
    if topic: conditions.append(articles.c.topic == norm_topic(topic))
    if geo: conditions.append(articles.c.geo == geo)
    return _frame(articles, conditions, desc(articles.c.published_at), engine=engine)


def get_refreshes(topic=None, engine=None, limit=120):
    conditions = [refreshes.c.topic == norm_topic(topic)] if topic else []
    return _frame(refreshes, conditions, desc(refreshes.c.id), limit=limit, engine=engine)


def save_social_texts(rows, engine=None):
    engine = engine or get_engine()
    total = 0
    with engine.begin() as con:
        for row in rows:
            payload = dict(row)
            payload["topic"] = norm_topic(payload["topic"])
            payload.setdefault("created_at", now_iso())
            payload["fingerprint"] = hashlib.sha256(json.dumps([payload.get(k) for k in
                ("topic", "platform", "geo", "date", "text", "source_url", "batch_id")],
                ensure_ascii=False).encode()).hexdigest()
            total += _insert_ignore(con, social_texts, payload)
    return total


def get_social_texts(topic=None, geo=None, engine=None):
    filters = []
    if topic: filters.append(social_texts.c.topic == norm_topic(topic))
    if geo: filters.append(social_texts.c.geo == geo)
    return _frame(social_texts, filters, desc(social_texts.c.date), engine=engine)
