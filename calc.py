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
    """Return instances as a new list of dicts."""
    return [dict(b) for b in instances]


def calculate_summary(annotated_instances):
    """Return aggregate stats across all instances."""
    total_due  = sum(b["amount"] for b in annotated_instances if b.get("status") == "Due")
    total_paid = sum(b["amount"] for b in annotated_instances if b.get("status") == "Paid")

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
        "total_due":  total_due,
        "total_paid": total_paid,
        "bill_count": len(annotated_instances),
        "by_account": by_account,
    }
