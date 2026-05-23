import pandas as pd
import pytest

from src.cleaner import (
    clean_customers,
    clean_subscriptions,
    drop_duplicate_customers,
    drop_invalid_date_range,
    drop_unknown_customers,
    normalize_country,
    parse_customer_signup_date,
    parse_end_date,
    parse_monthly_price,
    parse_start_date,
    strip_strings,
    warn_overlapping,
)


def _customers_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, dtype=str)


def _subscriptions_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, dtype=str)


# ---------------------------------------------------------------------------
# strip_strings
# ---------------------------------------------------------------------------

def test_strip_strings_removes_leading_trailing_whitespace():
    df = pd.DataFrame({"a": [" hello ", "world"], "b": ["  x", "y  "]})
    result = strip_strings(df)
    assert list(result["a"]) == ["hello", "world"]
    assert list(result["b"]) == ["x", "y"]


def test_strip_strings_leaves_non_string_columns_unchanged():
    df = pd.DataFrame({"num": [1, 2], "text": [" a ", " b "]})
    result = strip_strings(df)
    assert list(result["num"]) == [1, 2]


# ---------------------------------------------------------------------------
# normalize_country
# ---------------------------------------------------------------------------

def test_normalize_country_uppercases():
    df = _customers_df([{"customer_id": "C001", "signup_date": "2024-01-01", "country": "nl"}])
    result = normalize_country(df)
    assert result.iloc[0]["country"] == "NL"


def test_normalize_country_warns_on_blank_but_keeps_row():
    df = _customers_df([{"customer_id": "C001", "signup_date": "2024-01-01", "country": ""}])
    result = normalize_country(df)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# parse_customer_signup_date  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_parse_customer_signup_date_valid():
    df = _customers_df([{"customer_id": "C001", "signup_date": "2024-03-15", "country": "NL"}])
    clean, rejected = parse_customer_signup_date(df)
    assert clean.iloc[0]["signup_date"] == pd.Timestamp("2024-03-15")
    assert rejected.empty


def test_parse_customer_signup_date_drops_invalid():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-13-01", "country": "NL"},
        {"customer_id": "C002", "signup_date": "2024-01-01", "country": "DE"},
    ])
    clean, rejected = parse_customer_signup_date(df)
    assert list(clean["customer_id"]) == ["C002"]
    assert list(rejected["customer_id"]) == ["C001"]


# ---------------------------------------------------------------------------
# drop_duplicate_customers  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_drop_duplicate_customers_keeps_first():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-01-01", "country": "NL"},
        {"customer_id": "C001", "signup_date": "2024-06-01", "country": "DE"},
    ])
    clean, rejected = drop_duplicate_customers(df)
    assert len(clean) == 1
    assert clean.iloc[0]["country"] == "NL"
    assert len(rejected) == 1
    assert rejected.iloc[0]["country"] == "DE"


def test_drop_duplicate_customers_no_dupes_unchanged():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-01-01", "country": "NL"},
        {"customer_id": "C002", "signup_date": "2024-02-01", "country": "DE"},
    ])
    clean, rejected = drop_duplicate_customers(df)
    assert len(clean) == 2
    assert rejected.empty


# ---------------------------------------------------------------------------
# drop_unknown_customers  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_drop_unknown_customers_removes_unrecognised_ids():
    df = _subscriptions_df([
        {"customer_id": "C999", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = drop_unknown_customers(df, {"C001"})
    assert list(clean["customer_id"]) == ["C001"]
    assert list(rejected["customer_id"]) == ["C999"]


def test_drop_unknown_customers_all_valid_unchanged():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = drop_unknown_customers(df, {"C001"})
    assert len(clean) == 1
    assert rejected.empty


# ---------------------------------------------------------------------------
# parse_start_date  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_parse_start_date_valid():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-15", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = parse_start_date(df)
    assert clean.iloc[0]["start_date"] == pd.Timestamp("2024-01-15")
    assert rejected.empty


def test_parse_start_date_drops_invalid():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "not-a-date", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
        {"customer_id": "C002", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = parse_start_date(df)
    assert list(clean["customer_id"]) == ["C002"]
    assert list(rejected["customer_id"]) == ["C001"]


# ---------------------------------------------------------------------------
# parse_end_date  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_parse_end_date_blank_becomes_nat():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = parse_end_date(df)
    assert pd.isna(clean.iloc[0]["end_date"])
    assert rejected.empty


def test_parse_end_date_whitespace_only_becomes_nat():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "   ",
         "plan": "basic", "monthly_price": "30"},
    ])
    df["end_date"] = df["end_date"].str.strip()  # strip_strings runs first in practice
    clean, rejected = parse_end_date(df)
    assert pd.isna(clean.iloc[0]["end_date"])
    assert rejected.empty


def test_parse_end_date_valid_date_parsed():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "2024-03-31",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = parse_end_date(df)
    assert clean.iloc[0]["end_date"] == pd.Timestamp("2024-03-31")
    assert rejected.empty


def test_parse_end_date_invalid_non_blank_dropped():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "2024-02-30",
         "plan": "basic", "monthly_price": "30"},
        {"customer_id": "C002", "start_date": "2024-01-01", "end_date": "2024-03-31",
         "plan": "basic", "monthly_price": "30"},
    ])
    clean, rejected = parse_end_date(df)
    assert list(clean["customer_id"]) == ["C002"]
    assert list(rejected["customer_id"]) == ["C001"]


# ---------------------------------------------------------------------------
# parse_monthly_price  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_parse_monthly_price_valid():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "29.99"},
    ])
    clean, rejected = parse_monthly_price(df)
    assert clean.iloc[0]["monthly_price"] == pytest.approx(29.99)
    assert rejected.empty


