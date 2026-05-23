import calendar
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


def funded_through_parts(instances, month_key):
    """Return (days_str, caption_str) for the Funded Not Paid KPI card."""
    today = date.today()
    year, month = map(int, month_key.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)
    month_name = date(year, month, 1).strftime("%B")

    upcoming = []
    for b in instances:
        if b.get("status") == "Paid":
            continue
        d = _parse_date(b.get("due_date", ""))
        if d and d >= today:
            upcoming.append((d, b))
    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        days = (month_end - today).days
        days_str = "today" if days == 0 else f"{days} days"
        return (days_str, f"Funded through {month_end.strftime('%b %-d')}")

    funded_through_date = None
    i = 0
    while i < len(upcoming):
        current_date = upcoming[i][0]
        j = i
        while j < len(upcoming) and upcoming[j][0] == current_date:
            j += 1
        group = upcoming[i:j]
        if all(b.get("funded") for _, b in group):
            funded_through_date = current_date
            i = j
        else:
            break

    if funded_through_date is None:
        return ("0 days", f"not funded in {month_name}")

    days = (funded_through_date - today).days
    days_str = "today" if days == 0 else f"{days} days"
    return (days_str, f"Funded through {funded_through_date.strftime('%b %-d')}")


def calculate_summary(annotated_instances):
    """Return aggregate stats across all instances."""
    total_due  = sum(b["amount"] for b in annotated_instances if b.get("status") == "Due")
    total_paid = sum(b["amount"] for b in annotated_instances if b.get("status") == "Paid")

    return {
        "total_due":  total_due,
        "total_paid": total_paid,
        "bill_count": len(annotated_instances),
    }
