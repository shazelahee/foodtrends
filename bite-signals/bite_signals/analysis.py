"""Evidence-led calculations: each metric retains its own denominator and unit."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import re

import pandas as pd

STOPWORDS = set("""a about after all also an and are as at be been but by can could day days do does for from
had has have in into is it its like more most new no not of on one or our out over so some than that the
their them there these this those to too up us was were what when where which while who why with year years
say says said food foods eat eating drink drinks restaurant restaurants recipe recipes chefs chef uk us
latest how why people gets get now just here's it’s it's trend trends best""".split())


def wikimedia_growth(observations, topic=None, period=28):
    """Coverage-matched, consecutive daily observations, last 2 vs prior 28 days.
    Returns None on insufficient, stale or non-comparable samples.
    """
    if observations.empty:
        return None
    f = observations[observations["source"] == "wikipedia"].copy()
    if topic:
        f = f[f["topic"] == topic.casefold()]
    f = f[(f["metric"] == "pageviews") & (f["geo"] == "GLOBAL")]
    if f.empty:
        return None
    f["date"] = pd.to_datetime(f["date"], errors="coerce", utc=True)
    f = f.dropna(subset=["date"]).sort_values(["date", "created_at"])
    f = f.drop_duplicates(subset=["date"], keep="last")
    if f.empty:
        return None
    latest = f["date"].max()
    if (pd.Timestamp.now(tz="UTC") - latest).days > 7:
        return None
    current_start = latest - pd.Timedelta(days=period - 1)
    previous_start = latest - pd.Timedelta(days=period * 2 - 1)
    current = f[(f.date >= current_start) & (f.date <= latest)]
    prior = f[(f.date >= previous_start) & (f.date < current_start)]
    if len(current) != period or len(prior) != period:
        return None
    earlier = float(prior.value.sum())
    current_value = float(current.value.sum())
    if earlier <= 0:
        return None
    return {"pct": 100 * (current_value - earlier) / earlier, "current": current_value,
            "previous": earlier, "period": period, "latest": latest.strftime("%Y-%m-%d"),
            "source_url": str(f.iloc[-1].source_url), "unit": "English Wikipedia article views"}


def google_trends_groups(df, topic=None):
    if df.empty:
        return pd.DataFrame()
    f = df[df.source == "google_trends_csv"]
    if topic:
        f = f[f.topic == topic.casefold()]
    return f.copy()


def comparable_trends(df, topic_names, geo):
    """Select only an uploaded Google Trends batch containing all given terms.
    Returns (data, message) rather than silently merging unrelated 0–100 indices.
    """
    terms = {x.casefold() for x in topic_names}
    f = google_trends_groups(df)
    if f.empty:
        return pd.DataFrame(), "No Google Trends CSV has been imported."
    f = f[f.geo == geo]
    candidates = []
    for batch_id, g in f.groupby("batch_id"):
        if terms.issubset(set(g.topic)):
            count = len(set(g.date))
            candidates.append((count, batch_id, g))
    if not candidates:
        return pd.DataFrame(), "No single Google Trends export contains all these terms at this geography. Import a single side-by-side Google Trends comparison CSV; separate exports have incompatible 0–100 scales."
    _, batch, chosen = sorted(candidates, key=lambda t: (t[0], t[1]), reverse=True)[0]
    return chosen[chosen.topic.isin(terms)].copy(), f"Relative indices from the same upload ({batch}); comparable within that export only."


def news_daily(articles_df):
    if articles_df.empty:
        return pd.DataFrame(columns=["date", "articles"])
    f = articles_df.copy()
    f["date"] = pd.to_datetime(f.published_at, errors="coerce", utc=True).dt.date
    f = f.dropna(subset=["date"])
    if f.empty:
        return pd.DataFrame(columns=["date", "articles"])
    return f.groupby("date").size().reset_index(name="articles")


def related_headline_terms(df, topic, limit=8):
    if df.empty:
        return []
    banned = STOPWORDS | set(re.findall(r"[a-zA-ZÀ-ÿ]+", topic.casefold()))
    tokens = []
    for title in df.title.dropna().astype(str):
        tokens.extend(t for t in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", title.casefold()) if t not in banned)
    return Counter(tokens).most_common(limit)


def sentiment_from_texts(text_df):
    """VADER lexical polarity on uploaded text only; not population sentiment."""
    if text_df.empty:
        return None
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:
        return None
    analyser = SentimentIntensityAnalyzer()
    rows = [str(t) for t in text_df.text if str(t).strip()]
    if len(rows) < 5:
        return None
    scores = [analyser.polarity_scores(t)["compound"] for t in rows]
    counts = Counter("Positive" if s >= 0.05 else "Negative" if s <= -0.05 else "Neutral" for s in scores)
    return {"counts": counts, "samples": len(scores), "method": "VADER dictionary-based tone of imported text; language/context dependent, not a representative sentiment poll."}


def story_ideas(topic, observations, article_df):
    ideas = []
    growth = wikimedia_growth(observations, topic)
    if growth:
        direction = "rising" if growth["pct"] > 5 else "falling" if growth["pct"] < -5 else "steady"
        ideas.append({"title": f"Is attention to {topic.title()} {direction}?",
            "finding": f"Views of the English Wikipedia article changed {growth['pct']:+.1f}% across consecutive {growth['period']}-day periods ({growth['previous']:,.0f} vs {growth['current']:,.0f} views), ending {growth['latest']}.",
            "caveat": "This is article readership, not Google search activity, sales, TikTok demand or UK-only behaviour.",
            "url": growth["source_url"], "grade": "API observation"})
    if not article_df.empty:
        valid = article_df.copy()
        valid["published"] = pd.to_datetime(valid.published_at, errors="coerce", utc=True)
        valid = valid.dropna(subset=["published"])
        fresh = valid[valid.published >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)]
        if len(fresh) >= 3:
            ideas.append({"title": f"What are newsrooms saying about {topic.title()}?",
                "finding": f"{len(fresh)} distinct matching RSS items with known publication dates were saved from selected feeds in the last 30 days. Story angles can be explored in the linked headlines below.",
                "caveat": "Not a census of articles, not an estimate of total internet mentions or an unbiased measure of popularity. Feeds may overlap or limit results.",
                "url": str(fresh.iloc[0].url), "grade": "Sampled RSS items"})
    return ideas


def ranked_topics(obs_df, topic_names):
    rows = []
    for name in topic_names:
        growth = wikimedia_growth(obs_df, name)
        if growth:
            rows.append({"Topic": name.title(), "28-day change": round(growth["pct"], 1),
                         "Views · latest 28d": int(growth["current"]), "Through": growth["latest"],
                         "Evidence": "Wikipedia API", "Source": growth["source_url"]})
    return pd.DataFrame(rows).sort_values("28-day change", ascending=False) if rows else pd.DataFrame()
