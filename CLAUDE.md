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
| `db.py` | All SQLite access — six tables, see schema below |
| `calc.py` | Pure functions: `annotate_instances()`, `calculate_summary()`, `funded_through_parts()` |
| `app.py` | customtkinter GUI — 4 tabs: Dashboard, Definitions, Debt, Register |
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
- `transaction_number` — bank-assigned ID; used for duplicate detection on CSV import; blank for manual entries
- `memo`, `check_number` — from bank CSV columns
- `bank_balance` (REAL, nullable) — bank's own running balance from CSV; used as authoritative current balance; NULL for manually added rows
- `reviewed` (0/1) — user-toggled "I have reviewed this transaction" flag; always 0 on import
- `notes` — legacy field, kept for manual entries

**`account_settings`** — single-row table (id=1) for the checking account
- `account_name`, `starting_balance` (REAL), `as_of_date` (MM/DD/YYYY)
- Read/written via `db.get_account_settings()` / `db.set_account_settings()`
- Note: `buffer` column exists in DB from a prior migration but is no longer used — Safe2Spend has no buffer

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
- **Tab switching**: no CTkTabview — manual frame-swap via `_switch_tab()`; "Dashboard" / "Definitions" / "Debt" / "Register" buttons centered in header; active tab highlighted in blue, inactive in `C["card2"]`
- **Header**: 💰 emoji (size 36) on left and right ends; tab buttons centered via 3-column grid layout; window title is "Bill Tracker"
- **`self._register` is a reserved name** on `ctk.CTk` (shadows tkinter's internal `_register()` method) — the Register tab instance is stored as `self._reg_tab`

## Dashboard tab (`CombinedDashboard`)

- **Nav bar** layout: left cluster (◀ [Month YYYY] ▶ This Month) | 5-column equal-weight middle grid | ▲ Hide Summary (right)
  - Middle grid columns: funded-through label | 4 random animal emojis | bills info label | progress bar + Paid % | Safe2Spend
  - Implemented as a `CTkFrame` packed with `fill="x", expand=True`, children in `grid` with `columnconfigure(weight=1)` — ensures even spacing regardless of window width
  - 4 random animals picked at app launch via `random.sample()` from a pool of 16 emoji (fox, lion, unicorn, parrot, peacock, butterfly, dragon, raccoon, frog, tiger, shark, flamingo, otter, hedgehog, brontosaurus, T-Rex); Noto Color Emoji is installed so they render in color
  - All nav bar text is size 13; Safe2Spend is green
  - No vibe filter buttons (removed — `_vibe_filter` set exists but is always empty)
- **Metrics panel** (collapsible): 2 rows of 4 KPI widgets
  - Row 1: `VibeBarsCard`, Payment Progress, Paid, Due
  - Row 2: Funded Not Paid, Funding Progress, Funded, Not Funded
  - Right sidebar: Spending by Vibe + By Pay Mode breakdowns
- **Toolbar**: `All Funded` / `All Unfunded` / `Funded/Unfunded` / `💸 Soft Pay` / `+ Add Bill` / `✎ Edit` / `🗑 Delete` + search box + `Show Paid (N)` / `Show Unpaid (N)` status filter toggles
  - `All Funded`: funds all unfunded visible bills (Safe2Spend check); `All Unfunded`: strips funding from all funded visible bills
  - `Soft Pay`: toggles `soft_pay` flag; bill must be funded first; does not affect status or Safe2Spend
- **Bill table columns** (left→right): Funded | Soft | Vibe | ✓ | Status | Pay Mode | Expense | Due Date | Amount | Frequency | Date Paid
  - Funded and Soft are leftmost for visibility
- **`_draw` conflict**: `ctk.CTkFrame` calls `self._draw()` internally — never name a canvas paint method `_draw` in a CTkFrame subclass; use `_paint` instead
- **VibeBarsCard**: tk.Canvas with `height=1` hint; draws horizontal bars — emoji left, bar, count right; spread via `_paint` on `<Configure>`
- **Funding Progress** widget label: shows `"Funded through [date] · [days]"` when funded; falls back to `"Funding Progress"`
- **Due** and **Not Funded** KPI values turn green when $0.00, red otherwise

## Register tab (`RegisterTab`)

- Stored as `self._reg_tab` on `MoneyTrackerApp`
- **Account info bar**: Account Name | Balance | Safe2Spend | Cumulative Txns | Showing Txns | Last Import | ⚙ Account Settings
  - `Cumulative Txns`: total row count in `register_transactions`
  - `Showing Txns`: count of rows currently visible after all filters; updates live
  - `Last Import`: "Last Import: N new" — set after each CSV import, blank until first import
- **Toolbar left**: ⬆ Import CSV | 🔗 Link to Bill | Unlink | ✓ Review | 📋 Create Bill | ⚠ Delete All | search box
- **Toolbar right**: [All][Linked][Unlinked] filter | [All][Reviewed][Unreviewed] filter
- **Table columns**: Rev | Txn # | Date | Description | Memo | Debit | Credit | Balance | Check # | Bill
  - Balance column = `bank_balance` from CSV (the bank's own running balance per row)
  - Bill column = linked bill instance description (blank if unlinked)
  - Deposit rows: green; linked rows: blue tint; reviewed rows: muted foreground; negative balance: red
- **CSV import**: `parse_bank_csv(path)` → dedup by `transaction_number` (rows with one) or `(date, type, amount, description)` fingerprint (rows without); new rows always get `reviewed=0`; flash shows "Imported N (M duplicates skipped)"
- **Review toggle** (`✓ Review`): toggles `reviewed` flag; after toggling, selection auto-advances to the next row in current display order — if the toggled row disappears from the filter view, the row at the same index becomes selected; if it stays, selection moves one down
- **Link-to-Bill flow**: select a Payment transaction → click 🔗 Link to Bill → `LinkBillDialog` opens
  - Default view: bills from the same month as the transaction, sorted by closest amount match
  - Search box filters by description or amount in real time
  - "Show All" button (blue when active) reveals all unlinked+unpaid bills across all months
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

## Debt tab (`DebtTrackerTab`)
- Summary card at top: Total Debt / Total Monthly Payments / Years Until Debt Free
- Toolbar: Add/Edit/Delete; clicking a debt row opens `BalanceDialog` to log balance for current month
- Chart (`tk.Canvas`) toggles between Total and Per Debt trend lines; table is sortable by column heading click
- **Debt balance workflow**: one `debt_balances` row per debt per month; multiple updates in same month overwrite (last write wins)
- **Years Until Debt Free**: derived from latest `payoff_date` across all debts; shows "N/A" if any debt has no payoff date

## Expected totals (from fixtures)
- May 2026: 16 bills, $3,486.59 (Monthly only — no AdHoc)
- June 2026: 19 bills, $4,156.09 (Monthly + 3 AdHoc payoffs)
