# Plan: Register Tab — Full Transaction Workflow

## Overview

The Register tab is a read-only ledger fed exclusively by CSV import from the bank.
Transactions drive bill payment: a bill instance is only considered paid when it is
linked to a real transaction. A Safe2Spend metric shows spendable cash after accounting
for funded-but-unpaid bills and a configurable buffer.

---

## Core Rules

- **Transactions come in only via CSV import.** No manual Add or Edit buttons.
- **Duplicate detection is fully automatic.** No preview checklist; the app skips rows
  whose `transaction_number` is already in the DB and reports a simple summary.
- **Delete is all-or-nothing.** The only delete option wipes every transaction ever.
  Any bill instances linked to deleted transactions revert to unpaid (and unfunded if
  they were auto-funded via the link).
- **A bill instance is marked Paid only by being linked to a transaction.**
  Linking also auto-funds the instance if it was not already funded.
- **One transaction per bill instance.** A single transaction can be linked to at most
  one bill instance per month (and vice versa).
- **Soft Pay** is a separate informational flag — it does not affect Paid/Funded status
  or Safe2Spend. It lets the user track "I paid this manually but the transaction hasn't
  cleared yet."
- **You cannot fund a bill if its amount exceeds the current Safe2Spend.** Funding
  reduces Safe2Spend (because the bill moves into `funded_not_yet_paid`), so the
  constraint is: `bill.amount ≤ Safe2Spend` at the moment the user clicks Mark Funded.
  If multiple bills are selected for bulk-fund, only the *unfunded* bills in the
  selection are summed — already-funded bills are no-ops and are excluded from the check.
- **Unlinking always resets `funded=0`.** When a link is removed, the bill loses its
  financial backing. Leaving `funded=1` would cause the bill to re-enter
  `funded_not_yet_paid` while the transaction (and its balance impact) remains in the
  register — double-counting the money. Resetting to unfunded is always correct; the
  user can re-fund manually if needed.

---

## Bank CSV Format (confirmed from sample)

Standard **comma-separated (CSV)** with a header row. Columns:

| Column               | Example                              | Notes                                  |
|----------------------|--------------------------------------|----------------------------------------|
| `Transaction Number` | `"3611"`                             | Quoted integer; unique per transaction |
| `Date`               | `05/23/2026`                         | MM/DD/YYYY                             |
| `Description`        | `"Debit AMAZON"`                     | Quoted string                          |
| `Memo`               | `"MKTPL*0I8HT9Amzn.com/bill WAUS"`  | Quoted string; extra detail            |
| `Amount Debit`       | `-41.67`                             | Negative float; blank for deposits     |
| `Amount Credit`      | (blank)                              | Positive float; blank for payments     |
| `Balance`            | `1694.82`                            | Bank's running balance — ignored       |
| `Check Number`       | (blank)                              | Non-blank only for paper checks        |

### Column mapping to register_transactions

| CSV column           | Register field       | Transform                                     |
|----------------------|----------------------|-----------------------------------------------|
| `Transaction Number` | `transaction_number` | Store as-is for duplicate detection           |
| `Date`               | `date`               | Direct (already MM/DD/YYYY)                   |
| `Description`        | `description`        | Strip leading "Debit " / "Credit " prefix     |
| `Memo`               | `notes`              | Direct; Check # prepended if present          |
| `Amount Debit`       | `type`, `amount`     | Non-blank → type=Payment, amount=abs(value)   |
| `Amount Credit`      | `type`, `amount`     | Non-blank → type=Deposit, amount=abs(value)   |
| `Balance`            | —                    | Ignored                                       |
| `Check Number`       | `notes`              | If non-blank, prepend "Check #X — " to notes  |

---

## DB Schema Changes

### `register_transactions` — existing table

```sql
ALTER TABLE register_transactions ADD COLUMN transaction_number TEXT NOT NULL DEFAULT ''
```

Already planned. Add in `init_db()` via try/except for safe migration.

Remove the ability to manually add or edit rows — `db.insert_transaction()` is only
called from the CSV import path; no UI calls it directly.

### `bill_instances` — new columns

