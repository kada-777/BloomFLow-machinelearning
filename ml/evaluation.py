from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ml.models import FEATURE_COLUMNS, TARGET_COLUMNS, train_direct_models


def calculate_mae_and_wape(actual, predicted) -> Dict[str, float]:
    """Calculate mean absolute error and weighted absolute percentage error."""
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    absolute_error = np.abs(actual_values - predicted_values)
    total_actual = np.abs(actual_values).sum()
    wape = (
        absolute_error.sum() / total_actual if total_actual else float("inf")
    )
    return {
        "mae": float(absolute_error.mean()),
        "wape": float(wape),
    }


def split_chronologically(
    feature_data: pd.DataFrame,
    validation_days: int = 28,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split complete rows by date, keeping the newest dates for validation."""
    required_columns = {"date"} | set(FEATURE_COLUMNS) | set(TARGET_COLUMNS)
    missing_columns = sorted(set(required_columns) - set(feature_data.columns))
    if missing_columns:
        raise ValueError(
            "feature_data missing required columns: {}".format(", ".join(missing_columns))
        )
    if validation_days < 1:
        raise ValueError("validation_days must be greater than zero")

    usable = feature_data.dropna(subset=list(required_columns)).copy()
    usable["date"] = pd.to_datetime(usable["date"], errors="raise")
    dates = sorted(usable["date"].unique())
    if len(dates) <= validation_days:
        raise ValueError("not enough dates for the requested validation period")

    validation_start = dates[-validation_days]
    training = usable[usable["date"] < validation_start].reset_index(drop=True)
    validation = usable[usable["date"] >= validation_start].reset_index(drop=True)
    return training, validation


def evaluate_direct_models(
    feature_data: pd.DataFrame,
    validation_days: int = 28,
) -> Dict[str, Dict[str, float]]:
    """Train on earlier dates and report MAE/WAPE for each horizon."""
    training, validation = split_chronologically(feature_data, validation_days)
    models = train_direct_models(training)
    validation_features = validation[FEATURE_COLUMNS]

    metrics = {}
    for horizon, target in zip(["h1", "h2", "h3"], TARGET_COLUMNS):
        predictions = models[horizon].predict(validation_features)
        horizon_metrics = calculate_mae_and_wape(validation[target], predictions)
        horizon_metrics["rows"] = len(validation)
        metrics[horizon] = horizon_metrics
    return metrics


def evaluate_seven_day_baseline(
    feature_data: pd.DataFrame,
    validation_days: int = 28,
) -> Dict[str, Dict[str, float]]:
    """Evaluate a seven-day moving-average forecast for every horizon."""
    _, validation = split_chronologically(feature_data, validation_days)
    metrics = {}
    baseline_predictions = validation["rolling_mean_7"]
    for horizon, target in zip(["h1", "h2", "h3"], TARGET_COLUMNS):
        horizon_metrics = calculate_mae_and_wape(
            validation[target], baseline_predictions
        )
        horizon_metrics["rows"] = len(validation)
        metrics[horizon] = horizon_metrics
    return metrics
