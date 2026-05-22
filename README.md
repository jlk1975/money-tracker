# Money Tracker

A personal household bill tracker built with Python and customtkinter. Track recurring and one-off bills across multiple accounts, manage funding and payment status, and get a monthly dashboard overview.

## Requirements

- Python 3.10+
- Install dependencies:

```bash
pip install -r requirements.txt
```

## Getting Started

### 1. (Optional) Load sample data

To explore the app with example bills before entering your own:

```bash
python3 seed.py
```

This populates the database with generic sample household bills (rent, utilities, insurance, etc.) so you can see what the app looks like with real data.

### 2. Run the app

```bash
python3 app.py
```

### 3. Wipe sample data and enter your own bills

When you're ready to use the app for real, wipe the sample data and start fresh:

```bash
python3 wipe.py
```

Then go to the **Definitions** tab in the app and add your own bills.

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
