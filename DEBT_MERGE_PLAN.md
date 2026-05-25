# Debt Tab Merger — Implementation Plan

## Overview

Fold the entire Debt tab into the Accounts tab. The Debt tab is removed from the
nav bar. All debt metrics, the debt chart, and debt management (add/edit/delete/log
balance) live on the Accounts tab alongside the existing net worth content.

No schema changes. `debts` and `debt_balances` tables stay exactly as-is. The only
new data surfaced in the UI comes from a richer JOIN in `get_accounts()`.

---

## What Moves to the Accounts Tab

| Debt Tab Feature | Landing Spot on Accounts Tab |
|---|---|
| Total Debt / Total Monthly Payments / Years Until Debt Free summary card | New "Debt Summary" row added below the existing NW summary card |
| Debt Balance Trend chart (Total / Per Debt toggle) | Second chart panel below the NW trend chart |
| Per-debt table columns: Rate, Monthly Pmt, Payoff Date, Days Left, Balance | Extra columns on the account list treeview; blank for Cash/Investment rows |
| Balance Dialog (log debt balance for current month) | Replaced by existing `LogBalanceDialog` — already writes to `debt_balances` via `log_account_balance()` when `debt_id` is set |
| Add Debt / Edit Debt dialogs | Rolled into `AccountDialog` — extra fields appear when category is Credit Cards or Loans |
| Delete Debt button | Becomes delete for the account row; backend deletes both the account and the linked debt |

---

## UI Changes

### 1. Summary Area

Current layout (two panels side-by-side: NW summary card | NW trend chart) stays.

Add a **Debt Summary row** below it, full-width, same card style:

```
┌──────────────────┬──────────────────┬──────────────────────────┐
│  Total Debt      │ Monthly Payments │  Years Until Debt Free   │
│  -$XX,XXX  (red) │  $X,XXX (yellow) │  X.X  (teal)             │
└──────────────────┴──────────────────┴──────────────────────────┘
```

Only shown when at least one CC or Loan account exists.

### 2. Charts

Two chart panels stacked vertically, both in the right-side area or below the summary:

- **Top chart**: Net Worth Trend (existing, unchanged)
- **Bottom chart**: Debt Balance Trend (from `DebtTrackerTab`) with "Per Debt" / "Total"
  toggle — copy the existing `_repaint_chart` logic and `_CHART_COLORS` directly

### 3. Account List — Extra Columns

Add 4 columns to the treeview that only populate for CC/Loan rows:

| Column | Width | Alignment | Notes |
|--------|-------|-----------|-------|
| Rate | 60 | right | "14.99%" or blank |
| Monthly Pmt | 100 | right | "$281.43" or blank |
| Payoff Date | 95 | center | "MM/DD/YYYY" or blank |
| Days Left | 75 | right | integer days or "N/A" or blank |

Category header rows (bold/italic) leave these columns blank.

### 4. Toolbar

Keep the existing Accounts toolbar. Add toolbar buttons:

```
[+ Add Account]  [✎ Edit]  [🗑 Delete]  [📈 Log Balance]  [⚙ Settings]
```

No separate "Add Debt" button — debt fields appear in `AccountDialog` when the
category is Credit Cards or Loans.

### 5. Double-click / Log Balance

Current behavior: double-click or Log Balance button opens `LogBalanceDialog`.
For debt-linked accounts this already works — `log_account_balance()` in db.py
upserts `debt_balances` whenever `debt_id` is set. No change needed.

---

## AccountDialog Expansion

When **Category** is "Credit Cards" or "Loans", show three additional fields below
the existing ones:

```
Interest Rate %    [_______]  e.g. 14.99
Monthly Payment    [_______]  e.g. 281.43
Payoff Date        [_______]  MM/DD/YYYY — leave blank for N/A
```

On **Save**:
- If no linked debt yet: call `db.insert_debt(...)` first, then set `debt_id` on
  the account row.
- If already linked: call `db.update_debt(debt_id, ...)` to keep the debt record
  in sync.
