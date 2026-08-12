# Minimum-History Baseline Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select the existing baseline forecast before feature engineering when the dataset has fewer than the configured number of distinct sales-history days.

**Architecture:** `ml.data` owns sales-date validation and distinct-history counting. `ml.api` reads `MINIMUM_HISTORY_DAYS` from the environment, performs the preflight, and routes insufficient history to the existing baseline builder while preserving the current ML and training-error fallback paths. The Express recommendation engine is out of scope.

**Tech Stack:** Python, pandas, FastAPI, pytest, existing scikit-learn forecasting pipeline.

## Global Constraints

- Minimum history is counted as distinct calendar days in `daily_sales`, across the whole dataset.
- The default minimum is 28 days.
- Insufficient history is an intentional `BASELINE` selection, not an error.
- The response format and baseline identifiers remain unchanged: `forecastMethod: "BASELINE"`, `modelVersion: "baseline-v1"`.
- Recommendation business rules remain in Express and are not moved into `ml/`.
- Preserve the existing fallback when model training raises `ValueError`.

## File Map

- Modify `ml/data.py`: add the focused distinct-history helper beside `get_latest_sales_date`.
- Modify `ml/api.py`: add environment configuration and the pre-training baseline branch.
- Modify `tests/test_data.py`: test distinct-date history semantics and threshold boundaries.
- Modify `tests/test_api.py`: test sufficient and insufficient history routing, including skipped training.
- Do not modify `ml/models.py` or move recommendation logic.

### Task 1: Add Distinct History Policy Helper

**Files:**
- Modify: `ml/data.py` near `get_latest_sales_date`
- Test: `tests/test_data.py`

**Interfaces:**
- Produces `has_sufficient_sales_history(daily_sales: pd.DataFrame, minimum_days: int) -> bool`.
- The helper validates `salesDate` using the existing validation conventions, converts values with `pd.to_datetime(..., errors="coerce")`, rejects invalid dates, and counts `nunique()` normalized calendar dates.

- [ ] **Step 1: Write failing tests for duplicate dates and threshold boundaries**

```python
def test_has_sufficient_sales_history_counts_distinct_calendar_days():
    daily_sales = pd.DataFrame(
        {"salesDate": ["2024-01-01", "2024-01-01", "2024-01-02"]}
    )

    assert has_sufficient_sales_history(daily_sales, minimum_days=2)
    assert not has_sufficient_sales_history(daily_sales, minimum_days=3)
```

Also add a test that `minimum_days=0` raises `ValueError` with a clear positive-value message, and import the helper in `tests/test_data.py`.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/test_data.py -k "sufficient_sales_history" -v`

Expected: FAIL because `has_sufficient_sales_history` does not yet exist.

- [ ] **Step 3: Implement the minimal helper**

Add the helper with this behavior:

```python
def has_sufficient_sales_history(daily_sales: pd.DataFrame, minimum_days: int) -> bool:
    if minimum_days < 1:
        raise ValueError("minimum_days must be greater than zero")
    validate_required_columns(daily_sales, "daily_sales", {"salesDate"})
    sales_dates = pd.to_datetime(daily_sales["salesDate"], errors="coerce")
    if sales_dates.isna().any():
        raise ValueError("daily_sales contains an invalid salesDate")
    return sales_dates.dt.date.nunique() >= minimum_days
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/test_data.py -k "sufficient_sales_history" -v`

Expected: PASS.

- [ ] **Step 5: Commit the data helper**

```bash
git add ml/data.py tests/test_data.py
git commit -m "feat: detect sufficient sales history"
```

### Task 2: Route Insufficient History to Baseline

**Files:**
- Modify: `ml/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes `has_sufficient_sales_history` from `ml.data`.
- Produces the same `generate_forecast_payload(tables, forecast_date=None, model_version="hgb-v1") -> dict` payload contract.
- Configuration key: `MINIMUM_HISTORY_DAYS`; default value: `28`.

- [ ] **Step 1: Add API tests for both routes**

Use the existing `make_tables(days=45)` fixture and add a short-history call such as `make_tables(days=10)`. Assert sufficient history returns `ML`, while insufficient history returns `BASELINE`, `baseline-v1`, 12 results, and only `BASELINE` result rows.

Add the skip-training assertion:

```python
def test_insufficient_history_skips_training(monkeypatch):
    def fail_training(_feature_data):
        raise AssertionError("training should not run")

    monkeypatch.setattr("ml.api.train_direct_models", fail_training)
    monkeypatch.setattr("ml.api.MINIMUM_HISTORY_DAYS", 28)

    payload = generate_forecast_payload(make_tables(days=10))

    assert payload["forecastMethod"] == "BASELINE"
```

Add a configuration test that monkeypatches `ml.api.MINIMUM_HISTORY_DAYS` to a value above the fixture's 45 days and verifies the insufficient-history baseline route, then restores it automatically through `monkeypatch`. The data-level exact-threshold test from Task 1 remains the authoritative boundary test.

- [ ] **Step 2: Run the new API tests to verify they fail**

Run: `pytest tests/test_api.py -k "history or skips_training" -v`

Expected: FAIL because the current API always builds features before deciding whether to train.

- [ ] **Step 3: Add environment-backed configuration**

Import `os`, define `DEFAULT_MINIMUM_HISTORY_DAYS = 28`, and expose `MINIMUM_HISTORY_DAYS` from `os.getenv("MINIMUM_HISTORY_DAYS", str(DEFAULT_MINIMUM_HISTORY_DAYS))`. Convert the value to an integer and reject values below 1 with `ValueError`. Keep the value easy to monkeypatch in API tests.

- [ ] **Step 4: Add the pre-training baseline branch**

After `latest_observed_date` and `cutoff_date` validation, call `has_sufficient_sales_history(tables["daily_sales"], MINIMUM_HISTORY_DAYS)`. If false, build only the `sales_grid` needed by `build_baseline_results`, then return the same baseline payload currently used by the training-error handler. Do not call `add_model_features`, `add_forecast_targets`, or `train_direct_models` on the insufficient-history route. If true, build the feature data and retain the current training-error fallback.

Refactor the duplicated baseline payload into a local helper only if needed to keep both baseline branches identical. Do not change keys, result serialization, or model-version values.

- [ ] **Step 5: Run the API tests to verify they pass**

Run: `pytest tests/test_api.py -v`

Expected: PASS, including existing ML and training-error fallback tests.

- [ ] **Step 6: Commit the API routing change**

```bash
git add ml/api.py tests/test_api.py
git commit -m "feat: use baseline for insufficient history"
```

### Task 3: Run the Full Regression Suite

**Files:**
- No additional files.

- [ ] **Step 1: Run all tests**

Run: `pytest -q`

Expected: all existing and new tests pass.

- [ ] **Step 2: Inspect the final diff and worktree**

Run: `git diff HEAD~2..HEAD -- ml/api.py ml/data.py tests/test_api.py tests/test_data.py` and `git status --short`.

Confirm no Express files, recommendation code, or unrelated user changes were modified.

- [ ] **Step 3: Commit any required test-only correction**

If the full suite exposes a test correction needed for this feature, stage only the relevant files and use a focused commit message such as `test: cover minimum history boundary`.
