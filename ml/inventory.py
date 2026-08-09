from datetime import date

import pandas as pd

from ml.data import validate_required_columns


def build_inventory_snapshot(tables: dict, as_of: date) -> pd.DataFrame:
    """Build current usable and outstanding in-transit stock by branch and flower."""
    stock_lots = tables["branch_stock_lots"].copy()
    orders = tables["distribution_orders"].copy()
    allocations = tables["distribution_batch_allocations"].copy()
    batches = tables["flower_batches"].copy()

    validate_required_columns(
        stock_lots,
        "branch_stock_lots",
        {"branchId", "flowerId", "quantity", "shippedAt"},
    )
    validate_required_columns(orders, "distribution_orders", {"id", "branchId", "status"})
    validate_required_columns(
        allocations,
        "distribution_batch_allocations",
        {"distributionOrderId", "batchId", "quantity"},
    )
    validate_required_columns(batches, "flower_batches", {"id", "flowerId"})

    stock_lots["shippedDate"] = pd.to_datetime(
        stock_lots["shippedAt"], errors="coerce"
    ).dt.date
    if stock_lots["shippedDate"].isna().any():
        raise ValueError("branch_stock_lots contains an invalid shippedAt")
    stock_lots["quantity"] = pd.to_numeric(stock_lots["quantity"], errors="raise")
    stock_lots["ageDays"] = stock_lots["shippedDate"].apply(
        lambda shipped_date: (as_of - shipped_date).days
    )
    usable_lots = stock_lots[
        stock_lots["quantity"].gt(0)
        & stock_lots["ageDays"].between(0, 11)
    ]
    current_stock = (
        usable_lots.groupby(["branchId", "flowerId"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "currentUsableStock"})
    )

    in_transit_orders = orders[orders["status"].eq("IN_TRANSIT")][
        ["id", "branchId"]
    ]
    in_transit = allocations.merge(
        in_transit_orders,
        left_on="distributionOrderId",
        right_on="id",
        how="inner",
        validate="many_to_one",
    ).merge(
        batches[["id", "flowerId"]],
        left_on="batchId",
        right_on="id",
        how="inner",
        suffixes=("_order", "_batch"),
        validate="many_to_one",
    )
    in_transit["quantity"] = pd.to_numeric(in_transit["quantity"], errors="raise")
    in_transit_stock = (
        in_transit.groupby(["branchId", "flowerId"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "inTransitStock"})
    )

    snapshot = current_stock.merge(
        in_transit_stock,
        on=["branchId", "flowerId"],
        how="outer",
    ).fillna(0)
    return snapshot.sort_values(["branchId", "flowerId"]).reset_index(drop=True)
