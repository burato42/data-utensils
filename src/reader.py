import sys

import pandas as pd

CUSTOMERS_REQUIRED_COLS: frozenset[str] = frozenset({"customer_id", "signup_date", "country"})
SUBSCRIPTIONS_REQUIRED_COLS: frozenset[str] = frozenset(
    {"customer_id", "start_date", "end_date", "plan", "monthly_price"}
)


def read_customers(path: str) -> pd.DataFrame:
    """Read customers CSV as raw strings. Exits on missing file or missing columns."""
    return _read_csv(path, CUSTOMERS_REQUIRED_COLS)


def read_subscriptions(path: str) -> pd.DataFrame:
    """Read subscriptions CSV as raw strings. Exits on missing file or missing columns."""
    return _read_csv(path, SUBSCRIPTIONS_REQUIRED_COLS)


def _read_csv(path: str, required_cols: frozenset[str]) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not read {path}: {e}", file=sys.stderr)
        sys.exit(1)

    missing = required_cols - set(df.columns)
    if missing:
        print(
            f"ERROR: {path} is missing required columns: {sorted(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    return df
