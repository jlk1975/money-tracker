"""
db.py — SQLite persistence layer for Money Tracker.

Two tables:
  bill_definitions  — master list of recurring/adhoc bill templates
  bill_instances    — one row per bill per month, generated from definitions
"""

import os
import sqlite3
import calendar
from contextlib import contextmanager
from datetime import date

DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".local", "share", "money-tracker", "money_tracker.db")


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
                description    TEXT    NOT NULL DEFAULT '',
                frequency      TEXT    NOT NULL DEFAULT 'Monthly',
                typical_amount REAL    NOT NULL DEFAULT 0,
                due_day        INTEGER NOT NULL DEFAULT 1,
                months_active  TEXT    NOT NULL DEFAULT '',
                adhoc_month    TEXT    NOT NULL DEFAULT '',
                active         INTEGER NOT NULL DEFAULT 1,
                notes          TEXT    NOT NULL DEFAULT '',
                payment_mode   TEXT    NOT NULL DEFAULT '',
                vibe           TEXT    NOT NULL DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS bill_instances (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                row_order      INTEGER NOT NULL,
                definition_id  INTEGER,
                month_key      TEXT    NOT NULL DEFAULT '',
                description    TEXT    NOT NULL DEFAULT '',
                status         TEXT    NOT NULL DEFAULT 'Due',
                due_date       TEXT    NOT NULL DEFAULT '',
                amount         REAL    NOT NULL DEFAULT 0,
                frequency      TEXT    NOT NULL DEFAULT '',
                date_paid      TEXT    NOT NULL DEFAULT '',
                notes          TEXT    NOT NULL DEFAULT '',
                funded         INTEGER NOT NULL DEFAULT 0,
                payment_mode   TEXT    NOT NULL DEFAULT '',
                vibe           TEXT    NOT NULL DEFAULT ''
            )
        """)
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN funded INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_definitions ADD COLUMN payment_mode TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN payment_mode TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_definitions ADD COLUMN vibe TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN vibe TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS debts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sort_order      INTEGER NOT NULL DEFAULT 0,
                name            TEXT    NOT NULL DEFAULT '',
                interest_rate   REAL    NOT NULL DEFAULT 0,
                monthly_payment REAL    NOT NULL DEFAULT 0,
                payoff_date     TEXT    NOT NULL DEFAULT '',
                notes           TEXT    NOT NULL DEFAULT ''
            )
        """)
        try:
            con.execute("ALTER TABLE debts ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS debt_balances (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id   INTEGER NOT NULL,
                month_key TEXT    NOT NULL,
                balance   REAL    NOT NULL DEFAULT 0,
                UNIQUE(debt_id, month_key)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS register_transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                type        TEXT    NOT NULL DEFAULT 'Payment',
                amount      REAL    NOT NULL DEFAULT 0,
                notes       TEXT    NOT NULL DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_settings (
                id               INTEGER PRIMARY KEY DEFAULT 1,
                account_name     TEXT    NOT NULL DEFAULT '',
                starting_balance REAL    NOT NULL DEFAULT 0,
                as_of_date       TEXT    NOT NULL DEFAULT ''
            )
        """)
        try:
            con.execute(
                "ALTER TABLE register_transactions ADD COLUMN transaction_number TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE register_transactions ADD COLUMN memo TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE register_transactions ADD COLUMN check_number TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE register_transactions ADD COLUMN bank_balance REAL"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE register_transactions ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN transaction_id INTEGER REFERENCES register_transactions(id)"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE bill_instances ADD COLUMN soft_pay INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
        try:
            con.execute(
                "ALTER TABLE account_settings ADD COLUMN buffer REAL NOT NULL DEFAULT 0.0"
            )
        except Exception:
            pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL DEFAULT '',
                category   TEXT    NOT NULL DEFAULT 'Cash',
                active     INTEGER NOT NULL DEFAULT 1,
                debt_id    INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS account_balances (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                date       TEXT    NOT NULL DEFAULT '',
                balance    REAL    NOT NULL DEFAULT 0
            )
        """)
        for col, definition in [
            ("nw_start_date",      "TEXT NOT NULL DEFAULT ''"),
            ("cash_goal",          "REAL NOT NULL DEFAULT 0"),
            ("investment_haircut", "REAL NOT NULL DEFAULT 0.65"),
        ]:
            try:
                con.execute(f"ALTER TABLE account_settings ADD COLUMN {col} {definition}")
            except Exception:
                pass
        try:
            con.execute(
                "ALTER TABLE accounts ADD COLUMN register_linked INTEGER NOT NULL DEFAULT 0"
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
                (sort_order, description, frequency, typical_amount,
                 due_day, months_active, adhoc_month, active, notes, payment_mode, vibe)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (
            max_order + 1,
            defn.get("description", ""),
            defn.get("frequency", "Monthly"),
            defn.get("typical_amount", 0.0),
            defn.get("due_day", 1),
            defn.get("months_active", ""),
            defn.get("adhoc_month", ""),
            defn.get("notes", ""),
            defn.get("payment_mode", ""),
            defn.get("vibe", ""),
        ))
        return cur.lastrowid


