# NovaQ workflow integration verification report

Date: 2026-09-13

## Outcome

The two stop conditions recorded by the pre-integration audit at commit
`5646f6cc` are resolved in the current repository:

- DES aggregate results and Live playback events now originate from one
  instrumented SimPy execution path.
- Decision now consumes durable, ownership-scoped workflow evidence and Reports
  consume the matching persisted Decision.

The implementation was introduced by commit `bb7b138c` and verified on current
HEAD `46334f84`. This report supersedes the old stop conditions as a statement
of current status; it does not rewrite the historical audit result.

## DES equivalence evidence

`backend/queueing_engine/simulation/simulation.py` has one multi-segment core:

- `simulate_segments` calls `_simulate_segments_core` without a recorder.
- `simulate_segments_with_trace` calls the same `_simulate_segments_core` with
  a bounded `_TraceRecorder`.
- `trace_simulate_segments` is a compatibility wrapper around
  `simulate_segments_with_trace`.
- The recorder observes arrival, service-start, and service-end transitions. It
  does not draw random values or choose resources.
- Reaching `max_events` stops recording only; the SimPy run continues and still
  produces the complete aggregate result.

Regression coverage in `tests/test_simulation.py` compares traced `results`
with ordinary aggregate results using identical durations, seeds, and carryover
settings across single-server and multi-server, single-segment and
multi-segment configurations. A separate capped-trace test proves that event
truncation does not truncate or change aggregate simulation results.

## Decision evidence

`backend/api/workflow.py` persists user-owned `Job` records for:

- `workflow_selection`
- `workflow_des`
- `workflow_mc`
- `workflow_validation`
- `workflow_decision`

The persisted Decision records the IDs of the exact selection, DES, standalone
Monte Carlo when present, and validation evidence used in derivation. Retrieval
recomputes staleness against the current evidence and withholds an outdated
Decision. Missing or incomplete evidence produces `insufficient_evidence`
rather than an adoption claim.

Regression coverage in `tests/test_workflow_api.py` proves:

- simulation is rejected before Compare selects a verified Scenario;
- incomplete evidence produces `insufficient_evidence`;
- selection, unified DES, validation, and Decision survive retrieval;
- the persisted Decision contains the exact evidence IDs used to derive it;
- cross-owner Scenario selection is rejected;
- a newer simulation makes the prior Decision stale and unavailable;
- pass, fail, conditional, and incomplete Decision outcomes are deterministic.

`tests/test_reports_api.py` proves that analysis-scoped reports use the saved
Decision recommendation and explicitly report when a valid current Decision is
unavailable.

## Verification

Focused backend verification command:

```text
python -m pytest tests/test_simulation.py tests/test_simulation_api.py tests/test_workflow_api.py tests/test_reports_api.py -x --tb=short
```

Result after the strengthened assertions: **86 passed and 6 subtests passed**
in 91.97 seconds.

Focused frontend verification:

```text
npm test -- src/components/analysis/DecisionEndpointPage.test.tsx src/pages/SimulationPage.test.tsx src/pages/ReportsPage.test.tsx
```

Result: **3 test files and 15 tests passed** in 62.28 seconds.

Additional checks:

- `python -m ruff check tests/test_simulation.py tests/test_workflow_api.py`:
  passed.
- `npm run typecheck`: passed.
- `npm run lint`: passed with two pre-existing Fast Refresh warnings in
  `NovaQInsights.tsx`.
- `git diff --check`: passed; Git reported only line-ending conversion
  notices.

These are focused workflow verification results, not a claim that every
repository-wide gate was rerun.

## Simulation UI refinement entry gate

**Status: CLEARED FOR SIMULATION REFINEMENT SPECIFICATION.**

The repository confirms that the earlier “DES equivalence not proven” and
“Decision evidence missing” findings are historical findings from commit
`5646f6cc`, not defects in the current implementation. They are excluded from
the new Simulation UI refinement problem statement. Their remediated behavior
is instead treated as protected behavior that subsequent refinement must
preserve.

| Protected fact | Current implementation evidence | Regression evidence |
|---|---|---|
| Aggregate DES and playback events share one execution | `simulate_segments` and `simulate_segments_with_trace` both delegate to `_simulate_segments_core`; tracing is an optional recorder | `test_trace_and_aggregate_results_match_across_configurations` |
| Trace caps do not shorten aggregate simulation | `_TraceRecorder.record` stops recording at `max_events` without stopping the SimPy environment | `test_trace_cap_does_not_truncate_aggregate_simulation` |
| One frontend response drives playback and aggregate presentation | `SimulationPage` derives `desRows` from `trace.results`, passes the same `trace` to `LiveSimulationPlayback`, and uses those rows for charts and CSV | `SimulationPage.test.tsx`: “uses one persisted DES result for metrics, charts, and playback” |
| Simulation uses the Scenario selected in Compare | `backend/api/workflow.py::run_des` calls `_require_selection` and derives segments server-side from that verified Scenario | Workflow API and `SimulationPage` selection-required tests |
| Simulation evidence is durable and ownership-scoped | `workflow_des`, `workflow_mc`, and `workflow_validation` are saved as user-owned `Job` records | `test_workflow_persists_selection_simulation_validation_and_decision` and `test_workflow_selection_is_owner_scoped` |
| Decision is evidence-derived and stale evidence is withheld | `_derive_decision` records exact evidence IDs; `_current_evidence` compares them with current evidence and suppresses a stale Decision | persisted evidence-ID assertions, deterministic outcome tests, and `test_new_simulation_makes_saved_decision_stale` |
| Reports consume the current persisted Decision | analysis-scoped report routes call `current_decision_for_report` | both analysis-scoped report tests |

### Allowed refinement scope

The next specification may refine Simulation-page information hierarchy,
plain-language explanations, control grouping, table and chart presentation,
playback layout and controls, responsive behavior, focus order, screen-reader
labels and announcements, reduced motion, semantic status presentation, and
English/Filipino copy.

### Protected scope

Refinement must not change:

- the selected verified Scenario as the Simulation input;
- workflow API request/response meaning or evidence persistence;
- the shared DES lifecycle, random draws, warm-up, carryover, or trace-cap
  behavior;
- the rule that playback, KPI cards, charts, tables, and CSV use one persisted
  trace response;
- event ordering, customer/server identity, or shared-FIFO representation;
- the configured server count or conditional abandonment display;
- DES, Monte Carlo, or validation calculations and status rules;
- Decision derivation, evidence IDs, freshness/staleness, ownership, or Report
  consumption.

This gate permits Phase 2 Simulation refinement specification work. It does not
by itself satisfy the full Phase 2 and Phase 3 exit gates or authorize Phase 4
implementation. Before implementation, the Simulation-specific specification
must define affected states, responsive and accessibility acceptance criteria,
translation changes, and tests, then map every protected contract above into
the approved safety boundary.

## Protected behavior

No queueing formula, model-selection rule, optimizer equation, Monte Carlo
distribution, confidence rule, scenario snapshot meaning, or legacy
`/simulation/*` response field was changed while strengthening this evidence.
