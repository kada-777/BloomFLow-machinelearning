from datetime import date
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from ml.data import (
    get_latest_sales_date,
    has_sufficient_sales_history,
    load_training_data,
)
from ml.features import add_forecast_targets, add_model_features, build_complete_sales_grid
from ml.models import train_direct_models
from ml.prediction import build_baseline_results, build_forecast_results
from ml.supabase_client import create_supabase_client


app = FastAPI(title="BloomFlow Forecast Service", version="1.0.0")

DEFAULT_MINIMUM_HISTORY_DAYS = 28
MINIMUM_HISTORY_DAYS = int(
    os.getenv("MINIMUM_HISTORY_DAYS", str(DEFAULT_MINIMUM_HISTORY_DAYS))
)
if MINIMUM_HISTORY_DAYS < 1:
    raise ValueError("MINIMUM_HISTORY_DAYS must be greater than zero")


class ForecastRequest(BaseModel):
    forecastDate: Optional[date] = None
    modelVersion: str = "hgb-v1"


def get_training_tables():
    """Load read-only training tables for a forecast request."""
    return load_training_data(create_supabase_client())


def generate_forecast_payload(
    tables: dict,
    forecast_date: Optional[date] = None,
    model_version: str = "hgb-v1",
) -> dict:
    """Run the forecast pipeline and return a JSON-ready response payload."""
    latest_observed_date = get_latest_sales_date(tables["daily_sales"])
    cutoff_date = forecast_date or latest_observed_date
    if cutoff_date > latest_observed_date:
        raise ValueError("forecastDate cannot be after the latest observed sales date")

    def build_baseline_payload(sales_grid):
        results = build_baseline_results(
            sales_grid,
            tables["branches"],
            tables["flowers"],
            cutoff_date=cutoff_date,
        )
        return {
            "cutoffDate": cutoff_date,
            "forecastMethod": "BASELINE",
            "modelVersion": "baseline-v1",
            "results": results.to_dict(orient="records"),
        }

    if not has_sufficient_sales_history(
        tables["daily_sales"], MINIMUM_HISTORY_DAYS
    ):
        return build_baseline_payload(
            build_complete_sales_grid(tables, cutoff_date=cutoff_date)
        )

    sales_grid = build_complete_sales_grid(tables, cutoff_date=cutoff_date)
    feature_data = add_forecast_targets(add_model_features(sales_grid))
    try:
        models = train_direct_models(feature_data)
    except ValueError:
        return build_baseline_payload(sales_grid)

    results = build_forecast_results(
        feature_data,
        models,
        tables["branches"],
        tables["flowers"],
        cutoff_date=cutoff_date,
        model_version=model_version,
    )
    return {
        "cutoffDate": cutoff_date,
        "forecastMethod": "ML",
        "modelVersion": model_version,
        "results": results.to_dict(orient="records"),
    }


@app.post("/forecast")
def forecast(
    request: ForecastRequest,
    tables: dict = Depends(get_training_tables),
):
    """Generate forecasts without writing inventory or forecast records."""
    try:
        return generate_forecast_payload(
            tables,
            forecast_date=request.forecastDate,
            model_version=request.modelVersion,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
