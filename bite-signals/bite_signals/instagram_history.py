"""Owned-Instagram read-only media snapshots. Never logs or persists credentials."""
from datetime import datetime, timezone
from sqlalchemy import Table, Column, String, Integer, MetaData, UniqueConstraint, select, desc
import pandas as pd
from .instagram_api import profile, media

metadata = MetaData()
snapshots = Table('instagram_media_snapshots', metadata,
    Column('username', String(200), nullable=False),
    Column('media_id', String(120), nullable=False),
    Column('captured_at', String(40), nullable=False),
    Column('posted_at', String(40)),
    Column('media_type', String(40)),
    Column('permalink', String(1000)),
    Column('caption', String(2200)),
    Column('likes', Integer), Column('comments', Integer),
    UniqueConstraint('username','media_id','captured_at',name='uq_ig_snapshot_time'))

def _count(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def capture(token, engine, at=None, account_fetch=profile, media_fetch=media):
    """Fetch account + up to 25 media snapshots and save as a single transaction."""
    account = account_fetch(token)
    username = str(account.get('username') or '').strip()
    if not username:
        raise ValueError('Instagram response contained no username.')
    items = media_fetch(token)
    if not isinstance(items, list):
        raise ValueError('Instagram returned an unexpected media response.')
    at = at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    metadata.create_all(engine)
    rows = []
    for item in items:
        if not isinstance(item, dict) or not item.get('id'):
            continue
        rows.append({'username': username, 'media_id': str(item['id']), 'captured_at': at,
                     'posted_at': item.get('timestamp'), 'media_type': item.get('media_type'),
                     'permalink': item.get('permalink'), 'caption': (item.get('caption') or '')[:2200],
                     'likes': _count(item.get('like_count')),
                     'comments': _count(item.get('comments_count'))})
    with engine.begin() as con:
        for row in rows:
            con.execute(snapshots.insert().values(**row))
    return {'username': username, 'posts': len(rows), 'captured_at': at}

def history(engine, username=None):
    metadata.create_all(engine)
    query = select(snapshots).order_by(desc(snapshots.c.captured_at))
    if username:
        query = query.where(snapshots.c.username == username)
    with engine.connect() as con:
        rows = [dict(x) for x in con.execute(query).mappings().all()]
    return pd.DataFrame(rows,columns=[c.name for c in snapshots.columns])
