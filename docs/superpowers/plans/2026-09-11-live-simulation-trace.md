# Live Simulation Trace Implementation Plan

## 1. Backend trace engine

- Add typed trace event helpers in `backend/queueing_engine/simulation/simulation.py`.
- Extend the existing SimPy customer and arrival lifecycle through a trace-specific execution path, preserving the current aggregate path unchanged.
- Capture arrival, service start, service end, and abandon events with simulated time, segment ID, server ID, and queue depth after each event.
- Add bounded trace execution for one or more segments, deterministic seed offsets, carryover support, unsupported-model/error handling, and `max_events` truncation.

## 2. Additive API endpoint

- Add `TraceRequest` validation to `backend/api/simulation.py` with the existing segment max length and trace bounds.
- Add `POST /simulation/des/trace` using the new engine function.
- Return trace metadata and segment summaries without changing existing endpoint models or response bodies.

## 3. Contracts and frontend API types

- Add `TraceOptions`, `SimulationTraceEvent`, `SimulationTraceSegment`, and `SimulationTrace` types to `frontend/src/api/types.ts`.
- Add `simulateDesTrace` to `frontend/src/api/simulation.ts`.

## 4. Live Simulation tab

- Add the `live` tab to `SimulationPage.tsx` and add bounded trace controls using the existing DES settings where appropriate.
- Fetch once per explicit run, store the trace, and implement client-side play/pause/step/reset/speed state.
- Derive cursor state only from real events: queue depth by lane, serving/idle state, waiting count, completed service count, running average wait, and observed utilization.
- Render responsive queue/server lanes using existing classes and tokens, with an explicit interpolation caption if visual interpolation is used.
- Keep existing DES, Monte Carlo, and validation render paths unchanged.

## 5. i18n and tests

- Add matching Live labels, controls, statuses, errors, and captions to both locale JSON files.
- Add backend unit/API tests for deterministic event traces, schema/order, caps, bounds, and additive routing.
- Extend `SimulationPage.test.tsx` with a mocked trace response and assertions for request parameters and replay controls.

## 6. Verification and report

- Run focused backend and frontend tests after implementation.
- Run all required gates:
  - `python -m pytest tests/ -x --tb=short`
  - `ruff check .`
  - `mypy .`
  - from `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`
- Write exact results and any environment limitations to `docs/superpowers/reports/2026-09-11-live-simulation-trace-report.md`.
