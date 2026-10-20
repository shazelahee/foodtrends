"""Configuration. No credentials are bundled in the project."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE = ROOT / "data" / "bite_signals.sqlite3"
REFRESH_HOURS = {"news_google_uk": 6, "news_google_world": 6, "news_guardian": 6, "wikipedia": 24}
WATCHLIST = ["matcha", "pistachio", "Dubai chocolate", "iced coffee", "ramen"]


def database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url:
        return url
    path = Path(os.environ.get("BITE_DB_PATH", str(DEFAULT_SQLITE))).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(path)


def wiki_contact():
    return os.environ.get("BITE_WIKIMEDIA_CONTACT", "").strip()
