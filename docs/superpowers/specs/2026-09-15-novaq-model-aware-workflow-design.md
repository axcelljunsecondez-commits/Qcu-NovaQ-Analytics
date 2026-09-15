# NovaQ Model-Aware Workflow, Optimization, DES Playback, Decision, and Reporting Design

Date: 2026-09-15
Mode: repository-first, minimal additive generalization (Approach A)
Status: design — approved sections 1–5, implementation not started

## 0. Goal

Refine NovaQ into a model-aware architecture where queue structure determines
operational layout, central model selection determines mathematics, optimization
dispatches per supported model, DES remains unified, playback renders by queue
structure, Compare/Decision consume verified evidence, and Reports adapt by
structure/model/evidence — without inventing unsupported models, optimizers, or
evidence.

Target hierarchy (conceptual):

```text
CURRENT DATA
  → QUEUE STRUCTURE (pooled / separate)
  → SUPPORTED MODEL SELECTION (central select_model)
  → MODEL-APPROPRIATE OPTIMIZER (or BLOCKED)
  → OPTIMIZED SCENARIO (only when genuinely optimized)
  → UNIFIED DES
  → NORMALIZED TRACE
  → PLAYBACK (pooled view / separate view by queue_structure)
  → COMPARE → DECISION → REPORTS
```

Fallback (supported):

```text
CURRENT → CURRENT DES → PLAYBACK → CURRENT-ONLY REPORT
```

## 1. Verified repository findings (pre-change)

- Single source of truth: `backend/queueing_engine/services/model_selection.py`
  (`select_model` / `_select_model`). Dispatch precedence: separate_queues branch
  → theta>0 Erlang-A → K+variance M/G/c/K → K M/M/c/K → variance M/G/c →
  c==1 M/M/1 → else M/M/c.
- `queue_structure` (input layout: `shared_queue | single_server |
  separate_queues | unknown`) is distinct from `model_id` (output math id).
  Both are persisted (e.g. `data_processing.py` CURRENT_COLUMNS).
- Separate branch yields `parallel_mg1` only when `c==1 + variance +
  unlimited + no theta`; otherwise `separate_fifo_unsupported`.
- Optimizer (`services/optimization.py`) searches only `c_optimal` by
  brute force; supports 6 non-separate paths; explicitly rejects
  `separate_queues / parallel_mg1` (Phase A). No demand-allocation / routing
  policy exists; `queue_lifecycle.py` deliberately does not route.
- DES: one file `simulation/simulation.py` with unified entry
  (`simulate_segments`, `simulate_segments_with_trace`) branching to shared
  M/M core vs parallel dedicated-queue core. Coverage gate supports M/M/1,
  M/M/c; parallel M/G/1 via workflow empirical path. Trace events:
  `arrival | service_start | service_end` with
  `t, type, segment_id, customer_id, server_id, queue_len_after` plus optional
  `queue_id, service_time_hours`. Output `queue_structure: shared | separate`.
- Frontend playback is shared-only (`LiveSimulationPlayback.tsx` hardcoded,
  `simulationPlayback.ts` ignores queue_id, types expect numeric ids).
- Compare reads `Scenario.results` (Current-vs-Optimized), no DES.
- Decision (`workflow.py _derive_decision`) is pure interpretation, no recalc.
- Reports: PDF (title/executive/staffing/comparison/recommendations) + Excel
  (summary/segments/recommendations), minutes conversion; separate datasets
  currently 422.
- Canonical order: Setup → Current → Optimize → Compare → Simulate →
  Decision → Reports (Compare persists verified scenario selection;
  `_require_selection` enforced).

## 2. Verified support matrix (do not invent support)

