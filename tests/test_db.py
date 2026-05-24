import os
import tempfile
import pytest
import db


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(path)
    yield path
    os.unlink(path)


def _defn(**kwargs):
    base = {
        "description":    "Test Bill",
        "frequency":      "Monthly",
        "typical_amount": 100.0,
        "due_day":        15,
        "months_active":  "",
        "adhoc_month":    "",
        "notes":          "",
    }
    base.update(kwargs)
    return base


def _inst(month_key="2026-06", **kwargs):
    base = {
        "definition_id": None,
        "month_key":     month_key,
        "description":   "Test Bill",
        "status":        "Due",
        "due_date":      "06/15/2026",
        "amount":        100.0,
        "frequency":     "Monthly",
        "date_paid":     "",
        "notes":         "",
    }
    base.update(kwargs)
    return base


# ── init_db ───────────────────────────────────────────────────────────────────

def test_init_creates_tables(tmp_db):
    assert db.load_definitions(tmp_db) == []
    assert db.load_instances("2026-06", tmp_db) == []


def test_init_idempotent(tmp_db):
    db.init_db(tmp_db)
    db.insert_definition(_defn(), tmp_db)
    db.init_db(tmp_db)
    assert len(db.load_definitions(tmp_db)) == 1


# ── bill_definitions ──────────────────────────────────────────────────────────

def test_insert_definition_returns_id(tmp_db):
    row_id = db.insert_definition(_defn(), tmp_db)
    assert isinstance(row_id, int) and row_id > 0


def test_insert_definition_stores_fields(tmp_db):
    db.insert_definition(_defn(
        description="Electric", frequency="Annual",
        typical_amount=85.50, due_day=5, months_active="3", adhoc_month="",
        notes="Annual spring bill"
    ), tmp_db)
    rows = db.load_definitions(tmp_db)
    r = rows[0]
    assert r["description"]    == "Electric"
    assert r["frequency"]      == "Annual"
    assert r["typical_amount"] == 85.50
    assert r["due_day"]        == 5
    assert r["months_active"]  == "3"
    assert r["notes"]          == "Annual spring bill"
    assert r["active"]         == 1


def test_insert_definition_sort_order_sequential(tmp_db):
    for _ in range(3):
        db.insert_definition(_defn(), tmp_db)
    rows = db.load_definitions(tmp_db)
    orders = [r["sort_order"] for r in rows]
    assert orders == [1, 2, 3]


def test_update_definition(tmp_db):
    row_id = db.insert_definition(_defn(description="Original", typical_amount=50.0), tmp_db)
    db.update_definition(row_id, _defn(description="Updated", typical_amount=75.0), tmp_db)
    rows = db.load_definitions(tmp_db)
    assert rows[0]["description"]    == "Updated"
    assert rows[0]["typical_amount"] == 75.0


def test_update_definition_active_flag(tmp_db):
    row_id = db.insert_definition(_defn(), tmp_db)
    d = db.load_definitions(tmp_db)[0]
    d["active"] = 0
    db.update_definition(row_id, d, tmp_db)
    assert db.load_definitions(tmp_db)[0]["active"] == 0


def test_delete_definition(tmp_db):
    row_id = db.insert_definition(_defn(), tmp_db)
    db.delete_definition(row_id, tmp_db)
    assert db.load_definitions(tmp_db) == []


def test_delete_definition_leaves_instances(tmp_db):
    defn_id = db.insert_definition(_defn(), tmp_db)
    db.insert_instance(_inst(definition_id=defn_id), tmp_db)
    db.delete_definition(defn_id, tmp_db)
    # Definition gone, instance stays
    assert db.load_definitions(tmp_db) == []
    assert len(db.load_instances("2026-06", tmp_db)) == 1


# ── bill_instances ────────────────────────────────────────────────────────────

def test_insert_instance_returns_id(tmp_db):
    row_id = db.insert_instance(_inst(), tmp_db)
    assert isinstance(row_id, int) and row_id > 0


def test_insert_instance_stores_fields(tmp_db):
    db.insert_instance(_inst(
        description="Health", status="Paid",
        due_date="06/01/2026", amount=85.50, frequency="Monthly",
        date_paid="05/28/2026", notes="Auto pay"
    ), tmp_db)
    rows = db.load_instances("2026-06", tmp_db)
    r = rows[0]
    assert r["description"] == "Health"
    assert r["status"]      == "Paid"
    assert r["due_date"]    == "06/01/2026"
    assert r["amount"]      == 85.50
    assert r["date_paid"]   == "05/28/2026"
    assert r["notes"]       == "Auto pay"


