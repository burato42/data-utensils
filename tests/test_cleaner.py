import pandas as pd
import pytest

from src.cleaner import clean_customers, clean_subscriptions


def _customers_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, dtype=str)


def _subscriptions_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, dtype=str)


# --- customers ---

def test_invalid_signup_date_dropped():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-13-01", "country": "NL"},
        {"customer_id": "C002", "signup_date": "2024-01-01", "country": "DE"},
    ])
    result = clean_customers(df)
    assert list(result["customer_id"]) == ["C002"]


def test_duplicate_customer_keeps_first():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-01-01", "country": "NL"},
        {"customer_id": "C001", "signup_date": "2024-06-01", "country": "DE"},
    ])
    result = clean_customers(df)
    assert len(result) == 1
    assert result.iloc[0]["country"] == "NL"


def test_country_normalized_to_uppercase():
    df = _customers_df([
        {"customer_id": "C001", "signup_date": "2024-01-01", "country": "nl"},
    ])
    result = clean_customers(df)
    assert result.iloc[0]["country"] == "NL"


# --- subscriptions ---

def test_unknown_customer_id_dropped():
    df = _subscriptions_df([
        {"customer_id": "C999", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert result.empty


def test_whitespace_in_date_stripped():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": " 2024-01-01 ", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert len(result) == 1
    assert pd.notna(result.iloc[0]["start_date"])


def test_non_numeric_price_dropped():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "thirty"},
        {"customer_id": "C002", "start_date": "2024-01-01", "end_date": "",
         "plan": "pro", "monthly_price": "50"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001", "C002"})
    assert list(result["customer_id"]) == ["C002"]


def test_end_before_start_dropped():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-09-01", "end_date": "2024-08-01",
         "plan": "basic", "monthly_price": "30"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert result.empty


def test_blank_end_date_treated_as_active():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "",
         "plan": "basic", "monthly_price": "30"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["end_date"])


def test_whitespace_only_end_date_treated_as_active():
    df = _subscriptions_df([
        {"customer_id": "C001", "start_date": "2024-01-01", "end_date": "   ",
         "plan": "basic", "monthly_price": "30"},
    ])
    result = clean_subscriptions(df, valid_customer_ids={"C001"})
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["end_date"])