| Queue structure | Model id | Current | Optimizer | DES | Playback | Compare | Decision | Reports |
|---|---|---|---|---|---|---|---|---|
| shared/single | mm1 | yes | yes | yes | yes (shared) | yes (when optimized) | yes (with full evidence) | yes |
| shared/single | mmc | yes | yes | yes | yes (shared) | yes | yes | yes |
| shared/single | mgc | yes | yes | no | no | yes (analytical) | gated (needs DES) | yes (analytical) |
| shared/single | mmc_k | yes | yes (capped) | no | no | yes | gated | yes |
| shared/single | mgc_k | yes | yes (capped) | no | no | yes | gated | yes |
| shared/single | mmc_erlang_a | yes | yes | no | no | yes | gated | yes |
| separate_queues | parallel_mg1 | yes (when prerequisites met) | BLOCKED — DEMAND ALLOCATION POLICY NOT DEFINED | yes (empirical path) | to be added (separate view) | GATED / N-A | GATED | CURRENT-ONLY (new) |
| separate_queues | separate_fifo_unsupported | gated | BLOCKED | no | no | GATED | GATED | gated |

## 3. Architectural problems found (verified)

1. Playback routing is effectively shared-only; no `queue_structure`-routed
   separate renderer despite backend separate trace identity.
2. Frontend trace types (`server_id: number|null`, numeric `segment_id`, no
   `queue_id`) mismatch backend (`server:Q1` strings, string segment ids).
3. No Current-DES fallback: simulation requires verified optimized selection
   even when Current+DES are supported but optimizer is BLOCKED.
4. Reports blanket-422 separate datasets even when Current+Current-DES are valid.
5. Risk of hard-coded `pooled==M/M/c` / `separate==Parallel M/G/1` if future code
   routes by `model_id` instead of `queue_structure` (must not introduce).

## 4. Final workflow (implemented order)

Preserve optimized path:

```text
Setup → Current → Optimize → Compare → verified selection → Simulate
  → Decision → Reports
```

Add Current-DES fallback (distinct provenance):

```text
Validated persisted Current → Current DES (unified engine, provenance=CURRENT)
  → Separate/Shared Playback → Current-only Report
```

Current-DES must not create `c_optimal` / `optimized_stable` / fake Scenario,
must not satisfy Compare selection or `_require_selection` for optimized
simulation, must not unlock optimized Decision/Reports.

## 5. Model / optimizer dispatch

- Keep `select_model` authoritative; downstream consumes `model_id` +
  `queue_structure`, never re-dispatches inline.
- Supported pooled/single models route to existing `optimize_segment`
  brute-force `c` search (unchanged math, unchanged contracts).
- `separate_queues / parallel_mg1` → explicit BLOCKED with reason
  `BLOCKED — DEMAND ALLOCATION POLICY NOT DEFINED`; no `c_optimal`, no
  lambda redistribution, no invented routing.
- No optimizer registry refactor in this task.

## 6. DES architecture

- One unified DES (`simulation.py` + `queue_lifecycle.py` for parallel
  schedule/lifecycle). No duplicated engines.
- Shared core (SimPy Resource capacity=c) for mm1/mmc; parallel core
  (per-queue Resource cap=1 + DedicatedQueueLifecycle) for parallel_mg1.
- `rho>=1` remains DES-executable finite-horizon (backlog reported), still
  analytically unstable. Preserve existing rules.
- Trace contract preserved + documented; no invented event types.

## 7. Playback architecture

```text
UNIFIED DES → normalized trace → PLAYBACK ENGINE → queue_structure
  → pooled → existing shared renderer
  → separate_queues → new separate renderer
```

- Normalize/widen frontend types additively (`string | number` for
  queue/server/segment ids); backend authoritative. Map trace-level
  `queue_structure: shared` to the pooled renderer and `separate` to the
  separate renderer, corresponding to setup-level `shared_queue /
  single_server` (by physical layout) and `separate_queues` respectively.
- Separate view: per-queue + dedicated server, trace `queue_id`/`server_id`
  preserved, no pooling, no rerouting; ACTIVE→DRAINING→INACTIVE only from
  evidence; draining queues persist visually while customers remain.
- Controls (play/pause/restart/step/speed/timeline) presentation-only; same
  trace → same events regardless of speed.

## 8. Decision architecture

