from datetime import date, timedelta

import pandas as pd
import pytest

from fastapi import HTTPException
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


def test_generate_forecast_payload_returns_only_eligible_pairs():
    payload = generate_forecast_payload(
        make_tables(),
        eligible_pairs=[{"branchId": 1, "flowerId": 10}],
    )

    assert len(payload["results"]) == 3
    assert {(row["branchId"], row["flowerId"]) for row in payload["results"]} == {(1, 10)}


def test_eligible_pairs_bypass_global_history_gate(monkeypatch):
    monkeypatch.setenv("MINIMUM_HISTORY_DAYS", "100")

    payload = generate_forecast_payload(
        make_tables(),
        eligible_pairs=[{"branchId": 1, "flowerId": 10}],
    )

    assert payload["forecastMethod"] == "ML"
    assert len(payload["results"]) == 3


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

    payload = generate_forecast_payload(make_tables(days=10))

    assert payload["forecastMethod"] == "BASELINE"


def test_minimum_history_days_can_be_configured(monkeypatch):
    monkeypatch.setenv("MINIMUM_HISTORY_DAYS", "46")

    payload = generate_forecast_payload(make_tables(days=45))

    assert payload["forecastMethod"] == "BASELINE"
    assert payload["modelVersion"] == "baseline-v1"


def test_invalid_minimum_history_days_returns_http_422(monkeypatch):
    monkeypatch.setenv("MINIMUM_HISTORY_DAYS", "not-an-integer")

    with pytest.raises(HTTPException) as error:
        forecast(ForecastRequest(), make_tables())

    assert error.value.status_code == 422
    assert "MINIMUM_HISTORY_DAYS" in error.value.detail


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


def test_forecast_logs_request_data_to_terminal(caplog):
    import logging
    tables = make_tables()
    req = ForecastRequest(modelVersion="hgb-v1")
    with caplog.at_level(logging.INFO):
        response = forecast(req, tables)

    assert response["forecastMethod"] == "ML"
    assert "Handling /forecast request with data:" in caplog.text
    assert "hgb-v1" in caplog.text


@pytest.mark.anyio
async def test_middleware_logs_incoming_requests_to_terminal(caplog):
    import logging
    import httpx
    from ml.api import app, get_training_tables

    tables = make_tables()
    app.dependency_overrides[get_training_tables] = lambda: tables

    transport = httpx.ASGITransport(app=app)
    with caplog.at_level(logging.INFO):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/forecast",
                json={"modelVersion": "hgb-v1"},
            )
            assert response.status_code == 200

    app.dependency_overrides.clear()
    assert "Incoming Request from" in caplog.text
    assert "POST /forecast" in caplog.text
    assert "hgb-v1" in caplog.text
    assert "Completed POST /forecast -> Status 200" in caplog.text

