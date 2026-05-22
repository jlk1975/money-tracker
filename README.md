# Bill Tracker

A personal household bill tracker built with Python and customtkinter. Track recurring and one-off bills, manage funding and payment status, and get a monthly dashboard overview.

## Quick start (Linux Mint / Ubuntu)

```bash
git clone https://github.com/jlk1975/money-tracker.git
cd money-tracker
./start.sh
```

That's it. `start.sh` installs dependencies, loads sample data, and opens the app.

> **Note:** The script will `sudo apt install python3-tk` if tkinter isn't already present — you may be prompted for your password on first run.

## Wipe sample data and enter your own bills

When you're ready to use the app for real:

```bash
python3 wipe.py
```

Then open the app, go to the **Definitions** tab, and add your own bills.

---

## Usage

### Dashboard tab
- **Navigate months** with the ◀ ▶ arrows — the app auto-generates bill instances for future months
- **Fund bills** before marking them paid (use *Funded/Unfunded* or *All Funded/Unfunded*)
- **Mark bills paid** once funded (use *Paid/Unpaid* or *All Paid/Unpaid*)
- **Sort** the bill grid by clicking any column header
- Row colors: red = unfunded/unpaid, gold = funded but not yet paid, green = paid

### Definitions tab
- Add, edit, delete, and toggle bill templates
- Supported frequencies: Monthly, AdHoc, Annual, Semi-Annual, Quarterly, Bi-Weekly, Weekly

## Running tests

```bash
python3 -m pytest tests/ -v
```
