# Money Tracker — Claude Code Context

Personal household bill tracker. Tracks recurring and one-off bills.

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
| `db.py` | All SQLite access — two tables, see schema below |
| `calc.py` | Pure functions: `annotate_instances()`, `calculate_summary()` |
| `app.py` | customtkinter GUI — 2 tabs: Dashboard, Definitions |
| `seed.py` | One-time seeder using `tests/fixtures.py` sample data |
| `wipe.py` | Interactive wipe utility |
| `tests/fixtures.py` | 19 sample definitions + expected totals (SAMPLE_JUNE_TOTAL, SAMPLE_MAY_TOTAL) |

## Database schema

**`bill_definitions`** — source of truth for recurring bills
- `id`, `description`, `frequency`, `typical_amount`, `due_day`
- `months_active` — comma-separated month numbers for Annual/Semi-Annual/Quarterly (e.g. `"3,9"`)
- `adhoc_month` — YYYY-MM target for AdHoc bills (e.g. `"2026-06"`)
- `notes`, `active` (0/1), `sort_order`

**`bill_instances`** — one row per bill per month
- `id`, `definition_id`, `month_key` (YYYY-MM), `description`
- `status` (Due/Paid), `due_date` (MM/DD/YYYY), `amount`, `frequency`
- `date_paid`, `notes`, `row_order`
- `funded` (0/1) — whether the bill has been funded for the month (default 0)

## Key concepts

- **Month key format**: `"YYYY-MM"` strings throughout
- **`generate_month_instances(month_key)`** — idempotent; creates instances from active definitions for that month; skips if any instances already exist
- **Frequency routing**: Monthly=every month; AdHoc=only in `adhoc_month`; Annual/Semi-Annual/Quarterly/Bi-Weekly/Weekly use `months_active`
- **`due_day` clamping**: clamped to actual month-end (e.g. day 31 → Feb 28)
- **Navigation**: left arrow = only to months with existing instances; right arrow = auto-generates up to 12 months ahead of today
- **`annotate_instances()`** returns instances as a new list of dicts (no longer adds computed fields)
- **`calculate_summary()`** returns `total_due`, `total_paid`, `bill_count`
- **Funded workflow**: bills must be marked Funded before they can be marked Paid; toolbar has Mark Funded / Mark Not Funded / Mark Paid / Mark Unpaid buttons
- **Dashboard tab**: 2 rows of 4 KPI cards (Total Bills, Payment Progress, Paid, Due / Funded Not Paid (YNAB), Funding Progress, Funded, Not Funded) + full bill grid with sortable columns; Definitions tab unchanged

## Expected totals (from fixtures)
- May 2026: 16 bills, $3,486.59 (Monthly only — no AdHoc)
- June 2026: 19 bills, $4,156.09 (Monthly + 3 AdHoc payoffs)
