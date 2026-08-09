from datetime import date, timedelta

import pandas as pd

from ml.inventory import build_inventory_snapshot


def test_inventory_snapshot_excludes_damaged_lots_and_includes_in_transit_allocations():
    as_of = date(2025, 1, 15)
    tables = {
        "branch_stock_lots": pd.DataFrame(
            {
                "branchId": [1, 1, 2],
                "flowerId": [10, 10, 20],
                "quantity": [8, 3, 5],
                "shippedAt": [
                    as_of - timedelta(days=2),
                    as_of - timedelta(days=12),
                    as_of - timedelta(days=8),
                ],
            }
        ),
        "distribution_orders": pd.DataFrame(
            {
                "id": [100, 101],
                "branchId": [1, 2],
                "status": ["IN_TRANSIT", "RECEIVED"],
            }
        ),
        "distribution_batch_allocations": pd.DataFrame(
            {
                "distributionOrderId": [100, 101],
                "batchId": [1000, 1001],
                "quantity": [4, 9],
            }
        ),
        "flower_batches": pd.DataFrame(
            {
                "id": [1000, 1001],
                "flowerId": [10, 20],
            }
        ),
    }

    result = build_inventory_snapshot(tables, as_of)

    branch_one_flower_ten = result[
        (result["branchId"] == 1) & (result["flowerId"] == 10)
    ].iloc[0]
    assert branch_one_flower_ten["currentUsableStock"] == 8
    assert branch_one_flower_ten["inTransitStock"] == 4

    branch_two_flower_twenty = result[
        (result["branchId"] == 2) & (result["flowerId"] == 20)
    ].iloc[0]
    assert branch_two_flower_twenty["currentUsableStock"] == 5
    assert branch_two_flower_twenty["inTransitStock"] == 0
