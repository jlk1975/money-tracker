# Money Tracker — Claude Code Context

Personal household bill tracker. Tracks recurring and one-off bills.

## Data directory
Runtime files (DB and settings) live at `~/.local/share/money-tracker/` — separate from the project source.

## Running the app
```bash
money-tracker          # alias in ~/.bashrc — launches in background
# or directly:
DISPLAY=:0 nohup python3 app.py > /tmp/money_tracker.log 2>&1 & disown
```

## Running tests
```bash
python3 -m pytest tests/ -v
```

## Seeding / wiping data
```bash
python3 seed.py    # populate with sample data + generate current month instances (run once on fresh db)
python3 wipe.py    # interactive: wipe instances only, or everything
```

## Architecture

| File | Purpose |
|------|---------|
| `db.py` | All SQLite access — eight tables, see schema below |
| `calc.py` | Pure functions: `annotate_instances()`, `calculate_summary()`, `funded_through_parts()`, `compute_nw_metrics()`, `compute_debt_summary()` |
| `app.py` | customtkinter GUI — 4 tabs: Dashboard, Definitions, Register, Accounts |
| `seed.py` | One-time seeder using `tests/fixtures.py` sample data |
| `wipe.py` | Interactive wipe utility |
| `tests/fixtures.py` | 19 sample definitions + expected totals (SAMPLE_JUNE_TOTAL, SAMPLE_MAY_TOTAL) |

## Database schema

**`bill_definitions`** — source of truth for recurring bills
- `id`, `description`, `frequency`, `typical_amount`, `due_day`
- `months_active` — comma-separated month numbers for Annual/Semi-Annual/Quarterly (e.g. `"3,9"`)
- `adhoc_month` — YYYY-MM target for AdHoc bills (e.g. `"2026-06"`)
- `payment_mode` — `"Auto Pay"`, `"Manual Pay"`, or `""` (unset); display-only, no automation
- `notes`, `active` (0/1), `sort_order`

**`bill_instances`** — one row per bill per month
- `id`, `definition_id`, `month_key` (YYYY-MM), `description`
- `status` (Due/Paid), `due_date` (MM/DD/YYYY), `amount`, `frequency`
- `date_paid`, `notes`, `row_order`, `payment_mode`, `vibe`
- `funded` (0/1) — whether the bill has been funded (default 0)
- `deleted` (0/1) — soft-delete flag; rows are never physically removed so `generate_month_instances` can see that a definition was already handled for the month and won't recreate it on restart
- `transaction_id` — FK to `register_transactions.id`; NULL when unpaid/unlinked; set by Link-to-Bill flow which also auto-funds and auto-pays
- `soft_pay` (0/1) — informational flag: "I paid this manually but the transaction hasn't cleared"; does NOT change status/funded/Safe2Spend; requires bill to be funded first; cleared automatically when a transaction is linked

**`debts`** — one row per debt (e.g. loan, credit card)
- `id`, `name`, `interest_rate` (REAL), `monthly_payment` (REAL)
- `payoff_date` — MM/DD/YYYY or `""` for open-ended debts (e.g. credit cards)
- `notes`, `sort_order`

**`debt_balances`** — one balance entry per debt per month
- `id`, `debt_id`, `month_key` (YYYY-MM), `balance` (REAL)
- UNIQUE constraint on `(debt_id, month_key)` — `INSERT OR REPLACE` for upserts
- User logs a new balance each month by clicking a debt row; most recent entry is the "current" balance

**`register_transactions`** — one row per checking account transaction
- `id`, `date` (MM/DD/YYYY), `description`, `type` ("Deposit" or "Payment"), `amount` (REAL, always positive)
- `transaction_number` — bank-assigned ID; used for duplicate detection on CSV import (combined with `date`); blank for manual entries
- `memo`, `check_number` — from bank CSV columns
- `bank_balance` (REAL, nullable) — bank's own running balance from CSV; used as authoritative current balance; NULL for manually added rows
- `reviewed` (0/1) — user-toggled "I have reviewed this transaction" flag; always 0 on import
- `notes` — legacy field, kept for manual entries

