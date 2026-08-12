# Minimum-History Baseline Selection

## Goal

Select the existing `BASELINE` forecast intentionally when the dataset does not contain enough historical sales history for the ML feature set. Preserve the current response format and keep inventory recommendation business rules in Express.

## Configuration

Expose the minimum history as an environment-backed setting in `ml/api.py`. The default is 28 distinct calendar days, matching the longest configured sales lag. Parse the setting once at module load. Invalid values should raise `ValueError`, which the existing endpoint handler converts to HTTP 422.

## Data Validation

Add a focused helper in `ml/data.py` that validates the `daily_sales.salesDate` column, normalizes dates, counts distinct calendar days, and determines whether the count meets the configured minimum. Duplicate sales rows on the same date count once. The check applies across the full dataset, not separately per branch or flower.

## Forecast Flow

`generate_forecast_payload` will:

1. Determine the latest observed sales date and effective cutoff date.
2. Check distinct-date history before building the sales grid, features, or models.
3. Return the existing baseline payload with `forecastMethod: "BASELINE"` and `modelVersion: "baseline-v1"` when history is insufficient.
4. Otherwise continue through the current ML path.
5. Preserve the current `ValueError` training fallback for sufficient-history datasets where training still fails.

The baseline result builder and payload fields remain unchanged. No recommendation engine code moves into the ML folder.

## Testing

Add data-level tests for duplicate dates, below-threshold history, and exactly-at-threshold history. Add API tests proving sufficient history returns `ML`, insufficient history returns the unchanged baseline payload shape, and insufficient history does not call training. Retain the existing test for fallback after a training `ValueError`. Model tests remain focused on feature preparation and model training rather than API history policy.

## Error Handling

Existing invalid-date and empty-sales validation remains authoritative. Configuration errors and malformed sales dates continue through the existing `ValueError` handling. Insufficient history is not an error; it is an intentional baseline selection.
