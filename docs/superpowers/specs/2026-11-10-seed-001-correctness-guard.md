# SEED-001: selected-load correctness guard

Date: 2026-11-10. **Owner-approved objective and outcome; independent written-plan/derivation and bounded Phase 1 reference reviews PASS; Phase 2A/final verification pending.** The owner requested fixing SEED-001 and selected: implement the correctness guard first, accept insufficient results, and retain useful precision as a separate open item. This authorizes the necessary selected-only statistical/evidence change, not a commit, push, release, deployment, larger replication budget, RNG change or unrelated repair.

## 1. Baseline, evidence and completion boundary

- Implementation checkout: `output/seed-001-repair-20261110/worktree`, branch `codex/seed-001-repair-20261110`, clean starting HEAD `d87cb514e3a41af2aa7a82c6c00446e3aa4e2745`, tree `9f472b16a63aaff91221de3d80fdf84f16960a0c` (parent-verified remote main; local identity independently inspected by Chrome).
- Root checkout and `output/cobalt-brass-ui-20261109/worktree` contain unrelated work and are not writable targets. Root `AGENTS.md` and `docs/agents/` Vongola V2 instructions supplied by the owner govern this task even if the candidate's older adapter differs.
- VERIFIED source: `backend/api/workflow.py` retains the DES load means at 3081-3112, uses them as MC inputs at 3257-3296, and validates conditional MC at 3381-3451. The raw Wilson interval at `backend/queueing_engine/simulation/simulation.py:1546` does not assess uncertainty in the estimated input mean.
- Inspected prior execution logs, not new tests in this specification: the unchanged five-seed regression returned conditional, conditional, revise, revise, revise; 90 selected validation/Decision/report/load controls passed at the earlier release snapshot. These are not passing results for this unimplemented guard.
- Reuse the qualified revision-2 derivation and independent numeric/calibration records under `output/selected-load-revision-2-2026-10-19/` in the root checkout, with their original hashes and corrections. The Student-t candidate remains rejected. The later 5,120-run study failed its registered precision/usefulness target; it does not authorize increasing the production bound.
- The requested outcome is a truthful conservative assessment. It does not promise informative conclusions at 20 replications, identical decisions for every possible seed, true real-world input parameters, or operational safety. Useful precision and a production latency SLA remain OPEN/UNKNOWN. A passing bounded regression or all-insufficient output alone does not close that broader item.

## 2. Estimand and fixed statistical contract

For each required active pair `j=(time, queue_id)` in the frozen saved schedule, let `X_j` be its routed-arrival count in one complete selected-plan DES replication and `h_j>0` its actual duration in hours. The load estimand is `E[X_j]/h_j`. The assessed failure probability is `p(E[X_j]/h_j)`, conditional on frozen dataset/plan/setup/multiplier, empirical service mean, and the existing independent-uniform perturbation assumptions. It is not `E[p(X_j/h_j)]`, a whole-day failure event, or uncertainty about estimated real-world input parameters.

Use **`selected-load-truncated-hoeffding-v1`**, the previously researched fixed-input truncation/Poisson-envelope/Hoeffding method. Do not silently substitute the rejected t method, KL, bootstrap, a normal approximation, empirical-Bernstein bound or an adaptive sampler.

- Confidence: 95% simultaneous coverage over all `m` unique required active lane-period pairs in this one selected job. Allocate `alpha=.05` over the entire family, including pairs that later abstain. Do not shrink `m` to evaluable/passing pairs. The claim is conditional on ideal independent marginal replication streams and the audited potential-arrival domination; distinct deterministic seeds are not a proof of independence. Within-vector or cross-coordinate independence is not required by the union bound. No across-jobs/repeated-selection guarantee is made.
- Request contract stays `load_replications=1..20`, default 20. Inferential support is `n=2..20`; `n=1` still runs normally but receives insufficient assessment. No additional DES or MC runs, changed seeds, reseeding or optional stopping.
- V1 reproducible seed support: nonnegative integer DES base seed. `None` and negative bases preserve their existing raw run behavior and receive insufficient assessment with `unsupported_seed_domain`. `random.Random(-1)` and `random.Random(1)` have equal states in the inspected interpreter; signed seed uniqueness cannot justify independent replications. Do not change the RNG to work around this boundary.
- Require unique required identities, complete nonnegative integer counts (booleans rejected), matching positive finite durations and supported/conserved replication evidence. Never replace a missing count with zero, drop an unsuccessful run, condition on passing runs, or infer certainty from observed zero variance. A failed replication-wide conservation check invalidates the whole inferential family; a missing/invalid coordinate invalidates that coordinate without reducing `m` or `n`.
- Numerical envelope domain: finite `Lambda_j` in `[0,1000]`. Outside the independently checked domain, abstain in this assessment without rejecting otherwise valid business inputs. Known model envelope zero plus all observed counts zero yields exact zero bounds; nonzero counts under a zero envelope are inconsistent. The n/seed/identity gates still apply.

