# Forecast Contract Documentation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align all normative ML and backend documentation with the existing cutoff-based ML contract that always returns horizons 1, 2, and 3.

**Architecture:** Preserve the implemented ML wire contract: request `forecastDate` means the Daily Sales cutoff, while response `cutoffDate` identifies that cutoff and each result carries `forecastDate` plus `horizon`. Document the backend as the orchestration boundary that validates `planningDate`, chooses the matching returned result, applies Asia/Jakarta and duplicate-plan rules, and exposes the frontend-facing planning workflow.

**Tech Stack:** Markdown, Mermaid ERD, YAML, FastAPI/Python contract references, pytest, Prettier YAML parser.

## Global Constraints

- This is a documentation-only change; do not modify frontend, backend, ML, test, dependency, or training code.
- Keep the existing ML request key `forecastDate`; document it as the Daily Sales cutoff rather than renaming it.
- ML always returns horizons 1, 2, and 3 and does not support a configurable planning horizon.
- For cutoff 12 August, horizon 1 maps to 13 August, horizon 2 to 14 August, and horizon 3 to 15 August.
- ML does not accept `planningDate`, validate Asia/Jakarta business dates, detect duplicate plans, or select a planning result.
- Backend owns planning-date validation, Asia/Jakarta rules, duplicate-plan handling, and selection of the result whose `forecastDate` equals `planningDate`.
- Do not add backward-compatibility aliases, support horizons beyond 3, or retrain the model.
- Treat records already stored under `docs/superpowers/` as historical; do not rewrite them while executing this plan.

---

### Task 1: Define the ML Contract and Architecture Boundary

**Files:**
- Modify: `docs/RFC/RFC-005-ML-Forecasting.md:6-20`
- Modify: `docs/RFC/RFC-001-System-Architecture.md:8-15`

**Interfaces:**
- Consumes: Existing `POST /forecast` contract from `ml/api.py:41-44,131-149` and result construction from `ml/prediction.py`.
- Produces: The normative ML contract and responsibility vocabulary reused by the API contract, PRD, workflow RFC, and ERD tasks.

- [ ] **Step 1: Replace the ambiguous RFC-005 input description with cutoff semantics**

In `docs/RFC/RFC-005-ML-Forecasting.md`, state all of the following explicitly:

```markdown
## Request Contract

Backend memanggil `POST /forecast`. Field request `forecastDate` dipertahankan sebagai nama wire contract, tetapi nilainya adalah cutoff Daily Sales: tanggal penjualan terakhir yang boleh digunakan oleh pipeline untuk forecast run tersebut. Jika field tidak diberikan, ML menggunakan tanggal Daily Sales terbaru yang tersedia.

ML tidak menerima `planningDate` atau `planningHorizon` dari frontend maupun backend. Data training dan feature forecast dibatasi sampai cutoff yang dipilih.
```

- [ ] **Step 2: Document the fixed result contract and normative date example**

Replace the current RFC-005 output field list with the implemented shape and fixed date rule:

```markdown
## Response Contract

Response memuat `cutoffDate`, `forecastMethod`, `modelVersion`, dan `results`. Setiap item `results` memuat `branchId`, `flowerId`, `branchName`, `flowerName`, `forecastDate`, `horizon`, `forecastDemand`, `forecastMethod`, `modelVersion`, dan `generatedAt`.

ML selalu menghasilkan horizon 1, 2, dan 3. Untuk setiap hasil, `forecastDate = cutoffDate + horizon` hari:

| Cutoff | Horizon | Forecast date |
|---|---:|---|
| 12 Agustus | 1 | 13 Agustus |
| 12 Agustus | 2 | 14 Agustus |
| 12 Agustus | 3 | 15 Agustus |
```

Remove promises that ML returns `trainingDataUntil`, `modelName`, or a caller-selected horizon.

- [ ] **Step 3: Make backend-only validation responsibilities explicit in RFC-005**

Add a boundary section with this meaning:

```markdown
## Responsibility Boundary

Backend memilih cutoff dan memilih hasil yang `forecastDate`-nya sama dengan `planningDate`. Backend juga menangani validasi planning date, aturan tanggal Asia/Jakarta, duplicate plan, validasi response ML, persistence, dan distribution workflow.

ML hanya menghasilkan forecast. ML tidak menghitung valid planning date, tidak memeriksa duplicate plan, tidak mendukung horizon di atas 3, dan tidak mengubah inventory atau membuat distribution plan/order.
```

Keep the existing fallback and versioning sections, but phrase fallback metadata in terms of the same response fields rather than adding new fields.

- [ ] **Step 4: Clarify the orchestration sentence in RFC-001**

