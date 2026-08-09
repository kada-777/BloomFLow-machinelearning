from datetime import date
from typing import Optional

import pandas as pd

from ml.data import get_latest_sales_date, validate_required_columns


def build_complete_sales_grid(
    tables: dict,
    cutoff_date: Optional[date] = None,
) -> pd.DataFrame:
    """Create one zero-filled sales row for every date, branch, and flower."""
    daily_sales = tables["daily_sales"].copy()
    sales_items = tables["daily_sales_items"].copy()
    branches = tables["branches"].copy()
    flowers = tables["flowers"].copy()

    validate_required_columns(daily_sales, "daily_sales", {"id", "branchId", "salesDate"})
    validate_required_columns(
        sales_items,
        "daily_sales_items",
        {"dailySaleId", "flowerId", "soldQuantity", "damagedQuantity"},
    )
    validate_required_columns(branches, "branches", {"id"})
    validate_required_columns(flowers, "flowers", {"id"})

    daily_sales["date"] = pd.to_datetime(daily_sales["salesDate"], errors="coerce").dt.date
    if daily_sales["date"].isna().any():
        raise ValueError("daily_sales contains an invalid salesDate")

    end_date = cutoff_date or get_latest_sales_date(daily_sales)
    start_date = daily_sales["date"].min()
    if end_date < start_date:
        raise ValueError("cutoff_date cannot be before the first sales date")

    sales_items = sales_items.merge(
        daily_sales[["id", "branchId", "date"]],
        left_on="dailySaleId",
        right_on="id",
        how="inner",
        validate="many_to_one",
    )
    sales_items["soldQuantity"] = pd.to_numeric(
        sales_items["soldQuantity"], errors="raise"
    )
    sales_items["damagedQuantity"] = pd.to_numeric(
        sales_items["damagedQuantity"], errors="raise"
    )
    aggregated_sales = (
        sales_items.groupby(["date", "branchId", "flowerId"], as_index=False)[
            ["soldQuantity", "damagedQuantity"]
        ]
        .sum()
    )

    dates = pd.date_range(start_date, end_date, freq="D").date
    grid = pd.MultiIndex.from_product(
        [dates, branches["id"].tolist(), flowers["id"].tolist()],
        names=["date", "branchId", "flowerId"],
    ).to_frame(index=False)
    result = grid.merge(
        aggregated_sales,
        on=["date", "branchId", "flowerId"],
        how="left",
    )
    result[["soldQuantity", "damagedQuantity"]] = result[
        ["soldQuantity", "damagedQuantity"]
    ].fillna(0)
    return result.sort_values(["date", "branchId", "flowerId"]).reset_index(drop=True)


def add_model_features(sales_grid: pd.DataFrame) -> pd.DataFrame:
    """Add lag, shifted rolling, and calendar features to the sales grid."""
    validate_required_columns(
        sales_grid,
        "sales_grid",
        {"date", "branchId", "flowerId", "soldQuantity"},
    )
    result = sales_grid.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    result = result.sort_values(["branchId", "flowerId", "date"]).reset_index(drop=True)

    grouped_sales = result.groupby(["branchId", "flowerId"], sort=False)["soldQuantity"]
    for lag in [1, 2, 3, 7, 14, 28]:
        result["sales_lag_{}".format(lag)] = grouped_sales.shift(lag)

    for window in [3, 7, 14, 28]:
        result["rolling_mean_{}".format(window)] = grouped_sales.transform(
            lambda values: values.shift(1).rolling(window, min_periods=window).mean()
        )

    result["day_of_week"] = result["date"].dt.dayofweek
    result["month"] = result["date"].dt.month
    result["day_of_month"] = result["date"].dt.day
    result["is_weekend"] = result["day_of_week"].isin([5, 6]).astype(int)
    result["date"] = result["date"].dt.date
    return result


def add_forecast_targets(feature_data: pd.DataFrame) -> pd.DataFrame:
    """Add direct next-day, two-day, and three-day sales targets."""
    validate_required_columns(
        feature_data,
        "feature_data",
        {"date", "branchId", "flowerId", "soldQuantity"},
    )
    result = feature_data.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    result = result.sort_values(["branchId", "flowerId", "date"]).reset_index(drop=True)
    grouped_sales = result.groupby(["branchId", "flowerId"], sort=False)["soldQuantity"]
    for horizon in [1, 2, 3]:
        result["target_h{}".format(horizon)] = grouped_sales.shift(-horizon)
    result["date"] = result["date"].dt.date
    return result
