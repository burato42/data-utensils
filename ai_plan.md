# Prompt
I want you to plan the implementation of the assignment `assignmnent.md`.
The desired project structure:
In the src folder I need separate files with a following components
- reader to read the data from the sources;
- extractor (let's make it a placeholder, it seems we shouldn't extract anything here);
- cleaner (which cleans the data)
- transformer to make transformations we need
- sink for writing the results.


# Plan: Subscription Analytics CLI Tool

## Context
Implement a small data analytics CLI tool for a subscription SaaS product. It reads two CSVs (`customers.csv`, `subscriptions.csv`), validates and cleans the data, computes three key metrics (MRR, monthly churn count, 3-month cohort retention), and writes a JSON report. The code must be structured for extensibility — adding a new metric should touch only `transformer.py` and `main.py`.

---

## Project Structure

```
main.py                  # CLI entry point (~50 lines)
src/__init__.py
src/reader.py            # Read CSVs, validate required columns
src/extractor.py         # Placeholder stub
src/cleaner.py           # Data quality enforcement + dataclass models
src/transformer.py       # Business logic: MRR, churn, cohort retention
src/sink.py              # JSON output writer
tests/__init__.py
tests/test_reader.py
tests/test_cleaner.py
tests/test_transformer.py
DESIGN.md
```

---

## Module Details

### `src/reader.py`
- `read_customers(path: str) -> pd.DataFrame`
- `read_subscriptions(path: str) -> pd.DataFrame`
- Validates required columns; calls `sys.exit(1)` with a clear message on missing file or missing columns.
- Returns raw DataFrames with all columns as strings (no date parsing here).

### `src/extractor.py`
Stub only:
```python
def extract() -> None:
    """Placeholder: no remote extraction required for this pipeline."""
    pass
```

### `src/cleaner.py`
Houses `Customer` and `Subscription` dataclasses (schema reference).

**Cleaning — customers:**
- Strip whitespace from all string columns
- Parse `signup_date` with `pd.to_datetime(format="%Y-%m-%d")`; drop row + log WARNING on failure
- Normalize `country` to uppercase (warn on blank, keep row)
- Deduplicate on `customer_id` (keep first, log WARNING for each duplicate)

**Cleaning — subscriptions:**
- Strip whitespace before parsing dates (handles `" 2024-10-14 "`)
- Parse `start_date`; drop + warn on failure
- Parse `end_date`; blank/whitespace-only → `NaT` (active); drop + warn on invalid date
- Cast `monthly_price` to float; drop + warn on failure (handles `"thirty"`)
- Drop rows where `end_date < start_date`; warn
- Drop rows where `customer_id` not in cleaned customers set; warn
- Detect overlapping subscriptions per customer; warn but **keep both** (dropping would undercount MRR)

Signatures:
```python
def clean_customers(raw: pd.DataFrame) -> pd.DataFrame
def clean_subscriptions(raw: pd.DataFrame, valid_customer_ids: set[str]) -> pd.DataFrame
```

### `src/transformer.py`
Pure functions, no I/O.

**`compute_mrr(subscriptions: pd.DataFrame) -> list[dict]`**
- Enumerate all calendar months in range `[min(start_date), max(end_date or today)]`
- Active in month M: `start_date <= last_day_of_M` AND (`end_date is NaT` OR `end_date >= first_day_of_M`)
- Sum `monthly_price` for active rows per month
- Returns: `[{"month": "YYYY-MM", "mrr": float}, ...]`

**`compute_churn(subscriptions: pd.DataFrame) -> list[dict]`**
- Churn event: subscription has non-null `end_date` AND customer has no subscription with `start_date` in `(end_date, end_date + 30 days]` (day 30 inclusive = not churned)
- Attribute to calendar month of `end_date`
- Returns: `[{"month": "YYYY-MM", "churned_customers": int}, ...]`

**`compute_cohort_retention(customers: pd.DataFrame, subscriptions: pd.DataFrame) -> list[dict]`**
- Group customers by `signup_date` year-month
- Target date = first day of `cohort_month + 3 calendar months`
- Active at target: has subscription where `start_date <= target_date` AND (`end_date is NaT` OR `end_date >= target_date`)
- Returns: `[{"cohort_month": "YYYY-MM", "cohort_size": int, "active_after_3_months": int, "retention_rate_3m": float}, ...]`

### `src/sink.py`
- `write_output(results: dict, output_path: str) -> None`
- `json.dumps(indent=2)` with a custom encoder for `date` objects
- `sys.exit(1)` on I/O error

