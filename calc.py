from datetime import date, datetime


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def annotate_instances(instances):
    """Add is_overdue and days_until_due to each instance. Returns a new list."""
    today = date.today()
    result = []
    for b in instances:
        due = _parse_date(b.get("due_date", ""))
        if due and b.get("status") == "Due":
            days_until = (due - today).days
            is_overdue = days_until < 0
        else:
            days_until = None
            is_overdue = False
        result.append({**b, "is_overdue": is_overdue, "days_until_due": days_until})
    return result


def calculate_summary(annotated_instances):
    """Return aggregate stats across all instances."""
    total_due  = sum(b["amount"] for b in annotated_instances if b.get("status") == "Due")
    total_paid = sum(b["amount"] for b in annotated_instances if b.get("status") == "Paid")
    overdue    = [b for b in annotated_instances if b.get("is_overdue")]

    by_account = {}
    for b in annotated_instances:
        acct = b.get("account") or "Unknown"
        if acct not in by_account:
            by_account[acct] = {"due": 0.0, "paid": 0.0}
        if b.get("status") == "Due":
            by_account[acct]["due"]  += b.get("amount", 0.0)
        else:
            by_account[acct]["paid"] += b.get("amount", 0.0)

    return {
        "total_due":      total_due,
        "total_paid":     total_paid,
        "overdue_count":  len(overdue),
        "overdue_amount": sum(b["amount"] for b in overdue),
        "bill_count":     len(annotated_instances),
        "by_account":     by_account,
    }
