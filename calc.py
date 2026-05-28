import calendar
from datetime import date, datetime, timedelta


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


def compute_nw_period_changes(nw_history):
    """Return NW and debt deltas for 1w/1m/3m/6m/1y periods.

    Keys: nw_1w, nw_1m, nw_3m, nw_6m, nw_1y, debt_1w, ..., debt_1y.
    Value is a float (positive = increased) or None when no historical data exists
    for that period.
    """
    result = {f"{k}_{p}": None for k in ("nw", "debt")
              for p in ("1w", "1m", "3m", "6m", "1y")}
    if not nw_history or len(nw_history) < 2:
        return result

    entries = []
    for r in nw_history:
        d = _parse_date(r["date"])
        if d:
            entries.append({
                "date": d,
                "nw":   compute_net_worth(r["cash"], r["investments"],
                                          r["credit_cards"], r["loans"]),
                "debt": r["credit_cards"] + r["loans"],
            })
    if len(entries) < 2:
        return result

    today = date.today()
    current = max(entries, key=lambda e: e["date"])
    for label, days in (("1w", 7), ("1m", 30), ("3m", 91), ("6m", 182), ("1y", 365)):
        target = today - timedelta(days=days)
        candidates = [e for e in entries if e["date"] <= target]
        if candidates:
            snap = max(candidates, key=lambda e: e["date"])
            result[f"nw_{label}"]   = current["nw"]   - snap["nw"]
            result[f"debt_{label}"] = current["debt"] - snap["debt"]
    return result


def compute_spending_metrics(transactions):
    """Compute spending and cashflow KPIs from register transaction dicts.

    Each transaction: {date: MM/DD/YYYY, type: "Payment"|"Deposit", amount: float}.
    """
    today = date.today()
    this_year, this_month = today.year, today.month
    if this_month == 1:
        last_year, last_month = this_year - 1, 12
    else:
        last_year, last_month = this_year, this_month - 1
    today_day = today.day
    last_month_name = date(last_year, last_month, 1).strftime("%b")

    cutoff_7d  = today - timedelta(days=7)
    cutoff_14d = today - timedelta(days=14)
    cutoff_30d = today - timedelta(days=30)

    spending_7d = spending_14d = spending_30d = 0.0
    spending_mtd = spending_mtd_last = 0.0
    cashflow_this = cashflow_last = 0.0

    for t in transactions:
        d = _parse_date(t["date"])
        if not d:
            continue
        amt = t["amount"]
        typ = t["type"]
        if typ == "Payment":
            if d >= cutoff_7d:
                spending_7d += amt
            if d >= cutoff_14d:
                spending_14d += amt
            if d >= cutoff_30d:
                spending_30d += amt
            if d.year == this_year and d.month == this_month and d.day <= today_day:
                spending_mtd += amt
            if d.year == last_year and d.month == last_month and d.day <= today_day:
                spending_mtd_last += amt
            if d.year == this_year and d.month == this_month:
                cashflow_this -= amt
            if d.year == last_year and d.month == last_month:
                cashflow_last -= amt
        elif typ == "Deposit":
            if d.year == this_year and d.month == this_month:
                cashflow_this += amt
            if d.year == last_year and d.month == last_month:
                cashflow_last += amt

    return {
        "spending_7d":       spending_7d,
        "spending_14d":      spending_14d,
        "spending_30d":      spending_30d,
        "spending_mtd":      spending_mtd,
        "spending_mtd_last": spending_mtd_last,
        "cashflow_this":     cashflow_this,
        "cashflow_last":     cashflow_last,
        "last_month_name":   last_month_name,
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
