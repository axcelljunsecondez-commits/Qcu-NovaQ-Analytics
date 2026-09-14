# NovaQ workflow restructure — repository audit and stop report

> **Historical baseline:** This report describes the pre-integration state at
> commit `5646f6cc`. The DES-equivalence and Decision-evidence gaps recorded
> below were remediated by `bb7b138c`. Current proof is recorded in
> `docs/superpowers/reports/2026-09-13-workflow-integration-verification-report.md`.

Date: 2026-09-13

## Requested workflow

`Setup → Current → Optimize → Simulate → Compare → Decision → Reports`

This document records the mandatory repository-first audit performed before any
application code change. The repository state at commit `5646f6cc` is the source
of truth.

## Repository findings

- The active-analysis routes already exist under `/analyses/:analysisId` for all
  seven requested stages.
- `AnalysisWorkspace` renders two horizontal navigation controls: a four-item
  setup/progress strip and a second major-stage tab row. The major-stage row
  duplicates the intended sidebar workflow.
- `Sidebar` does not currently render an active-analysis workflow. Its Optimize,
  Simulate, Compare, and Reports links use `/analyses/latest/...`, but
  `AnalysisWorkspace` accepts only numeric IDs. Those links therefore produce an
  invalid workspace context and redirect to `/analyses`.
- The global Datasets page is not a reusable cross-analysis attachment library,
  but it does provide global history, upload, validation status, deletion, and
  legacy-analysis compatibility. It is not proven dead.
- `AnalysisPage` is an independent expert/manual calculator for six explicitly
  selected queueing models. It does not own analysis-workspace state and remains
  a legitimate Tool.
- Current uses the latest successfully processed dataset and remains baseline
  analytical output.
- Optimize reads an analysis-scoped dataset, invokes the existing optimizer, and
  saves an immutable, server-verified calculation snapshot as a Scenario.
- Simulate currently selects a dataset, not a saved Scenario. Its Validate tab
  re-runs the optimizer from editable local options before invoking simulation.
- Simulation, Monte Carlo, and validation results are component state only. No
  persisted validated-scenario record or retrieval endpoint was found.
- Compare consumes saved Scenario results and preserves scenario identity and
  provenance.
- Decision currently shows only a three-item completion checklist based on setup,
  dataset presence, and scenario presence. It does not consume Current,
  simulation, Monte Carlo, or comparison evidence.
- Reports independently calls backend `build_recommendations()` from dataset or
  Scenario optimization rows. It does not consume a Decision recommendation.

## NOT FOUND IN CURRENT REPOSITORY

- A saved-Scenario selector or saved-Scenario input path on `SimulationPage`.
- Persistence for DES results, Live trace results, Monte Carlo results, or
  validation results.
- A durable “validated scenario” entity or field.
- Persisted comparison selection/evidence.
- A Decision evidence API or persisted Decision result.
- A Report path that consumes Decision as its recommendation source of truth.

## KEEP / MOVE / MERGE / REMOVE / REWORK assessment