### Envelope and bound

Establish `X_j <= N_j`, with potential-arrival envelope `N_j~Poisson(Lambda_j)`, from the actual unchanged kernel, not an assumed Poisson law for routed lanes. `Lambda_j=R_j*h_j` uses frozen scaled rates and the actual supported execution mode:

- Period-independent: `R_j` sums all available lane input rates (`active + inactive`), matching `evaluate_candidate_with_des`; horizon is the actual DES period duration.
- Representative-day and per-date continuous: `R_j` sums the active input rates for that actual window, matching `run_routing_day_des`; use its actual duration and dated identity. Preserve pause/late-start/label attribution and date seed stride. Do not substitute active-only rates into the static mode or a 24-hour horizon into continuous windows.
- Unknown/malformed mapping, inconsistent duration, identity duplication or unverified domination receives insufficient assessment; no fallback to another mode.

For `n>=2`, `m>=1`, let `a=sqrt(log(2*m/.05)/(2*n))`. Fix integer `B=1` if `a>=1`, otherwise `B=max(1, Poisson.isf(a,Lambda_j))`, before inspecting counts. This retained rule minimizes the one-sided slack objective `a*B+delta(B)`; do not claim it globally minimizes full interval width.

Use `Y=min(X_j,B)`, `delta(B)=Lambda_j*P(N_j>=B)-B*P(N_j>=B+1)`, and count bounds `[max(0, mean(Y)-B*a), min(Lambda_j, mean(Y)+B*a+delta(B))]`, enlarged outward for numerical error. Divide by `h_j` for customers/hour. Preserve the original direct routed mean and first replay trace exactly; truncation applies only to the auxiliary inferential statistic. Retain the researched tail guard `64*float_epsilon*max(1,Lambda_j,B)` and conservative outward radius/endpoint guards; independently verify the actual implementation rather than asserting universal floating-point certification. Nonfinite or contradictory arithmetic abstains.

### Conditional stress propagation and verdict

Use the actual saved/resolved MC threshold and cap, actual empirical `mu>0`, one active server, and metadata declaring independent uniform arrival factors `[.8,1.2]` and service factors `[.9,1.1]`. Require supported raw MC configuration/evidence; other distributions/fractions are outside v1. Do not use the default target when the request explicitly recorded a different threshold.

For `rho=lambda/mu`, compute the exact area for `P(rho*A/S > threshold)` under these fixed uniform factors. Use exact `0` when `rho<=.75*threshold` and exact `1` when `rho>=1.375*threshold`; integrate only the stable interior with conservative outward endpoint rounding. The old prototype's difference-of-squares expression returns 0 for `(rho,threshold)=(1e16,1)` although the event is certain. It must not be copied unguarded. Independent Fraction/rational-area references, threshold boundary tests, and quadrature must check the new helper before integration.

The function is monotone in load, so propagate the mean-rate endpoints to probability endpoints `[L,U]`. Compare **unrounded** values with the saved cap: `U<=cap` gives supported pass; `L>cap` gives supported fail; overlap, invalid or unsupported evidence gives insufficient. Display rounding never determines the verdict.

After existing required-identity, conservation, supported-model, exact-count and raw-MC adequacy gates, selected validation uses the new supported assessment, not the raw conditional MC point PASS/FAIL. Preserve raw diagnostics separately. Across required checks use supported FAIL > insufficient > supported PASS; an empty required family is insufficient, never a vacuous pass. Existing Decision taxonomy remains: fail -> revise; insufficient -> insufficient_evidence; all pass with conserved DES -> conditional. ADOPT remains unavailable for Separate plans.