def test_insert_instance_row_order_per_month(tmp_db):
    for i in range(3):
        db.insert_instance(_inst(month_key="2026-06", amount=float(i)), tmp_db)
    rows = db.load_instances("2026-06", tmp_db)
    assert [r["row_order"] for r in rows] == [1, 2, 3]


def test_load_instances_isolated_by_month(tmp_db):
    db.insert_instance(_inst(month_key="2026-05", amount=10.0), tmp_db)
    db.insert_instance(_inst(month_key="2026-06", amount=20.0), tmp_db)
    assert len(db.load_instances("2026-05", tmp_db)) == 1
    assert len(db.load_instances("2026-06", tmp_db)) == 1
    assert db.load_instances("2026-07", tmp_db) == []


def test_update_instance_changes_fields(tmp_db):
    row_id = db.insert_instance(_inst(amount=100.0, description="Original"), tmp_db)
    db.update_instance(row_id, _inst(amount=999.0, description="Updated"), tmp_db)
    rows = db.load_instances("2026-06", tmp_db)
    assert rows[0]["amount"]      == 999.0
    assert rows[0]["description"] == "Updated"


def test_update_instance_to_paid(tmp_db):
    row_id = db.insert_instance(_inst(status="Due"), tmp_db)
    db.update_instance(row_id, _inst(status="Paid", date_paid="05/21/2026"), tmp_db)
    rows = db.load_instances("2026-06", tmp_db)
    assert rows[0]["status"]    == "Paid"
    assert rows[0]["date_paid"] == "05/21/2026"


def test_delete_instance_removes_row(tmp_db):
    row_id = db.insert_instance(_inst(), tmp_db)
    db.delete_instance(row_id, tmp_db)
    assert db.load_instances("2026-06", tmp_db) == []


def test_delete_instance_renormalises_row_order(tmp_db):
    id1 = db.insert_instance(_inst(amount=1.0), tmp_db)
    db.insert_instance(_inst(amount=2.0), tmp_db)
    db.insert_instance(_inst(amount=3.0), tmp_db)
    db.delete_instance(id1, tmp_db)
    rows = db.load_instances("2026-06", tmp_db)
    assert [r["row_order"] for r in rows] == [1, 2]
    assert [r["amount"] for r in rows]    == [2.0, 3.0]


# ── generate_month_instances ──────────────────────────────────────────────────

def test_generate_creates_monthly_instances(tmp_db):
    db.insert_definition(_defn(frequency="Monthly", typical_amount=50.0, due_day=15), tmp_db)
    db.generate_month_instances("2026-07", tmp_db)
    rows = db.load_instances("2026-07", tmp_db)
    assert len(rows) == 1
    assert rows[0]["amount"]  == 50.0
    assert rows[0]["due_date"] == "07/15/2026"
    assert rows[0]["status"]   == "Due"


def test_generate_adhoc_only_in_target_month(tmp_db):
    db.insert_definition(_defn(frequency="AdHoc", adhoc_month="2026-06"), tmp_db)
    db.generate_month_instances("2026-06", tmp_db)
    db.generate_month_instances("2026-07", tmp_db)
    assert len(db.load_instances("2026-06", tmp_db)) == 1
    assert len(db.load_instances("2026-07", tmp_db)) == 0


def test_generate_annual_only_in_correct_month(tmp_db):
    db.insert_definition(_defn(frequency="Annual", months_active="3", due_day=1), tmp_db)
    db.generate_month_instances("2026-03", tmp_db)
    db.generate_month_instances("2026-06", tmp_db)
    assert len(db.load_instances("2026-03", tmp_db)) == 1
    assert len(db.load_instances("2026-06", tmp_db)) == 0


def test_generate_semi_annual(tmp_db):
    db.insert_definition(_defn(frequency="Semi-Annual", months_active="3,9", due_day=1), tmp_db)
    db.generate_month_instances("2026-03", tmp_db)
    db.generate_month_instances("2026-06", tmp_db)
    db.generate_month_instances("2026-09", tmp_db)
    assert len(db.load_instances("2026-03", tmp_db)) == 1
    assert len(db.load_instances("2026-06", tmp_db)) == 0
    assert len(db.load_instances("2026-09", tmp_db)) == 1


def test_generate_is_idempotent(tmp_db):
    db.insert_definition(_defn(), tmp_db)
    db.generate_month_instances("2026-06", tmp_db)
    db.generate_month_instances("2026-06", tmp_db)  # second call is no-op
    assert len(db.load_instances("2026-06", tmp_db)) == 1


