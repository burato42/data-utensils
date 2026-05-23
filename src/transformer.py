from datetime import date, timedelta

import pandas as pd
from dateutil.relativedelta import relativedelta


def compute_mrr(subscriptions: pd.DataFrame) -> list[dict]:
    """
    Compute Monthly Recurring Revenue for each calendar month.

    A subscription is active in month M if:
      start_date <= last day of M  AND  (end_date is NaT OR end_date >= first day of M)

    Returns list of {"month": "YYYY-MM", "mrr": float} sorted by month.
    """
    if subscriptions.empty:
        return []

    today = pd.Timestamp(date.today())
    end_dates_filled = subscriptions["end_date"].fillna(today)

    min_month = subscriptions["start_date"].min().to_period("M")
    max_month = end_dates_filled.max().to_period("M")

    results = []
    period = min_month
    while period <= max_month:
        first_day = period.to_timestamp()
        last_day = (period + 1).to_timestamp() - timedelta(days=1)

        active = (subscriptions["start_date"] <= last_day) & (
            subscriptions["end_date"].isna() | (subscriptions["end_date"] >= first_day)
        )
        mrr = subscriptions.loc[active, "monthly_price"].sum()
        results.append({"month": str(period), "mrr": round(float(mrr), 2)})
        period += 1

    return results


def compute_churn(subscriptions: pd.DataFrame) -> list[dict]:
    """
    Count churned customers per calendar month.

    A churn event occurs when a subscription has an end_date AND the customer
    has no subscription starting within 30 days after that end_date (inclusive:
    new_start <= end_date + 30 days is NOT a churn). The event is attributed to
    the calendar month of end_date.

    Returns list of {"month": "YYYY-MM", "churned_customers": int} sorted by month,
    only including months with at least one churn.
    """
    ended = subscriptions[subscriptions["end_date"].notna()].copy()
    if ended.empty:
        return []

    churn_months: dict[str, int] = {}

    for _, row in ended.iterrows():
        cid = row["customer_id"]
        end_date = row["end_date"]
        window_end = end_date + timedelta(days=30)

        # Check if any subscription for this customer starts within 30 days
        customer_subs = subscriptions[subscriptions["customer_id"] == cid]
        resubscribed = (customer_subs["start_date"] > end_date) & (
            customer_subs["start_date"] <= window_end
        )
        if not resubscribed.any():
            month_key = str(end_date.to_period("M"))
            churn_months[month_key] = churn_months.get(month_key, 0) + 1

    return [{"month": m, "churned_customers": c} for m, c in sorted(churn_months.items())]


def compute_cohort_retention(
    customers: pd.DataFrame,
    subscriptions: pd.DataFrame,
) -> list[dict]:
    """
    Compute 3-month retention by signup cohort.

    Customers are grouped by the year-month of signup_date. For each cohort:
      - cohort_size: number of customers in the cohort
      - active_after_3_months: customers with any subscription active on the target date
        (first day of cohort_month + 3 calendar months)
      - retention_rate_3m: active_after_3_months / cohort_size, rounded to 4 decimal places

    A customer is active at the target date if they have a subscription where:
      start_date <= target_date  AND  (end_date is NaT OR end_date >= target_date)

    Returns list of cohort dicts sorted by cohort_month.
    """
    if customers.empty:
        return []

    customers = customers.copy()
    customers["cohort_month"] = customers["signup_date"].dt.to_period("M")

    results = []
    for cohort_period, group in customers.groupby("cohort_month"):
        cohort_size = len(group)
        # Target date: first day of the month that is 3 calendar months after cohort start
        cohort_start = cohort_period.to_timestamp()
        target_date = cohort_start + relativedelta(months=3)
        target_ts = pd.Timestamp(target_date)

        cohort_customer_ids = set(group["customer_id"])
        cohort_subs = subscriptions[subscriptions["customer_id"].isin(cohort_customer_ids)]

        active_mask = (cohort_subs["start_date"] <= target_ts) & (
            cohort_subs["end_date"].isna() | (cohort_subs["end_date"] >= target_ts)
        )
        active_customers = cohort_subs.loc[active_mask, "customer_id"].nunique()

        retention = round(active_customers / cohort_size, 4) if cohort_size > 0 else 0.0

        results.append(
            {
                "cohort_month": str(cohort_period),
                "cohort_size": cohort_size,
                "active_after_3_months": int(active_customers),
                "retention_rate_3m": retention,
            }
        )

    return results
