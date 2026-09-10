# Live Simulation Trace

## Goal

Add a Live tab inside the existing Simulation page that replays a real, bounded event trace captured by the DES engine. The feature must remain additive: existing `/simulation/des`, `/simulation/mc`, and `/simulation/validate` request and response shapes remain unchanged.

## Design

Use a new `POST /simulation/des/trace` endpoint. This keeps the established DES contract frozen and makes the larger event payload explicit to callers that need it. The endpoint will accept the existing DES segment inputs plus:

- `trace_hours`: simulated duration per segment, default `1.0`, `> 0`, `<= 4`
- `max_events`: total trace event cap, default `10000`, `>= 1`, `<= 10000`
- `queue_overload_threshold`, `seed`, and `carryover` using the existing DES conventions

The request keeps `segments: list[dict] = Field(max_length=1000)`. The response is additive and shaped as:

```json
{
  "trace": [
    {
      "t": 0.123,
      "type": "arrival",
      "segment_id": 0,
      "server_id": null,
      "queue_len_after": 1
    }
  ],
  "trace_hours": 1.0,
  "event_count": 1,
  "truncated": false,
  "segments": [{"time": "08:00-09:00", "c": 3, "served": 10}]
}
```

Each event has `t` in simulated hours, `type` from `arrival`, `service_start`, `service_end`, or `abandon`, a zero-based segment identifier, a server identifier when applicable, and the queue depth immediately after the event. Events are ordered by simulation time and process ordering. If `max_events` is reached, the trace stops recording and returns `truncated: true`; the simulation itself remains bounded and does not fabricate omitted events.

## Backend behavior

- Add a trace-specific SimPy recorder to the existing M/M/1 and M/M/c DES lifecycle.
- Reuse `_validate_segment`, `simulation_coverage`, `select_model`, exponential draws, queue/resource behavior, carryover, and seeded segment progression from the current engine.
- Assign server IDs from the resource request order and record actual service start/end events.
- Record arrivals and queue depth changes from the real queue state. Unsupported models and invalid segments return a valid empty trace with segment error metadata rather than silently inventing events.
- Keep the existing aggregate simulation functions and endpoint untouched.

## Frontend behavior

- Add `live` to the existing `TABS` array; do not add a route or sidebar item.
- The Live tab uses the selected dataset and fetches `/simulation/des/trace` once when the user clicks Run Live Simulation.
- Controls: play/pause, step, reset, and speed selection. Playback is client-side over the returned ordered trace.
- Render one lane per segment/server identity represented in the trace. Each lane shows queue depth and server state derived from events (`serving` or `idle`); no random values are generated.
- Live KPIs are derived from the trace cursor: customers waiting, completed services, running average wait from paired arrival/service-start timestamps, and utilization from observed service intervals over elapsed trace time. If a KPI cannot be derived from available events, show the existing unavailable marker rather than a made-up value.
- Event-to-event visual interpolation may be used only for visual positioning and must be labeled `Interpolated for display`.
- Reuse existing cards, metric cards, badges, and theme tokens. Add all strings symmetrically to English and Tagalog locale files.

## Tests

Backend tests cover deterministic seeded traces, event schema/order, server IDs, queue depths, event cap/truncation, validation bounds, and unchanged existing DES behavior. Frontend tests cover the Live tab, trace request parameters, event-derived controls/KPIs, and replay controls.

## Scope

Only the requested backend simulation/API files, simulation tests, SimulationPage/API/types files, locale files, and this feature's spec/plan/report are changed. No database migration, Docker port, nginx, or new chart is required.