| Element | Current location/purpose | Dependencies | Action | Reason |
|---|---|---|---|---|
| My Analyses | `AnalysesPage`; lists, opens, archives owned analyses | analyses API, auth | KEEP | Canonical workspace entry point |
| New Analysis | `NewAnalysisPage`; creates named analysis | `POST /analyses` | KEEP | Required workflow entry |
| Active Analysis selector/header | `AnalysisWorkspace` | `getAnalysis`, `listAnalyses`, route ID | KEEP | Preserves refresh, direct URL, and analysis switching |
| Setup | `/analyses/:id/setup` | analysis and dataset APIs | REWORK | Keep page; make setup progress distinct from major navigation |
| Guided Setup | `/analyses/:id/guided-setup` | `patchAnalysis` | KEEP | Independent guided operation questionnaire |
| Queue Setup | `AnalysisSetupPage` | `PATCH /analyses/:id` | KEEP | Required operational configuration |
| Upload Data | `AnalysisSetupPage` | `POST /analyses/:id/datasets` | KEEP | Owns analysis-scoped ingestion |
| Model Selection | analysis current backend services | centralized model selection | KEEP/PROTECT | Existing authoritative dispatch |
| Analyze | `AnalysisCurrentPage` and current endpoint | processed dataset, KPI/model services | KEEP | Produces baseline evidence |
| Current | `/analyses/:id/current` | `GET /analyses/:id/current` | KEEP | Baseline-only semantics already present |
| Optimize | `/analyses/:id/optimize` | dataset, optimizer, scenario API | KEEP/PROTECT | Candidate generation and verified snapshot persistence |
| Simulate | `/analyses/:id/simulate` | dataset, DES, trace, MC, validation APIs | REWORK/UNRESOLVED | Does not currently use a selected saved Scenario |
| Standard DES interface | DES tab in `SimulationPage` | `simulateDes`, `/simulation/des` | KEEP | Unique aggregate metrics and warm-up behavior |
| Aggregate row playback | local `SimulationPlayback` in `SimulationPage` | standard DES result rows | KEEP pending decision | Presentation is unique but can be confused with event playback |
| Live DES / queue playback | Live tab and `LiveSimulationPlayback` | `simulateDesTrace`, `/simulation/des/trace` | KEEP/REWORK | Real events, but generated by a separate DES execution path |
| Monte Carlo | MC tab | `/simulation/mc` | KEEP/PROTECT | Independent risk evidence |
| Validate | Validate tab | optimizer plus `/simulation/validate` | KEEP/REWORK | Valuable, but local and not tied to a persisted selected Scenario |
| Compare | `/analyses/:id/compare` | saved Scenario API and comparison utilities | KEEP | Scenario identity/provenance already scoped |
| Decision | `DecisionEndpointPage` / `DecisionEndpoint` | analysis metadata only | REWORK/BLOCKED | Insufficient persisted evidence for the requested final layer |
| Reports | `/analyses/:id/reports` and backend reports | datasets, scenarios, report generator | MOVE/REWORK | Route stays; sidebar order changes; recommendation source conflicts with target |
| Advanced Calculator | `/analysis` / `AnalysisPage` | model analysis API | MOVE | Keep as an independent Tool |
| Datasets | `/datasets` / `DatasetsPage` | global dataset CRUD and legacy compatibility | KEEP | Not proven redundant or dead |
| Sidebar navigation | `Sidebar` | router, auth, active URL | REWORK | Must become canonical numeric-ID workflow |
| Horizontal setup progress | `AnalysisWorkspace.analysis-progress` | setup/current routes and translations | REWORK | Keep its setup-progress purpose but separate it from major navigation |
| Horizontal major navigation | `AnalysisWorkspace.analysis-tabs` | route links only | REMOVE | Confirmed duplicate control; pages/routes remain |
| Scenario persistence | scenarios API/model | immutable verified snapshots | KEEP/PROTECT | Existing lineage and validation are security/correctness boundaries |
| Report generation | reports API and `report_export.py` | dataset/scenario results | KEEP/REWORK | Preserve exports; source recommendation from Decision only after evidence design |
| Frontend API clients | analysis/dataset/optimization/simulation/scenario/report clients | frozen backend contracts | KEEP | No dead client proven |
| Backend endpoints | existing analysis, dataset, optimize, simulation, scenario, report routes | auth, DB, engines | KEEP/PROTECT | No endpoint removal justified |

No component or route is approved for deletion except the confirmed duplicate
horizontal major-stage navigation control. Even that removal must retain every
route and page component.

## Dependency trace

### Analysis lineage currently implemented

1. `NewAnalysisPage` → `POST /analyses` → `analysis_projects`.
2. `AnalysisSetupPage` → `PATCH /analyses/:id` and
   `POST /analyses/:id/datasets` → queue setup plus processed Dataset.
3. `AnalysisCurrentPage` → `GET /analyses/:id/current` → latest valid Dataset,
   centralized model analysis, baseline rows, KPIs, and explanations.
4. `OptimizePage` → `GET /datasets/:id` → `POST /optimize/batch` → candidate
   rows → `POST /scenarios` with immutable calculation snapshot.
5. `SimulationPage` → Dataset, not saved Scenario → independent DES/trace/MC
   calls or a local optimizer run followed by validation.
6. `ComparisonPage` → saved analysis-scoped Scenarios.
7. `DecisionEndpointPage` → analysis metadata only.
8. `ReportsPage` → dataset/scenario report endpoints; backend derives its own
   recommendation list from report input rows.

### Protected services inspected

- Central model dispatch: `backend/queueing_engine/services/model_selection.py`.
- Optimizer: existing frontend `/optimize/batch` client and backend optimization
  path; no proposed equation or constraint change.
- DES and trace: `backend/queueing_engine/simulation/simulation.py`.
- Monte Carlo and validation: the same simulation module and existing API
  wrappers; no proposed sampling, failure, or CI change.
