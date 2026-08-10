from datetime import date

import pandas as pd


TRAINING_TABLES = (
    "daily_sales",
    "daily_sales_items",
    "branch_stock_lots",
    "flower_batches",
    "distribution_orders",
    "distribution_batch_allocations",
    "inventory_movements",
    "distribution_receipts",
    "branches",
    "flowers",
)


def validate_required_columns(
    dataframe: pd.DataFrame,
    table_name: str,
    required_columns: set,
) -> None:
    """Raise a clear error when a Supabase table lacks expected columns."""
    missing_columns = sorted(set(required_columns) - set(dataframe.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError("{} missing required columns: {}".format(table_name, missing))


def get_latest_sales_date(daily_sales: pd.DataFrame) -> date:
    """Return the latest observed sales date used as the forecast cutoff."""
    validate_required_columns(daily_sales, "daily_sales", {"salesDate"})
    if daily_sales.empty:
        raise ValueError("daily sales data is empty")

    sales_dates = pd.to_datetime(daily_sales["salesDate"], errors="coerce")
    if sales_dates.isna().any():
        raise ValueError("daily_sales contains an invalid salesDate")

    return sales_dates.max().date()


def has_sufficient_sales_history(
    daily_sales: pd.DataFrame, minimum_days: int
) -> bool:
    if minimum_days < 1:
        raise ValueError("minimum_days must be greater than zero")
    validate_required_columns(daily_sales, "daily_sales", {"salesDate"})
    sales_dates = pd.to_datetime(daily_sales["salesDate"], errors="coerce")
    if sales_dates.isna().any():
        raise ValueError("daily_sales contains an invalid salesDate")
    return sales_dates.dt.date.nunique() >= minimum_days


def fetch_table(client, table_name: str, page_size: int = 1000) -> pd.DataFrame:
    """Read one Supabase table in pages and return it as a DataFrame."""
    if page_size < 1:
        raise ValueError("page_size must be greater than zero")

    rows = []
    offset = 0
    while True:
        response = (
            client.table(table_name)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = response.data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return pd.DataFrame(rows)


def load_training_data(client, page_size: int = 1000) -> dict:
    """Load the read-only dataset needed for training and recommendations."""
    return {
        table_name: fetch_table(client, table_name, page_size)
        for table_name in TRAINING_TABLES
    }


def profile_training_data(tables: dict) -> dict:
    """Return the first data-quality facts needed before feature engineering."""
    daily_sales = tables.get("daily_sales", pd.DataFrame())
    sales_start = None
    sales_end = None
    if not daily_sales.empty:
        validate_required_columns(daily_sales, "daily_sales", {"salesDate"})
        sales_dates = pd.to_datetime(daily_sales["salesDate"], errors="coerce")
        if sales_dates.isna().any():
            raise ValueError("daily_sales contains an invalid salesDate")
        sales_start = sales_dates.min().date()
        sales_end = sales_dates.max().date()

    return {
        "row_counts": {
            table_name: len(dataframe) for table_name, dataframe in tables.items()
        },
        "sales_start": sales_start,
        "sales_end": sales_end,
    }
