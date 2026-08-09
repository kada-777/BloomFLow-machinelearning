import pandas as pd
import pytest
from pathlib import Path

from ml.data import (
    get_latest_sales_date,
    load_training_data,
    profile_training_data,
    validate_required_columns,
)
from ml.supabase_client import load_settings


def test_latest_sales_date_uses_latest_observed_date():
    daily_sales = pd.DataFrame(
        {
            "salesDate": ["2024-01-02", "2024-01-04", "2024-01-03"],
        }
    )

    assert get_latest_sales_date(daily_sales) == pd.Timestamp("2024-01-04").date()


def test_latest_sales_date_rejects_empty_sales_data():
    with pytest.raises(ValueError, match="daily sales data is empty"):
        get_latest_sales_date(pd.DataFrame({"salesDate": []}))


def test_required_columns_reports_missing_columns():
    data = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError, match="missing required columns: branchId, salesDate"):
        validate_required_columns(data, "daily_sales", {"salesDate", "branchId"})


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.requested_ranges = []

    def select(self, _columns):
        return self

    def range(self, start, end):
        self.requested_ranges.append((start, end))
        return self

    def execute(self):
        start, end = self.requested_ranges[-1]
        return type("Response", (), {"data": self.rows[start : end + 1]})()


class FakeSupabaseClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, table_name):
        return FakeQuery(self.tables[table_name])


def test_load_training_data_reads_all_required_tables_in_pages():
    client = FakeSupabaseClient(
        {
            "daily_sales": [{"id": 1}, {"id": 2}],
            "daily_sales_items": [{"id": 3}],
            "branch_stock_lots": [],
            "flower_batches": [],
            "distribution_orders": [],
            "distribution_batch_allocations": [],
            "inventory_movements": [],
            "distribution_receipts": [],
            "branches": [{"id": 10}],
            "flowers": [{"id": 20}],
        }
    )

    result = load_training_data(client, page_size=1)

    assert set(result) == {
        "daily_sales",
        "daily_sales_items",
        "branch_stock_lots",
        "flower_batches",
        "distribution_orders",
        "distribution_batch_allocations",
        "inventory_movements",
        "distribution_receipts",
        "branches",
        "flowers",
    }
    assert result["daily_sales"].shape[0] == 2
    assert result["branches"].iloc[0]["id"] == 10


def test_load_settings_reads_supabase_credentials_from_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/rest/v1/")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")

    settings = load_settings()

    assert settings.url == "https://example.supabase.co"
    assert settings.key == "test-key"


def test_load_settings_rejects_missing_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_KEY are required"):
        load_settings(dotenv_path=Path("missing-test.env"))


def test_profile_training_data_reports_counts_and_sales_date_range():
    tables = {
        "daily_sales": pd.DataFrame(
            {"salesDate": ["2024-01-01", "2024-01-03"]}
        ),
        "branches": pd.DataFrame({"id": [1, 2]}),
        "flowers": pd.DataFrame({"id": [10]}),
    }

    profile = profile_training_data(tables)

    assert profile["row_counts"] == {
        "daily_sales": 2,
        "branches": 2,
        "flowers": 1,
    }
    assert profile["sales_start"] == pd.Timestamp("2024-01-01").date()
    assert profile["sales_end"] == pd.Timestamp("2024-01-03").date()