```sql
ALTER TABLE bill_instances ADD COLUMN transaction_id INTEGER REFERENCES register_transactions(id)
ALTER TABLE bill_instances ADD COLUMN soft_pay INTEGER NOT NULL DEFAULT 0
```

- `transaction_id` — FK to the linked transaction; NULL when unpaid/unlinked.
- `soft_pay` — 0/1 flag; independent of paid/funded status.

### `account_settings` — new column

```sql
ALTER TABLE account_settings ADD COLUMN buffer REAL NOT NULL DEFAULT 0.0
```

- User-configurable dollar amount subtracted from Safe2Spend at all times.
- Default $0.00 (no effect until the user sets it).

All three ALTERs go in `init_db()` using the existing try/except migration pattern.

---

## Register Tab UI Changes

### Toolbar

Remove **Add** and **Edit** buttons entirely.

New toolbar layout (left to right):
- **⬆ Import CSV** — triggers CSV import flow
- **🔗 Link to Bill** — links selected transaction to a bill instance (active only when
  one Payment-type transaction is selected and it is not already linked)
- **🗑 Unlink** — removes the bill link from the selected transaction, reverting the
  bill instance to unpaid/unfunded (active only when selected transaction has a link)
- **⚠ Delete All Transactions** — nuclear delete (see below)

### Account info bar

Add a **Buffer** field next to the account name / balance area:

```
[Account Name]   Balance: $X,XXX.XX   Buffer: $[___]   Safe2Spend: $X,XXX.XX
```

- Buffer field is an inline editable dollar amount; saves to `account_settings.buffer`
  on focus-out or Enter.
- Safe2Spend recalculates live whenever balance, buffer, or funded bills change.

### Register table

Add a **Bill** column (last column): shows the linked bill instance's description if
this transaction has been matched to a bill, blank otherwise.

Linked payment rows also receive a distinct **background tint** (a muted green or blue,
TBD at implementation time to contrast with the existing green used for deposit rows).
The tint makes matched rows immediately scannable without reading the Bill column; the
Bill column answers "linked to what?" without any extra interaction. This follows the
existing row-coloring convention (deposits=green, negative balance=red).

### Transaction Filter

Three mutually exclusive toggle buttons in the toolbar, styled like the Dashboard vibe
filter buttons (active = blue highlight, inactive = `C["card2"]`):

```
[ All ]  [ Linked ]  [ Unlinked ]
```

- **All** — show every transaction (default)
- **Linked** — show only transactions with a bill attached (`transaction_id IS NOT NULL`)
- **Unlinked** — show only transactions with no bill attached (`transaction_id IS NULL`)

State stored as `_link_filter: str` (`"all"` / `"linked"` / `"unlinked"`) on `RegisterTab`.
Clicking a button sets `_link_filter` and calls `refresh()`. Filtering is applied Python-side
after fetching all transactions, before building table rows. Tinted backgrounds are unaffected
— they are applied per-row based on link status regardless of the active filter.

**Balance column caveat**: when the filter is not "All", the running Balance column reflects
only the filtered subset, not the full account balance. Show a small note (e.g., `"Balance
reflects filtered rows"`) below or beside the table whenever the filter is active, so the
user isn't confused by the numbers not matching their bank statement.

---

## CSV Import Flow

1. User clicks **⬆ Import CSV**.
2. `tkinter.filedialog.askopenfilename` opens a file picker (filter: .csv, .txt, all).
3. App parses the file → list of row dicts (see Parsing section).
4. App queries existing `transaction_number` values from the DB.
5. New rows (not in DB) are inserted automatically via `db.insert_transaction()`.
6. Duplicate rows are silently skipped — no user action required.
7. A brief result toast or message label shows: **"Imported N transactions (M duplicates skipped)"**.
8. `RegisterTab.refresh()` is called.

No preview dialog. No checklist. The bank's `Transaction Number` is the authoritative
duplicate key — exact match, no fuzzy logic needed.

---

## Parsing

- Use Python's `csv.DictReader` — handles quoted fields, commas in values, etc.
- Skip rows where both `Amount Debit` and `Amount Credit` are blank.
- For each valid row:
  - Parse amounts: strip `$`, `,`, whitespace → float
  - If `Amount Debit` non-blank and non-zero → type=Payment, amount=abs(value)
  - Else if `Amount Credit` non-blank and non-zero → type=Deposit, amount=abs(value)
  - Strip leading "Debit " / "Credit " from Description (case-insensitive)
  - Build notes: start with Memo value; if Check Number non-blank prepend "Check #X — "
  - Store raw Transaction Number as `transaction_number`
