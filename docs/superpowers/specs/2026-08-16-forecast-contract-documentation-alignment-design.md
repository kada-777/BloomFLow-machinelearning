# Forecast Contract Documentation Alignment

## Goal

Align BloomFlow's internal ML and backend documentation with the forecast contract already implemented by the ML service. This is a documentation-only change. It does not change frontend, backend, or ML behavior, and it does not require model retraining.

## Current Contract

The backend calls the ML `POST /forecast` endpoint. The request field named `forecastDate` is the Daily Sales cutoff: the latest sales date the ML pipeline may use for that forecast run. The field name remains unchanged to preserve the existing wire contract.

The ML service always returns forecasts for horizons 1, 2, and 3. Each result's date is derived as:

```text
result.forecastDate = cutoffDate + result.horizon days
```

The normative example is:

| Cutoff | Horizon | Forecast date |
|---|---:|---|
| 12 August | 1 | 13 August |
| 12 August | 2 | 14 August |
| 12 August | 3 | 15 August |

The ML pipeline uses Daily Sales data only through the cutoff. It does not accept a frontend planning date or a configurable planning horizon.

## Responsibility Boundary

### Frontend

The frontend collects the planning date required by the distribution-planning workflow and sends it to the backend. It does not call the ML service directly or calculate an ML horizon.

### Backend

The backend remains the orchestration and business-validation layer. It is responsible for:

- determining and sending the Daily Sales cutoff to ML through the existing `forecastDate` request field;
- selecting the ML result whose `forecastDate` matches the requested `planningDate`;
- validating the planning date and Asia/Jakarta date rules;
- preventing duplicate distribution plans;
- rejecting malformed or unusable ML responses; and
- applying distribution-planning and persistence rules.

These responsibilities are documented as the intended existing architecture. This work does not implement or alter them.

### ML

The ML service is responsible for:

- receiving the cutoff from the backend;
- reading Daily Sales through that cutoff;
- producing horizons 1, 2, and 3;
- returning the corresponding forecast date for each horizon; and
- returning forecast values and model metadata without changing inventory or creating plans.

The ML service is not responsible for:

- accepting `planningDate` from the frontend;
- calculating or validating a business planning date;
- validating Asia/Jakarta date rules;
- detecting duplicate plans;
- supporting horizons beyond 3; or
- retraining the model for this alignment.

## Document Changes

Update the current normative documentation as follows:

- `docs/RFC/RFC-005-ML-Forecasting.md`: define cutoff semantics, fixed horizons, result dates, the request/response contract, and the ML/backend boundary.
- `docs/RFC/RFC-001-System-Architecture.md`: clarify that backend orchestration includes cutoff selection and mapping `planningDate` to an ML result.
- `docs/RFC/RFC-007-Distribution-Workflow.md`: place planning-date validation and duplicate-plan prevention with the backend workflow.
- `docs/API_Contract.yaml`: document the backend distribution-plan input and ML integration semantics, and remove the configurable `AI_PLANNING_HORIZON` contract.
- `docs/PRD_BloomFlow.md`: replace user-selected planning horizon language with a planning date selected by Staff HO and a fixed ML horizon set of 1-3.
- `docs/ERD.md`: align forecast-run and forecast-result field descriptions with the implemented cutoff, forecast date, and numeric horizon metadata where the ERD represents the integration contract.

Historical design and plan records under `docs/superpowers/` are not retroactively rewritten. They are implementation history rather than the current normative product contract.

## Response Metadata

Documentation of the ML response must match the implemented payload:

- top level: `cutoffDate`, `forecastMethod`, `modelVersion`, and `results`;
- each result: `branchId`, `flowerId`, `branchName`, `flowerName`, `forecastDate`, `horizon`, `forecastDemand`, `forecastMethod`, `modelVersion`, and `generatedAt`.

The documentation must not promise `planningDate`, `planningHorizon`, `modelName`, or `trainingDataUntil` as ML response fields because the service does not return them.

## Error Handling

The documentation should distinguish ML input errors from backend business-validation errors. The ML service may reject an invalid cutoff or invalid eligible pairs. Valid planning dates, Asia/Jakarta semantics, duplicate plans, and matching the selected planning date to one of the three returned forecast dates remain backend concerns.

## Verification

The documentation alignment is complete when:

1. No normative document describes `planningHorizon` as an ML request or configurable horizon.
2. The `forecastDate` request field is consistently described as the Daily Sales cutoff despite its retained wire name.
3. The fixed horizon-to-date mapping is stated and includes the 12-15 August example.
4. Backend and ML responsibilities are consistent across the PRD, API contract, ERD, and RFCs.
5. YAML remains parseable.
6. The existing ML test suite passes unchanged, confirming no behavior or training changes.

## Out of Scope

- ML model, feature, prediction, API, or training changes
- Backend or frontend implementation changes
- Model retraining
- Support for horizons beyond 3
- Backward-compatibility aliases or request-field renaming
- Verification of backend or frontend code located outside this repository