One `_derive_decision` interpretation layer consuming persisted Current +
optimization + DES + Compare + validation/cost evidence. No recalculation of
lambda/Wq/rho/costs/KPIs. Separate wording preserves dedicated-pair semantics
(never `Set c = 4` when meaning `Operate 4 dedicated queue-server pairs`).
Without verified optimization evidence: GATED / NOT AVAILABLE FOR
OPTIMIZATION RECOMMENDATION. Current-DES never counts as optimized evidence.

## 9. Report architecture

One adaptive framework (`report_export.py` + `api/reports.py`) branching on
`queue_structure + model_id + evidence status`. Sections: analysis info,
dataset/validation, queue config (pooled/separate + servers/segments),
model selection, Current (per-queue when separate + weighted aggregates),
optimization (or BLOCKED), DES validation (measurable KPIs, conservation,
lifecycle, per-queue), comparison status, decision status, assumptions/
limitations/evidence status. Missing → N/A/Blocked, never 0. Preserve minute
conversion. Add CURRENT-ONLY mode for verified separate Current+Current-DES.

## 10. Files to change (plan, not yet changed)

- Backend: workflow/simulation access for Current-DES fallback (additive,
  preserve `_require_selection` for optimized); `api/reports.py` +
  `reports/report_export.py` current-only mode (remove blanket separate 422
  only for verified Current path); explicit BLOCKED reason plumbing where
  missing (reuse existing optimizer gate; no math change).
- Frontend: `api/types.ts` trace widening; `lib/simulationPlayback.ts`
  queue_structure routing + identity preservation; new
  `SeparateSimulationPlayback` renderer + routing in `SimulationPage` /
  `LiveSimulationPlayback` integration; Compare/Decision/Reports gating copy
  (EN+TL locale symmetry); workflow lib for Current-DES entry.
- Tests: backend + frontend regressions groups A–N (see §11).

## 11. Tests to add (before implementation)

A. Structure persists; B. central authority, no model reinterpretation;
C. supported optimizer correct + separate BLOCKED, no fake evidence;
D. pooled stays shared; E. separate identity intact, no pooling;
F. unified DES (both paths same engine); G. Current-DES fallback + provenance;
H. playback routing by queue_structure; I. trace-driven playback, speed-safe;
J. lifecycle ACTIVE→DRAINING→INACTIVE; K. Compare distinct + gated;
L. Decision consumes evidence, correct separate wording;
M. current-only reports render with BLOCKED/N-A, no zeros;
N. provenance separation + legacy M/M regressions green.

## 12. Verification

Focused tests → protected suites (model selection, queue models,
optimization, workflow, scenarios, DES/API, Compare, Decision, Reports) →
full `python -m pytest tests/ -x --tb=short` → `ruff check .`, `mypy .`,
`git diff --check` → frontend focused + full tests, `npm run typecheck`,
`npm run lint`, `npm run build`, locale symmetry. Report exact commands and
real counts; never claim unexecuted passes.

## 13. Remaining limitations (verified)

- Separate optimization BLOCKED until demand-allocation policy is defined,
  persisted, justified, tested.
- DES/playback for mgc/mmc_k/mgc_k/erlang_a remain unsupported unless proven.
- No abandonment transitions in DES trace (`abandonment_supported: false`).
- Count-based (not identity-based) cross-segment carryover (pre-existing).

## 14. Completion checklist

- [ ] structure vs model distinct
- [ ] central selection authoritative
- [ ] matrix documented from evidence
- [ ] pooled not hard-coded M/M/c; separate not hard-coded parallel_mg1
- [ ] unsupported gated; no fake evidence; separate BLOCKED stated
- [ ] Current baseline valid; Current-DES + Optimized-DES share engine
- [ ] trace compatible; playback by queue_structure; pooled + separate work
- [ ] playback presentation-only; Compare provenance kept
- [ ] Decision interpretation-only + correct wording
- [ ] Reports adaptive + current-only + N/A-not-zero
- [ ] legacy workflows green; full/static checks pass

## 15. Final status

ARCHITECTURE REFINEMENT INCOMPLETE — UNPROVEN ITEMS REMAIN GATED
(design approved; implementation + verification pending)
