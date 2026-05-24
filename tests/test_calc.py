import os
import tempfile
import pytest
import calc

TOLERANCE = 0.02


def _inst(**kwargs):
    base = {
        "id":          1,
        "description": "Test Bill",
        "status":      "Due",
        "due_date":    "06/15/2026",
        "amount":      100.0,
        "frequency":   "Monthly",
        "date_paid":   "",
        "notes":       "",
    }
    base.update(kwargs)
    return base


# ── annotate_instances ────────────────────────────────────────────────────────

def test_annotate_preserves_fields():
    result = calc.annotate_instances([_inst(description="Mortgage", amount=602.13)])
    assert result[0]["description"] == "Mortgage"
    assert result[0]["amount"]      == 602.13


def test_annotate_empty_list():
    assert calc.annotate_instances([]) == []


# ── calculate_summary ─────────────────────────────────────────────────────────

def test_summary_total_due():
    instances = calc.annotate_instances([
        _inst(amount=100.0, status="Due"),
        _inst(amount=200.0, status="Due"),
        _inst(amount=50.0,  status="Paid"),
    ])
    assert calc.calculate_summary(instances)["total_due"] == 300.0


def test_summary_total_paid():
    instances = calc.annotate_instances([
        _inst(amount=100.0, status="Due"),
        _inst(amount=75.0,  status="Paid"),
        _inst(amount=25.0,  status="Paid"),
    ])
    assert calc.calculate_summary(instances)["total_paid"] == 100.0


def test_summary_bill_count():
    instances = calc.annotate_instances([_inst() for _ in range(5)])
    assert calc.calculate_summary(instances)["bill_count"] == 5



def test_summary_empty():
    s = calc.calculate_summary([])
    assert s["total_due"]  == 0.0
    assert s["total_paid"] == 0.0
    assert s["bill_count"] == 0


# ── integration with sample definitions ──────────────────────────────────────

def test_june_total_from_sample_definitions():
    """All 19 definitions generate the correct June 2026 total."""
    import db
    from tests.fixtures import SAMPLE_DEFINITIONS, SAMPLE_JUNE_TOTAL

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(path)
    for defn in SAMPLE_DEFINITIONS:
        db.insert_definition(defn, path)
    db.generate_month_instances("2026-06", path)

    raw       = db.load_instances("2026-06", path)
    annotated = calc.annotate_instances(raw)
    s         = calc.calculate_summary(annotated)
    os.unlink(path)

    assert s["bill_count"] == 19
    assert abs(s["total_due"] - SAMPLE_JUNE_TOTAL) <= TOLERANCE


# ── funded_through_parts ──────────────────────────────────────────────────────
# Use 2099 dates so they are always in the future (>= today) and the function
# never filters them out as past-due.

MONTH = "2099-06"


def _fi(**kwargs):
    """Minimal instance dict for funded_through_parts tests."""
    base = {"status": "Due", "due_date": "06/15/2099", "funded": 0, "amount": 100.0}
    base.update(kwargs)
    return base


def test_funded_through_empty_returns_month_end():
    _, caption = calc.funded_through_parts([], MONTH)
    assert caption == "Funded through Jun 30"


def test_funded_through_all_paid_returns_month_end():
    instances = [_fi(status="Paid", due_date="06/10/2099")]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 30"


def test_funded_through_first_bill_unfunded():
    instances = [_fi(due_date="06/10/2099", funded=0)]
    days_str, caption = calc.funded_through_parts(instances, MONTH)
    assert days_str == "0 days"
    assert "not funded" in caption


def test_funded_through_single_funded_bill():
    instances = [_fi(due_date="06/10/2099", funded=1)]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 10"


def test_funded_through_stops_at_first_gap():
    instances = [
        _fi(due_date="06/10/2099", funded=1),
        _fi(due_date="06/20/2099", funded=0),
    ]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 10"


def test_funded_through_all_funded_multiple_dates():
    instances = [
        _fi(due_date="06/05/2099", funded=1),
        _fi(due_date="06/15/2099", funded=1),
        _fi(due_date="06/25/2099", funded=1),
    ]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 25"


def test_funded_through_same_date_group_partially_unfunded():
    """Two bills on the same date — one unfunded — blocks the whole group."""
    instances = [
        _fi(due_date="06/10/2099", funded=1),
        _fi(due_date="06/15/2099", funded=1),
        _fi(due_date="06/15/2099", funded=0),
        _fi(due_date="06/20/2099", funded=1),
    ]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 10"


def test_funded_through_paid_bills_skipped():
    """Paid bills don't count as upcoming; chain is evaluated over Due bills only."""
    instances = [
        _fi(due_date="06/01/2099", status="Paid", funded=0),
        _fi(due_date="06/10/2099", funded=1),
    ]
    _, caption = calc.funded_through_parts(instances, MONTH)
    assert caption == "Funded through Jun 10"


# ── integration with sample definitions ──────────────────────────────────────

def test_may_total_excludes_adhoc():
    """May 2026 gets only the 16 monthly bills — no AdHoc."""
    import db
    from tests.fixtures import SAMPLE_DEFINITIONS, SAMPLE_MAY_TOTAL

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(path)
    for defn in SAMPLE_DEFINITIONS:
        db.insert_definition(defn, path)
    db.generate_month_instances("2026-05", path)

    raw       = db.load_instances("2026-05", path)
    annotated = calc.annotate_instances(raw)
    s         = calc.calculate_summary(annotated)
    os.unlink(path)

    assert s["bill_count"] == 16
    assert abs(s["total_due"] - SAMPLE_MAY_TOTAL) <= TOLERANCE
