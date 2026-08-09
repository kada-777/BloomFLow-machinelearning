from datetime import date, timedelta

import pandas as pd
import pytest

from ml.features import add_forecast_targets, add_model_features


def test_model_features_use_previous_sales_for_lags_and_rollings():
    start = date(2024, 1, 1)
    sales_grid = pd.DataFrame(
        {
            "date": [start + timedelta(days=day) for day in range(30)],
            "branchId": [1] * 30,
            "flowerId": [10] * 30,
            "soldQuantity": list(range(1, 30)) + [100],
            "damagedQuantity": [0] * 30,
        }
    )

    result = add_model_features(sales_grid)
    row = result[result["date"] == date(2024, 1, 30)].iloc[0]

    assert row["sales_lag_1"] == 29
    assert row["sales_lag_2"] == 28
    assert row["sales_lag_7"] == 23
    assert row["rolling_mean_3"] == 28
    assert row["rolling_mean_7"] == 26


def test_model_features_add_calendar_columns():
    sales_grid = pd.DataFrame(
        {
            "date": [date(2024, 1, 6)],
            "branchId": [1],
            "flowerId": [10],
            "soldQuantity": [4],
            "damagedQuantity": [0],
        }
    )

    result = add_model_features(sales_grid)

    assert result.loc[0, "day_of_week"] == 5
    assert result.loc[0, "month"] == 1
    assert result.loc[0, "day_of_month"] == 6
    assert result.loc[0, "is_weekend"] == 1


def test_forecast_targets_use_future_sales_within_each_series():
    sales_grid = pd.DataFrame(
        {
            "date": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
            ],
            "branchId": [1, 1, 1, 2, 2, 2],
            "flowerId": [10, 10, 10, 10, 10, 10],
            "soldQuantity": [5, 6, 7, 50, 60, 70],
        }
    )

    result = add_forecast_targets(sales_grid)
    first_branch = result[result["branchId"] == 1].sort_values("date")

    assert first_branch.iloc[0]["target_h1"] == 6
    assert first_branch.iloc[0]["target_h2"] == 7
    assert pd.isna(first_branch.iloc[0]["target_h3"])
    assert pd.isna(first_branch.iloc[2]["target_h1"])


def test_forecast_targets_require_sales_columns():
    with pytest.raises(ValueError, match="missing required columns: soldQuantity"):
        add_forecast_targets(
            pd.DataFrame(
                {"date": [date(2024, 1, 1)], "branchId": [1], "flowerId": [10]}
            )
        )
