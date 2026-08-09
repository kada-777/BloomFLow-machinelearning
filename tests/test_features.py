from datetime import date

import pandas as pd

from ml.features import build_complete_sales_grid


def test_complete_sales_grid_contains_every_date_branch_and_flower():
    tables = {
        "daily_sales": pd.DataFrame(
            {
                "id": [1, 2],
                "branchId": [1, 2],
                "salesDate": ["2024-01-01", "2024-01-02"],
            }
        ),
        "daily_sales_items": pd.DataFrame(
            {
                "dailySaleId": [1, 2],
                "flowerId": [10, 20],
                "soldQuantity": [4, 7],
                "damagedQuantity": [1, 0],
            }
        ),
        "branches": pd.DataFrame({"id": [1, 2]}),
        "flowers": pd.DataFrame({"id": [10, 20]}),
    }

    result = build_complete_sales_grid(tables)

    assert len(result) == 8
    assert set(result.columns) == {
        "date",
        "branchId",
        "flowerId",
        "soldQuantity",
        "damagedQuantity",
    }

    missing_row = result[
        (result["date"] == date(2024, 1, 1))
        & (result["branchId"] == 2)
        & (result["flowerId"] == 20)
    ].iloc[0]
    assert missing_row["soldQuantity"] == 0
    assert missing_row["damagedQuantity"] == 0


def test_complete_sales_grid_respects_cutoff_date():
    tables = {
        "daily_sales": pd.DataFrame(
            {
                "id": [1, 2],
                "branchId": [1, 1],
                "salesDate": ["2024-01-01", "2024-01-02"],
            }
        ),
        "daily_sales_items": pd.DataFrame(
            columns=["dailySaleId", "flowerId", "soldQuantity", "damagedQuantity"]
        ),
        "branches": pd.DataFrame({"id": [1]}),
        "flowers": pd.DataFrame({"id": [10]}),
    }

    result = build_complete_sales_grid(tables, cutoff_date=date(2024, 1, 1))

    assert result["date"].tolist() == [date(2024, 1, 1)]
