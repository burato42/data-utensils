from dataclasses import dataclass
from datetime import date

import pandas as pd
from loguru import logger


@dataclass
class Customer:
    customer_id: str
    signup_date: date
    country: str


@dataclass
class Subscription:
    customer_id: str
    start_date: date
    end_date: date | None  # None means currently active
    plan: str
    monthly_price: float


def clean_customers(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean the customers DataFrame.

    Drops rows with unparseable signup_date. Deduplicates on customer_id (keep first).
    Normalizes country to uppercase. Returns DataFrame with signup_date as datetime64.
    """
    df = raw.copy()

    # Strip whitespace from all string columns
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()

    # Warn about blank country but keep the row
    blank_country = df["country"].isna() | (df["country"] == "")
    for cid in df.loc[blank_country, "customer_id"]:
        logger.warning(f"Customer {cid} has blank country")
    df["country"] = df["country"].str.upper()

    # Parse signup_date — drop rows that fail
    parsed = pd.to_datetime(df["signup_date"], format="%Y-%m-%d", errors="coerce")
    bad_date = parsed.isna()
    for cid in df.loc[bad_date, "customer_id"]:
        logger.warning(f"Customer {cid} has invalid signup_date — row dropped")
    df = df[~bad_date].copy()
    df["signup_date"] = parsed[~bad_date]

    # Deduplicate customer_id — keep first
    dupes = df.duplicated(subset="customer_id", keep="first")
    for cid in df.loc[dupes, "customer_id"]:
        logger.warning(f"Duplicate customer_id {cid} — keeping first occurrence, dropping duplicate")
    df = df[~dupes].reset_index(drop=True)

    return df


def clean_subscriptions(raw: pd.DataFrame, valid_customer_ids: set[str]) -> pd.DataFrame:
    """
    Validate and clean the subscriptions DataFrame.

    Drops rows with invalid start_date, invalid end_date (non-blank), non-numeric
    monthly_price, end_date < start_date, or unknown customer_id. Blank/whitespace
    end_date is treated as NaT (active subscription). Warns about overlapping
    subscriptions per customer but keeps them.
    """
    df = raw.copy()

    # Strip whitespace from all string columns before any parsing
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()

    # Drop rows with unknown customer_id
    unknown = ~df["customer_id"].isin(valid_customer_ids)
    for cid in df.loc[unknown, "customer_id"].unique():
        logger.warning(f"Subscription references unknown customer_id {cid} — rows dropped")
    df = df[~unknown].copy()

    # Parse start_date — drop rows that fail
    parsed_start = pd.to_datetime(df["start_date"], format="%Y-%m-%d", errors="coerce")
    bad_start = parsed_start.isna()
    for cid in df.loc[bad_start, "customer_id"]:
        logger.warning(f"Subscription for {cid} has invalid start_date '{df.loc[bad_start & (df['customer_id'] == cid), 'start_date'].iloc[0]}' — row dropped")
    df = df[~bad_start].copy()
    df["start_date"] = parsed_start[~bad_start]

    # Parse end_date — blank/whitespace → NaT (active); invalid non-blank → drop
    end_raw = df["end_date"].fillna("")
    blank_end = end_raw == ""
    parsed_end = pd.to_datetime(df["end_date"].where(~blank_end), format="%Y-%m-%d", errors="coerce")
    # Rows where end_date was non-blank but failed to parse
    bad_end = (~blank_end) & parsed_end.isna()
    for cid in df.loc[bad_end, "customer_id"]:
        logger.warning(f"Subscription for {cid} has invalid end_date — row dropped")
    df = df[~bad_end].copy()
    df["end_date"] = parsed_end[~bad_end]  # NaT for both blank and truly active

    # Cast monthly_price to float — drop rows that fail
    numeric_price = pd.to_numeric(df["monthly_price"], errors="coerce")
    bad_price = numeric_price.isna()
    for cid in df.loc[bad_price, "customer_id"]:
        logger.warning(f"Subscription for {cid} has non-numeric monthly_price '{df.loc[bad_price & (df['customer_id'] == cid), 'monthly_price'].iloc[0]}' — row dropped")
    df = df[~bad_price].copy()
    df["monthly_price"] = numeric_price[~bad_price]

    # Drop rows where end_date < start_date
    invalid_range = df["end_date"].notna() & (df["end_date"] < df["start_date"])
    for cid in df.loc[invalid_range, "customer_id"]:
        logger.warning(f"Subscription for {cid} has end_date before start_date — row dropped")
    df = df[~invalid_range].reset_index(drop=True)

    # Warn about overlapping subscriptions per customer (keep both)
    _warn_overlapping(df)

    return df.reset_index(drop=True)


def _warn_overlapping(df: pd.DataFrame) -> None:
    """Log a warning for each customer that has overlapping subscription periods."""
    for cid, group in df.groupby("customer_id"):
        g = group.sort_values("start_date").reset_index(drop=True)
        for i in range(len(g) - 1):
            curr_end = g.loc[i, "end_date"]
            next_start = g.loc[i + 1, "start_date"]
            # If current sub has no end_date (active) or ends after next starts
            if pd.isna(curr_end) or curr_end >= next_start:
                logger.warning(
                    f"Customer {cid} has overlapping subscriptions "
                    f"(row {i}: ends {curr_end}, row {i+1}: starts {next_start}) — both kept"
                )
