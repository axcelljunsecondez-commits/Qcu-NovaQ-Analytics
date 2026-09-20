# Store Floor Playback View

## Goal

Render the existing separate-queue playback as a checkout floor that fits on one screen,
so an operations reader sees every lane at once instead of scrolling a stacked diagram.
The view is presentation-only and additive: no queueing mathematics, no DES behavior, no
API contract, and no existing aggregate or trace field changes.

## Verified repository facts

- `POST /analyses/{id}/workflow/simulation/des/selected` already returns, per period,
  `active_queue_ids`, `inactive_queue_ids`, per-lane `results`, and a `trace` carrying
  `arrival` / `service_start` / `service_end` events with `queue_id`, `server_id`, and
  `customer_id` (`backend/api/workflow.py`).
- Each period's `trace.segments` already carries one entry per lane, including `queue_id`
  and `server_id`, for both active and inactive lanes.
- `deriveSeparateLaneSnapshots` in `frontend/src/lib/simulationPlayback.ts` is a pure
  reducer over that trace. Before this change it derived lane identity from events only,
  so a lane with no events was not rendered at all.
- The separate DES has no finite capacity and no abandonment; the response states
  `abandonment_supported: false`.
- The trace schema has no break event. `DedicatedQueueLifecycle` models DRAINING and
  ON_BREAK internally, but those transitions are not emitted, so a break window cannot be
  shown on the playback clock.
- `evaluate_candidate_with_des` omits `trace_events` on its INFEASIBLE early return
  (`backend/queueing_engine/services/separate_optimization.py:591`), so a period above the
  utilization target yields an empty playback in every view. This is pre-existing and out
  of scope here.

## Presentation contract

- Lane identity is taken from `trace.segments` first and from events second. A lane the
  run declared but never used is drawn as a real, empty lane.
- Every displayed value is derived from the snapshot at the playback clock:
  waiting dots from `waitingCustomerIds`, the counter occupant from `servingByServer`,
  elapsed service from `simulationTime - serviceStartByServer[serverId]`, and the
  departing count from `servedCustomerIds`.
- A lane listed in the period's `inactive_queue_ids` is labeled **Closed / not staffed in
  this plan**. It must not be labeled as a break: the trace carries no break transition.
- The abandoned exit stays gated on `abandonment_supported` or an observed `abandon`
  event. The aggregate `dropped` field is never visualized as an abandonment.
- The accounting identity (arrived = waiting + serving + served + abandoned) remains
  displayed and unchanged.

## Layout contract

- Lanes are grid columns, never stacked rows. The floor panel stays vertically bounded
  regardless of lane count.
- Waiting customers stack toward their own counter, front of queue nearest the counter,
  capped at six dots with the real remainder shown as `+N`.
- Above ten lanes the floor switches to a dense layout: customer ids and service timers
  are hidden and the lane strip may overflow horizontally. Overflow is horizontal only.
- Dot transitions are disabled at 5x and above so the animation can never lag behind the
  clock and contradict the numbers.

## Controls

- A "Floor layout" selector chooses store view (default) or the existing diagram view.
  Both views read the same snapshot and carry the same lane, customer, and server test
  identifiers, so lane isolation stays provable in either.
- Playback speeds gain 0.25x in both the shared and separate playbacks. No other control
  behavior changes.

## Out of scope

- Break windows on the playback clock (no trace events exist for them).
- The empty-trace INFEASIBLE backend path.
- Any change to the shared-queue playback beyond the added speed option.
