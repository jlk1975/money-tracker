"""
app.py — Money Tracker main application.
Two tabs: Bill Dashboard (summary + nav + bill grid), Bill Definitions (master bill template list).
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import os
import json
import calendar
from datetime import date

import db
import calc

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_DATA_DIR     = os.path.join(os.path.expanduser("~"), ".local", "share", "money-tracker")
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH       = os.path.join(_DATA_DIR, "money_tracker.db")
SETTINGS_PATH = os.path.join(_DATA_DIR, "settings.json")

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#1e1e2e",
    "card":    "#2a2a3e",
    "card2":   "#252538",
    "border":  "#3a3a55",
    "text":    "#e0e0f0",
    "muted":   "#888899",
    "green":   "#4ade80",
    "red":     "#f87171",
    "blue":    "#60a5fa",
    "yellow":  "#fbbf24",
    "purple":  "#c084fc",
    "teal":    "#2dd4bf",
    "orange":  "#fb923c",
    "heading": "#8ab4f8",
}

STATUSES      = ["Due", "Paid"]
FREQUENCIES   = ["Monthly", "AdHoc", "Annual", "Semi-Annual", "Quarterly", "Bi-Weekly", "Weekly"]
PAYMENT_MODES = ["—", "🤖", "🔔"]
_PM_LEGACY    = {"Auto Pay": "🤖", "Manual Pay": "🔔"}
VIBES         = ["—", "🌟", "🤷", "💔"]
_VIBE_LEGACY  = {"Good": "🌟", "Meh": "🤷", "Regret": "💔"}
MONTH_NAMES   = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Bills tab grid ────────────────────────────────────────────────────────────
GRID_COLUMNS = [
    ("Vibe",       50),
    ("✓",          40),
    ("Status",     70),
    ("Pay Mode",   65),
    ("Expense",   240),
    ("Due Date",   90),
    ("Amount",     90),
    ("Frequency",  90),
    ("Date Paid",  90),
    ("Funded",     70),
]
LEFT_ALIGN = {"Status", "Expense", "Due Date", "Frequency", "Date Paid"}

# ── Definitions tab grid ──────────────────────────────────────────────────────
DEF_COLUMNS = [
    ("Vibe",        50),
    ("Active",      55),
    ("Description",230),
    ("Frequency",  100),
    ("Pay Mode",    80),
    ("Typical $",   90),
    ("Due Day",     65),
    ("Due In",     150),
    ("Notes",      150),
]
DEF_LEFT_ALIGN = {"Description", "Frequency", "Due In", "Notes"}

# ── Debt tab grid ─────────────────────────────────────────────────────────────
DEBT_COLUMNS = [
    ("Days Left",      80),
    ("Payoff Date",   105),
    ("Debt",          220),
    ("Balance",        95),
    ("Monthly Pmt",    95),
    ("Rate",           65),
    ("Notes",         200),
]
DEBT_LEFT_ALIGN = {"Debt", "Payoff Date"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val):
    if val is None:
        return ""
    if val == 0.0:
        return "$0.00"
    sign = "-" if val < 0 else ""
    return f"{sign}${abs(val):,.2f}"


def _payment_emoji(mode):
    v = _PM_LEGACY.get(mode, mode)
    return v if v in ("🤖", "🔔") else "❓"


def _vibe_emoji(vibe):
    v = _VIBE_LEGACY.get(vibe, vibe)
    return v if v in ("🌟", "🤷", "💔") else ""


def _month_label(month_key):
    year, month = map(int, month_key.split("-"))
    return f"{calendar.month_name[month]} {year}"


def _add_months(month_key, n):
    year, month = map(int, month_key.split("-"))
    month += n
    year  += (month - 1) // 12
    month  = ((month - 1) % 12) + 1
    return f"{year:04d}-{month:02d}"


def _max_future_month():
    today = date.today()
    return _add_months(f"{today.year:04d}-{today.month:02d}", 12)


def _load_and_annotate(month_key):
    raw       = db.load_instances(month_key, DB_PATH)
    annotated = calc.annotate_instances(raw) if raw else []
    summary   = calc.calculate_summary(annotated)
    return annotated, summary


def _merge_row(inst):
    return (
        _vibe_emoji(inst.get("vibe", "")),
        "✓" if inst.get("status") == "Paid" else "",
        inst.get("status", ""),
        _payment_emoji(inst.get("payment_mode", "")),
        inst.get("description", ""),
        inst.get("due_date", ""),
        _fmt(inst.get("amount")),
        inst.get("frequency", ""),
        inst.get("date_paid", ""),
        "✓" if inst.get("funded") else "",
    )


def _inst_tag(inst):
    if inst.get("funded") and inst.get("status") != "Paid":
        return "funded"
    return inst.get("status", "due").lower()


def _format_due_in(defn):
    freq = defn.get("frequency", "")
    if freq == "Monthly":
        return "Every month"
    if freq == "AdHoc":
        adhoc = defn.get("adhoc_month", "")
        if adhoc:
            try:
                y, m = adhoc.split("-")
                return f"{MONTH_NAMES[int(m)-1]} {y}"
            except Exception:
                return adhoc
        return "—"
    months_str = defn.get("months_active", "")
    if months_str:
        try:
            nums = [int(m.strip()) for m in months_str.split(",") if m.strip().isdigit()]
            return ", ".join(MONTH_NAMES[n-1] for n in nums if 1 <= n <= 12)
        except Exception:
            return months_str
    return "—"


def _merge_defn_row(defn):
    return (
        _vibe_emoji(defn.get("vibe", "")),
        "✓" if defn.get("active") else "✗",
        defn.get("description", ""),
        defn.get("frequency", ""),
        _payment_emoji(defn.get("payment_mode", "")),
        _fmt(defn.get("typical_amount")),
        str(defn.get("due_day", "")),
        _format_due_in(defn),
        defn.get("notes", ""),
    )


def _days_until_payoff(payoff_date_str):
    if not payoff_date_str:
        return "—"
    try:
        parts = payoff_date_str.split("/")
        if len(parts) != 3:
            return "—"
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        delta = (date(y, m, d) - date.today()).days
        if delta < 0:
            return "Paid"
        if delta == 0:
            return "Today"
        return f"{delta:,}"
    except Exception:
        return "—"


def _merge_debt_row(debt, balance):
    return (
        _days_until_payoff(debt.get("payoff_date", "")),
        debt.get("payoff_date", "") or "N/A",
        debt.get("name", ""),
        _fmt(balance) if balance is not None else "—",
        _fmt(debt.get("monthly_payment", 0)),
        f"{debt.get('interest_rate', 0):.2f}%",
        debt.get("notes", ""),
    )


# ── KPI / Progress Cards ──────────────────────────────────────────────────────

class ProgressCard(ctk.CTkFrame):
    def __init__(self, parent, label, progress, sub=None, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=12),
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(8, 3))
        bar = ctk.CTkProgressBar(self, progress_color=C["green"],
                                  fg_color=C["border"])
        bar.set(max(0.0, min(1.0, progress)))
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 3))
        if sub:
            ctk.CTkLabel(self, text=sub, font=ctk.CTkFont(size=11),
                         text_color=C["muted"], anchor="w").grid(
                row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        else:
            ctk.CTkFrame(self, height=4, fg_color="transparent").grid(row=2, column=0)


class KPICard(ctk.CTkFrame):
    def __init__(self, parent, label, value_str, value_color=None, sub=None, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=12),
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(8, 2))
        ctk.CTkLabel(self, text=value_str,
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=value_color or C["text"], anchor="w").grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 2))
        if sub:
            ctk.CTkLabel(self, text=sub, font=ctk.CTkFont(size=11),
                         text_color=C["muted"], anchor="w").grid(
                row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        else:
            ctk.CTkFrame(self, height=4, fg_color="transparent").grid(row=2, column=0)



class VibeBarsCard(ctk.CTkFrame):
    _COLORS = {"🌟": "#4ade80", "🤷": "#60a5fa", "💔": "#f87171", "": "#555566"}

    def __init__(self, parent, vibe_counts, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self._counts = {k: v for k, v in vibe_counts.items() if v > 0}
        self._max    = max(self._counts.values()) if self._counts else 1
        self._canvas = tk.Canvas(self, bg=C["card"], highlightthickness=0, height=1)
        self._canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self._canvas.bind("<Configure>", self._paint)

    def _paint(self, _=None):
        self._canvas.delete("all")
        w, h = self._canvas.winfo_width(), self._canvas.winfo_height()
        if w < 10 or h < 10 or not self._counts:
            return
        vibes      = [e for e in ("🌟", "🤷", "💔", "") if e in self._counts]
        n          = len(vibes)
        pad_left   = 28
        pad_right  = 30
        pad_y      = 8
        bar_h      = 16  # fixed to match emoji glyph height
        bar_area_w = w - pad_left - pad_right
        slot_h     = (h - 2 * pad_y) / n  # spread evenly across available height
        for i, emoji in enumerate(vibes):
            count  = self._counts[emoji]
            bar_w  = max(4, int(bar_area_w * count / self._max))
            cy     = int(pad_y + slot_h * i + slot_h / 2)
            y0, y1 = cy - bar_h // 2, cy + bar_h // 2
            x0, x1 = pad_left, pad_left + bar_w
            self._canvas.create_rectangle(x0, y0, x1, y1,
                                          fill=self._COLORS.get(emoji, C["muted"]),
                                          outline="")
            self._canvas.create_text(pad_left - 4, cy, text=emoji or "?",
                                     anchor="e", fill=C["text"], font=("Helvetica", 13))
            self._canvas.create_text(x1 + 5, cy, text=str(count),
                                     anchor="w", fill=C["text"], font=("Helvetica", 10, "bold"))


class _HBar(tk.Canvas):
    def __init__(self, parent, label, value, max_value, color):
        super().__init__(parent, bg=C["card"], highlightthickness=0, height=34)
        self._data = (label, value, max_value, color)
        self.bind("<Configure>", self._draw)

    def _draw(self, _=None):
        label, value, max_value, color = self._data
        self.delete("all")
        w = self.winfo_width()
        if w < 10:
            return
        lw, bar_x, bar_h, y = 130, 138, 18, 8
        bw = w - lw - 100
        self.create_text(lw - 4, y + bar_h // 2, text=label,
                         anchor="e", fill=C["muted"], font=("Helvetica", 11))
        self.create_rectangle(bar_x, y, bar_x + bw, y + bar_h, fill="#333350", outline="")
        fw = int(bw * min(value / max_value, 1.0)) if max_value else 0
        if fw > 0:
            self.create_rectangle(bar_x, y, bar_x + fw, y + bar_h, fill=color, outline="")
        self.create_text(bar_x + bw + 8, y + bar_h // 2, text=_fmt(value),
                         anchor="w", fill=C["text"], font=("Consolas", 11))


# ── Combined Dashboard Tab ────────────────────────────────────────────────────

class CombinedDashboard(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._app = app
        self._selected_id = None
        self._sort_col = None
        self._sort_asc = True
        self._metrics_visible = True
        self._vibe_filter = set()
        self._vibe_btns = {}
        self._display = []
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search_filter())
        self._status_filter = None
        self._status_btns = {}
        self._build()

    def _build(self):
        self._nav_bar = ctk.CTkFrame(self, height=42, corner_radius=0, fg_color=C["card"])
        self._nav_bar.pack(fill="x")
        self._nav_bar.pack_propagate(False)

        self._left_btn = ctk.CTkButton(self._nav_bar, text="◀", width=36, height=28,
                                        command=self._app.navigate_left)
        self._left_btn.pack(side="left", padx=(10, 4), pady=7)

        self._month_lbl = ctk.CTkLabel(self._nav_bar, text="",
                                        font=ctk.CTkFont(size=15, weight="bold"),
                                        text_color=C["heading"], width=160)
        self._month_lbl.pack(side="left", padx=6)

        self._right_btn = ctk.CTkButton(self._nav_bar, text="▶", width=36, height=28,
                                         command=self._app.navigate_right)
        self._right_btn.pack(side="left", padx=(0, 4), pady=7)

        ctk.CTkButton(self._nav_bar, text="This Month", width=90, height=28,
                      command=self._app.navigate_to_today).pack(
            side="left", padx=(10, 0), pady=7)

        for emoji, color in [("🌟", C["green"]), ("🤷", C["blue"]), ("💔", C["red"])]:
            btn = ctk.CTkButton(self._nav_bar, text=emoji, width=36, height=28,
                                fg_color=C["border"], hover_color=C["card2"],
                                command=lambda e=emoji: self._toggle_vibe_filter(e))
            btn.pack(side="left", padx=(6, 0), pady=7)
            self._vibe_btns[emoji] = (btn, color)

        self._month_total_lbl = ctk.CTkLabel(
            self._nav_bar, text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=C["heading"],
        )
        self._month_total_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._toggle_btn = ctk.CTkButton(self._nav_bar, text="▲ Hide Summary",
                                          width=120, height=28,
                                          command=self._toggle_metrics)
        self._toggle_btn.pack(side="right", padx=(0, 10), pady=7)

        self._metrics_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._metrics_panel.pack(fill="x")

        self._toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        self._toolbar.pack(fill="x")
        self._toolbar.pack_propagate(False)
        for label, cmd, width in [
            ("All Funded/Unfunded", self._mark_all_funded_unfunded, 145),
            ("All Paid/Unpaid",     self._mark_all_paid_unpaid,     128),
            ("Funded/Unfunded",     self._toggle_funded,            120),
            ("Paid/Unpaid",         self._toggle_paid,              110),
            ("+ Add Bill",          self._add,                      110),
            ("✎ Edit",              self._edit,                      80),
            ("🗑 Delete",            self._delete,                    90),
        ]:
            ctk.CTkButton(self._toolbar, text=label, width=width, height=30,
                          command=cmd).pack(side="left", padx=6, pady=7)
        ctk.CTkEntry(self._toolbar, textvariable=self._search_var,
                     placeholder_text="🔍  Search bills...",
                     width=200, height=30).pack(side="left", padx=(12, 0), pady=7)
        for label, status, color in [("Show Paid", "Paid", C["green"]),
                                      ("Show Unpaid", "Due", C["red"])]:
            btn = ctk.CTkButton(self._toolbar, text=label, width=100, height=30,
                                fg_color=C["border"], hover_color=C["card2"],
                                command=lambda s=status: self._toggle_status_filter(s))
            btn.pack(side="left", padx=(8, 0), pady=7)
            self._status_btns[status] = (btn, color)

        self._bottom = tk.Frame(self, bg="#1a1a2e")
        self._bottom.pack(fill="both", expand=True)

        self._sidebar = ctk.CTkFrame(self._bottom, width=210, fg_color=C["card"],
                                      corner_radius=0, border_width=1,
                                      border_color=C["border"])
        self._sidebar.pack(side="right", fill="y")
        self._sidebar.pack_propagate(False)

        self._tree_container = tk.Frame(self._bottom, bg="#1a1a2e")
        self._tree_container.pack(side="left", fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Money.Treeview",
                        background="#2b2b3b", foreground="#e0e0e0",
                        fieldbackground="#2b2b3b", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Money.Treeview.Heading",
                        background="#1f1f2e", foreground="#8ab4f8",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Money.Treeview",
                  background=[("selected", "#3a5a8a")],
                  foreground=[("selected", "#ffffff")])

        col_ids = [c[0] for c in GRID_COLUMNS]
        vsb = ttk.Scrollbar(self._tree_container, orient="vertical")
        hsb = ttk.Scrollbar(self._tree_container, orient="horizontal")
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree = ttk.Treeview(self._tree_container, columns=col_ids, show="headings",
                                   style="Money.Treeview",
                                   yscrollcommand=vsb.set,
                                   xscrollcommand=hsb.set,
                                   selectmode="browse")
        vsb.config(command=self._tree.yview)
        hsb.config(command=self._tree.xview)
        self._tree.pack(fill="both", expand=True)

        for col, width in GRID_COLUMNS:
            anchor = "w" if col in LEFT_ALIGN else "e"
            self._tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=50, anchor=anchor, stretch=False)

        self._tree.tag_configure("due",    background="#3a1e1e", foreground="#f08080")
        self._tree.tag_configure("paid",   background="#1e3a2f", foreground="#7defa7")
        self._tree.tag_configure("funded", background="#2e2a00", foreground="#ffd700")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit())

    def _toggle_metrics(self):
        if self._metrics_visible:
            self._metrics_panel.pack_forget()
            self._toggle_btn.configure(text="▼ Show Summary")
        else:
            self._metrics_panel.pack(fill="x", before=self._toolbar)
            self._toggle_btn.configure(text="▲ Hide Summary")
        self._metrics_visible = not self._metrics_visible

    def _toggle_vibe_filter(self, emoji):
        if emoji in self._vibe_filter:
            self._vibe_filter.discard(emoji)
        else:
            self._vibe_filter.add(emoji)
        for e, (btn, color) in self._vibe_btns.items():
            btn.configure(fg_color=color if e in self._vibe_filter else C["border"])
        self._app.refresh()

    def _refresh_sidebar(self, annotated):
        for w in self._sidebar.winfo_children():
            w.destroy()
        if not annotated:
            return

        def _section(title):
            ctk.CTkLabel(self._sidebar, text=title,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=C["heading"], anchor="w").pack(
                fill="x", padx=14, pady=(14, 4))

        def _row(label, amount, color=None):
            f = ctk.CTkFrame(self._sidebar, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=12),
                         text_color=C["text"], anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=_fmt(amount),
                         font=ctk.CTkFont(size=12),
                         text_color=color or C["muted"], anchor="e").pack(side="right")

        def _divider():
            tk.Frame(self._sidebar, height=1, bg=C["border"]).pack(
                fill="x", padx=14, pady=(8, 0))

        # ── Vibe breakdown ────────────────────────────────────────────
        vibe_totals = {}
        for inst in annotated:
            v = _vibe_emoji(inst.get("vibe", ""))
            vibe_totals[v] = vibe_totals.get(v, 0) + inst.get("amount", 0)

        _section("Spending by Vibe")
        for emoji, label, color in [
            ("🌟", "Good",    C["green"]),
            ("🤷", "Meh",    C["blue"]),
            ("💔", "Regret", C["red"]),
        ]:
            if emoji in vibe_totals:
                _row(f"{emoji}  {label}", vibe_totals[emoji], color)
        if "" in vibe_totals:
            _row("   Not Set", vibe_totals[""])

        # ── Pay Mode breakdown ────────────────────────────────────────
        _divider()
        pm_totals = {}
        for inst in annotated:
            pm = _payment_emoji(inst.get("payment_mode", ""))
            pm_totals[pm] = pm_totals.get(pm, 0) + inst.get("amount", 0)

        _section("By Pay Mode")
        for emoji, label, color in [
            ("🤖", "Auto Pay", C["teal"]),
            ("🔔", "Manual",   C["yellow"]),
        ]:
            if emoji in pm_totals:
                _row(f"{emoji}  {label}", pm_totals[emoji], color)
        if "❓" in pm_totals:
            _row("   Not Set", pm_totals["❓"])

    def get_column_widths(self):
        return {col: self._tree.column(col, "width") for col, _ in GRID_COLUMNS}

    def set_column_widths(self, widths):
        for col, _ in GRID_COLUMNS:
            if col in widths:
                self._tree.column(col, width=widths[col])

    def refresh(self, annotated, summary, month_key):
        year, month = map(int, month_key.split("-"))
        self._month_lbl.configure(text=f"{calendar.month_name[month]} {year}")
        self._left_btn.configure(
            state="normal" if self._app.can_navigate_left() else "disabled")
        self._right_btn.configure(
            state="normal" if self._app.can_navigate_right() else "disabled")

        month_total = summary["total_due"] + summary["total_paid"]
        self._month_total_lbl.configure(text=f"Bills This Month:  ${month_total:,.2f}")

        if self._vibe_filter:
            display = [b for b in annotated
                       if _vibe_emoji(b.get("vibe", "")) in self._vibe_filter]
            summary = calc.calculate_summary(display)
        else:
            display = annotated

        for w in self._metrics_panel.winfo_children():
            w.destroy()

        if display:
            pad = {"padx": 18, "pady": 4}

            row1 = ctk.CTkFrame(self._metrics_panel, fg_color="transparent")
            row1.pack(fill="x", **pad)
            for col in range(4):
                row1.grid_columnconfigure(col, weight=1, uniform="k1")
            row1.grid_rowconfigure(0, weight=1)

            _vibe_counts = {}
            for _b in display:
                _v = _vibe_emoji(_b.get("vibe", ""))
                _vibe_counts[_v] = _vibe_counts.get(_v, 0) + 1
            VibeBarsCard(row1, _vibe_counts).grid(
                row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
            _paid  = summary.get("total_paid", 0)
            _due   = summary.get("total_due",  0)
            _total = _paid + _due
            _pct   = (_paid / _total) if _total else 0
            ProgressCard(row1, "Payment Progress", _pct,
                         sub=f"{_pct*100:.0f}%  —  {_fmt(_paid)} of {_fmt(_total)}").grid(
                row=0, column=1, sticky="nsew", padx=6, pady=4)
            KPICard(row1, "Paid",
                    _fmt(summary.get("total_paid", 0)), C["green"]).grid(
                row=0, column=2, sticky="nsew", padx=6, pady=4)
            _due = summary.get("total_due", 0)
            KPICard(row1, "Due",
                    _fmt(_due), C["green"] if _due == 0 else C["red"],
                    sub="Unpaid balance").grid(
                row=0, column=3, sticky="nsew", padx=(6, 0), pady=4)

            row2 = ctk.CTkFrame(self._metrics_panel, fg_color="transparent")
            row2.pack(fill="x", **pad)
            for col in range(4):
                row2.grid_columnconfigure(col, weight=1, uniform="k2")
            row2.grid_rowconfigure(0, weight=1)

            _funded_not_paid = sum(b.get("amount", 0) for b in display
                                   if b.get("funded") and b.get("status") != "Paid")
            KPICard(row2, "Funded Not Paid", _fmt(_funded_not_paid), C["yellow"]).grid(
                row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
            _funded_total = sum(b.get("amount", 0) for b in display if b.get("funded"))
            _funded_total2  = sum(b.get("amount", 0) for b in display if b.get("funded"))
            _total2         = sum(b.get("amount", 0) for b in display)
            _fpct           = (_funded_total2 / _total2) if _total2 else 0
            _days_str, _caption_str = calc.funded_through_parts(display, month_key)
            _progress_label = (f"{_caption_str} · {_days_str}"
                               if _days_str != "0 days" else "Funding Progress")
            ProgressCard(row2, _progress_label, _fpct,
                         sub=f"{_fpct*100:.0f}%  —  {_fmt(_funded_total2)} of {_fmt(_total2)}").grid(
                row=0, column=1, sticky="nsew", padx=6, pady=4)
            KPICard(row2, "Funded", _fmt(_funded_total), C["green"]).grid(
                row=0, column=2, sticky="nsew", padx=6, pady=4)
            _not_funded_total = sum(b.get("amount", 0) for b in display if not b.get("funded"))
            KPICard(row2, "Not Funded", _fmt(_not_funded_total),
                    C["green"] if _not_funded_total == 0 else C["red"]).grid(
                row=0, column=3, sticky="nsew", padx=(6, 0), pady=4)


        self._display = display
        self._update_status_btn_labels()
        self._apply_search_filter()
        self._refresh_sidebar(display)

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._apply_sort()

    def _update_status_btn_labels(self):
        counts = {"Paid": 0, "Due": 0}
        for b in self._display:
            s = b.get("status")
            if s in counts:
                counts[s] += 1
        labels = {"Paid": f"Show Paid ({counts['Paid']})",
                  "Due":  f"Show Unpaid ({counts['Due']})"}
        for status, (btn, _) in self._status_btns.items():
            btn.configure(text=labels[status])

    def _toggle_status_filter(self, status):
        self._status_filter = None if self._status_filter == status else status
        for s, (btn, color) in self._status_btns.items():
            btn.configure(fg_color=color if s == self._status_filter else C["border"])
        self._apply_search_filter()

    def _apply_search_filter(self):
        q = self._search_var.get().strip().lower()
        rows = self._display
        if q:
            rows = [b for b in rows if q in b.get("description", "").lower()]
        if self._status_filter:
            rows = [b for b in rows if b.get("status") == self._status_filter]
        self._tree.delete(*self._tree.get_children())
        self._selected_id = None
        for inst in rows:
            self._tree.insert("", "end", iid=str(inst["id"]),
                              values=_merge_row(inst), tags=(_inst_tag(inst),))
        if self._sort_col:
            self._apply_sort()

    def _apply_sort(self):
        for col, _ in GRID_COLUMNS:
            self._tree.heading(col, text=col)
        arrow = " ▲" if self._sort_asc else " ▼"
        self._tree.heading(self._sort_col, text=self._sort_col + arrow)
        items = [(self._tree.set(k, self._sort_col), k)
                 for k in self._tree.get_children("")]
        if self._sort_col == "Vibe":
            set_items   = [(v, k) for v, k in items if v]
            unset_items = [(v, k) for v, k in items if not v]
            set_items.sort(key=lambda x: self._sort_key("Vibe", x[0]),
                           reverse=not self._sort_asc)
            items = set_items + unset_items
        else:
            items.sort(key=lambda x: self._sort_key(self._sort_col, x[0]),
                       reverse=not self._sort_asc)
        for idx, (_, k) in enumerate(items):
            self._tree.move(k, "", idx)

    def _sort_key(self, col, val):
        if col == "Vibe":
            return {"🌟": 0, "🤷": 1, "💔": 2}.get(val, 3)
        if col == "Amount":
            try:
                return float(val.replace("$", "").replace(",", ""))
            except ValueError:
                return 0.0
        if col in ("Due Date", "Date Paid"):
            if not val:
                return (9999, 99, 99)
            try:
                m, d, y = val.split("/")
                return (int(y), int(m), int(d))
            except Exception:
                return (9999, 99, 99)
        return val.lower()

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _add(self):
        InstDialog(self, self._app, mode="add",
                   month_key=self._app.current_month())

    def _edit(self):
        if not self._selected_id:
            self._app.flash("Select a bill to edit.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if inst:
            InstDialog(self, self._app, mode="edit", inst=inst)

    def _toggle_paid(self):
        if not self._selected_id:
            self._app.flash("Select a bill to toggle paid status.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if inst.get("status") == "Paid":
            updated = dict(inst)
            updated["status"]    = "Due"
            updated["date_paid"] = ""
            db.update_instance(self._selected_id, updated, DB_PATH)
            self._app.refresh()
            self._app.flash(f"Marked unpaid: {inst.get('description', '')[:40]}")
        else:
            if not inst.get("funded"):
                self._app.flash("Bill must be funded before it can be marked paid.")
                return
            updated = dict(inst)
            updated["status"]    = "Paid"
            updated["date_paid"] = date.today().strftime("%m/%d/%Y")
            db.update_instance(self._selected_id, updated, DB_PATH)
            self._app.refresh()
            self._app.flash(f"Marked paid: {inst.get('description', '')[:40]}")

    def _toggle_funded(self):
        if not self._selected_id:
            self._app.flash("Select a bill to toggle funded status.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        new_val = 0 if inst.get("funded") else 1
        updated = dict(inst)
        updated["funded"] = new_val
        db.update_instance(self._selected_id, updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked {'funded' if new_val else 'not funded'}: {inst.get('description', '')[:40]}")

    def _delete(self):
        if not self._selected_id:
            self._app.flash("Select a bill to delete.")
            return
        ConfirmDialog(self, self._app,
                      "Delete this bill from this month?\nThis cannot be undone.",
                      lambda: (db.delete_instance(self._selected_id, DB_PATH),
                               self._app.refresh()))

    def _visible_bills(self):
        annotated, _ = _load_and_annotate(self._app.current_month())
        if self._vibe_filter:
            return [b for b in annotated
                    if _vibe_emoji(b.get("vibe", "")) in self._vibe_filter]
        return annotated

    def _mark_all_funded_unfunded(self):
        bills = self._visible_bills()
        if not bills:
            self._app.flash("No bills to update.")
            return
        all_funded = all(b.get("funded") for b in bills)
        new_val = 0 if all_funded else 1
        for inst in bills:
            updated = dict(inst)
            updated["funded"] = new_val
            db.update_instance(inst["id"], updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"All bills marked {'unfunded' if all_funded else 'funded'}.")

    def _mark_all_paid_unpaid(self):
        bills = self._visible_bills()
        if not bills:
            self._app.flash("No bills to update.")
            return
        all_paid = all(b.get("status") == "Paid" for b in bills)
        if not all_paid and not all(b.get("funded") for b in bills):
            self._app.flash("All bills must be funded before marking all as paid.")
            return
        new_status = "Due" if all_paid else "Paid"
        new_date   = date.today().strftime("%m/%d/%Y") if new_status == "Paid" else ""
        for inst in bills:
            updated = dict(inst)
            updated["status"]    = new_status
            updated["date_paid"] = new_date
            db.update_instance(inst["id"], updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"All bills marked {'unpaid' if all_paid else 'paid'}.")


# ── Definitions Tab ───────────────────────────────────────────────────────────

class DefinitionsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._app = app
        self._selected_id = None
        self._build()

    def _build(self):
        sub = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        sub.pack(fill="x")
        sub.pack_propagate(False)
        for label, cmd in [
            ("+ Add",           self._add),
            ("✎ Edit",          self._edit),
            ("⏸ Toggle Active", self._toggle),
            ("🗑 Delete",        self._delete),
        ]:
            ctk.CTkButton(sub, text=label, width=130, height=30,
                          command=cmd).pack(side="right", padx=6, pady=7)

        container = tk.Frame(self, bg="#1a1a2e")
        container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Def.Treeview",
                        background="#2b2b3b", foreground="#e0e0e0",
                        fieldbackground="#2b2b3b", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Def.Treeview.Heading",
                        background="#1f1f2e", foreground="#8ab4f8",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Def.Treeview",
                  background=[("selected", "#3a5a8a")],
                  foreground=[("selected", "#ffffff")])

        col_ids = [c[0] for c in DEF_COLUMNS]
        vsb = ttk.Scrollbar(container, orient="vertical")
        hsb = ttk.Scrollbar(container, orient="horizontal")
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree = ttk.Treeview(container, columns=col_ids, show="headings",
                                   style="Def.Treeview",
                                   yscrollcommand=vsb.set,
                                   xscrollcommand=hsb.set,
                                   selectmode="browse")
        vsb.config(command=self._tree.yview)
        hsb.config(command=self._tree.xview)
        self._tree.pack(fill="both", expand=True)

        for col, width in DEF_COLUMNS:
            anchor = "w" if col in DEF_LEFT_ALIGN else "e"
            self._tree.heading(col, text=col)
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=False)

        self._tree.tag_configure("active",   foreground="#e0e0f0")
        self._tree.tag_configure("inactive", foreground="#555566")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit())

    def refresh(self, definitions):
        self._tree.delete(*self._tree.get_children())
        self._selected_id = None
        for defn in definitions:
            tag = "active" if defn.get("active") else "inactive"
            self._tree.insert("", "end", iid=str(defn["id"]),
                              values=_merge_defn_row(defn), tags=(tag,))

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _add(self):
        DefnDialog(self, self._app, mode="add")

    def _edit(self):
        if not self._selected_id:
            self._app.flash("Select a definition to edit.")
            return
        defs = db.load_definitions(DB_PATH)
        defn = next((d for d in defs if d["id"] == self._selected_id), None)
        if defn:
            DefnDialog(self, self._app, mode="edit", defn=defn)

    def _toggle(self):
        if not self._selected_id:
            self._app.flash("Select a definition to toggle.")
            return
        defs = db.load_definitions(DB_PATH)
        defn = next((d for d in defs if d["id"] == self._selected_id), None)
        if defn:
            updated = dict(defn)
            updated["active"] = 0 if defn["active"] else 1
            db.update_definition(self._selected_id, updated, DB_PATH)
            state = "active" if updated["active"] else "inactive"
            self._app.refresh()
            self._app.flash(f"Definition marked {state}.")

    def _delete(self):
        if not self._selected_id:
            self._app.flash("Select a definition to delete.")
            return
        ConfirmDialog(self, self._app,
                      "Delete this definition?\nExisting instances are kept.\nFuture months will no longer include this bill.",
                      lambda: (db.delete_definition(self._selected_id, DB_PATH),
                               self._app.refresh()))


# ── Debt Tracker Tab ──────────────────────────────────────────────────────────

class DebtTrackerTab(ctk.CTkFrame):
    _CHART_COLORS = ["#f87171", "#60a5fa", "#4ade80", "#fbbf24", "#c084fc", "#fb923c", "#2dd4bf"]

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._app = app
        self._selected_id = None
        self._sort_col = None
        self._sort_asc = True
        self._chart_mode = "total"
        self._debts = []
        self._balances = []
        self._latest_balance = {}
        self._chart_btns = {}
        self._build()

    def _build(self):
        # ── Summary card ──────────────────────────────────────────────
        summary = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10,
                               border_width=1, border_color=C["border"])
        summary.pack(fill="x", padx=18, pady=(12, 6))
        summary.grid_columnconfigure(0, weight=1)
        summary.grid_columnconfigure(1, weight=0)
        summary.grid_columnconfigure(2, weight=1)
        summary.grid_columnconfigure(3, weight=0)
        summary.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(summary, text="Total Debt",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(18, 8), pady=(10, 0))
        self._lbl_total_debt = ctk.CTkLabel(summary, text="—",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=C["red"], anchor="w")
        self._lbl_total_debt.grid(row=1, column=0, sticky="w", padx=(18, 8), pady=(0, 10))

        tk.Frame(summary, width=1, bg=C["border"]).grid(
            row=0, column=1, rowspan=2, sticky="ns", pady=10)

        ctk.CTkLabel(summary, text="Total Monthly Payments",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=2, sticky="w", padx=(18, 8), pady=(10, 0))
        self._lbl_total_pmt = ctk.CTkLabel(summary, text="—",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=C["yellow"], anchor="w")
        self._lbl_total_pmt.grid(row=1, column=2, sticky="w", padx=(18, 8), pady=(0, 10))

        tk.Frame(summary, width=1, bg=C["border"]).grid(
            row=0, column=3, rowspan=2, sticky="ns", pady=10)

        ctk.CTkLabel(summary, text="Years Until Debt Free",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=4, sticky="w", padx=(18, 8), pady=(10, 0))
        self._lbl_total_years = ctk.CTkLabel(summary, text="—",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=C["teal"], anchor="w")
        self._lbl_total_years.grid(row=1, column=4, sticky="w", padx=(18, 8), pady=(0, 10))

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        for label, cmd, width in [
            ("+ Add Debt", self._add,   110),
            ("✎ Edit",     self._edit,   80),
            ("🗑 Delete",   self._delete, 90),
        ]:
            ctk.CTkButton(toolbar, text=label, width=width, height=30,
                          command=cmd).pack(side="left", padx=6, pady=7)

        # ── Chart (packed bottom so table gets remaining space) ────────
        chart_outer = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10,
                                    border_width=1, border_color=C["border"])
        chart_outer.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        chart_hdr = ctk.CTkFrame(chart_outer, fg_color="transparent")
        chart_hdr.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(chart_hdr, text="Debt Balance Trend",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C["heading"]).pack(side="left")
        for val, label in [("per_debt", "Per Debt"), ("total", "Total")]:
            btn = ctk.CTkButton(
                chart_hdr, text=label, width=76, height=24,
                fg_color=C["blue"] if val == "total" else C["border"],
                hover_color=C["card2"],
                command=lambda v=val: self._set_chart_mode(v))
            btn.pack(side="right", padx=3)
            self._chart_btns[val] = btn

        self._canvas = tk.Canvas(chart_outer, bg=C["card"], highlightthickness=0, height=185)
        self._canvas.pack(fill="x", padx=8, pady=(4, 8))
        self._canvas.bind("<Configure>", self._repaint_chart)

        # ── Table ─────────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg="#1a1a2e")
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Debt.Treeview",
                        background="#2b2b3b", foreground="#e0e0e0",
                        fieldbackground="#2b2b3b", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Debt.Treeview.Heading",
                        background="#1f1f2e", foreground="#8ab4f8",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Debt.Treeview",
                  background=[("selected", "#3a5a8a")],
                  foreground=[("selected", "#ffffff")])

        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._tree = ttk.Treeview(table_frame,
                                   columns=[c[0] for c in DEBT_COLUMNS],
                                   show="headings", style="Debt.Treeview",
                                   yscrollcommand=vsb.set, selectmode="browse")
        vsb.config(command=self._tree.yview)
        self._tree.pack(fill="both", expand=True)

        for col, width in DEBT_COLUMNS:
            anchor = "w" if col in DEBT_LEFT_ALIGN else "e"
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=False)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Button-1>", self._on_click)

    def refresh(self, debts, balances):
        self._debts = debts
        self._balances = balances
        latest = {}
        for b in sorted(balances, key=lambda x: x["month_key"]):
            latest[b["debt_id"]] = b["balance"]
        self._latest_balance = latest

        total_debt = sum(latest.get(d["id"], 0) for d in debts)
        total_pmt  = sum(d.get("monthly_payment", 0) for d in debts)
        self._lbl_total_debt.configure(
            text=_fmt(total_debt),
            text_color=C["green"] if total_debt == 0 else C["red"])
        self._lbl_total_pmt.configure(text=_fmt(total_pmt))

        years_str = "—"
        if debts:
            max_payoff = None
            valid = True
            for d in debts:
                pd = d.get("payoff_date", "")
                if not pd:
                    valid = False
                    break
                try:
                    m, day, y = pd.split("/")
                    max_payoff = max(max_payoff, date(int(y), int(m), int(day))) \
                                 if max_payoff else date(int(y), int(m), int(day))
                except Exception:
                    valid = False
                    break
            if valid and max_payoff:
                delta_days = (max_payoff - date.today()).days
                years_str = f"{max(delta_days, 0) / 365.25:.1f}"
            else:
                years_str = "N/A"
        self._lbl_total_years.configure(text=years_str)

        self._tree.delete(*self._tree.get_children())
        self._selected_id = None
        for debt in debts:
            self._tree.insert("", "end", iid=str(debt["id"]),
                              values=_merge_debt_row(debt, latest.get(debt["id"])))
        if self._sort_col:
            self._apply_sort()
        self._repaint_chart()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._apply_sort()

    def _apply_sort(self):
        for col, _ in DEBT_COLUMNS:
            self._tree.heading(col, text=col)
        arrow = " ▲" if self._sort_asc else " ▼"
        self._tree.heading(self._sort_col, text=self._sort_col + arrow)
        items = [(self._tree.set(k, self._sort_col), k)
                 for k in self._tree.get_children("")]
        items.sort(key=lambda x: self._sort_key(self._sort_col, x[0]),
                   reverse=not self._sort_asc)
        for idx, (_, k) in enumerate(items):
            self._tree.move(k, "", idx)

    def _sort_key(self, col, val):
        if col == "Days Left":
            if val in ("—", "N/A", ""):
                return 999999
            if val == "Today":
                return 0
            if val == "Paid":
                return -1
            try:
                return int(val.replace(",", ""))
            except ValueError:
                return 999999
        if col in ("Balance", "Monthly Pmt"):
            if val == "—":
                return -1.0
            try:
                return float(val.replace("$", "").replace(",", ""))
            except ValueError:
                return -1.0
        if col == "Rate":
            try:
                return float(val.replace("%", ""))
            except ValueError:
                return -1.0
        if col == "Payoff Date":
            if val in ("N/A", "—", ""):
                return (9999, 99, 99)
            try:
                m, d, y = val.split("/")
                return (int(y), int(m), int(d))
            except Exception:
                return (9999, 99, 99)
        return val.lower()

    def _repaint_chart(self, _=None):
        self._canvas.delete("all")
        w, h = self._canvas.winfo_width(), self._canvas.winfo_height()
        if w < 20 or h < 20:
            return
        if not self._balances:
            self._canvas.create_text(w // 2, h // 2,
                text="Click a debt row to log your first balance entry",
                fill=C["muted"], font=("Helvetica", 11))
            return

        pad_l, pad_r, pad_t, pad_b = 76, 16, 12, 28
        cw = w - pad_l - pad_r
        ch = h - pad_t - pad_b

        months = sorted({b["month_key"] for b in self._balances})
        nm = len(months)

        def xp(i):
            return pad_l + (i / max(nm - 1, 1)) * cw

        def yp(v, lo, hi):
            return pad_t + (1.0 - (v - lo) / (hi - lo or 1)) * ch

        # Axes
        self._canvas.create_line(pad_l, pad_t, pad_l, h - pad_b,
                                  fill=C["border"], width=1)
        self._canvas.create_line(pad_l, h - pad_b, w - pad_r, h - pad_b,
                                  fill=C["border"], width=1)

        # X labels
        for i, m in enumerate(months):
            if nm <= 8 or i % max(1, nm // 8) == 0 or i == nm - 1:
                yr, mo = m.split("-")
                self._canvas.create_text(
                    xp(i), h - pad_b + 4,
                    text=f"{MONTH_NAMES[int(mo)-1]} '{yr[2:]}",
                    anchor="n", fill=C["muted"], font=("Helvetica", 8))

        if self._chart_mode == "total":
            totals = {}
            for b in self._balances:
                totals[b["month_key"]] = totals.get(b["month_key"], 0) + b["balance"]
            vals = [totals.get(m, 0) for m in months]
            lo, hi = min(vals), max(vals)
            self._canvas.create_text(pad_l - 4, pad_t, text=_fmt(hi),
                anchor="e", fill=C["muted"], font=("Helvetica", 9))
            self._canvas.create_text(pad_l - 4, h - pad_b, text=_fmt(lo),
                anchor="e", fill=C["muted"], font=("Helvetica", 9))
            pts = [(xp(i), yp(v, lo, hi)) for i, v in enumerate(vals)]
            for i in range(len(pts) - 1):
                x0, y0 = pts[i]; x1, y1 = pts[i + 1]
                self._canvas.create_line(x0, y0, x1, y1, fill=C["red"], width=2)
            for x, y in pts:
                self._canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                          fill=C["red"], outline="")
        else:
            by_debt = {}
            for b in self._balances:
                by_debt.setdefault(b["debt_id"], {})[b["month_key"]] = b["balance"]
            all_v = [b["balance"] for b in self._balances]
            lo, hi = min(all_v), max(all_v)
            self._canvas.create_text(pad_l - 4, pad_t, text=_fmt(hi),
                anchor="e", fill=C["muted"], font=("Helvetica", 9))
            self._canvas.create_text(pad_l - 4, h - pad_b, text=_fmt(lo),
                anchor="e", fill=C["muted"], font=("Helvetica", 9))
            for ci, (debt_id, mdata) in enumerate(by_debt.items()):
                color = self._CHART_COLORS[ci % len(self._CHART_COLORS)]
                debt_months = [m for m in months if m in mdata]
                if not debt_months:
                    continue
                pts = [(xp(months.index(m)), yp(mdata[m], lo, hi)) for m in debt_months]
                for i in range(len(pts) - 1):
                    x0, y0 = pts[i]; x1, y1 = pts[i + 1]
                    self._canvas.create_line(x0, y0, x1, y1, fill=color, width=2)
                for x, y in pts:
                    self._canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                              fill=color, outline="")
                name = next((d["name"] for d in self._debts if d["id"] == debt_id), "")
                if name and pts:
                    lx, ly = pts[-1]
                    self._canvas.create_text(lx + 6, ly, text=name[:15],
                        anchor="w", fill=color, font=("Helvetica", 8))

    def _set_chart_mode(self, mode):
        self._chart_mode = mode
        for val, btn in self._chart_btns.items():
            btn.configure(fg_color=C["blue"] if val == mode else C["border"])
        self._repaint_chart()

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _on_click(self, event):
        item = self._tree.identify_row(event.y)
        if not item:
            return
        debt_id = int(item)
        self._selected_id = debt_id
        debt = next((d for d in self._debts if d["id"] == debt_id), None)
        if debt:
            bal = self._latest_balance.get(debt_id)
            BalanceDialog(self, self._app, debt, bal)

    def _add(self):
        DebtDialog(self, self._app, mode="add")

    def _edit(self):
        if not self._selected_id:
            self._app.flash("Select a debt to edit.")
            return
        debt = next((d for d in self._debts if d["id"] == self._selected_id), None)
        if debt:
            DebtDialog(self, self._app, mode="edit", debt=debt)

    def _delete(self):
        if not self._selected_id:
            self._app.flash("Select a debt to delete.")
            return
        ConfirmDialog(self, self._app,
                      "Delete this debt and all balance history?\nThis cannot be undone.",
                      lambda: (db.delete_debt(self._selected_id, DB_PATH),
                               self._app.refresh()))


# ── Balance Update Dialog ─────────────────────────────────────────────────────

class BalanceDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, debt, current_balance=None):
        super().__init__(parent)
        self._app = app
        self._debt = debt
        today = date.today()
        self._month_key = f"{today.year:04d}-{today.month:02d}"

        self.title("Update Balance")
        self.geometry("370x205")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=debt["name"],
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            padx=16, pady=(14, 2), anchor="w")
        ctk.CTkLabel(self, text=f"Balance for {_month_label(self._month_key)}",
                     font=ctk.CTkFont(size=11), text_color=C["muted"]).pack(
            padx=16, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(row, text="Current Balance:", width=140, anchor="w").pack(side="left")
        default_val = f"{current_balance:.2f}" if current_balance is not None else ""
        self._bal_var = tk.StringVar(value=default_val)
        entry = ctk.CTkEntry(row, textvariable=self._bal_var, width=160)
        entry.pack(side="left")
        entry.select_range(0, "end")
        entry.focus_set()

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=10, side="bottom")
        ctk.CTkButton(btn_row, text="Save", width=100,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=90,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda _: self._save())

    def _save(self):
        try:
            balance = float(self._bal_var.get().replace("$", "").replace(",", ""))
        except ValueError:
            self._err.configure(text="Balance must be a number.")
            return
        db.set_debt_balance(self._debt["id"], self._month_key, balance, DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Debt Add/Edit Dialog ──────────────────────────────────────────────────────

class DebtDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, mode, debt=None):
        super().__init__(parent)
        self._app = app
        self._mode = mode
        self._debt = debt

        title = "Add Debt" if mode == "add" else "Edit Debt"
        self.title(title)
        self.geometry("420x410")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}
        fields = [
            ("Name",            debt["name"]                     if debt else "",  ""),
            ("Interest Rate %", str(debt["interest_rate"])       if debt else "",  "e.g. 14.99"),
            ("Monthly Pmt",     str(debt["monthly_payment"])     if debt else "",  "e.g. 281.43"),
            ("Payoff Date",     debt["payoff_date"]              if debt else "",  "MM/DD/YYYY — leave blank for N/A"),
            ("Notes",           debt.get("notes", "")            if debt else "",  ""),
        ]
        for label, default, hint in fields:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(5, 0))
            ctk.CTkLabel(row, text=label, width=130, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            ctk.CTkEntry(row, textvariable=var, width=230).pack(side="left")
            self._vars[label] = var
            if hint:
                ctk.CTkLabel(self, text=hint, font=ctk.CTkFont(size=10),
                             text_color=C["muted"]).pack(padx=16, anchor="w")

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w", pady=(6, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=10, side="bottom")
        ctk.CTkButton(btn_row, text="Save", width=120,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

    def _save(self):
        name = self._vars["Name"].get().strip()
        if not name:
            self._err.configure(text="Name is required.")
            return
        try:
            rate = float(self._vars["Interest Rate %"].get().replace("%", "").strip())
        except ValueError:
            self._err.configure(text="Interest rate must be a number.")
            return
        try:
            pmt = float(self._vars["Monthly Pmt"].get().replace("$", "").replace(",", "").strip())
        except ValueError:
            self._err.configure(text="Monthly payment must be a number.")
            return
        payoff = self._vars["Payoff Date"].get().strip()
        notes  = self._vars["Notes"].get().strip()
        data = {"name": name, "interest_rate": rate,
                "monthly_payment": pmt, "payoff_date": payoff, "notes": notes}
        if self._mode == "add":
            db.insert_debt(data, DB_PATH)
        else:
            db.update_debt(self._debt["id"], data, DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Bill Instance Dialog ──────────────────────────────────────────────────────

class InstDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, mode, inst=None, month_key=""):
        super().__init__(parent)
        self._app       = app
        self._mode      = mode
        self._inst      = inst
        self._month_key = month_key or (inst.get("month_key", "") if inst else "")

        title = "Add Bill" if mode == "add" else "Edit Bill"
        self.title(title)
        self.geometry("440x660")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}
        _pm_raw = inst.get("payment_mode", "") if inst else ""
        _pm_default = _PM_LEGACY.get(_pm_raw, _pm_raw) if _pm_raw else "—"
        if _pm_default not in ("🤖", "🔔"):
            _pm_default = "—"
        _vibe_raw = inst.get("vibe", "") if inst else ""
        _vibe_default = _VIBE_LEGACY.get(_vibe_raw, _vibe_raw) if _vibe_raw else "—"
        if _vibe_default not in ("🌟", "🤷", "💔"):
            _vibe_default = "—"
        fields = [
            ("Expense",        "entry", inst["description"] if inst else ""),
            ("Status",         "combo", inst["status"]      if inst else STATUSES[0]),
            ("Payment Mode",   "combo", _pm_default),
            ("Vibe",           "combo", _vibe_default),
            ("Due Date",       "entry", inst["due_date"]    if inst else ""),
            ("Amount",         "entry", str(inst["amount"]) if inst else ""),
            ("Frequency",      "combo", inst["frequency"]   if inst else FREQUENCIES[0]),
            ("Date Paid",      "entry", inst["date_paid"]   if inst else ""),
            ("Notes",          "entry", inst["notes"]       if inst else ""),
        ]
        for label, kind, default in fields:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=110, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            if kind == "entry":
                ctk.CTkEntry(row, textvariable=var, width=260).pack(side="left")
            else:
                if label == "Status":
                    choices = STATUSES
                elif label == "Payment Mode":
                    choices = PAYMENT_MODES
                elif label == "Vibe":
                    choices = VIBES
                else:
                    choices = FREQUENCIES
                ctk.CTkOptionMenu(row, values=choices, variable=var,
                                  width=260).pack(side="left")
            self._vars[label] = var

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12, side="bottom")
        ctk.CTkButton(btn_row, text="Save", width=120,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

    def _save(self):
        desc = self._vars["Expense"].get().strip()
        if not desc:
            self._err.configure(text="Expense description is required.")
            return
        due_date = self._vars["Due Date"].get().strip()
        if not due_date:
            self._err.configure(text="Due Date is required.")
            return
        try:
            amount = float(self._vars["Amount"].get().replace("$", "").replace(",", ""))
        except ValueError:
            self._err.configure(text="Amount must be a number.")
            return

        _pm   = self._vars["Payment Mode"].get()
        _vibe = self._vars["Vibe"].get()
        try:
            _m, _d, _y = due_date.split("/")
            _month_key = f"{_y}-{_m.zfill(2)}"
        except Exception:
            _month_key = self._month_key
        data = {
            "month_key":    _month_key,
            "description":  desc,
            "status":       self._vars["Status"].get(),
            "payment_mode": "" if _pm   == "—" else _pm,
            "vibe":         "" if _vibe == "—" else _vibe,
            "due_date":     due_date,
            "amount":       amount,
            "frequency":    self._vars["Frequency"].get(),
            "date_paid":    self._vars["Date Paid"].get().strip(),
            "notes":        self._vars["Notes"].get().strip(),
        }
        if self._mode == "add":
            db.insert_instance(data, DB_PATH)
        else:
            db.update_instance(self._inst["id"], data, DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Definition Dialog ─────────────────────────────────────────────────────────

class DefnDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, mode, defn=None):
        super().__init__(parent)
        self._app  = app
        self._mode = mode
        self._defn = defn

        title = "Add Definition" if mode == "add" else "Edit Definition"
        self.title(title)
        self.geometry("480x700")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}

        # Static fields
        for label, default in [
            ("Description", defn["description"]          if defn else ""),
            ("Typical $",   str(defn["typical_amount"])  if defn else ""),
            ("Due Day",     str(defn["due_day"])         if defn else "1"),
        ]:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=110, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            ctk.CTkEntry(row, textvariable=var, width=270).pack(side="left")
            self._vars[label] = var

        # Frequency (triggers Due In update)
        freq_row = ctk.CTkFrame(self, fg_color="transparent")
        freq_row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(freq_row, text="Frequency", width=110, anchor="w").pack(side="left")
        freq_default = defn["frequency"] if defn else "Monthly"
        self._freq_var = tk.StringVar(value=freq_default)
        ctk.CTkOptionMenu(freq_row, values=FREQUENCIES, variable=self._freq_var,
                          width=270, command=self._on_freq_change).pack(side="left")
        self._vars["Frequency"] = self._freq_var

        # Due In (dynamic label + hint based on frequency)
        self._due_in_row = ctk.CTkFrame(self, fg_color="transparent")
        self._due_in_row.pack(fill="x", padx=16, pady=5)
        self._due_in_label = ctk.CTkLabel(self._due_in_row, text="Due In",
                                           width=110, anchor="w")
        self._due_in_label.pack(side="left")
        self._due_in_var = tk.StringVar(value=self._default_due_in(defn))
        self._due_in_entry = ctk.CTkEntry(self._due_in_row, textvariable=self._due_in_var,
                                           width=270)
        self._due_in_entry.pack(side="left")
        self._vars["Due In"] = self._due_in_var

        self._due_in_hint = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=10),
                                          text_color=C["muted"])
        self._due_in_hint.pack(padx=16, anchor="w")

        # Payment Mode
        pm_row = ctk.CTkFrame(self, fg_color="transparent")
        pm_row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(pm_row, text="Payment Mode", width=110, anchor="w").pack(side="left")
        _pm_raw = defn.get("payment_mode", "") if defn else ""
        _pm_default = _PM_LEGACY.get(_pm_raw, _pm_raw) if _pm_raw else "—"
        if _pm_default not in ("🤖", "🔔"):
            _pm_default = "—"
        self._pm_var = tk.StringVar(value=_pm_default)
        ctk.CTkOptionMenu(pm_row, values=PAYMENT_MODES, variable=self._pm_var,
                          width=270).pack(side="left")
        self._vars["Payment Mode"] = self._pm_var

        # Vibe
        vibe_row = ctk.CTkFrame(self, fg_color="transparent")
        vibe_row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(vibe_row, text="Vibe", width=110, anchor="w").pack(side="left")
        _vibe_raw = defn.get("vibe", "") if defn else ""
        _vibe_default = _VIBE_LEGACY.get(_vibe_raw, _vibe_raw) if _vibe_raw else "—"
        if _vibe_default not in ("🌟", "🤷", "💔"):
            _vibe_default = "—"
        self._vibe_var = tk.StringVar(value=_vibe_default)
        ctk.CTkOptionMenu(vibe_row, values=VIBES, variable=self._vibe_var,
                          width=270).pack(side="left")
        self._vars["Vibe"] = self._vibe_var

        # Notes
        notes_row = ctk.CTkFrame(self, fg_color="transparent")
        notes_row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(notes_row, text="Notes", width=110, anchor="w").pack(side="left")
        notes_var = tk.StringVar(value=defn["notes"] if defn else "")
        ctk.CTkEntry(notes_row, textvariable=notes_var, width=270).pack(side="left")
        self._vars["Notes"] = notes_var

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12, side="bottom")
        ctk.CTkButton(btn_row, text="Save", width=120,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

        self._on_freq_change(freq_default)

    def _default_due_in(self, defn):
        if not defn:
            return ""
        freq = defn.get("frequency", "Monthly")
        if freq == "AdHoc":
            return defn.get("adhoc_month", "")
        return defn.get("months_active", "")

    def _on_freq_change(self, freq):
        cfg = {
            "Monthly":    ("",          True,  ""),
            "AdHoc":      ("Target Month", False, "Format: YYYY-MM  (e.g. 2026-09)"),
            "Annual":     ("Month #",   False, "Month number 1–12  (e.g. 6 for June)"),
            "Semi-Annual":("Months #",  False, "Two months  (e.g. 3,9)"),
            "Quarterly":  ("Months #",  False, "Four months  (e.g. 1,4,7,10)"),
            "Bi-Weekly":  ("",          True,  ""),
            "Weekly":     ("",          True,  ""),
        }
        label, disabled, hint = cfg.get(freq, ("Due In", False, ""))
        if disabled:
            self._due_in_var.set("")
            self._due_in_row.pack_forget()
            self._due_in_hint.pack_forget()
        else:
            self._due_in_row.pack(fill="x", padx=16, pady=5, before=self._due_in_hint)
            self._due_in_hint.pack(padx=16, anchor="w", before=self._err)
            self._due_in_label.configure(text=label or "Due In")
            self._due_in_entry.configure(state="normal")
            self._due_in_hint.configure(text=hint)

    def _save(self):
        desc = self._vars["Description"].get().strip()
        if not desc:
            self._err.configure(text="Description is required.")
            return
        try:
            amount = float(self._vars["Typical $"].get().replace("$", "").replace(",", ""))
        except ValueError:
            self._err.configure(text="Typical $ must be a number.")
            return
        try:
            due_day = int(self._vars["Due Day"].get().strip())
            if not 1 <= due_day <= 31:
                raise ValueError
        except ValueError:
            self._err.configure(text="Due Day must be 1–31.")
            return

        freq     = self._freq_var.get()
        due_in   = self._due_in_var.get().strip()
        adhoc_m  = ""
        months_a = ""

        if freq == "AdHoc":
            if not due_in:
                self._err.configure(text="Target Month is required for AdHoc (YYYY-MM).")
                return
            adhoc_m = due_in
        elif freq in ("Annual", "Semi-Annual", "Quarterly"):
            if not due_in:
                self._err.configure(text="Month number(s) required for this frequency.")
                return
            months_a = due_in

        _pm   = self._vars["Payment Mode"].get()
        _vibe = self._vars["Vibe"].get()
        data = {
            "description":    desc,
            "frequency":      freq,
            "typical_amount": amount,
            "due_day":        due_day,
            "months_active":  months_a,
            "adhoc_month":    adhoc_m,
            "active":         self._defn["active"] if self._defn else 1,
            "notes":          self._vars["Notes"].get().strip(),
            "payment_mode":   "" if _pm   == "—" else _pm,
            "vibe":           "" if _vibe == "—" else _vibe,
        }
        if self._mode == "add":
            db.insert_definition(data, DB_PATH)
        else:
            db.update_definition(self._defn["id"], data, DB_PATH)
        db.generate_month_instances(self._app.current_month(), DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Generic Confirm Dialog ────────────────────────────────────────────────────

class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, message, on_confirm):
        super().__init__(parent)
        self._app        = app
        self._on_confirm = on_confirm
        self.title("Confirm")
        self.geometry("340x170")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=message, justify="center",
                     font=ctk.CTkFont(size=13)).pack(padx=20, pady=22)
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 14))
        ctk.CTkButton(btn_row, text="Confirm", width=110,
                      fg_color="#c0392b", hover_color="#922b21",
                      command=self._confirm).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

    def _confirm(self):
        self._on_confirm()
        self.destroy()


# ── Main Application ──────────────────────────────────────────────────────────

class MoneyTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Bill Tracker")
        self.minsize(960, 620)

        db.init_db(DB_PATH)

        self._settings = self._load_settings()
        self.geometry(self._settings.get("geometry", "1300x820"))
        today = date.today()
        default_month = f"{today.year:04d}-{today.month:02d}"
        self._current_month = self._settings.get("last_month", default_month)
        db.generate_month_instances(self._current_month, DB_PATH)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        saved_widths = self._settings.get("column_widths", {})
        if saved_widths:
            self.after(0, lambda: self._dashboard.set_column_widths(saved_widths))
        self.refresh()

    def current_month(self):
        return self._current_month

    def can_navigate_left(self):
        months = db.get_months_with_instances(DB_PATH)
        if not months or self._current_month not in months:
            return False
        return months.index(self._current_month) > 0

    def can_navigate_right(self):
        return self._current_month < _max_future_month()

    def navigate_left(self):
        if not self.can_navigate_left():
            return
        months = db.get_months_with_instances(DB_PATH)
        idx = months.index(self._current_month)
        self._current_month = months[idx - 1]
        db.generate_month_instances(self._current_month, DB_PATH)
        self.refresh()

    def navigate_right(self):
        if not self.can_navigate_right():
            return
        self._current_month = _add_months(self._current_month, 1)
        db.generate_month_instances(self._current_month, DB_PATH)
        self.refresh()

    def navigate_to_today(self):
        today = date.today()
        self._current_month = f"{today.year:04d}-{today.month:02d}"
        db.generate_month_instances(self._current_month, DB_PATH)
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#1a1a2e")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        header.columnconfigure(2, weight=1)

        ctk.CTkLabel(header, text="💰",
                     font=ctk.CTkFont(size=36)).grid(row=0, column=0, sticky="w", padx=18, pady=8)

        self._tab_btns = {}
        tab_group = ctk.CTkFrame(header, fg_color="transparent")
        tab_group.grid(row=0, column=1, pady=10)
        ctk.CTkLabel(header, text="💰",
                     font=ctk.CTkFont(size=36)).grid(row=0, column=2, sticky="e", padx=18, pady=8)
        for name in ("Dashboard", "Definitions", "Debt"):
            btn = ctk.CTkButton(
                tab_group, text=name, width=130, height=30,
                corner_radius=6,
                fg_color="#3a5a8a", hover_color="#4a6a9a",
                text_color=C["heading"],
                font=ctk.CTkFont(size=13),
                command=lambda n=name: self._switch_tab(n),
            )
            btn.pack(side="left", padx=4)
            self._tab_btns[name] = btn

        self._status_var = tk.StringVar(value="Loading…")
        status_bar = ctk.CTkFrame(self, height=26, corner_radius=0,
                                  fg_color=("gray85", "gray20"))
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        ctk.CTkLabel(status_bar, textvariable=self._status_var,
                     font=ctk.CTkFont(size=11), anchor="w",
                     text_color=C["muted"]).pack(side="left", padx=12)

        content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        content.pack(fill="both", expand=True)

        self._dashboard = CombinedDashboard(content, self)
        self._dashboard.pack(fill="both", expand=True)

        self._defs = DefinitionsTab(content, self)
        self._debt_tab = DebtTrackerTab(content, self)

        self._active_tab = "Dashboard"
        self._update_tab_btn_styles()

    def _switch_tab(self, name):
        if name == self._active_tab:
            return
        self._active_tab = name
        self._dashboard.pack_forget()
        self._defs.pack_forget()
        self._debt_tab.pack_forget()
        if name == "Dashboard":
            self._dashboard.pack(fill="both", expand=True)
        elif name == "Definitions":
            self._defs.pack(fill="both", expand=True)
        else:
            self._debt_tab.pack(fill="both", expand=True)
        self._update_tab_btn_styles()

    def _update_tab_btn_styles(self):
        for name, btn in self._tab_btns.items():
            if name == self._active_tab:
                btn.configure(fg_color="#3a5a8a", text_color=C["heading"])
            else:
                btn.configure(fg_color=C["card2"], text_color=C["muted"])

    def refresh(self):
        annotated, summary = _load_and_annotate(self._current_month)
        definitions        = db.load_definitions(DB_PATH)
        debts              = db.load_debts(DB_PATH)
        balances           = db.get_all_debt_balances(DB_PATH)
        self._dashboard.refresh(annotated, summary, self._current_month)
        self._defs.refresh(definitions)
        self._debt_tab.refresh(debts, balances)
        self._update_status(annotated, summary)

    def _update_status(self, annotated, summary):
        if not annotated:
            self._status_var.set(f"{_month_label(self._current_month)} — No bills")
            return
        self._status_var.set(
            f"{_month_label(self._current_month)}  |  "
            f"{summary['bill_count']} bills  |  "
            f"Due: {_fmt(summary['total_due'])}  |  "
            f"Paid: {_fmt(summary['total_paid'])}"
        )

    def _load_settings(self):
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump({
                    "last_month":    self._current_month,
                    "column_widths": self._dashboard.get_column_widths(),
                    "geometry":      self.geometry(),
                }, f, indent=2)
        except Exception:
            pass

    def _on_close(self):
        self._save_settings()
        self.destroy()

    def flash(self, msg, duration_ms=3000):
        old = self._status_var.get()
        self._status_var.set(msg)
        self.after(duration_ms, lambda: self._status_var.set(old))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MoneyTrackerApp()
    app.mainloop()