## 3. Additive evidence and compatibility

No new endpoint, request field, database migration or global engine-version bump. Persist `selected_load_method` in both params and result of selected DES, MC, validation and Decision jobs. Its value is the canonical v1 identifier above; consumers must verify compatibility in both places.

DES adds `load_uncertainty` with `estimand`, `confidence_level`, `family_size`, `replications`, `assumptions` and `results`. Use the fixed estimand code `conditional_stress_at_expected_routed_load`; assumptions identify frozen inputs, ideal independent marginal replications and potential-arrival Poisson domination. Each required result row contains:

`time`, `queue_id`, `duration_hours`, `envelope_mean`, `cutoff`, `sum_truncated`, `mean_rate_lower`, `mean_rate_upper`, `status` (`bounded` or `insufficient`) and `reason_codes`.

Use null for unavailable numeric fields, not zero. Store sufficient summaries, not all replication traces/count vectors. Collect these from the existing loop; leave original trace, `arrivals_mean`, `lambda_routed_mean`, seed schedule and existing load metadata unchanged. A pure settings cache may be bounded to 1,024 frozen `(Lambda,n,m)` entries; it must not cache measurements, selections or jobs.

MC preserves its complete existing raw result rows/status/Wilson fields and adds a separate `load_uncertainty` assessment with the same family identity. Rows carry the source mean-rate endpoints and append `mu`, `failure_threshold`, `failure_rate_cap`, the supported perturbation configuration, `failure_probability_lower`, `failure_probability_upper`, `status` (`pass`, `fail`, `insufficient`) and `reason_codes`. Copy inputs; do not mutate persisted DES JSON.

Selected validation queue rows retain existing raw fields and add `raw_mc_verdict` plus `load_assessment` (the corresponding assessed MC row). Existing `validation_verdict`, period statuses and overall verdict now describe the approved guard. Persist the top-level method identifier and a family summary. Selected Decision retains its existing evidence links and adds the same method identifier plus confidence/family/pass/fail/insufficient counts. Never copy a raw point PASS/FAIL into the supported assessment.

Machine reasons are limited to: `insufficient_replications`, `invalid_family`, `missing_replication_evidence`, `inconsistent_replication_evidence`, `failed_conservation`, `invalid_count`, `invalid_duration`, `unsupported_envelope_domain`, `unsupported_seed_domain`, `inconsistent_zero_envelope`, `unsupported_mc_configuration`, `raw_mc_inadequate`, `numeric_failure`, `threshold_overlap`. Do not show these opaque identifiers as invented explanatory prose in the primary UI.

Extend `EvidencePolicy` with an optional selected-load method family; production workflow policy enables it, unrelated classifier callers can leave it unset. Method requirements, ordinary dependency references and DFS traversal must share the same selected-producer identity predicate (`selected_load_record` in the inspected implementation). Engine-only or provenance-only recognition is insufficient when those markers are missing: retain the existing engine/`SELECTED` markers, and recognize the current producers by a recorded selected DES execution basis; a typed direct DES link for MC; typed direct DES+MC links for validation; and typed direct validation+DES+MC links for Decision. This recognizes producer structure, not numerical metrics or scenario ID alone. Check params/result method requirements for all four, including required ordinary references and upstream DFS under the same supplied policy.

If producer markers/structure are completely erased, only a verified selected Separate consumer context may establish that these four job kinds require the guard. The optional per-call `selected_load_context` flag defaults OFF; `_current_evidence` and `require_dependencies_current` enable it only after their existing selected scenario/dataset/Separate-context resolution. Do not globally enable it, infer it from a metric/scenario ID, or weaken owner/scenario/generation checks. Shared/Current behavior and callers with a None/no-selected-method policy remain unchanged. Scenario binding remains in existing job params JSON and resolved owner/analysis/scenario checks; no `Job.scenario_id` database column is introduced. Missing method means missing provenance; do not fabricate an old version from absence. A recognized obsolete version requires recalculation; an unknown version is unsupported. Marker erasure cannot turn an unusable selected chain into current evidence.

