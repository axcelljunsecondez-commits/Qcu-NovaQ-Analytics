# Shared DES automatic replications — implementation report

Date: 2026-10-29. Status: COMPLETE for the requested frontend change and bounded numerical
preservation checks. Whole-folder Python lint/type checks retain the artifact failures below.
Branch: codex/shared-queue-workflow-20261029.

## Owner request and actual change

The owner called repetition management unnecessary and asked for the separate-queue DES
interaction pattern while preserving mathematics. The shared full-day run now has one
Run full operation action without an editable Repeated days field. Its existing DES
replications happen automatically; the shared-queue engine is retained.

- frontend/src/components/queueSimulation/ContinuousRun.tsx removes the count field/local
  state, submits the checked automatic count, and retains seed access under Advanced.
- frontend/src/lib/continuous.ts chooses a count using the server's default, maximum count
  and expected-customer budget. It does not calculate arrival rates, alter uploaded data,
  sample demand, select models or run the engine in the browser.
- The two existing helper/page test files exercise this behavior and the budget boundaries.
- Existing stored-count disclosures, actual-day replay selection, key metrics, range notes,
  Decision evidence/cache refresh and earlier plan-selection/recovery fixes remain.

When the default fits, the requested parameters are unchanged. Where fewer complete repeats
fit, the UI chooses that count automatically instead of asking the user to lower it. A day
that cannot fit once is refused with existing localized limit wording and no request.
No partial day, altered demand, relaxed cap or statistical precision guarantee is introduced.

This does not implement the separate proposed CSV auto-Setup redesign. That remains pending.

## Verified preservation and numerical evidence

- All 94 protected backend/locale file hashes match the saved pre-change baseline. No API,
  database schema, queueing formula, seed scheme, engine, model selection, confidence interval
  definition, locale catalog or approved wording record changed.
- The earlier PlanChanges.tsx and ResultsPage.test.tsx repair hashes match exactly. Earlier
  capacity-recovery/hour-status changes remain in ContinuousRun.tsx and its page regressions.
- The supplied Avg_total_data_of_14_days.csv is unchanged: SHA-256
  236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e.
  It contains 13 hourly aggregate periods, 05:00–18:00. Rates use NovaQ's per-hour convention;
  the raw observations and method behind the filename's 14-day average remain UNKNOWN.
- The new real-browser Current run uses that CSV, five replications, seed 42 and DRAIN.
  Its five replication rows, period-utilization results and full summary match the earlier
  saved Current diagnostic run exactly as parsed JSON values. This is actual before/after
  numerical evidence for this scenario, not a proof of every queueing model.
- Diagnostic Setup choices (shared line, unlimited capacity, abandonment not modeled,
  staffing varies, no breaks, DRAIN) were explicit test settings, not inferred from the CSV
  as real operating facts. Operational data/databases were not accessed.

Evidence: output/shared-des-automatic-20261029/preservation.json and
numerical-comparison.json. Baseline job 2 is in the earlier owned diagnostic SQLite file;
the browser-created job 1 is in a new owned browser-fixture database, recorded by exact path
in the comparison artifact. Both comparisons used read-only SQLite connections.

## Tests and checks executed

- New-expectation baseline: 16 selected tests failed before the implementation, including
  the still-visible input, missing helper and the new budget behavior (67 deselected).
- PASS: 85 focused tests across helper, QueueSimulationPage and approved wording policy.
- PASS: full frontend suite, 766 tests / 90 files, 563.72 seconds, exit 0.
- PASS: frontend npm run typecheck, npm run lint and npm run build. Build retained the
  existing large-chunk warning; jsdom emitted its existing canvas-not-implemented messages.
- PASS: 55 fixed numerical DES references and replication regressions, 11.02 seconds.
  Starlette/AnyIO emitted an existing deprecation warning.
- PASS: Ruff on all tracked Python files. PASS: mypy backend tests, 230 source files;
  informational unchecked-untyped-function notes remain.
- Whole-folder ruff check . FAILED with 1,304 issues, all located under the pre-existing
  untracked output/ diagnostic artifact tree. Whole-folder mypy . FAILED because an older
  output/.../original/backend snapshot duplicates the real backend package. These commands
  are not reported as passing. No diagnostic scripts, root lint configuration or unrelated
  files were rewritten to conceal those failures.
- PASS: full backend suite, exit 0: 3,288 passed, 125 skipped, 1 xfailed, 9 subtests passed,
  2,191.46 seconds. The existing expected failure is
  test_selected_mc_load.py::test_novamart_failing_lanes_are_stable_across_base_seeds;
  this separate selected-load finding is not repaired or declared resolved by this UI work.
  Skipped cases were not executed; PostgreSQL/deployment parity is not inferred from them.
- PASS: synthetic real-API automatic-budget acceptance. A clearly labeled one-hour
  fixture with lambda=600/hour, mu=400/hour/counter and c=3 accepted four complete
  replications (200, all replications conserved). Five were refused with 422
  limit_exceeded, and exactly one Job remained. This fixture is not owner observations.
  Evidence: budget-acceptance.json and its request log.

## Browser observations

Built frontend served through an isolated loopback app using a fresh disposable SQLite
database. This was not the existing localhost Docker stack or production deployment.

- Advanced contains the existing Random seed field and no Repeated days input.
- One click produced one successful full-day run request, then Done and all four Current
  key metrics. Saved evidence records the actual internal count and seed.
- Replay loaded the stored run, and switching to its second execution regenerated playback.
  Native time input sought to 13:30: 73 arrived = 69 served + 4 serving + 0 waiting + 0 unserved.
  Direct programmatic filling alone did not update the controlled time value; a native
  ArrowUp input resolved that tool-event limitation. No application replay repair was made.
- At 375px in dark and light themes, document width was 360px and the count input was absent.
  Temporary viewport override was reset. Browser warning/error entries returned none.
- Screenshots were viewed inline through CUA. The used API returned no saved image path;
  no separate screenshot artifact is claimed. The owned browser tab and diagnostic
  server were closed/stopped after verification; the separate earlier prototype was retained.

## Limits and remaining scope

The change removes repetition management from the form; recorded replication counts and
replay execution identities remain visible for traceability. Statistical sampling still
exists internally, as in separate DES. Budget-limited requests can have fewer repetitions;
the saved count and existing range/undefined-statistic behavior remain authoritative.

No staging, commit, push, Docker activation, production change or operational database write.
Actual deployment parity and the owner's authenticated operating workflow remain NOT TESTED.
The full backend/frontend test gates finished; the documented whole-folder lint/type failures
are explained by existing diagnostic artifacts and were not bypassed or relabeled as passing.
No unresolved new defect was found in the scoped implementation. There was no implementation
scope deviation. The existing selected-load finding and the separate CSV auto-Setup proposal
retain their earlier status. The local test server was stopped and its browser tab closed.

Final machine-readable results: output/shared-des-automatic-20261029/verification-summary.json.
The same directory holds all gate logs, the preserved baseline, browser/budget checks and
exact numerical comparison. Specification and plan use the matching shared-des-automatic-
replications filename under docs/superpowers/specs and docs/superpowers/plans.
