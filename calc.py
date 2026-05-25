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


def compute_net_worth(cash, investments, credit_cards, loans):
    return cash + investments - credit_cards - loans


def compute_nw_metrics(nw_history, start_date, cash_goal):
    """Return a dict of display metrics derived from nw_history.

    nw_history: list of {date, cash, investments, credit_cards, loans} dicts,
                oldest first — as returned by db.get_nw_history().
    """
    if not nw_history:
        return None

    today = date.today()
    latest = nw_history[-1]
    cash        = latest["cash"]
    investments = latest["investments"]
    credit_cards = latest["credit_cards"]
    loans        = latest["loans"]
    bad_debt     = credit_cards + loans
    nw_current   = compute_net_worth(cash, investments, credit_cards, loans)

    # Find start-date snapshot (first entry on or after start_date; fallback to earliest)
    start = None
    if start_date:
        for row in nw_history:
            if row["date"] >= start_date:
                start = row
                break
    if start is None:
        start = nw_history[0]

    nw_start    = compute_net_worth(start["cash"], start["investments"],
                                    start["credit_cards"], start["loans"])
    bad_debt_start = start["credit_cards"] + start["loans"]
    assets_start   = start["cash"] + start["investments"]

    nw_css      = nw_current - nw_start
    assets_css  = (cash + investments) - assets_start
    debt_css    = bad_debt - bad_debt_start

    # Previous snapshot for NW LC
    nw_prev = compute_net_worth(
        nw_history[-2]["cash"], nw_history[-2]["investments"],
        nw_history[-2]["credit_cards"], nw_history[-2]["loans"],
    ) if len(nw_history) >= 2 else nw_current
    nw_lc = nw_current - nw_prev

    # Day number
    try:
        from datetime import datetime
        start_d = datetime.strptime(start["date"], "%m/%d/%Y").date()
        day_no  = (today - start_d).days
    except Exception:
        day_no = 0

    # Goals
    cash_goal_pct = min(cash / cash_goal, 1.0) if cash_goal else 0.0
    debt_goal_pct = (bad_debt / bad_debt_start) if bad_debt_start != 0 else 1.0

    return {
        "cash":           cash,
        "investments":    investments,
        "credit_cards":   credit_cards,
        "loans":          loans,
        "bad_debt":       bad_debt,
        "net_worth":      nw_current,
        "nw_css":         nw_css,
        "nw_css_ok":      nw_css >= 0,
        "nw_lc":          nw_lc,
        "assets_css":     assets_css,
        "debt_css":       debt_css,
        "day_no":         day_no,
        "cash_goal_pct":  cash_goal_pct,
        "debt_goal_pct":  debt_goal_pct,
        "cash_goal":      cash_goal,
    }


def compute_debt_summary(accounts):
    """Return {total_debt, total_monthly_pmt, years_until_free} from CC/Loan accounts."""
    debt_accts = [a for a in accounts if a.get("category") in ("Credit Cards", "Loans")]
    total_debt = sum(
        abs(a["latest_balance"]) for a in debt_accts if a.get("latest_balance") is not None
    )
    total_monthly_pmt = sum(a.get("debt_monthly_payment") or 0 for a in debt_accts)

    if not debt_accts:
        return {"total_debt": 0.0, "total_monthly_pmt": 0.0, "years_until_free": "—"}

    max_payoff = None
    valid = True
    for a in debt_accts:
        pd = a.get("debt_payoff_date") or ""
        if not pd:
            valid = False
            break
        try:
            m, day, y = pd.split("/")
            d = date(int(y), int(m), int(day))
            max_payoff = max(max_payoff, d) if max_payoff else d
        except Exception:
            valid = False
            break

    if valid and max_payoff:
        delta_days = (max_payoff - date.today()).days
        years_str = f"{max(delta_days, 0) / 365.25:.1f}"
    else:
        years_str = "N/A"

    return {
        "total_debt":       total_debt,
        "total_monthly_pmt": total_monthly_pmt,
        "years_until_free": years_str,
    }


def calculate_summary(annotated_instances):
    """Return aggregate stats across all instances."""
    total_due  = sum(b["amount"] for b in annotated_instances if b.get("status") == "Due")
    total_paid = sum(b["amount"] for b in annotated_instances if b.get("status") == "Paid")

    return {
        "total_due":  total_due,
        "total_paid": total_paid,
        "bill_count": len(annotated_instances),
    }
