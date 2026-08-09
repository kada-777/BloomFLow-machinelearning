from datetime import date, timedelta

import pandas as pd

from ml.features import add_forecast_targets, add_model_features
from ml.models import FEATURE_COLUMNS, TARGET_COLUMNS, prepare_training_data, train_direct_models


def make_feature_data(days=45):
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


def test_prepare_training_data_drops_rows_without_lags_or_future_targets():
    data = make_feature_data()

    features, targets = prepare_training_data(data)

    assert list(features.columns) == FEATURE_COLUMNS
    assert list(targets) == TARGET_COLUMNS
    assert len(features) == 14
    assert all(len(values) == 14 for values in targets.values())


def test_train_direct_models_returns_one_model_per_horizon():
    data = make_feature_data()

    models = train_direct_models(data)

    assert set(models) == {"h1", "h2", "h3"}
    predictions = models["h1"].predict(data.dropna()[FEATURE_COLUMNS].tail(2))
    assert len(predictions) == 2
    assert (predictions >= 0).all()
