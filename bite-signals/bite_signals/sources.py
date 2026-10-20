"""Legitimate public data sources. Uses published RSS and Wikimedia APIs only.
No social scraping, unofficial Google Trends clients, or platform bypasses.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
import re
import xml.etree.ElementTree as ET

import requests

from .config import REFRESH_HOURS, wiki_contact
from .db import (norm_topic, now_iso, save_articles, save_observations,
                 log_refresh, latest_refresh)


class SourceUnavailable(RuntimeError):
    pass


def http_session():
    s = requests.Session()
    contact = wiki_contact()
    identity = f"; contact: {contact}" if contact else "; contact: configure BITE_WIKIMEDIA_CONTACT"
    s.headers.update({"User-Agent": f"BiteSignals/0.1 (food-culture research{identity})",
                      "Accept": "application/json, application/rss+xml, text/xml, */*"})
    return s


def _get(url, *, params=None, session=None):
    s = session or http_session()
    try:
        r = s.get(url, params=params, timeout=(6, 15))
        r.raise_for_status()
        if len(r.content) > 4_000_000:
            raise SourceUnavailable("Remote response was too large")
        return r
    except requests.RequestException as exc:
        raise SourceUnavailable(f"Source request failed: {str(exc)[:250]}") from exc


def _child_text(elem, child):
    found = elem.find(child)
    return "" if found is None or found.text is None else " ".join(found.text.split())


def parse_rss(xml_bytes, topic, geo, feed):
    """Return article metadata (not article bodies) from RSS 2.0/Atom feeds."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SourceUnavailable("Feed returned invalid RSS/XML") from exc
    # Captcha HTML and an unexpected XML response are not legitimate empty RSS feeds.
    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in ("rss", "feed", "rdf"):
        raise SourceUnavailable("Response was XML, but not an RSS/Atom feed")
    rows = []
    atom = "{http://www.w3.org/2005/Atom}"
    channel_items = root.findall(".//item")
    for item in channel_items:
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        publisher = _child_text(item, "source") or feed.replace("news_", "").replace("_", " ").title()
        raw_date = _child_text(item, "pubDate") or _child_text(item, "date")
        summary = _child_text(item, "description")
        if feed == "news_guardian" and norm_topic(topic) not in norm_topic(title + " " + summary):
            continue
        if not title or not link.startswith("https://"):
            continue
        try:
            parsed = parsedate_to_datetime(raw_date)
            published = parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except (TypeError, ValueError, OverflowError):
            published = ""  # Unspecified date, never use collection date as article publish date.
        rows.append({"topic": topic, "geo": geo, "feed": feed, "title": title[:600],
                     "publisher": publisher[:200], "published_at": published, "url": link,
                     "captured_at": now_iso()})
    if not channel_items:
        for item in root.findall(f".//{atom}entry"):
            title = _child_text(item, f"{atom}title")
            link_obj = item.find(f"{atom}link")
            url = link_obj.get("href", "") if link_obj is not None else ""
            raw_date = _child_text(item, f"{atom}published") or _child_text(item, f"{atom}updated")
            if not title or not url.startswith("https://"):
                continue
            if feed == "news_guardian" and norm_topic(topic) not in norm_topic(title):
                continue
            rows.append({"topic": topic, "geo": geo, "feed": feed,
                         "title": title[:600], "publisher": feed, "published_at": raw_date,
                         "url": url, "captured_at": now_iso()})
    return rows


def google_news_rss(topic, edition="GB", session=None):
    """Public RSS search feed, not an official/complete news volume API."""
    if edition not in ("GB", "WORLD"):
        raise ValueError("Edition must be GB or WORLD")
    config = {"GB": ("en-GB", "GB", "GB:en"), "WORLD": ("en-US", "US", "US:en")}
    hl, gl, ceid = config[edition]
    url = "https://news.google.com/rss/search"
    query = f'"{topic}" (food OR drink OR restaurant OR recipe OR ingredient OR menu)'
    response = _get(url, params={"q": query, "hl": hl, "gl": gl, "ceid": ceid}, session=session)
    return parse_rss(response.content, topic, edition, "news_google_uk" if edition == "GB" else "news_google_world")


