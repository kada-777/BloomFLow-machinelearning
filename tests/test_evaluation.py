from datetime import date, timedelta

import pandas as pd
import pytest

from ml.evaluation import (
    calculate_mae_and_wape,
    evaluate_seven_day_baseline,
    evaluate_direct_models,
    split_chronologically,
)
from ml.features import add_forecast_targets, add_model_features


def make_feature_data(days=90):
    grid = pd.DataFrame(
        {
            "date": [date(2024, 1, 1) + timedelta(days=day) for day in range(days)],
            "branchId": [1] * days,
            "flowerId": [10] * days,
            "soldQuantity": [day % 10 for day in range(days)],
            "damagedQuantity": [0] * days,
        }
    )
    return add_forecast_targets(add_model_features(grid))


def test_calculate_mae_and_wape():
    metrics = calculate_mae_and_wape(
        actual=[10, 20, 0],
        predicted=[8, 25, 0],
    )

    assert metrics["mae"] == pytest.approx(7 / 3)
    assert metrics["wape"] == pytest.approx(7 / 30)


def test_split_chronologically_keeps_validation_after_training():
    data = make_feature_data()

    training, validation = split_chronologically(data, validation_days=7)

    assert training["date"].max() < validation["date"].min()
    assert len(validation["date"].unique()) == 7


def test_evaluate_direct_models_returns_metrics_for_each_horizon():
    metrics = evaluate_direct_models(make_feature_data(), validation_days=7)

    assert set(metrics) == {"h1", "h2", "h3"}
    assert all("mae" in values and "wape" in values for values in metrics.values())


def test_evaluate_seven_day_baseline_returns_metrics_for_each_horizon():
    metrics = evaluate_seven_day_baseline(make_feature_data(), validation_days=7)

    assert set(metrics) == {"h1", "h2", "h3"}
    assert all("mae" in values and "wape" in values for values in metrics.values())