def test_parse_monthly_price_non_numeric_dropped():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "thirty"},
        {"customer_id": "C002", "start_date": "2024-01-01", "end_date": "",
         "plan": "pro", "monthly_price": "50"},
    ])
    clean, rejected = parse_monthly_price(df)
    assert list(clean["customer_id"]) == ["C002"]
    assert list(rejected["customer_id"]) == ["C001"]


# ---------------------------------------------------------------------------
# drop_invalid_date_range  — now returns (clean, rejected)
# ---------------------------------------------------------------------------

def test_drop_invalid_date_range_removes_end_before_start():
    df = pd.DataFrame([{
        "customer_id": "C001",
        "start_date": pd.Timestamp("2024-09-01"),
        "end_date": pd.Timestamp("2024-08-01"),
        "plan": "basic",
        "monthly_price": 30.0,
    }])
    clean, rejected = drop_invalid_date_range(df)
    assert clean.empty
    assert len(rejected) == 1


def test_drop_invalid_date_range_keeps_valid_rows():
    df = pd.DataFrame([{
        "customer_id": "C001",
        "start_date": pd.Timestamp("2024-01-01"),
        "end_date": pd.Timestamp("2024-03-31"),
        "plan": "basic",
        "monthly_price": 30.0,
    }])
    clean, rejected = drop_invalid_date_range(df)
    assert len(clean) == 1
    assert rejected.empty


def test_drop_invalid_date_range_keeps_nat_end_date():
    df = pd.DataFrame([{
        "customer_id": "C001",
        "start_date": pd.Timestamp("2024-01-01"),
        "end_date": pd.NaT,
        "plan": "basic",
        "monthly_price": 30.0,
    }])
    clean, rejected = drop_invalid_date_range(df)
    assert len(clean) == 1
    assert rejected.empty


# ---------------------------------------------------------------------------
# warn_overlapping  (no drop — just verify no exception and rows intact)
# ---------------------------------------------------------------------------

def test_warn_overlapping_does_not_drop_rows():
    df = pd.DataFrame([
        {"customer_id": "C001", "start_date": pd.Timestamp("2024-01-01"),
         "end_date": pd.Timestamp("2024-04-01"), "plan": "basic", "monthly_price": 30.0},
        {"customer_id": "C001", "start_date": pd.Timestamp("2024-03-15"),
         "end_date": pd.Timestamp("2024-05-01"), "plan": "pro", "monthly_price": 50.0},
    ])
    warn_overlapping(df)
    assert len(df) == 2


def test_warn_overlapping_no_overlap_no_warning(caplog):
    import logging
    df = pd.DataFrame([
        {"customer_id": "C001", "start_date": pd.Timestamp("2024-01-01"),
         "end_date": pd.Timestamp("2024-02-28"), "plan": "basic", "monthly_price": 30.0},
        {"customer_id": "C001", "start_date": pd.Timestamp("2024-03-01"),
         "end_date": pd.NaT, "plan": "pro", "monthly_price": 50.0},
    ])
    with caplog.at_level(logging.WARNING):
        warn_overlapping(df)
    assert "overlapping" not in caplog.text


# ---------------------------------------------------------------------------
# clean_customers / clean_subscriptions  (integration, now return tuples)
# ---------------------------------------------------------------------------

def test_clean_customers_full_pipeline():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-13-01", "country": "NL"},  # bad date
        {"customer_id": "C002", "signup_date": "2024-01-01", "country": "nl"},  # lowercase
        {"customer_id": "C002", "signup_date": "2024-06-01", "country": "DE"},  # duplicate
    ])
    result, rejected = clean_customers(df)
    assert list(result["customer_id"]) == ["C002"]
    assert result.iloc[0]["country"] == "NL"
    # C001 (bad date) and second C002 (duplicate) should appear in rejected
    assert not rejected.empty


def test_clean_customers_returns_rejected_rows():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-13-01", "country": "NL"},
        {"customer_id": "C002", "signup_date": "2024-01-01", "country": "DE"},
    ])
    _, rejected = clean_customers(df)
    reasons = set(rejected.frames[0]["_rejection_reason"]) if rejected.frames else set()
    assert "invalid signup_date" in reasons


def test_clean_subscriptions_full_pipeline():
    df = _subscriptions_df([
        {"customer_id": "C999", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},           # unknown id
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "2024-02-30",
         "plan": "basic", "monthly_price": "thirty"},       # bad end_date + bad price
        {"customer_id": "C001", "start_date": "2024-09-01", "end_date": "2024-08-01",
         "plan": "basic", "monthly_price": "30"},           # end before start
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},           # valid
    ])
    result, rejected = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert list(result["customer_id"]) == ["C001"]
    assert pd.isna(result.iloc[0]["end_date"])
    assert not rejected.empty


def test_clean_subscriptions_whitespace_in_date():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": " 2024-01-01 ", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    result, _ = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert len(result) == 1
    assert pd.notna(result.iloc[0]["start_date"])


def test_clean_subscriptions_collects_all_rejection_reasons():
    df = _subscriptions_df([
        {"customer_id": "C999", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
        {"customer_id": "C001", "start_date": "bad", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "free"},
    ])
    _, rejected = clean_subscriptions(df, valid_customer_ids={"C001"})
    all_reasons = {
        reason
        for frame in rejected.frames
        for reason in frame["_rejection_reason"].unique()
    }
    assert "unknown customer_id" in all_reasons
    assert "invalid start_date" in all_reasons
    assert "non-numeric monthly_price" in all_reasons
