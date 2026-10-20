#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "Python not found. Install Python 3.11+ from https://python.org/downloads/"
  read -p "Press Enter to exit..."
  exit 1
fi
if [ ! -f .venv/bin/python ]; then
  echo "[Bite Signals] Preparing your first-time setup..."
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
echo "Opening Bite Signals at http://localhost:8501"
echo "Press Ctrl+C to stop the dashboard."
.venv/bin/python -m streamlit run app.py
