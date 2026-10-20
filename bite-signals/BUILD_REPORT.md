# Bite Signals · MVP 0.1 build verification

Date: 19 October 2026

## Completed in this build session

- Implemented interactive Streamlit dashboard: Explore a trend, Signals board, Compare, Import studio, Data & sources.
- SQLite persistence by default; optionally PostgreSQL using `DATABASE_URL`.
- Public-source adapters: Google News UK/global RSS, Guardian Food RSS and official Wikimedia daily Wikipedia pageviews.
- Google Trends, Instagram, TikTok, menu / industry CSV import with field validation, provenance, units and deduplication.
- Matched-batch Google Trends comparison protections; same-metric Wikipedia article-view rankings; deterministic evidence-based story ideas; imported-text VADER sentiment with explicit caveats.
- Portable evidence backup/restore; source-status and ingestion-error archive; optional shared password.
- GitHub Actions scheduled refresh for persistent hosted PostgreSQL and a backend CI test workflow.
- Two platform start scripts and README with beginner setup and online deployment instructions.

## Tests actually executed here

1. `python -m pytest -q`: **15 passed**.
2. `python -m compileall -q .`: **passed**, all Python files syntactically valid.
3. Simulated no-network execution through the main Python flow of **all five app pages** with substitute Streamlit interface controls and seeded *test fixture* records: **passed**.

## Not verified here (important)

- A real Streamlit server/browser could not be launched in this container because the `streamlit` package is not installed in its offline environment. Streamlit UI API signatures were checked against official Streamlit documentation, but actual end-to-end browser interaction and visual rendering remain to be tested after installation.
- External live HTTP requests could not be exercised in this container because outbound DNS/network access is disabled. RSS and Wikimedia request construction was reviewed against public documentation and fixture-driven tests; external availability and provider changes are not guaranteed.
- PostgreSQL/Neon deployment and GitHub Actions scheduled jobs require user-provided credentials and have not been connected or executed here.
- Instagram, TikTok and the restricted Google Trends API have no approved credentials or live connection in this MVP.

The dashboard **does not ship invented measurements**. Any numerical records used in automated tests are self-contained fixtures in `tests/` only. No fake observations are inserted into the production startup database.