def update_definition(defn_id, defn, db_path=DEFAULT_DB):
    """Update an existing definition by id."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_definitions
            SET description=?, frequency=?, typical_amount=?,
                due_day=?, months_active=?, adhoc_month=?, active=?, notes=?, payment_mode=?, vibe=?
            WHERE id=?
        """, (
            defn.get("description", ""),
            defn.get("frequency", "Monthly"),
            defn.get("typical_amount", 0.0),
            defn.get("due_day", 1),
            defn.get("months_active", ""),
            defn.get("adhoc_month", ""),
            defn.get("active", 1),
            defn.get("notes", ""),
            defn.get("payment_mode", ""),
            defn.get("vibe", ""),
            defn_id,
        ))
        con.execute(
            "UPDATE bill_instances SET payment_mode=?, vibe=? WHERE definition_id=?",
            (defn.get("payment_mode", ""), defn.get("vibe", ""), defn_id)
        )


def delete_definition(defn_id, db_path=DEFAULT_DB):
    """Delete a definition. Existing instances are kept (historical data)."""
    with _conn(db_path) as con:
        con.execute("DELETE FROM bill_definitions WHERE id=?", (defn_id,))


# ── Bill Instances CRUD ───────────────────────────────────────────────────────

def load_instances(month_key, db_path=DEFAULT_DB):
    """Return all instances for a month ordered by due_date, row_order."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM bill_instances WHERE month_key=? AND deleted=0 ORDER BY due_date, row_order",
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
                (row_order, definition_id, month_key, description,
                 status, due_date, amount, frequency, date_paid, notes, funded, payment_mode, vibe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            max_order + 1,
            instance.get("definition_id"),
            instance.get("month_key", ""),
            instance.get("description", ""),
            instance.get("status", "Due"),
            instance.get("due_date", ""),
            instance.get("amount", 0.0),
            instance.get("frequency", ""),
            instance.get("date_paid", ""),
            instance.get("notes", ""),
            instance.get("funded", 0),
            instance.get("payment_mode", ""),
            instance.get("vibe", ""),
        ))
        return cur.lastrowid


def update_instance(instance_id, instance, db_path=DEFAULT_DB):
    """Update editable fields of an instance by id."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_instances
            SET description=?, status=?, month_key=?, due_date=?,
                amount=?, frequency=?, date_paid=?, notes=?, funded=?, payment_mode=?, vibe=?
            WHERE id=?
        """, (
            instance.get("description", ""),
            instance.get("status", "Due"),
            instance.get("month_key", ""),
            instance.get("due_date", ""),
            instance.get("amount", 0.0),
            instance.get("frequency", ""),
            instance.get("date_paid", ""),
            instance.get("notes", ""),
            instance.get("funded", 0),
            instance.get("payment_mode", ""),
            instance.get("vibe", ""),
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
        con.execute("UPDATE bill_instances SET deleted=1 WHERE id=?", (instance_id,))
        rows = con.execute(
            "SELECT id FROM bill_instances WHERE month_key=? AND deleted=0 ORDER BY row_order",
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
                    (row_order, definition_id, month_key, description,
                     status, due_date, amount, frequency, date_paid, notes, payment_mode, vibe)
                VALUES (?, ?, ?, ?, 'Due', ?, ?, ?, '', '', ?, ?)
            """, (
                row_order, d["id"], month_key,
                d["description"],
                due_date, d["typical_amount"], d["frequency"],
                d.get("payment_mode", ""),
                d.get("vibe", ""),
            ))
            row_order += 1


