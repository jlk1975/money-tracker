# Money Tracker — Claude Code Context

Personal household bill tracker for Jason & Heather. Tracks 19 bills across 3 accounts.

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
python3 seed.py    # populate definitions + generate June 2026 instances (run once on fresh db)
python3 wipe.py    # interactive: wipe instances only, or everything
```

## Architecture

| File | Purpose |
|------|---------|
| `db.py` | All SQLite access — two tables, see schema below |
| `calc.py` | Pure functions: `annotate_instances()`, `calculate_summary()` |
| `app.py` | customtkinter GUI — 3 tabs: Dashboard, Bills, Definitions |
| `seed.py` | One-time seeder using `tests/fixtures.py` sample data |
| `wipe.py` | Interactive wipe utility |
| `tests/fixtures.py` | 19 sample definitions + expected totals (SAMPLE_JUNE_TOTAL, SAMPLE_MAY_TOTAL) |

## Database schema

**`bill_definitions`** — source of truth for recurring bills
- `id`, `account`, `description`, `frequency`, `typical_amount`, `due_day`
- `months_active` — comma-separated month numbers for Annual/Semi-Annual/Quarterly (e.g. `"3,9"`)
- `adhoc_month` — YYYY-MM target for AdHoc bills (e.g. `"2026-06"`)
- `notes`, `active` (0/1), `sort_order`

**`bill_instances`** — one row per bill per month
- `id`, `definition_id`, `month_key` (YYYY-MM), `account`, `description`
- `status` (Due/Paid), `due_date` (MM/DD/YYYY), `amount`, `frequency`
- `date_paid`, `notes`, `row_order`

## Key concepts

- **Month key format**: `"YYYY-MM"` strings throughout
- **`generate_month_instances(month_key)`** — idempotent; creates instances from active definitions for that month; skips if any instances already exist
- **Frequency routing**: Monthly=every month; AdHoc=only in `adhoc_month`; Annual/Semi-Annual/Quarterly/Bi-Weekly/Weekly use `months_active`
- **`due_day` clamping**: clamped to actual month-end (e.g. day 31 → Feb 28)
- **Navigation**: left arrow = only to months with existing instances; right arrow = auto-generates up to 12 months ahead of today
- **`annotate_instances()`** adds `is_overdue` and `days_until_due` to each instance dict
- **`calculate_summary()`** returns `total_due`, `total_paid`, `bill_count`, `overdue_count`, `overdue_amount`, `by_account`

## Accounts
- **UWBC** — primary checking (most bills)
- **BOAC1** — Bank of America
- **Sam's Card** — credit card

## Expected totals (from fixtures)
- May 2026: 16 bills, $3,486.59 (Monthly only — no AdHoc)
- June 2026: 19 bills, $4,156.09 (Monthly + 3 AdHoc payoffs)
