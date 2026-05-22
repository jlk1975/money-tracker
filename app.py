"""
app.py — Money Tracker main application.
Two tabs: Dashboard (summary + nav + bill grid), Definitions (master bill template list).
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import os
import calendar
from datetime import date

import db
import calc

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DB_PATH = os.path.join(os.path.dirname(__file__), "money_tracker.db")

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

ACCOUNTS    = ["UWBC", "BOAC1", "Sam's Card", "Other"]
STATUSES    = ["Due", "Paid"]
FREQUENCIES = ["Monthly", "AdHoc", "Annual", "Semi-Annual", "Quarterly", "Bi-Weekly", "Weekly"]
MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

ACCOUNT_COLORS = {
    "UWBC":       C["blue"],
    "BOAC1":      C["teal"],
    "Sam's Card": C["purple"],
}

# ── Bills tab grid ────────────────────────────────────────────────────────────
GRID_COLUMNS = [
    ("✓",          40),
    ("Status",     70),
    ("Account",   100),
    ("Expense",   240),
    ("Due Date",   90),
    ("Amount",     90),
    ("Frequency",  90),
    ("Date Paid",  90),
    ("Funded",     70),
]
LEFT_ALIGN = {"Status", "Account", "Expense", "Due Date", "Frequency", "Date Paid"}

# ── Definitions tab grid ──────────────────────────────────────────────────────
DEF_COLUMNS = [
    ("Active",      55),
    ("Account",    100),
    ("Description",230),
    ("Frequency",  100),
    ("Typical $",   90),
    ("Due Day",     65),
    ("Due In",     150),
    ("Notes",      150),
]
DEF_LEFT_ALIGN = {"Account", "Description", "Frequency", "Due In", "Notes"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val):
    if val is None:
        return ""
    if val == 0.0:
        return "$0.00"
    sign = "-" if val < 0 else ""
    return f"{sign}${abs(val):,.2f}"


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
        "✓" if inst.get("status") == "Paid" else "",
        inst.get("status", ""),
        inst.get("account", ""),
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
        "✓" if defn.get("active") else "✗",
        defn.get("account", ""),
        defn.get("description", ""),
        defn.get("frequency", ""),
        _fmt(defn.get("typical_amount")),
        str(defn.get("due_day", "")),
        _format_due_in(defn),
        defn.get("notes", ""),
    )


# ── KPI / Progress Cards ──────────────────────────────────────────────────────

class ProgressCard(ctk.CTkFrame):
    def __init__(self, parent, label, progress, sub=None, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=12),
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        bar = ctk.CTkProgressBar(self, progress_color=C["green"],
                                  fg_color=C["border"])
        bar.set(max(0.0, min(1.0, progress)))
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        ctk.CTkLabel(self, text=sub or "", font=ctk.CTkFont(size=11),
                     text_color=C["muted"], anchor="w").grid(
            row=2, column=0, sticky="ew", padx=14, pady=(0, 10))


class KPICard(ctk.CTkFrame):
    def __init__(self, parent, label, value_str, value_color=None, sub=None, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=12),
                     text_color=C["muted"], anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
        ctk.CTkLabel(self, text=value_str,
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=value_color or C["text"], anchor="w").grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 2))
        ctk.CTkLabel(self, text=sub or "", font=ctk.CTkFont(size=11),
                     text_color=C["muted"], anchor="w").grid(
            row=2, column=0, sticky="ew", padx=14, pady=(0, 10))



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

        self._metrics_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._metrics_panel.pack(fill="x")

        self._toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=C["card2"])
        self._toolbar.pack(fill="x")
        self._toolbar.pack_propagate(False)
        for label, cmd, width in [
            ("+ Add Bill",              self._add,                    128),
            ("✎ Edit",                  self._edit,                   128),
            ("✗ Mark Not Funded",       self._mark_not_funded,        128),
            ("✓ Mark Funded",           self._mark_funded,            128),
            ("✗ Mark Unpaid",           self._mark_unpaid,            128),
            ("✓ Mark Paid",             self._mark_paid,              128),
            ("🗑 Delete",               self._delete,                 128),
            ("All Paid/Unpaid",    self._mark_all_paid_unpaid,   128),
            ("All Funded/Unfunded",self._mark_all_funded_unfunded,145),
        ]:
            ctk.CTkButton(self._toolbar, text=label, width=width, height=30,
                          command=cmd).pack(side="right", padx=6, pady=7)

        self._tree_container = tk.Frame(self, bg="#1a1a2e")
        self._tree_container.pack(fill="both", expand=True)

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

    def refresh(self, annotated, summary, month_key):
        year, month = map(int, month_key.split("-"))
        self._month_lbl.configure(text=f"{calendar.month_name[month]} {year}")
        self._left_btn.configure(
            state="normal" if self._app.can_navigate_left() else "disabled")
        self._right_btn.configure(
            state="normal" if self._app.can_navigate_right() else "disabled")

        for w in self._metrics_panel.winfo_children():
            w.destroy()

        if annotated:
            pad = {"padx": 18, "pady": 8}

            row1 = ctk.CTkFrame(self._metrics_panel, fg_color="transparent")
            row1.pack(fill="x", **pad)
            for col in range(4):
                row1.grid_columnconfigure(col, weight=1, uniform="k1")
            row1.grid_rowconfigure(0, weight=1)

            KPICard(row1, "Total Bills",
                    str(summary.get("bill_count", 0)), C["blue"]).grid(
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
            KPICard(row1, "Due",
                    _fmt(summary.get("total_due", 0)), C["red"],
                    sub="Unpaid balance").grid(
                row=0, column=3, sticky="nsew", padx=(6, 0), pady=4)

            row2 = ctk.CTkFrame(self._metrics_panel, fg_color="transparent")
            row2.pack(fill="x", **pad)
            for col in range(4):
                row2.grid_columnconfigure(col, weight=1, uniform="k2")
            row2.grid_rowconfigure(0, weight=1)

            _funded_not_paid = sum(b.get("amount", 0) for b in annotated
                                   if b.get("funded") and b.get("status") != "Paid")
            KPICard(row2, "Funded Not Paid (YNAB)", _fmt(_funded_not_paid), C["yellow"]).grid(
                row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
            _funded_total = sum(b.get("amount", 0) for b in annotated if b.get("funded"))
            _funded_total2  = sum(b.get("amount", 0) for b in annotated if b.get("funded"))
            _total2         = sum(b.get("amount", 0) for b in annotated)
            _fpct           = (_funded_total2 / _total2) if _total2 else 0
            ProgressCard(row2, "Funding Progress", _fpct,
                         sub=f"{_fpct*100:.0f}%  —  {_fmt(_funded_total2)} of {_fmt(_total2)}").grid(
                row=0, column=1, sticky="nsew", padx=6, pady=4)
            KPICard(row2, "Funded", _fmt(_funded_total), C["green"]).grid(
                row=0, column=2, sticky="nsew", padx=6, pady=4)
            _not_funded_total = sum(b.get("amount", 0) for b in annotated if not b.get("funded"))
            KPICard(row2, "Not Funded", _fmt(_not_funded_total), C["red"]).grid(
                row=0, column=3, sticky="nsew", padx=(6, 0), pady=4)


        self._tree.delete(*self._tree.get_children())
        self._selected_id = None
        for inst in annotated:
            self._tree.insert("", "end", iid=str(inst["id"]),
                              values=_merge_row(inst), tags=(_inst_tag(inst),))
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
        for col, _ in GRID_COLUMNS:
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

    def _mark_paid(self):
        if not self._selected_id:
            self._app.flash("Select a bill to mark as paid.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if inst.get("status") == "Paid":
            self._app.flash("Bill is already marked paid.")
            return
        if not inst.get("funded"):
            self._app.flash("Bill must be funded before it can be marked paid.")
            return
        updated = dict(inst)
        updated["status"]    = "Paid"
        updated["date_paid"] = date.today().strftime("%m/%d/%Y")
        db.update_instance(self._selected_id, updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked paid: {inst.get('description', '')[:40]}")

    def _mark_unpaid(self):
        if not self._selected_id:
            self._app.flash("Select a bill to mark as unpaid.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if inst.get("status") == "Due":
            self._app.flash("Bill is already unpaid.")
            return
        updated = dict(inst)
        updated["status"]    = "Due"
        updated["date_paid"] = ""
        db.update_instance(self._selected_id, updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked unpaid: {inst.get('description', '')[:40]}")

    def _mark_funded(self):
        if not self._selected_id:
            self._app.flash("Select a bill to mark as funded.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if inst.get("funded"):
            self._app.flash("Bill is already funded.")
            return
        updated = dict(inst)
        updated["funded"] = 1
        db.update_instance(self._selected_id, updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked funded: {inst.get('description', '')[:40]}")

    def _mark_not_funded(self):
        if not self._selected_id:
            self._app.flash("Select a bill to mark as not funded.")
            return
        annotated, _ = _load_and_annotate(self._app.current_month())
        inst = next((b for b in annotated if b["id"] == self._selected_id), None)
        if not inst:
            return
        if not inst.get("funded"):
            self._app.flash("Bill is already not funded.")
            return
        updated = dict(inst)
        updated["funded"] = 0
        db.update_instance(self._selected_id, updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"Marked not funded: {inst.get('description', '')[:40]}")

    def _delete(self):
        if not self._selected_id:
            self._app.flash("Select a bill to delete.")
            return
        ConfirmDialog(self, self._app,
                      "Delete this bill from this month?\nThis cannot be undone.",
                      lambda: (db.delete_instance(self._selected_id, DB_PATH),
                               self._app.refresh()))

    def _mark_all_funded_unfunded(self):
        annotated, _ = _load_and_annotate(self._app.current_month())
        if not annotated:
            self._app.flash("No bills to update.")
            return
        all_funded = all(b.get("funded") for b in annotated)
        new_val = 0 if all_funded else 1
        for inst in annotated:
            updated = dict(inst)
            updated["funded"] = new_val
            db.update_instance(inst["id"], updated, DB_PATH)
        self._app.refresh()
        self._app.flash(f"All bills marked {'unfunded' if all_funded else 'funded'}.")

    def _mark_all_paid_unpaid(self):
        annotated, _ = _load_and_annotate(self._app.current_month())
        if not annotated:
            self._app.flash("No bills to update.")
            return
        all_paid = all(b.get("status") == "Paid" for b in annotated)
        if not all_paid and not all(b.get("funded") for b in annotated):
            self._app.flash("All bills must be funded before marking all as paid.")
            return
        new_status = "Due" if all_paid else "Paid"
        new_date   = date.today().strftime("%m/%d/%Y") if new_status == "Paid" else ""
        for inst in annotated:
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
        self.geometry("440x570")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}
        fields = [
            ("Account",   "combo", inst["account"]     if inst else ACCOUNTS[0]),
            ("Expense",   "entry", inst["description"] if inst else ""),
            ("Status",    "combo", inst["status"]      if inst else STATUSES[0]),
            ("Due Date",  "entry", inst["due_date"]    if inst else ""),
            ("Amount",    "entry", str(inst["amount"]) if inst else ""),
            ("Frequency", "combo", inst["frequency"]   if inst else FREQUENCIES[0]),
            ("Date Paid", "entry", inst["date_paid"]   if inst else ""),
            ("Notes",     "entry", inst["notes"]       if inst else ""),
        ]
        for label, kind, default in fields:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            if kind == "entry":
                ctk.CTkEntry(row, textvariable=var, width=260).pack(side="left")
            else:
                choices = (ACCOUNTS if label == "Account"
                           else STATUSES if label == "Status"
                           else FREQUENCIES)
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

        data = {
            "month_key":   self._month_key,
            "account":     self._vars["Account"].get(),
            "description": desc,
            "status":      self._vars["Status"].get(),
            "due_date":    due_date,
            "amount":      amount,
            "frequency":   self._vars["Frequency"].get(),
            "date_paid":   self._vars["Date Paid"].get().strip(),
            "notes":       self._vars["Notes"].get().strip(),
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
        self.geometry("480x600")
        self.resizable(False, False)
        self.after(100, self.grab_set)
        self.after(100, self.focus_set)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=16, pady=(14, 6), anchor="w")

        self._vars = {}

        # Static fields
        for label, kind, default in [
            ("Account",    "combo", defn["account"]         if defn else ACCOUNTS[0]),
            ("Description","entry", defn["description"]     if defn else ""),
            ("Typical $",  "entry", str(defn["typical_amount"]) if defn else ""),
            ("Due Day",    "entry", str(defn["due_day"])    if defn else "1"),
        ]:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=5)
            ctk.CTkLabel(row, text=label, width=110, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            if kind == "entry":
                ctk.CTkEntry(row, textvariable=var, width=270).pack(side="left")
            else:
                ctk.CTkOptionMenu(row, values=ACCOUNTS, variable=var,
                                  width=270).pack(side="left")
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
        self._due_in_label.configure(text=label or "Due In")
        if disabled:
            self._due_in_var.set("")
            self._due_in_entry.configure(state="disabled")
        else:
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

        data = {
            "account":        self._vars["Account"].get(),
            "description":    desc,
            "frequency":      freq,
            "typical_amount": amount,
            "due_day":        due_day,
            "months_active":  months_a,
            "adhoc_month":    adhoc_m,
            "active":         self._defn["active"] if self._defn else 1,
            "notes":          self._vars["Notes"].get().strip(),
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
        self.title("Money Tracker")
        self.geometry("1300x820")
        self.minsize(960, 620)

        db.init_db(DB_PATH)

        today = date.today()
        self._current_month = f"{today.year:04d}-{today.month:02d}"
        db.generate_month_instances(self._current_month, DB_PATH)

        self._build_ui()
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

    def _build_ui(self):
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#1a1a2e")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="Money Tracker",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=C["heading"]).pack(side="left", padx=18, pady=10)

        self._status_var = tk.StringVar(value="Loading…")
        status_bar = ctk.CTkFrame(self, height=26, corner_radius=0,
                                  fg_color=("gray85", "gray20"))
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        ctk.CTkLabel(status_bar, textvariable=self._status_var,
                     font=ctk.CTkFont(size=11), anchor="w",
                     text_color=C["muted"]).pack(side="left", padx=12)

        tabs = ctk.CTkTabview(self, corner_radius=6, fg_color=C["bg"],
                              segmented_button_fg_color=C["card2"],
                              segmented_button_selected_color="#3a5a8a",
                              segmented_button_selected_hover_color="#4a6a9a",
                              segmented_button_unselected_color=C["card2"],
                              segmented_button_unselected_hover_color=C["border"])
        tabs.pack(fill="both", expand=True)
        tabs.add("Dashboard")
        tabs.add("Definitions")

        self._dashboard = CombinedDashboard(tabs.tab("Dashboard"), self)
        self._dashboard.pack(fill="both", expand=True)

        self._defs = DefinitionsTab(tabs.tab("Definitions"), self)
        self._defs.pack(fill="both", expand=True)

    def refresh(self):
        annotated, summary = _load_and_annotate(self._current_month)
        definitions        = db.load_definitions(DB_PATH)
        self._dashboard.refresh(annotated, summary, self._current_month)
        self._defs.refresh(definitions)
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

    def flash(self, msg, duration_ms=3000):
        old = self._status_var.get()
        self._status_var.set(msg)
        self.after(duration_ms, lambda: self._status_var.set(old))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MoneyTrackerApp()
    app.mainloop()