**`account_settings`** — single-row table (id=1) for the checking account
- `account_name`, `starting_balance` (REAL), `as_of_date` (MM/DD/YYYY)
- `nw_start_date` (MM/DD/YYYY) — day-0 anchor for NW CSS calculations
- `cash_goal` (REAL) — target cash balance for goal progress bar
- `investment_haircut` (REAL, default 0.65) — column exists in DB but is no longer used; NW uses full investment values
- Read/written via `db.get_account_settings()` / `db.set_account_settings()`; NW fields via `db.get_nw_settings()` / `db.set_nw_settings()`
- Note: `buffer` column exists in DB from a prior migration but is no longer used — Safe2Spend has no buffer

**`accounts`** — one row per named account
- `id`, `name`, `category` (`"Cash"` / `"Investments"` / `"Credit Cards"` / `"Loans"`), `active` (0/1), `sort_order`
- `debt_id` — FK → `debts.id`; NULL for non-debt accounts; when set, `log_account_balance()` also upserts `debt_balances`
- `register_linked` (0/1) — exactly one Cash account may be marked; its balance auto-syncs from `register_transactions.bank_balance` on every refresh via `db.sync_register_account()`

**`account_balances`** — balance snapshots for each account
- `id`, `account_id` (FK → `accounts.id`), `date` (MM/DD/YYYY), `balance` (REAL)
- No UNIQUE constraint — multiple entries per account per date allowed; queries use most recent entry
- `db.get_accounts()` JOINs with `debts` to surface `debt_interest_rate`, `debt_monthly_payment`, `debt_payoff_date` for linked accounts
- `db.delete_account()` cascades: also deletes the linked debt + debt_balances rows when `debt_id` is set

## Key concepts

