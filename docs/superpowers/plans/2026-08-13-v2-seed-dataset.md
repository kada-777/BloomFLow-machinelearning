# V2 Seed Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a new versioned dataset whose HO stock is constrained by farm supply and drained through same-day branch distribution.

**Architecture:** Keep the existing single-file generator. Reduce demand multipliers, generate one per-flower HO supply target from D+2/D+3 demand, split that target across farms, then distribute accepted HO stock proportionally to branch demand.

**Tech Stack:** Python standard library CSV generation and `unittest` regression tests.

## Global Constraints

- Output must go to a new folder, not the existing `output` folder.
- HO acts as QC; accepted flowers should be sent to branches rather than accumulated at HO.
- Farm supply should be generated once per flower and split across farms, not multiplied by farm count.
- Daily sales may use branch stock, but may not exceed sellable fresh branch stock.

---

### Task 1: Regression Test

**Files:**
- Create: `tests/test_generate_data_seed.py`

**Interfaces:**
- Consumes: `python generate_data_seed.py`
- Produces: assertions against `output_v2/*.csv`

- [ ] Add a `unittest` file that runs the generator, confirms `output_v2` exists, confirms old farm-multiplied stock is gone, confirms HO ending stock is small, and confirms sales do not exceed branch fresh stock.
- [ ] Run `python -m unittest tests.test_generate_data_seed -v` and confirm it fails before code changes because `output_v2` is not generated.

### Task 2: Generator Update

**Files:**
- Modify: `generate_data_seed.py`

**Interfaces:**
- Produces: `OUT_DIR = output_v2`
- Produces: reduced `WEEKLY_RANGES`, `SEASONAL_SPIKES`, and `BRANCH_BASE_RANGES`
- Produces: `run_receiving(day)` with one D+2/D+3 target per flower split across farms
- Produces: `run_distribution(day)` with proportional branch allocation from HO available stock

- [ ] Change `OUT_DIR` to `output_v2`.
- [ ] Reduce multipliers and base demand ranges.
- [ ] Rewrite receiving to calculate each flower's supply target once, then split across farms.
- [ ] Rewrite distribution to allocate all available HO stock per flower proportionally across branches.
- [ ] Run `python generate_data_seed.py`.
- [ ] Run `python -m unittest tests.test_generate_data_seed -v` and confirm it passes.
