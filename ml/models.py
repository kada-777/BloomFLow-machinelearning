from typing import Dict, Optional

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


FEATURE_COLUMNS = [
    "branchId",
    "flowerId",
    "sales_lag_1",
    "sales_lag_2",
    "sales_lag_3",
    "sales_lag_7",
    "sales_lag_14",
    "sales_lag_28",
    "rolling_mean_3",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "day_of_week",
    "month",
    "day_of_month",
    "is_weekend",
]

TARGET_COLUMNS = ["target_h1", "target_h2", "target_h3"]

DEFAULT_MODEL_PARAMS = {
    "loss": "poisson",
    "learning_rate": 0.05,
    "max_iter": 300,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "random_state": 42,
}


def prepare_training_data(feature_data: pd.DataFrame):
    """Keep only rows with complete features and all three future targets."""
    required_columns = FEATURE_COLUMNS + TARGET_COLUMNS
    missing_columns = sorted(set(required_columns) - set(feature_data.columns))
    if missing_columns:
        raise ValueError(
            "feature_data missing required columns: {}".format(", ".join(missing_columns))
        )

    usable = feature_data.dropna(subset=required_columns).copy()
    features = usable[FEATURE_COLUMNS].reset_index(drop=True)
    targets = {
        target: usable[target].reset_index(drop=True) for target in TARGET_COLUMNS
    }
    return features, targets


def train_direct_models(
    feature_data: pd.DataFrame,
    model_params: Optional[dict] = None,
) -> Dict[str, HistGradientBoostingRegressor]:
    """Train independent direct models for one-, two-, and three-day horizons."""
    features, targets = prepare_training_data(feature_data)
    params = dict(DEFAULT_MODEL_PARAMS)
    if model_params:
        params.update(model_params)

    models = {}
    for horizon, target in zip(["h1", "h2", "h3"], TARGET_COLUMNS):
        model = HistGradientBoostingRegressor(**params)
        model.fit(features, targets[target])
        models[horizon] = model
    return models
