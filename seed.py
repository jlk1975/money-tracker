"""
seed.py — Populate the database with generic sample household bills.

Run on a fresh database to see the app with realistic example data:
    python3 seed.py

Run wipe.py first if you want to reset and re-seed.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import db

DB_PATH = os.path.join(os.path.dirname(__file__), "money_tracker.db")

# AdHoc bill targets the current month so it shows up immediately
_today = date.today()
_this_month = f"{_today.year:04d}-{_today.month:02d}"

SAMPLE_DEFINITIONS = [
    # ── Monthly ───────────────────────────────────────────────────────────────
    {"description": "Rent / Mortgage",          "frequency": "Monthly",      "typical_amount": 1500.00, "due_day":  1, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Health Insurance",          "frequency": "Monthly",      "typical_amount":  400.00, "due_day":  1, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Electric Bill",             "frequency": "Monthly",      "typical_amount":  120.00, "due_day":  8, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Water & Sewer",             "frequency": "Monthly",      "typical_amount":   65.00, "due_day": 10, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Internet",                  "frequency": "Monthly",      "typical_amount":   80.00, "due_day": 10, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Cell Phone",                "frequency": "Monthly",      "typical_amount":  150.00, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Streaming Services",        "frequency": "Monthly",      "typical_amount":   50.00, "due_day": 15, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Car Payment",               "frequency": "Monthly",      "typical_amount":  350.00, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Auto Insurance",            "frequency": "Monthly",      "typical_amount":  180.00, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Natural Gas",               "frequency": "Monthly",      "typical_amount":   90.00, "due_day": 20, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Gym Membership",            "frequency": "Monthly",      "typical_amount":   40.00, "due_day": 22, "months_active": "", "adhoc_month": "", "notes": ""},
    {"description": "Credit Card Minimum",       "frequency": "Monthly",      "typical_amount":   75.00, "due_day": 25, "months_active": "", "adhoc_month": "", "notes": ""},
    # ── Annual ────────────────────────────────────────────────────────────────
    {"description": "Car Registration",          "frequency": "Annual",       "typical_amount":  200.00, "due_day": 15, "months_active": "3",    "adhoc_month": "", "notes": ""},
    {"description": "Home / Renters Insurance",  "frequency": "Annual",       "typical_amount":  900.00, "due_day":  1, "months_active": "7",    "adhoc_month": "", "notes": ""},
    # ── Semi-Annual ───────────────────────────────────────────────────────────
    {"description": "Property Tax",              "frequency": "Semi-Annual",  "typical_amount": 1200.00, "due_day": 15, "months_active": "6,12", "adhoc_month": "", "notes": ""},
    # ── AdHoc (targets current month so it appears immediately) ───────────────
    {"description": "Annual Credit Card Fee",    "frequency": "AdHoc",        "typical_amount":   95.00, "due_day": 21, "months_active": "", "adhoc_month": _this_month, "notes": ""},
]


def seed():
    db.init_db(DB_PATH)

    existing = db.load_definitions(DB_PATH)
    if existing:
        print(f"Database already has {len(existing)} definition(s). Aborting — run wipe.py first.")
        return

    for defn in SAMPLE_DEFINITIONS:
        db.insert_definition(defn, DB_PATH)

    db.generate_month_instances(_this_month, DB_PATH)

    defs  = db.load_definitions(DB_PATH)
    insts = db.load_instances(_this_month, DB_PATH)
    print(f"Seeded {len(defs)} definitions.")
    print(f"Generated {len(insts)} instances for {_this_month}.")
    print("Launch the app and explore — then wipe.py when ready to enter your own bills.")


if __name__ == "__main__":
    seed()
