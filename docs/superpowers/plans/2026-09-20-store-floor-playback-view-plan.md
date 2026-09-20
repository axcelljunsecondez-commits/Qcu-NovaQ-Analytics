# Store Floor Playback View Implementation Plan

## 1. Extend the pure reducer

- Record `serviceStartByServer` alongside `servingByServer` in
  `deriveSeparateLaneSnapshots`, clearing it on `service_end`.
- Seed lane order and server identity from `trace.segments` before scanning events, so a
  declared-but-unused lane still appears.
- Declare the optional `queue_id` / `server_id` fields the backend already sends on
  `SimulationTraceSegment`.

## 2. Build the floor component

- Add `StoreFloorView.tsx`: arrivals rail, lane columns, departures rail.
- Derive every dot, badge, and timer from the snapshot; add no local state.
- Reuse existing theme tokens and badge classes so both themes stay readable.
- Keep the `lane-*`, `customer-*`, and `server-*` test identifiers of the diagram view.

## 3. Integrate

- Add the "Floor layout" selector to `SeparateSimulationPlayback`, defaulting to store
  view and keeping the diagram intact.
- Pass the period's `inactive_queue_ids` from `SimulationPage` so the closed state is
  real data rather than a prop nobody supplies.
- Add 0.25x to the speed list in both playbacks.
- Add symmetric English and Tagalog strings.

## 4. Verify

- Focused playback tests, then typecheck, lint, the full frontend suite, and the
  production build.
- Confirm against a real selected-plan DES payload that the service timer equals the
  traced `service_start`, that the closed lane comes from `inactive_queue_ids`, and that
  the panel stays vertically bounded with many lanes in both themes.
