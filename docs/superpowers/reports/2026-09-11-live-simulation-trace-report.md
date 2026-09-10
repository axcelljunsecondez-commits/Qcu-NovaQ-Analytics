# Live Simulation Trace Report

## Summary

Added a new Live tab to the existing Simulation page. It calls an additive `POST /simulation/des/trace` endpoint, captures bounded events from a seeded SimPy DES run, and replays those real events in the browser with play, pause, step, reset, and speed controls.

Existing `/simulation/des`, `/simulation/mc`, and `/simulation/validate` contracts were not changed. No database migration, Docker port mapping, nginx configuration, or new chart was added.

## Backend changes

- Added bounded trace recording to `backend/queueing_engine/simulation/simulation.py`.
- Captured ordered `arrival`, `service_start`, and `service_end` events with simulated time, segment ID, server ID, and queue depth.
- Added deterministic seed handling, carryover support, segment metadata, and a 10,000-event cap with truncation metadata.
- Added `TraceRequest` and `POST /simulation/des/trace` in `backend/api/simulation.py`.
- Bounds: `segments <= 1000`, `trace_hours` in `(0, 4]`, and `max_events` in `[1, 10000]`.

## Frontend changes

- Added a fourth `Live` tab to `SimulationPage.tsx`.
- Added typed trace API/client contracts.
- Added event-derived queue lanes, serving/idle state, waiting count, served count, running average wait, observed utilization, and replay controls.
- The Live tab does not generate simulation values in the browser; all displayed state comes from the returned event trace.
- Added symmetric English and Tagalog translations.
- Added frontend tests for trace requests and replay controls.

## Verification

- `python -m pytest tests/ -x --tb=short -q`: **448 passed, 3 skipped**.
- `python -m ruff check .`: **passed**.
- `python -m mypy . --config-file=pyproject.toml`: **passed**.
- `frontend/npm test`: **22 files, 133 tests passed**.
- `frontend/npm run typecheck`: **passed**.
- `frontend/npm run lint`: **passed** with three existing Fast Refresh warnings in `DecisionEndpoint.tsx` and `NovaQInsights.tsx`.
- `frontend/npm run build`: **passed**; Vite emitted the existing large-chunk warning for Charts.
- Locale key symmetry check: **489 matching keys**.
- `git diff --check`: **passed**.

A Windows pytest cleanup warning reported an access-denied temp directory after successful test completion; it did not affect test results.
