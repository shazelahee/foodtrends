# 🍅 Bite Signals — START HERE

**Your dashboard is in this folder. You do not need to write Python code to use it.**

### First, try it on your laptop (free)

**Windows:** Install [Python 3.12](https://www.python.org/downloads/) (tick **Add Python to PATH**), unzip this project and double-click `START_WINDOWS.bat`.

**Mac:** Install [Python 3.12](https://www.python.org/downloads/), unzip and open `START_MAC.command`. If macOS blocks the script, open Terminal in the folder and type `bash START_MAC.command`.

The first launch installs packages, then opens **http://localhost:8501** in your browser. Search `matcha`. Visit **Data & sources** to see which public feeds succeeded or failed. Live external data requires internet access.

### What you can do immediately

- Search ingredients, dishes, drinks and restaurant topics.
- See real published news RSS items and official Wikipedia daily article views **if their servers respond**; these are clearly labelled and aren't sales or UK search volumes.
- Compare like-for-like Wikipedia article views.
- Upload official **Google Trends / Interest over time** CSV data and correctly compare terms from a single export batch.
- Upload permitted Instagram / TikTok / menu / industry CSV metrics and, if supplied, analyse small text samples with explicit caveats.
- Download a backup ZIP of your saved research and restore it later.

### Want it on your phone?

See **README.md → Section 6**. The simplest setup is GitHub + Streamlit Community Cloud. Add optional Neon PostgreSQL storage to avoid losing cloud history. Step 7 shows how to configure scheduled news / Wikipedia refresh via GitHub Actions, with no paid data API.

**Limitations:** The file does *not* contain fabricated live measurements. It is not yet connected to official Instagram/TikTok APIs; Google Trends is manual CSV, not a live API. The software has backend tests but the build environment could not connect to the live websites or launch Streamlit itself. Source errors are visible, not concealed.
