from datetime import date

import pandas as pd
import pytest

from ml.models import FEATURE_COLUMNS
from ml.prediction import build_forecast_results


class FakeModel:
    def __init__(self, values):
        self.values = values

    def predict(self, _features):
        return self.values


def test_build_forecast_results_matches_branch_and_flower_metadata():
    latest_features = pd.DataFrame(
        {
            "date": [date(2025, 6, 30), date(2025, 6, 30)],
            "branchId": [1, 2],
            "flowerId": [10, 10],
            **{column: [1.0, 2.0] for column in FEATURE_COLUMNS if column not in {"branchId", "flowerId"}},
        }
    )
    branches = pd.DataFrame({"id": [1, 2], "name": ["Central", "North"]})
    flowers = pd.DataFrame({"id": [10], "name": ["Rose Red"]})
    models = {
        "h1": FakeModel([12.0, 8.0]),
        "h2": FakeModel([10.0, 7.0]),
        "h3": FakeModel([9.0, 6.0]),
    }

    result = build_forecast_results(
        latest_features,
        models,
        branches,
        flowers,
        cutoff_date=date(2025, 6, 30),
        model_version="hgb-v1",
    )

    assert len(result) == 6
    assert set(result["branchName"]) == {"Central", "North"}
    assert set(result["flowerName"]) == {"Rose Red"}
    assert result[result["horizon"] == 1]["forecastDemand"].tolist() == [12.0, 8.0]
    assert result[result["horizon"] == 1]["forecastDate"].tolist() == [
        date(2025, 7, 1),
        date(2025, 7, 1),
    ]
    assert set(result["modelVersion"]) == {"hgb-v1"}


def test_build_forecast_results_rejects_missing_model_horizon():
    with pytest.raises(ValueError, match="missing model for horizon h3"):
        build_forecast_results(
            pd.DataFrame(),
            {"h1": FakeModel([]), "h2": FakeModel([])},
            pd.DataFrame(),
            pd.DataFrame(),
            cutoff_date=date(2025, 6, 30),
        )
