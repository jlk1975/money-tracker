# Accounts Tab — Implementation Plan

## Overview

A read/write snapshot-based tab for tracking account balances over time, computing
net worth, and visualizing trends. No transaction-level data — balances only.
Individual named accounts roll up into four categories: **Cash**, **Investments**,
**Credit Cards**, **Loans**. Debt-linked accounts write back to the existing
`debt_balances` table so the Debt tab stays in sync.

---

## Database Schema

### New table: `accounts`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT | e.g. "Chase Checking", "Fidelity 401k" |
| `category` | TEXT | `"Cash"` / `"Investments"` / `"Credit Cards"` / `"Loans"` |
| `active` | INTEGER | 0/1 |
| `debt_id` | INTEGER | FK → `debts.id`; NULL for non-debt accounts |
| `sort_order` | INTEGER | |

### New table: `account_balances`
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `account_id` | INTEGER | FK → `accounts.id` |
| `date` | TEXT | MM/DD/YYYY — ad hoc, not locked to month |
| `balance` | REAL | Positive for assets; negative for liabilities |

- No UNIQUE constraint — multiple entries per account per date are allowed;
  queries always use the most recent entry per account as of a given date.

### New columns on `account_settings` (id=1)
| Column | Type | Notes |
|--------|------|-------|
| `nw_start_date` | TEXT | MM/DD/YYYY — "day 0" for all CSS calculations |
| `cash_goal` | REAL | Target cash balance (e.g. 10000.00) |
| `investment_haircut` | REAL | Multiplier on investments for NW (default 0.65) |

---

## Computed Metrics (never stored — always calculated)

All metrics derive from the latest balance per account as of a given date.

| Metric | Formula |
|--------|---------|
| **Cash** | Sum of latest balances for Cash accounts |
| **Investments** | Sum of latest balances for Investment accounts |
| **Credit Cards** | Sum of latest balances for Credit Card accounts (negative) |
| **Loans** | Sum of latest balances for Loan accounts (negative) |
| **Bad Debt** | Credit Cards + Loans |
| **Net Worth** | Cash + (Investments × haircut) + Credit Cards + Loans |
| **NW CSS** | Current NW − NW on `nw_start_date` |
| **NW CSS Status** | ✅ Ok if NW CSS ≥ 0, ⚠️ Behind if < 0 |
| **NW LC** | Current NW − NW at previous snapshot date |
| **Assets CSS** | (Cash + Investments×haircut) − same at start |
| **Debt CSS** | Bad Debt − Bad Debt at start |
| **Day No.** | Today − `nw_start_date` in days |
| **Cash Goal %** | Cash ÷ cash_goal (capped at 100%) |
| **Debt Goal %** | Bad Debt ÷ Bad Debt on start date (shows reduction ratio) |

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [+ Add Account]  [✎ Edit]  [🗑 Delete]  [📈 Log Balance]           │
├──────────────────────────┬──────────────────────────────────────────┤
│  SUMMARY CARD            │  NET WORTH TREND CHART                   │
│  Net Worth: $XXX,XXX     │  (line chart — all history)              │
│  Day 42 · ✅ Ok          │                                          │
│  NW CSS: +$X,XXX         │                                          │
│  NW LC:  +$XXX           │                                          │
│  Assets CSS: +$X,XXX     │                                          │
│  Debt CSS:   -$XXX       │                                          │
│                          │                                          │
│  GOALS                   │                                          │
│  Cash  [████░░░] 43%     │                                          │
│  Debt  [███████] 72%     │                                          │
├──────────────────────────┴──────────────────────────────────────────┤
│  ACCOUNT LIST (grouped by category)                                 │
│                                                                     │
│  Cash                                        $X,XXX  (total)        │
│    Chase Checking                            $X,XXX  updated 5/20  │
│    HYSA Savings                              $X,XXX  updated 5/18  │
│                                                                     │
│  Investments                                $XX,XXX  (total)        │
│    Fidelity 401k                            $XX,XXX  updated 5/15  │
│    Fidelity Brokerage                        $X,XXX  updated 5/15  │
│    529 Plan                                  $X,XXX  updated 5/10  │
│                                                                     │
│  Credit Cards                              -$XX,XXX  (total)        │
│    Discover Card ⇢ Debt tab                -$X,XXX  updated 5/20  │
│    Chase Sapphire ⇢ Debt tab              -$X,XXX  updated 5/20  │
│                                                                     │
│  Loans                                     -$XX,XXX  (total)        │
│    Auto Loan ⇢ Debt tab                   -$XX,XXX  updated 5/01  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Behaviors

### Logging a balance
- Select an account in the list → click **Log Balance** (or double-click row)
- Dialog: account name (read-only), date (defaults to today), balance input
- On save:
  - Inserts into `account_balances`
  - If `debt_id` is set: also upserts into `debt_balances` for the matching
    month key (derived from the entered date) — keeps Debt tab in sync
- The "updated" date shown in the account list is the date of the most recent
  `account_balances` entry for that account

### Adding an account
- Fields: Name, Category (dropdown), Active, Sort Order
- If Category is **Credit Cards** or **Loans**: optional **Link to Debt** picker
  that shows existing debts not yet linked to an account
- Linked accounts show a ⇢ Debt tab indicator in the list

### Trend chart
- X axis: all dates that have at least one balance entry
- Y axis: computed Net Worth as of each date
- Single line — Net Worth only (keep it simple for now)
- Rendered on `tk.Canvas`, same approach as Debt tab chart

### Settings (⚙ gear icon, opens dialog)
- Start Date (`nw_start_date`) — the day 0 anchor
- Cash Goal target amount
- Investment haircut % (default 65%)

### Debt tab read-back
- The Debt tab already reads from `debt_balances` — no changes needed there.
  Write-back from Accounts tab is purely additive (INSERT OR REPLACE).

---

## db.py additions needed
- `get_accounts()` — all active accounts with latest balance + date
- `add_account(name, category, debt_id)` / `update_account(...)` / `delete_account(...)`
- `get_account_balances(account_id)` — full history for one account
- `log_account_balance(account_id, date, balance)` — inserts into account_balances;
  if debt_id set, also upserts debt_balances
- `get_nw_history()` — returns list of (date, cash, investments, credit_cards, loans)
  for all snapshot dates, using latest-per-account-as-of-date logic
- `get_account_settings_nw()` / `set_account_settings_nw()` — read/write the three
  new columns on account_settings

---

## calc.py additions needed
- `compute_nw_snapshot(cash, investments, credit_cards, loans, haircut)` → net worth
- `compute_nw_metrics(history, start_date, haircut, cash_goal)` → dict of all CSS,
  LC, goal %, day no. metrics for display

---

## Out of scope (for now)
- Forecasting
- Per-account trend lines on the chart
- Import from CSV or external sources
- Any connection to the Register tab
