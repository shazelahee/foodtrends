"""Portable ZIP backups. Export/restore recorded observations and articles."""
from io import BytesIO
import zipfile
import pandas as pd
from .db import (get_observations, get_articles, get_social_texts,
                 save_observations, save_articles, save_social_texts, add_topic, now_iso)

MAX_BACKUP = 15 * 1024 * 1024


def export_zip(engine=None):
    out = BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("observations.csv", get_observations(engine=engine).to_csv(index=False))
        z.writestr("articles.csv", get_articles(engine=engine).to_csv(index=False))
        z.writestr("social_texts.csv", get_social_texts(engine=engine).to_csv(index=False))
        z.writestr("README.txt", "Bite Signals portable backup, created " + now_iso() +
                   "\nContains uploaded data and possibly private captions. Keep it secure.\n"
                   "Restore via Data & Sources. This is NOT an anonymised release.\n")
    return out.getvalue()


def restore_zip(raw, engine=None):
    if len(raw) > MAX_BACKUP:
        raise ValueError("Backup ZIP too large (15 MB limit).")
    total = {"observations": 0, "articles": 0, "social_texts": 0}
    with zipfile.ZipFile(BytesIO(raw)) as z:
        for name in total:
            file = f"{name}.csv"
            if file not in z.namelist():
                continue
            meta = z.getinfo(file)
            if meta.file_size > 20 * 1024 * 1024:
                raise ValueError("Backup contains a file larger than 20 MB.")
            df = pd.read_csv(BytesIO(z.read(file)), dtype=str, keep_default_na=False)
            if len(df) > 75_000:
                raise ValueError("Too many data rows in backup")
            allowed = {
                "observations": {"topic", "source", "platform", "metric", "geo", "date", "value", "unit", "source_url", "batch_id", "evidence", "notes", "created_at"},
                "articles": {"topic", "geo", "feed", "title", "publisher", "published_at", "url", "captured_at"},
                "social_texts": {"topic", "platform", "geo", "date", "text", "source_url", "batch_id", "created_at"},
            }[name]
            if df.empty:
                continue
            if not allowed.issubset(df.columns):
                raise ValueError(f"Backup file {file} has missing columns")
            if name == "observations":
                df["value"] = pd.to_numeric(df["value"], errors="raise")
            rows = df[list(allowed)].to_dict(orient="records")
            if name == "observations":
                total[name] = save_observations(rows, engine=engine)
            elif name == "articles":
                total[name] = save_articles(rows, engine=engine)
            else:
                total[name] = save_social_texts(rows, engine=engine)
            for topic in df.topic.dropna().unique():
                add_topic(str(topic), engine=engine)
    return total
