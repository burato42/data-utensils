import textwrap
import pytest

from src.reader import read_customers, read_subscriptions


def test_missing_customers_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        read_customers(str(tmp_path / "nonexistent.csv"))


def test_missing_subscriptions_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        read_subscriptions(str(tmp_path / "nonexistent.csv"))


def test_missing_column_in_customers_exits(tmp_path):
    csv = tmp_path / "customers.csv"
    csv.write_text("customer_id,signup_date\nC001,2024-01-01\n")
    with pytest.raises(SystemExit):
        read_customers(str(csv))


def test_missing_column_in_subscriptions_exits(tmp_path):
    csv = tmp_path / "subscriptions.csv"
    csv.write_text("customer_id,start_date\nC001,2024-01-01\n")
    with pytest.raises(SystemExit):
        read_subscriptions(str(csv))


def test_valid_customers_loads(tmp_path):
    csv = tmp_path / "customers.csv"
    csv.write_text("customer_id,signup_date,country\nC001,2024-01-01,NL\n")
    df = read_customers(str(csv))
    assert len(df) == 1
    assert df.iloc[0]["customer_id"] == "C001"
