"""BITE SIGNALS · Food culture, with receipts.
Run: streamlit run app.py
"""
import html
import hmac
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Read secrets only if provided. Never check secrets into source control.
try:
    for name in ("DATABASE_URL", "APP_PASSWORD", "BITE_WIKIMEDIA_CONTACT", "INSTAGRAM_ACCESS_TOKEN"):
        secret = st.secrets.get(name)
        if secret and not os.getenv(name):
            os.environ[name] = str(secret)
except Exception:  # No secrets configured, or Streamlit secret store unavailable.
    pass

from bite_signals.analysis import (comparable_trends, news_daily, ranked_topics,
    related_headline_terms, sentiment_from_texts, story_ideas, wikimedia_growth)
from bite_signals.backup import export_zip, restore_zip
from bite_signals.config import WATCHLIST
from bite_signals.connectors import CONNECTORS
from bite_signals.db import (add_topic, get_articles, get_observations, get_refreshes,
    get_social_texts, initialize, list_topics, norm_topic, latest_refresh)
from bite_signals.imports import (google_trends_preview, import_google_trends,
    import_social, social_preview)
from bite_signals.sources import refresh_topic, refresh_one
from bite_signals.instagram_api import profile as instagram_profile, media as instagram_media, InstagramError
from bite_signals.instagram_history import capture as capture_instagram, history as instagram_history

RED = "#E94B35"
GREEN = "#173E34"
CREAM = "#FFF3DA"
YELLOW = "#F3C64E"
LILAC = "#8A77D6"

