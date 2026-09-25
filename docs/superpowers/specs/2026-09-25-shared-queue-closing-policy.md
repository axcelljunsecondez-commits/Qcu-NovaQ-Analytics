# Shared Queue Enhancement: Phase 3A, Closing Policy and Day Cost

Date: 2026-09-25. Status: approved by the product owner on 2026-09-25 (chat decisions recorded
below). Not wired into any API, page, report, or saved scenario.

Builds on Phase 3 (`2026-09-24-shared-queue-continuous-des.md`, `9eaf5d4a`), whose closing
policy was UNRESOLVED: the engine observed the horizon only and reported customers still
waiting or in service at the end.

## Approved decisions

1. Two closing policies, **DRAIN** and **HARD_CUTOFF**. Every run must name one; there is no
   default.
2. HARD_CUTOFF: arrivals stop at closing, customers still waiting are recorded as unserved,
   and services already under way finish (non-preemptive).
3. DRAIN: arrivals stop at closing, and the servers on duty at closing keep serving the line
   with no overrun cap. A server that is draining at closing only finishes its own customer.
   Each server closes once it is idle and nobody is waiting. When no server is on duty,
   waiting customers are recorded as unserved (reason `no_eligible_server`), so draining
   cannot run forever.
4. Costs use rates the caller supplies, with no defaults, in a calculation separate from the
   DES:

   ```
   total_cost = regular_server_hours × regular_server_rate
              + overtime_server_hours × overtime_rate
              + total_waiting_customer_hours × waiting_rate
              + unserved_customer_count × unserved_customer_rate
   ```

   The unserved-customer term applies only when the configured closing policy can produce
   unserved customers. A missing rate is never replaced by zero.
5. Server-hours are modeled service-capacity hours, not necessarily paid employee-hours.

The separate-queue day DES also drains after closing
(`separate_optimization.run_routing_day_des`). The shared behavior here comes from the
decisions above, not from that code.

## Closing (horizon end = closing time)

Arrivals exist only inside `[start, end)` (Phase 3 validation and generation). So "arrivals
stop at closing" already holds, and the tests pin it.

Order at the closing time `end`:

1. Events before `end` run exactly as in Phase 3.
2. Service completions at exactly `end` are processed; those customers depart at closing,
   without overtime. No customer is assigned during this step.
3. The at-close state is recorded: waiting customers, customers in service, accepting
   servers, and draining servers.
4. The policy is applied:
   - HARD_CUTOFF: every waiting customer becomes `unserved_at_close` (reason
     `hard_cutoff`), in line order. Idle servers close. No service starts at or after `end`.
   - DRAIN: if no accepting server exists and customers are waiting, each becomes
     `unserved_at_close` (reason `no_eligible_server`). Otherwise, idle accepting servers take
     waiting customers first come, first served (lowest server number first). Idle servers
     with nobody waiting close.
5. After `end`, only completions remain. At each completion, a draining server closes. Under
   DRAIN, a freed accepting server takes the next waiting customer, or closes if nobody
   waits. Under HARD_CUTOFF it closes.

Services that start after closing (DRAIN only) last `work / μ`, with μ the final demand
period's rate, because no demand data exists after closing. Termination: after closing there
are no new arrivals or capacity events, so the run ends after at most (in service + waiting at
closing) completions. The engine asserts that no customer is still waiting or in service and
that every server is closed when it returns.

### When unserved customers are possible

- HARD_CUTOFF: always possible.
- DRAIN: accepting servers always equal the scheduled count, so the crew on duty at closing
  is the final staffing segment's count. Unserved customers are possible exactly when that
  count is 0.

This configuration-level flag (`unserved_possible`) decides whether the unserved-customer
cost term applies. A run where the term applies but nobody was unserved still needs the
rate: the rule depends on the configured policy, not on the realized count.

## Outputs (additive to Phase 3 unless stated)

- Customer `status` is `departed` or `unserved_at_close`. The Phase 3 statuses
  `in_service_at_end` and `waiting_at_end` can no longer occur and are removed. An unserved
  customer has `unserved_reason` and `elapsed_wait_at_close_hours` (closing − arrival); its
  `wait_hours` stays `None` (censored, not zero).
- Per staffing segment, `waiting_at_end` is replaced by `unserved_at_close`
  (arrival-attributed). All time-attributed segment values still cover `[start, end)` only.
- Totals: `unserved_at_close` replaces `waiting_at_end` and `in_service_at_end`, and
  conservation is arrivals = departed + unserved_at_close. The mean wait is over customers
  who started service, including starts after closing under DRAIN. The in-horizon keys keep
  their Phase 3 meaning.
- `closing` (replaces `horizon_end`):
  - policy and rule text;
  - closing time;
  - at-close state;
  - unserved customer ids;
  - `unserved_possible` and its reason;
  - starts and completions after closing;
  - after-close server-hours, busy server-hours, and waiting customer-hours;
  - last server release, and the overrun (last release − closing, 0 when none).
- `cost_quantities` (no money):
  - `regular_server_hours`: present server-hours inside the horizon, including above-schedule
    drain time during the day;
  - `overtime_server_hours`: present server-hours after closing;
  - `total_waiting_customer_hours`: waiting customer-hours before plus after closing;
  - `unserved_customer_count` and `unserved_possible`.
- Events and transitions at or after closing carry `segment_id: None`. New trace types:
  `closing` and `unserved_at_close`.

## Cost calculation (`services/shared_day_cost.py`)

`DayCostRates(regular_server_rate, overtime_rate, waiting_rate, unserved_customer_rate)`
takes four required fields with no defaults. `None` means not supplied. A supplied rate must
be a finite number, 0 or more; an explicit 0 is accepted and recorded.

`cost_shared_day(result, rates)` reads `cost_quantities` only. Each component is reported
with its quantity, unit, rate, cost, and status:

- `COSTED`: cost = quantity × rate.
- `RATE_MISSING`: the component applies, but no rate was supplied. The cost is `None`.
- `NOT_APPLICABLE`: only the unserved term when `unserved_possible` is false. A supplied
  rate is recorded as not applied.

`total_cost` is the sum of the costed components only when no applicable rate is missing.
Otherwise it is `None`, with the missing rates named. Rates are in the caller's currency; the
module assumes none. The legacy `REGULAR_RATE` and `OT_RATE` are not used.

## Verification

- Exact deterministic closing cases (μ = 1, binary-exact times):
  - an empty system at closing;
  - waiting customers under both policies;
  - busy servers finishing after closing;
  - a server draining at closing;
  - a completion exactly at closing;
  - a zero-capacity final segment under both policies (no infinite drain);
  - zero capacity mid-day then closing;
  - a staffing transition just before closing;
  - a service after closing using the final μ.
- Sample-path identities over the whole run:
  - waiting customer-hours = Σ served (start − arrival) + Σ unserved (closing − arrival);
  - busy server-hours in and after the horizon = Σ service time.
- In-horizon results are identical under both policies for the same inputs. This holds for
  every Phase 3 exact case, and for seeded runs on the in-horizon trace and the time
  integrals.
- Conservation, identity, and first-come-first-served order under both policies on seeded
  multi-transition runs.
- Cost: hand-computed totals, missing rates, explicit zero rates, non-applicable unserved
  rate, and invalid rates.
- Regression: the Erlang C benchmark under both policies, the full backend suite, the
  separate-queue suites, ruff, and mypy.