Require compatible current evidence in MC, selected validation, Decision, workflow-slot/currentness readers and both new selected full-report paths. Keep all current owner/setup/dataset/scenario/generation/link checks and existing refusal response shapes. Legacy records and already generated export files remain intact/viewable as historical data; they cannot establish new-method current evidence. Rerun the selected DES -> MC -> validation -> Decision chain to obtain current v1 evidence; do not force unrelated optimization/Current/shared reruns or mutate records automatically.

Preserve `_save_job` whole-result cap and existing refusal contract. Additional metadata can cause an oversized result to be refused; no cap increase is authorized. Measure complete serialized jobs, not just minimal summaries. No claimed universal largest-input runtime or invented SLA.

## 4. Minimal consumer and wording change

No UI redesign, charts, palette change, replay styling, new navigation or new interval dashboard. The separate Cobalt/Brass worktree is untouched. Existing raw variation tables/body/details remain explicitly raw diagnostics. Existing selected validation/Decision status labels are reused. The existing period column labelled MC must use `raw_mc_verdict`, not the newly changed `validation_verdict`.

For v1 evidence, stop rendering the unconditional old `Not checked` label. Keep that original label/body for legacy evidence where it remains accurate. Existing body/details describing the raw variation test can remain verbatim when clearly associated with raw MC. Show the generic missing-DES/MC hint only for truly missing raw evidence, not a completed but inconclusive assessment.

The owner approved the following exact shared EN/TL text with the reply **"Use this exact wording"**, supplied verbatim through the parent. Key: `decision.plain.selected_load_assessment_notice`. Placement: the selected-scope notice in ChecksView, DecisionEndpoint and ReportsPage, and the matching English selected report notice. Apply it exactly; do not invent another translation, shorten it or add a production placeholder. Retain existing scope details and provenance warnings wherever accurate.

English:

> Validation checks uncertainty in the average customer load estimated by simulation. Unsupported or inconclusive checks remain Insufficient evidence. This does not establish seed stability or future operational safety.

Filipino:

> Sinusuri sa validation kung gaano katiyak ang average na dami ng customer mula sa simulation. Kapag hindi suportado ang pagsusuri o hindi sapat ang ebidensya para magsabing pasado o bagsak, kulang pa ang ebidensya. Hindi nito pinatutunayang pare-pareho ang resulta sa lahat ng seed o ligtas ang aktuwal na operasyon sa hinaharap.

Selected report models and PDF/Excel detail/provenance data carry the method, family confidence, rate/probability endpoints, statuses and reasons separately from raw MC. Reuse existing details/provenance structures and approved labels; no report redesign or plan-only export dependency change. Any unavoidable extra human-readable label is a concrete wording gap to return, not permission to invent copy.

## 5. Acceptance and stop gates

1. Independently review the amended selected-only contract and source-mode envelope mapping. Reuse prior qualified proof/calibration; rerun only invalidated or missing checks, with original failures/corrections preserved. Test success alone is not mathematical proof.
2. Pure helper passes independent Decimal tail/bound checks, rational stress-area references, exact zero/one and extreme-rho tests, monotonicity, cap equality just above/below the boundary, n1/n2/n20, known zero versus observed zero, sparse/rare counts, dependent coordinates, arbitrary IDs, unequal durations, invalid/missing data and seed-domain abstention. No fabricated samples or favorable seed selection.
3. Capture preserves complete original raw DES means and first trace, original raw MC payload/CI/status, RNG calls and all Current/shared behavior. Verify static, representative-day, per-date, pauses, closed lanes and date attribution with existing reference cases. Include guard FAIL/raw PASS, guard PASS/raw FAIL, overlap/raw FAIL, invalid or unsupported DES/MC, inadequate raw evidence and empty-family insufficiency; do not blindly raise fixture adequacy flags to obtain passing results.
4. Ownership/generation/dependency/method refusal and legacy preservation are executed through API/Decision/workflow/report consumers using isolated fixtures. Inspect actual PDF/Excel data and display paths; report native/browser checks not executed as NOT TESTED.
5. Run the unchanged original five-seed test with `--runxfail`. Preserve fixture and all assertions byte-for-byte. If every assertion genuinely passes and Kyoya independently verifies, remove only the obsolete strict-xfail marker/reason, then run it normally. Preserve old failure receipts and state that only the bounded criterion passed; useful precision remains OPEN. If any assertion fails, retain the xfail/failure and report it; no forced agreement or intentionally failing replacement test.
6. Add disjoint holdouts (bases 42, 100042, 200042, 300042; 20 unchanged replications each) for the retained fixture. Record all supported/insufficient outcomes and any conflicting definitive classification without selecting favorable batches. These are empirical holdouts, not universal seed-stability proof. Reuse registered known-mean calibration cases; investigate any coverage/numerical failure before interpretation.
7. Measure normal-fixture complete workflow timing, pure assessment overhead and full job JSON near the existing cap. Record environment, input size and refusals; no fabricated production SLA or larger-count implementation.
8. Run required backend/frontend/Ruff/mypy gates on the final authorized diff using the existing project venv. System Python's observed NumPy 2.4.6 is outside the repository constraint and is not the test runtime. Record actual venv package versions. Tests/logs/evidence belong outside the candidate in `output/seed-001-repair-20261110/evidence/`, not output scripts inside the candidate that contaminate root lint scans.
9. Kyoya independently reviews actual source, derivations, scoped diff and outputs. Failed required gates, unsupported assumptions, unexplained differences or unintended protected changes stop the affected work. No self-approval, no auto commit/push/deploy.

