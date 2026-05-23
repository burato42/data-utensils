import pandas as pd
import pytest

from src.error_sink import RejectedRows, write_quarantine


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# RejectedRows
# ---------------------------------------------------------------------------

def test_rejected_rows_empty_by_default():
    r = RejectedRows(source="customers.csv")
    assert r.empty


def test_rejected_rows_add_tags_reason():
    r = RejectedRows(source="customers.csv")
    r.add(_frame([{"customer_id": "C001", "signup_date": "bad"}]), "invalid signup_date")
    assert not r.empty
    assert r.frames[0]["_rejection_reason"].iloc[0] == "invalid signup_date"


def test_rejected_rows_add_empty_frame_stays_empty():
    r = RejectedRows(source="customers.csv")
    r.add(pd.DataFrame(), "some reason")
    assert r.empty


def test_rejected_rows_add_multiple_reasons():
    r = RejectedRows(source="subscriptions.csv")
    r.add(_frame([{"customer_id": "C999"}]), "unknown customer_id")
    r.add(_frame([{"customer_id": "C001", "monthly_price": "free"}]), "non-numeric monthly_price")
    all_reasons = {row for f in r.frames for row in f["_rejection_reason"]}
    assert all_reasons == {"unknown customer_id", "non-numeric monthly_price"}


# ---------------------------------------------------------------------------
# write_quarantine
# ---------------------------------------------------------------------------

def test_write_quarantine_creates_run_dir_and_csv(tmp_path):
    r = RejectedRows(source="customers.csv")
    r.add(_frame([{"customer_id": "C001", "signup_date": "bad"}]), "invalid signup_date")
    run_dir = tmp_path / "quarantine" / "20240101T120000"
    write_quarantine([r], run_dir)
    out = run_dir / "customers_errors.csv"
    assert out.exists()
    df = pd.read_csv(out)
    assert "_rejection_reason" in df.columns
    assert list(df["customer_id"]) == ["C001"]


def test_write_quarantine_multiple_sources(tmp_path):
    rc = RejectedRows(source="customers.csv")
    rc.add(_frame([{"customer_id": "C001"}]), "invalid signup_date")
    rs = RejectedRows(source="subscriptions.csv")
    rs.add(_frame([{"customer_id": "C999"}]), "unknown customer_id")
    run_dir = tmp_path / "run"
    write_quarantine([rc, rs], run_dir)
    assert (run_dir / "customers_errors.csv").exists()
    assert (run_dir / "subscriptions_errors.csv").exists()


def test_write_quarantine_combines_multiple_rejection_reasons(tmp_path):
    r = RejectedRows(source="subscriptions.csv")
    r.add(_frame([{"customer_id": "C001"}]), "invalid start_date")
    r.add(_frame([{"customer_id": "C002"}]), "non-numeric monthly_price")
    run_dir = tmp_path / "run"
    write_quarantine([r], run_dir)
    df = pd.read_csv(run_dir / "subscriptions_errors.csv")
    assert len(df) == 2
    assert set(df["_rejection_reason"]) == {"invalid start_date", "non-numeric monthly_price"}


def test_write_quarantine_skips_empty_sources(tmp_path):
    r = RejectedRows(source="customers.csv")  # nothing added
    run_dir = tmp_path / "run"
    write_quarantine([r], run_dir)
    assert not run_dir.exists()


def test_write_quarantine_does_not_create_dir_when_nothing_rejected(tmp_path):
    run_dir = tmp_path / "quarantine" / "run1"
    write_quarantine([], run_dir)
    assert not run_dir.exists()


def test_write_quarantine_preserves_original_columns(tmp_path):
    r = RejectedRows(source="subscriptions.csv")
    r.add(
        _frame([{"customer_id": "C001", "start_date": "bad", "end_date": "", "plan": "basic", "monthly_price": "30"}]),
        "invalid start_date",
    )
    run_dir = tmp_path / "run"
    write_quarantine([r], run_dir)
    df = pd.read_csv(run_dir / "subscriptions_errors.csv")
    assert "customer_id" in df.columns
    assert "start_date" in df.columns
    assert "_rejection_reason" in df.columns
