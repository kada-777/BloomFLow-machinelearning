from datetime import date, timedelta

import pandas as pd

from ml.api import ForecastRequest, generate_forecast_payload, forecast


def make_tables(days=45):
    dates = [date(2024, 1, 1) + timedelta(days=day) for day in range(days)]
    daily_sales = []
    sales_items = []
    sale_id = 1
    item_id = 1
    for sales_date in dates:
        for branch_id in [1, 2]:
            daily_sales.append(
                {"id": sale_id, "branchId": branch_id, "salesDate": sales_date}
            )
            for flower_id in [10, 20]:
                sales_items.append(
                    {
                        "id": item_id,
                        "dailySaleId": sale_id,
                        "flowerId": flower_id,
                        "soldQuantity": (sale_id + flower_id) % 10,
                        "damagedQuantity": 0,
                    }
                )
                item_id += 1
            sale_id += 1

    empty = pd.DataFrame()
    return {
        "daily_sales": pd.DataFrame(daily_sales),
        "daily_sales_items": pd.DataFrame(sales_items),
        "branches": pd.DataFrame({"id": [1, 2], "name": ["Central", "North"]}),
        "flowers": pd.DataFrame({"id": [10, 20], "name": ["Rose", "Tulip"]}),
        "branch_stock_lots": empty,
        "flower_batches": empty,
        "distribution_orders": empty,
        "distribution_batch_allocations": empty,
        "inventory_movements": empty,
        "distribution_receipts": empty,
    }


def test_generate_forecast_payload_returns_api_ready_results():
    payload = generate_forecast_payload(make_tables())

    assert payload["forecastMethod"] == "ML"
    assert payload["modelVersion"] == "hgb-v1"
    assert len(payload["results"]) == 12
    assert {row["horizon"] for row in payload["results"]} == {1, 2, 3}


def test_generate_forecast_payload_uses_baseline_for_insufficient_history():
    payload = generate_forecast_payload(make_tables(days=10))

    assert payload["forecastMethod"] == "BASELINE"
    assert payload["modelVersion"] == "baseline-v1"
    assert len(payload["results"]) == 12
    assert {row["forecastMethod"] for row in payload["results"]} == {"BASELINE"}


def test_insufficient_history_skips_training(monkeypatch):
    def fail_training(_feature_data):
        raise AssertionError("training should not run")

    monkeypatch.setattr("ml.api.train_direct_models", fail_training)
    monkeypatch.setattr("ml.api.MINIMUM_HISTORY_DAYS", 28)

    payload = generate_forecast_payload(make_tables(days=10))

    assert payload["forecastMethod"] == "BASELINE"


def test_minimum_history_days_can_be_configured(monkeypatch):
    monkeypatch.setattr("ml.api.MINIMUM_HISTORY_DAYS", 46)

    payload = generate_forecast_payload(make_tables(days=45))

    assert payload["forecastMethod"] == "BASELINE"
    assert payload["modelVersion"] == "baseline-v1"


def test_forecast_endpoint_returns_forecast_payload():
    tables = make_tables()
    response = forecast(ForecastRequest(), tables)

    assert response["forecastMethod"] == "ML"
    assert len(response["results"]) == 12


def test_generate_forecast_payload_falls_back_to_baseline_when_training_fails(monkeypatch):
    def fail_training(_feature_data):
        raise ValueError("not enough training rows")

    monkeypatch.setattr("ml.api.train_direct_models", fail_training)

    payload = generate_forecast_payload(make_tables())

    assert payload["forecastMethod"] == "BASELINE"
    assert payload["modelVersion"] == "baseline-v1"
    assert len(payload["results"]) == 12
    assert {row["forecastMethod"] for row in payload["results"]} == {"BASELINE"}