- Scenario verification: `backend/api/scenarios.py` recalculates and verifies
  saved calculation snapshots and makes result/settings content immutable.
- Reports: `backend/api/reports.py` and `backend/reports/report_export.py`.

## Standard DES versus Live DES equivalence matrix

| Property | Standard DES | Live DES / playback | Equivalent? |
|---|---|---|---|
| Frontend entry | DES tab in `SimulationPage` | Live tab plus `LiveSimulationPlayback` | No |
| User inputs | dataset, hours, overload threshold, seed | dataset, trace hours, event cap, seed | No |
| Scenario source | analysis-scoped Dataset | analysis-scoped Dataset | Yes, but neither uses a saved Scenario |
| Frontend API | `simulateDes` | `simulateDesTrace` | No |
| Backend endpoint | `POST /simulation/des` | `POST /simulation/des/trace` | No |
| Backend service | `simulate_segments` | `trace_simulate_segments` | No |
| Simulation function | `simulate_segment` using `_arrival_process` and `_customer_process` | separate `_trace_arrival_process` and `_trace_customer_process` | No |
| Randomization | `random.Random(seed + segment)` | `random.Random(seed + segment)` | Partially |
| Arrival/service sampling | exponential via shared helper | exponential via shared helper | Yes |
| Staffing input | segment `c`, pooled `simpy.Resource` | segment `c`, pooled `simpy.Resource` | Yes |
| Queue structure | shared FIFO for supported M/M/1 and M/M/c | shared FIFO for supported M/M/1 and M/M/c | Yes |
| Abandonment/patience | unsupported by simulation coverage | unsupported; response says false | Yes |
| Finite capacity | unsupported by simulation coverage | unsupported by simulation coverage | Yes |
| Duration | default 24 hours, API maximum 168 | default 1 hour, API maximum 4 | No |
| Warm-up | adaptive post-warm-up measurement, default fraction 0.2 | no warm-up | No |
| Event generation | aggregate process without emitted entity events | separate event-generating process | No |
| Aggregate outputs | rho, Lq, Wq, served, queue/status and metadata | segment descriptors and final queue depth | No |
| Event stream | none | arrival, service_start, service_end | No |
| Persistence | component state only | component state only | Yes |
| Consumption | KPI cards, aggregate animation, charts, CSV | customer/server/queue playback | No |

## DES conclusion

**DES EQUIVALENCE NOT PROVEN**

The two paths share distributions, seed convention, supported-model coverage,
and pooled FIFO semantics, but they execute separate SimPy processes with
different controls, horizons, warm-up behavior, and outputs. Live playback is
therefore not presently a presentation of the Standard DES execution's events.
Deleting or merging either interface is prohibited by the supplied stop rule.

## Decision and Reports evidence gap

Decision can safely access analysis metadata, Current data through an existing
endpoint, and saved optimizer Scenarios through an existing endpoint. It cannot
retrieve persisted DES, Monte Carlo, validation, or comparison-selection
evidence because those records/endpoints do not exist. Reports independently
derive recommendation text and cannot consume Decision as a source of truth.

A fully compliant Decision → Reports chain therefore requires an explicit design
choice outside this presentation-only restructure:

1. Add durable, analysis/scenario-scoped validation and Decision evidence with
   additive API/schema changes; or
2. Limit Decision to Current plus saved optimizer evidence and explicitly show
   simulation/comparison as insufficient evidence after reload. Reports would
   remain unable to document those ephemeral results.

## Stop conditions reached

The master prompt requires work to stop when DES equivalence cannot be
established or Decision cannot safely access sufficient evidence. Both
conditions are present. No frontend application code, backend code, analytical
logic, API contract, or database schema was changed during this audit.

## Safest next decision

Choose one explicitly scoped continuation:

- **Navigation-only partial restructure:** implement the canonical sidebar,
  remove only the duplicate major-stage links, keep both DES experiences, and
  make Decision disclose missing simulation evidence. Final status would remain
  partial.
- **Full workflow integration design:** separately authorize a protected design
  for one instrumented DES execution that can return aggregate results plus its
  own event trace, and additive persistence/API support for validation and
  Decision evidence consumed by Reports. Queueing formulas, optimizer logic,
  Monte Carlo definitions, and existing response fields would remain unchanged,
  but this is more than a presentation-only restructure and requires a new spec,
  migration plan, and regression baseline.