- Return list of parsed row dicts

---

## Bill-Transaction Linking Flow

Direction: **Register → Dashboard** (select a transaction, link it to a bill).

1. User selects a Payment-type transaction row in the Register table.
2. Clicks **🔗 Link to Bill**.
3. A `LinkBillDialog` opens — a scrollable list of **unlinked, unpaid** bill instances
   from the same month as the transaction (YYYY-MM of the transaction date).
4. User selects one bill instance and clicks **Link**.
5. App writes `bill_instances.transaction_id = transaction.id`.
6. App also sets `bill_instances.funded = 1` and `bill_instances.status = 'Paid'`
   (auto-fund + auto-pay in a single DB write).
7. Dialog closes; both Register and Dashboard refresh.

### Unlinking

1. User selects a linked transaction row.
2. Clicks **🗑 Unlink**.
3. Confirmation prompt: "Unlink this transaction from [bill description]? The bill will
   revert to unpaid."
4. App clears `bill_instances.transaction_id = NULL`, sets `status = 'Due'`,
   and sets `funded = 0`. Resetting funded prevents the bill from re-entering
   `funded_not_yet_paid` while the transaction (and its balance impact) is still
   in the register. The user can re-fund manually if needed.
5. Both tabs refresh.

### LinkBillDialog

A `CTkToplevel` with:
- Title: "Link Transaction to Bill"
- Transaction summary at top: Date | Description | Amount
- Scrollable table of eligible bill instances: Month | Description | Amount | Due Date | Funded?
- Shows **all** unlinked, unpaid bill instances across all months (not just the
  transaction's month) — this allows late-clearing transactions to pay past-month bills
- Sorted by month descending so the most recent bills appear first
- **Link** button (disabled until a bill is selected) and **Cancel**

---

## Delete All Transactions

1. User clicks **⚠ Delete All Transactions**.
2. Confirmation dialog: "This will permanently delete ALL N transactions and revert any
   bills linked to them to unpaid. This cannot be undone. Continue?"
3. On confirm:
   - Query all `bill_instances` where `transaction_id IS NOT NULL` → collect IDs
   - Set those instances: `status = 'Due'`, `transaction_id = NULL`, `funded = 0`
     (funded is reset for the same reason as unlinking — the transaction backing is
     gone, and leaving funded=1 would double-count against a balance that is also
     being wiped)
   - `DELETE FROM register_transactions`
4. Both Register and Dashboard refresh.

---

## Safe2Spend Calculation

```
Safe2Spend = current_balance - buffer - funded_not_yet_paid
```

Where:
- `current_balance` — derived from `account_settings.starting_balance` plus all
  Deposit transactions minus all Payment transactions (same running-balance logic as
  the Balance column)
- `buffer` — `account_settings.buffer` (default 0.00)
- `funded_not_yet_paid` — sum of `amount` for all bill instances where
  `funded = 1` AND `status = 'Due'` AND `deleted = 0`, across **all months** (not just
  current month — a bill funded in a future month still reduces spendable cash now)

Safe2Spend is displayed in the account info bar and recalculates whenever the DB changes.
It can be negative (shown in red).

---

## Orphaned Past-Month Bill Instances

When the month rolls over, bill instances that were never paid (never linked to a
transaction) remain in the DB. There are two cases:

### Funded but never paid

The instance has `funded=1, status='Due'` and continues to reduce Safe2Spend
indefinitely via `funded_not_yet_paid`. Two remedies:

1. **Link it** — if the payment eventually clears (even months later), import the CSV
   and link the transaction. The LinkBillDialog shows all months, so this always works.
2. **Mark Not Funded** — the existing dashboard toolbar button sets `funded=0`, removing
   the bill from `funded_not_yet_paid` and releasing its hold on Safe2Spend. Use this
   to write off a bill that will never get a matching transaction (e.g., a duplicate
   import, a cancelled bill, or cash paid outside the checking account with no
   transaction to link).

### Unfunded and never paid

The instance has `funded=0, status='Due'`. It has no impact on Safe2Spend and requires
no action. The user can link it to a transaction whenever one appears, or leave it as a
historical record. It will not reappear in future months (each month generates its own
instances from the definition).

---

## Soft Pay Flag

A **Soft Pay** checkbox on the Dashboard bill table — intended for Manual Pay bills
(payment_mode = "Manual Pay") but allowed on any bill instance for simplicity.

- Represents: "I know I paid this, but the transaction hasn't cleared my checking account yet."
- Does **not** change `status`, `funded`, or Safe2Spend.
- Stored in `bill_instances.soft_pay` (0/1).
- Visual indicator: a small checkbox or icon in the bill row (e.g., 💸 or ✓ in a
  "Soft" column).
- Toggle via a toolbar button or right-click context menu on the Dashboard.
- When a bill is later linked to a real transaction (and auto-paid), `soft_pay` is
  cleared automatically (it has served its purpose).

---

## Funding Enforcement

When the user clicks **Mark Funded** on one or more bill instances, the app must verify
the action is affordable before writing to the DB.

### Check logic

```
candidates = [b for b in selected if b.funded == 0]
affordable = sum(b.amount for b in candidates) <= current Safe2Spend
```

Only unfunded bills in the selection are checked and summed — already-funded bills are
no-ops and are excluded entirely. `current Safe2Spend` is computed fresh at the moment
of the click (not cached), so it reflects any funding that happened earlier in the
same session.

### Single-bill case

If `bill.amount > Safe2Spend`, block the action and show an inline error:
> "Cannot fund [description] ($X.XX) — Safe2Spend is only $Y.YY."

### Bulk-fund case

If the unfunded subset of the selection totals more than Safe2Spend, block the entire
batch and show:
> "Cannot fund N bills ($X.XX total) — Safe2Spend is only $Y.YY."

No partial funding of the batch. The user must deselect some bills and retry.

### Bills with no amount

If a bill instance has a NULL or $0.00 amount, the constraint is trivially satisfied —
allow funding without a check (funding a $0 bill doesn't reduce Safe2Spend).

### Already-funded bills

"Mark Funded" on an already-funded bill is a no-op — no check needed.

---

## Code Locations

| What                                | Where                                                         |
|-------------------------------------|---------------------------------------------------------------|
| Schema migrations (all 3)           | `db.init_db()` — ALTER TABLE try/except blocks                |
| `transaction_number` in insert      | `db.insert_transaction()`                                     |
| `transaction_id` / `soft_pay` ops   | New `db.link_bill_to_transaction()`, `db.unlink_transaction()`, `db.toggle_soft_pay()` |
| `buffer` read/write                 | `db.get_account_settings()` / `db.set_account_settings()`    |
| `get_funded_not_paid_total()`       | New function in `db.py` — sum across all months               |
| CSV parsing function                | `parse_bank_csv(path)` — new function in `app.py`             |
| Existing txn number lookup          | `db.get_imported_transaction_numbers()` — new fn in `db.py`  |
| Import trigger method               | `RegisterTab._import_csv()` in `app.py`                      |
| Link to Bill button + dialog        | `RegisterTab._link_to_bill()` + `LinkBillDialog` in `app.py` |
| Unlink button                       | `RegisterTab._unlink_transaction()` in `app.py`               |
| Delete All button                   | `RegisterTab._delete_all_transactions()` in `app.py`          |
| Safe2Spend label                    | Computed in `RegisterTab._refresh_safe2spend()`, shown in account info bar |
| Funding enforcement check           | `CombinedDashboard._mark_funded()` — calls `db.get_safe2spend()` then validates before writing |
| Buffer field                        | Inline entry in `RegisterTab` account info bar                |
| Soft Pay toggle                     | `DashboardTab` toolbar button + `db.toggle_soft_pay()`        |
| Soft Pay column                     | Added to Dashboard bill table                                 |

---

## Out of Scope for This Plan

- Supporting multiple bank CSV formats or multiple checking accounts
- Auto-categorization or description normalization beyond prefix stripping
- Fuzzy bill-matching (auto-suggesting which transaction matches which bill)
- Exporting or printing the register
