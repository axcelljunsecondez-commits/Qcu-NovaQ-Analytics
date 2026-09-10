# Analysis Workspaces Design

Date: 2026-09-08

## Context and constraints

NovaQ is a FastAPI/SQLAlchemy service with a React Router/TanStack Query SPA. Persisted analytical state currently consists of user-owned `Dataset` and `Scenario` rows; optimization, DES, and Monte Carlo remain authenticated stateless compute APIs. Dataset uploads accept normalized aggregate segments, scenario saves are recalculated by the backend, and reports are generated on demand. The queueing formulas and model dispatch in `backend/queueing_engine/services/model_selection.py` are frozen.

The working tree was already heavily modified before this work. Those changes are user-owned and must be preserved. This design adds an ownership/context layer without rewriting compute engines or their request/response contracts.

## Domain model

The internal entity is `AnalysisProject`, stored in `analysis_projects` and exposed as “Analysis”. It contains `id`, `user_id`, `name`, optional descriptive `service_type` and `location_label`, validated `queue_setup_json`, `setup_status`, optional `archived_at`, and timestamps.

Queue setup is represented at the API boundary by enums and validation rules:

- structure: shared, single-server, separate queues, or unknown;
- fixed server count and whether staffing varies by period;
- unlimited, finite, or unknown total-system capacity;
- unmodeled, modeled, or unknown abandonment and optional patience rate.

`single_server` forces a fixed count of one. Finite capacity requires an integer total capacity at least as large as fixed staffing when staffing is fixed. Modeled abandonment may be saved while incomplete, but processing is blocked until theta is positive. Separate queues are stored honestly and processing returns a supported, user-facing 422 state rather than combining queues.

`Dataset.analysis_id` and `Scenario.analysis_id` are required for newly created records. They remain nullable at the physical/ORM level so conservative migration and legacy compatibility can retain records that cannot be assigned safely. Jobs are not analysis-scoped because no persisted job is used by the active UI workflow.

## Migration and legacy data

Migration `0002` creates `analysis_projects`, adds indexed foreign keys to datasets and scenarios, and backfills deterministically:

1. one legacy/unknown Analysis per existing dataset, owned by the dataset user;
2. scenarios referencing that dataset join the same Analysis only when scenario and dataset ownership agree;
3. one “Legacy scenarios” Analysis per user for scenarios with no dataset;
4. inconsistent cross-owner references remain unassigned and are documented by a warning emitted during migration.

No global Analysis is created. No analytical history is deleted. Downgrade removes only the new columns/table. The migration uses portable SQLAlchemy operations and explicit row processing so it runs on PostgreSQL and SQLite.

## Backend API

An authenticated `/analyses` router provides list/create/get/patch/archive plus nested dataset/current/scenario resources. Every nested lookup starts from an owned, unarchived-or-explicitly-requested Analysis and constrains the child by both `analysis_id` and `user_id`. Cross-user and cross-Analysis access is reported as 404.

Legacy `/datasets` and `/scenarios` keep their contracts. Optional `analysis_id` filters are additive. Legacy dataset creation remains possible for compatibility, but when the caller supplies `analysis_id` it is validated and assigned. The Analysis upload endpoint always assigns ownership. Scenario creation accepts additive `analysis_id`; if omitted while `dataset_id` is present it inherits the dataset Analysis, preserving old clients while ensuring all new workspace saves are scoped.

The CSRF exemption changes from broad prefix matching to exact route-family matching: `/analysis` and `/analysis/...` remain exempt, while `/analyses` does not match. `/simulation` and `/optimize` retain their current exemptions.

## Upload normalization and provenance

One ingestion adapter distinguishes aggregate input from event input only when unambiguous. Aggregate input is delegated to the existing validator. Event input requires exactly `arrival_time`, `service_start`, and `service_end`, parses all three consistently, rejects invalid ordering, derives waiting/service durations, and groups arrivals by clock-hour.

Each event segment uses arrival count computed from observed rows in that hour, calculates lambda as the arrival count per hour, mu as inverse mean service hours, and variance in hours squared. Fixed `c` comes only from explicit queue setup. Variable staffing blocks event input for the MVP. Explicit finite K/theta from setup are applied; neither is inferred from count differences. Provenance is persisted in the dataset validation JSON per field as `user_provided`, `data_derived`, or `model_assumption`.

The adapter returns the existing normalized segment shape and `process_segments`/`select_model` remain the compute path. Raw-file limits, extension/magic validation, safe filenames, and formula-injection sanitization remain in use.

## Current metrics and model explanation

`GET /analyses/{id}/current` selects the most recent successfully processed dataset and returns normalized inputs, processed current rows/KPIs, and structured explanations. A reusable explanation service calls the existing `select_model` exactly once per segment, then categorizes only:

- queue-setup statements as operational facts;
- uploaded/derived characteristics as measured characteristics;
- documented model requirements as assumptions.

Uniform segment selections produce one selected model; differing selections produce “Multiple models by time period” and retain every per-segment result. Business type never participates in dispatch. Event-derived variance is disclosed as the reason the existing selector enters the general-service family.

## Frontend architecture

The URL is the active Analysis source of truth. New routes are `/analyses`, `/analyses/new`, and `/analyses/:analysisId/{setup,current,optimize,simulate,compare,reports}`. Login defaults to `/analyses`; `/analysis` remains the advanced manual calculator.

An Analysis route shell reads `analysisId`, loads `['analysis', analysisId]`, renders the active name/workflow navigation, and owns cleanup of transient query/cache state on identifier changes. Page data uses Analysis-aware keys including datasets/current/scenarios. Existing Optimize, Simulation, Comparison, and Reports components receive or read the route identifier and filter through nested/filtered endpoints; their mathematics and result rendering stay intact.

The setup page is a guided sequence (details/queue setup, upload, processing result, explanation). A compact progress strip is reused across the Analysis shell. Unsupported/incomplete states are rendered as translated actionable messages, never raw exception text.

## Isolation and compatibility invariants

- Every new workspace dataset/scenario receives `analysis_id` server-side.
- Child lookups require user and Analysis agreement.
- Scenario dataset references must agree on user and Analysis.
- Active dataset is the newest successfully processed dataset in that Analysis.
- Query keys include Analysis identity and transient state is remounted/cleared on route changes.
- Existing `/analysis`, `/optimize`, `/simulation`, dataset, scenario, and report contracts remain additive-compatible.
- No queueing formula, optimization, DES, Monte Carlo, or comparison calculation changes are part of this design.

## Verification

Backend tests cover schema migration/backfill, CRUD/CSRF/ownership, validation, both ingestion paths, provenance, explanation families, and isolation. Frontend tests cover routing/login, setup/upload states, scoped query keys, scenario saving, and Analysis switching. Existing suites and all repository gates remain required.
