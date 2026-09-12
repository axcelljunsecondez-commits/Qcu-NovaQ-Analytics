# Simulation Playback Implementation Report

## A. Repository findings

- The DES is in `backend/queueing_engine/simulation/simulation.py` and uses `simpy.Environment` with a pooled `simpy.Resource`.
- The supported DES models are M/M/1 and M/M/c. Both have one shared FIFO queue feeding the configured `c` servers.
- An additive `POST /simulation/des/trace` endpoint and Live Simulation tab already existed.
- The pre-change trace recorded `arrival`, `service_start`, and `service_end` with simulated time, segment, server, and queue depth, but no customer identity.
- The pre-change UI replayed one event per fixed wall-clock interval and repeated the shared queue count on each server card.
- The current DES has no patience/reneging process and produces no abandonment events. The aggregate `dropped` metric is not a traced abandonment transition.

## B. Architecture chosen

```text
Existing trace-specific SimPy customer lifecycle
→ additive customer-ID instrumentation
→ existing /simulation/des/trace API
→ pure TypeScript playback state reducer
→ requestAnimationFrame simulation-time clock
→ isolated LiveSimulationPlayback component
```

The trace recorder allocates a stable integer ID for each real traced customer process and reuses it for that customer's lifecycle events. It does not draw random values or influence resource scheduling.

The UI uses one shared queue, the exact segment server count, and recorded customer/server identities. Events at the same simulation time are applied atomically. The abandoned exit is hidden because the backend declares abandonment unsupported.

## C. Files changed

- `backend/queueing_engine/simulation/simulation.py` — adds customer IDs plus truthful queue-structure and abandonment-support metadata to the existing trace path.
- `frontend/src/api/types.ts` — types the additive trace fields.
- `frontend/src/lib/simulationPlayback.ts` — adds the pure event-to-visual-state reducer, time stepping, speed conversion, clock formatting, KPIs, and accounting.
- `frontend/src/components/simulation/LiveSimulationPlayback.tsx` — renders arrival, shared queue, configured servers, served exit, conditional abandonment exit, clock, and controls.
- `frontend/src/pages/SimulationPage.tsx` — replaces the old inline replay with the isolated component and adds the no-run state.
- `frontend/src/styles/global.css` — adds responsive, accessible playback-floor styles and reduced-motion handling.
- `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json` — add symmetric playback copy.
- `tests/test_simulation.py` and `tests/test_simulation_api.py` — cover the additive backend contract, lifecycle, accounting, and 1/3/5-server configurations.
- `frontend/src/lib/simulationPlayback.test.ts` — covers event ordering, equal-time batching, queue/service/completion transitions, optional abandonment handling, accounting, stepping, and speed conversion.
- `frontend/src/components/simulation/LiveSimulationPlayback.test.tsx` — covers zero arrivals and bounded heavy-queue rendering.
- `frontend/src/pages/SimulationPage.test.tsx` — covers trace integration, shared-queue truth, conditional abandonment, pause/restart, and speed controls.
- `docs/superpowers/specs/2026-09-12-simulation-playback.md` and `docs/superpowers/plans/2026-09-12-simulation-playback.md` — record the verified design and implementation plan.
- `handoff.md` — records the current state and verification results.

## D. Analytical protection

| Area | Change |
| --- | --- |
| Queueing formulas | No change |
| Aggregate DES behavior | No change |
| DES random draws/distributions | No change |
| Monte Carlo | No change |
| Optimizer | No change |
| Model selection | No change |
| Utilization calculations | No change |
| Waiting-time calculations | No change |
| Cost calculations | No change |

## E. Tests and gates

- `python -m pytest tests/ -x --tb=short`: **450 passed, 3 skipped, 3 subtests passed**.
- Focused frontend playback tests: **3 files, 39 tests passed**.
- `npm test`: **24 files, 140 tests passed**.
- `npm run typecheck`: **passed**.
- `python -m ruff check .`: **passed**. The bare `ruff` executable is not on this Windows PATH, so the installed module invocation was used.
- `python -m mypy . --config-file=pyproject.toml`: **passed, 94 source files**. The bare `mypy` executable is not on this Windows PATH, so the installed module invocation was used.
- `npm run lint`: **passed** with the three pre-existing Fast Refresh warnings in `DecisionEndpoint.tsx` and `NovaQInsights.tsx`.
- `npm run build`: **passed** with the existing large Charts chunk warning.
- Locale validation: **509 matching English and Tagalog keys**.

The frontend suite emitted the existing jsdom `HTMLCanvasElement.getContext` notices from chart tests; all tests passed.

## F. Remaining verified limitations

- Playback coverage matches DES coverage: M/M/1 and M/M/c only.
- The DES implements a shared FIFO queue. Separate physical queues cannot be shown because the current simulation does not model them.
- The DES has no abandonment transition, so the abandoned lane remains hidden for current traces.
- Cross-segment queue carryover in the engine is count-based rather than identity-based. Playback therefore scopes customer identity and accounting to the active segment and does not claim customer continuity across segment boundaries.
- Trace payloads remain capped at 10,000 events and are explicitly labeled when truncated.
