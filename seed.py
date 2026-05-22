"""
seed.py — Seed bill definitions and generate the first month's instances.
Run:  python3 seed.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import db
from tests.fixtures import SAMPLE_DEFINITIONS

DB_PATH = os.path.join(os.path.dirname(__file__), "money_tracker.db")


def seed():
    db.init_db(DB_PATH)

    existing_defs = db.load_definitions(DB_PATH)
    if existing_defs:
        print(f"Database already has {len(existing_defs)} definition(s). Aborting — run wipe.py first.")
        return

    for defn in SAMPLE_DEFINITIONS:
        db.insert_definition(defn, DB_PATH)

    # Generate June 2026 (the first month with actual bill data)
    db.generate_month_instances("2026-06", DB_PATH)

    defs  = db.load_definitions(DB_PATH)
    insts = db.load_instances("2026-06", DB_PATH)
    print(f"Seeded {len(defs)} definitions.")
    print(f"Generated {len(insts)} instances for June 2026.")


if __name__ == "__main__":
    seed()
