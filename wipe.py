"""
wipe.py — Wipe data from the database.
Run:  python3 wipe.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import db

DB_PATH = os.path.join(os.path.dirname(__file__), "money_tracker.db")


def wipe():
    db.init_db(DB_PATH)

    defs  = db.load_definitions(DB_PATH)
    months = db.get_months_with_instances(DB_PATH)

    if not defs and not months:
        print("Database is already empty.")
        return

    print(f"Found {len(defs)} definition(s) and instances in {len(months)} month(s): {', '.join(months) or 'none'}")
    print("Options:")
    print("  1 — Wipe instances only (keep definitions)")
    print("  2 — Wipe everything (instances + definitions)")
    choice = input("Enter 1 or 2 (or anything else to abort): ").strip()

    if choice == "1":
        for month in months:
            rows = db.load_instances(month, DB_PATH)
            for row in rows:
                db.delete_instance(row["id"], DB_PATH)
        print(f"Wiped all instances across {len(months)} month(s). Definitions intact.")

    elif choice == "2":
        confirm = input(f"This will delete ALL {len(defs)} definitions and all instances. Type YES to confirm: ")
        if confirm.strip() != "YES":
            print("Aborted.")
            return
        for month in months:
            rows = db.load_instances(month, DB_PATH)
            for row in rows:
                db.delete_instance(row["id"], DB_PATH)
        for d in defs:
            db.delete_definition(d["id"], DB_PATH)
        print("Wiped all instances and definitions.")

    else:
        print("Aborted.")


if __name__ == "__main__":
    wipe()
