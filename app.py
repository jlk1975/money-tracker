"""
app.py — Money Tracker main application.
Two tabs: Bill Dashboard (summary + nav + bill grid), Bill Definitions (master bill template list).
"""

import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
import csv
import os
import json
import re
import calendar
import random
from datetime import date

import db
import calc

ctk.set_appearance_mode("light")
ctk.set_default_color_theme(os.path.join(os.path.dirname(__file__), "warm-brown.json"))

_DATA_DIR     = os.path.join(os.path.expanduser("~"), ".local", "share", "money-tracker")
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH       = os.path.join(_DATA_DIR, "money_tracker.db")
SETTINGS_PATH = os.path.join(_DATA_DIR, "settings.json")

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#fefce8",
    "card":    "#ffffff",
    "card2":   "#fef9c3",
    "border":  "#e5d58a",
    "text":    "#1c1917",
    "muted":   "#78716c",
    "green":   "#15803d",
    "red":     "#b91c1c",
    "blue":    "#854d0e",
    "yellow":  "#ca8a04",
    "purple":  "#78716c",
    "teal":    "#0e7490",
    "orange":  "#c2410c",
    "heading": "#713f12",
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
    ("Funded",     70),
    ("Soft",       50),
    ("Vibe",       50),
    ("✓",          40),
    ("Status",     70),
    ("Pay Mode",   65),
    ("Expense",   240),
    ("Due Date",   90),
    ("Amount",     90),
    ("Frequency",  90),
    ("Date Paid",  90),
    ("Notes",     150),
]
LEFT_ALIGN = {"Status", "Expense", "Due Date", "Frequency", "Date Paid", "Notes"}

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
# ── Register tab grid ─────────────────────────────────────────────────────────
REG_COLUMNS = [
    ("Rev",         36),
    ("Txn #",       80),
    ("Date",        90),
    ("Description",190),
    ("Memo",       175),
    ("Debit",       95),
    ("Credit",      95),
    ("Balance",    110),
    ("Check #",     72),
    ("Bill",       160),
]
REG_LEFT_ALIGN = {"Date", "Description", "Memo", "Bill"}


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
        "✓" if inst.get("funded") else "",
        "💸" if inst.get("soft_pay") else "",
        _vibe_emoji(inst.get("vibe", "")),
        "✓" if inst.get("status") == "Paid" else "",
        inst.get("status", ""),
        _payment_emoji(inst.get("payment_mode", "")),
        inst.get("description", ""),
        inst.get("due_date", ""),
        _fmt(inst.get("amount")),
        inst.get("frequency", ""),
        inst.get("date_paid", ""),
        inst.get("notes", ""),
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


# ── Tooltip ──────────────────────────────────────────────────────────────────

