# Simulation Playback Implementation Plan

## 1. Extend trace instrumentation

- Allocate stable integer customer IDs in the existing bounded trace recorder.
- Thread the ID through the existing trace customer process and its arrival, service-start, and service-end records.
- Add truthful shared-queue and abandonment-support metadata without changing the existing aggregate DES path.

## 2. Add deterministic playback state

- Add a pure TypeScript event reducer for customer, queue, server, KPI, and accounting state.
- Batch equal-time events and provide helpers for step navigation and relative time formatting.
- Unit-test the reducer independently of rendering and timers.

## 3. Build the playback floor

- Extract the Live replay UI from `SimulationPage.tsx` into an isolated component.
- Drive playback with `requestAnimationFrame` and a simulation-time conversion.
- Render arrival, one shared queue, configured servers, served exit, and a conditional abandoned exit.
- Bound customer tokens, preserve exact numeric counts, and use existing theme tokens.

## 4. Integrate and localize

- Keep the existing Live tab and trace request workflow.
- Add a no-run state and unsupported-data state.
- Add symmetric English and Tagalog strings.

## 5. Verify

- Run focused backend and frontend playback tests.
- Run the required backend, lint, type, frontend test, frontend lint, and build gates.
- Record exact results and verified limitations in a feature report and update `handoff.md`.
