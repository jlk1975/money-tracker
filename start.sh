#!/bin/bash
set -e

# Ensure tkinter is available (not installable via pip — needs the system package)
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Installing python3-tk (requires sudo)..."
    sudo apt-get install -y python3-tk
fi

# Create a virtualenv on first run
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Install Python dependencies into the venv
.venv/bin/pip install -q -r requirements.txt

# Seed sample data (safe to re-run — aborts silently if data already exists)
.venv/bin/python seed.py

# Launch the app
.venv/bin/python app.py