class _Tooltip:
    def __init__(self, widget, text):
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)
        self._text = text

    def _show(self, event):
        if self._tip:
            return
        x = event.widget.winfo_rootx() + 10
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(event.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, background="#1c1917", foreground="#fef9c3",
                 font=("Helvetica", 11), padx=6, pady=3, relief="flat").pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


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
    _COLORS = {"🌟": "#2a7a3b", "🤷": "#888888", "💔": "#b91c1c", "": "#888888"}

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
        self.create_rectangle(bar_x, y, bar_x + bw, y + bar_h, fill=C["border"], outline="")
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
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color=C["heading"], width=130)
        self._month_lbl.pack(side="left", padx=6)

        self._right_btn = ctk.CTkButton(self._nav_bar, text="▶", width=36, height=28,
                                         command=self._app.navigate_right)
        self._right_btn.pack(side="left", padx=(0, 4), pady=7)

        ctk.CTkButton(self._nav_bar, text="This Month", width=90, height=28,
                      command=self._app.navigate_to_today).pack(
            side="left", padx=(10, 0), pady=7)

        for _emoji, _label, _color in [("🌟", "Good", C["green"]), ("🤷", "Meh", C["blue"]), ("💔", "Regret", C["red"])]:
            _btn = ctk.CTkButton(
                self._nav_bar, text=_emoji, width=36, height=28,
                fg_color=C["border"], hover_color=C["card2"],
                font=ctk.CTkFont(size=12),
                command=lambda e=_emoji: self._toggle_vibe_filter(e),
            )
            _btn.pack(side="left", padx=(6, 0), pady=7)
            self._vibe_btns[_emoji] = (_btn, _color)

        # Hide button packed right first so the middle frame fills remaining space
        self._toggle_btn = ctk.CTkButton(self._nav_bar, text="▲ Hide",
                                          width=80, height=28,
                                          command=self._toggle_metrics)
        self._toggle_btn.pack(side="right", padx=(0, 10), pady=7)

        # Middle expanding frame — 4 equal columns, evenly spaced between nav and Hide
        _mid = ctk.CTkFrame(self._nav_bar, fg_color="transparent")
        _mid.pack(side="left", fill="x", expand=True)
        for _c in range(4):
            _mid.columnconfigure(_c, weight=1)

        self._funded_through_lbl = ctk.CTkLabel(
            _mid, text="",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C["heading"])
        self._funded_through_lbl.grid(row=0, column=0, pady=7)

        ctk.CTkLabel(_mid, text=self._app._animal, font=ctk.CTkFont(size=15)).grid(
            row=0, column=1, pady=7)

        self._month_total_lbl = ctk.CTkLabel(
            _mid, text="",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C["heading"])
        self._month_total_lbl.grid(row=0, column=2, pady=7)

        # Progress bar + pct label as a unit in column 3
        _prog_frame = ctk.CTkFrame(_mid, fg_color="transparent")
        _prog_frame.grid(row=0, column=3, pady=7)
        self._nav_progress_bar = ctk.CTkProgressBar(
            _prog_frame, width=120, height=10,
            progress_color=C["green"], fg_color=C["border"])
        self._nav_progress_bar.set(0)
        self._nav_progress_bar.pack(side="left", padx=(0, 4))
        self._nav_pct_label = ctk.CTkLabel(
            _prog_frame, text="Paid 0%",
            font=ctk.CTkFont(size=12), text_color=C["muted"], width=52)
        self._nav_pct_label.pack(side="left")

        self._metrics_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._metrics_panel.pack(fill="x")

        self._toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        self._toolbar.pack(fill="x")
        self._toolbar.pack_propagate(False)
        for label, cmd, width in [
            ("All Funded",   self._mark_all_funded,   100),
            ("All Unfunded", self._mark_all_unfunded, 108),
            ("Funded/Unfunded",     self._toggle_funded,            120),
            ("💸 Soft Pay",          self._toggle_soft_pay,          100),
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

        self._bottom = tk.Frame(self, bg="#fefce8")
        self._bottom.pack(fill="both", expand=True)

        self._sidebar = ctk.CTkFrame(self._bottom, width=210, fg_color=C["card"],
                                      corner_radius=0, border_width=1,
                                      border_color=C["border"])
        self._sidebar.pack(side="right", fill="y")
        self._sidebar.pack_propagate(False)

        self._tree_container = tk.Frame(self._bottom, bg="#fefce8")
        self._tree_container.pack(side="left", fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Money.Treeview",
                        background="#fefce8", foreground="#1c1917",
                        fieldbackground="#fefce8", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Money.Treeview.Heading",
                        background="#fef08a", foreground="#713f12",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Money.Treeview",
                  background=[("selected", "#854d0e")],
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

        self._tree.tag_configure("due",    background="#fecaca", foreground="#7f1d1d")
        self._tree.tag_configure("paid",   background="#bbf7d0", foreground="#14532d")
        self._tree.tag_configure("funded", background="#fde68a", foreground="#78350f")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit())

    def _toggle_metrics(self):
        if self._metrics_visible:
            self._metrics_panel.pack_forget()
            self._toggle_btn.configure(text="▼ Show")
        else:
            self._metrics_panel.pack(fill="x", before=self._toolbar)
            self._toggle_btn.configure(text="▲ Hide")
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

        s2s = db.get_safe2spend(DB_PATH)
        s2s_color = C["green"] if s2s >= 0 else C["red"]
        s2s_str = f"${s2s:,.2f}" if s2s >= 0 else f"-${abs(s2s):,.2f}"
        self._app._header_s2s_label.configure(text=f"Safe2Spend: {s2s_str}", text_color=s2s_color)

        _paid  = summary.get("total_paid", 0)
        _total = _paid + summary.get("total_due", 0)
        _pct   = (_paid / _total) if _total else 0
        self._nav_progress_bar.set(max(0.0, min(1.0, _pct)))
        self._nav_pct_label.configure(text=f"Paid {_pct*100:.0f}%")

        days_str, caption_str = calc.funded_through_parts(annotated, month_key)
        if days_str and days_str != "0 days":
            self._funded_through_lbl.configure(text=caption_str)
        else:
            self._funded_through_lbl.configure(text="")

        if self._vibe_filter:
            display = [b for b in annotated
                       if _vibe_emoji(b.get("vibe", "")) in self._vibe_filter]
            summary = calc.calculate_summary(display)
        else:
            display = annotated

        month_total  = summary["total_due"] + summary["total_paid"]
        paid_count   = sum(1 for b in display if b.get("status") == "Paid")
        unpaid_count = sum(1 for b in display if b.get("status") != "Paid")
        self._month_total_lbl.configure(
            text=f"{summary['bill_count']} bills  ·  ${month_total:,.2f}  ·  ✓ {paid_count}  ·  ○ {unpaid_count}")

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

    def _toggle_soft_pay(self):
        if not self._selected_id:
            self._app.flash("Select a bill to toggle soft pay.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if not inst.get("soft_pay") and not inst.get("funded"):
            self._app.flash("Bill must be funded before it can be marked soft paid.")
            return
        db.toggle_soft_pay(self._selected_id, DB_PATH)
        self._app.refresh()

    def _toggle_funded(self):
        if not self._selected_id:
            self._app.flash("Select a bill to toggle funded status.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if inst.get("funded"):
            updated = dict(inst)
            updated["funded"] = 0
            db.update_instance(self._selected_id, updated, DB_PATH)
            self._app.refresh()
            self._app.flash(f"Marked not funded: {inst.get('description', '')[:40]}")
        else:
            amount = inst.get("amount", 0.0) or 0.0
            if amount > 0:
                s2s = db.get_safe2spend(DB_PATH)
                if amount > s2s:
                    self._app.flash(
                        f"Cannot fund {inst.get('description', '')[:28]} ({_fmt(amount)}) — "
                        f"Safe2Spend is only {_fmt(s2s)}."
                    )
                    return
            updated = dict(inst)
            updated["funded"] = 1
            db.update_instance(self._selected_id, updated, DB_PATH)
            self._app.refresh()
            self._app.flash(f"Marked funded: {inst.get('description', '')[:40]}")

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

    def _mark_all_funded(self):
        bills = self._visible_bills()
        candidates = [b for b in bills if not b.get("funded")]
        if not candidates:
            self._app.flash("All visible bills are already funded.")
            return
        total = sum(b.get("amount", 0) or 0 for b in candidates)
        if total > 0:
            s2s = db.get_safe2spend(DB_PATH)
            if total > s2s:
                self._app.flash(
                    f"Cannot fund {len(candidates)} bills ({_fmt(total)} total) — "
                    f"Safe2Spend is only {_fmt(s2s)}."
                )
                return
        for inst in candidates:
            updated = dict(inst)
            updated["funded"] = 1
            db.update_instance(inst["id"], updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked {len(candidates)} bills funded.")

    def _mark_all_unfunded(self):
        bills = self._visible_bills()
        candidates = [b for b in bills if b.get("funded")]
        if not candidates:
            self._app.flash("No funded bills to unmark.")
            return
        for inst in candidates:
            updated = dict(inst)
            updated["funded"] = 0
            db.update_instance(inst["id"], updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked {len(candidates)} bills unfunded.")



# ── Definitions Tab ───────────────────────────────────────────────────────────

class DefinitionsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._app = app
        self._selected_id = None
        self._sort_col = None
        self._sort_asc = True
        self._definitions = []
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search_filter())
        self._build()

    def _build(self):
        sub = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        sub.pack(fill="x")
        sub.pack_propagate(False)
        ctk.CTkLabel(sub, text=self._app._animal, fg_color="transparent",
                     font=ctk.CTkFont(size=15)).place(relx=0.5, rely=0.5, anchor="center")
        for label, cmd in [
            ("+ Add",           self._add),
            ("✎ Edit",          self._edit),
            ("⏸ Toggle Active", self._toggle),
            ("🗑 Delete",        self._delete),
        ]:
            ctk.CTkButton(sub, text=label, width=130, height=30,
                          command=cmd).pack(side="right", padx=6, pady=7)
        ctk.CTkEntry(sub, textvariable=self._search_var,
                     placeholder_text="🔍  Search definitions...",
                     width=200, height=30).pack(side="left", padx=(12, 0), pady=7)

        container = tk.Frame(self, bg="#fefce8")
        container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Def.Treeview",
                        background="#fefce8", foreground="#1c1917",
                        fieldbackground="#fefce8", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Def.Treeview.Heading",
                        background="#fef08a", foreground="#713f12",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Def.Treeview",
                  background=[("selected", "#854d0e")],
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
            self._tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=False)

        self._tree.tag_configure("active",   foreground="#1c1917")
        self._tree.tag_configure("inactive", foreground="#a8a29e")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit())

    def refresh(self, definitions):
        self._definitions = definitions
        self._apply_search_filter()

    def _apply_search_filter(self):
        q = self._search_var.get().strip().lower()
        rows = self._definitions
        if q:
            rows = [d for d in rows if
                    q in d.get("description", "").lower() or
                    q in d.get("frequency", "").lower() or
                    q in d.get("notes", "").lower()]
        self._tree.delete(*self._tree.get_children())
        self._selected_id = None
        for defn in rows:
            tag = "active" if defn.get("active") else "inactive"
            self._tree.insert("", "end", iid=str(defn["id"]),
                              values=_merge_defn_row(defn), tags=(tag,))
        if self._sort_col:
            self._apply_sort()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._apply_sort()

    def _apply_sort(self):
        for col, _ in DEF_COLUMNS:
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
        if col == "Active":
            return 0 if val == "✓" else 1
        if col == "Typical $":
            try:
                return float(val.replace("$", "").replace(",", ""))
            except ValueError:
                return 0.0
        if col == "Due Day":
            try:
                return int(val)
            except ValueError:
                return 0
        return val.lower()

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


# ── Register Tab ─────────────────────────────────────────────────────────────

class RegisterTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self._app = app
        self._selected_id = None
        self._sort_col = "Date"
        self._sort_asc = True
        self._transactions = []
        self._acct_settings = {"account_name": "", "starting_balance": 0.0, "as_of_date": ""}
        self._link_filter = "all"
        self._link_filter_btns = {}
        self._review_filter = "all"
        self._review_filter_btns = {}
        self._current_balance = 0.0
        self._last_import_msg = ""
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._populate_tree())
        today = date.today()
        self._reg_month = f"{today.year:04d}-{today.month:02d}"
        self._reg_all_months = []
        self._build()

    def _build(self):
        # ── Account info bar ─────────────────────────────────────────
        info_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card"])
        info_bar.pack(fill="x")
        info_bar.pack_propagate(False)

        self._acct_name_label = ctk.CTkLabel(
            info_bar, text="No account configured",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C["heading"])
        self._acct_name_label.pack(side="left", padx=(16, 0))

        self._balance_label = ctk.CTkLabel(
            info_bar, text="Balance: —",
            font=ctk.CTkFont(size=13), text_color=C["green"])
        self._balance_label.pack(side="left", padx=16)

        self._safe2spend_label = ctk.CTkLabel(
            info_bar, text="Safe2Spend: —",
            font=ctk.CTkFont(size=13), text_color=C["green"])
        self._safe2spend_label.pack(side="left", padx=16)

        self._txn_count_label = ctk.CTkLabel(
            info_bar, text="",
            font=ctk.CTkFont(size=12), text_color=C["muted"])
        self._txn_count_label.pack(side="left", padx=(20, 0))

        self._showing_txns_label = ctk.CTkLabel(
            info_bar, text="",
            font=ctk.CTkFont(size=12), text_color=C["muted"])
        self._showing_txns_label.pack(side="left", padx=(12, 0))

        self._totals_label = ctk.CTkLabel(
            info_bar, text="",
            font=ctk.CTkFont(size=12), text_color=C["muted"])
        self._totals_label.pack(side="left", padx=(12, 0))

        self._last_import_label = ctk.CTkLabel(
            info_bar, text="",
            font=ctk.CTkFont(size=12), text_color=C["muted"])
        self._last_import_label.pack(side="left", padx=(12, 0))

        ctk.CTkButton(info_bar, text="⚙ Account Settings", width=155, height=30,
                      command=self._account_settings).pack(side="right", padx=12, pady=7)

        # ── Month nav bar ─────────────────────────────────────────────
        nav = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=C["card"])
        nav.pack(fill="x")
        nav.pack_propagate(False)

        self._reg_left_btn = ctk.CTkButton(
            nav, text="◀", width=32, height=26,
            fg_color=C["border"], hover_color=C["card2"],
            command=self._reg_nav_left)
        self._reg_left_btn.pack(side="left", padx=(12, 2), pady=5)

        self._reg_month_lbl = ctk.CTkLabel(
            nav, text="", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C["heading"], width=130, anchor="center")
        self._reg_month_lbl.pack(side="left", padx=4)

        self._reg_right_btn = ctk.CTkButton(
            nav, text="▶", width=32, height=26,
            fg_color=C["border"], hover_color=C["card2"],
            command=self._reg_nav_right)
        self._reg_right_btn.pack(side="left", padx=(2, 8))

        self._reg_all_btn = ctk.CTkButton(
            nav, text="All", width=52, height=26,
            fg_color=C["border"], hover_color=C["card2"],
            command=self._reg_set_all)
        self._reg_all_btn.pack(side="left", padx=4)

        ctk.CTkLabel(nav, text=self._app._animal, fg_color="transparent",
                     font=ctk.CTkFont(size=15)).place(relx=0.5, rely=0.5, anchor="center")

        # ── Toolbar ──────────────────────────────────────────────────
        sub = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        sub.pack(fill="x")
        sub.pack_propagate(False)

        # Right side: filter button groups in a frame so they stay ordered
        filter_frame = ctk.CTkFrame(sub, fg_color="transparent")
        filter_frame.pack(side="right", padx=(0, 6), pady=7)

        for label, val in [("All", "all"), ("Linked", "linked"), ("Unlinked", "unlinked")]:
            btn = ctk.CTkButton(filter_frame, text=label, width=78, height=30,
                                fg_color=C["blue"] if val == "all" else C["border"],
                                hover_color=C["card2"],
                                command=lambda v=val: self._set_link_filter(v))
            btn.pack(side="left", padx=2)
            self._link_filter_btns[val] = btn

        tk.Frame(filter_frame, width=1, bg=C["border"]).pack(
            side="left", fill="y", padx=8, pady=4)

        for label, val in [("All", "all"), ("Reviewed", "reviewed"), ("Unreviewed", "unreviewed")]:
            btn = ctk.CTkButton(filter_frame, text=label, width=88, height=30,
                                fg_color=C["blue"] if val == "all" else C["border"],
                                hover_color=C["card2"],
                                command=lambda v=val: self._set_review_filter(v))
            btn.pack(side="left", padx=2)
            self._review_filter_btns[val] = btn

        # Left side: action buttons + search
        for label, cmd, width in [
            ("⬆ Import CSV",   self._import_csv,             115),
            ("🔗 Link to Bill", self._link_to_bill,           120),
            ("Unlink",          self._unlink_transaction,      72),
            ("✓ Review",        self._toggle_reviewed,         88),
            ("📋 Create Bill",  self._create_bill_from_txn,   110),
            ("⚠ Delete All",    self._delete_all_transactions, 100),
        ]:
            ctk.CTkButton(sub, text=label, width=width, height=30,
                          command=cmd).pack(side="left", padx=6, pady=7)

        ctk.CTkEntry(sub, textvariable=self._search_var,
                     placeholder_text="🔍  Search...",
                     width=180, height=30).pack(side="left", padx=(8, 0), pady=7)

        # ── Table ────────────────────────────────────────────────────
        self._table_container = tk.Frame(self, bg="#fefce8")
        self._table_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Reg.Treeview",
                        background="#fefce8", foreground="#1c1917",
                        fieldbackground="#fefce8", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Reg.Treeview.Heading",
                        background="#fef08a", foreground="#713f12",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Reg.Treeview",
                  background=[("selected", "#854d0e")],
                  foreground=[("selected", "#ffffff")])

        col_ids = [c[0] for c in REG_COLUMNS]
        vsb = ttk.Scrollbar(self._table_container, orient="vertical")
        hsb = ttk.Scrollbar(self._table_container, orient="horizontal")
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree = ttk.Treeview(self._table_container, columns=col_ids, show="headings",
                                   style="Reg.Treeview",
                                   yscrollcommand=vsb.set,
                                   xscrollcommand=hsb.set,
                                   selectmode="browse")
        vsb.config(command=self._tree.yview)
        hsb.config(command=self._tree.xview)
        self._tree.pack(fill="both", expand=True)

        for col, width in REG_COLUMNS:
            anchor = "w" if col in REG_LEFT_ALIGN else "e"
            self._tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=False)

        self._tree.tag_configure("deposit",      foreground=C["green"])
        self._tree.tag_configure("payment",      foreground="#1c1917")
        self._tree.tag_configure("negative_bal", foreground=C["red"])
        self._tree.tag_configure("linked",       background="#fde68a", foreground="#78350f")
        self._tree.tag_configure("reviewed",     foreground="#a8a29e")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._apply_sort_arrow()

    def _apply_sort_arrow(self):
        for col, _ in REG_COLUMNS:
            self._tree.heading(col, text=col)
        arrow = " ▲" if self._sort_asc else " ▼"
        self._tree.heading(self._sort_col, text=self._sort_col + arrow)

    def _latest_bank_balance(self, transactions):
        """Return the bank's balance from the most recently dated transaction."""
        txns_with_bal = [t for t in transactions if t.get("bank_balance") is not None]
        if not txns_with_bal:
            return 0.0
        def date_key(t):
            d = t.get("date", "")
            try:
                m, day, y = d.split("/")
                txn_num = t.get("transaction_number") or ""
                try:
                    tnum = int(txn_num)
                except (ValueError, TypeError):
                    tnum = 0
                return (int(y), int(m), int(day), tnum, t["id"])
            except Exception:
                return (0, 0, 0, 0, t["id"])
        return max(txns_with_bal, key=date_key)["bank_balance"]

    def _update_reg_nav(self):
        if self._reg_month is None:
            self._reg_month_lbl.configure(text="All Months")
            self._reg_all_btn.configure(fg_color=C["blue"])
            self._reg_left_btn.configure(state="disabled")
            self._reg_right_btn.configure(state="disabled")
        else:
            self._reg_month_lbl.configure(text=_month_label(self._reg_month))
            self._reg_all_btn.configure(fg_color=C["border"])
            months = self._reg_all_months
            if months and self._reg_month in months:
                idx = months.index(self._reg_month)
                self._reg_left_btn.configure(
                    state="normal" if idx > 0 else "disabled")
                self._reg_right_btn.configure(
                    state="normal" if idx < len(months) - 1 else "disabled")
            else:
                self._reg_left_btn.configure(state="disabled")
                self._reg_right_btn.configure(state="disabled")

    def _reg_nav_left(self):
        if not self._reg_all_months or self._reg_month is None:
            return
        try:
            idx = self._reg_all_months.index(self._reg_month)
        except ValueError:
            self._reg_month = self._reg_all_months[-1]
            self._update_reg_nav()
            self._populate_tree()
            return
        if idx > 0:
            self._reg_month = self._reg_all_months[idx - 1]
            self._update_reg_nav()
            self._populate_tree()

    def _reg_nav_right(self):
        if not self._reg_all_months or self._reg_month is None:
            return
        try:
            idx = self._reg_all_months.index(self._reg_month)
        except ValueError:
            self._reg_month = self._reg_all_months[-1]
            self._update_reg_nav()
            self._populate_tree()
            return
        if idx < len(self._reg_all_months) - 1:
            self._reg_month = self._reg_all_months[idx + 1]
            self._update_reg_nav()
            self._populate_tree()

    def _reg_set_all(self):
        if self._reg_month is None:
            today = date.today()
            self._reg_month = f"{today.year:04d}-{today.month:02d}"
        else:
            self._reg_month = None
        self._update_reg_nav()
        self._populate_tree()

    def refresh(self, transactions, acct_settings):
        self._transactions = transactions
        self._acct_settings = acct_settings
        name = acct_settings.get("account_name", "").strip()
        self._acct_name_label.configure(text=name if name else "No account configured")

        self._current_balance = self._latest_bank_balance(transactions)
        bal_color = C["green"] if self._current_balance >= 0 else C["red"]
        bal_str = (f"${self._current_balance:,.2f}"
                   if self._current_balance >= 0
                   else f"-${abs(self._current_balance):,.2f}")
        self._balance_label.configure(text=f"Balance: {bal_str}", text_color=bal_color)

        funded_not_paid = db.get_funded_not_paid_total(DB_PATH)
        s2s = self._current_balance - funded_not_paid
        s2s_color = C["green"] if s2s >= 0 else C["red"]
        s2s_str = f"${s2s:,.2f}" if s2s >= 0 else f"-${abs(s2s):,.2f}"
        self._safe2spend_label.configure(text=f"Safe2Spend: {s2s_str}", text_color=s2s_color)
        self._app._header_s2s_label.configure(text=f"Safe2Spend: {s2s_str}", text_color=s2s_color)

        txn_count = db.get_transaction_count(DB_PATH)
        self._txn_count_label.configure(text=f"Cumulative Txns: {txn_count:,}")
        self._last_import_label.configure(text=self._last_import_msg)

        # compute months that have transactions
        seen = set()
        for t in transactions:
            d = t.get("date", "")
            try:
                m, _d, y = d.split("/")
                seen.add(f"{y}-{m.zfill(2)}")
            except Exception:
                pass
        self._reg_all_months = sorted(seen)

        # if current month has no transactions, snap to nearest earlier month
        if self._reg_month is not None and self._reg_all_months:
            if self._reg_month not in self._reg_all_months:
                candidates = [m for m in self._reg_all_months if m <= self._reg_month]
                self._reg_month = candidates[-1] if candidates else self._reg_all_months[-1]

        self._update_reg_nav()
        self._populate_tree()

    def _set_link_filter(self, val):
        self._link_filter = val
        for v, btn in self._link_filter_btns.items():
            btn.configure(fg_color=C["blue"] if v == val else C["border"])
        self._populate_tree()

    def _set_review_filter(self, val):
        self._review_filter = val
        for v, btn in self._review_filter_btns.items():
            btn.configure(fg_color=C["blue"] if v == val else C["border"])
        self._populate_tree()

    def _toggle_reviewed(self):
        if not self._selected_id:
            self._app.flash("Select a transaction to toggle reviewed status.")
            return
        # Capture display order before refresh so we can advance the selection.
        ordered = list(self._tree.get_children(""))
        cur_iid = str(self._selected_id)
        try:
            cur_idx = ordered.index(cur_iid)
        except ValueError:
            cur_idx = None

        db.toggle_reviewed(self._selected_id, DB_PATH)
        self._app.refresh()

        if cur_idx is not None:
            new_order = self._tree.get_children("")
            if new_order:
                # If the acted-on row is gone (filtered out), the next item is
                # now sitting at cur_idx. If it stayed, advance by 1.
                row_still_present = cur_iid in new_order
                next_idx = cur_idx + (1 if row_still_present else 0)
                target = new_order[min(next_idx, len(new_order) - 1)]
                self._tree.selection_set(target)
                self._tree.focus(target)
                self._tree.see(target)
                self._selected_id = int(target)

    def _populate_tree(self):
        self._tree.delete(*self._tree.get_children())
        self._selected_id = None

        txns = self._transactions
        if self._reg_month is not None:
            _rm = self._reg_month
            def _in_month(t):
                d = t.get("date", "")
                try:
                    m, _d, y = d.split("/")
                    return f"{y}-{m.zfill(2)}" == _rm
                except Exception:
                    return False
            txns = [t for t in txns if _in_month(t)]
        if self._link_filter == "linked":
            txns = [t for t in txns if t.get("bill_description")]
        elif self._link_filter == "unlinked":
            txns = [t for t in txns if not t.get("bill_description")]

        if self._review_filter == "reviewed":
            txns = [t for t in txns if t.get("reviewed")]
        elif self._review_filter == "unreviewed":
            txns = [t for t in txns if not t.get("reviewed")]

        q = self._search_var.get().strip().lower()
        if q:
            def _matches(t):
                if q in t.get("description", "").lower():
                    return True
                if q in t.get("memo", "").lower():
                    return True
                if q in f"{t.get('amount', 0):,.2f}":
                    return True
                return False
            txns = [t for t in txns if _matches(t)]

        for txn in txns:
            bb = txn.get("bank_balance")
            is_linked = bool(txn.get("bill_description"))
            is_reviewed = bool(txn.get("reviewed"))
            if bb is not None and bb < 0:
                tag = "negative_bal"
            elif is_linked:
                tag = "linked"
            elif is_reviewed:
                tag = "reviewed"
            elif txn["type"] == "Deposit":
                tag = "deposit"
            else:
                tag = "payment"
            self._tree.insert("", "end", iid=str(txn["id"]),
                              values=_merge_reg_row(txn), tags=(tag,))
        self._showing_txns_label.configure(text=f"Showing Txns: {len(txns):,}")
        total_debit = sum(t["amount"] for t in txns if t["type"] == "Payment")
        total_credit = sum(t["amount"] for t in txns if t["type"] == "Deposit")
        self._totals_label.configure(
            text=f"Debits: ${total_debit:,.2f}  Credits: ${total_credit:,.2f}")
        self._apply_sort()

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._apply_sort()

    def _apply_sort(self):
        self._apply_sort_arrow()
        items = [(self._tree.set(k, self._sort_col), k)
                 for k in self._tree.get_children("")]
        items.sort(key=lambda x: self._sort_key(self._sort_col, x[0]),
                   reverse=not self._sort_asc)
        for idx, (_, k) in enumerate(items):
            self._tree.move(k, "", idx)

    def _sort_key(self, col, val):
        if col == "Date":
            if not val:
                return (9999, 99, 99)
            try:
                m, d, y = val.split("/")
                return (int(y), int(m), int(d))
            except Exception:
                return (9999, 99, 99)
        if col in ("Debit", "Credit", "Balance"):
            try:
                return float(val.replace("$", "").replace(",", "").replace("-", "")) if val else 0.0
            except ValueError:
                return 0.0
        return val.lower() if val else ""

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _import_csv(self):
        path = filedialog.askopenfilename(
            title="Import Bank CSV",
            filetypes=[("CSV files", "*.csv *.CSV"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            rows = parse_bank_csv(path)
        except Exception as e:
            self._app.flash(f"Error reading CSV: {e}")
            return
        existing_keys = db.get_imported_transaction_keys(DB_PATH)
        existing_fps  = db.get_transaction_fingerprints(DB_PATH)
        new_count = 0
        dup_count = 0
        for row in rows:
            txn_num = row.get("transaction_number", "")
            if txn_num:
                key = (txn_num, row.get("date", ""))
                if key in existing_keys:
                    dup_count += 1
                    continue
                db.insert_transaction(row, DB_PATH)
                existing_keys.add(key)
            else:
                fp = (row.get("date", ""), row.get("type", ""), row.get("amount", 0.0), row.get("description", ""))
                if fp in existing_fps:
                    dup_count += 1
                    continue
                db.insert_transaction(row, DB_PATH)
                existing_fps.add(fp)
            new_count += 1
        self._last_import_msg = f"Last Import: {new_count} new"
        self._app.refresh()
        s2s = db.get_safe2spend(DB_PATH)
        msg = f"Imported {new_count} transactions ({dup_count} duplicates skipped)"
        if s2s < 0:
            msg += f"  ⚠ Safe2Spend is now {_fmt(s2s)} — consider unfunding some bills"
        self._app.flash(msg)

    def _link_to_bill(self):
        if not self._selected_id:
            self._app.flash("Select a transaction to link to a bill.")
            return
        txn = next((t for t in self._transactions if t["id"] == self._selected_id), None)
        if not txn:
            return
        if txn["type"] != "Payment":
            self._app.flash("Only Payment transactions can be linked to bills.")
            return
        if txn.get("bill_description"):
            self._app.flash("This transaction is already linked to a bill.")
            return
        LinkBillDialog(self, self._app, txn)

    def _unlink_transaction(self):
        if not self._selected_id:
            self._app.flash("Select a transaction to unlink.")
            return
        txn = next((t for t in self._transactions if t["id"] == self._selected_id), None)
        if not txn or not txn.get("bill_instance_id"):
            self._app.flash("Selected transaction has no linked bill.")
            return
        bill_desc  = txn.get("bill_description", "this bill")
        instance_id = txn["bill_instance_id"]
        ConfirmDialog(self, self._app,
                      f"Unlink from \"{bill_desc}\"?\nThe bill will revert to unpaid.",
                      lambda: (db.unlink_transaction(instance_id, DB_PATH),
                               self._app.refresh()))

    def _create_bill_from_txn(self):
        if not self._selected_id:
            self._app.flash("Select a transaction to create a bill from.")
            return
        txn = next((t for t in self._transactions if t["id"] == self._selected_id), None)
        if not txn:
            return
        CreateBillFromTxnDialog(self, self._app, txn)

    def _delete_all_transactions(self):
        count = len(self._transactions)
        if count == 0:
            self._app.flash("No transactions to delete.")
            return
        ConfirmDialog(self, self._app,
                      f"Delete ALL {count} transactions and revert\n"
                      f"any linked bills to unpaid?\nThis cannot be undone.",
                      lambda: (db.delete_all_transactions(DB_PATH),
                               self._app.refresh()))

    def _account_settings(self):
        AccountSettingsDialog(self, self._app, self._acct_settings)


def _merge_reg_row(txn):
    debit   = f"${txn['amount']:,.2f}" if txn["type"] == "Payment" else ""
    credit  = f"${txn['amount']:,.2f}" if txn["type"] == "Deposit"  else ""
    bb      = txn.get("bank_balance")
    bal_str = (f"${bb:,.2f}" if bb >= 0 else f"-${abs(bb):,.2f}") if bb is not None else ""
    return (
        "✓" if txn.get("reviewed") else "",
        txn.get("transaction_number", ""),
        txn.get("date", ""),
        txn.get("description", ""),
        txn.get("memo", ""),
        debit,
        credit,
        bal_str,
        txn.get("check_number", ""),
        txn.get("bill_description", "") or "",
    )


def parse_bank_csv(path):
    """Parse bank CSV export into a list of transaction dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for _ in range(3):
            next(f, None)
        reader = csv.DictReader(f)
        for raw in reader:
            debit  = raw.get("Amount Debit",  "").strip()
            credit = raw.get("Amount Credit", "").strip()
            if not debit and not credit:
                continue
            if debit:
                try:
                    amount = abs(float(debit.replace("$", "").replace(",", "")))
                    txn_type = "Payment"
                except ValueError:
                    continue
            else:
                try:
                    amount = abs(float(credit.replace("$", "").replace(",", "")))
                    txn_type = "Deposit"
                except ValueError:
                    continue
            if amount == 0:
                continue
            desc      = re.sub(r"(?i)^(?:debit|credit)\s+", "", raw.get("Description", "").strip())
            memo      = raw.get("Memo", "").strip()
            check_num = raw.get("Check Number", "").strip()
            bb_str    = raw.get("Balance", "").strip().replace("$", "").replace(",", "")
            try:
                bank_bal = float(bb_str) if bb_str else None
            except ValueError:
                bank_bal = None
            rows.append({
                "date":               raw.get("Date", "").strip(),
                "description":        desc,
                "type":               txn_type,
                "amount":             amount,
                "memo":               memo,
                "check_number":       check_num,
                "bank_balance":       bank_bal,
                "notes":              "",
                "transaction_number": raw.get("Transaction Number", "").strip().strip('"'),
            })
    return rows

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
            self._due_in_hint.pack(padx=16, anchor="w", before=self._err)
            self._due_in_row.pack(fill="x", padx=16, pady=5, before=self._due_in_hint)
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


# ── Transaction Dialog ────────────────────────────────────────────────────────

class TransactionDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, mode, txn=None):
        super().__init__(parent)
        self._app  = app
        self._mode = mode
        self._txn  = txn

        title = "Add Transaction" if mode == "add" else "Edit Transaction"
        self.title(title)
        self.geometry("420x360")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        today_str = date.today().strftime("%m/%d/%Y")

        self._vars = {}
        for label, default in [
            ("Date",        txn["date"]        if txn else today_str),
            ("Description", txn["description"] if txn else ""),
            ("Amount",      str(txn["amount"]) if txn else ""),
            ("Notes",       txn["notes"]       if txn else ""),
        ]:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            ctk.CTkEntry(row, textvariable=var, width=260).pack(side="left")
            self._vars[label] = var

        # Type toggle
        type_row = ctk.CTkFrame(self, fg_color="transparent")
        type_row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(type_row, text="Type", width=100, anchor="w").pack(side="left")
        self._type_var = tk.StringVar(value=txn["type"] if txn else "Payment")
        self._dep_btn = ctk.CTkButton(type_row, text="Deposit",  width=125, height=30,
                                      command=lambda: self._set_type("Deposit"))
        self._pay_btn = ctk.CTkButton(type_row, text="Payment",  width=125, height=30,
                                      command=lambda: self._set_type("Payment"))
        self._dep_btn.pack(side="left", padx=(0, 4))
        self._pay_btn.pack(side="left")
        self._update_type_btns()

        ctk.CTkLabel(self, text="Date format: MM/DD/YYYY",
                     font=ctk.CTkFont(size=10), text_color=C["muted"]).pack(
            padx=16, anchor="w")

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

    def _set_type(self, t):
        self._type_var.set(t)
        self._update_type_btns()

    def _update_type_btns(self):
        t = self._type_var.get()
        self._dep_btn.configure(
            fg_color=C["blue"] if t == "Deposit" else C["border"],
            text_color=C["heading"] if t == "Deposit" else C["muted"])
        self._pay_btn.configure(
            fg_color=C["blue"] if t == "Payment" else C["border"],
            text_color=C["heading"] if t == "Payment" else C["muted"])

    def _save(self):
        date_str = self._vars["Date"].get().strip()
        try:
            parts = date_str.split("/")
            if len(parts) != 3:
                raise ValueError
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            if not (1 <= m <= 12 and 1 <= d <= 31 and y >= 1900):
                raise ValueError
        except ValueError:
            self._err.configure(text="Date must be MM/DD/YYYY.")
            return

        desc = self._vars["Description"].get().strip()
        if not desc:
            self._err.configure(text="Description is required.")
            return

        try:
            amount = float(self._vars["Amount"].get().replace("$", "").replace(",", ""))
            if amount < 0:
                raise ValueError
        except ValueError:
            self._err.configure(text="Amount must be a positive number.")
            return

        data = {
            "date":        date_str,
            "description": desc,
            "type":        self._type_var.get(),
            "amount":      amount,
            "notes":       self._vars["Notes"].get().strip(),
        }
        if self._mode == "add":
            db.insert_transaction(data, DB_PATH)
        else:
            db.update_transaction(self._txn["id"], data, DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Account Settings Dialog ───────────────────────────────────────────────────

class AccountSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, current_settings):
        super().__init__(parent)
        self._app = app
        self._current_settings = current_settings

        self.title("Account Settings")
        self.geometry("380x170")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text="Account Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(row, text="Account Name", width=130, anchor="w").pack(side="left")
        var = tk.StringVar(value=current_settings.get("account_name", ""))
        ctk.CTkEntry(row, textvariable=var, width=220).pack(side="left")
        self._vars["Account Name"] = var

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12, side="bottom")
        ctk.CTkButton(btn_row, text="Save", width=120, height=36,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100, height=36,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

    def _save(self):
        name = self._vars["Account Name"].get().strip()
        db.set_account_settings({
            "account_name":     name,
            "starting_balance": 0.0,
            "as_of_date":       "",
        }, DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Create Bill from Transaction Dialog ──────────────────────────────────────

class CreateBillFromTxnDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, txn):
        super().__init__(parent)
        self._app = app
        self._txn = txn

        self.title("Create Bill from Transaction")
        self.geometry("460x520")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        # Transaction summary header
        hdr = ctk.CTkFrame(self, fg_color=C["card2"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="Transaction:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C["muted"]).pack(side="left", padx=(12, 6), pady=8)
        ctk.CTkLabel(hdr,
                     text=f"{txn['date']}  |  {txn['description']}  |  ${txn['amount']:,.2f}",
                     font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")

        # Parse transaction date for pre-fills
        try:
            _m, _d, _y = txn["date"].split("/")
            self._txn_month_key = f"{_y}-{_m}"
            self._txn_due_day   = int(_d)
        except Exception:
            self._txn_month_key = date.today().strftime("%Y-%m")
            self._txn_due_day   = 1

        def _field(label, default):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=120, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            ctk.CTkEntry(row, textvariable=var, width=260).pack(side="left")
            return var

        def _menu(label, values, default):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=120, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            ctk.CTkOptionMenu(row, values=values, variable=var, width=260).pack(side="left")
            return var

        # Strip leading "Debit "/"Credit " from description (already done in parse, but just in case)
        raw_desc = re.sub(r"^(debit|credit)\s+", "", txn.get("description", ""), flags=re.IGNORECASE).strip()

        self._desc_var    = _field("Description",   raw_desc)
        self._amount_var  = _field("Typical $",     f"{txn['amount']:.2f}")
        self._due_day_var = _field("Due Day (1–31)", str(self._txn_due_day))
        self._freq_var    = _menu("Frequency",      FREQUENCIES, "Monthly")
        self._pm_var      = _menu("Payment Mode",   PAYMENT_MODES, "—")
        self._vibe_var    = _menu("Vibe",           VIBES, "—")
        self._notes_var   = _field("Notes",         "")

        # Link checkbox
        link_row = ctk.CTkFrame(self, fg_color="transparent")
        link_row.pack(fill="x", padx=16, pady=(8, 2))
        self._link_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(link_row, text="Link this transaction to the new bill",
                        variable=self._link_var).pack(side="left")

        self._err = ctk.CTkLabel(self, text="", text_color=C["red"],
                                 font=ctk.CTkFont(size=11))
        self._err.pack(padx=16, anchor="w", pady=(4, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12, side="bottom")
        ctk.CTkButton(btn_row, text="Create", width=120,
                      command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

    def _save(self):
        desc = self._desc_var.get().strip()
        if not desc:
            self._err.configure(text="Description is required.")
            return
        try:
            amount = float(self._amount_var.get().replace("$", "").replace(",", ""))
        except ValueError:
            self._err.configure(text="Typical $ must be a number.")
            return
        try:
            due_day = int(self._due_day_var.get().strip())
            if not 1 <= due_day <= 31:
                raise ValueError
        except ValueError:
            self._err.configure(text="Due Day must be 1–31.")
            return

        freq = self._freq_var.get()
        pm   = self._pm_var.get()
        vibe = self._vibe_var.get()

        defn_data = {
            "description":    desc,
            "frequency":      freq,
            "typical_amount": amount,
            "due_day":        due_day,
            "months_active":  "",
            "adhoc_month":    self._txn_month_key if freq == "AdHoc" else "",
            "notes":          self._notes_var.get().strip(),
            "payment_mode":   "" if pm   == "—" else pm,
            "vibe":           "" if vibe == "—" else vibe,
        }

        # Safe2Spend / funding rules:
        #
        # Case A — link checked: link_bill_to_transaction sets funded=1 + status=Paid
        #   atomically. A Paid bill is never counted in funded_not_yet_paid, so
        #   Safe2Spend is unchanged. No check needed — the money already left the
        #   account and is reflected in bank_balance.
        #
        # Case B — link unchecked: instance is created funded=0 + status=Due.
        #   Unfunded bills also never enter funded_not_yet_paid, so Safe2Spend is
        #   unchanged. If the user manually funds it later, _toggle_funded enforces
        #   the Safe2Spend check at that point.
        #
        # In neither case do we create a funded=1 + status=Due (the only combination
        # that would reduce Safe2Spend), so no pre-flight check is required here.

        # Clamp due_day to actual month-end for the due_date on the instance
        import calendar as _cal
        yr, mo = map(int, self._txn_month_key.split("-"))
        actual_day = min(due_day, _cal.monthrange(yr, mo)[1])
        due_date = f"{mo:02d}/{actual_day:02d}/{yr}"

        def_id  = db.insert_definition(defn_data, DB_PATH)
        inst_id = db.insert_instance({
            "definition_id": def_id,
            "month_key":     self._txn_month_key,
            "description":   desc,
            "status":        "Due",
            "due_date":      due_date,
            "amount":        amount,
            "frequency":     freq,
            "payment_mode":  defn_data["payment_mode"],
            "vibe":          defn_data["vibe"],
            "funded":        0,       # always starts unfunded; link_bill_to_transaction
            "date_paid":     "",      # handles fund+pay atomically if link is checked
            "notes":         defn_data["notes"],
        }, DB_PATH)

        if self._link_var.get():
            db.link_bill_to_transaction(inst_id, self._txn["id"], DB_PATH)

        self.destroy()
        self._app.refresh()


# ── Link Bill Dialog ──────────────────────────────────────────────────────────

class LinkBillDialog(ctk.CTkToplevel):
    def __init__(self, parent, app, txn):
        super().__init__(parent)
        self._app = app
        self._txn = txn
        self._selected_instance_id = None
        self._show_all = False

        self.title("Link Transaction to Bill")
        self.geometry("620x440")
        self.resizable(True, True)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        hdr = ctk.CTkFrame(self, fg_color=C["card2"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="Transaction:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=C["muted"]).pack(side="left", padx=(12, 6), pady=8)
        ctk.CTkLabel(hdr,
                     text=f"{txn['date']}  |  {txn['description']}  |  ${txn['amount']:,.2f}",
                     font=ctk.CTkFont(size=12), text_color=C["text"]).pack(side="left")

        # Toolbar row: filter label + search + Show All button
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(6, 0))
        self._filter_label = ctk.CTkLabel(toolbar, text="",
                                           font=ctk.CTkFont(size=11),
                                           text_color=C["muted"])
        self._filter_label.pack(side="left")
        self._show_all_btn = ctk.CTkButton(toolbar, text="Show All",
                                            width=80, height=26,
                                            fg_color=C["border"],
                                            command=self._toggle_show_all)
        self._show_all_btn.pack(side="right")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search())
        ctk.CTkEntry(toolbar, textvariable=self._search_var,
                     placeholder_text="🔍  description or amount...",
                     width=200, height=26).pack(side="right", padx=(0, 8))

        container = tk.Frame(self, bg="#fefce8")
        container.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        cols = [("Month", 90), ("Description", 240), ("Amount", 95),
                ("Due Date", 95), ("Funded?", 65)]
        style = ttk.Style()
        style.configure("Link.Treeview",
                        background="#fefce8", foreground="#1c1917",
                        fieldbackground="#fefce8", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Link.Treeview.Heading",
                        background="#fef08a", foreground="#713f12",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Link.Treeview",
                  background=[("selected", "#854d0e")],
                  foreground=[("selected", "#ffffff")])

        vsb = ttk.Scrollbar(container, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._tree = ttk.Treeview(container, columns=[c[0] for c in cols], show="headings",
                                   style="Link.Treeview",
                                   yscrollcommand=vsb.set,
                                   selectmode="browse")
        vsb.config(command=self._tree.yview)
        self._tree.pack(fill="both", expand=True)

        for col, width in cols:
            anchor = "w" if col == "Description" else "e"
            self._tree.column(col, width=width, minwidth=40, anchor=anchor, stretch=False)
            self._tree.heading(col, text=col)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Pre-compute smart vs all lists once
        all_instances = db.load_linkable_instances(DB_PATH)
        txn_amount = txn.get("amount", 0.0) or 0.0
        try:
            m, d, y = txn["date"].split("/")
            txn_month = f"{y}-{m}"
        except Exception:
            txn_month = ""

        same_month = [i for i in all_instances if i["month_key"] == txn_month]
        same_month.sort(key=lambda i: abs((i.get("amount") or 0.0) - txn_amount))

        self._smart_instances = same_month
        self._all_instances   = all_instances

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=10, side="bottom")
        self._link_btn = ctk.CTkButton(btn_row, text="Link", width=110,
                                        state="disabled", command=self._do_link)
        self._link_btn.pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right")

        self._apply_search()

    def _toggle_show_all(self):
        self._show_all = not self._show_all
        self._show_all_btn.configure(
            fg_color=C["blue"] if self._show_all else C["border"])
        self._selected_instance_id = None
        self._link_btn.configure(state="disabled")
        self._apply_search()

    def _apply_search(self):
        q = self._search_var.get().strip().lower()
        base = self._all_instances if self._show_all else self._smart_instances
        if q:
            def _matches(inst):
                if q in inst.get("description", "").lower():
                    return True
                if q in _fmt(inst.get("amount", 0)):
                    return True
                return False
            filtered = [i for i in base if _matches(i)]
        else:
            filtered = base
        self._selected_instance_id = None
        self._link_btn.configure(state="disabled")
        self._populate(filtered)

    def _populate(self, instances):
        self._tree.delete(*self._tree.get_children())
        for inst in instances:
            yr, mo = inst["month_key"].split("-")
            mlabel = f"{MONTH_NAMES[int(mo)-1]} {yr}"
            funded = "✓" if inst.get("funded") else ""
            self._tree.insert("", "end", iid=str(inst["id"]),
                              values=(mlabel, inst["description"],
                                      _fmt(inst["amount"]), inst["due_date"], funded))
        total = len(self._all_instances)
        base_count = len(self._all_instances if self._show_all else self._smart_instances)
        showing = len(instances)
        if self._show_all:
            self._filter_label.configure(
                text=f"Showing {showing} of {total} unlinked bills")
        else:
            try:
                m, d, y = self._txn["date"].split("/")
                mo_name = f"{MONTH_NAMES[int(m)-1]} {y}"
            except Exception:
                mo_name = "this month"
            self._filter_label.configure(
                text=f"Showing {showing} of {total} bills — {mo_name}, by amount match")
        if not instances:
            ctk.CTkLabel(self, text="No matching bills found.",
                         font=ctk.CTkFont(size=12), text_color=C["muted"]).pack(pady=16)

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._selected_instance_id = int(sel[0]) if sel else None
        self._link_btn.configure(state="normal" if self._selected_instance_id else "disabled")

    def _do_link(self):
        if not self._selected_instance_id:
            return
        db.link_bill_to_transaction(self._selected_instance_id, self._txn["id"], DB_PATH)
        self.destroy()
        self._app.refresh()


# ── Accounts Tab ─────────────────────────────────────────────────────────────

ACCT_CATEGORIES = ["Cash", "Investments", "Credit Cards", "Loans"]

class AccountsTab(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self._app      = app
        self._accounts = []
        self._nw_history = []
        self._nw_settings = {"nw_start_date": "", "cash_goal": 0.0}
        self._metrics  = None
        self._debt_metrics = None
        self._selected_id = None
        self._metric_vals  = {}
        self._summary_visible = True
        self._saved_sash_y = None
        self._initial_sash_y = None
        self._initial_summary_visible = True
        self._cat_open = {c: True for c in ACCT_CATEGORIES}

        self._build_toolbar()
        self._build_body()

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text=self._app._animal, fg_color="transparent",
                     font=ctk.CTkFont(size=15)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(bar, text="+ Add Account", width=120, height=30,
                      fg_color=C["blue"], hover_color=C["heading"],
                      text_color="#ffffff", font=ctk.CTkFont(size=13),
                      command=self._on_add).pack(side="left", padx=(10, 4), pady=7)
        ctk.CTkButton(bar, text="✎ Edit", width=80, height=30,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"], font=ctk.CTkFont(size=13),
                      command=self._on_edit).pack(side="left", padx=4, pady=7)
        ctk.CTkButton(bar, text="🗑 Delete", width=90, height=30,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"], font=ctk.CTkFont(size=13),
                      command=self._on_delete).pack(side="left", padx=4, pady=7)
        self._log_btn = ctk.CTkButton(bar, text="📈 Log Balance", width=120, height=30,
                                      fg_color=C["border"], hover_color=C["card2"],
                                      text_color=C["text"], font=ctk.CTkFont(size=13),
                                      command=self._on_log)
        self._log_btn.pack(side="left", padx=4, pady=7)
        ctk.CTkButton(bar, text="⚙ Settings", width=100, height=30,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"], font=ctk.CTkFont(size=13),
                      command=self._on_settings).pack(side="right", padx=(4, 10), pady=7)
        self._toggle_btn = ctk.CTkButton(bar, text="▲ Hide Summary", width=130, height=30,
                                         fg_color=C["border"], hover_color=C["card2"],
                                         text_color=C["text"], font=ctk.CTkFont(size=13),
                                         command=self._toggle_summary)
        self._toggle_btn.pack(side="right", padx=(0, 4), pady=7)

    # ── Body layout ───────────────────────────────────────────────────────────

    def _build_body(self):
        self._paned = tk.PanedWindow(self, orient="vertical",
                                     sashwidth=7, sashrelief="flat",
                                     bg=C["border"], bd=0)
        self._paned.pack(fill="both", expand=True)

        # ── Top pane: collapsible summary ─────────────────────────────────────
        self._summary_section = tk.Frame(self._paned, bg=C["bg"])

        top = ctk.CTkFrame(self._summary_section, fg_color=C["bg"], corner_radius=0)
        top.pack(fill="x", padx=12, pady=(10, 0))
        self._build_summary_panel(top)
        self._build_metrics_panel(top)

        self._build_debt_summary(self._summary_section)
        tk.Frame(self._summary_section, height=1, bg=C["border"]).pack(
            fill="x", padx=12, pady=(6, 0))

        self._paned.add(self._summary_section, stretch="always", minsize=0)

        # ── Bottom pane: account list ──────────────────────────────────────────
        acct_pane = tk.Frame(self._paned, bg=C["bg"])
        self._build_account_list(acct_pane)
        self._paned.add(acct_pane, stretch="always", minsize=60)

        # Set initial sash at ~50% after first render
        self._paned.after(100, self._set_initial_sash)

    # ── Summary panel ─────────────────────────────────────────────────────────

    def _build_summary_panel(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10,
                            border_width=1, border_color=C["border"], width=320)
        card.pack(side="left", fill="y", padx=(0, 10), pady=0)
        card.pack_propagate(False)

        pad = {"padx": 16, "pady": (4, 0)}

        ctk.CTkLabel(card, text="Net Worth",
                     font=ctk.CTkFont(size=12), text_color=C["muted"]).pack(anchor="w", **pad)
        self._nw_label = ctk.CTkLabel(card, text="—",
                                      font=ctk.CTkFont(size=28, weight="bold"),
                                      text_color=C["text"])
        self._nw_label.pack(anchor="w", padx=16, pady=(0, 4))

        self._status_label = ctk.CTkLabel(card, text="",
                                          font=ctk.CTkFont(size=13), text_color=C["muted"])
        self._status_label.pack(anchor="w", **pad)

        tk.Frame(card, height=1, bg=C["border"]).pack(fill="x", padx=16, pady=8)

        for attr, label in [
            ("_nw_css_label",    "NW Since Start"),
            ("_nw_lc_label",     "Last Change"),
            ("_assets_css_label","Assets Since Start"),
            ("_debt_css_label",  "Debt Since Start"),
        ]:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=1)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                         text_color=C["muted"], width=140, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=C["text"], anchor="e")
            lbl.pack(side="right")
            setattr(self, attr, lbl)

        tk.Frame(card, height=1, bg=C["border"]).pack(fill="x", padx=16, pady=8)

        # Goals
        ctk.CTkLabel(card, text="GOALS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C["muted"]).pack(anchor="w", padx=16)

        for attr_bar, attr_lbl, label in [
            ("_cash_goal_bar",  "_cash_goal_lbl",  "Cash Goal"),
            ("_debt_goal_bar",  "_debt_goal_lbl",  "Debt Reduction"),
        ]:
            g = ctk.CTkFrame(card, fg_color="transparent")
            g.pack(fill="x", padx=16, pady=(4, 0))
            hdr = ctk.CTkFrame(g, fg_color="transparent")
            hdr.pack(fill="x")
            ctk.CTkLabel(hdr, text=label, font=ctk.CTkFont(size=12),
                         text_color=C["muted"], anchor="w").pack(side="left")
            pct_lbl = ctk.CTkLabel(hdr, text="—", font=ctk.CTkFont(size=12),
                                   text_color=C["muted"], anchor="e")
            pct_lbl.pack(side="right")
            bar = ctk.CTkProgressBar(g, progress_color=C["green"], fg_color=C["border"],
                                     height=10, corner_radius=4)
            bar.set(0)
            bar.pack(fill="x", pady=(2, 4))
            setattr(self, attr_bar, bar)
            setattr(self, attr_lbl, pct_lbl)

    # ── Debt summary row ──────────────────────────────────────────────────────

    def _build_debt_summary(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10,
                            border_width=1, border_color=C["border"])
        card.pack(fill="x", padx=12, pady=(8, 0))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)
        card.grid_columnconfigure(2, weight=1)
        card.grid_columnconfigure(3, weight=0)
        card.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(card, text="Total Debt",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(18, 8), pady=(8, 0))
        self._lbl_total_debt = ctk.CTkLabel(card, text="—",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=C["red"], anchor="w")
        self._lbl_total_debt.grid(row=1, column=0, sticky="w", padx=(18, 8), pady=(0, 8))

        tk.Frame(card, width=1, bg=C["border"]).grid(row=0, column=1, rowspan=2, sticky="ns", pady=8)

        ctk.CTkLabel(card, text="Monthly Payments",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=2, sticky="w", padx=(18, 8), pady=(8, 0))
        self._lbl_total_pmt = ctk.CTkLabel(card, text="—",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=C["yellow"], anchor="w")
        self._lbl_total_pmt.grid(row=1, column=2, sticky="w", padx=(18, 8), pady=(0, 8))

        tk.Frame(card, width=1, bg=C["border"]).grid(row=0, column=3, rowspan=2, sticky="ns", pady=8)

        ctk.CTkLabel(card, text="Years Until Debt Free",
                     font=ctk.CTkFont(size=12), text_color=C["muted"],
                     anchor="w").grid(row=0, column=4, sticky="w", padx=(18, 8), pady=(8, 0))
        self._lbl_total_years = ctk.CTkLabel(card, text="—",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=C["teal"], anchor="w")
        self._lbl_total_years.grid(row=1, column=4, sticky="w", padx=(18, 8), pady=(0, 8))

    # ── Chart panel ───────────────────────────────────────────────────────────

    def _build_metrics_panel(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10,
                            border_width=1, border_color=C["border"])
        card.pack(side="left", fill="both", expand=True)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        def _hdr(text):
            ctk.CTkLabel(content, text=text,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=C["muted"], anchor="w").pack(
                fill="x", pady=(5, 2))

        def _tile_row(keys_labels, sub_key=None):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x")
            n = len(keys_labels)
            for i, (key, period_label) in enumerate(keys_labels):
                tile = ctk.CTkFrame(row, fg_color=C["bg"], corner_radius=6,
                                    border_width=1, border_color=C["border"])
                tile.pack(side="left", fill="x", expand=True,
                          padx=(0, 5) if i < n - 1 else 0)
                ctk.CTkLabel(tile, text=period_label,
                             font=ctk.CTkFont(size=10),
                             text_color=C["muted"], anchor="w").pack(
                    anchor="w", padx=8, pady=(5, 0))
                val_lbl = ctk.CTkLabel(tile, text="—",
                                       font=ctk.CTkFont(size=15, weight="bold"),
                                       text_color=C["muted"], anchor="w")
                val_lbl.pack(anchor="w", padx=8, pady=(1, 0))
                self._metric_vals[key] = val_lbl
                # Sub-line only on rows that need one; keeps tile heights uniform within the row
                if sub_key is not None:
                    sub_lbl = ctk.CTkLabel(tile, text="",
                                           font=ctk.CTkFont(size=10),
                                           text_color=C["muted"], anchor="w")
                    sub_lbl.pack(anchor="w", padx=8, pady=(0, 5))
                    if key == sub_key:
                        self._metric_vals[f"{key}_sub"] = sub_lbl
                else:
                    ctk.CTkFrame(tile, height=5, fg_color="transparent").pack()

        _hdr("NET WORTH CHANGE")
        _tile_row([("nw_1w", "1 Week"), ("nw_1m", "1 Month"), ("nw_3m", "3 Months"),
                   ("nw_6m", "6 Months"), ("nw_1y", "1 Year")])
        _hdr("DEBT CHANGE")
        _tile_row([("debt_1w", "1 Week"), ("debt_1m", "1 Month"), ("debt_3m", "3 Months"),
                   ("debt_6m", "6 Months"), ("debt_1y", "1 Year")])
        _hdr("SPENDING")
        _tile_row([("spend_7d", "Past 7 Days"), ("spend_14d", "Past 14 Days"),
                   ("spend_30d", "Past 30 Days"), ("spend_mtd", "This Month MTD")],
                  sub_key="spend_mtd")
        _hdr("CASH FLOW")
        _tile_row([("cf_this", "This Month"), ("cf_last", "Last Month")])

    # ── Account list ──────────────────────────────────────────────────────────

    def _build_account_list(self, parent):
        container = tk.Frame(parent, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=12, pady=8)

        style = ttk.Style()
        style.configure("Acct.Treeview",
                        background="#fefce8", foreground="#1c1917",
                        fieldbackground="#fefce8", rowheight=26,
                        font=("Consolas", 11))
        style.configure("Acct.Treeview.Heading",
                        background="#fef08a", foreground="#713f12",
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Acct.Treeview",
                  background=[("selected", "#854d0e")],
                  foreground=[("selected", "#ffffff")])

        vsb = ttk.Scrollbar(container, orient="vertical")
        vsb.pack(side="right", fill="y")

        self._tree = ttk.Treeview(
            container, style="Acct.Treeview",
            columns=("name", "balance", "updated", "rate", "monthly_pmt", "payoff", "days_left"),
            show="headings", yscrollcommand=vsb.set,
        )
        vsb.configure(command=self._tree.yview)

        self._tree.heading("name",        text="Account")
        self._tree.heading("balance",     text="Balance")
        self._tree.heading("updated",     text="Last Updated")
        self._tree.heading("rate",        text="Rate")
        self._tree.heading("monthly_pmt", text="Monthly Pmt")
        self._tree.heading("payoff",      text="Payoff Date")
        self._tree.heading("days_left",   text="Days Left")
        self._tree.column("name",        width=260, minwidth=120, anchor="w")
        self._tree.column("balance",     width=120, minwidth=80,  anchor="e")
        self._tree.column("updated",     width=110, minwidth=80,  anchor="w")
        self._tree.column("rate",        width=65,  minwidth=40,  anchor="e")
        self._tree.column("monthly_pmt", width=100, minwidth=60,  anchor="e")
        self._tree.column("payoff",      width=100, minwidth=70,  anchor="center")
        self._tree.column("days_left",   width=75,  minwidth=50,  anchor="e")
        self._tree.pack(fill="both", expand=True)

        self._tree.tag_configure("category", background="#fde68a",
                                 foreground="#78350f",
                                 font=("Helvetica", 11, "bold"))
        self._tree.tag_configure("account",  background="#fefce8", foreground="#1c1917")
        self._tree.tag_configure("inactive", background="#fefce8", foreground="#a8a29e")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda e: self._on_log())
        self._tree.bind("<ButtonRelease-1>", self._on_tree_click)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        db.sync_register_account(DB_PATH)
        self._accounts    = db.get_accounts(DB_PATH)
        self._nw_history  = db.get_nw_history(DB_PATH)
        self._nw_settings = db.get_nw_settings(DB_PATH)
        self._metrics = calc.compute_nw_metrics(
            self._nw_history,
            self._nw_settings["nw_start_date"],
            self._nw_settings["cash_goal"],
        ) if self._nw_history else None
        self._debt_metrics = calc.compute_debt_summary(self._accounts)

        period_changes = calc.compute_nw_period_changes(self._nw_history)
        txns           = db.get_register_cashflow_data(DB_PATH)
        spending_m     = calc.compute_spending_metrics(txns)

        self._refresh_summary()
        self._refresh_debt_summary()
        self._refresh_tree()
        self._refresh_metrics_panel(period_changes, spending_m)

    def _refresh_summary(self):
        m = self._metrics
        if not m:
            self._nw_label.configure(text="No data yet")
            self._status_label.configure(text="Add accounts and log balances to get started")
            for attr in ("_nw_css_label", "_nw_lc_label", "_assets_css_label", "_debt_css_label"):
                getattr(self, attr).configure(text="—")
            self._cash_goal_bar.set(0)
            self._debt_goal_bar.set(0)
            self._cash_goal_lbl.configure(text="—")
            self._debt_goal_lbl.configure(text="—")
            return

        def _fmt(v):
            sign = "+" if v >= 0 else ""
            return f"{sign}${v:,.2f}"

        def _color(v):
            return C["green"] if v >= 0 else C["red"]

        self._nw_label.configure(text=f"${m['net_worth']:,.2f}",
                                 text_color=C["green"] if m["net_worth"] >= 0 else C["red"])
        status = "✅ Ok" if m["nw_css_ok"] else "⚠️ Behind"
        self._status_label.configure(text=f"Day {m['day_no']} · {status}")

        self._nw_css_label.configure(text=_fmt(m["nw_css"]),       text_color=_color(m["nw_css"]))
        self._nw_lc_label.configure(text=_fmt(m["nw_lc"]),         text_color=_color(m["nw_lc"]))
        self._assets_css_label.configure(text=_fmt(m["assets_css"]),text_color=_color(m["assets_css"]))
        self._debt_css_label.configure(text=_fmt(m["debt_css"]),    text_color=_color(m["debt_css"]))

        self._cash_goal_bar.set(m["cash_goal_pct"])
        self._cash_goal_lbl.configure(text=f"{m['cash_goal_pct']*100:.0f}%")
        self._debt_goal_bar.set(max(0, min(1, 1 - m["debt_goal_pct"])))
        debt_reduced = (1 - m["debt_goal_pct"]) * 100 if m.get("bad_debt", 0) != 0 else 0
        self._debt_goal_lbl.configure(text=f"{max(0, debt_reduced):.0f}% reduced")

    def _refresh_debt_summary(self):
        d = self._debt_metrics or {}
        total_debt = d.get("total_debt", 0)
        self._lbl_total_debt.configure(
            text=_fmt(total_debt) if total_debt else "—",
            text_color=C["green"] if total_debt == 0 else C["red"])
        total_pmt = d.get("total_monthly_pmt", 0)
        self._lbl_total_pmt.configure(
            text=_fmt(total_pmt) if total_pmt else "—")
        self._lbl_total_years.configure(text=d.get("years_until_free", "—"))

    def _refresh_tree(self):
        self._tree.delete(*self._tree.get_children())
        by_cat = {c: [] for c in ACCT_CATEGORIES}
        for a in self._accounts:
            cat = a.get("category", "Cash")
            if cat in by_cat:
                by_cat[cat].append(a)

        for cat in ACCT_CATEGORIES:
            accts = by_cat[cat]
            total = sum(
                a["latest_balance"] for a in accts
                if a["latest_balance"] is not None and a.get("active", 1)
            )
            is_open = self._cat_open.get(cat, True)
            arrow = "▼" if is_open else "▶"
            cat_iid = f"cat_{cat}"
            self._tree.insert("", "end", iid=cat_iid,
                              values=(f"{arrow} {cat}", f"${total:,.2f}", "", "", "", "", ""),
                              tags=("category",), open=is_open)
            for a in accts:
                bal = a["latest_balance"]
                bal_str = f"${bal:,.2f}" if bal is not None else "—"
                date_str = a["latest_date"] or "—"
                tag = "account" if a.get("active", 1) else "inactive"
                name_str = f"  {a['name']}"
                if a.get("register_linked"):
                    name_str += " ⇢ Register"
                rate_str = pmt_str = payoff_str = days_str = ""
                if a.get("debt_id") and cat in ("Credit Cards", "Loans"):
                    rate = a.get("debt_interest_rate")
                    pmt  = a.get("debt_monthly_payment")
                    pd   = a.get("debt_payoff_date") or ""
                    rate_str   = f"{rate:.2f}%" if rate is not None else ""
                    pmt_str    = _fmt(pmt) if pmt else ""
                    payoff_str = pd or ""
                    days_str   = _days_until_payoff(pd)
                self._tree.insert(cat_iid, "end", iid=str(a["id"]),
                                  values=(name_str, bal_str, date_str,
                                          rate_str, pmt_str, payoff_str, days_str),
                                  tags=(tag,))

    # ── Charts ────────────────────────────────────────────────────────────────

    def _refresh_metrics_panel(self, period_changes, spending_m):
        def _set(key, text, color):
            lbl = self._metric_vals.get(key)
            if lbl:
                lbl.configure(text=text, text_color=color)

        def _fmt_delta(val, good_positive=True):
            if val is None:
                return "—", C["muted"]
            if val == 0:
                return "$0.00", C["muted"]
            prefix = "+" if val > 0 else "-"
            color = C["green"] if (val > 0) == good_positive else C["red"]
            return f"{prefix}${abs(val):,.2f}", color

        for p in ("1w", "1m", "3m", "6m", "1y"):
            txt, col = _fmt_delta(period_changes.get(f"nw_{p}"),   good_positive=True)
            _set(f"nw_{p}", txt, col)
            txt, col = _fmt_delta(period_changes.get(f"debt_{p}"), good_positive=False)
            _set(f"debt_{p}", txt, col)

        _set("spend_7d",  _fmt(spending_m.get("spending_7d",  0)), C["text"])
        _set("spend_14d", _fmt(spending_m.get("spending_14d", 0)), C["text"])
        _set("spend_30d", _fmt(spending_m.get("spending_30d", 0)), C["text"])
        _set("spend_mtd", _fmt(spending_m.get("spending_mtd", 0)), C["text"])
        mtd_delta = spending_m.get("spending_mtd", 0) - spending_m.get("spending_mtd_last", 0)
        arrow = "▲" if mtd_delta > 0 else "▼"
        sub_color = C["red"] if mtd_delta > 0 else C["green"]
        _set("spend_mtd_sub",
             f"{arrow} ${abs(mtd_delta):,.2f} vs {spending_m.get('last_month_name', 'prev')}",
             sub_color)

        txt, col = _fmt_delta(spending_m.get("cashflow_this", 0), good_positive=True)
        _set("cf_this", txt, col)
        txt, col = _fmt_delta(spending_m.get("cashflow_last", 0), good_positive=True)
        _set("cf_last", txt, col)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            self._selected_id = None
        else:
            iid = sel[0]
            if iid.startswith("cat_"):
                self._selected_id = None
                self._tree.selection_remove(iid)
            else:
                try:
                    self._selected_id = int(iid)
                except ValueError:
                    self._selected_id = None

        acct = self._selected_account()
        if acct and acct.get("register_linked"):
            self._log_btn.configure(state="disabled", text="📈 Log Balance",
                                    fg_color=C["border"], text_color=C["muted"])
        else:
            self._log_btn.configure(state="normal", text="📈 Log Balance",
                                    fg_color=C["border"], text_color=C["text"])

    def _on_tree_click(self, event):
        iid = self._tree.identify_row(event.y)
        if iid and iid.startswith("cat_"):
            cat = iid[4:]
            self._cat_open[cat] = not self._cat_open.get(cat, True)
            prev_sel = self._selected_id
            self._refresh_tree()
            if prev_sel and self._tree.exists(str(prev_sel)):
                self._tree.selection_set(str(prev_sel))

    def _selected_account(self):
        if self._selected_id is None:
            return None
        return next((a for a in self._accounts if a["id"] == self._selected_id), None)

    def _on_add(self):
        AccountDialog(self, None, self._on_account_saved)

    def _on_edit(self):
        acct = self._selected_account()
        if not acct:
            return
        AccountDialog(self, acct, self._on_account_saved)

    def _on_delete(self):
        acct = self._selected_account()
        if not acct:
            return
        msg = f"Delete '{acct['name']}' and all its balance history?"
        if acct.get("debt_id") and acct.get("category") in ("Credit Cards", "Loans"):
            msg += "\nThis will also remove the linked debt record and all monthly balances."
        ConfirmDialog(self,
            title="Delete Account",
            message=msg,
            on_confirm=lambda: self._do_delete(acct["id"]))

    def _do_delete(self, account_id):
        db.delete_account(account_id, DB_PATH)
        self.refresh()

    def _on_log(self):
        acct = self._selected_account()
        if not acct:
            return
        if acct.get("register_linked"):
            return
        LogBalanceDialog(self, acct, self._on_balance_saved)

    def _on_account_saved(self, account_id, data):
        if account_id:
            db.update_account(account_id, data, DB_PATH)
        else:
            new_id = db.insert_account(data, DB_PATH)
            if data.get("start_bal") is not None and data.get("start_date"):
                db.log_account_balance(new_id, data["start_date"], data["start_bal"], DB_PATH)
        self.refresh()

    def _on_balance_saved(self, account_id, entry_date, balance):
        db.log_account_balance(account_id, entry_date, balance, DB_PATH)
        self.refresh()

    def _on_settings(self):
        NWSettingsDialog(self, self._nw_settings, self._on_settings_saved)

    def _on_settings_saved(self, settings):
        db.set_nw_settings(settings, DB_PATH)
        self.refresh()

    def configure_initial_sash(self, sash_y, summary_visible):
        self._initial_sash_y = sash_y
        self._initial_summary_visible = summary_visible

    def get_sash_position(self):
        if not self._summary_visible:
            return self._saved_sash_y
        try:
            return self._paned.sash_coord(0)[1]
        except Exception:
            return None

    def set_sash_position(self, y):
        if y is not None and y > 0:
            self._paned.sash_place(0, 1, y)

    def _set_initial_sash(self):
        total = self._paned.winfo_height()
        if total < 100:
            return
        target_y = self._initial_sash_y if self._initial_sash_y is not None else total // 2
        if not self._initial_summary_visible:
            self._saved_sash_y = target_y
            self._paned.sash_place(0, 1, 0)
            self._summary_visible = False
            self._toggle_btn.configure(text="▼ Show Summary")
        else:
            self._paned.sash_place(0, 1, target_y)

    def _toggle_summary(self):
        if self._summary_visible:
            try:
                self._saved_sash_y = self._paned.sash_coord(0)[1]
            except Exception:
                self._saved_sash_y = None
            self._paned.sash_place(0, 1, 0)
            self._toggle_btn.configure(text="▼ Show Summary")
        else:
            pos = self._saved_sash_y or (self._paned.winfo_height() // 2)
            self._paned.sash_place(0, 1, pos)
            self._toggle_btn.configure(text="▲ Hide Summary")
        self._summary_visible = not self._summary_visible


# ── Account dialogs ───────────────────────────────────────────────────────────

class AccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, account, on_save):
        super().__init__(parent)
        self._account = account
        self._on_save = on_save
        self.title("Edit Account" if account else "Add Account")
        self.resizable(False, False)
        self.geometry("380x340")
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        pad = {"padx": 16, "pady": 6}

        ctk.CTkLabel(self, text="Name", anchor="w").pack(fill="x", **pad)
        self._name = ctk.CTkEntry(self, width=320)
        self._name.pack(fill="x", padx=16, pady=(0, 6))
        if account:
            self._name.insert(0, account.get("name", ""))

        ctk.CTkLabel(self, text="Category", anchor="w").pack(fill="x", **pad)
        self._category = ctk.CTkOptionMenu(self, values=ACCT_CATEGORIES,
                                           command=self._on_category_change)
        self._category.pack(fill="x", padx=16, pady=(0, 6))
        if account:
            self._category.set(account.get("category", "Cash"))

        # Middle container keeps pack order stable when debt/register frames swap
        self._mid = ctk.CTkFrame(self, fg_color="transparent")
        self._mid.pack(fill="x")

        # Debt detail fields (Credit Cards / Loans only)
        self._debt_frame = ctk.CTkFrame(self._mid, fg_color="transparent")
        tk.Frame(self._debt_frame, height=1, bg=C["border"]).pack(fill="x", padx=0, pady=(0, 4))
        for label_text, attr in [
            ("Interest Rate %", "_debt_rate"),
            ("Monthly Payment", "_debt_pmt"),
            ("Payoff Date (MM/DD/YYYY)", "_debt_payoff"),
        ]:
            row = ctk.CTkFrame(self._debt_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(2, 0))
            ctk.CTkLabel(row, text=label_text, width=190, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=140)
            entry.pack(side="left")
            setattr(self, attr, entry)
        if account and account.get("debt_id"):
            self._debt_rate.insert(0, str(account.get("debt_interest_rate") or ""))
            self._debt_pmt.insert(0, str(account.get("debt_monthly_payment") or ""))
            self._debt_payoff.insert(0, account.get("debt_payoff_date") or "")

        # Register link (Cash only)
        self._register_frame = ctk.CTkFrame(self._mid, fg_color="transparent")
        self._register_var = ctk.BooleanVar(
            value=bool(account.get("register_linked")) if account else False
        )
        ctk.CTkCheckBox(self._register_frame,
                        text="Auto-sync balance from Register tab",
                        variable=self._register_var).pack(anchor="w", padx=16, pady=(0, 4))

        self._active_var = ctk.BooleanVar(value=account.get("active", 1) if account else True)
        ctk.CTkCheckBox(self, text="Active", variable=self._active_var).pack(
            anchor="w", padx=16, pady=6)

        # Starting balance — new accounts only
        if not account:
            from datetime import date as _date
            tk.Frame(self, height=1, bg=C["border"]).pack(fill="x", padx=16, pady=(4, 0))
            ctk.CTkLabel(self, text="Starting Balance (optional)", anchor="w").pack(
                fill="x", padx=16, pady=(6, 0))
            bal_row = ctk.CTkFrame(self, fg_color="transparent")
            bal_row.pack(fill="x", padx=16, pady=(2, 0))
            self._start_bal = ctk.CTkEntry(bal_row, width=140, placeholder_text="e.g. 1500.00")
            self._start_bal.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(bal_row, text="as of", text_color=C["muted"]).pack(side="left", padx=(0, 6))
            self._start_date = ctk.CTkEntry(bal_row, width=110)
            self._start_date.insert(0, _date.today().strftime("%m/%d/%Y"))
            self._start_date.pack(side="left")
        else:
            self._start_bal  = None
            self._start_date = None

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 12))
        ctk.CTkButton(btn_row, text="Save", width=80,
                      command=self._save).pack(side="left", padx=(0, 6))
        if not account:
            ctk.CTkButton(btn_row, text="Save & Add Another", width=150,
                          fg_color=C["blue"], hover_color=C["heading"],
                          text_color="#ffffff",
                          command=self._save_and_add).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Cancel", width=80,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"],
                      command=self.destroy).pack(side="left")

        self._on_category_change(self._category.get())
        self.after(150, self._name.focus_set)

    def _on_category_change(self, cat):
        self._debt_frame.pack_forget()
        self._register_frame.pack_forget()
        if cat in ("Credit Cards", "Loans"):
            self._debt_frame.pack(fill="x", in_=self._mid)
            h = "440" if not self._account else "400"
        elif cat == "Cash":
            self._register_frame.pack(fill="x", in_=self._mid)
            h = "340" if not self._account else "310"
        else:
            h = "310" if not self._account else "280"
        self.geometry(f"380x{h}")

    def _build_data(self):
        name = self._name.get().strip()
        if not name:
            return None
        cat = self._category.get()
        register_linked = (cat == "Cash" and self._register_var.get())
        start_bal  = None
        start_date = None
        if self._start_bal is not None:
            raw = self._start_bal.get().strip().replace(",", "")
            if raw:
                try:
                    start_bal  = float(raw)
                    start_date = self._start_date.get().strip() or None
                except ValueError:
                    pass
        # Debt fields — only when CC/Loans
        debt_data = None
        if cat in ("Credit Cards", "Loans"):
            try:
                rate = float(self._debt_rate.get().replace("%", "").strip() or "0")
            except ValueError:
                rate = 0.0
            try:
                pmt = float(self._debt_pmt.get().replace("$", "").replace(",", "").strip() or "0")
            except ValueError:
                pmt = 0.0
            payoff = self._debt_payoff.get().strip()
            if rate or pmt or payoff:
                debt_data = {"name": name, "interest_rate": rate,
                             "monthly_payment": pmt, "payoff_date": payoff, "notes": ""}
        return {
            "name":            name,
            "category":        cat,
            "active":          1 if self._active_var.get() else 0,
            "register_linked": 1 if register_linked else 0,
            "start_bal":       start_bal,
            "start_date":      start_date,
            "_debt_data":      debt_data,
        }

    def _commit(self, data):
        """Resolve debt_id (create/update debt record) then call on_save."""
        account_id = self._account["id"] if self._account else None
        debt_data = data.pop("_debt_data", None)
        existing_debt_id = self._account.get("debt_id") if self._account else None

        if debt_data:
            if existing_debt_id:
                db.update_debt(existing_debt_id, debt_data, DB_PATH)
                data["debt_id"] = existing_debt_id
            else:
                new_debt_id = db.insert_debt(debt_data, DB_PATH)
                data["debt_id"] = new_debt_id
        else:
            data["debt_id"] = existing_debt_id

        self._on_save(account_id, data)

    def _save(self):
        data = self._build_data()
        if data is None:
            return
        self._commit(data)
        self.destroy()

    def _save_and_add(self):
        data = self._build_data()
        if data is None:
            return
        self._commit(data)
        self._name.delete(0, "end")
        self._start_bal.delete(0, "end")
        self._register_var.set(False)
        self._active_var.set(True)
        self._debt_rate.delete(0, "end")
        self._debt_pmt.delete(0, "end")
        self._debt_payoff.delete(0, "end")
        self._name.focus_set()


class LogBalanceDialog(ctk.CTkToplevel):
    def __init__(self, parent, account, on_save):
        super().__init__(parent)
        self._account = account
        self._on_save = on_save
        self.title("Log Balance")
        self.resizable(False, False)
        self.geometry("320x240")
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        from datetime import date as _date
        today = _date.today().strftime("%m/%d/%Y")

        ctk.CTkLabel(self, text=account["name"],
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(self, text=account.get("category", ""),
                     text_color=C["muted"]).pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Date (MM/DD/YYYY)", anchor="w").pack(fill="x", padx=16)
        self._date = ctk.CTkEntry(self, width=200)
        self._date.insert(0, today)
        self._date.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(self, text="Balance", anchor="w").pack(fill="x", padx=16)
        self._balance = ctk.CTkEntry(self, width=200)
        if account.get("latest_balance") is not None:
            self._balance.insert(0, str(account["latest_balance"]))
        self._balance.pack(fill="x", padx=16, pady=(2, 8))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkButton(btn_row, text="Save", width=100,
                      command=self._save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"],
                      command=self.destroy).pack(side="left")

        self.after(150, self._balance.focus_set)

    def _save(self):
        try:
            balance = float(self._balance.get().strip().replace(",", ""))
        except ValueError:
            return
        entry_date = self._date.get().strip()
        if not entry_date:
            return
        self._on_save(self._account["id"], entry_date, balance)
        self.destroy()


class NWSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, settings, on_save):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Net Worth Settings")
        self.resizable(False, False)
        self.geometry("320x170")
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        fields = [
            ("Start Date (MM/DD/YYYY)", "nw_start_date", str(settings.get("nw_start_date", ""))),
            ("Cash Goal ($)",           "cash_goal",      str(settings.get("cash_goal", 0))),
        ]
        self._entries = {}
        for label, key, val in fields:
            ctk.CTkLabel(self, text=label, anchor="w").pack(fill="x", padx=16, pady=(8, 0))
            e = ctk.CTkEntry(self, width=260)
            e.insert(0, val)
            e.pack(fill="x", padx=16, pady=(2, 0))
            self._entries[key] = e

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(12, 12))
        ctk.CTkButton(btn_row, text="Save", width=100,
                      command=self._save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color=C["border"], hover_color=C["card2"],
                      text_color=C["text"],
                      command=self.destroy).pack(side="left")

    def _save(self):
        try:
            data = {
                "nw_start_date": self._entries["nw_start_date"].get().strip(),
                "cash_goal":     float(self._entries["cash_goal"].get().strip() or 0),
            }
        except ValueError:
            return
        self._on_save(data)
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

        _animals = ["🦊","🦁","🦄","🦜","🦚","🦋","🐉","🦝","🐸","🐯","🦈","🦩","🦦","🦔","🦕","🦖"]
        self._animal = random.choice(_animals)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        saved_widths = self._settings.get("column_widths", {})
        if saved_widths:
            self.after(0, lambda: self._dashboard.set_column_widths(saved_widths))
        saved_sash    = self._settings.get("acct_sash_y")
        saved_visible = self._settings.get("acct_summary_visible", True)
        if saved_sash is not None:
            self._accounts_tab.configure_initial_sash(saved_sash, saved_visible)
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
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=C["card2"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        header.columnconfigure(2, weight=1)

        _left = ctk.CTkFrame(header, fg_color="transparent")
        _left.grid(row=0, column=0, sticky="ew", padx=10, pady=4)
        _left.columnconfigure(0, weight=0)
        _left.columnconfigure(1, weight=1)
        ctk.CTkLabel(_left, text="💰", font=ctk.CTkFont(size=36)).grid(row=0, column=0, padx=(8, 0))
        self._header_s2s_label = ctk.CTkLabel(
            _left, text="Safe2Spend: —",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=C["green"],
        )
        self._header_s2s_label.grid(row=0, column=1)

        self._tab_btns = {}
        tab_group = ctk.CTkFrame(header, fg_color="transparent")
        tab_group.grid(row=0, column=1, pady=10)
        _right = ctk.CTkFrame(header, fg_color="transparent")
        _right.grid(row=0, column=2, sticky="e", padx=10, pady=4)
        self._header_nwcss_label = ctk.CTkLabel(
            _right, text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=C["green"])
        self._header_nwcss_label.pack(side="left", padx=(0, 6))
        _Tooltip(self._header_nwcss_label, "NW Change Since Start")
        ctk.CTkLabel(_right, text=self._animal,
                     font=ctk.CTkFont(size=36)).pack(side="left", padx=(0, 8))
        for name in ("Bills", "Bill List", "Register", "Accounts", "Insurance", "Legal"):
            btn = ctk.CTkButton(
                tab_group, text=name, width=90, height=30,
                corner_radius=6,
                fg_color=C["border"], hover_color=C["yellow"],
                text_color=C["text"],
                font=ctk.CTkFont(size=13),
                command=lambda n=name: self._switch_tab(n),
            )
            btn.pack(side="left", padx=4)
            self._tab_btns[name] = btn

        ctk.CTkButton(
            tab_group, text="💾", width=36, height=30,
            corner_radius=6,
            fg_color=C["border"], hover_color=C["card2"],
            font=ctk.CTkFont(size=16),
            command=self._backup_db,
        ).pack(side="left", padx=(12, 0))

        ctk.CTkButton(
            tab_group, text="⬇", width=36, height=30,
            corner_radius=6,
            fg_color=C["border"], hover_color=C["card2"],
            font=ctk.CTkFont(size=16),
            command=self._restore_db,
        ).pack(side="left", padx=(4, 4))

        ctk.CTkButton(
            tab_group, text="📊", width=36, height=30,
            corner_radius=6,
            fg_color=C["border"], hover_color=C["card2"],
            font=ctk.CTkFont(family="Noto Color Emoji", size=16),
            command=lambda: None,
        ).pack(side="left", padx=(4, 4))

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

        self._defs         = DefinitionsTab(content, self)
        self._reg_tab      = RegisterTab(content, self)
        self._accounts_tab = AccountsTab(content, self)

        def _placeholder(label):
            f = ctk.CTkFrame(content, fg_color=C["bg"], corner_radius=0)
            nav = ctk.CTkFrame(f, height=42, corner_radius=0, fg_color=C["card"])
            nav.pack(fill="x")
            nav.pack_propagate(False)
            ctk.CTkLabel(nav, text=self._animal, fg_color="transparent",
                         font=ctk.CTkFont(size=15)).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=22),
                         text_color=C["muted"]).place(relx=0.5, rely=0.5, anchor="center")
            return f
        self._insurance_tab = _placeholder("Insurance — coming soon")
        self._legal_tab     = _placeholder("Legal — coming soon")

        self._active_tab = "Bills"
        self._update_tab_btn_styles()

    def _switch_tab(self, name):
        if name == self._active_tab:
            return
        self._active_tab = name
        for frame in (self._dashboard, self._defs, self._reg_tab,
                      self._accounts_tab, self._insurance_tab, self._legal_tab):
            frame.pack_forget()
        tab_map = {
            "Bills":     self._dashboard,
            "Bill List": self._defs,
            "Register":  self._reg_tab,
            "Accounts":  self._accounts_tab,
            "Insurance": self._insurance_tab,
            "Legal":     self._legal_tab,
        }
        tab_map[name].pack(fill="both", expand=True)
        self._update_tab_btn_styles()

    def _update_tab_btn_styles(self):
        for name, btn in self._tab_btns.items():
            if name == self._active_tab:
                btn.configure(fg_color=C["blue"], text_color="#ffffff")
            else:
                btn.configure(fg_color=C["card2"], text_color=C["muted"])

    def refresh(self):
        annotated, summary = _load_and_annotate(self._current_month)
        definitions        = db.load_definitions(DB_PATH)
        transactions       = db.load_transactions(DB_PATH)
        acct_settings      = db.get_account_settings(DB_PATH)
        self._dashboard.refresh(annotated, summary, self._current_month)
        self._defs.refresh(definitions)
        self._reg_tab.refresh(transactions, acct_settings)
        self._accounts_tab.refresh()
        self._update_header_nwcss()
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

    def _update_header_nwcss(self):
        m = self._accounts_tab._metrics
        if not m:
            self._header_nwcss_label.configure(text="", text_color=C["green"])
            return
        v = m["nw_css"]
        sign = "+" if v >= 0 else ""
        color = C["green"] if v >= 0 else C["red"]
        self._header_nwcss_label.configure(text=f"{sign}${v:,.2f}", text_color=color)

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
                    "last_month":       self._current_month,
                    "column_widths":    self._dashboard.get_column_widths(),
                    "geometry":         self.geometry(),
                    "acct_sash_y":           self._accounts_tab.get_sash_position(),
                    "acct_summary_visible":  self._accounts_tab._summary_visible,
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

    def _backup_db(self):
        import tarfile
        desktop = os.path.expanduser("~/Desktop")
        ts = date.today().strftime("%Y-%m-%d")
        dest = os.path.join(desktop, f"money-tracker-backup-{ts}.tar.gz")
        try:
            with tarfile.open(dest, "w:gz") as tar:
                tar.add(DB_PATH, arcname=f"money-tracker-backup-{ts}.db")
            self.flash(f"Backup saved to ~/Desktop/money-tracker-backup-{ts}.tar.gz")
        except Exception as e:
            self.flash(f"Backup failed: {e}")

    def _restore_db(self):
        import tarfile
        import tempfile
        import tkinter.messagebox as mb
        import tkinter.filedialog as fd

        confirmed = mb.askyesno(
            "Restore Database",
            "WARNING: This will permanently replace your entire current database "
            "with the selected backup.\n\nAll current data will be lost and cannot "
            "be recovered unless you have another backup.\n\nContinue?",
            icon="warning",
        )
        if not confirmed:
            return

        path = fd.askopenfilename(
            title="Select backup file",
            filetypes=[("Backup archive", "*.tar.gz"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with tarfile.open(path, "r:gz") as tar:
                db_members = [m for m in tar.getmembers() if m.name.endswith(".db")]
                if not db_members:
                    self.flash("Restore failed: no .db file found in archive.")
                    return
                member = db_members[0]
                with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                    tmp_path = tmp.name
                extracted = tar.extractfile(member)
                with open(tmp_path, "wb") as f:
                    f.write(extracted.read())
            os.replace(tmp_path, DB_PATH)
            self.refresh()
            self.flash("Database restored successfully.")
        except Exception as e:
            self.flash(f"Restore failed: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MoneyTrackerApp()
    app.mainloop()
