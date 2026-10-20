"""Optional scheduled job for an always-on, persistent deployment.
Usage: python -m scripts.refresh [GB|WORLD]
Run this from cron or a platform scheduler; Streamlit Cloud is not an always-on scheduler.
"""
import sys
from bite_signals.db import initialize, list_topics
from bite_signals.sources import refresh_topic


def main():
    geo = sys.argv[1].upper() if len(sys.argv) > 1 else "GB"
    if geo not in {"GB", "WORLD"}:
        raise SystemExit("Usage: python -m scripts.refresh [GB|WORLD]")
    engine = initialize()
    for topic in list_topics(engine=engine):
        print(topic["display_name"], refresh_topic(topic["display_name"], geo, engine=engine), flush=True)


if __name__ == "__main__":
    main()