Extend the backend and ML bullets in `docs/RFC/RFC-001-System-Architecture.md` so they state:

```markdown
- Backend menangani JWT, role/branch scope, business rule, transaksi, FIFO, validasi planning date dan duplicate plan, pemilihan cutoff Daily Sales, validasi output AI/ML, serta pemilihan hasil forecast yang tanggalnya cocok dengan `planningDate`.
- AI/ML menerima cutoff melalui field request `forecastDate`, menggunakan Daily Sales sampai cutoff tersebut, dan mengembalikan horizon tetap 1-3; AI/ML tidak boleh mengubah stok, membuat movement, atau mengeksekusi workflow.
```

- [ ] **Step 5: Check the two RFCs for stale contract terms**

Run:

```powershell
rg -n "planningHorizon|trainingDataUntil|modelName|planning horizon" docs/RFC/RFC-005-ML-Forecasting.md docs/RFC/RFC-001-System-Architecture.md
```

Expected: no stale field promises; any remaining human-readable reference must explicitly say that ML does not accept or return that concept.

- [ ] **Step 6: Review and commit the RFC contract**

Run:

```powershell
git diff --check
git diff -- docs/RFC/RFC-005-ML-Forecasting.md docs/RFC/RFC-001-System-Architecture.md
git add docs/RFC/RFC-005-ML-Forecasting.md docs/RFC/RFC-001-System-Architecture.md
git commit -m "docs: define cutoff forecast contract"
```

Expected: the diff changes documentation only and the commit succeeds.

---

### Task 2: Align the Backend API Contract

**Files:**
- Modify: `docs/API_Contract.yaml:66-84`
- Modify: `docs/API_Contract.yaml:516-531`

**Interfaces:**
- Consumes: RFC-005 request/response terminology and RFC-001 responsibility boundary from Task 1.
- Produces: The frontend-facing planning input and backend-to-ML integration contract used by product and workflow documentation.

- [ ] **Step 1: Remove the configurable horizon key and align minimum-history naming**

Delete `AI_PLANNING_HORIZON`. Rename `AI_MINIMUM_HISTORY` to the key read by the ML implementation:

```yaml
  MINIMUM_HISTORY_DAYS:
    type: integer
    unit: distinct sales dates
    default: 28
    description: Minimum riwayat Daily Sales agar model ML dapat digunakan sebelum fallback baseline.
```

Do not introduce any replacement setting for the fixed horizons 1-3.

- [ ] **Step 2: Document the frontend-facing distribution-plan request**

Under endpoint id 28 (`POST /distribution-plans/generate`), add:

```yaml
  required_request_fields:
  - planningDate
  rules:
  - Backend memvalidasi planningDate menggunakan aturan tanggal bisnis Asia/Jakarta.
  - Backend menolak duplicate distribution plan untuk planningDate yang sama.
  - Frontend tidak mengirim planningHorizon atau cutoff ML.
```

- [ ] **Step 3: Document the internal backend-to-ML mapping**

Under the same endpoint, add an `ml_integration` mapping:

```yaml
  ml_integration:
    endpoint: POST /forecast
    request:
      forecastDate: Cutoff Daily Sales yang dipilih backend; nama field dipertahankan sesuai wire contract ML.
    fixed_horizons:
    - 1
    - 2
    - 3
    result_date_rule: forecastDate hasil = cutoffDate + horizon hari.
    selection_rule: Backend memilih result dengan forecastDate yang sama dengan planningDate.
    normative_example:
      cutoffDate: 12 Agustus
      results:
      - horizon: 1
        forecastDate: 13 Agustus
      - horizon: 2
        forecastDate: 14 Agustus
      - horizon: 3
        forecastDate: 15 Agustus
```

Do not place `planningDate` or `planningHorizon` inside the ML request mapping.

- [ ] **Step 4: Parse the YAML after editing**

Run:

```powershell
npx --yes prettier docs/API_Contract.yaml --parser yaml > $null
```

Expected: exit code 0 with no YAML syntax error; redirecting output prevents whole-file reformatting.

- [ ] **Step 5: Verify that no configurable planning horizon remains**

Run:

```powershell
rg -n "AI_PLANNING_HORIZON|planningHorizon" docs/API_Contract.yaml
```

Expected: `AI_PLANNING_HORIZON` is absent; `planningHorizon` may occur only in the explicit rule saying the frontend does not send it.

- [ ] **Step 6: Review and commit the API contract**

Run:

```powershell
git diff --check
git diff -- docs/API_Contract.yaml
git add docs/API_Contract.yaml
git commit -m "docs: align distribution forecast API contract"
```

