# Simulation Playback

## Goal

Upgrade the existing Live simulation trace into a customer-level playback of the real SimPy event stream. The playback remains presentation-only and additive to the existing `/simulation/des/trace` contract.

## Verified repository facts

- DES execution is implemented in `backend/queueing_engine/simulation/simulation.py` with `simpy.Environment` and a pooled `simpy.Resource`.
- Supported DES models are M/M/1 and M/M/c. Both use one shared FIFO resource queue feeding `c` identical servers.
- The trace path already records `arrival`, `service_start`, and `service_end` events. It does not currently record customer identity.
- The DES has no patience, reneging, or abandonment process. The aggregate `dropped` field is not a customer abandonment transition and must not be visualized as one.
- Server identifiers in the trace are assigned only after an actual resource request is granted.
- The existing Live tab replays events in fixed wall-clock intervals and repeats the shared queue depth on every server card.

## Contract extension

Each trace event gains a required integer `customer_id`. The identifier is allocated by the trace recorder when a real traced customer process is created and is reused for that customer's arrival, service start, and service end events.

Each trace segment gains `queue_structure: "shared"`. The response gains `abandonment_supported: false`. These fields state existing DES behavior; they do not introduce queue or abandonment behavior.

Existing endpoints and existing fields remain unchanged.

## Playback behavior

- Render the active time segment only, with one shared FIFO queue feeding exactly `c` server cards.
- Derive customer state solely from events at or before the playback clock:
  - `arrival` places that customer in the waiting set;
  - `service_start` removes that customer from waiting and assigns the recorded server;
  - `service_end` clears the recorded server and adds that customer to served;
  - `abandon` remains a defensive frontend contract case, but the lane is hidden because the current backend declares abandonment unsupported and emits no such events.
- Apply all events with the same timestamp together so an immediate arrival/service start is not displayed as a fabricated wait.
- Bound visible customer tokens and show the real remaining count numerically.
- Show arrived, waiting, serving, served, optional abandoned, running average wait, and observed utilization from the processed events.
- Show the accounting identity for the active segment: arrived equals waiting plus serving plus served plus abandoned.
- Use a relative `HH:MM:SS` simulation clock. At 1x, the loaded trace spans 60 seconds of playback; other speeds multiply that playback rate without changing event ordering.
- Play, pause, restart, step-to-next-event-time, speed selection, and timeline seeking change only presentation state.

## Empty and boundary states

- Before a trace run, prompt the user to run a simulation.
- For supported zero-arrival traces, render the empty shared-queue environment.
- When every segment is unsupported or invalid, show that playback data is unavailable and retain the returned error metadata.
- A capped trace is labeled as truncated; visible accounting is based only on captured events.

## Analytical protection

No queueing formula, model selection rule, DES arrival/service distribution, optimizer, Monte Carlo path, utilization calculation, wait calculation, or cost calculation changes. Trace instrumentation observes the existing trace-specific customer lifecycle only.

## Tests

Backend tests cover deterministic IDs, lifecycle ordering, server bounds for 1/3/5 servers, queue metadata, lack of abandonment support, event caps, and event-derived accounting. Frontend tests cover event reduction, same-time batching, arrival/queue/service/completion state, optional abandonment handling, controls, restart, pause, speed selection, and active-segment accounting.
