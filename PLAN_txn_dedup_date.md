# Plan: Use (transaction_number, date) for CSV Import Deduplication

## Problem

CSV import deduplicates rows that have a `transaction_number` by checking that number alone.
If the bank ever reuses a transaction number on a different date, the second transaction would
be silently skipped as a false duplicate.

## Fix

Use `(transaction_number, date)` as the composite dedup key instead of `transaction_number` alone.

## Changes Required

### `db.py` — `get_imported_transaction_numbers()`

Rename to `get_imported_transaction_keys()` (or keep name, just change what it returns).
Return a set of `(transaction_number, date)` tuples instead of `{transaction_number}` strings.

```python
def get_imported_transaction_keys(db_path=DEFAULT_DB):
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT transaction_number, date FROM register_transactions WHERE transaction_number != ''"
        ).fetchall()
    return {(r[0], r[1]) for r in rows}
```

### `app.py` — CSV import loop (around line 1881)

1. Call `get_imported_transaction_keys()` instead of `get_imported_transaction_numbers()`.
2. Change the dedup check and the post-insert add to use the tuple key.

Before:
```python
existing_nums = db.get_imported_transaction_numbers(DB_PATH)
...
if txn_num in existing_nums:
    dup_count += 1
    continue
db.insert_transaction(row, DB_PATH)
existing_nums.add(txn_num)
```

After:
```python
existing_keys = db.get_imported_transaction_keys(DB_PATH)
...
key = (txn_num, row.get("date", ""))
if key in existing_keys:
    dup_count += 1
    continue
db.insert_transaction(row, DB_PATH)
existing_keys.add(key)
```

## Notes

- No DB schema change needed — `transaction_number` and `date` columns already exist.
- Rows without a `transaction_number` use the existing fingerprint dedup path — no change needed there.
- No migration needed for existing data; the new key is derived from columns already stored.
