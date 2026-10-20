# 🍅 BITE SIGNALS

**Food culture, with receipts.**  
A working, editable, evidence-first Streamlit app for investigating food topics, with a UK editorial perspective and global public signals.

**Version:** MVP 0.1 · **Stack:** Python, Streamlit, Plotly, SQLAlchemy, SQLite / optional PostgreSQL.  
**No paid data API is necessary for the starter version.** Internet access is needed when refreshing the public feeds.

> This is a research starting point, not a commercial social-listening subscription. It never makes up TikTok view counts, Instagram hashtag volumes or Google search numbers. An empty result is shown as unavailable. **As of this package, external live calls have not been exercised from the build environment (outbound network unavailable); parsers, persistence, mocked connector calls, CSV imports and backups are covered by tests.**

## 1. QUICK START — open it on your own laptop

### Windows (easiest)

1. Install **Python 3.12** from [python.org/downloads](https://www.python.org/downloads/). Check **Add python.exe to PATH** during installation.
2. Unzip `Bite_Signals_MVP.zip` to somewhere easy to find, e.g. **Documents**.
3. Double-click **`START_WINDOWS.bat`** inside the `bite-signals` folder. On first use it installs the Python packages; this needs the internet. Windows may show a warning because this is a local script—inspect the script before running it.
4. Your default browser should open **http://localhost:8501**. If it doesn't, paste that address into your browser.
5. Search **matcha**, **pistachio**, **ramen**, etc. Expand **Data & sources** for the specific success/failure record of each external source.
6. To stop the app, close the black command window (or press Ctrl+C). The local SQLite database stays saved in `data/bite_signals.sqlite3`.

**On macOS:** Install Python 3.12, unzip, then use **`START_MAC.command`**. Depending on Gatekeeper, Control-click → Open, or use Terminal: `bash START_MAC.command` from the project folder. The browser URL is the same.

### Cross-platform Terminal alternative

```bash
cd bite-signals
python3 -m venv .venv
# Mac/Linux: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

You only need to install dependencies once. For the next launch use the start script again (or the final `streamlit run` command with the virtual environment activated).

**First search:** Clicking **Analyse** checks the UK public Google News RSS, The Guardian food RSS, and the exact English Wikipedia article (if any). This can take several seconds. Refresh again with the button, or let its automatic on-visit refresh pick up due feeds.

## 2. What is genuinely connected?

| Source | Connection | What you really measure | Limits |
|---|---|---|---|
| UK Google News RSS search | **Implemented live public RSS request**, no API key | Article links, titles, publisher and dates in the feed | Only a returned sample; query/coverage varies. Not an exhaustive press-mention count or UK reader count. Google News RSS is not a formally supported analytics API. |
| Global English Google News RSS | **Implemented live public RSS request** | English US-edition search RSS content | Edition selection is not world-wide population coverage. |
| The Guardian Food RSS | **Implemented live public RSS request** | Matching item titles, links and dates from the feed | Limited recent items and textual matching. |
| Wikimedia Analytics API | **Implemented live official public API** | Daily views of a matching **English Wikipedia article** (worldwide traffic) | No exact Wikipedia article → unavailable. Not Google search demand, no UK-only breakdown. May require a valid User-Agent contact. |
| Google Trends | **Working CSV import** | Exported relative interest index (0–100) by period / geo | Official API has restricted alpha access; **not connected**. Different CSVs have different scales and cannot be casually compared. |
| Instagram | **Working authorised CSV import** | Imported professional account/post data, whatever the export actually contains | No Instagram Graph API permissions/OAuth implementation. No platform-wide hashtags. |
| TikTok | **Working authorised CSV import** | Uploaded permitted engagement/post data | No TikTok API app approval/OAuth implementation. Not unrestricted trend/hashtag access. |
| Restaurant menus, prices & industry statistics | **Working CSV import** | Dated, sourced menu/sales/price measurements supplied by you | No commercial menu database subscription, no automated menu market census. |
| Uploaded captions / text | **Working CSV import + optional VADER sentiment** | Lexical tone of **at least 5** provided texts | Only a biased uploaded sample; not general consumer sentiment. |

Google Trends official API status: [Google's alpha API documentation](https://developers.google.com/search/apis/trends). TikTok's [Display API](https://developers.tiktok.com/docs/en/display-api-overview) requires developer registration and authorised user scopes and primarily concerns a connected creator's public videos. Its [Research Tools](https://developers.tiktok.com/docs/en/about-research-api) have separate eligibility and are intended for qualifying non-profit research; a commercial food platform must **not** assume access. Instagram's permissions and app-review procedures need to be assessed against the current [Meta Instagram platform documentation](https://developers.facebook.com/docs/instagram-platform/).

**Important:** "Live/implemented" means the application makes a real HTTP request to the public endpoint when the service is reachable, not that this package contains current collected public data or guarantees that the provider will respond. Source failures are recorded with messages and timestamps.

## 3. Understanding each dashboard section

- **Explore a trend:** type any term, check the source cards, inspect numeric time-series and original links, view sampled news coverage, and see grounded story prompts. An unavailable signal remains unavailable.
- **Signals board:** tracks searched topics. Ranks only topics with enough daily **English Wikipedia article views**, using the change in total views in consecutive 28-day periods. This is explicitly **not** a composite food popularity score.
- **Compare:** compare same-method Wikipedia views between article titles, or Google Trends 0–100 indices **only when all search terms were exported together in one CSV batch with the same geography**. Disallowed comparisons show a clear explanation.
- **Import studio:** accepts official Google Trends *Interest over time* CSVs, or a standardised, permission-respecting CSV of social/restaurant/industry metrics.
- **Data & sources:** displays exact update status and errors, saved numeric observations, an exportable backup, and a backup restore facility.

**Units & provenance:** every saved observation has `topic`, `source`, `platform`, `metric`, `geo`, `date`, `value`, `unit`, `source_url`, `batch_id`, `evidence`, and `notes`. Public API points use evidence=`public_api`, uploaded points use evidence=`user_csv`. Google Trends values are *not* absolute search counts. RSS coverage counts are *not* full media-monitoring estimates.

**Story generator:** this deliberately uses deterministic, auditable conditional rules—not a language model making up percentages. If enough records do not exist, it declines to suggest evidence-based quantitative claims. Co-occurring headline words are identified as words in the sampled RSS headlines, **not** Google's related searches.

## 4. Importing Google Trends without a subscription

1. Go to [Google Trends Explore](https://trends.google.com/trends/explore?geo=GB).
2. Enter **matcha** (and optionally **coffee** in the same comparison), pick **United Kingdom**, choose a period.
3. Find the **Interest over time** chart and use its download CSV button. (Do not use the separate related-queries CSV.)
4. In the app, choose **Import studio → Google Trends CSV**. Upload the export, inspect the table, then **Save verified Google Trends import**.
5. Go back to Explore or Compare. The values now have source, geo, date, unit and unique upload batch.

A native export may have a header like `Week,matcha: (United Kingdom),coffee: (United Kingdom)`. A simplified alternative is `date,topic,value,geo`; blank templates are in `examples/`. The string `<1` is treated as a censored observation and **omitted**, not rounded to zero. Dates that represent weekly periods are stored as the period's start date, not daily measurements.

**Comparison rule:** If you separately export matcha and coffee and upload them as two files, they cannot validly be compared on the same 0–100 scale. Export both terms **together** in one Trends comparison instead.

## 5. Importing Instagram, TikTok, menu and industry data

The file must use the headers:

```text
platform,topic,date,metric,value,unit,geo,source_url,notes,text
```

- **Required:** the first eight columns, including an actual `https://` evidence URL for every data row. `notes` and `text` are optional. The `source_url` is whatever original authorised post, dataset, or evidence page supports the row; a fabricated URL is not evidence.
- **Platform values:** `Instagram`, `TikTok`, `Restaurant`, `Industry`, `Other`.
- **Metric examples:** `likes`, `views`, `reach`, `impressions`, `posts`, `engagement_rate`, `menu_items`, `price`, `orders`. Specify your *actual* unit (not a label invented by the app).
- **Date:** `YYYY-MM-DD`. **Geo:** e.g. `GB`, `US`, `GLOBAL` or another geographic code that genuinely describes the observation.
- **Optional `text`:** only text you are authorised to process; the VADER model can show lexical sentiment of five or more uploaded texts. Its count is **not** a representative poll.

The provided template is intentionally empty: **no demonstration metrics are presented as real data.** Values that do not exist in permitted sources display as unavailable.

**Do not upload unauthorised third-party personal data, private account exports or other people's copyrighted content without permission.** A public Streamlit dashboard without authentication is not a private vault.

## 6. PUT IT ON YOUR PHONE — easiest web deployment

**Free/low-cost starter: Streamlit Community Cloud + GitHub; optional Neon-hosted PostgreSQL for durable history.** Cloud cost/availability and free-tier allowances may change. The starter can run locally for free without Neon, but preserving an online history across restarts requires external storage.

### Step A — make a GitHub repository

1. Create a free account at [github.com](https://github.com/) and sign in.
2. Click **New repository**, name it `bite-signals`, and create it. Prefer **private** if your hosting arrangement can deploy from a private repo (confirm your plan's eligibility).
3. Upload the **contents** of the unzipped `bite-signals` folder. They must include `app.py`, `requirements.txt`, the `bite_signals/` folder, and the hidden `.streamlit/` and `.github/` folders. **Never upload `.streamlit/secrets.toml`, a real `.env`, your database or user CSV exports.**
4. Using the free GitHub Desktop app to add the unzipped folder is another way to preserve its directories; publish to your new repo.

### Step B — create persistent storage (recommended before uploading private data)

1. Sign up to [Neon](https://neon.com/) (a hosted PostgreSQL provider; check current free tier and limits).
2. Create a new PostgreSQL project and copy its **connection string** from the dashboard. It resembles `postgresql://USERNAME:PASSWORD@HOST/DBNAME?sslmode=require`. Do **not** share it with anyone or publish it on GitHub.
3. The Bite Signals app automatically detects the `DATABASE_URL` setting. It supports both `postgresql://` and `postgres://` (translated for the psycopg driver). The database schema will be created automatically on first launch.

Without Neon, the online app will still run with SQLite, **but its history and uploaded data can disappear at any restart**. To preserve that temporary data, download a backup under **Data & sources** and restore it later; a backup is not a substitute for durable hosted storage.

### Step C — publish Streamlit app

1. Visit [share.streamlit.io](https://share.streamlit.io/) and sign in using GitHub.
2. Click **Create app / New app**, select the GitHub repository and its default branch; enter **`app.py`** as the main file.
3. In **Advanced settings → Secrets**, enter the following TOML, replacing placeholder text (omit `DATABASE_URL` only if you accept temporary cloud data):

```toml
DATABASE_URL = "postgresql://YOUR_USER:YOUR_PASSWORD@YOUR_HOST/YOUR_DB?sslmode=require"
APP_PASSWORD = "REPLACE_WITH_A_LONG_RANDOM_PASSWORD"
BITE_WIKIMEDIA_CONTACT = "you@example.com"
```

4. Click **Deploy**. Streamlit installs `requirements.txt` automatically. If it needs a few moments to start, read the onscreen deployment logs for a specific problem. **This project has not been deployed on your behalf.**
5. Open your `*.streamlit.app` URL in any laptop or phone browser. Save it to your home screen if you like. Sign in with your chosen `APP_PASSWORD`.

**Security note:** `APP_PASSWORD` is a simple shared gate, not fully fledged user authentication, access auditing or encrypted end-to-end private storage. Use a private/authenticated hosting product before using sensitive business/customer data. For a demo that uses only public data, the temporary cloud SQLite option may be adequate.

Streamlit's [official storage documentation](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data) expressly states local files on Community Cloud are not guaranteed to persist. This is why external PostgreSQL is recommended.

## 7. FULL AUTO-REFRESH even when your browser is closed (optional)

The app has **two refresh modes**:

1. **On-visit refresh:** when you analyse a new topic, feeds check if due. News uses at least a 6-hour interval and Wikipedia at least a 24-hour interval after success. Source failures are retried no more than hourly. This runs on a laptop without a scheduler, but **not when it is switched off**.
2. **GitHub Actions schedule, included:** the file `.github/workflows/refresh.yml` runs an optional collection job at **00:17, 06:17, 12:17 and 18:17 UTC**, with a manual-run option. It updates ALL topics stored in the same **persistent PostgreSQL** database, collects UK and global RSS editions plus Wikipedia daily observations, and writes success/error statuses to the app. It automatically **skips** execution if the `DATABASE_URL` GitHub repository secret has not been set.

### Enable the unattended job

1. Complete deployment **with a Neon database** (both dashboard and the scheduler must share the same database URL).
2. On GitHub in your repo, click **Settings → Secrets and variables → Actions → New repository secret**.
3. Create secret `DATABASE_URL` with exactly the **same** PostgreSQL connection URL you put into Streamlit's Secrets. Do **not** add the URL to code.
4. Optionally set secret `BITE_WIKIMEDIA_CONTACT` with your contact email for the Wikimedia User-Agent.
5. Go to **Actions → Refresh public food signals → Run workflow** to test it manually. Then inspect the job logs and the dashboard's Data & sources page.
6. Scheduled runs should subsequently occur on the indicated UTC schedule, subject to GitHub quotas and service availability. They can be delayed or skipped; **they are not real-time monitoring**. Scheduled workflows in inactive public repos can be disabled after 60 days of inactivity (see [GitHub docs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)).

For a self-hosted always-on server, you can instead schedule `python -m scripts.refresh GB` and `python -m scripts.refresh WORLD` with cron or the server's task scheduler. Never schedule GitHub Action collection to ephemeral local SQLite: the database would be lost at the end of each run. The provided workflow prevents that mistake.

## 8. Tests and project files

Run tests locally:

```bash
python -m pip install pytest
python -m pytest -q
```

The build includes backend tests using realistic **fixtures**, not claimed live measurements: parsing RSS, geographic labels, exact Wikipedia API response parsing, independent-batch Trends scales, deduplicated imports, source errors, growth calculations, and data backup/restore. The test runner `.github/workflows/test.yml` also executes on GitHub pushes once enabled.

```text
bite-signals/
├── app.py                        # Interactive Streamlit dashboard
├── requirements.txt              # Python dependencies
├── START_WINDOWS.bat             # Double-click setup / launch
├── START_MAC.command             # Mac setup / launch
├── README.md                      # This guide
├── START_HERE.md                  # One-page short instructions
├── bite_signals/
│   ├── db.py                      # Evidence database (SQLite / PostgreSQL)
│   ├── sources.py                 # RSS + official Wikimedia ingestion
│   ├── imports.py                 # Google Trends and social/menu CSV
│   ├── analysis.py                # Growth metrics, rankings, story leads
│   ├── backup.py                  # Portable ZIP export / import
│   ├── connectors.py              # API permissions and extension points
│   └── config.py                  # App configuration
├── scripts/refresh.py            # Scheduler entrypoint
├── examples/                     # Blank CSV templates
├── tests/                        # Automated backend tests
├── .github/workflows/            # Optional scheduled refresh + CI tests
└── .streamlit/                    # Brand theme and example secrets
```

## 9. Adding official API connections later

The file `bite_signals/connectors.py` explicitly lists provider statuses; `bite_signals/sources.py` houses fetches; `bite_signals/db.py:save_observations()` is the normalised data-ingest boundary. A new approved connector must:

1. Document the exact provider, app ID, credential scopes, user consent, lawful/contractual basis, quotas and data retention rules.
2. Use officially supported API endpoints, refresh tokens and permissioned accounts only (never website/hashtag scraping or covert bypasses).
3. Map numbers into `topic`, `source`, `platform`, `metric`, `geo`, `date`, `value`, `unit`, `source_url`, `batch_id`, `evidence`, `notes`.
4. Record source status/errors, preserve units/denominators and **never** substitute one metric for another.
5. Add integration tests and update the source-catalog labels to accurately reflect connectivity.

Even if TikTok Display API access is approved, it does **not** magically provide unrestricted hashtag-wide statistics. The TikTok Research API has distinct eligibility constraints; likewise, Instagram's authorised professional account insights are not a global hashtag listening feed. Google Trends' official alpha API should be integrated only after obtaining alpha credentials/documentation.

## 10. Troubleshooting

| Symptom | What to try |
|---|---|
| App says `No module named streamlit` | Launch via the start script, or install dependencies with `python -m pip install -r requirements.txt` in a Python 3.12 environment. |
| Wikipedia says no matching article | Search the exact English Wikipedia page title; a food-brand name may not have an article. Do not substitute fuzzy matches without editorial review. |
| Feed says HTTP error / access denied | Check **Data & sources** for the specific status, retry later. Public external feeds may throttle, change or disappear; no restricted scraping fallback is used. |
| Online data vanished | Community Cloud's local SQLite is temporary. Set a persistent `DATABASE_URL` or import a saved backup ZIP. |
| Comparing Google Trends uploads is blocked | Re-export all chosen terms **together in the same Google Trends comparison chart**, then upload that one file. |
| Sentiment is unavailable | Import 5+ permitted text samples using the optional `text` column; check VADER is installed. This cannot guarantee representative consumer sentiment. |
| Google Trends 'Related queries' CSV rejected | Use the **Interest over time** CSV instead, which has dates and numbers. |
| Scheduled refresh didn't run | Set GitHub `DATABASE_URL` secret to the persistent DB URL, manually run Actions workflow, inspect logs and check Actions are enabled. |

## 11. Responsible interpretation & limitations

This is an **MVP, not audited market research**. RSS collection is opportunistic, misses articles, and may change without warning. Wikipedia pageviews are affected by news cycles, page naming, bots/filters and audience composition. Google Trends indices are normalised by the originating export. CSV provenance reflects the user's declaration, not an independent platform certification. Caption sentiment is lexical and sample-biased. No market size, sales increase, UK regional readership, audience share or viral platform-wide statistics are inferred from these proxy signals.

**Data economics and restaurant menus:** you can upload real dated sources with units and citations today; automated licensed UK prices / menu feeds would be a later connector and are not falsely presented as already integrated.

---

**Bite Signals** · *Food culture, with receipts.* · Made for evidence-led UK food culture research.