- If category changed away from CC/Loans: clear `debt_id`, but leave the `debts`
  row in place (don't auto-delete — user can always clean up).

The "Link to Debt" picker (existing) becomes a fallback for linking to a *pre-existing*
debt that was created before the merge. It stays in the dialog but is de-emphasized
(small label: "Or link to existing debt:").

---

## Delete Account — Debt Cleanup

When deleting a Credit Card or Loan account that has a `debt_id`:

Show a confirmation dialog:
> "Delete [Name] and all its balance history? This will also remove the linked
> debt record and all monthly balance entries."

On confirm: `db.delete_account(id)` — extend this function to also call
`db.delete_debt(debt_id)` when set.

---

## Nav Tab Changes

Remove **"Debt"** from the tab button list in `MoneyTrackerApp.__init__`:

```python
# Before
("Bills", "Bill List", "Debt", "Register", "Accounts")

# After
("Bills", "Bill List", "Register", "Accounts")
```

Update `_switch_tab()` to not reference `_debt_tab`. Remove the
`DebtTrackerTab` instance and its `refresh()` call from the main `refresh()`
method.

---

## db.py Changes

### `get_accounts()` — add debt JOIN

```sql
SELECT a.*, ab.balance AS latest_balance, ab.date AS latest_date,
       d.interest_rate, d.monthly_payment, d.payoff_date
FROM accounts a
LEFT JOIN (
    SELECT account_id, balance, date
    FROM account_balances
    WHERE id IN (
        SELECT MAX(id) FROM account_balances GROUP BY account_id
    )
) ab ON ab.account_id = a.id
LEFT JOIN debts d ON d.id = a.debt_id
WHERE a.active = 1
ORDER BY a.sort_order, a.id
```

### `delete_account(account_id, db_path)` — new function

Deletes the account, its balance history, and the linked debt + debt_balances
if `debt_id` is set.

### `insert_debt` / `update_debt` — no changes

Already exist; called directly from `AccountDialog._save()`.

---

## calc.py Changes

### `compute_debt_summary(accounts, nw_history_or_balances)`

```python
def compute_debt_summary(accounts, debt_balances):
    """Return {total_debt, total_monthly_pmt, years_until_free} for CC/Loan accounts."""
```

Mirrors the existing logic in `DebtTrackerTab.refresh()`. Takes the list of accounts
(with latest_balance from the JOIN) and returns the three KPI values. Logic:

- `total_debt` — sum of `abs(latest_balance)` for CC/Loan accounts
- `total_monthly_pmt` — sum of `monthly_payment` for CC/Loan accounts
- `years_until_free` — derived from latest `payoff_date` across CC/Loan accounts;
  "N/A" if any has no payoff date

---

## Code to Remove

Once the merge is complete:

- `DebtTrackerTab` class (~350 lines, roughly lines 1088–1439)
- `BalanceDialog` class (replaced by `LogBalanceDialog`)
- `DebtDialog` class (rolled into `AccountDialog`)
- `DEBT_COLUMNS`, `DEBT_LEFT_ALIGN`, `_merge_debt_row()` helper
- `self._debt_tab` reference in `MoneyTrackerApp`
- `db.py`: `get_debts()` and `get_debt_balances()` can be kept (still called
  internally) but remove them from the app-level `refresh()` pass

---

## Implementation Order

1. **db.py** — extend `get_accounts()` JOIN; add `delete_account()`
2. **calc.py** — add `compute_debt_summary()`
3. **AccountDialog** — add debt fields for CC/Loan categories; wire insert/update_debt
4. **AccountsTab._build()** — add Debt Summary card; add second chart panel; add extra
   treeview columns; wire `_repaint_debt_chart()`
5. **AccountsTab.refresh()** — compute and populate debt summary + chart data
6. **Nav** — remove Debt tab button; update `_switch_tab()`; remove `DebtTrackerTab`
   instance and its `refresh()` call
7. **Cleanup** — delete `DebtTrackerTab`, `BalanceDialog`, `DebtDialog`, dead helpers

Each step is independently testable before moving to the next.

---

## Out of Scope

- Per-account trend lines on the NW chart
- Amortization schedule / projected payoff chart
- Moving debt data out of `debts` / `debt_balances` into the accounts schema
- Any changes to the Register tab or Dashboard tab
