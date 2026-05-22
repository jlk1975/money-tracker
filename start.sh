#!/bin/bash
set -e

# Ensure tkinter is available (not installable via pip — needs the system package)
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Installing python3-tk (requires sudo)..."
    sudo apt-get install -y python3-tk
fi

# Install Python dependencies
python3 -m pip install -q -r requirements.txt

# Seed sample data (safe to re-run — aborts silently if data already exists)
python3 seed.py

# Launch the app
python3 app.py
