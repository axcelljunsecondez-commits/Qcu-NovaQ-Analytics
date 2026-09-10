# NovaQ system remediation audit

## Executive assessment

This system-first remediation implements the approved constraint controls, truthful DES utilization/duration, explicit Monte Carlo metadata, consistent configuration, and additive result provenance. It does not modify observational workbooks or establish empirical/external validity. Multi-model analytical behavior is retained; general-service models remain approximations and DES/MC coverage remains limited to M/M/1 and M/M/c.

The engine now searches the complete allowed integer staffing range and returns an explicit unavailable result if no candidate passes every enabled constraint. Calculated recommendations are internally explainable under the supplied model and cost assumptions. They are not executable shift schedules, observed savings, or a guarantee that simulated utilization will remain below a planning target.

## Issue matrix

| # | Issue | Initial status and evidence | Action and implementation areas | Verification | Final classification |
|---|---|---|---|---|---|
| 1 | Hard constraints | Partial: target/max/capacity enforced, minimum and wait limit absent | Add minimum, optional wait limit in minutes, joint feasibility, status and rejection reasons; optimizer/API/UI | New boundary, zero-wait, capacity and snapshot regressions | FIXED |
| 2 | Universal 70% | Partial: configurable optimizer, comparison substituted default | Preserve (0,1] API range and default 70%; comparison receives previous dataset options and editable controls | 40/70/90% cases, frontend target forwarding | FIXED |
| 3 | DES utilization | Confirmed: unstable-case 0.9999 cap and one-hour duration override | Remove both; expose requested/effective/measurement hours and warm-up | Continuously busy server returns 1; requested two hours retained | FIXED |
| 4 | MC definition | Partial: utilization criterion and Wilson CI existed, metadata incomplete | Expose strict exceedance criterion, threshold, trials/failures, method, confidence, allowance and noise assumptions | Zero failures, threshold equality, seeded repeatability and metadata tests | FIXED |
| 5 | MC defaults | Confirmed: API 10%, frontend 5% allowance | Standardize 5%; generate browser defaults from API configuration | Default parity and MC API tests | FIXED |
| 6 | Model consistency | Shared selector already present; explanations missing | Add selection reason, supplied CV and model assumptions without changing dispatch | M/G/c and M/G/c/K CV=1 reductions, Erlang-A and finite-capacity benchmarks | FIXED for system scope; dataset CV deferred |
| 7 | Dataset reconciliation | Data-specific discrepancies and reconstructions previously identified | No data changes or automatic corrections in this remediation | Not part of system acceptance | REQUIRES DATA — deferred by owner |
| 8 | Metric provenance | Partial: snapshots and coverage labeled | Analytical/API/export labels, DES provenance, analytical-perturbation MC labels; no new observed-data claims | Metadata, report and snapshot checks | FIXED for existing system outputs |
| 9 | Cross-engine handoff | Partial: coverage restrictions existed; duration substituted | Preserve inputs/options; expose DES time basis and MC method; avoid model-label merge collisions | Validation handoff regression, model coverage suite | FIXED for supported paths |
| 10 | Costs | Confirmed: engine fallback 1 versus API 87; abandonment defaults differed | Server default 87; default abandonment costs disabled consistently; explicit values preserved; effective assumptions exported | Cost consistency and per-row cost tests | FIXED |
| 11 | Abandonment | Needed explicit interpretation | Label configured percentages as sensitivity assumptions and theta as patience rate per hour | UI language, report text, explicit cost tests | FIXED for system labeling |
| 12 | Inter-rater reliability | No functionality located in current backend/frontend search | No records or reliability results manufactured | Source search | PAPER/METHODOLOGY ISSUE — deferred |
| 13 | Citation traceability | No reference-generating functionality located in current backend/frontend search | No citations invented or paper edited | Source search | PAPER/METHODOLOGY ISSUE — deferred |
| 14 | Explainability | Partial: add/remove/maintain only | Add lowest-cost feasible explanation, constraints, model reason and costs | API metadata and export checks | FIXED |
| 15 | Stability | Already guarded for infinite-capacity models | Preserve model-specific stability; retain unavailable waits when unstable | Existing model suite plus independent finite-capacity/Erlang-A checks | ALREADY CORRECT; retained |
| 16 | External validation | Not established | Disclose analytical/simulated provenance and verification limits | No empirical claim or fabricated measurement | REQUIRES DATA — deferred |
| 17 | Multi-model architecture | Already present | Preserve six-model API/selector; add independent reductions and birth-death checks | Analytical benchmarks and model regressions | ALREADY CORRECT; strengthened verification |
| 18 | Regression gates | Existing suites present | Add system, UI and snapshot/export regressions; update obsolete expectations with reasons below | Backend 375, frontend 114, PostgreSQL 81 passed; static gates passed | FIXED; frontend runtime allowance disclosed |
| 19 | Avoid speculative features | No new speculative feature required | No billing, tenancy, adaptive selection or re-optimization added | Change review | ALREADY CORRECT |
| 20 | Audit report | Earlier report did not cover this checklist | This issue matrix, math ledger, inventory, test evidence and file inventory | Documentation review | FIXED |