st.set_page_config(page_title="Bite Signals · food culture, with receipts",
    page_icon="🍅", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
html, body, [class*="css"], [data-testid="stApp"] {font-family: 'DM Sans', sans-serif;}
[data-testid="stAppViewContainer"] {background: #fffaf0; color: #173E34;}
[data-testid="stSidebar"] {background: #173E34;}
[data-testid="stSidebar"] * {color: #fff9e8 !important;}
[data-testid="stSidebar"] label {font-weight:600;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#173E34 !important;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a {color: #F3C64E !important;}
h1,h2,h3 {font-family:'Space Grotesk',sans-serif; color: #173E34; letter-spacing:-.035em;}
h1 {font-size:2.5rem!important;}
h2 {font-size:1.7rem!important;}
p {line-height:1.5;}
.bite-masthead {background:#173E34; border-radius:19px; padding:28px 34px 24px;
  color:#fff3da; border-bottom:7px solid #F3C64E; margin:0 0 24px;}
.bite-brand {color:#FFF3DA;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:clamp(34px,6vw,60px);letter-spacing:-.055em;line-height:1;}
.bite-brand span {color:#F3C64E;}
.bite-tag {margin-top:9px;color:#FFF3DA;font-size:15px;font-weight:600;letter-spacing:.06em;}
.bite-flag {font-size:12px;font-weight:800;color:#173E34;background:#F3C64E;border-radius:30px;padding:5px 12px; display:inline-block;margin-top:17px;}
.bite-strap {font-size:12px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:#8A77D6;margin:13px 0 3px;}
.bite-kicker {color:#E94B35;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;}
.bite-data-card {background:#fff; border:1px solid #e5dfd3;border-top:5px solid #E94B35;
 border-radius:13px;padding:15px 17px;min-height:130px;box-shadow:0 2px 12px #173e340b;}
.bite-data-card.purple {border-top-color:#8A77D6;}
.bite-data-card.yellow {border-top-color:#F3C64E;}
.bite-data-card.green {border-top-color:#173E34;}
.bite-data-card .card-label {color:#6e756d;font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;}
.bite-data-card .card-value {color:#173E34;font-family:'Space Grotesk',sans-serif;font-size:25px;font-weight:700;margin-top:13px;line-height:1.1;}
.bite-data-card .card-foot {color:#666c61;font-size:12px;margin-top:11px;}
[data-testid="stMetric"] {background:white;border:1px solid #e5dfd3;padding:14px;border-radius:12px;}
div.stButton > button[kind="primary"], button[kind="primary"] {background:#E94B35;border-color:#E94B35;color:white;}
[data-testid="stTabs"] button {font-weight:700;}
hr {border-color:#e2dfd8;}
a {color:#ba4533;}
</style>
""", unsafe_allow_html=True)

# Optional, straightforward single-user password guard; NOT multi-user access control.
password = os.getenv("APP_PASSWORD", "")
if password:
    if not st.session_state.get("authenticated", False):
        st.markdown("<div class='bite-masthead'><div class='bite-brand'>BITE <span>SIGNALS</span></div><div class='bite-tag'>Food culture, with receipts.</div></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            attempt = st.text_input("Dashboard password", type="password")
            if st.form_submit_button("Unlock dashboard", type="primary"):
                if hmac.compare_digest(attempt, password):
                    st.session_state["authenticated"] = True
                    st.rerun()
                st.error("Incorrect password")
        st.stop()

try:
    engine = initialize()
except Exception as exc:
    st.error("Database connection failed. Check DATABASE_URL and any secrets.")
    st.exception(exc)
    st.stop()


def cutoff(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat() if days else None


def recent_frame(df, days, col="date"):
    if not days or df.empty:
        return df
    return df[df[col].fillna("").astype(str).str[:10] >= cutoff(days)].copy()


def line_chart(df, x="date", y="value", color=None, unit="", title=""):
    if df.empty:
        st.info("No dated observations for this chart yet.")
        return
    fig = px.line(df, x=x, y=y, color=color, markers=len(df) < 90,
                  color_discrete_sequence=[RED, GREEN, LILAC, YELLOW, "#c39b5e"],
                  title=title, hover_data=["source_url"] if "source_url" in df.columns else None)
    fig.update_layout(paper_bgcolor="#fffaf0", plot_bgcolor="#fffaf0", font_family="DM Sans",
                      title_font_color=GREEN, font_color=GREEN, legend_title_text="",
                      margin=dict(l=6, r=6, t=50 if title else 12, b=10), hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title_text=unit, gridcolor="#e7e3db", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True)


def evidence_card(label, value, foot, theme="",):
    st.markdown(f'<div class="bite-data-card {theme}"><div class="card-label">{html.escape(label)}</div>'
                f'<div class="card-value">{html.escape(str(value))}</div>'
                f'<div class="card-foot">{html.escape(str(foot))}</div></div>', unsafe_allow_html=True)


def show_feed(df, n=12):
    if df.empty:
        st.info("No matching published feed items have been collected. Try refreshing or changing the edition.")
        return
    data = df[["published_at", "title", "publisher", "feed", "url"]].head(n).copy()
    data.columns = ["Published (UTC)", "Headline", "Publisher", "Feed", "Original source / RSS link"]
    st.dataframe(data, hide_index=True, use_container_width=True,
                 column_config={"Original source / RSS link": st.column_config.LinkColumn("Article ↗", display_text="Open ↗")})
    st.caption("Links may point first to Google News syndication. Headlines are third-party material; publication dates may be absent. News-feed editions are not the geography of the event.")


def sync_topic(topic, edition, force=False):
    with st.spinner("Checking public feeds and Wikimedia API (sources may be unavailable)..."):
        return refresh_topic(topic, "GB" if edition == "United Kingdom" else "WORLD",
                             force=force, engine=engine)


st.sidebar.markdown("## 🍅 BITE SIGNALS")
st.sidebar.caption("**FOOD CULTURE, WITH RECEIPTS.**")
page = st.sidebar.radio("Navigate", ["Explore a trend", "Signals board", "Compare", "Import studio", "Instagram (beta)", "Data & sources"])
st.sidebar.divider()
edition = st.sidebar.selectbox("News edition", ["United Kingdom", "Global (English)"])
period_label = st.sidebar.selectbox("Chart time window", ["90 days", "30 days", "365 days", "All saved"])
days = {"30 days": 30, "90 days": 90, "365 days": 365, "All saved": None}[period_label]
st.sidebar.caption("UK / global selection affects the **news feed edition**, not the origin of readers, posts or articles. Wikipedia measures English Wikipedia pageviews worldwide.")
st.sidebar.divider()
st.sidebar.markdown("🟢 **Public RSS + Wikimedia** · configured")
st.sidebar.markdown("🟡 **Google Trends + social** · CSV upload")
st.sidebar.markdown("🟡 **Instagram (beta)** · read-only token test")
st.sidebar.caption("Public source availability can change. Missing or failed data is shown explicitly.")

st.markdown('''<div class="bite-masthead"><div class="bite-brand">BITE <span>SIGNALS</span> <span style="color:#E94B35">●</span></div>
<div class="bite-tag">Food culture, with receipts.</div><div class="bite-flag">THE FOOD INTELLIGENCE DESK · MVP / 0.1</div></div>''', unsafe_allow_html=True)

if page == "Explore a trend":
    st.markdown("<div class='bite-strap'>01 / THE SEARCH DESK</div>", unsafe_allow_html=True)
    st.title("What's cooking?")
    st.write("Search any food, ingredient, drink or cuisine. The app checks accessible public sources; everything else is labelled by provenance.")
    if "chosen_topic" not in st.session_state:
        st.session_state.chosen_topic = "matcha"
    with st.form("search_form", border=False):
        a, b = st.columns([5, 1])
        query = a.text_input("Search", value=st.session_state.chosen_topic, placeholder="e.g. pistachio, ramen, Dubai chocolate", label_visibility="collapsed", max_chars=180)
        search = b.form_submit_button("Analyse ↗", type="primary", use_container_width=True)
    if search:
        if not query.strip():
            st.warning("Enter a search term first.")
        else:
            st.session_state.chosen_topic = query.strip()
    chips = st.columns(5)
    for i, food in enumerate(WATCHLIST):
        if chips[i].button(food.title(), key="chip-" + food, use_container_width=True):
            st.session_state.chosen_topic = food
    topic = st.session_state.chosen_topic
    normalized = add_topic(topic, engine=engine)
    refresh_col, stamp_col = st.columns([2, 4])
    if refresh_col.button("↻ Refresh sources now", key="force_refresh", help="Skips the automatic 6/24-hour refresh interval"):
        outcomes = sync_topic(topic, edition, force=True)
        st.session_state["auto_key"] = (normalized, edition)
        for r in outcomes:
            (st.error if r["status"] == "error" else st.success)(f"{r['source']}: {r['message']}")
    elif st.session_state.get("auto_key") != (normalized, edition):
        outcomes = sync_topic(topic, edition)
        st.session_state["auto_key"] = (normalized, edition)
        failures = [r for r in outcomes if r["status"].startswith("error")]
        if failures:
            st.warning("Some public sources could not update. See Data & sources for exact errors. Previous results, if any, remain available.")
    stamp_col.caption("AUTO: checks when the dashboard is opened or a new topic is searched · NEWS: at most every 6h · WIKIPEDIA: at most every 24h. Not a background daemon.")

    all_obs = get_observations(topic, engine=engine)
    selected_edition = "GB" if edition == "United Kingdom" else "WORLD"
    all_articles = get_articles(topic, selected_edition, engine=engine)
    obs = recent_frame(all_obs, days)
    news = recent_frame(all_articles, days, "published_at")
    wiki = obs[(obs.source == "wikipedia") & (obs.metric == "pageviews")].copy() if not obs.empty else obs
    trend = obs[obs.source == "google_trends_csv"].copy() if not obs.empty else obs
    social = obs[obs.source == "social_csv"].copy() if not obs.empty else obs
    growth = wikimedia_growth(all_obs, normalized)
    pub_dated = news[news.published_at.astype(str).str.len() > 0] if not news.empty else news
    feed_names = ["news_google_uk", "news_guardian"] if selected_edition == "GB" else ["news_google_world"]
    news_checked = any((r := latest_refresh(topic, selected_edition, src, engine=engine)) and r["status"] == "ok" for src in feed_names)

    st.divider()
    st.markdown(f"<div class='bite-kicker'>EVIDENCE SNAPSHOT / {html.escape(topic.upper())}</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        evidence_card("Wikipedia article views", f"{growth['pct']:+.1f}%" if growth else "Unavailable",
                      "Latest 28d vs previous 28d · global English Wikipedia" if growth else "Insufficient fresh consecutive daily data", "green")
    with c2:
        evidence_card("Saved news items", f"{len(news):,}" if news_checked else "Unavailable",
                      f"{edition} RSS sample · {period_label}" if news_checked else "No successful RSS feed check recorded", "")
    with c3:
        evidence_card("Google Trends", f"{len(trend):,} points" if not trend.empty else "Unavailable",
                      "User-uploaded 0–100 interest data" if not trend.empty else "Import an official CSV", "yellow")
    with c4:
        evidence_card("Social / industry data", f"{len(social):,} rows" if not social.empty else "Unavailable",
                      "Authorised CSV evidence only" if not social.empty else "No platform-wide API connected", "purple")

    st.markdown("## The signal, by source")
    tab_wiki, tab_trends, tab_news, tab_social = st.tabs(["Wikipedia attention", "Google Trends", "News coverage", "Instagram / TikTok / industry"])
    with tab_wiki:
        st.caption("**Unit:** daily article views on English Wikipedia · **Geography:** worldwide traffic · **Source:** public Wikimedia Analytics API. **Not** Google searches, restaurant sales or a UK trend score.")
        if wiki.empty:
            st.info("No verified Wikipedia pageview data. A matching English Wikipedia article may not exist, or its API may be unavailable.")
        else:
            wiki = wiki.sort_values("date").drop_duplicates("date", keep="last")
            line_chart(wiki, unit="Article views per day")
            if growth:
                st.write(f"**28-day movement:** {growth['pct']:+.1f}% · {growth['previous']:,.0f} views in the earlier period vs {growth['current']:,.0f} views in the later period (ending {growth['latest']}).")
            st.markdown(f"[Inspect original API observations ↗]({wiki.iloc[-1].source_url})")
    with tab_trends:
        st.caption("**Unit:** Google Trends relative search-interest index (0–100), not absolute searches. Compare indices only **within the same exported query batch** and geography.")
        if trend.empty:
            st.info("Google Trends data unavailable. Go to **Import studio → Google Trends**, export ‘Interest over time’ as CSV, and upload it.")
        else:
            geo = st.selectbox("Google Trends geography", sorted(trend.geo.unique()), key="trend_geo")
            batches = trend[trend.geo == geo].batch_id.unique().tolist()
            batch = st.selectbox("Export batch (keeps scales comparable)", batches, key="trend_batch")
            chunk = trend[(trend.geo == geo) & (trend.batch_id == batch)]
            line_chart(chunk, unit="Relative interest index / 100")
            st.caption(f"Source: https://trends.google.com/trends/ · Batch: {batch} · upload-derived, not live API")
    with tab_news:
        st.caption("**Unit:** matched RSS feed entries saved in this database. Dates are article publication dates (UTC), not trends-search activity. Feed results are a changing, incomplete sample.")
        if news.empty:
            st.info("No matching RSS articles are saved for this topic, edition and date range." if news_checked
                    else "RSS evidence unavailable: no successful feed check. See Data & sources for the error messages.")
        else:
            st.write(f"**{len(news)} archived matching feed entries** · {len(pub_dated)} with publication dates · {period_label}.")
            daily = news_daily(news)
            if not daily.empty:
                fig = px.bar(daily, x="date", y="articles", color_discrete_sequence=[RED])
                fig.update_layout(paper_bgcolor="#fffaf0", plot_bgcolor="#fffaf0", font_color=GREEN,
                                  yaxis_title="Saved feed entries", xaxis_title="Publication date", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            related = related_headline_terms(news, normalized)
            if related:
                st.markdown("**Co-occurring headline words** · exploratory, not related search queries")
                st.write(" · ".join(f"{word} ({count})" for word, count in related))
            show_feed(news)
    with tab_social:
        st.caption("Only authorised **user-imported metrics** appear here. No automatic Instagram hashtag, TikTok search, account reach or viral-trend claims are made.")
        if social.empty:
            st.info("No permitted Instagram, TikTok, restaurant or industry CSV metrics saved for this topic. See Import studio for a template.")
        else:
            platforms = sorted(social.platform.unique().tolist())
            platform = st.selectbox("Platform", platforms, key="social_platform")
            sub = social[social.platform == platform]
            metrics = sorted(sub.metric.unique().tolist())
            metric = st.selectbox("Metric", metrics, key="social_metric")
            sub = sub[sub.metric == metric]
            geos = sorted(sub.geo.unique().tolist())
            sub = sub[sub.geo == st.selectbox("Source geography", geos, key="social_geo")]
            units = sorted(sub.unit.unique().tolist())
            sub = sub[sub.unit == st.selectbox("Measurement unit", units, key="social_unit")]
            batches = sorted(sub.batch_id.unique().tolist())
            sub = sub[sub.batch_id == st.selectbox("Export batch", batches, key="social_batch")]
            st.caption("A batch's numbers may refer to selected posts/accounts, not platform-wide trends. Confirm sampling scope in the original export before drawing conclusions.")
            line_chart(sub.sort_values("date"), unit=sub.iloc[0].unit if not sub.empty else "")
            st.dataframe(sub[["date", "value", "unit", "source_url", "notes"]], hide_index=True, use_container_width=True,
                         column_config={"source_url": st.column_config.LinkColumn("Evidence ↗")})
        text_df = get_social_texts(topic, engine=engine)
        text_df = recent_frame(text_df, days)
        if not text_df.empty:
            st.markdown("#### Imported text sentiment · experimental")
            result = sentiment_from_texts(text_df)
            if result:
                tone = pd.DataFrame([{"Tone": k, "Samples": result["counts"].get(k, 0)} for k in ("Positive", "Neutral", "Negative")])
                st.bar_chart(tone.set_index("Tone"), color=LILAC)
                st.caption(f"{result['samples']} uploaded text samples · {result['method']}")
            else:
                st.info("Sentiment unavailable: at least 5 nonempty imported texts and the VADER package are needed.")
        else:
            st.caption("Sentiment: unavailable (no authorised uploaded text samples).")

    st.markdown("## 🍋 Story leads, not invented headlines")
    st.caption("Automatically generated prompts below only appear when their stated source actually supplies enough evidence.")
    suggestions = story_ideas(normalized, all_obs, all_articles)
    if suggestions:
        for s in suggestions:
            with st.container(border=True):
                st.markdown(f"**{s['title']}** · {s['grade']}")
                st.write(s["finding"])
                st.caption("LIMITATION: " + s["caveat"])
                st.markdown(f"[View evidence ↗]({s['url']})")
    else:
        st.info("Not enough validated evidence for a responsible story claim yet. Try another topic, import Google Trends, or return after more observations have accumulated.")

elif page == "Signals board":
    st.markdown("<div class='bite-strap'>02 / THE WATCHLIST</div>", unsafe_allow_html=True)
    st.title("The signals board")
    st.write("A live watchlist of topics you've analysed. **Rankings use one comparable source and unit only:** change in English Wikipedia article views (latest 28 days versus previous 28 days). Not an overall 'food trend score'.")
    stored = list_topics(engine=engine)
    names = [t["display_name"] for t in stored]
    with st.form("new_track"):
        c, b = st.columns([5, 1])
        new_food = c.text_input("Add to watchlist", placeholder="e.g. Korean fried chicken", label_visibility="collapsed")
        add = b.form_submit_button("Track +", use_container_width=True)
    if add and new_food.strip():
        add_topic(new_food, engine=engine)
        st.success(f"{new_food.strip()} added to your watchlist.")
        names = [t["display_name"] for t in list_topics(engine=engine)]
    selected = st.multiselect("Update selected topics (limited refresh, optional)", names, default=[], max_selections=8)
    if st.button("↻ Refresh selected", disabled=not selected):
        bar = st.progress(0)
        for i, n in enumerate(selected):
            refresh_topic(n, "GB" if edition == "United Kingdom" else "WORLD", engine=engine)
            bar.progress((i + 1) / len(selected))
        st.success(f"Checked {len(selected)} topics.")
    observations = get_observations(engine=engine)
    ranking = ranked_topics(observations, names)
    if ranking.empty:
        st.info("Rankings aren't available yet. Update watchlist topics to collect 56+ days of Wikimedia pageviews where an exact article exists. No placeholder rankings are displayed.")
    else:
        a, b = st.columns(2)
        with a:
            st.markdown("### Fastest-rising article attention")
            st.dataframe(ranking[ranking["28-day change"] > 0].head(15), hide_index=True, use_container_width=True,
                         column_config={"Source": st.column_config.LinkColumn("API ↗")})
        with b:
            st.markdown("### Declining article attention")
            st.dataframe(ranking[ranking["28-day change"] < 0].sort_values("28-day change").head(15), hide_index=True, use_container_width=True,
                         column_config={"Source": st.column_config.LinkColumn("API ↗")})
        st.caption("Rank is by relative change in total pageviews with complete 28-day windows (not absolute food popularity). Entries with missing or stale data are excluded.")
    st.markdown("### Monitored topics & RSS coverage")
    coverage = []
    edition_geo = "GB" if edition == "United Kingdom" else "WORLD"
    for n in names:
        df = recent_frame(get_articles(n, edition_geo, engine=engine), 30, "published_at")
        feeds = ["news_google_uk", "news_guardian"] if edition_geo == "GB" else ["news_google_world"]
        checked = any((r := latest_refresh(n, edition_geo, src, engine=engine)) and r["status"] == "ok" for src in feeds)
        coverage.append({"Topic": n, "Saved RSS items · last 30d": len(df) if checked else "Unavailable",
                         "Edition": edition_geo, "Interpretation": "Sampled RSS coverage" if checked else "No successful feed check"})
    st.dataframe(pd.DataFrame(coverage), hide_index=True, use_container_width=True)
    st.caption("0 may mean not collected or a feed outage, not evidence that a trend disappeared. Compare RSS totals cautiously; retrieval coverage varies by query and refresh history.")

elif page == "Compare":
    st.markdown("<div class='bite-strap'>03 / THE COMPARISON LAB</div>", unsafe_allow_html=True)
    st.title("Side-by-side, apples to apples.")
    names = [t["display_name"] for t in list_topics(engine=engine)]
    chosen = st.multiselect("Food & drink topics", names, default=[x for x in ("matcha", "pistachio") if x in names], max_selections=6)
    if not chosen:
        st.info("Choose one or more tracked topics to compare.")
    else:
        if st.button("↻ Update Wikipedia data for these topics"):
            for n in chosen:
                refresh_one(n, "wikipedia", engine=engine)
            st.success("Attempted the public API refresh. Check Data & sources for any failure details.")
        all_obs = get_observations(engine=engine)
        st.markdown("### Global English Wikipedia article views")
        st.caption("Absolute views per article, per day, on the same Wikimedia project and collection method. More views do not imply more purchases or UK interest.")
        if all_obs.empty:
            st.info("No live numeric observations available. Collect Wikipedia observations in Explore first.")
        else:
            df = all_obs[(all_obs.topic.isin([norm_topic(t) for t in chosen])) &
                         (all_obs.source == "wikipedia") & (all_obs.metric == "pageviews")].copy()
            df = recent_frame(df, days)
            df = df.sort_values("created_at").drop_duplicates(["topic", "date"], keep="last") if not df.empty else df
            line_chart(df, color="topic", unit="Daily English Wikipedia article views")
            available = sorted(df.topic.unique()) if not df.empty else []
            missing = sorted(set(norm_topic(x) for x in chosen) - set(available))
            if missing:
                st.warning("Wikipedia data unavailable for: " + ", ".join(missing))
        st.divider()
        st.markdown("### Google Trends · shared export only")
        st.caption("No combining individual 0–100 Google Trends exports. A single Google Trends CSV must include all compared search terms for its values to share a reference scale.")
        if not all_obs.empty:
            trends = all_obs[all_obs.source == "google_trends_csv"]
            places = sorted(trends.geo.unique().tolist()) if not trends.empty else ["GB"]
        else:
            places = ["GB"]
        trend_geo = st.selectbox("Google Trends comparison geography", places)
        if len(chosen) >= 2 and not all_obs.empty:
            match, explanation = comparable_trends(all_obs, chosen, trend_geo)
        else:
            match, explanation = pd.DataFrame(), "Choose at least 2 foods to compare within one imported Google Trends CSV."
        st.caption(explanation)
        if not match.empty:
            match = recent_frame(match, days)
            line_chart(match, color="topic", unit="Relative search interest (0–100)")
        else:
            st.info("No valid comparable Google Trends evidence for this selection.")
        st.markdown("### Instagram / TikTok")
        st.info("Cross-platform comparisons are unavailable until authorised data has matched scopes, denominators, time periods and units. Comparing TikTok views to Google Trends indices would be misleading.")

elif page == "Import studio":
    st.markdown("<div class='bite-strap'>04 / THE IMPORT STUDIO</div>", unsafe_allow_html=True)
    st.title("Bring your own receipts.")
    st.write("Upload exports you are authorised to use. All imports retain the source, date, geography, unit, evidence type and batch identifier in the database.")
    tab1, tab2 = st.tabs(["Google Trends CSV", "Social, menu & industry CSV"])
    with tab1:
        st.markdown("### Google Trends / Interest over time")
        st.markdown("1. Open [Google Trends](https://trends.google.com/trends/explore?geo=GB), enter a term (or multiple terms for comparisons). 2. Choose a location and period. 3. Download the **Interest over time** CSV. 4. Upload it below.")
        st.caption("Supports official Google Trends native CSV with header such as 'Week,matcha: (United Kingdom)' and tidy 'date,topic,value,geo' CSV. Values '<1' are omitted, never fabricated.")
        geo = st.selectbox("Fallback geography, only if missing from export", ["GB", "GLOBAL", "US"], key="import_geo")
        upload = st.file_uploader("Choose Google Trends CSV", type="csv", key="gt_upload", max_upload_size=5)
        if upload:
            try:
                raw = upload.getvalue()
                preview = google_trends_preview(raw, geo)
                st.success(f"Validated {len(preview)} source-labelled observations · {len(set(x['topic'] for x in preview))} topics.")
                st.dataframe(pd.DataFrame(preview)[["date", "topic", "geo", "value", "unit", "batch_id"]].head(25), hide_index=True, use_container_width=True)
                if st.button("Save verified Google Trends import", type="primary"):
                    result = import_google_trends(raw, geo, engine=engine)
                    for t in result["topics"]:
                        add_topic(t, engine=engine)
                    st.success(f"Saved {result['added']} new observations. {result['parsed'] - result['added']} already present. Batch: {result['batch_id']}")
            except Exception as exc:
                st.error(f"CSV could not be imported: {exc}")
        st.download_button("↓ Download Google Trends tidy template", data="date,topic,value,geo\n", file_name="google_trends_template.csv", mime="text/csv")
    with tab2:
        st.markdown("### Instagram, TikTok, menu or industry evidence")
        st.write("Convert permitted exports to the common template. Include an HTTPS link to the original evidence for **each** row, and the actual unit (e.g. likes, posts, £ per item). You must not upload private or third-party data without permission.")
        st.code("platform,topic,date,metric,value,unit,geo,source_url,notes,text\n"
                "Instagram,matcha,YYYY-MM-DD,likes,VALUE,likes,GB,https://example.org/original-post,,", language="csv")
        st.caption("The example above is a PLACEHOLDER schema, not sample measurements; replace the date, value and evidence URL. Platform options: Instagram, TikTok, Restaurant, Industry, Other. Optional 'text' allows experimental VADER tone analysis with at least 5 nonempty samples.")
        upload = st.file_uploader("Choose authorised social / menu CSV", type="csv", key="social_upload", max_upload_size=5)
        if upload:
            try:
                raw = upload.getvalue()
                preview, text_preview = social_preview(raw)
                st.success(f"Validated {len(preview)} metrics and {len(text_preview)} text samples.")
                st.dataframe(pd.DataFrame(preview)[["platform", "topic", "date", "metric", "value", "unit", "geo", "source_url"]].head(20), hide_index=True, use_container_width=True)
                if st.button("Save authorised data", type="primary"):
                    result = import_social(raw, engine=engine)
                    for t in result["topics"]:
                        add_topic(t, engine=engine)
                    st.success(f"Saved {result['added']} metric rows and {result['text_added']} text samples. Duplicate imports are ignored.")
            except Exception as exc:
                st.error(f"CSV could not be imported: {exc}")
        st.download_button("↓ Download social / menu CSV template",
                           data="platform,topic,date,metric,value,unit,geo,source_url,notes,text\n",
                           file_name="social_industry_template.csv", mime="text/csv")
    st.info("Official Instagram / TikTok API connections are not enabled in this MVP; the CSV importer does **not** bypass those platforms. The source adapters can be expanded after permissions are granted.")

elif page == "Instagram (beta)":
    st.markdown("<div class='bite-strap'>05 / OWNED ACCOUNT ANALYTICS</div>", unsafe_allow_html=True)
    st.title("Instagram · your account analytics")
    st.caption("Official Instagram Login: authorised account only. Likes and comments are snapshots, not reach or platform-wide trend activity.")
    st.warning("Never paste a token into this page. Keep INSTAGRAM_ACCESS_TOKEN in Streamlit Secrets. Protect account analytics with APP_PASSWORD or private app access.")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        st.info("Add INSTAGRAM_ACCESS_TOKEN in Streamlit app Settings → Secrets.")
    else:
        if st.button("Refresh Instagram analytics", type="primary"):
            try:
                result = capture_instagram(token, engine)
                st.success(f"Saved {result['posts']} post snapshots for @{result['username']} at {result['captured_at']} (UTC).")
            except (InstagramError, ValueError) as exc:
                st.error(str(exc))
            except Exception:
                st.error("Could not save Instagram results. Check that your database is writable and the API token is valid.")
    try:
        history = instagram_history(engine)
        if history.empty:
            st.info("No saved Instagram snapshots yet. Select Refresh Instagram analytics above.")
        else:
            usernames = sorted(history.username.unique().tolist())
            selected = st.selectbox("Account", usernames)
            filtered = history[history.username == selected].copy()
            st.metric("Saved post snapshots", len(filtered))
            st.metric("Distinct posts", filtered.media_id.nunique())
            st.caption("Counts show the numbers returned by Instagram when captured. Missing counts remain blank rather than zero.")
            st.dataframe(filtered[["captured_at","posted_at","media_type","likes","comments","permalink","caption"]],
                         hide_index=True, use_container_width=True)
            metric = st.selectbox("Metric over time", ["likes", "comments"])
            graph = filtered.dropna(subset=[metric]).copy()
            if not graph.empty:
                graph["post"] = graph["media_id"].str[-8:]
                st.plotly_chart(px.line(graph.sort_values("captured_at"), x="captured_at", y=metric,
                                        color="post", markers=True,
                                        labels={"captured_at":"Snapshot date (UTC)",metric:metric.title(),"post":"Post ID suffix"}),
                                use_container_width=True)
            st.download_button("Download saved Instagram snapshots (CSV)", filtered.to_csv(index=False).encode(),
                               file_name="instagram_snapshots.csv", mime="text/csv")
    except Exception:
        st.error("Instagram history could not load. Check database configuration.")
    st.caption("To preserve historical data across cloud restarts, set DATABASE_URL to persistent PostgreSQL. For scheduled updates, see INSTAGRAM_AUTOMATION.md.")

elif page == "Data & sources":
    st.markdown("<div class='bite-strap'>05 / THE RECEIPT ARCHIVE</div>", unsafe_allow_html=True)
    st.title("What's connected. What's not.")
    st.write("Every status is explicit. A connection being *implemented* does not guarantee that an external server will respond today.")
    catalog = pd.DataFrame([{"Data source": s.name, "State": s.state, "Requirement": s.needed} for s in CONNECTORS])
    st.dataframe(catalog, hide_index=True, use_container_width=True)
    st.markdown("### Recent collection attempts")
    logs = get_refreshes(engine=engine)
    if logs.empty:
        st.info("No live fetches recorded. Search a topic in Explore to begin.")
    else:
        st.dataframe(logs[["attempted_at", "topic", "geo", "source", "status", "added", "message"]].head(100),
                     hide_index=True, use_container_width=True)
    st.markdown("### Your saved evidence")
    evidence = get_observations(engine=engine)
    archive = get_articles(engine=engine)
    a, b, c = st.columns(3)
    a.metric("Numeric observations", len(evidence))
    b.metric("Saved RSS articles", len(archive))
    c.metric("Tracked topics", len(list_topics(engine=engine)))
    if not evidence.empty:
        with st.expander("View observations and original evidence URLs"):
            st.dataframe(evidence[["date", "topic", "source", "platform", "metric", "geo", "value", "unit", "evidence", "source_url", "batch_id", "notes"]],
                         hide_index=True, use_container_width=True,
                         column_config={"source_url": st.column_config.LinkColumn("Original source ↗")})
    st.markdown("### Back up and restore")
    st.warning("**Storage caveat:** SQLite persists locally, but Streamlit Community Cloud can discard local files after restarts or redeployments. For reliable online history, configure a persistent PostgreSQL DATABASE_URL (e.g. Neon) before launch. Never treat the free cloud's local SQLite file as permanent.")
    st.download_button("↓ Download all data as a portable ZIP backup", data=export_zip(engine=engine),
                       file_name="bite-signals-data-backup.zip", mime="application/zip", type="primary")
    st.caption("Backups can contain private uploaded captions or account data. Store them securely; do not share this file publicly.")
    file = st.file_uploader("Restore a Bite Signals backup ZIP", type="zip", key="restore_zip")
    if file and st.button("Restore saved observations and articles"):
        try:
            counts = restore_zip(file.getvalue(), engine=engine)
            st.success(f"Restored new rows: {counts}. Previously saved duplicate rows were skipped.")
        except Exception as exc:
            st.error(f"Could not restore backup: {exc}")
    st.markdown("### Access, provenance & security")
    st.markdown("""
- **Live when reachable:** published UK/global Google News search RSS, The Guardian Food RSS, and Wikimedia's official pageviews API. Feeds are sampled coverage; the Wikimedia series is English Wikipedia article traffic.
- **CSV only:** Google Trends search interest, Instagram, TikTok, restaurant menus, permitted industry statistics, user-authorised text samples. All CSVs are labelled user-supplied, not verified with the provider API.
- **Not included:** platform-wide hashtag/engagement data, menu coverage from commercial aggregators, national sales data, paid social listening, UK-specific Wikipedia traffic or an automatic Google Trends API integration.
- **Privacy:** A deployed app is not private by default. Set APP_PASSWORD and use a private repository where available. For sensitive data use a properly authenticated private deployment; this simple password gate is not enterprise-grade access control.
- **Scheduling:** Refreshes occur upon use, subject to short cache intervals; automatic unattended hourly/daily jobs need a continuously running service or external scheduler with a persistent database.
    """)
    st.markdown("[Google Trends alpha API documentation ↗](https://developers.google.com/search/apis/trends) · [Wikimedia pageview policies ↗](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html) · [TikTok official developer documentation ↗](https://developers.tiktok.com/docs/en/display-api-overview) · [Streamlit Cloud storage guidance ↗](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data)")

st.divider()
st.caption("BITE SIGNALS / FOOD CULTURE, WITH RECEIPTS. · Not a licensed social listening product · Nothing in this dashboard is a purchase, sales, or consumer-preference estimate unless the original dataset expressly measures it.")
