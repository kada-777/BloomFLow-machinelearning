from math import ceil
from typing import Union

import pandas as pd

from ml.data import validate_required_columns


def build_recommendation_plan(
    forecasts: pd.DataFrame,
    inventory_snapshot: pd.DataFrame,
    safety_stock: Union[int, float],
) -> pd.DataFrame:
    """Calculate same-day shipment needs across the forecast horizon."""
    validate_required_columns(
        forecasts,
        "forecasts",
        {"date", "branchId", "flowerId", "forecastDemand"},
    )
    validate_required_columns(
        inventory_snapshot,
        "inventory_snapshot",
        {"branchId", "flowerId", "currentUsableStock", "inTransitStock"},
    )
    if safety_stock < 0:
        raise ValueError("safety_stock cannot be negative")

    result = forecasts.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.date
    result["forecastDemand"] = pd.to_numeric(result["forecastDemand"], errors="raise")
    if result["forecastDemand"].lt(0).any():
        raise ValueError("forecastDemand cannot be negative")
    result = result.sort_values(["date", "branchId", "flowerId"]).reset_index(drop=True)

    inventory = inventory_snapshot.copy()
    inventory["currentUsableStock"] = pd.to_numeric(
        inventory["currentUsableStock"], errors="raise"
    )
    inventory["inTransitStock"] = pd.to_numeric(
        inventory["inTransitStock"], errors="raise"
    )
    inventory_by_pair = inventory.set_index(["branchId", "flowerId"])
    projected_stock = {}
    opening_stock_values = []
    recommendations = []
    ending_stock = []

    for row in result.itertuples(index=False):
        pair = (row.branchId, row.flowerId)
        if pair not in projected_stock:
            if pair in inventory_by_pair.index:
                inventory_row = inventory_by_pair.loc[pair]
                projected_stock[pair] = (
                    inventory_row["currentUsableStock"]
                    + inventory_row["inTransitStock"]
                )
            else:
                projected_stock[pair] = 0.0

        opening_stock = projected_stock[pair]
        opening_stock_values.append(opening_stock)
        required_stock = row.forecastDemand + safety_stock
        recommendation = ceil(max(0.0, required_stock - opening_stock))
        closing_stock = opening_stock + recommendation - row.forecastDemand
        projected_stock[pair] = closing_stock
        recommendations.append(recommendation)
        ending_stock.append(closing_stock)

    result["safetyStock"] = float(safety_stock)
    result["projectedOpeningStock"] = opening_stock_values
    result["recommendedQuantity"] = recommendations
    result["projectedEndingStock"] = ending_stock
    return result
