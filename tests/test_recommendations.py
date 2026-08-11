from datetime import date
from numbers import Integral

import pandas as pd

from ml.recommendations import build_recommendation_plan


def test_recommendation_projects_stock_across_three_same_day_shipments():
    forecasts = pd.DataFrame(
        {
            "date": [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)],
            "branchId": [1, 1, 1],
            "flowerId": [10, 10, 10],
            "forecastDemand": [15, 10, 8],
        }
    )
    inventory = pd.DataFrame(
        {
            "branchId": [1],
            "flowerId": [10],
            "currentUsableStock": [4],
            "inTransitStock": [2],
        }
    )

    result = build_recommendation_plan(forecasts, inventory, safety_stock=3)

    assert result["recommendedQuantity"].tolist() == [12, 10, 8]
    assert result["projectedEndingStock"].tolist() == [3, 3, 3]


def test_recommendation_is_zero_when_projected_stock_covers_need():
    forecasts = pd.DataFrame(
        {
            "date": [date(2025, 1, 1)],
            "branchId": [1],
            "flowerId": [10],
            "forecastDemand": [5],
        }
    )
    inventory = pd.DataFrame(
        {
            "branchId": [1],
            "flowerId": [10],
            "currentUsableStock": [10],
            "inTransitStock": [0],
        }
    )

    result = build_recommendation_plan(forecasts, inventory, safety_stock=3)

    assert result.loc[0, "recommendedQuantity"] == 0
    assert result.loc[0, "projectedEndingStock"] == 5


def test_recommendation_quantity_is_ceiled_to_whole_units():
    forecasts = pd.DataFrame(
        {
            "date": [date(2025, 1, 1)],
            "branchId": [1],
            "flowerId": [10],
            "forecastDemand": [12.25],
        }
    )
    inventory = pd.DataFrame(
        {
            "branchId": [1],
            "flowerId": [10],
            "currentUsableStock": [4],
            "inTransitStock": [2],
        }
    )

    result = build_recommendation_plan(forecasts, inventory, safety_stock=3)

    assert result.loc[0, "recommendedQuantity"] == 10
    assert isinstance(result.loc[0, "recommendedQuantity"], Integral)
    assert result.loc[0, "forecastDemand"] == 12.25
    assert result.loc[0, "projectedEndingStock"] == 3.75
