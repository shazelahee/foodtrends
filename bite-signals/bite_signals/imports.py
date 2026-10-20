"""Permission-respecting CSV loaders. No guessed geography, dates, or metrics."""
from datetime import datetime
from io import StringIO
import csv
import hashlib
import math
import re

import pandas as pd
from .db import save_observations, save_social_texts, norm_topic

MAX_CSV_BYTES = 5 * 1024 * 1024
ALLOWED_PLATFORMS = {"instagram": "Instagram", "tiktok": "TikTok", "restaurant": "Restaurant", "industry": "Industry", "other": "Other"}
METRICS = {"views", "likes", "comments", "shares", "saves", "reach", "impressions", "mentions", "posts", "engagements", "engagement_rate", "menu_items", "price", "orders", "sentiment_score", "other"}


def _read_csv(raw):
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError("CSV is too large (maximum 5 MB).")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save the CSV as UTF-8 and retry.") from exc


def _date(raw):
    value = str(raw).strip()
    # Google Trends sometimes labels a week as a start/end interval.
    value = re.split(r"\s+-\s+", value)[0]
    try:
        return pd.to_datetime(value, errors="raise").date().isoformat()
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"Invalid date: {value!r}. Use YYYY-MM-DD.") from exc


def _geo(value, fallback=""):
    value = str(value or "").strip()
    names = {"united kingdom": "GB", "uk": "GB", "great britain": "GB", "gb": "GB",
             "united states": "US", "usa": "US", "us": "US", "worldwide": "GLOBAL",
             "world": "GLOBAL", "global": "GLOBAL"}
    return names.get(value.casefold(), value.upper() or fallback)


def _number(value):
    if str(value).strip().startswith("<"):
        return None  # Censored Google Trends <1 is not silently converted to zero.
    try:
        x = float(str(value).replace(",", "").replace("%", "").strip())
        if not math.isfinite(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def google_trends_preview(raw, default_geo="GB"):
    """Parse Google Trends Interest over time export or a tidy date/topic/value CSV.
    The returned batch is shared only by terms FROM THE SAME uploaded export.
    """
    content = _read_csv(raw)
    digest = "GT-" + hashlib.sha256(raw).hexdigest()[:16]
    lines = list(csv.reader(StringIO(content)))
    header_at = None
    mode = None
    for i, line in enumerate(lines):
        normalized = [str(x).strip().lower() for x in line]
        if {"date", "topic", "value"}.issubset(set(normalized)):
            header_at, mode = i, "tidy"
            break
        if line and line[0].strip().lower() in ("day", "week", "month", "year", "date") and len(line) >= 2:
            header_at, mode = i, "native"
            break
    if header_at is None:
        raise ValueError("No Google Trends time-series header found. Upload 'Interest over time' CSV, not 'Related queries'.")
    header = [str(x).strip() for x in lines[header_at]]
    out = []
    for raw_line in lines[header_at + 1:]:
        if len(raw_line) < 2 or not any(v.strip() for v in raw_line):
            continue
        if not raw_line[0].strip():
            continue
        if mode == "tidy":
            d = dict(zip([x.casefold() for x in header], raw_line))
            if not d.get("date") or not d.get("topic"):
                continue
            date = _date(d["date"])
            topic = norm_topic(d["topic"])
            val = _number(d.get("value"))
            geo = _geo(d.get("geo", default_geo), default_geo)
            values = [(topic, geo, val)]
        else:
            date = _date(raw_line[0])
            values = []
            for h, v in zip(header[1:], raw_line[1:]):
                if not h or h.lower().startswith("ispartial"):
                    continue
                m = re.match(r"^(.*?)\s*:\s*\((.*?)\)\s*$", h)
                term, place = (m.group(1), m.group(2)) if m else (h, default_geo)
                values.append((norm_topic(term), _geo(place, default_geo), _number(v)))
        for topic, geo, val in values:
            if val is None:
                continue
            if not 0 <= val <= 100:
                raise ValueError(f"Google Trends indices must be between 0 and 100; got {val}.")
            if not topic:
                continue
            out.append({"topic": topic, "source": "google_trends_csv", "platform": "Google Trends",
                        "metric": "interest_index", "geo": geo, "date": date, "value": val,
                        "unit": "relative index 0–100", "source_url": "https://trends.google.com/trends/",
                        "batch_id": digest, "evidence": "user_csv",
                        "notes": "Google Trends export. Indexed within this query and period; compare only within this upload."})
    if not out:
        raise ValueError("The CSV had no valid numeric values. Values like '<1' are omitted, not guessed.")
    return out


def import_google_trends(raw, default_geo="GB", engine=None):
    rows = google_trends_preview(raw, default_geo)
    return {"parsed": len(rows), "added": save_observations(rows, engine=engine),
            "batch_id": rows[0]["batch_id"], "topics": sorted(set(r["topic"] for r in rows))}


def social_preview(raw):
    content = _read_csv(raw)
    reader = csv.DictReader(StringIO(content))
    required = {"platform", "topic", "date", "metric", "value", "unit", "geo", "source_url"}
    columns = {str(c).strip().lower() for c in (reader.fieldnames or [])}
    missing = required - columns
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(sorted(missing)))
    digest = "SOC-" + hashlib.sha256(raw).hexdigest()[:16]
    metric_rows, text_rows = [], []
    for line_no, raw_row in enumerate(reader, start=2):
        row = {str(k).strip().lower(): str(v or "").strip() for k, v in raw_row.items() if k is not None}
        if not any(row.values()):
            continue
        platform = ALLOWED_PLATFORMS.get(row["platform"].casefold())
        if not platform:
            raise ValueError(f"Row {line_no}: unsupported platform. Choose Instagram, TikTok, Restaurant, Industry or Other.")
        metric = row["metric"].casefold()
        if metric not in METRICS:
            raise ValueError(f"Row {line_no}: unsupported metric {metric}. Use a documented name (see example).")
        url = row["source_url"]
        if not url.startswith("https://"):
            raise ValueError(f"Row {line_no}: source_url must be a real HTTPS source link.")
        val = _number(row["value"])
        if val is None:
            raise ValueError(f"Row {line_no}: value must be a finite number.")
        if not row["geo"] or not row["unit"] or not row["topic"]:
            raise ValueError(f"Row {line_no}: topic, geo and unit cannot be empty.")
        date = _date(row["date"])
        topic, geo = norm_topic(row["topic"]), _geo(row["geo"])
        metric_rows.append({"topic": topic, "source": "social_csv", "platform": platform,
                            "metric": metric, "geo": geo, "date": date, "value": val,
                            "unit": row["unit"], "source_url": url, "batch_id": digest,
                            "evidence": "user_csv", "notes": row.get("notes", "")[:400]})
        if row.get("text", ""):
            text_rows.append({"topic": topic, "platform": platform, "geo": geo, "date": date,
                              "text": row["text"][:2000], "source_url": url, "batch_id": digest})
    if not metric_rows:
        raise ValueError("CSV contains no valid data rows.")
    return metric_rows, text_rows


def import_social(raw, engine=None):
    rows, texts = social_preview(raw)
    return {"parsed": len(rows), "added": save_observations(rows, engine=engine),
            "text_added": save_social_texts(texts, engine=engine) if texts else 0,
            "topics": sorted(set(r["topic"] for r in rows))}
