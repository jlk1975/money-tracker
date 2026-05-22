#!/bin/bash
set -e

# Ensure system packages that pip can't provide are installed
MISSING=()
python3 -c "import tkinter" 2>/dev/null || MISSING+=(python3-tk)
python3 -c "import ensurepip" 2>/dev/null || MISSING+=(python3-venv)

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Installing system packages (requires sudo): ${MISSING[*]}"
    sudo apt-get install -y "${MISSING[@]}"
fi

# Create a virtualenv on first run (or if a previous attempt left a broken one)
if [ ! -f ".venv/bin/python" ]; then
    rm -rf .venv
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Install Python dependencies into the venv
.venv/bin/pip install -q -r requirements.txt

# Seed sample data (safe to re-run — aborts silently if data already exists)
.venv/bin/python seed.py

# Launch the app
.venv/bin/python app.py
