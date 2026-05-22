"""
db.py — SQLite persistence layer for Money Tracker.

Two tables:
  bill_definitions  — master list of recurring/adhoc bill templates
  bill_instances    — one row per bill per month, generated from definitions
"""

import sqlite3
import calendar
from contextlib import contextmanager

DEFAULT_DB = "money_tracker.db"


@contextmanager
def _conn(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _row_to_dict(row):
    return dict(row)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db(db_path=DEFAULT_DB):
    """Create tables if they don't exist."""
    with _conn(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS bill_definitions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                sort_order     INTEGER NOT NULL DEFAULT 0,
                account        TEXT    NOT NULL DEFAULT '',
                description    TEXT    NOT NULL DEFAULT '',
                frequency      TEXT    NOT NULL DEFAULT 'Monthly',
                typical_amount REAL    NOT NULL DEFAULT 0,
                due_day        INTEGER NOT NULL DEFAULT 1,
                months_active  TEXT    NOT NULL DEFAULT '',
                adhoc_month    TEXT    NOT NULL DEFAULT '',
                active         INTEGER NOT NULL DEFAULT 1,
                notes          TEXT    NOT NULL DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS bill_instances (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                row_order      INTEGER NOT NULL,
                definition_id  INTEGER,
                month_key      TEXT    NOT NULL DEFAULT '',
                account        TEXT    NOT NULL DEFAULT '',
                description    TEXT    NOT NULL DEFAULT '',
                status         TEXT    NOT NULL DEFAULT 'Due',
                due_date       TEXT    NOT NULL DEFAULT '',
                amount         REAL    NOT NULL DEFAULT 0,
                frequency      TEXT    NOT NULL DEFAULT '',
                date_paid      TEXT    NOT NULL DEFAULT '',
                notes          TEXT    NOT NULL DEFAULT '',
                funded         INTEGER NOT NULL DEFAULT 0
            )
        """)
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN funded INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass


# ── Bill Definitions CRUD ─────────────────────────────────────────────────────

def load_definitions(db_path=DEFAULT_DB):
    """Return all definitions ordered by sort_order, id."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM bill_definitions ORDER BY sort_order, id"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert_definition(defn, db_path=DEFAULT_DB):
    """Insert a new definition. Returns the new id."""
    with _conn(db_path) as con:
        max_order = con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM bill_definitions"
        ).fetchone()[0]
        cur = con.execute("""
            INSERT INTO bill_definitions
                (sort_order, account, description, frequency, typical_amount,
                 due_day, months_active, adhoc_month, active, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            max_order + 1,
            defn.get("account", ""),
            defn.get("description", ""),
            defn.get("frequency", "Monthly"),
            defn.get("typical_amount", 0.0),
            defn.get("due_day", 1),
            defn.get("months_active", ""),
            defn.get("adhoc_month", ""),
            defn.get("notes", ""),
        ))
        return cur.lastrowid


def update_definition(defn_id, defn, db_path=DEFAULT_DB):
    """Update an existing definition by id."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_definitions
            SET account=?, description=?, frequency=?, typical_amount=?,
                due_day=?, months_active=?, adhoc_month=?, active=?, notes=?
            WHERE id=?
        """, (
            defn.get("account", ""),
            defn.get("description", ""),
            defn.get("frequency", "Monthly"),
            defn.get("typical_amount", 0.0),
            defn.get("due_day", 1),
            defn.get("months_active", ""),
            defn.get("adhoc_month", ""),
            defn.get("active", 1),
            defn.get("notes", ""),
            defn_id,
        ))


def delete_definition(defn_id, db_path=DEFAULT_DB):
    """Delete a definition. Existing instances are kept (historical data)."""
    with _conn(db_path) as con:
        con.execute("DELETE FROM bill_definitions WHERE id=?", (defn_id,))


# ── Bill Instances CRUD ───────────────────────────────────────────────────────

def load_instances(month_key, db_path=DEFAULT_DB):
    """Return all instances for a month ordered by due_date, row_order."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM bill_instances WHERE month_key=? ORDER BY due_date, row_order",
            (month_key,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert_instance(instance, db_path=DEFAULT_DB):
    """Insert a one-off instance for a specific month. Returns the new id."""
    with _conn(db_path) as con:
        max_order = con.execute(
            "SELECT COALESCE(MAX(row_order), 0) FROM bill_instances WHERE month_key=?",
            (instance.get("month_key", ""),)
        ).fetchone()[0]
        cur = con.execute("""
            INSERT INTO bill_instances
                (row_order, definition_id, month_key, account, description,
                 status, due_date, amount, frequency, date_paid, notes, funded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            max_order + 1,
            instance.get("definition_id"),
            instance.get("month_key", ""),
            instance.get("account", ""),
            instance.get("description", ""),
            instance.get("status", "Due"),
            instance.get("due_date", ""),
            instance.get("amount", 0.0),
            instance.get("frequency", ""),
            instance.get("date_paid", ""),
            instance.get("notes", ""),
            instance.get("funded", 0),
        ))
        return cur.lastrowid


def update_instance(instance_id, instance, db_path=DEFAULT_DB):
    """Update editable fields of an instance by id."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_instances
            SET account=?, description=?, status=?, due_date=?,
                amount=?, frequency=?, date_paid=?, notes=?, funded=?
            WHERE id=?
        """, (
            instance.get("account", ""),
            instance.get("description", ""),
            instance.get("status", "Due"),
            instance.get("due_date", ""),
            instance.get("amount", 0.0),
            instance.get("frequency", ""),
            instance.get("date_paid", ""),
            instance.get("notes", ""),
            instance.get("funded", 0),
            instance_id,
        ))


def delete_instance(instance_id, db_path=DEFAULT_DB):
    """Delete an instance and renormalise row_order within its month."""
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT month_key FROM bill_instances WHERE id=?", (instance_id,)
        ).fetchone()
        if not row:
            return
        month_key = row["month_key"]
        con.execute("DELETE FROM bill_instances WHERE id=?", (instance_id,))
        rows = con.execute(
            "SELECT id FROM bill_instances WHERE month_key=? ORDER BY row_order",
            (month_key,)
        ).fetchall()
        for i, r in enumerate(rows, start=1):
            con.execute("UPDATE bill_instances SET row_order=? WHERE id=?", (i, r["id"]))


# ── Month generation ──────────────────────────────────────────────────────────

def _should_include_definition(defn, year, month):
    """Return True if this definition applies to the given year/month."""
    freq = defn.get("frequency", "Monthly")
    if freq == "Monthly":
        return True
    if freq == "AdHoc":
        return defn.get("adhoc_month", "") == f"{year:04d}-{month:02d}"
    # Annual, Semi-Annual, Quarterly, etc. — check months_active
    months_str = defn.get("months_active", "")
    if not months_str:
        return False
    months = [int(m.strip()) for m in months_str.split(",") if m.strip().isdigit()]
    return month in months


def generate_month_instances(month_key, db_path=DEFAULT_DB):
    """
    Auto-generate bill instances for month_key from active definitions.
    Additive: skips definitions that already have an instance in this month.
    """
    year, month = map(int, month_key.split("-"))

    with _conn(db_path) as con:
        existing_def_ids = {
            r[0] for r in con.execute(
                "SELECT definition_id FROM bill_instances "
                "WHERE month_key=? AND definition_id IS NOT NULL",
                (month_key,)
            ).fetchall()
        }

        row_order = con.execute(
            "SELECT COALESCE(MAX(row_order), 0) FROM bill_instances WHERE month_key=?",
            (month_key,)
        ).fetchone()[0] + 1

        defs = con.execute(
            "SELECT * FROM bill_definitions WHERE active=1 ORDER BY sort_order, id"
        ).fetchall()

        for d in [dict(r) for r in defs]:
            if d["id"] in existing_def_ids:
                continue
            if not _should_include_definition(d, year, month):
                continue
            due_day = min(d.get("due_day", 1), calendar.monthrange(year, month)[1])
            due_date = f"{month:02d}/{due_day:02d}/{year}"
            con.execute("""
                INSERT INTO bill_instances
                    (row_order, definition_id, month_key, account, description,
                     status, due_date, amount, frequency, date_paid, notes)
                VALUES (?, ?, ?, ?, ?, 'Due', ?, ?, ?, '', '')
            """, (
                row_order, d["id"], month_key,
                d["account"], d["description"],
                due_date, d["typical_amount"], d["frequency"],
            ))
            row_order += 1


def get_months_with_instances(db_path=DEFAULT_DB):
    """Return sorted list of month_key strings that have at least one instance."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT DISTINCT month_key FROM bill_instances ORDER BY month_key"
        ).fetchall()
    return [r[0] for r in rows]
