from dataclasses import dataclass
from datetime import date

import pandas as pd
from loguru import logger

from src.error_sink import RejectedRows


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


# --- customers ---

def clean_customers(raw: pd.DataFrame, source: str = "customers") -> tuple[pd.DataFrame, RejectedRows]:
    """
    Validate and clean the customers DataFrame.

    Drops rows with unparseable signup_date and duplicate customer_ids (keep first).
    Normalizes country to uppercase. Rows with a blank country are kept but flagged.

    Returns (clean_df, rejected) where rejected accumulates all dropped rows with reasons.
    """
    rejected = RejectedRows(source=source)
    df = strip_strings(raw.copy())
    df = normalize_country(df, rejected)
    df, rej = parse_customer_signup_date(df)
    rejected.add(rej, "invalid signup_date")
    df, rej = drop_duplicate_customers(df)
    rejected.add(rej, "duplicate customer_id")
    return df.reset_index(drop=True), rejected


def strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()
    return df


def normalize_country(df: pd.DataFrame, rejected: RejectedRows | None = None) -> pd.DataFrame:
    """Uppercase the country column; log a warning for blank values (rows kept).

    Blank-country rows are flagged in rejected (not dropped) when rejected is provided.
    """
    blank = df["country"].isna() | (df["country"] == "")
    for cid in df.loc[blank, "customer_id"]:
        logger.warning(f"Customer {cid} has blank country")
    if rejected is not None:
        rejected.add(df[blank], "blank country (row kept)")
    df["country"] = df["country"].str.upper()
    return df


def parse_customer_signup_date(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse signup_date; return (clean, rejected) where rejected holds unparseable rows."""
    parsed = pd.to_datetime(df["signup_date"], format="%Y-%m-%d", errors="coerce")
    bad = parsed.isna()
    for cid in df.loc[bad, "customer_id"]:
        logger.warning(f"Customer {cid} has invalid signup_date — row dropped")
    clean = df[~bad].copy()
    clean["signup_date"] = parsed[~bad]
    return clean, df[bad].copy()


def drop_duplicate_customers(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the first occurrence of each customer_id; return (clean, rejected duplicates)."""
    dupes = df.duplicated(subset="customer_id", keep="first")
    for cid in df.loc[dupes, "customer_id"]:
        logger.warning(f"Duplicate customer_id {cid} — keeping first occurrence, dropping duplicate")
    return df[~dupes].copy(), df[dupes].copy()


# --- subscriptions ---

def clean_subscriptions(
    raw: pd.DataFrame,
    valid_customer_ids: set[str],
    source: str = "subscriptions",
) -> tuple[pd.DataFrame, RejectedRows]:
    """
    Validate and clean the subscriptions DataFrame.

    Drops rows with unknown customer_id, invalid start_date, invalid end_date (non-blank),
    non-numeric monthly_price, or end_date < start_date. Blank/whitespace end_date is
    treated as NaT (active subscription). Overlapping subscriptions are flagged but kept.

    Returns (clean_df, rejected) where rejected accumulates all dropped rows with reasons.
    """
    rejected = RejectedRows(source=source)
    df = strip_strings(raw.copy())
    df, rej = drop_unknown_customers(df, valid_customer_ids)
    rejected.add(rej, "unknown customer_id")
    df, rej = parse_start_date(df)
    rejected.add(rej, "invalid start_date")
    df, rej = parse_end_date(df)
    rejected.add(rej, "invalid end_date")
    df, rej = parse_monthly_price(df)
    rejected.add(rej, "non-numeric monthly_price")
    df, rej = drop_invalid_date_range(df)
    rejected.add(rej, "end_date before start_date")
    warn_overlapping(df)
    return df.reset_index(drop=True), rejected


def drop_unknown_customers(df: pd.DataFrame, valid_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop rows whose customer_id is not in valid_ids; return (clean, rejected)."""
    unknown = ~df["customer_id"].isin(valid_ids)
    for cid in df.loc[unknown, "customer_id"].unique():
        logger.warning(f"Subscription references unknown customer_id {cid} — rows dropped")
    return df[~unknown].copy(), df[unknown].copy()


def parse_start_date(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse start_date; return (clean, rejected) where rejected holds unparseable rows."""
    parsed = pd.to_datetime(df["start_date"], format="%Y-%m-%d", errors="coerce")
    bad = parsed.isna()
    for cid in df.loc[bad, "customer_id"]:
        raw_val = df.loc[bad & (df["customer_id"] == cid), "start_date"].iloc[0]
        logger.warning(f"Subscription for {cid} has invalid start_date '{raw_val}' — row dropped")
    clean = df[~bad].copy()
    clean["start_date"] = parsed[~bad]
    return clean, df[bad].copy()


def parse_end_date(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse end_date; blank/whitespace → NaT (active). Return (clean, rejected) for invalid non-blank."""
    blank = df["end_date"].fillna("") == ""
    parsed = pd.to_datetime(df["end_date"].where(~blank), format="%Y-%m-%d", errors="coerce")
    bad = (~blank) & parsed.isna()
    for cid in df.loc[bad, "customer_id"]:
        logger.warning(f"Subscription for {cid} has invalid end_date — row dropped")
    clean = df[~bad].copy()
    clean["end_date"] = parsed[~bad]
    return clean, df[bad].copy()


def parse_monthly_price(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cast monthly_price to float; return (clean, rejected) where rejected holds non-numeric rows."""
    parsed = pd.to_numeric(df["monthly_price"], errors="coerce")
    bad = parsed.isna()
    for cid in df.loc[bad, "customer_id"]:
        raw_val = df.loc[bad & (df["customer_id"] == cid), "monthly_price"].iloc[0]
        logger.warning(f"Subscription for {cid} has non-numeric monthly_price '{raw_val}' — row dropped")
    clean = df[~bad].copy()
    clean["monthly_price"] = parsed[~bad]
    return clean, df[bad].copy()


def drop_invalid_date_range(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop rows where end_date is set but precedes start_date; return (clean, rejected)."""
    invalid = df["end_date"].notna() & (df["end_date"] < df["start_date"])
    for cid in df.loc[invalid, "customer_id"]:
        logger.warning(f"Subscription for {cid} has end_date before start_date — row dropped")
    return df[~invalid].copy(), df[invalid].copy()


def warn_overlapping(df: pd.DataFrame) -> None:
    """Log a warning for each customer that has overlapping subscription periods."""
    for cid, group in df.groupby("customer_id"):
        g = group.sort_values("start_date").reset_index(drop=True)
        for i in range(len(g) - 1):
            curr_end = g.loc[i, "end_date"]
            next_start = g.loc[i + 1, "start_date"]
            if pd.isna(curr_end) or curr_end >= next_start:
                logger.warning(
                    f"Customer {cid} has overlapping subscriptions "
                    f"(row {i}: ends {curr_end}, row {i+1}: starts {next_start}) — both kept"
                )
