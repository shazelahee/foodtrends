from datetime import datetime, timedelta, timezone
from io import BytesIO
import math
import zipfile

import pandas as pd
import pytest
from sqlalchemy import create_engine

from bite_signals import analysis, db, imports, sources, backup


@pytest.fixture
def engine():
    e = create_engine("sqlite+pysqlite:///:memory:")
    db.initialize(e)
    yield e
    e.dispose()


def test_watchlist_initialized(engine):
    assert "matcha" in [t["name"] for t in db.list_topics(engine)]
    assert len(db.list_topics(engine)) == 5


def test_add_topic_normalization(engine):
    assert db.add_topic("  Dubai   Chocolate ", engine=engine) == "dubai chocolate"
    assert len(db.list_topics(engine)) == 5


def test_rss_parser_google():
    xml = b'''<?xml version="1.0"?><rss version="2.0"><channel><item><title>Matcha and the menu</title>
    <link>https://example.com/news/2</link><source>Food Journal</source>
    <pubDate>Sun, 18 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>'''
    result = sources.parse_rss(xml, "matcha", "GB", "news_google_uk")
    assert len(result) == 1
    assert result[0]["publisher"] == "Food Journal"
    assert result[0]["published_at"] == "2026-10-18T10:00:00+00:00"
    assert result[0]["url"].startswith("https://")


def test_guardian_feed_only_matches():
    xml = b'''<rss><channel><item><title>Matcha cake today</title><link>https://www.theguardian.com/food/x</link></item>
    <item><title>Spaghetti today</title><link>https://www.theguardian.com/food/y</link></item></channel></rss>'''
    assert len(sources.parse_rss(xml, "matcha", "GB", "news_guardian")) == 1


def test_invalid_xml_raises():
    with pytest.raises(sources.SourceUnavailable):
        sources.parse_rss(b"<broken", "matcha", "GB", "news_google_uk")


def test_import_google_trends_native(engine):
    native = b"Category: All categories\n\nWeek,matcha: (United Kingdom),coffee: (United Kingdom),isPartial\n2026-10-04,45,98,False\n2026-10-11,<1,100,False\n"
    parsed = imports.google_trends_preview(native)
    assert len(parsed) == 3
    assert set(r["topic"] for r in parsed) == {"matcha", "coffee"}
    assert all(r["geo"] == "GB" for r in parsed)
    first = imports.import_google_trends(native, engine=engine)
    assert first["added"] == 3
    assert imports.import_google_trends(native, engine=engine)["added"] == 0


def test_import_trends_tidy_validates(engine):
    native = b"date,topic,value,geo\n2026-10-01,matcha,101,GB\n"
    with pytest.raises(ValueError, match="between 0 and 100"):
        imports.import_google_trends(native, engine=engine)


def test_google_trends_batch_comparison_protects_scales(engine):
    imports.import_google_trends(b"date,topic,value,geo\n2026-10-01,matcha,80,GB\n", engine=engine)
    imports.import_google_trends(b"date,topic,value,geo\n2026-10-01,coffee,60,GB\n", engine=engine)
    frame, message = analysis.comparable_trends(db.get_observations(engine=engine), ["matcha", "coffee"], "GB")
    assert frame.empty and "No single" in message
    native = b"Week,matcha: (United Kingdom),coffee: (United Kingdom)\n2026-10-02,12,15\n"
    imports.import_google_trends(native, engine=engine)
    frame, message = analysis.comparable_trends(db.get_observations(engine=engine), ["matcha", "coffee"], "GB")
    assert len(frame) == 2
    assert frame.batch_id.nunique() == 1


def test_social_csv_acceptable(engine):
    row = ("platform,topic,date,metric,value,unit,geo,source_url,notes,text\n"
           "TikTok,matcha,2026-10-18,likes,32,likes,GB,https://tiktok.com/video/1,export,delicious drink!\n").encode()
    r = imports.import_social(row, engine=engine)
    assert r["added"] == 1 and r["text_added"] == 1
    assert imports.import_social(row, engine=engine)["added"] == 0
    assert len(db.get_social_texts("matcha", engine=engine)) == 1