def guardian_food_rss(topic, session=None):
    response = _get("https://www.theguardian.com/food/rss", session=session)
    return parse_rss(response.content, topic, "GB", "news_guardian")


def wikipedia_pageviews(topic, session=None, days=365):
    """English Wikipedia article pageviews; NOT Google searches or UK consumer demand.
    Exact Wikipedia article title or redirect only, no fuzzy invented matches.
    """
    s = session or http_session()
    info = _get("https://en.wikipedia.org/w/api.php", params={
        "action": "query", "format": "json", "redirects": "1", "titles": topic}, session=s).json()
    pages = info.get("query", {}).get("pages", {})
    if not pages:
        raise SourceUnavailable("Wikipedia article lookup produced no pages")
    page = next(iter(pages.values()))
    if "missing" in page or page.get("pageid", -1) == -1:
        raise SourceUnavailable("No exact English Wikipedia article/redirect for this search. Nothing inferred.")
    article = page["title"].replace(" ", "_")
    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    metric_url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                  f"en.wikipedia.org/all-access/user/{quote(article, safe='')}/daily/"
                  f"{start:%Y%m%d}00/{end:%Y%m%d}00")
    data = _get(metric_url, session=s).json()
    items = data.get("items", [])
    if not items:
        raise SourceUnavailable("Wikimedia supplied no dated pageview observations")
    rows = []
    for item in items:
        stamp, value = str(item.get("timestamp", "")), item.get("views")
        if not re.fullmatch(r"\d{10,14}", stamp) or not isinstance(value, (int, float)) or value < 0:
            continue
        rows.append({"topic": topic, "source": "wikipedia", "platform": "Wikipedia",
                     "metric": "pageviews", "geo": "GLOBAL", "date": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}",
                     "value": float(value), "unit": "article views/day", "source_url": metric_url,
                     "batch_id": "enwiki:" + article[:65], "evidence": "public_api",
                     "notes": f"English Wikipedia article: {page['title']}. Worldwide requests; not regional searches."})
    return rows


def refresh_one(topic, source, *, force=False, engine=None, session=None):
    topic = norm_topic(topic)
    geo = "GLOBAL" if source == "wikipedia" else ("WORLD" if source == "news_google_world" else "GB")
    if source not in REFRESH_HOURS:
        raise ValueError("Unsupported source")
    recent = latest_refresh(topic, geo, source, engine=engine)
    if not force and recent:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(recent["attempted_at"])
        retry_hours = REFRESH_HOURS[source] if recent["status"] == "ok" else 1
        if age < timedelta(hours=retry_hours):
            return {"source": source, "status": "cached" if recent["status"] == "ok" else "error (retry paused)",
                    "added": 0, "message": f"Last check {recent['attempted_at']}: {recent['message']}. Auto retry after {retry_hours}h"}
    try:
        if source == "wikipedia":
            rows = wikipedia_pageviews(topic, session=session)
            added = save_observations(rows, engine=engine)
            message = f"{len(rows)} dated API observations fetched; {added} newly saved"
        elif source == "news_guardian":
            rows = guardian_food_rss(topic, session=session)
            added = save_articles(rows, engine=engine)
            message = f"{len(rows)} topic-matching feed entries; {added} newly saved"
        else:
            rows = google_news_rss(topic, edition="GB" if source == "news_google_uk" else "WORLD", session=session)
            added = save_articles(rows, engine=engine)
            message = f"{len(rows)} feed entries; {added} newly saved"
        log_refresh(topic, geo, source, "ok", added, message, engine=engine)
        return {"source": source, "status": "ok", "added": added, "message": message}
    except (SourceUnavailable, ValueError, requests.exceptions.JSONDecodeError, KeyError) as exc:
        message = f"{type(exc).__name__}: {str(exc)[:400]}"
        log_refresh(topic, geo, source, "error", 0, message, engine=engine)
        return {"source": source, "status": "error", "added": 0, "message": message}


def refresh_topic(topic, news_edition="GB", *, force=False, engine=None, session=None):
    wanted = ["news_google_uk", "news_guardian"] if news_edition == "GB" else ["news_google_world"]
    wanted += ["wikipedia"]
    return [refresh_one(topic, src, force=force, engine=engine, session=session) for src in wanted]
