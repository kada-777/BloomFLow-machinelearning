from datetime import date, datetime, timedelta, timezone

import pandas as pd

from ml.data import validate_required_columns
from ml.models import FEATURE_COLUMNS


def _build_metadata(feature_data, branches, flowers, cutoff_date):
    data = feature_data.copy()
    data["date"] = pd.to_datetime(data["date"], errors="raise").dt.date
    latest = data[data["date"].eq(cutoff_date)].copy()
    if latest.empty:
        raise ValueError("no feature rows found for cutoff_date")

    latest = latest.sort_values(["branchId", "flowerId"]).reset_index(drop=True)
    metadata = latest[["branchId", "flowerId"]].merge(
        branches[["id", "name"]].rename(columns={"id": "branchId", "name": "branchName"}),
        on="branchId",
        how="left",
        validate="many_to_one",
    ).merge(
        flowers[["id", "name"]].rename(columns={"id": "flowerId", "name": "flowerName"}),
        on="flowerId",
        how="left",
        validate="many_to_one",
    )
    if metadata[["branchName", "flowerName"]].isna().any().any():
        raise ValueError("prediction rows contain an unknown branch or flower")
    return data, metadata


def build_forecast_results(
    feature_data: pd.DataFrame,
    models: dict,
    branches: pd.DataFrame,
    flowers: pd.DataFrame,
    cutoff_date: date,
    model_version: str = "hgb-v1",
    model_name: str = "HistGradientBoostingRegressor",
    forecast_method: str = "ML",
) -> pd.DataFrame:
    """Pack direct model predictions with branch, flower, and forecast metadata."""
    for horizon in ["h1", "h2", "h3"]:
        if horizon not in models:
            raise ValueError("missing model for horizon {}".format(horizon))

    validate_required_columns(
        feature_data,
        "feature_data",
        {"date", "branchId", "flowerId"} | set(FEATURE_COLUMNS),
    )
    validate_required_columns(branches, "branches", {"id", "name"})
    validate_required_columns(flowers, "flowers", {"id", "name"})

    data, metadata = _build_metadata(feature_data, branches, flowers, cutoff_date)
    latest = data[data["date"].eq(cutoff_date)].copy()

    generated_at = datetime.now(timezone.utc).isoformat()
    result_frames = []
    for horizon_number, horizon in enumerate(["h1", "h2", "h3"], start=1):
        predictions = models[horizon].predict(latest[FEATURE_COLUMNS])
        frame = metadata.copy()
        frame["forecastDate"] = cutoff_date + timedelta(days=horizon_number)
        frame["horizon"] = horizon_number
        frame["forecastDemand"] = pd.Series(predictions, index=frame.index).clip(lower=0)
        frame["forecastMethod"] = forecast_method
        frame["modelName"] = model_name
        frame["modelVersion"] = model_version
        frame["generatedAt"] = generated_at
        result_frames.append(frame)

    return pd.concat(result_frames, ignore_index=True).sort_values(
        ["forecastDate", "branchId", "flowerId"]
    ).reset_index(drop=True)


def build_baseline_results(
    sales_grid: pd.DataFrame,
    branches: pd.DataFrame,
    flowers: pd.DataFrame,
    cutoff_date: date,
    model_version: str = "baseline-v1",
    window: int = 7,
    model_name: str = "SevenDayMovingAverage",
    forecast_method: str = "BASELINE",
) -> pd.DataFrame:
    """Build one seven-day moving-average forecast for each direct horizon."""
    validate_required_columns(
        sales_grid,
        "sales_grid",
        {"date", "branchId", "flowerId", "soldQuantity"},
    )
    if window < 1:
        raise ValueError("window must be positive")

    data, metadata = _build_metadata(sales_grid, branches, flowers, cutoff_date)
    recent = (
        data[data["date"] <= cutoff_date]
        .sort_values(["branchId", "flowerId", "date"])
        .groupby(["branchId", "flowerId"], sort=False)
        .tail(window)
    )
    averages = recent.groupby(["branchId", "flowerId"], as_index=False)["soldQuantity"].mean()
    averages = averages.rename(columns={"soldQuantity": "forecastDemand"})
    metadata = metadata.merge(averages, on=["branchId", "flowerId"], how="left")
    metadata["forecastDemand"] = metadata["forecastDemand"].fillna(0).clip(lower=0)

    generated_at = datetime.now(timezone.utc).isoformat()
    result_frames = []
    for horizon in [1, 2, 3]:
        frame = metadata.copy()
        frame["forecastDate"] = cutoff_date + timedelta(days=horizon)
        frame["horizon"] = horizon
        frame["forecastMethod"] = forecast_method
        frame["modelName"] = model_name
        frame["modelVersion"] = model_version
        frame["generatedAt"] = generated_at
        result_frames.append(frame)

    return pd.concat(result_frames, ignore_index=True).sort_values(
        ["forecastDate", "branchId", "flowerId"]
    ).reset_index(drop=True)
