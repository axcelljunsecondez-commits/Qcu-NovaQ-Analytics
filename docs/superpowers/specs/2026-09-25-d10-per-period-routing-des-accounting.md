# D10: Per-Period Routing DES Accounting (Fixed Horizon)

Date: 2026-09-25. Status: approved for implementation by the product owner (D2/D10 review,
Decisions 1, 2, 3 and 5). Branch `fix/d1-replication-costs`, after D1 `c25591a7` and D5 `5291f7ec`.

## Scope

`_run_routing_des` and `evaluate_candidate_with_des` in
`backend/queueing_engine/services/separate_optimization.py`: the per-period routing DES used by
the per-date optimizer and by the per-date selected-plan DES. Additive disclosure fields in the
replication aggregate and in the selected-plan per-date DES lane rows.

Out of scope: the continuous-day simulator (`run_routing_day_des`, protected), the Current-state
DES (D2), D11, the available-time utilization denominator, horizon extension, engine versions.

## Definitions (one run, horizon H hours)

For customer i: admission time a_i (the generated arrival), routing time r_i >= a_i (later only
while no lane accepts arrivals), service start s_i, service end e_i. At H each admitted customer
is exactly one of:

- completed: s_i and e_i both before H;
- in service: s_i before H, e_i at or after H;
- waiting in a lane: routed, not started;
- unrouted: admitted, not yet routed (at most one, because arrivals pause while no lane accepts).

## Utilization (calendar time, preserved)

Lane busy time B = sum over customers who started on the lane of (min(e_i, H) - s_i). Service
after H is never credited. rho = min(1, B / H), the existing calendar-time definition with the
existing clamp. Before the repair a service in progress at H added nothing to B.

## Waiting time

Population: customers whose service started before H; their full queue wait w_i = s_i - a_i is
known. Wq = (sum of w_i over that population) / (its size), None when it is empty. It is a
started-service cohort mean, never an all-arrivals mean. Before the repair the numerator used
this population, the denominator counted only completed customers, and w_i was measured from r_i
instead of a_i.

## Censored customers

Customers waiting in a lane or unrouted at H are censored: their count and their partial observed
waits sum(H - a_i) are reported. A partial wait is a lower bound, never used as a complete wait,
never zero-filled, and no service start is invented.

## Waiting cost (D1/D5 unchanged for complete observations)

Complete exposure E = sum of w_i over the started population; waiting cost per hour =
rate x E / H, exactly the D1 formula (served / H x Wq x rate) whenever no customer is still in
service, and the same started-population exposure otherwise. D5 then multiplies by the period
length.

The cost objective needs every customer's complete wait. If any customer is censored, the
replication's waiting and total cost are undefined, with the reason. The started-cohort estimate
rate x E / H is reported separately as `started_cohort_waiting_cost` with its coverage (started
and censored counts); it is never presented as the complete cost. Through D1, a candidate with
an undefined replicated cost is not ranked and no optimum is claimed. Any other censoring-cost
policy needs its own specification.

## Feasibility

Unchanged rule (maximum over active lanes of the replication-mean utilization <= target),
evaluated on the corrected utilization.

## Verification

Independent references rebuilt from each run's own event trace and from an independent
regeneration of the admission times; the controlled one-lane, one-hour, 0.90-target case; the
13 regression cases of the D2/D10 review; D1 and D5 regression; and a before/after check that the
continuous-day simulator's outputs and costs are unchanged.

## Disclosure (presentation only; no metric changes)

The basis of a stored selected-plan DES result comes only from its recorded `execution`
provenance (`selected_des_wait_disclosure`; frontend `selectedDesWaitCoverage`), never from metric
values. That field has been present since selected-plan DES was introduced (`9cddeb55`).

Per period, censoring is one of four states:

- **Recorded:** a verified count, zero or positive.
- **Unknown:** a per-period run stored without the D10 fields, a malformed count, or an
  unrecorded basis.
- **Not applicable:** the continuous day serves every admitted customer.

A missing field is never read as zero.

- **Simulation page, DES detail:**
  - Per-period runs show "Started service" and "Still waiting at horizon", the Wq population
    and whether the complete waiting cost is available.
  - Older per-period runs show a note that they used the earlier accounting.
  - An unrecorded basis shows a note that it is unknown.
  - The continuous day is unchanged.
- **Simulation page, validation detail:** a per-period note of who Wq_sim covers. It comes from
  the validation job's `des_wait_disclosure`, or, for older validation jobs, from the loaded DES
  job only when it is exactly the linked one; otherwise the note says it cannot be stated.
- **Optimize page:**
  - For a period without an optimum, its reason.
  - Per candidate, "customers still waiting at the horizon in n of N replications".
  - A status legend. Feasibility is never changed because a cost is unavailable.
- **Report:**
  - The DES and Validation Excel sheets keep every existing column and append "Wq population"
    and "Still waiting at horizon (period)".
  - Limitations (preview, PDF and Excel) state the definition and the per-period counts.
  - The report chain already requires the validation job to be linked to the DES job it reads.

## Verification results (2026-09-25)

- `tests/test_separate_routing_des_accounting.py`: 16 tests. It passes on the repair. Run against
  the pre-repair code (HEAD `5291f7ec` export), 15 fail and the D5 case passes. Examples:
  controlled rho 0.9 vs 0.996509; no-completion rho 0.0 vs 0.861255; admission-based Wq
  0.032217 h vs 0.045378 h.
- Sample path unchanged: event traces and per-lane counts are identical before and after over 60
  runs (1 and 3 lanes, with and without a break, 7,820 events). The repair changes accounting only.
- Continuous-day simulator unchanged: NovaMart representative-day DES outputs (5 seeds) and the
  full-coverage schedule are identical before and after.
- Uncensored runs: the waiting cost is numerically unchanged. The old served x (sum over started
  waits / served) equals the started exposure. D1/D5 costs of complete observations are preserved.

## Consequence (reported, not decided here)

Customers still waiting at a 24 h per-period horizon are common, so the complete waiting cost is
often undefined. Sweep: 24 synthetic per-date periods (3 or 5 lanes, per-lane load 0.2 to 0.7,
5-20 min services, target 0.85, 5 replications, 24 h, base seeds 42 and 142).

- Unrestricted lane search: OPTIMAL in 24 of 24 before, and 5 of 24 after (19 UNSUPPORTED).
  69 of 96 candidates had at least one censored replication.
- Full-coverage search (the saved-plan path): OPTIMAL in 24 of 24 before, and 15 of 24 after
  (9 UNSUPPORTED).

Where an optimum is still claimed, the lane count is unchanged in every case.

Options that would restore cost ranking all change the cost definition or the horizon, so each
needs its own specification. Examples:

- a time-integrated in-horizon waiting exposure;
- a drain-after-horizon run that completes every admitted customer's wait without crediting
  busy time after H;
- a warm-up / steady-state estimator.

## Recorded findings (not authorized; separate investigations)

- **D11:** per-date optimization needs a record for every scheduled lane in every period. NovaMart
  has 0 of 14 dates optimizable because some lane-period records are absent. Distinguish:
  - observed zero arrivals;
  - a missing observation;
  - a missing normalized record;
  - an unknown service distribution;
  - unavailable staffing.

  Never invent arrivals or samples.
- **A:** Compare weights period waiting times by arrival rate, not expected arrivals
  (rate x duration). Verify the metric definition and the zero-arrival treatment.
- **B:** stored selected-plan per-date period costs (`server_cost`, `waiting_cost`, `total_cost` in
  `_run_selected_plan_des`) keep hourly-rate semantics. Verify consumers before any change.