### `main.py`
- `argparse` for `customers_path`, `subscriptions_path`, `output_path`
- Configure `loguru` logger once at startup
- Wire: read → clean → transform (3 calls) → assemble results dict → sink
- JSON shape:
```json
{
  "mrr": [...],
  "churn": [...],
  "cohorts": [...]
}
```

---

## Tests

### `tests/test_transformer.py`
**Churn:**
- Basic churn (no re-sub within 30d)
- Re-sub on day 15 → no churn
- Re-sub exactly on day 30 → no churn (boundary inclusive)
- Re-sub on day 31 → churn
- Active sub (no end_date) → no churn
- Zero-duration sub (end = start), no re-sub → churn

**Cohort retention:**
- Basic: 3 customers in cohort, 2 active at 3m → 0.6667
- Re-subbed exactly at 3m boundary → counted as active
- All churned before 3m → 0.0

**MRR:**
- Subscription spanning multiple months counted each month
- Empty DataFrame → empty list
- Two customers churn same month → count = 2

### `tests/test_cleaner.py`
- Invalid date row dropped
- Duplicate customer_id: first kept
- Unknown customer_id in subscriptions dropped
- Whitespace in date stripped and parsed correctly
- Non-numeric price row dropped
- end_date before start_date dropped

### `tests/test_reader.py`
- Non-existent file → SystemExit
- Missing required column → SystemExit

---

## Key Assumptions & Trade-offs
- **30-day churn window**: inclusive on day 30 (`new_start <= end + 30d`)
- **3-month offset**: calendar months (not 90 days); target = first day of cohort month + 3 months
- **Overlapping subs**: kept (warn only) — dropping would undercount MRR
- **Duplicate customers**: keep first CSV occurrence

---

## Verification
```bash
# Run with sample data
python main.py data/customers.csv data/subscriptions.csv output.json
cat output.json

# Run tests
python -m pytest tests/ -v
```
Check that:
1. Warnings are logged for known bad rows (C019, C021, C026, C999, C050, etc.)
2. output.json contains all three keys: `mrr`, `churn`, `cohorts`
3. All tests pass



## Prompt
Let's generate a proper .gitignore file for python and vscode

## Prompt
I don't like cleaner.py. Every function does too much work. Let's split it too smaller functions keeping the same fucntionality

```
_strip_strings — whitespace trimming
_normalize_country — uppercase + blank warning
_parse_customer_signup_date — date parse + drop
_drop_duplicate_customers — dedup + warn
_drop_unknown_customers — customer_id validation
_parse_start_date / _parse_end_date / _parse_monthly_price — one field each
_drop_invalid_date_range — chronological check
_warn_overlapping — overlap detection (unchanged)
```

## Prompt
As we can reuse cleaning function in future, let's make them "public" and write a test not only for overall functionality but also for those small components

## Prompt
When we clean data and see some dataquality errors we log the "warning" and continue. It could be fine but is a potential risk. Let's create a csv-file with problematic records from the corresponding source file in a separate directory per ETL-run.
Also, let's create a component that will do this error processing.

```
New: src/error_sink.py

RejectedRows — accumulates dropped rows from one source file, each tagged with a _rejection_reason column via .add(frame, reason)
write_quarantine(rejected, run_dir) — writes one <stem>_errors.csv per source under quarantine/<timestamp>/; skips creating the directory entirely when nothing was rejected
Changed: src/cleaner.py

All dropping helpers (parse_customer_signup_date, drop_duplicate_customers, drop_unknown_customers, parse_start_date, parse_end_date, parse_monthly_price, drop_invalid_date_range) now return (clean_df, rejected_df) instead of just the clean half
clean_customers and clean_subscriptions accept a source parameter, build a RejectedRows object internally, and return (clean_df, rejected) — the caller decides what to do with rejected rows
normalize_country optionally accepts a RejectedRows to flag blank-country rows (kept but visible in the quarantine file)
Changed: main.py — unpacks the tuples, passes source filenames, calls write_quarantine; adds --quarantine-dir CLI option (default: quarantine/)

New: tests/test_error_sink.py — 10 tests covering RejectedRows and write_quarantine; all cleaner tests updated for the new tuple signatures.
```

## Prompt
Let's add requirements.txt containig the corresponding libraries to make an alternative way of running the pipeline.

## Prompt
And now let's create a concise README with very basic information on how to run the pipeline and the tests.