# Separate-Queue Monte Carlo / Validation Semantics (Frozen)

Date: 2026-09-17
Mode: repository-first audit freeze (Problem 6B)
Status: frozen contract — implementation not started, gates stay closed until proven

## 0. Authority and scope

This contract freezes what separate-queue Monte Carlo (MC) and validation
mean, based on the Problem 6 audit of current production code. It changes no
production behavior. Separate MC/Validation remain unavailable until an
implementation proves every rule below with tests.

Authoritative audit evidence (all verified in current source):

- `mc_simulate_segment` evaluates one segment dict at a time; it never pools
  queues (`backend/queueing_engine/simulation/simulation.py`).
- Failure is trial-level: per-trial ρ vs the persisted utilization threshold,
  `failure_rate` = failing fraction, Wilson 95% CI, PASS iff rate ≤ persisted
  cap. This definition is reused unchanged.
- `_pick_model` currently assumes the M/M family and is unsafe for
  variance-bearing separate rows; separate rows fail closed today with an
  explicit unsupported-model error and `failure_rate: None`.
- MC output carries no `queue_id`; validation records omit it; validation
  merges by `time` only.
- `mg1` exists and is verified, so no new queueing formula is required for
  supported separate M/G/1 rows.
- Workflow MC/validation/Decision require a verified selected scenario plus
  optimizer output, which separate analyses cannot produce while staffing
  optimization stays blocked; SimulationPage disables MC/Validate in
  Current-DES mode. These gates stay closed until implementation is proven.

## 1. Row identity (frozen)

For separate queues the analytical identity is `(time, queue_id)`. Never
`time` alone. Never pool queue IDs. Queue IDs are opaque identifiers —
`cashier-east`, `express`, `lane_03`, `counter-A`, and IDs containing spaces
must all work unchanged.

## 2. MC execution semantics (frozen)

For every supported separate-queue row: `(time, queue_id) → MC(row
parameters)`, each row independently. Reuse unchanged: lambda perturbation,
mu perturbation, trial count, utilization threshold, trial-level failure
definition, Wilson CI, adequacy/precision classification, persisted failure
cap, PASS/FAIL calculation. Never create a multi-queue MC trial combining
independent queues.

## 3. Model dispatch semantics (frozen)

MC dispatch must follow the same supported model identity implied by the
authoritative central coverage/model rules. The universal
`c > 1 → M/M/c / otherwise → M/M/1` selector must not decide separate rows.
Supported variance-bearing separate `c=1` rows use the existing verified M/G/1
implementation where central rules identify that model. Unsupported
combinations keep failing closed. No approximation may be invented to make
unsupported combinations run.

## 4. Queue identity propagation (frozen)

Every separate MC result preserves `time`, `queue_id`, model identity, and
the provenance required by existing evidence contracts. Validation records
retain `queue_id`; validation matching uses `(time, queue_id)` for separate
queues. Shared-queue matching stays time-based unless common infrastructure
can be extended without altering its semantics.

## 5. Missing-data semantics (frozen)

Configured-but-inactive queues produce no row for absent periods. Never
synthesize `lambda = 0`, `failure_rate = 0`, utilization `0`, or PASS for
missing queue-period rows. Missing remains missing; unavailable remains
N/A / `—`; unstable/unavailable results remain null, never zero.

## 6. Overall validation aggregation (frozen)

No pooled, averaged, or demand-weighted system failure rate for separate
queues. Each `(time, queue_id)` keeps its own MC result and PASS/FAIL
evidence; this does not modify the trial/row-level failure definition:

- **FAIL** — any required, valid validation row has a row-level FAIL verdict.
  A failing queue is never averaged away.
- **INSUFFICIENT EVIDENCE** — no valid row fails, but some required row is
  missing, unsupported, errored, stale, or otherwise inadequate under
  existing validation evidence rules. Represent with existing
  incomplete/insufficient-evidence semantics, never PASS or zero.
- **PASS** — only when every required validation row is current, supported,
  adequate under existing rules, and row-level PASS. No new numeric
  system-level failure rate is introduced.

## 7. Decision consumption (frozen)

Decision outcome taxonomy (Adopt / Conditional / Revise /
Insufficient-evidence) and substantive rules are unchanged. Decision consumes
separate validation evidence by `(time, queue_id)` identity only. No
optimization evidence, staffing recommendations, savings, ROI, or pooled
failure metrics may be invented. Incomplete required evidence uses existing
insufficient-evidence behavior.

## 8. UI gating (frozen)

Separate MC/Validate stay disabled until backend support, persistence,
identity, validation matching, Decision consumption, and tests are all
proven. Gates are removed only by a complete proven implementation, never
during partial work.

## 9. Protected behavior (frozen)

Unchanged throughout: shared-queue MC/validation behavior, lambda/mu
perturbation math, trial counts, utilization threshold, Wilson 95% CI,
precision/adequacy rules, persisted failure cap, queueing formulas, central
model selection, DES, playback, optimizer and its economics, Decision
taxonomy, evidence staleness rules, report semantics, null ≠ zero behavior.

## 10. Implementation proof required (before any enablement)

Tests must prove: arbitrary queue IDs survive MC; every MC row retains
`queue_id`; variance-bearing supported rows dispatch to the existing correct
model; unsupported rows fail closed; unstable/unavailable stay null/N/A;
validation joins by `(time, queue_id)` with no cross-matching between
same-time queues; inactive queues create no synthetic rows; missing periods
stay missing; one FAIL row forces overall FAIL; incomplete evidence cannot
become PASS; all-supported/all-adequate/all-PASS yields overall PASS;
Decision consumes queue-specific evidence; shared behavior unchanged; Wilson
and failure-definition behavior unchanged.