## Mathematical and behavioral changes

1. **Joint feasibility:** previously search began at one server and had no hard wait ceiling. Now candidates satisfy `min_servers <= c <= max_servers`, applicable `c <= K`, valid model stability, `rho <= target + 1e-12`, and, when enabled, `60 * Wq <= max_wait_minutes + 1e-12`. Cost minimization occurs only inside this feasible set; equal costs prefer fewer servers. Empty sets return `NO_FEASIBLE_CONFIGURATION`, null recommendations, and the union of rejected constraint names. This union identifies rejection categories across the search, not a claim that each category alone rejects every candidate.
2. **DES busy fraction:** retain the monitor's post-warm-up area calculation `integral(busy_servers dt)/(c * measurement_hours)` and remove the 0.9999 display manipulation. A fully occupied server legitimately produces 1. Requested duration now determines the horizon regardless of analytical stability. Warm-up remains the existing adaptive rule: `min(max(duration*fraction, 30/lambda), duration/2)` for positive arrival rate. Zero-load/no-initial-queue returns zero utilization without warm-up. No simulated outcome is forced to equal an analytical target.
3. **MC:** probability remains `count(rho_trial > threshold)/trials`; the change is default allowance 0.10 to 0.05 in backend paths and explicit metadata. Trial arrivals and service rates are multiplied by independent uniform factors within ±20% and ±10%. These are sensitivity assumptions, not empirically estimated distributions or repeated DES. Wilson 95% calculation is unchanged. Conditional finite Wq/Lq sample summaries retain their existing meaning; unstable trials still count toward utilization failure.
4. **Cost configuration:** direct engine fallback changes from 1 to 87 per server-hour to agree with API/costing. Default abandonment cost/rate now both zero; users can explicitly supply sensitivity values. Existing total-cost algebra remains server + waiting + assumed abandonment. The legacy 5000 unstable-cost sentinel remains, while incomparable/unstable baselines remain excluded from savings claims.
5. **Units and provenance:** rates are per hour; internal Wq is hours; maximum wait input and report wait displays are minutes; service variance is hours squared. Erlang-A's Wq remains workload per served throughput and is disclosed as such. DES served count retains its historical meaning of service starts after warm-up; result metadata discloses the sample mean and no-sample Little's Law fallback. Analytical estimates are not labeled observed.
6. **Version compatibility:** new UI snapshots use `novaq-2026-09-system-v2`. The API still accepts exact verified v1 calculations, allowing absence of additive metadata while checking the original result fields. Stored v1 snapshots are not rewritten or stamped v2. New options participate in recalculation and stale-save detection.

## Configuration inventory

| Setting | Default / limits | Authority and interpretation |
|---|---|---|
| Planning utilization | 0.70; finite (0,1] | Engine config and validated optimizer API; default planning target, not optimum guaranteed by theory |
| Minimum / maximum servers | 1 / 24; integers 1–256, minimum ≤ maximum | Optimizer request schema and engine; capacity can further restrict upper bound |
| Maximum wait | Disabled (`null`); finite minutes ≥0 | Optional API/engine hard constraint |
| Server cost | 87/hour | Config; configured cost assumption, explicit segment rate overrides global rate |
| Regular / overtime rates | 87 / 109 | Config; existing blended rate `(regular_hours*87 + overtime_hours*109)/total_hours` |
| Waiting cost | 100/customer-hour | Config; assumption, not measured loss |
| Abandonment cost / percentage | 0 / 0; percentage 0–1 | Config and API; explicit user sensitivity inputs preserved |
| Unstable sentinel | 5000 | Config; compatibility sentinel, not empirical loss or finite queue estimate |
| Cost interval | 1 hour | Existing cost helper default; operating-day summaries assume one-hour rows |
| MC trials | 2000; 1–100000 | Config/API; generated browser defaults |
| MC utilization threshold | 0.75; (0,1] | Config/API; strict exceedance defines a failed trial |
| MC permitted failure probability | 0.05; (0,1] | Config/API; user-configurable allowance, not observed rate |
| MC arrival / service noise | ±0.20 / ±0.10 | Config; independent uniform perturbations, disclosed fixed sensitivity assumptions |
| MC confidence | 95%; z≈1.959964 | Statistics proportions module; Wilson interval retained |
| MC precision | High half-width ≤0.03; adequate ≤0.05 | Statistics proportions module; adequacy is not proof the SLA passes |
| Conditional mean adequacy | CI half-width / mean <0.10 | Simulation module; existing finite-sample rule |
| DES duration | 24 hours; API >0 to168 | Simulation/API; no hidden unstable-case replacement |
| DES warm-up | Default 0.20, direct-call range clamped 0–0.5, adaptive 30 arrivals capped at half horizon | Simulation module; reported in output |
| DES queue threshold | 20; API integer ≥1 | Simulation/API; presentation overload classification |
| DES display thresholds | 0.60 / 0.80 / 0.90 / 1.00 | Simulation module; category boundaries, not optimizer constraints |
| Seed / carryover | DES/MC 42; validation seed may be null; carryover enabled | API/simulation; carryover transfers queue depth, not a full dynamic staffing simulation |
| Model selection | theta >0, then K+variance, K, variance, c=1, otherwise M/M/c | Central selector; no dataset CV hard-coded |
| Request size | At most1000 segments; maximum256 optimizer candidates | API; not a total CPU/concurrency quota |