- **Month key format**: `"YYYY-MM"` strings throughout
- **`generate_month_instances(month_key)`** — idempotent; creates instances from active definitions for that month; skips if any instances already exist
- **Frequency routing**: Monthly=every month; AdHoc=only in `adhoc_month`; Annual/Semi-Annual/Quarterly/Bi-Weekly/Weekly use `months_active`
- **`due_day` clamping**: clamped to actual month-end (e.g. day 31 → Feb 28)
- **Navigation**: left arrow = only to months with existing instances; right arrow = auto-generates up to 12 months ahead of today
- **`annotate_instances()`** returns instances as a new list of dicts
- **`calculate_summary()`** returns `total_due`, `total_paid`, `bill_count`
- **`funded_through_parts(instances, month_key)`** returns `(days_str, caption_str)` — consecutive funded-through date for unpaid bills from today
- **Funded workflow**: bills must be funded before soft pay or paid; a bill is marked Paid only by being linked to a register transaction (Link-to-Bill auto-funds + auto-pays in one step)
- **Safe2Spend** = `bank_balance` (most recent transaction's bank_balance) − `funded_not_yet_paid` (sum of amounts for funded+Due instances across all months); shown on both Register and Dashboard nav bars; can be negative (shown red)
  - Changes when: CSV imported (bank_balance updates), or bills funded/unfunded on Dashboard
  - Does NOT change when linking a transaction to an unfunded bill — the bank_balance already reflects the payment at import time; linking is bookkeeping only
- **Funding enforcement**: `Mark Funded` and `All Funded` check Safe2Spend before writing; blocked with flash message if insufficient; $0 bills skip the check
- **Tab switching**: no CTkTabview — manual frame-swap via `_switch_tab()`; "Bills" / "Bill List" / "Register" / "Accounts" / "Insurance" / "Legal" buttons centered in header (width=90); active tab highlighted in amber (`C["blue"]`), inactive in `C["border"]`; Insurance and Legal are placeholder tabs (coming soon)
- **Animal emoji in every tab**: each tab's topmost bar shows `self._app._animal` (size 15) centered via `place(relx=0.5, rely=0.5, anchor="center")` — Bills uses grid col 1 of the expanding mid frame; Bill List / Register / Accounts use `place()` on their respective toolbars/nav bars; Insurance and Legal have a dedicated `CTkFrame` (height=42, `fg_color=C["card"]`) added by `_placeholder()` solely to host the animal
- **Header**: 💰 emoji (size 36) on left; right side is a frame (sticky="e") containing: NWCSS label (size 18 bold, green/red) + animal emoji (size 36)
  - Animal picked once at app launch via `random.choice()` from 16-emoji pool (fox, lion, unicorn, parrot, peacock, butterfly, dragon, raccoon, frog, tiger, shark, flamingo, otter, hedgehog, brontosaurus, T-Rex); stored as `self._animal` on `MoneyTrackerApp`; Noto Color Emoji installed so they render in color
  - NWCSS label = `m["nw_css"]` from `calc.compute_nw_metrics()`; updated via `_update_header_nwcss()` on every `refresh()`; green if ≥ 0, red if < 0; format `+$X.XX` / `-$X.XX`; blank when no NW history; hovering shows tooltip "NW Change Since Start" (`_Tooltip` class)
  - Tab buttons centered via 3-column grid layout; window title is "Bill Tracker"; icon buttons (💾 backup, ⬇ restore, 📊 report placeholder) to the right of tab buttons; 📊 uses `family="Noto Color Emoji"` for color rendering
- **`_Tooltip` class**: lightweight hover tooltip — binds `<Enter>`/`<Leave>`/`<ButtonPress>` on a widget; shows a `tk.Toplevel` with `overrideredirect(True)` positioned below the widget; dark bg (`#1c1917`), yellow-tinted text (`#fef9c3`)
- **`self._register` is a reserved name** on `ctk.CTk` (shadows tkinter's internal `_register()` method) — the Register tab instance is stored as `self._reg_tab`

## Dashboard tab (`CombinedDashboard`)

- **Nav bar** layout: left cluster (◀ [Month YYYY] ▶ This Month) | 4-column equal-weight middle grid | ▲ Hide Summary (right)
  - Middle grid columns: funded-through label | animal emoji | bills info label | progress bar + Paid %
  - Implemented as a `CTkFrame` packed with `fill="x", expand=True`, children in `grid` with `columnconfigure(weight=1)` — ensures even spacing regardless of window width
  - Animal uses `self._app._animal` (same pick as the header); Safe2Spend was removed from this nav bar (now lives in the global header left side only)
  - All nav bar text is size 13
  - **Vibe filter buttons** (🌟 Good / 🤷 Meh / 💔 Regret) sit to the right of "This Month" in the nav bar; toggle `_vibe_filter` set; active = color-highlighted, inactive = `C["border"]`
- **Metrics panel** (collapsible): 2 rows of 4 KPI widgets
  - Row 1: `VibeBarsCard`, Payment Progress, Paid, Due
  - Row 2: Funded Not Paid, Funding Progress, Funded, Not Funded
  - Right sidebar: Spending by Vibe + By Pay Mode breakdowns
- **Toolbar**: `All Funded` / `All Unfunded` / `Funded/Unfunded` / `💸 Soft Pay` / `+ Add Bill` / `✎ Edit` / `🗑 Delete` + search box + `Show Paid (N)` / `Show Unpaid (N)` status filter toggles
  - `All Funded`: funds all unfunded visible bills (Safe2Spend check); `All Unfunded`: strips funding from all funded visible bills
  - `Soft Pay`: toggles `soft_pay` flag; bill must be funded first; does not affect status or Safe2Spend
- **Bill table columns** (left→right): Funded | Soft | Vibe | ✓ | Status | Pay Mode | Expense | Due Date | Amount | Frequency | Date Paid | Notes
  - Funded and Soft are leftmost for visibility
- **`_draw` conflict**: `ctk.CTkFrame` calls `self._draw()` internally — never name a canvas paint method `_draw` in a CTkFrame subclass; use `_paint` instead
- **VibeBarsCard**: tk.Canvas with `height=1` hint; draws horizontal bars — emoji left, bar, count right; spread via `_paint` on `<Configure>`
- **Funding Progress** widget label: shows `"Funded through [date] · [days]"` when funded; falls back to `"Funding Progress"`
- **Due** and **Not Funded** KPI values turn green when $0.00, red otherwise

## Register tab (`RegisterTab`)

- Stored as `self._reg_tab` on `MoneyTrackerApp`
- **Account info bar**: Account Name | Balance | Safe2Spend | Cumulative Txns | Showing Txns | Debits/Credits totals | Last Import | ⚙ Account Settings
  - `Cumulative Txns`: total row count in `register_transactions`
  - `Showing Txns`: count of rows currently visible after all filters; updates live
  - `Debits: $X  Credits: $Y`: sum of Payment/Deposit amounts for currently visible rows; updates with every filter change
  - `Last Import`: "Last Import: N new" — set after each CSV import, blank until first import
- **Month nav bar** (below info bar): ◀ [Month YYYY] ▶ All
  - Defaults to current calendar month on launch; ◀/▶ navigate only to months that have transactions (no empty months, arrows disabled at edges)
  - If current month has no transactions, snaps to nearest earlier month that does
  - "All" button (amber when active) drops the month filter and shows all transactions
  - `_reg_month` (YYYY-MM string or None) drives the filter; `_reg_all_months` is a sorted list of months derived from loaded transactions
  - Month filter is the outermost filter — Linked/Unlinked, Reviewed/Unreviewed, and search all apply on top of it
- **Toolbar left**: ⬆ Import CSV | 🔗 Link to Bill | Unlink | ✓ Review | 📋 Create Bill | ⚠ Delete All | search box
- **Toolbar right**: [All][Linked][Unlinked] filter | [All][Reviewed][Unreviewed] filter
- **Table columns**: Rev | Txn # | Date | Description | Memo | Debit | Credit | Balance | Check # | Bill
  - Balance column = `bank_balance` from CSV (the bank's own running balance per row)
  - Bill column = linked bill instance description (blank if unlinked)
  - Deposit rows: green; linked rows: amber tint; reviewed rows: muted foreground; negative balance: red
- **CSV import**: `parse_bank_csv(path)` → first 3 lines skipped (bank metadata); line 4 is the column header; accepts `.csv` or `.CSV`; dedup by `(transaction_number, date)` composite key (rows with a txn number) or `(date, type, amount, description)` fingerprint (rows without); new rows always get `reviewed=0`; flash shows "Imported N (M duplicates skipped)"
- **Review toggle** (`✓ Review`): toggles `reviewed` flag; after toggling, selection auto-advances to the next row in current display order — if the toggled row disappears from the filter view, the row at the same index becomes selected; if it stays, selection moves one down
- **Link-to-Bill flow**: select a Payment transaction → click 🔗 Link to Bill → `LinkBillDialog` opens
  - Default view: bills from the same month as the transaction, sorted by closest amount match
  - Search box filters by description or amount in real time
  - "Show All" button (amber when active) reveals all unlinked+unpaid bills across all months
  - Filter label shows "Showing X of Y bills — [Month], by amount match"
  - On link: sets `transaction_id`, `funded=1`, `status='Paid'`, `date_paid=today`, `soft_pay=0`
- **Unlink**: clears `transaction_id`, sets `status='Due'`, `funded=0`
- **📋 Create Bill** (`CreateBillFromTxnDialog`): creates a new bill definition + instance from a selected transaction in one flow
  - Pre-fills: description (from transaction, "Debit"/"Credit" prefix stripped), amount, due day (from transaction date)
  - User sets frequency, payment mode, vibe, notes
  - "Link this transaction" checkbox (checked by default): calls `link_bill_to_transaction` after insert, marking the bill funded+Paid atomically
  - **Safe2Spend rules**: linking sets `funded=1 + status='Paid'` — Paid bills are never in `funded_not_yet_paid`, so Safe2Spend is unchanged; no pre-flight check needed. If unchecked, bill is created `funded=0 + status=Due` — also no Safe2Spend impact. Manual funding later goes through `_toggle_funded` which enforces the check.
  - Instance is inserted directly for the transaction's month (bypasses `generate_month_instances` which skips months that already have instances)
- **Delete All Transactions**: confirmation dialog; resets all linked bill instances to Due/unfunded/unlinked
- **`AccountSettingsDialog`**: only account name field (no starting balance — balance is derived purely from imported CSV `bank_balance` values)

## Definitions tab (`DefinitionsTab`)
- Table is sortable by column heading click; search box filters live across Description, Frequency, and Notes

## Accounts tab (`AccountsTab`)
- **Layout**: `tk.PanedWindow` (orient="vertical") splits the tab into a collapsible top summary section and the account list below; draggable sash starts at 50/50; sash position persisted to settings JSON on close and restored on launch (`acct_sash_y` key)
- **▲ Hide Summary / ▼ Show Summary** toggle in toolbar collapses/restores the top section; sash position is saved before collapsing and restored on show
- **Top section** contains (top to bottom):
  - **NW summary card** (left, fixed 320px wide): Net Worth, Day N · ✅/⚠️ status, NW/Assets/Debt since-start, Goals progress bars (Cash Goal %, Debt Reduction %)
  - **Metrics card** (right, expands): 4 labeled groups of small KPI tiles (size-15 bold value + size-10 period label):
    - **NET WORTH CHANGE**: 1 Week | 1 Month | 3 Months | 6 Months | 1 Year (delta vs historical snapshot; green=up, red=down; "—" when no data for period)
    - **DEBT CHANGE**: same 5 periods (green=debt down, red=debt up)
    - **SPENDING**: Past 7 Days | Past 14 Days | Past 30 Days | This Month MTD (MTD tile has sub-line: ▲/▼ $X vs prior month same-day; red=more spending, green=less)
    - **CASH FLOW**: This Month | Last Month (credits − debits; green=positive, red=negative)
    - Data: NW/Debt from `db.get_nw_history()` via `calc.compute_nw_period_changes()`; Spending/CF from `db.get_register_cashflow_data()` via `calc.compute_spending_metrics()`
    - Tile values stored in `self._metric_vals` dict; updated by `_refresh_metrics_panel()` on every `refresh()`
  - **Debt summary row** (full-width below top panel): Total Debt | Monthly Payments | Years Until Debt Free
- **Toolbar**: `+ Add Account` | `✎ Edit` | `🗑 Delete` | `📈 Log Balance` | `▲ Hide Summary` | `⚙ Settings`
  - `Log Balance` disabled for the register-linked account (balance auto-syncs)
- **Account list** (bottom pane): grouped treeview by category (Cash / Investments / Credit Cards / Loans)
  - Columns: Account | Balance | Last Updated | Rate | Monthly Pmt | Payoff Date | Days Left
  - Rate/Monthly Pmt/Payoff Date/Days Left only populate for CC/Loan rows with a linked debt
  - Category header rows show category name + total balance
- **AccountDialog**: `+ Add Account` / `✎ Edit`; when category is Credit Cards or Loans, shows inline debt fields (Interest Rate %, Monthly Payment, Payoff Date); on save, creates or updates the linked `debts` record automatically; `debt_id` is set on the account
  - `Save & Add Another` button available when creating; starting balance (amount + date) available for new accounts
  - Deleting a CC/Loan account with a linked debt cascades: removes the debt record and all `debt_balances` rows
- **LogBalanceDialog**: date + balance entry; enter positive balances for all accounts including liabilities; if account has `debt_id`, also upserts `debt_balances` via `log_account_balance()`
- **NWSettingsDialog** (⚙ Settings): Start Date, Cash Goal, Investment Haircut
- **NW metrics** (`calc.compute_nw_metrics()`): Net Worth = Cash + Investments − CC − Loans (all at full value, no haircut); CSS = change since start date; LC = change since previous snapshot; goal %s
- **Account category rows**: collapsible — click a category header row to toggle; state tracked in `_cat_open` dict; ▼/▶ arrows prepended to category label
- **Debt metrics** (`calc.compute_debt_summary()`): total debt, total monthly payments, years until debt free — derived from CC/Loan accounts with latest balances
- **Debt balance write-back**: `db.log_account_balance()` automatically upserts `debt_balances` (using `abs(balance)`) when the account has a `debt_id`, keeping the debt balance history in sync
- **register_linked account**: one Cash account (UWBC) auto-syncs its balance from the most recent `register_transactions.bank_balance` on every refresh via `db.sync_register_account()`

## Expected totals (from fixtures)
- May 2026: 16 bills, $3,486.59 (Monthly only — no AdHoc)
- June 2026: 19 bills, $4,156.09 (Monthly + 3 AdHoc payoffs)