def test_generate_skips_inactive_definitions(tmp_db):
    defn_id = db.insert_definition(_defn(), tmp_db)
    d = db.load_definitions(tmp_db)[0]
    d["active"] = 0
    db.update_definition(defn_id, d, tmp_db)
    db.generate_month_instances("2026-06", tmp_db)
    assert db.load_instances("2026-06", tmp_db) == []


def test_generate_clamps_due_day_to_month_end(tmp_db):
    db.insert_definition(_defn(due_day=31), tmp_db)
    db.generate_month_instances("2026-02", tmp_db)
    rows = db.load_instances("2026-02", tmp_db)
    assert rows[0]["due_date"] == "02/28/2026"


# ── get_months_with_instances ─────────────────────────────────────────────────

def test_get_months_empty(tmp_db):
    assert db.get_months_with_instances(tmp_db) == []


def test_get_months_returns_sorted(tmp_db):
    db.insert_instance(_inst(month_key="2026-08"), tmp_db)
    db.insert_instance(_inst(month_key="2026-06"), tmp_db)
    db.insert_instance(_inst(month_key="2026-07"), tmp_db)
    assert db.get_months_with_instances(tmp_db) == ["2026-06", "2026-07", "2026-08"]


def test_get_months_no_duplicates(tmp_db):
    db.insert_instance(_inst(month_key="2026-06", amount=1.0), tmp_db)
    db.insert_instance(_inst(month_key="2026-06", amount=2.0), tmp_db)
    assert db.get_months_with_instances(tmp_db) == ["2026-06"]


# ── get_funded_not_paid_total ─────────────────────────────────────────────────

def _txn(**kwargs):
    base = {
        "date":               "05/24/2026",
        "description":        "Test Txn",
        "type":               "Payment",
        "amount":             100.0,
        "notes":              "",
        "transaction_number": "",
        "memo":               "",
        "check_number":       "",
        "bank_balance":       None,
    }
    base.update(kwargs)
    return base


def test_funded_not_paid_empty(tmp_db):
    assert db.get_funded_not_paid_total(tmp_db) == 0.0


def test_funded_not_paid_sums_due_funded(tmp_db):
    db.insert_instance(_inst(amount=200.0, funded=1, status="Due"), tmp_db)
    db.insert_instance(_inst(amount=150.0, funded=1, status="Due"), tmp_db)
    assert db.get_funded_not_paid_total(tmp_db) == 350.0


def test_funded_not_paid_ignores_paid(tmp_db):
    db.insert_instance(_inst(amount=200.0, funded=1, status="Paid"), tmp_db)
    assert db.get_funded_not_paid_total(tmp_db) == 0.0


def test_funded_not_paid_ignores_unfunded(tmp_db):
    db.insert_instance(_inst(amount=200.0, funded=0, status="Due"), tmp_db)
    assert db.get_funded_not_paid_total(tmp_db) == 0.0


# ── get_safe2spend ────────────────────────────────────────────────────────────

def test_safe2spend_no_data(tmp_db):
    assert db.get_safe2spend(tmp_db) == 0.0


def test_safe2spend_balance_no_funded_bills(tmp_db):
    db.insert_transaction(_txn(bank_balance=1000.0), tmp_db)
    assert db.get_safe2spend(tmp_db) == 1000.0


def test_safe2spend_funded_bills_no_balance(tmp_db):
    db.insert_instance(_inst(amount=300.0, funded=1, status="Due"), tmp_db)
    assert db.get_safe2spend(tmp_db) == -300.0


def test_safe2spend_balance_minus_funded(tmp_db):
    db.insert_transaction(_txn(bank_balance=1000.0), tmp_db)
    db.insert_instance(_inst(amount=300.0, funded=1, status="Due"), tmp_db)
    assert db.get_safe2spend(tmp_db) == 700.0


def test_safe2spend_uses_most_recent_bank_balance(tmp_db):
    db.insert_transaction(_txn(date="05/01/2026", bank_balance=500.0), tmp_db)
    db.insert_transaction(_txn(date="05/24/2026", bank_balance=300.0), tmp_db)
    assert db.get_safe2spend(tmp_db) == 300.0


def test_safe2spend_paid_bills_not_deducted(tmp_db):
    db.insert_transaction(_txn(bank_balance=1000.0), tmp_db)
    db.insert_instance(_inst(amount=400.0, funded=1, status="Paid"), tmp_db)
    assert db.get_safe2spend(tmp_db) == 1000.0