Browser configuration JSON is generated by `python -m scripts.export_planning_defaults`; API/default parity is tested. The simulation precision categories, display thresholds and warm-up rules remain separately documented algorithm settings, not hidden MC failure criteria.

## Verification and remaining limitations

Baseline: backend **360 passed**, one Starlette/AnyIO deprecation warning. Frontend **112 passed** with one worker. An initial parallel frontend run failed worker startup and timing-sensitive tests. A later run concurrent with image building also hit timing failures; assertions were not relaxed to disguise them.

New regressions cover joint constraints, target boundaries, full DES utilization/duration, MC definitions/intervals, cross-engine metadata, cost inputs, model reductions, versioned snapshot tampering, and Excel export of effective constraints. Frontend cases cover forwarding the new options and a nondefault comparison target. Old expectations of server cost 1 and implicit abandonment charges were updated because those inconsistent defaults were deliberately corrected. Dataset export tests now assert additive analytical provenance/model columns while retaining existing metric-column order.

Final backend run: **375 passed**, one existing AnyIO deprecation warning, 308.91 seconds. Isolated PostgreSQL integration: **81 passed**, two dependency deprecation warnings, 252.21 seconds. HTTP smoke passed nginx SPA/assets, readiness, sessions/CSRF, upload limits, snapshots and PDF/Excel. Ruff and `git diff --check` passed. Frontend type checking, lint and production build passed; the build retains a large chart-bundle warning.

Frontend timing evidence: a run concurrent with other checks had a worker-start failure and login timeout. An isolated run completed all 17 files with **113 passed, 1 failed**: the multi-step settings test exceeded Vitest's default five-second test limit. Final command `npm test -- --maxWorkers=1 --testTimeout=15000` passed **114 tests in 17 files**, 153.64 seconds, without changing assertions. The default five-second gate is therefore timing-sensitive on this host. Final mypy passed all 73 checked source files; its only notes concern existing untyped function bodies.

No current empirical validation, public deployment verification, load-capacity claim, or remote CI success is inferred from these tests. Data reconstruction/cutoff decisions, inter-rater methodology, academic citations, and external validation remain deferred.

Final integration image rebuild also passed (including the frontend production build). The refreshed stack was healthy and the HTTP smoke passed again against final source. Temporary project `novaq-system-ci` was removed with its test storage and network after verification. No existing application stack was deployed or modified. Final frontend type checking and lint passed again. Remaining warnings are dependency deprecations, the large chart bundle, and the documented host-sensitive frontend test runtime.

## Files changed in this remediation

- `backend/queueing_engine/config.py`: aligned defaults and MC configuration.
- `backend/queueing_engine/services/optimization.py`: joint constraints, feasibility and explanatory metadata.
- `backend/queueing_engine/services/model_selection.py`: selection reasons and supplied variability/assumption metadata.
- `backend/queueing_engine/simulation/simulation.py`: remove duration/utilization manipulation, disclose MC/DES metadata, preserve validation joins.
- `backend/queueing_engine/statistics/proportions.py`: correct outdated allowance comment; Wilson math unchanged.
- `backend/api/optimization.py`, `simulation.py`, `analysis.py`: additive inputs/results, defaults and provenance.
- `backend/api/scenarios.py`: v2 and backward-compatible v1 verification.
- `backend/api/reports.py`, `backend/reports/report_export.py`: provenance, effective constraints/costs and safe structured metadata export.
- `frontend/src/api/optimization.ts`, `types.ts`, `planning-defaults.json`, `simulation-defaults.json`: options, metadata and generated defaults.
- `frontend/src/pages/OptimizePage.tsx`, `SimulationPage.tsx`, `AnalysisPage.tsx`: controls, option handoff and explanations.
- Both locale JSON files: symmetric English/Tagalog labels.
- `tests/test_system_remediation.py`: new behavioral, mathematical and compatibility regressions.
- `tests/test_costing.py`, `test_optimization.py`, `test_reports_api.py`: explicit corrected default/export expectations.
- `frontend/src/pages/OptimizePage.test.tsx`, `SimulationPage.test.tsx`: new option forwarding regressions.
- `scripts/export_planning_defaults.py`: repeatable browser default generation.
- This report and the dated system-remediation spec/plan: approved design, implementation sequence and evidence.

Pre-existing working-tree edits were preserved. No commits, deployments, credentials, observational spreadsheets, or live application databases were changed by this remediation.
