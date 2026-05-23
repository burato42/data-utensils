# Design Note

## Code Structure

```
main.py          CLI entry point — wires the pipeline, ~40 lines
src/
  reader.py      Read raw CSVs; fatal exit on missing file/columns
  extractor.py   Placeholder for future remote data extraction
  cleaner.py     Data quality enforcement; canonical data models (dataclasses)
  transformer.py Pure business logic for MRR, churn, cohort retention
  sink.py        JSON output writer
tests/
  test_reader.py
  test_cleaner.py
  test_transformer.py
```

The pipeline is a linear sequence: **read → clean → transform → write**. Each stage is a
separate module with a single responsibility. `main.py` only imports, calls, and assembles;
no business logic lives there.

## Business Rule Modeling

**MRR** — For each calendar month, a subscription contributes its `monthly_price` if
`start_date ≤ last_day_of_month` and `(end_date is null OR end_date ≥ first_day_of_month)`.
This correctly handles subscriptions that begin or end mid-month.

**Churn** — A churn event is when a subscription ends (`end_date` is set) and the customer
has no new subscription starting within 30 days of that end date (boundary inclusive: a
re-subscription on exactly day 30 is not a churn). The event is attributed to the calendar
month of `end_date`.

**Cohort retention** — Customers are grouped by the year-month of `signup_date`. The
3-month target date is the first calendar day of `cohort_month + 3 months` (not 90 days,
matching standard SaaS cohort conventions). A customer is "active" at that target date if
they have any subscription where `start_date ≤ target_date` and
`(end_date is null OR end_date ≥ target_date)`.

## Adding a New Metric

1. Add a pure function `compute_<metric>(...)` to `src/transformer.py`.
2. Call it in `main.py` and add the result under a new key in the `results` dict.
3. Write tests in `tests/test_transformer.py`.

No other files need to change.

## Assumptions & Trade-offs

- **30-day churn window is inclusive**: a re-subscription on day 30 is not a churn. This
  matches the assignment wording ("no new subscription starting within 30 days").
- **3-month offset is calendar-based**: uses `relativedelta(months=3)` rather than 90 days,
  which is standard in SaaS reporting but means cohorts may behave differently for months of
  different lengths.
- **Overlapping subscriptions are kept**: they are a data quality warning, not an error.
  Dropping them would silently undercount MRR; both rows are kept and logged.
- **Duplicate customers**: the first CSV occurrence is treated as canonical. No business rule
  determines which signup date is "correct".
- **All pandas DataFrames**: the pipeline uses DataFrames throughout rather than converting
  to dataclass instances. The dataclasses in `cleaner.py` serve as the authoritative schema
  reference and are used in tests for constructing fixtures.