def test_social_must_have_real_https_source():
    bad = b"platform,topic,date,metric,value,unit,geo,source_url\nTikTok,matcha,2026-10-18,likes,32,likes,GB,none\n"
    with pytest.raises(ValueError, match="HTTPS"):
        imports.social_preview(bad)


def test_growth_uses_complete_periods(engine):
    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    rows = []
    for i in range(56):
        day = end - timedelta(days=55-i)
        rows.append({"topic": "matcha", "source": "wikipedia", "platform": "Wikipedia",
            "metric": "pageviews", "geo": "GLOBAL", "date": day.isoformat(),
            "value": float(100 if i < 28 else 200), "unit": "article views/day",
            "source_url": "https://wikimedia.org/api/rest_v1/test", "batch_id": "enwiki:Matcha",
            "evidence": "public_api", "notes": "Test fixture - not distributed data"})
    assert db.save_observations(rows, engine=engine) == 56
    change = analysis.wikimedia_growth(db.get_observations(engine=engine), "matcha")
    assert math.isclose(change["pct"], 100)
    assert change["current"] == 5600
    assert len(analysis.ranked_topics(db.get_observations(engine=engine), ["matcha"])) == 1
    # Removing a day makes growth unavailable, not extrapolated.
    df = db.get_observations(engine=engine)
    assert analysis.wikimedia_growth(df.iloc[:-1], "matcha") is None


def test_sourced_stories_only(engine):
    ideas = analysis.story_ideas("matcha", db.get_observations(engine=engine), db.get_articles(engine=engine))
    assert ideas == []


class MockResponse:
    def __init__(self, payload, content=b"", status_code=200):
        self._payload, self.content, self.status_code = payload, content, status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError
            raise HTTPError("Not found")
    def json(self):
        return self._payload


class MockSession:
    def __init__(self, missing=False):
        self.missing = missing
        self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if "w/api.php" in url:
            return MockResponse({"query": {"pages": {"1": {"pageid": 1, "title": "Matcha", **({"missing": True} if self.missing else {})}}}})
        if "wikimedia.org/api" in url:
            end = datetime.now(timezone.utc).date() - timedelta(days=2)
            items = [{"timestamp": (end - timedelta(days=k)).strftime("%Y%m%d") + "00", "views": 150} for k in range(60)]
            return MockResponse({"items": items})
        rss = b"<rss><channel><item><title>Matcha in cafes</title><link>https://example.org/news</link></item></channel></rss>"
        return MockResponse({}, content=rss)


def test_public_api_and_refresh_without_real_network(engine):
    mock = MockSession()
    out = sources.refresh_topic("matcha", "GB", engine=engine, session=mock)
    assert all(r["status"] == "ok" for r in out)
    assert len(db.get_observations("matcha", source="wikipedia", engine=engine)) == 60
    assert len(db.get_articles("matcha", engine=engine)) == 1  # same URL deduped across RSS feeds
    # no duplicate calls within refresh interval
    before = len(mock.calls)
    again = sources.refresh_topic("matcha", "GB", engine=engine, session=mock)
    assert len(mock.calls) == before
    assert all(r["status"] == "cached" for r in again)


def test_no_wikipedia_article_fails_explicitly(engine):
    result = sources.refresh_one("matcha", "wikipedia", engine=engine, session=MockSession(missing=True))
    assert result["status"] == "error"
    assert db.get_observations(engine=engine).empty


def test_backup_round_trip(engine):
    imports.import_google_trends(b"date,topic,value,geo\n2026-10-01,matcha,22,GB\n", engine=engine)
    original = backup.export_zip(engine)
    with zipfile.ZipFile(BytesIO(original)) as z:
        assert "observations.csv" in z.namelist()
    e2 = create_engine("sqlite+pysqlite:///:memory:")
    db.initialize(e2)
    restored = backup.restore_zip(original, e2)
    assert restored["observations"] == 1
    assert backup.restore_zip(original, e2)["observations"] == 0
    e2.dispose()