Status: specification prepared by Chrome from inspected source/research. Kyoya's earlier written-plan/derivation PASS covered spec SHA256 `775265fc20e02d783ddf5274022af4796d4cc8cbfa5f180012491c0925e6b030` and plan SHA256 `e0de03e1ba384a3848ee47a747d1b2da450a2208f3c11f0e2aa4f7a379002f2a`. The actual bounded Phase 1 closure receipt is `../evidence/kyoya-independent-references/phase1-closure-review.json`: PASS for 360 exact-neighbor enclosures, 9 rational references and 12 Decimal-tail references, with helper SHA256 `7d7bdcff2aa4afc2bac8f6a03ec57c45136bcd66756488aab56dd759063db190` and test SHA256 `066b5c5813338697a5d18d2496f33de771f7098bec09c4b41d8fb1d0f58856ce`. Chrome read the receipt, matched these source hashes and observed the Phase 1 log's 125 passed result; this is not a new Chrome test execution or universal floating-point certification.

Phase 2A source/currentness refinements above follow the inspected implementation and retained compatibility negatives: initial lost-engine/triple-erasure failures led to shared producer recognition; complete erasure required default-OFF trusted per-call context. The combined erasure-control log records 10 passed/41 deselected. The parent reports 392 focused tests across 11 files with the original five-seed case deselected, plus scoped Ruff/mypy passes. Phase 2A independent source review and the native original `--runxfail` result were still pending at this update; no result is invented. Report/frontend integration and final application/browser/production verification are not complete. Useful precision remains OPEN.

## Completion record (2026-11-11)

This record supersedes the "pending" status lines above.

- The owner said "Yes, take it over" (2026-11-11). Claude Code finished the work from the Codex WIP (ddb1560a3) on top of main 6d46a01.
- Hayato:
  - fixed the report defects R-1 to R-5;
  - added the report and frontend display of the guard result;
  - added the approved notice in en and tl (`decision.plain.selected_load_assessment_notice`).
- Owner decisions on the open questions:
  - OQ-1: the selected Decision's "insufficient" branch sets `missing_evidence=[]`. Its recommendation is: "The completed checks could not show whether this plan passes in every period. Do not adopt it on this run alone; review the plan and its estimated loads first."
  - OQ-2: a guard FAIL whose raw MC passed shows the time and lane only.
  - OQ-3: the existing stale text is kept.
  - OQ-4: `selected_scope_details` is kept.
- Gates:
  - full backend: 3634 passed, 125 skipped;
  - ruff and mypy: clean;
  - vitest: 1118 passed;
  - typecheck, lint and build: pass;
  - PostgreSQL 18 focused run: 473 passed (REPORTED).
- Independent review: Kyoya PASS (HIGH), with his own math references. 19,678 exact stress cases and 659 Poisson/Hoeffding cases found no false PASS.
- Open follow-ups (P3):
  - K1: list the inconclusive periods on the Reports page;
  - K2: shorten the per-pair detail in the PDF;
  - K3: should rows with unsupported simulation count as missing evidence?
- Useful precision stays OPEN, as decided.
