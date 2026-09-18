# Separate Queue Representative Day — Specification (2026-09-18)

## Problem (verified against NovaMart RAW-ALL-DATA, 1,600 customers, 14 days)

- Customer-event uploads create one period per **date** × segment. 84 of 182
  date-hours miss at least one cashier (no row), and a cashier serves a median
  of 2 customers per date-hour. Separate optimization therefore rejects most
  periods under full coverage, and DES service samples are too thin.
- Customer-event uploads reject `staffing_varies_by_period`, but NovaMart
  staffing changes during the day (C4–C5 start 06:00, C1–C3 end 17:00).
- Selected-plan DES simulates each period independently for 24 h from empty,
  so a break at 11:00 barely affects that period's evidence and nothing
  carries across hours (the item BLOCKED in the Decision C report).

## Approved product decisions (user, 2026-09-18)

1. **Pooling:** representative day. Per segment and queue:
   `lambda = arrivals / (segment_hours × D)`, `D` = number of distinct dates
   in the upload; `mu`, variance, and service samples from all service times
   of that segment and queue across all dates. Explicit setup option;
   default stays per-date so existing analyses do not change.
2. **Day model:** one continuous DES day from the earliest segment start to
   the latest segment end: arrival rate changes per segment, lanes open/close
   per the segment schedule, breaks fire at wall-clock offsets, queues and
   breaks carry across segment boundaries.
3. **Break joins:** keep the approved NovaQ break rule (a draining/on-break
   lane accepts no new arrivals).
4. **Full coverage with shifts:** every lane **scheduled** in a period must
   stay active; with fixed staffing that is every configured lane (unchanged).

## Behavior

- `QueueSetup.event_period_basis: "per_date" | "representative_day"`,
  default `"per_date"`. `representative_day` is only valid for
  `separate_queues`.
- Separate customer-event uploads accept `staffing_varies_by_period` (lanes
  come from each segment's `active_queue_ids`; `c` is always 1). Shared
  customer-event uploads still reject varying staffing.
- Representative-day records use the segment id (or `HH:MM-HH:MM`) as the
  period label, keep `segment_id`, and carry `observation_days = D`.
  Provenance records the basis and `D`.
- Full coverage per period: the lanes with records must equal the lanes
  scheduled for that period; the optimizer's lower bound is that count.
  Otherwise the request fails with an exact reason (never a silent drop).
- Selected-plan simulation for a representative-day analysis runs the
  continuous day; output keeps the existing per-period shape (lane rows keyed
  by arrival period, per-period duration) so Monte Carlo, validation,
  Decision, and reports consume it unchanged. Arrivals stop at the day end;
  service continues until every admitted customer is served (conservation).

## Unchanged (protected)

Queueing formulas, model selection, optimizer objective/cost/ranking,
routing policy (shortest live system size, seeded ties), empirical service
resampling, break lifecycle and 3-minute cutoff, day-origin conversion,
Monte Carlo semantics, Decision rules, per-date behavior (default).

## Known limitation

The optimizer still evaluates each period independently (24 h runs). Under
full coverage each period has exactly one candidate (the scheduled lanes), so
Optimize is a feasibility evaluation of the schedule; the continuous day is
used for Simulate and everything downstream of it.
