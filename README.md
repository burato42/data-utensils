# utilus

A small CLI tool that computes SaaS subscription metrics (MRR, churn, cohort retention) from CSV files.

## Setup

**With uv (recommended):**
```bash
uv sync
```

**With pip:**
```bash
pip install -r requirements.txt
```

## Run the pipeline

```bash
python main.py data/customers.csv data/subscriptions.csv output.json
```

Output is written to `output.json`. Rejected records (data quality issues) are saved to
`quarantine/<timestamp>/` as CSV files for inspection.

Optional flag:
```
--quarantine-dir PATH   Base directory for rejected-record CSVs (default: quarantine/)
```

## Run the tests

```bash
python -m pytest tests/
```

## Project structure

```
src/
  reader.py       Read CSVs, validate required columns
  extractor.py    Placeholder for future remote extraction
  cleaner.py      Data cleaning and validation
  transformer.py  Business logic: MRR, churn, cohort retention
  sink.py         Write JSON output
  error_sink.py   Collect and write rejected records to quarantine CSVs
tests/
data/             Sample input CSVs
main.py           CLI entry point
DESIGN.md         Design decisions and trade-offs
```
