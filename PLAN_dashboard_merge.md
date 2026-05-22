# Plan: Merge Dashboard + Bills into Single Dashboard Tab

## Goal
Combine the current Dashboard and Bills tabs into one "Dashboard" tab.
The Definitions tab is unchanged.

## New Tab Layout (top to bottom)

1. **Month navigation bar** (fixed 42px) — left arrow, month label, right arrow
2. **Metrics panel** (natural height, no scroll) — KPI cards row + account bar chart
3. **Action toolbar** (fixed 44px) — Add Bill, Edit, Mark Paid, Delete, Export CSV
4. **Bills Treeview** (expands to fill remaining space) — full bill grid for the active month

The "Next Bills Due" preview section from the old Dashboard is dropped entirely.

## Classes to change

### 1. Remove `DashboardTab` class entirely
It is replaced by the new combined class below.

### 2. Rename / replace `BillsTab` with `CombinedDashboard`
The new class absorbs everything from both old classes.

**`_build()` structure:**
```
_nav_bar        CTkFrame, height=42, fg_color=C["card"]   — static, just toggled on refresh
_metrics_panel  CTkFrame, fg_color="transparent"           — destroyed/rebuilt on refresh
_toolbar        CTkFrame, height=44, fg_color=C["card2"]  — static
_tree_container tk.Frame                                   — static, treeview lives here
```

**`_build()` steps:**
- Build `_nav_bar` with left button, `_month_lbl`, right button (same as current BillsTab nav bar).
- Build empty `_metrics_panel` (populated in `refresh()`).
- Build `_toolbar` with buttons: `+ Add Bill`, `✎ Edit`, `✓ Mark Paid`, `🗑 Delete`, `⬇ Export CSV` (same as current BillsTab toolbar).
- Build `_tree_container` + Treeview + scrollbars (identical to current BillsTab).

**`refresh(annotated, summary, month_key)` steps:**
1. Update `_month_lbl` text.
2. Update left/right button enabled states.
3. Clear `_metrics_panel` children, then rebuild:
   - KPI cards row (4 cards: Total Bills, Total Due, Total Paid, Overdue) — copied from `DashboardTab.refresh()`.
   - Account bar chart section — copied from `DashboardTab.refresh()`.
   - Do NOT add "Next Bills Due" section.
4. Clear and repopulate the Treeview rows (same as current `BillsTab.refresh()`).

**All action methods stay identical** (`_add`, `_edit`, `_mark_paid`, `_delete`, `_export`,
`_on_select`). No logic changes needed.

### 3. Update `MoneyTrackerApp`

**`__init__`:** no changes needed.

**`_build_ui()`:**
- Change tab list from `["Dashboard", "Bills", "Definitions"]` to `["Dashboard", "Definitions"]`.
- Remove `self._dash = DashboardTab(...)`.
- Remove `self._bills = BillsTab(...)`.
- Add `self._dashboard = CombinedDashboard(tabs.tab("Dashboard"), self)`.
- Keep `self._defs = DefinitionsTab(...)` unchanged.

**`refresh()`:**
```python
def refresh(self):
    annotated, summary = _load_and_annotate(self._current_month)
    definitions        = db.load_definitions(DB_PATH)
    self._dashboard.refresh(annotated, summary, self._current_month)
    self._defs.refresh(definitions)
    self._update_status(annotated, summary)
```
(Remove the two old separate `self._dash.refresh(...)` and `self._bills.refresh(...)` calls.)

## Helper class to keep

`_HBar` (used by the bar chart) — no changes needed.

`KPICard` — no changes needed.

## Files changed

| File | What changes |
|------|-------------|
| `app.py` | Remove `DashboardTab`; rename/rewrite `BillsTab` → `CombinedDashboard`; update `MoneyTrackerApp._build_ui()` and `refresh()` |

`db.py`, `calc.py`, `seed.py`, `wipe.py`, `tests/` — no changes.

## Execution notes for the implementing session

- Start by reading `app.py` in full before editing.
- Replace the entire `DashboardTab` class with nothing (delete it).
- Replace the entire `BillsTab` class with the new `CombinedDashboard` class.
- Edit `MoneyTrackerApp._build_ui()` and `refresh()` as described above.
- Run the app with `money-tracker` (or the direct launch command in CLAUDE.md) and verify:
  - Only two tabs appear: Dashboard and Definitions.
  - KPI cards and bar chart render at the top of Dashboard.
  - Full bill list renders below.
  - Month navigation arrows work.
  - Mark Paid, Edit, Add, Delete, Export all work.
  - Definitions tab is unaffected.
