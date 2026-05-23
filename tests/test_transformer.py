from datetime import date

import pandas as pd
import pytest

from src.transformer import compute_churn, compute_cohort_retention, compute_mrr


def _subs(*rows) -> pd.DataFrame:
    """Build a subscriptions DataFrame from (customer_id, start, end_or_None, plan, price) tuples."""
    records = []
    for cid, start, end, plan, price in rows:
        records.append({
            "customer_id": cid,
            "start_date": pd.Timestamp(start),
            "end_date": pd.Timestamp(end) if end else pd.NaT,
            "plan": plan,
            "monthly_price": float(price),
        })
    return pd.DataFrame(records)


def _customers(*rows) -> pd.DataFrame:
    """Build a customers DataFrame from (customer_id, signup_date, country) tuples."""
    records = [{"customer_id": cid, "signup_date": pd.Timestamp(signup), "country": country}
               for cid, signup, country in rows]
    return pd.DataFrame(records)


# ===== MRR =====

def test_mrr_empty_subscriptions():
    df = _subs()
    assert compute_mrr(df) == []


def test_mrr_single_active_subscription_spans_multiple_months():
    df = _subs(("C001", "2024-01-15", None, "basic", 30))
    result = compute_mrr(df)
    months = [r["month"] for r in result]
    # Should appear in Jan and every subsequent month up to today
    assert "2024-01" in months
    assert "2024-02" in months
    # All values should be 30.0
    for r in result:
        assert r["mrr"] == 30.0


def test_mrr_subscription_counted_only_in_active_months():
    df = _subs(("C001", "2024-01-01", "2024-02-28", "basic", 50))
    result = compute_mrr(df)
    by_month = {r["month"]: r["mrr"] for r in result}
    assert by_month["2024-01"] == 50.0
    assert by_month["2024-02"] == 50.0
    assert "2024-03" not in by_month


def test_mrr_sums_multiple_active_subscriptions():
    df = _subs(
        ("C001", "2024-01-01", "2024-01-31", "basic", 30),
        ("C002", "2024-01-15", "2024-01-31", "pro", 50),
    )
    result = compute_mrr(df)
    by_month = {r["month"]: r["mrr"] for r in result}
    assert by_month["2024-01"] == 80.0


# ===== CHURN =====

def test_churn_basic_no_resubscription():
    df = _subs(("C001", "2024-01-01", "2024-03-31", "basic", 30))
    result = compute_churn(df)
    assert result == [{"month": "2024-03", "churned_customers": 1}]


def test_no_churn_resubscribed_within_30_days():
    df = _subs(
        ("C001", "2024-01-01", "2024-03-31", "basic", 30),
        ("C001", "2024-04-15", None, "pro", 50),  # day 15 after end
    )
    result = compute_churn(df)
    assert result == []


def test_no_churn_resubscribed_on_day_30():
    # Day 30 is inclusive — not churned
    df = _subs(
        ("C001", "2024-01-01", "2024-03-31", "basic", 30),
        ("C001", "2024-04-30", None, "pro", 50),  # exactly 30 days after
    )
    result = compute_churn(df)
    assert result == []


def test_churn_resubscribed_on_day_31():
    # Day 31 is outside the window — churned
    df = _subs(
        ("C001", "2024-01-01", "2024-03-31", "basic", 30),
        ("C001", "2024-05-01", None, "pro", 50),  # 31 days after
    )
    result = compute_churn(df)
    assert len(result) == 1
    assert result[0]["churned_customers"] == 1


def test_no_churn_active_subscription():
    df = _subs(("C001", "2024-01-01", None, "basic", 30))
    result = compute_churn(df)
    assert result == []


def test_churn_zero_duration_subscription():
    # end_date == start_date, no re-sub within 30 days
    df = _subs(("C001", "2024-03-15", "2024-03-15", "basic", 30))
    result = compute_churn(df)
    assert result == [{"month": "2024-03", "churned_customers": 1}]


def test_churn_multiple_customers_same_month():
    df = _subs(
        ("C001", "2024-01-01", "2024-03-31", "basic", 30),
        ("C002", "2024-01-01", "2024-03-20", "pro", 50),
    )
    result = compute_churn(df)
    assert len(result) == 1
    assert result[0]["month"] == "2024-03"
    assert result[0]["churned_customers"] == 2


# ===== COHORT RETENTION =====

def test_cohort_basic_retention():
    customers = _customers(
        ("C001", "2024-01-05", "NL"),
        ("C002", "2024-01-10", "DE"),
        ("C003", "2024-01-20", "FR"),
    )
    # C001 and C002 still active at 2024-04-01 (target date)
    subs = _subs(
        ("C001", "2024-01-05", None, "basic", 30),
        ("C002", "2024-01-10", None, "basic", 25),
        ("C003", "2024-01-20", "2024-03-01", "basic", 20),  # churned before target
    )
    result = compute_cohort_retention(customers, subs)
    assert len(result) == 1
    r = result[0]
    assert r["cohort_month"] == "2024-01"
    assert r["cohort_size"] == 3
    assert r["active_after_3_months"] == 2
    assert r["retention_rate_3m"] == pytest.approx(0.6667, abs=1e-4)


def test_cohort_all_churned_before_3m():
    customers = _customers(("C001", "2024-01-01", "NL"))
    subs = _subs(("C001", "2024-01-01", "2024-02-28", "basic", 30))
    result = compute_cohort_retention(customers, subs)
    assert result[0]["active_after_3_months"] == 0
    assert result[0]["retention_rate_3m"] == 0.0


def test_cohort_resubscribed_exactly_at_3m_boundary():
    # Target date for Jan cohort = 2024-04-01
    # Customer re-subscribes on 2024-04-01 → counted as active
    customers = _customers(("C001", "2024-01-01", "NL"))
    subs = _subs(
        ("C001", "2024-01-01", "2024-03-15", "basic", 30),
        ("C001", "2024-04-01", None, "pro", 50),
    )
    result = compute_cohort_retention(customers, subs)
    assert result[0]["active_after_3_months"] == 1
    assert result[0]["retention_rate_3m"] == 1.0


def test_cohort_empty_customers():
    customers = _customers()
    subs = _subs(("C001", "2024-01-01", None, "basic", 30))
    result = compute_cohort_retention(customers, subs)
    assert result == []


def test_cohort_multiple_cohort_months():
    customers = _customers(
        ("C001", "2024-01-15", "NL"),
        ("C002", "2024-02-10", "DE"),
    )
    subs = _subs(
        ("C001", "2024-01-15", None, "basic", 30),
        ("C002", "2024-02-10", None, "basic", 25),
    )
    result = compute_cohort_retention(customers, subs)
    months = [r["cohort_month"] for r in result]
    assert "2024-01" in months
    assert "2024-02" in months