Expected: the diff contains only the configuration and endpoint contract changes described above.

---

### Task 3: Align Product Requirements and User Workflow

**Files:**
- Modify: `docs/PRD_BloomFlow.md:103-115`
- Modify: `docs/PRD_BloomFlow.md:309-329`
- Modify: `docs/PRD_BloomFlow.md:377-398`
- Modify: `docs/PRD_BloomFlow.md:639-661`

**Interfaces:**
- Consumes: The backend/ML boundary from Task 1 and endpoint semantics from Task 2.
- Produces: Product language that distinguishes Staff HO's `planningDate` from the ML cutoff and fixed horizons.

- [ ] **Step 1: Remove planning horizon from configurable product settings**

At the Superadmin configuration list, replace the model-parameter bullet with:

```markdown
- Mengatur minimum history AI/ML; horizon forecast MVP tetap 1, 2, dan 3 dan tidak dapat dikonfigurasi.
```

- [ ] **Step 2: Rewrite the model input and output lists around the implemented contract**

The AI/ML input list must identify `forecastDate` as the backend-selected Daily Sales cutoff and must not list a planning horizon. The output list must include:

```markdown
#### Output Model

- Forecast demand per branch dan flower.
- `cutoffDate` yang digunakan untuk Daily Sales.
- `forecastDate` dan `horizon` untuk setiap hasil.
- `forecastMethod`, `modelVersion`, dan `generatedAt`.
- Horizon tetap 1, 2, dan 3.
```

- [ ] **Step 3: Rewrite the distribution-planning workflow**

Replace the first three workflow steps with the explicit split:

```markdown
1. Staff HO memilih `planningDate`; Staff HO tidak memilih planning horizon.
2. Backend memvalidasi planning date dan duplicate plan, lalu memilih cutoff Daily Sales.
3. Backend meminta ML menghasilkan seluruh forecast horizon 1, 2, dan 3 dari cutoff tersebut.
4. Backend memilih hasil dengan `forecastDate` yang sama dengan `planningDate`.
```

Renumber the remaining recommendation, review, finalization, and order steps without changing their behavior.

- [ ] **Step 4: Align the AI/ML requirements and metadata list**

Rewrite section 10.1 so the model always predicts the next three dates from a cutoff, and rewrite section 10.3 to list only implemented metadata:

```markdown
Setiap forecast run dan hasilnya menyediakan:

- `cutoffDate`
- `forecastDate`
- `horizon`
- `modelVersion`
- `forecastMethod`
- `generatedAt`
```

Remove `modelName` and `trainingDataUntil`. Preserve the fallback requirements without introducing a new owner or implementation change.

- [ ] **Step 5: Check every planning-horizon occurrence in the PRD**

Run:

```powershell
rg -n -i "planning.?horizon|trainingDataUntil|modelName|forecast period" docs/PRD_BloomFlow.md
```

Expected: no stale configurable/requested planning horizon, `trainingDataUntil`, `modelName`, or ambiguous `forecast period` remains. A sentence saying Staff HO does not select a planning horizon is acceptable.

- [ ] **Step 6: Review and commit the PRD alignment**

Run:

```powershell
git diff --check
git diff -- docs/PRD_BloomFlow.md
git add docs/PRD_BloomFlow.md
git commit -m "docs: align forecast planning requirements"
```

Expected: product behavior outside forecast orchestration remains unchanged.

---

### Task 4: Align Persistence and Distribution Workflow Documentation

**Files:**
- Modify: `docs/ERD.md:78-100`
- Modify: `docs/RFC/RFC-007-Distribution-Workflow.md:14-16`

**Interfaces:**
- Consumes: Forecast metadata from Task 1 and backend rules from Tasks 2-3.
- Produces: Consistent persistence vocabulary and an explicit backend-owned planning rule.

- [ ] **Step 1: Replace stale forecast metadata in the Mermaid ERD**

Update the three forecast/planning entities to use this vocabulary:

```mermaid
    forecast_runs {
        int id PK
        datetime executedAt
        date cutoffDate
        varchar modelVersion
        enum forecastMethod
    }

    forecast_results {
        int id PK
        int runId FK
        int branchId FK
        int flowerId FK
        date forecastDate
        int horizon
        decimal forecastDemand
        datetime generatedAt
    }

    distribution_plans {
        int id PK
        enum status
        date planningDate UK
    }
```

This removes undocumented `trainingDataUntil`, `forecastPeriod`, and `confidenceInterval` fields from the forecast integration model and records the no-duplicate planning-date invariant.

- [ ] **Step 2: Add planning-date orchestration rules to RFC-007**

Extend the rules section with:

```markdown
Saat generate plan, backend memvalidasi `planningDate` berdasarkan tanggal bisnis Asia/Jakarta dan menolak plan lain dengan `planningDate` yang sama. Backend memilih cutoff Daily Sales, meminta seluruh horizon 1-3 dari ML, lalu menggunakan result yang `forecastDate`-nya sama dengan `planningDate`. Frontend tidak memilih horizon dan ML tidak memvalidasi planning date atau duplicate plan.
```

- [ ] **Step 3: Check persistence and workflow terminology**

Run:

```powershell
rg -n "trainingDataUntil|forecastPeriod|confidenceInterval|planningHorizon" docs/ERD.md docs/RFC/RFC-007-Distribution-Workflow.md
```

Expected: no matches except an explicit statement that the frontend or ML does not use `planningHorizon`, if that term is retained for clarity.

- [ ] **Step 4: Review and commit the ERD and workflow alignment**

Run:

```powershell
git diff --check
git diff -- docs/ERD.md docs/RFC/RFC-007-Distribution-Workflow.md
git add docs/ERD.md docs/RFC/RFC-007-Distribution-Workflow.md
git commit -m "docs: align forecast persistence workflow"
```

Expected: only forecast metadata and distribution-plan orchestration rules change.

---

### Task 5: Verify Cross-Document Consistency and Unchanged ML Behavior

**Files:**
- Verify: `docs/RFC/RFC-001-System-Architecture.md`
- Verify: `docs/RFC/RFC-005-ML-Forecasting.md`
- Verify: `docs/RFC/RFC-007-Distribution-Workflow.md`
- Verify: `docs/API_Contract.yaml`
- Verify: `docs/PRD_BloomFlow.md`
- Verify: `docs/ERD.md`
- Verify: `ml/`
- Verify: `tests/`

**Interfaces:**
- Consumes: All normative documentation changes from Tasks 1-4.
- Produces: Evidence that the contract is consistent, YAML is parseable, and ML behavior remains unchanged.

- [ ] **Step 1: Confirm the normative date example appears in ML and backend contract documentation**

Run:

```powershell
rg -n "12 Agustus|13 Agustus|14 Agustus|15 Agustus" docs/RFC/RFC-005-ML-Forecasting.md docs/API_Contract.yaml
```

Expected: both documents show cutoff 12 August mapping horizons 1-3 to 13-15 August.

- [ ] **Step 2: Audit stale terms across normative documentation**

Run:

```powershell
rg -n -i "AI_PLANNING_HORIZON|trainingDataUntil|modelName|forecastPeriod|planning.?horizon" docs/RFC docs/API_Contract.yaml docs/PRD_BloomFlow.md docs/ERD.md
```

Expected: no stale field/configuration promises. Negative statements explaining that planning horizon is not accepted or configurable are allowed and must be inspected manually.

- [ ] **Step 3: Audit the responsibility boundary across normative documentation**

Run:

```powershell
rg -n "Asia/Jakarta|duplicate|cutoff|planningDate|horizon" docs/RFC docs/API_Contract.yaml docs/PRD_BloomFlow.md docs/ERD.md
```

Expected: ML documents assign only cutoff-based horizon generation to ML; backend documents assign planning-date validation, duplicate prevention, and result selection to backend.

- [ ] **Step 4: Parse the final YAML contract**

Run:

```powershell
npx --yes prettier docs/API_Contract.yaml --parser yaml > $null
```

Expected: exit code 0 with no YAML syntax error; the source file remains unchanged.

- [ ] **Step 5: Run the unchanged ML test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all existing tests pass; no test, model, feature, API, or training file has changed.

- [ ] **Step 6: Verify scope and repository diff**

Run:

```powershell
git status --short
git diff --check
git diff --stat HEAD~4..HEAD
git diff --name-only HEAD~4..HEAD
```

Expected: only the six normative documentation files from Tasks 1-4 changed. The historical design spec and this plan may appear in earlier commits or as separately tracked planning artifacts, but no application, test, dependency, or generated file changed during execution.

- [ ] **Step 7: Record any verification-only correction**

If Steps 1-6 expose a documentation inconsistency, correct only the affected normative document, rerun the failed verification command, and commit the correction with exact paths:

```powershell
git add docs/RFC/RFC-001-System-Architecture.md docs/RFC/RFC-005-ML-Forecasting.md docs/RFC/RFC-007-Distribution-Workflow.md docs/API_Contract.yaml docs/PRD_BloomFlow.md docs/ERD.md
git commit -m "docs: fix forecast contract consistency"
```

Expected: skip this step when no correction is needed; never modify code to satisfy this documentation plan.
