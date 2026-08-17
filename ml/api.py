import json
import logging
import os
import sys
import time
from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from ml.data import (
    get_latest_sales_date,
    has_sufficient_sales_history,
    load_training_data,
)
from ml.features import add_forecast_targets, add_model_features, build_complete_sales_grid
from ml.models import train_direct_models
from ml.prediction import build_baseline_results, build_forecast_results
from ml.supabase_client import create_supabase_client


# Setup terminal logger
logger = logging.getLogger("bloomflow.api")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [BloomFlow Backend] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


app = FastAPI(title="BloomFlow Forecast Service", version="1.0.0")

DEFAULT_MINIMUM_HISTORY_DAYS = 28


def dump_model(model: BaseModel) -> dict:
    """Safely dump a Pydantic model for compatibility with v1 and v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.middleware("http")
async def log_incoming_requests(request: Request, call_next):
    """Log incoming request data passed from client/app to backend in terminal."""
    start_time = time.time()
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

    if body_str:
        try:
            parsed_json = json.loads(body_str)
            payload_info = f" | Data/Payload: {json.dumps(parsed_json, default=str)}"
        except Exception:
            payload_info = f" | Raw Data: {body_str}"
    else:
        query_params = str(request.query_params)
        if query_params:
            payload_info = f" | Query Params: {query_params}"
        else:
            payload_info = " | No Payload"

    client_host = request.client.host if request.client else "unknown"
    logger.info(
        f"Incoming Request from {client_host}: {request.method} {request.url.path}{payload_info}"
    )

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    request_with_body = Request(request.scope, receive=receive)

    try:
        response = await call_next(request_with_body)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Completed {request.method} {request.url.path} -> Status {response.status_code} ({duration_ms:.2f}ms)"
        )
        return response
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed {request.method} {request.url.path} -> Error: {exc} ({duration_ms:.2f}ms)"
        )
        raise


def get_minimum_history_days() -> int:
    """Read and validate the request-time minimum history configuration."""
    raw_value = os.getenv("MINIMUM_HISTORY_DAYS", str(DEFAULT_MINIMUM_HISTORY_DAYS))
    try:
        minimum_days = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("MINIMUM_HISTORY_DAYS must be a positive integer")
    if minimum_days < 1:
        raise ValueError("MINIMUM_HISTORY_DAYS must be a positive integer")
    return minimum_days


class EligiblePair(BaseModel):
    branchId: int = Field(gt=0)
    flowerId: int = Field(gt=0)


class ForecastRequest(BaseModel):
    forecastDate: Optional[date] = None
    modelVersion: str = "hgb-v1"
    eligiblePairs: Optional[List[EligiblePair]] = None


def get_training_tables():
    """Load read-only training tables for a forecast request."""
    return load_training_data(create_supabase_client())


def generate_forecast_payload(
    tables: dict,
    forecast_date: Optional[date] = None,
    model_version: str = "hgb-v1",
    eligible_pairs: Optional[List[dict]] = None,
) -> dict:
    """Run the forecast pipeline and return a JSON-ready response payload."""
    minimum_history_days = get_minimum_history_days()
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
        if eligible_pairs is not None:
            eligible_keys = {
                (pair["branchId"], pair["flowerId"])
                for pair in eligible_pairs
            }
            results = results[
                results[["branchId", "flowerId"]]
                .apply(tuple, axis=1)
                .isin(eligible_keys)
            ]
        return {
            "cutoffDate": cutoff_date,
            "forecastMethod": "BASELINE",
            "modelVersion": "baseline-v1",
            "results": results.to_dict(orient="records"),
        }

    if eligible_pairs is None and not has_sufficient_sales_history(
        tables["daily_sales"], minimum_history_days
    ):
        return build_baseline_payload(
            build_complete_sales_grid(tables, cutoff_date=cutoff_date)
        )

    sales_grid = build_complete_sales_grid(tables, cutoff_date=cutoff_date)
    if eligible_pairs is not None:
        eligible_keys = {
            (pair["branchId"], pair["flowerId"])
            for pair in eligible_pairs
        }
        sales_grid = sales_grid[
            sales_grid[["branchId", "flowerId"]]
            .apply(tuple, axis=1)
            .isin(eligible_keys)
        ].reset_index(drop=True)
        if sales_grid.empty:
            raise ValueError("eligiblePairs must contain at least one valid pair")
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
    req_dict = dump_model(request)
    logger.info("Handling /forecast request with data: %s", json.dumps(req_dict, default=str))
    try:
        eligible_pairs_list = (
            [dump_model(pair) for pair in request.eligiblePairs]
            if request.eligiblePairs is not None
            else None
        )
        result = generate_forecast_payload(
            tables,
            forecast_date=request.forecastDate,
            model_version=request.modelVersion,
            eligible_pairs=eligible_pairs_list,
        )
        logger.info(
            "Forecast completed: forecastMethod=%s, modelVersion=%s, result_count=%d",
            result.get("forecastMethod"),
            result.get("modelVersion"),
            len(result.get("results", [])),
        )
        return result
    except ValueError as error:
        logger.warning("Forecast validation error: %s", str(error))
        raise HTTPException(status_code=422, detail=str(error))