def get_months_with_instances(db_path=DEFAULT_DB):
    """Return sorted list of month_key strings that have at least one instance."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT DISTINCT month_key FROM bill_instances ORDER BY month_key"
        ).fetchall()
    return [r[0] for r in rows]


# ── Debt CRUD ─────────────────────────────────────────────────────────────────

def load_debts(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM debts ORDER BY sort_order, id"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert_debt(debt, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        max_order = con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM debts"
        ).fetchone()[0]
        cur = con.execute("""
            INSERT INTO debts (sort_order, name, interest_rate, monthly_payment, payoff_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            max_order + 1,
            debt.get("name", ""),
            debt.get("interest_rate", 0.0),
            debt.get("monthly_payment", 0.0),
            debt.get("payoff_date", ""),
            debt.get("notes", ""),
        ))
        return cur.lastrowid


def update_debt(debt_id, debt, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute("""
            UPDATE debts SET name=?, interest_rate=?, monthly_payment=?, payoff_date=?, notes=?
            WHERE id=?
        """, (
            debt.get("name", ""),
            debt.get("interest_rate", 0.0),
            debt.get("monthly_payment", 0.0),
            debt.get("payoff_date", ""),
            debt.get("notes", ""),
            debt_id,
        ))


def delete_debt(debt_id, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute("DELETE FROM debt_balances WHERE debt_id=?", (debt_id,))
        con.execute("DELETE FROM debts WHERE id=?", (debt_id,))


def set_debt_balance(debt_id, month_key, balance, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute("""
            INSERT OR REPLACE INTO debt_balances (debt_id, month_key, balance)
            VALUES (?, ?, ?)
        """, (debt_id, month_key, balance))


def get_all_debt_balances(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT debt_id, month_key, balance FROM debt_balances ORDER BY month_key"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_debt_account_balances(db_path=DEFAULT_DB):
    """Return latest balance per CC/Loan account per month as {account_id, month_key, balance}."""
    with _conn(db_path) as con:
        rows = con.execute("""
            SELECT ab.account_id,
                   substr(ab.date, 7, 4) || '-' || substr(ab.date, 1, 2) AS month_key,
                   ab.balance
            FROM account_balances ab
            JOIN accounts a ON a.id = ab.account_id
            WHERE a.category IN ('Credit Cards', 'Loans') AND a.active = 1
            ORDER BY ab.account_id, month_key, ab.id
        """).fetchall()
    # Keep only the last entry per (account_id, month_key)
    seen = {}
    for r in rows:
        d = _row_to_dict(r)
        seen[(d["account_id"], d["month_key"])] = d
    return sorted(seen.values(), key=lambda x: x["month_key"])


# ── Register CRUD ─────────────────────────────────────────────────────────────

def load_transactions(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        rows = con.execute("""
            SELECT rt.*,
                   (SELECT bi.description FROM bill_instances bi
                    WHERE bi.transaction_id = rt.id AND bi.deleted = 0 LIMIT 1) AS bill_description,
                   (SELECT bi.id FROM bill_instances bi
                    WHERE bi.transaction_id = rt.id AND bi.deleted = 0 LIMIT 1) AS bill_instance_id
            FROM register_transactions rt
            ORDER BY rt.date, rt.id
        """).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert_transaction(txn, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        cur = con.execute("""
            INSERT INTO register_transactions
                (date, description, type, amount, notes, transaction_number,
                 memo, check_number, bank_balance, reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            txn.get("date", ""),
            txn.get("description", ""),
            txn.get("type", "Payment"),
            txn.get("amount", 0.0),
            txn.get("notes", ""),
            txn.get("transaction_number", ""),
            txn.get("memo", ""),
            txn.get("check_number", ""),
            txn.get("bank_balance"),
        ))
        return cur.lastrowid


def get_account_settings(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        row = con.execute("SELECT * FROM account_settings WHERE id=1").fetchone()
    if row:
        return _row_to_dict(row)
    return {"account_name": "", "starting_balance": 0.0, "as_of_date": ""}


def set_account_settings(settings, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute("""
            INSERT OR REPLACE INTO account_settings (id, account_name, starting_balance, as_of_date)
            VALUES (1, ?, ?, ?)
        """, (
            settings.get("account_name", ""),
            settings.get("starting_balance", 0.0),
            settings.get("as_of_date", ""),
        ))


# ── Register / Linking helpers ────────────────────────────────────────────────

def toggle_reviewed(txn_id, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute(
            "UPDATE register_transactions SET reviewed = CASE WHEN reviewed=1 THEN 0 ELSE 1 END WHERE id=?",
            (txn_id,)
        )


def get_imported_transaction_keys(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT transaction_number, date FROM register_transactions WHERE transaction_number != ''"
        ).fetchall()
    return {(r[0], r[1]) for r in rows}


def get_transaction_count(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        return con.execute("SELECT COUNT(*) FROM register_transactions").fetchone()[0]


def get_transaction_fingerprints(db_path=DEFAULT_DB):
    """Return a set of (date, type, amount, description) tuples for rows without a transaction_number.
    Used to deduplicate CSV rows that lack a bank-assigned transaction ID."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT date, type, amount, description FROM register_transactions WHERE transaction_number = ''"
        ).fetchall()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


def load_linkable_instances(db_path=DEFAULT_DB):
    """Return all unlinked, unpaid, non-deleted bill instances across all months.

    Sorted so current and past months appear first (most recent first), followed
    by future months (nearest first), so the most relevant bills are at the top.
    """
    today_month = date.today().strftime("%Y-%m")

    def _sort_key(inst):
        mk = inst["month_key"]
        y, m = map(int, mk.split("-"))
        ordinal = y * 12 + m
        if mk <= today_month:
            # past/current: most recent first (negate ordinal)
            return (0, -ordinal, inst.get("row_order", 0))
        else:
            # future: nearest first
            return (1, ordinal, inst.get("row_order", 0))

    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM bill_instances "
            "WHERE transaction_id IS NULL AND status='Due' AND deleted=0"
        ).fetchall()
    instances = [_row_to_dict(r) for r in rows]
    instances.sort(key=_sort_key)
    return instances


def link_bill_to_transaction(instance_id, transaction_id, db_path=DEFAULT_DB):
    """Link a bill instance to a transaction; auto-funds and auto-pays the bill."""
    today = date.today().strftime("%m/%d/%Y")
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_instances
            SET transaction_id=?, funded=1, status='Paid', date_paid=?, soft_pay=0
            WHERE id=?
        """, (transaction_id, today, instance_id))


def unlink_transaction(instance_id, db_path=DEFAULT_DB):
    """Remove bill link and revert instance to Due / unfunded."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_instances
            SET transaction_id=NULL, status='Due', funded=0, date_paid=''
            WHERE id=?
        """, (instance_id,))


def toggle_soft_pay(instance_id, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute(
            "UPDATE bill_instances SET soft_pay = CASE WHEN soft_pay=1 THEN 0 ELSE 1 END WHERE id=?",
            (instance_id,)
        )


def get_funded_not_paid_total(db_path=DEFAULT_DB):
    """Sum of amount for all funded, unpaid, non-deleted bill instances across all months."""
    with _conn(db_path) as con:
        row = con.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bill_instances "
            "WHERE funded=1 AND status='Due' AND deleted=0"
        ).fetchone()
    return row[0] if row else 0.0


def get_safe2spend(db_path=DEFAULT_DB):
    """Compute Safe2Spend = current_balance - funded_not_yet_paid."""
    with _conn(db_path) as con:
        row = con.execute("""
            SELECT bank_balance FROM register_transactions
            WHERE bank_balance IS NOT NULL
            ORDER BY SUBSTR(date,7,4) DESC,
                     SUBSTR(date,1,2) DESC,
                     SUBSTR(date,4,2) DESC,
                     CAST(transaction_number AS INTEGER) DESC,
                     id DESC
            LIMIT 1
        """).fetchone()
        balance = row["bank_balance"] if row else 0.0
        funded_not_paid = con.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bill_instances "
            "WHERE funded=1 AND status='Due' AND deleted=0"
        ).fetchone()[0] or 0.0
    return balance - funded_not_paid


def delete_all_transactions(db_path=DEFAULT_DB):
    """Delete all transactions and revert any linked bill instances to unpaid/unfunded."""
    with _conn(db_path) as con:
        con.execute("""
            UPDATE bill_instances
            SET status='Due', transaction_id=NULL, funded=0, date_paid=''
            WHERE transaction_id IS NOT NULL
        """)
        con.execute("DELETE FROM register_transactions")


# ── Accounts CRUD ─────────────────────────────────────────────────────────────

def get_accounts(db_path=DEFAULT_DB):
    """Return all accounts with latest balance, date, and linked debt fields."""
    with _conn(db_path) as con:
        accounts = con.execute("""
            SELECT a.*,
                   d.interest_rate  AS debt_interest_rate,
                   d.monthly_payment AS debt_monthly_payment,
                   d.payoff_date    AS debt_payoff_date
            FROM accounts a
            LEFT JOIN debts d ON d.id = a.debt_id
            ORDER BY a.sort_order, a.id
        """).fetchall()
        result = []
        for a in accounts:
            row = _row_to_dict(a)
            latest = con.execute(
                "SELECT balance, date FROM account_balances "
                "WHERE account_id=? ORDER BY date DESC, id DESC LIMIT 1",
                (a["id"],)
            ).fetchone()
            row["latest_balance"] = latest["balance"] if latest else None
            row["latest_date"]    = latest["date"]    if latest else None
            result.append(row)
    return result


def insert_account(account, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        max_order = con.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM accounts"
        ).fetchone()[0]
        if account.get("register_linked"):
            con.execute("UPDATE accounts SET register_linked=0")
        cur = con.execute("""
            INSERT INTO accounts (name, category, active, debt_id, sort_order, register_linked)
            VALUES (?, ?, 1, ?, ?, ?)
        """, (
            account.get("name", ""),
            account.get("category", "Cash"),
            account.get("debt_id"),
            max_order + 1,
            1 if account.get("register_linked") else 0,
        ))
        return cur.lastrowid


def update_account(account_id, account, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        if account.get("register_linked"):
            con.execute("UPDATE accounts SET register_linked=0 WHERE id!=?", (account_id,))
        con.execute("""
            UPDATE accounts SET name=?, category=?, active=?, debt_id=?, register_linked=?
            WHERE id=?
        """, (
            account.get("name", ""),
            account.get("category", "Cash"),
            account.get("active", 1),
            account.get("debt_id"),
            1 if account.get("register_linked") else 0,
            account_id,
        ))


def sync_register_account(db_path=DEFAULT_DB):
    """Auto-update the register-linked account's balance from the latest bank_balance.

    Writes one account_balances entry per calendar day — overwrites today's
    entry if it already exists so repeated refreshes don't accumulate duplicates.
    Does nothing if no account is marked register_linked or the register has no
    bank_balance rows.
    """
    today = date.today().strftime("%m/%d/%Y")
    with _conn(db_path) as con:
        acct = con.execute(
            "SELECT id FROM accounts WHERE register_linked=1 LIMIT 1"
        ).fetchone()
        if not acct:
            return
        account_id = acct["id"]

        bal_row = con.execute("""
            SELECT bank_balance FROM register_transactions
            WHERE bank_balance IS NOT NULL
            ORDER BY SUBSTR(date,7,4) DESC,
                     SUBSTR(date,1,2) DESC,
                     SUBSTR(date,4,2) DESC,
                     CAST(transaction_number AS INTEGER) DESC,
                     id DESC
            LIMIT 1
        """).fetchone()
        if not bal_row:
            return
        balance = bal_row["bank_balance"]

        existing = con.execute(
            "SELECT id FROM account_balances WHERE account_id=? AND date=?",
            (account_id, today)
        ).fetchone()
        if existing:
            con.execute(
                "UPDATE account_balances SET balance=? WHERE id=?",
                (balance, existing["id"])
            )
        else:
            con.execute(
                "INSERT INTO account_balances (account_id, date, balance) VALUES (?, ?, ?)",
                (account_id, today, balance)
            )


def delete_account(account_id, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        row = con.execute("SELECT debt_id FROM accounts WHERE id=?", (account_id,)).fetchone()
        con.execute("DELETE FROM account_balances WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        if row and row["debt_id"]:
            con.execute("DELETE FROM debt_balances WHERE debt_id=?", (row["debt_id"],))
            con.execute("DELETE FROM debts WHERE id=?", (row["debt_id"],))


def log_account_balance(account_id, entry_date, balance, db_path=DEFAULT_DB):
    """Insert a balance snapshot; also writes back to debt_balances if account is debt-linked."""
    with _conn(db_path) as con:
        con.execute(
            "INSERT INTO account_balances (account_id, date, balance) VALUES (?, ?, ?)",
            (account_id, entry_date, balance)
        )
        row = con.execute(
            "SELECT debt_id FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if row and row["debt_id"]:
            parts = entry_date.split("/")
            month_key = f"{parts[2]}-{parts[0]}"
            con.execute(
                "INSERT OR REPLACE INTO debt_balances (debt_id, month_key, balance) VALUES (?, ?, ?)",
                (row["debt_id"], month_key, abs(balance))
            )


def get_account_balance_history(account_id, db_path=DEFAULT_DB):
    """Return full balance history for one account, oldest first."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT date, balance FROM account_balances WHERE account_id=? ORDER BY date, id",
            (account_id,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_nw_history(db_path=DEFAULT_DB):
    """Return list of {date, cash, investments, credit_cards, loans} for all snapshot dates."""
    from collections import defaultdict

    with _conn(db_path) as con:
        accounts = [_row_to_dict(r) for r in con.execute(
            "SELECT id, category FROM accounts WHERE active=1"
        ).fetchall()]
        balances = [_row_to_dict(r) for r in con.execute(
            "SELECT account_id, date, balance FROM account_balances ORDER BY date, id"
        ).fetchall()]

    if not balances or not accounts:
        return []

    account_map = {a["id"]: a["category"] for a in accounts}

    by_account = defaultdict(list)
    for b in balances:
        by_account[b["account_id"]].append((b["date"], b["balance"]))

    dates = sorted(set(b["date"] for b in balances))

    result = []
    for snap_date in dates:
        cash = investments = credit_cards = loans = 0.0
        for acc_id, category in account_map.items():
            relevant = [(d, bal) for d, bal in by_account.get(acc_id, []) if d <= snap_date]
            if not relevant:
                continue
            bal = sorted(relevant, key=lambda x: x[0])[-1][1]
            if category == "Cash":
                cash += bal
            elif category == "Investments":
                investments += bal
            elif category == "Credit Cards":
                credit_cards += bal
            elif category == "Loans":
                loans += bal
        result.append({
            "date": snap_date,
            "cash": cash,
            "investments": investments,
            "credit_cards": credit_cards,
            "loans": loans,
        })
    return result


# ── NW Settings ───────────────────────────────────────────────────────────────

def get_nw_settings(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        row = con.execute("SELECT * FROM account_settings WHERE id=1").fetchone()
    if row:
        d = _row_to_dict(row)
        return {
            "nw_start_date": d.get("nw_start_date", ""),
            "cash_goal":     d.get("cash_goal", 0.0),
        }
    return {"nw_start_date": "", "cash_goal": 0.0}


def set_nw_settings(settings, db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        con.execute("""
            INSERT INTO account_settings (id, nw_start_date, cash_goal)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nw_start_date = excluded.nw_start_date,
                cash_goal     = excluded.cash_goal
        """, (
            settings.get("nw_start_date", ""),
            settings.get("cash_goal", 0.0),
        ))
