# Analysis Workspaces Implementation Plan

Date: 2026-09-08

## Baseline audit

- Preserve the pre-existing dirty worktree captured by `git status --short --branch`.
- Record backend and frontend baseline gate results, distinguishing environment failures from assertions.
- Confirm DB, API, frontend route/query, compute, scenario integrity, and report flows.

## Incremental implementation

1. Add `AnalysisProject` ORM relationships and portable Alembic revision `0002` with deterministic legacy backfill.
2. Add validated queue setup schemas and owned Analysis CRUD/nested-resource router; register it in the app.
3. Tighten CSRF route matching so `/analyses` mutations are protected while frozen stateless route families remain exempt.
4. Add ingestion adapter for unambiguous aggregate/event schemas, timestamp ordering, hourly event aggregation, configured K/theta, and provenance.
5. Add Analysis-scoped upload, active-current, dataset-list, and scenario-list APIs.
6. Add structured model explanation service using the existing selector rather than duplicating dispatch.
7. Add optional Analysis filters/context fields to compatibility dataset/scenario APIs and enforce cross-Analysis dataset/scenario consistency.
8. Add frontend API types/functions and URL-derived Analysis shell, list page, create/setup workflow, progress navigation, and active Analysis display.
9. Route current/optimize/simulate/compare/reports through Analysis context; keep `/analysis` as the advanced legacy calculator.
10. Ensure query keys include `analysisId` and transient compute UI remounts when the route identifier changes.
11. Add symmetric English/Tagalog translation keys and minimal styles consistent with the current system.
12. Add backend/frontend regression tests, then run all mandated gates.

## Compatibility safeguards

- Do not edit queue model formulas, optimization service mathematics, simulation mathematics, or report calculations.
- Do not alter frozen compute request/response models.
- Keep legacy list/upload/scenario routes usable; additions are optional fields/query parameters.
- Prefer archive for Analyses and retain legacy dataset deletion behavior for the legacy route.
- Make migration downgrade structural only and never delete legacy analytical rows during upgrade.

## Required commands

- `.venv/Scripts/python.exe -m pytest tests/ -x --tb=short --basetemp=.pytest_tmp/analysis-workspaces`
- `.venv/Scripts/ruff.exe check .`
- `.venv/Scripts/mypy.exe .`
- `npm test -- --run`
- `npm run typecheck`
- `npm run lint`
- `npm run build`

Failures are reported exactly; an environment/worker startup failure is not described as a test assertion failure.
