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
| `db.py` | All SQLite access — two tables, see schema below |
| `calc.py` | Pure functions: `annotate_instances()`, `calculate_summary()`, `funded_through_parts()` |
| `app.py` | customtkinter GUI — 2 tabs: Dashboard, Definitions |
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
- **`funded_through_parts(instances, month_key)`** returns `(days_str, caption_str)` — consecutive funded-through date for unpaid bills from today; days_str is `"X days"`, `"today"`, or `"0 days"`
- **Funded workflow**: bills must be marked Funded before they can be marked Paid; toolbar has Mark Funded / Mark Not Funded / Mark Paid / Mark Unpaid buttons
- **Tab switching**: no CTkTabview — manual frame-swap via `_switch_tab()`; "Dashboard" / "Definitions" buttons centered in header; active tab highlighted in blue, inactive in `C["card2"]`
- **Header**: 💰 emoji (size 36) on left and right ends; tab buttons centered via 3-column grid layout; window title is "Bill Tracker"
- **Dashboard tab**: 2 rows of 4 widgets + collapsible toggle; Definitions tab unchanged
  - Row 1: `VibeBarsCard` (horizontal bar chart by vibe emoji), Payment Progress, Paid, Due
  - Row 2: Funded Not Paid, Funding Progress, Funded, Not Funded
  - Right sidebar: Spending by Vibe + By Pay Mode breakdowns
  - Nav bar vibe filter buttons (🌟 🤷 💔): toggle to filter table + all 8 KPI widgets to selected vibes; none selected = show all; stored in `_vibe_filter` set on `CombinedDashboard`
  - **Funding Progress** widget label is dynamic: shows `"Funded through [date] · [days]"` (from `funded_through_parts()`); falls back to `"Funding Progress"` when nothing is funded
  - **Due** and **Not Funded** KPI values turn green when $0.00, red otherwise
  - **Toolbar** (dashboard only): search box filters table rows live by description; "Show Paid (N)" and "Show Unpaid (N)" toggle buttons filter by status — mutually exclusive, counts reflect current vibe-filtered display; search and status filter stack
- **VibeBarsCard**: replaces old "Total Bills" KPI; tk.Canvas with `height=1` hint (prevents Tk 150px default); draws horizontal bars — emoji left, bar, count right; bars spread evenly to fill card height via `_paint` on `<Configure>`
- **`_draw` conflict**: `ctk.CTkFrame` calls `self._draw()` internally — never name a canvas paint method `_draw` in a CTkFrame subclass; use `_paint` instead

## Expected totals (from fixtures)
- May 2026: 16 bills, $3,486.59 (Monthly only — no AdHoc)
- June 2026: 19 bills, $4,156.09 (Monthly + 3 AdHoc payoffs)
