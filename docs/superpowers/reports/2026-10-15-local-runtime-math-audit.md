# Local Docker runtime and mathematical audit

Subsequent owner-authorized work: the original findings/failure evidence below are retained. The owner later approved the three-item repairs with source mapping first. See [source register](2026-10-15-formula-source-register.md) and [current repair verification](2026-10-15-approved-math-repairs-verification.md) for the current implementation/gate/activation state; the STOP status below describes this earlier audit only.

Date: 2026-10-15. Status: Docker activation COMPLETE; bounded audit COMPLETE WITH FINDINGS. Mathematical correctness of the whole system is not certified. Affected repairs are STOPPED pending separate authorization; no mathematical or application changes were made during this audit.

Owner instruction: "approve after the that we check all if theres error or math correct". This authorizes the previously itemized web-container recreation followed by an audit. It does not authorize protected mathematical changes, production access, pushes, commits or Docker cleanup.

## Execution plan and limits

1. Verify the approved old container identity and built image, recreate only web, then inspect actual Compose state, migration log and both local health endpoints.
2. Exercise the rebuilt localhost:80 navigation, saved Results/Reports/Simulation context, Current wording and Quick Calculator; capture browser errors and a screenshot.
3. Independently calculate reference cases for M/M/1, M/M/c, finite M/M/c/K, M/G/1, exponential-service reductions of M/G/c and M/G/c/K, Erlang-A birth/death probabilities, priority conservation, confidence intervals and cost units. Reference cases are explicitly synthetic mathematical inputs, not observations.
4. Audit model dispatch, customer-event ingestion, optimizer feasibility/cost ranking, continuous simulation conservation/closing/cost, Decision freshness and exported formula regression tests. Run bounded relevant tests sequentially; do not repeat the completed full backend suite without new cause.
5. Record every failure and its affected path. Stop affected implementation for a mathematical defect; continue independent audit work. No formulas or gates will be changed to obtain a pass. Passing selected cases never proves all parameter values, all distributions or production correctness.

Initial primary references inspected: [MIT M/G/1 derivation](https://web.mit.edu/urban_or_book/www/book/chapter4/4.7.html), [MIT priority queues](https://web.mit.edu/urban_or_book/www/book/chapter4/4.9.1.html), [MIT multiserver priorities](https://web.mit.edu/urban_or_book/www/book/chapter4/4.9.3.html), [NIST Wilson interval](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). A requested MIT PDF could not be opened by the browsing tool and is not treated as inspected proof. Source equations plus independently derived balance/flow/unit checks will be identified with each result.

## Authorized Docker refresh (VERIFIED)

- Preflight: Windows free memory 856.1 MiB, Docker allocation 4,022,951,936 bytes, VM available memory 2,928,284 kB.
- Rechecked the exact approved old ID `4390889e95cc22cf343a66d54515a8d5fa96580646ce3fb94a9e737abf4361bb`, writable layer 81,920 bytes, and final built image `sha256:987e2c88e52e426ed995bb967ada948156d14d166c65bd0399bea50f0229d698` before mutation.
- `docker compose up -d --no-deps web` exited 0 and printed Recreated / Started for web only. No build was needed in this refresh. No image, volume or cache cleanup was performed.
- New web ID `767af13c18dd228a9e0c4ce551298041d0813619bc8c395dd732e08e2c22aa18`, image matches the approved build, health healthy.
- Compose printed API Up 8 hours; db Up 8 hours (healthy); migrate and bootstrap-admin Exited (0) 8 hours ago; new web Up 18 seconds (healthy). Ports remained loopback 8000, 5432 and 80.
- Migration log includes `Running upgrade 0006 -> 0007` (historical startup log; no new migration was performed by the web-only recreation).
- Actual localhost health: `/healthz` -> `ok`, HTTP 200; `/api/health` -> `{"status":"ok"}`, HTTP 200.
- Raw evidence in artifact folder: `reconstruction-docker-refresh.log`, `reconstruction-docker-after-refresh.log`.

## Verified findings

### M1 — Active Quick Calculator mislabels the Erlang-A workload ratio

**VERIFIED, current signed-in UI.** `queue_models.py:527-546,592` explicitly defines Erlang-A Wq as `Lq / served_throughput`, with `metric_basis=workload_per_served_throughput`, rather than a served-customer mean wait. `frontend/src/lib/quickCalculator.ts:100` multiplies Wq by 60 and `QuickCalculatorPage.tsx:195` inserts it into the ordinary average-wait sentence. EN labels at `translation.json:871,877,887` call it Average wait in line and the time before service starts. The live tooltip repeats this meaning without disclosing the returned basis.

Actual localhost example, synthetic mathematical inputs (not customer observations): lambda 20/hour, mu 6/hour/counter, 2 counters, patience 60 minutes (theta 1/hour). UI showed **40.8599 minutes**, 99.1475% effective utilization and 40.5115% abandonment. The backend numeric ratio matches an independent birth/death calculation; the problem is its presented meaning.

Independent population calculation for the same case:

| Quantity | Minutes | Basis |
|---|---:|---|
| Existing backend workload per customer served | 40.8598511976 | Lq / served throughput |
| Mean queue residence over all arrivals, including abandonment | 24.3069074835 | Lq / offered arrival rate |
| Mean wait conditional on eventually starting service | 28.8677877940 | Tagged-customer calculation below |

The tagged reference conditions an arrival on stationary state n. For n<c service starts immediately. Otherwise its waiting position is k=n-c+1. While it waits, progress rate is c*mu+(k-1)*theta and its own abandonment rate is theta. Its service probability telescopes to c*mu/(c*mu+k*theta); conditional served wait is the sum, j=1..k, of 1/(c*mu+j*theta). Weight these by stationary arrival-state probabilities, with served probability in the denominator for the conditional mean. A separate 80-digit, 1000-state calculation produced the values above and a Little-law residual of 2e-80 hours for the all-arrival mean. These are independently derived mathematical reference values, not executed DES or observed waits.

Evidence: `novaq-erlang-a-caption-audit.png`, `novaq-erlang-a-tagged-reference.json`, `reconstruction-docker-browser-audit.json`. Current Results/report wording for Erlang-A was source-inspected only and was not exercised with a new live Erlang-A analysis; that extension is NOT TESTED. No existing record was repurposed to manufacture such evidence.

### M2 — Exported priority helper fails a conservation reference

**VERIFIED, legacy helper, no current application caller found.** `backend/queueing_engine/models/queue_models.py:415,486-493` uses the already-delayed M/M/c wait as the numerator for both priority classes. Repository-wide search found its definition, package export and two tests only; no backend API or frontend call. This is a statement about the inspected repository, not proof about unknown external library consumers.

Synthetic exact counterexample: two nonpreemptive classes, identical exponential service, lambda1=lambda2=2/hour, mu=6/hour, c=1. Residual workload W0=(lambda1+lambda2)*E[S^2]/2=1/9 hour. With rho1=1/3 and total rho=2/3:

| Quantity | Independent reference | Actual helper |
|---|---:|---:|
| Priority-class mean queue wait | 1/6 hour = 10 min | 0.5 hour = 30 min |
| Regular-class mean queue wait | 1/2 hour = 30 min | 1.5 hours = 90 min |
| Arrival-weighted aggregate wait | 1/3 hour = 20 min | approximately 1 hour = 60 min |

The aggregate number-in-system process with identical exponential service is unchanged by a work-conserving nonpreemptive priority ordering. Independent M/M/c normalization therefore also provides a conservation oracle. The helper failed that check for c=1,2,4. The existing priority tests check ordering and overload refusal only (`tests/test_queue_models.py:185-194`); their pass does not validate the numbers.

### M3 — Exported legacy costing helpers mix hourly flows and interval totals

**VERIFIED, legacy helper, no current application caller found.** `backend/queueing_engine/services/costing.py:82-93,142-153` applies `hours_per_interval` to server cost but omits it for waiting and abandonment flows. The parameter docstring describes interval duration. The vectorized function repeats the same expressions; the numerical counterexamples below executed `compute_segment_costs` directly. `compute_cost_summary` calls the vectorized function internally. Repository-wide backend search found no application caller outside this module.

Synthetic costing inputs: c=2, lambda=4 customers/hour, Wq=0.25 hours/customer; server rate=10 currency/server-hour; wait rate=100 currency/customer-hour; abandonment fraction=0.1; abandonment rate=5 currency/customer. This is a unit reference, not a real operational cost.

Expected interval cost is `H * (2*10 + 4*0.25*100 + 4*0.1*5) = H * 122`. Actual output:

| Interval H | Correct interval total | Actual total | Actual waiting / abandonment |
|---|---:|---:|---:|
| 1 hour | 122 | 122 | 100 / 2 |
| 0.5 hour | 61 | 112 | 100 / 2, expected 50 / 1 |
| 2 hours | 244 | 142 | 100 / 2, expected 200 / 4 |

This finding is not attributed to the newer continuous-day costing service. Independently hand-scheduled DRAIN and HARD_CUTOFF cases in `shared_day_cost.py` passed totals 255 and 247.5. The shared legacy optimizer's disclosed per-hour cost convention is a different path: `plan_report.py:151` explicitly describes hourly costs added over periods. This audit does not reinterpret that index as measured day expenditure or change its objective.

## Independent checks executed

Script `novaq_independent_math_audit.py` exited **1**, preserving failures: **131 cases, 125 PASS, 6 FAIL**. Six failures concern two helpers (one exact priority case, three priority conservation cases, two interval-duration cases). They are not erased by passing regression tests. Expected values were calculated without calling NovaQ's corresponding implementation:

| Group | Cases | Actual result / limit |
|---|---:|---|
| M/M/c | 30 | PASS, c=1/2/3/10/200/800, load 0/0.1/0.5/0.95/0.999; 90-digit stationary normalization instead of production Erlang-B recursion |
| M/M/1 | 5 | PASS against the same independent one-server balance model |
| M/M/c/K | 27 | PASS against exact rational local balance, including K=c, zero demand and offered load above capacity |
| M/G/1 | 16 | PASS against rational Pollaczek-Khinchine calculations, including zero/deterministic/exponential/nonzero variance |
| M/G/c / M/G/c/K reductions | 10 | PASS exponential and c=1 limits; this is not validation of general approximation error |
| Erlang-A | 5 | PASS numeric distribution/flow/basis checks against fixed 1000-state 90-digit chains; terminal mass below 1e-60 in each reference |
| Boundary refusals | 8 | PASS: saturation (including 3.15 vs 3*1.05), invalid capacity/rates/variance and nonfinite input |
| Dispatch | 8 | PASS: supported models, separate priority, theta precedence and unsupported separate c>1 |
| Wilson intervals | 8 | PASS against independently solved score-test quadratic, including 0/n and n/n |
| Replication mean interval | 1 | PASS Student-t df=2 hand-inverted quantile; missing value excluded and counted |
| Shared optimizer | 4 | PASS independently exhaustive 1..12 counter search, utilization/wait limits and no feasible solution; one-hour basis |
| Continuous deterministic DES / cost | 2 | PASS FIFO backlog with DRAIN and HARD_CUTOFF: counts, waiting and independent currency totals |
| Priority | 4 | FAIL; M2 above |
| Legacy interval costing | 3 | 1 PASS / 2 FAIL; M3 above |

All cases explicitly use synthetic mathematical inputs. No real samples, observations or user records were fabricated or altered. Constants for deterministic backlog cases are identified in `tests/test_shared_day_cost.py`; the independent interpretation is hand scheduling and quantity-times-rate costing.

### Live Docker API

`novaq_live_api_math_audit.py` used only `http://localhost/api`, with the documented demo login. Login HTTP 200; audit session was logged out HTTP 200. Tokens remained in memory and were not printed or written to disk. No analysis, dataset, scenario, simulation or Decision mutation was made by this script.

**14/14 comparisons passed, exit 0**: one independently referenced live case for each of six `/analysis` models; five validation/unknown-model refusals; saturation with absent Wq; and two fixture-derived current rows from synthetic analysis 5. This checks the running backend through nginx, not just local imports.

Analysis 5 fixture is the unchanged three-event constant from `tests/test_workflow_api.py:526`, SHA256 `f2284cd6335ff72abec501afbbaaad8de583f10612dfad3ea4973471c2032866`. One representative period is 07:00–08:00 on the one observed synthetic date, 2026-09-08. Cashier-east has 2 arrivals/hour, mean service 11/120 hour and population variance 1/14400 hours squared; express has 1 arrival/hour, mean service 1/15 hour, variance 0. Both recorded waits are 1 minute per customer. Current API modeled Wq matched **0.6224489796** and **0.1428571429** minutes respectively. These modeled steady-state estimates remain separate from the synthetic recorded wait and stochastic plan simulations.

### Focused repository regression

Ran 23 identified files covering queue models/numerical range, model selection, cost, proportions, optimizer/API, continuous DES and recorded service, day costs, setup derivation, ingestion, formula/report generation, Decision evidence, separate continuous-day feasibility/replication and queue lifecycle/break events. Exact file list and output are in `novaq-math-regression*.log`.

- First sandboxed attempt: **160 passed, 1 setup error, 1 warning, 31.98 s**. Pytest could not create its temporary fixture directory after ten attempts; this was not an assertion or numerical failure. Stopped that attempt at its configured `-x` gate.
- Identical command outside that Windows sandbox: **514 passed, 1 deprecation warning, 110.56 s, exit 0**. No test/database setting was weakened; no external test DB was supplied. These tests used temporary SQLite, not a full Postgres regression. The separately recorded earlier full suite was 3,185 passed / 123 skipped / 1 xfailed; it was not rerun during this audit.
- The independent counterexamples still fail. Existing tests passing does not certify the defective helpers.

### Actual workbook export (read-only)

Downloaded only synthetic analysis 5's `full.xlsx` and preview through the local endpoint: HTTP 200, 12,766 bytes for XLSX and 5,537 bytes for preview. Workbook sheets were Overview, Your data, Plan, Formula check, Plan search, Simulation, Checks, Decision, Assumptions and Provenance.

Used the bundled Python runtime and openpyxl for read-only extraction, plus the repository's bounded formula-string evaluator. Expected queue values came from the independent fixture derivation, not pasted NovaQ outputs. **20 formula cells evaluated; both Formula check rows D5:N6 matched independent values; zero stored error cells found.** Formula differences were approximately -3.33e-16 and 5.55e-17 minutes. SHA256 stayed `c5490cece458f01346365ddcf367557c204180783065615e43408245fa6dfc64` before/after. No workbook rewrite or settings change was made. `fullCalcOnLoad=True` is configuration, not evidence of Excel execution. **Microsoft Excel recalculation and PDF visual/content review are NOT TESTED.**

## Docker browser checks after refresh

At actual `http://localhost` on the approved image: all five sidebar destinations opened; all five collapsed links had names with label spans hidden by CSS. The area picker appeared; selected QA5 Results retained saved plan 3; Reports retained Conditional; Simulation/Replay/Checks retained the same selected plan and stored evidence. Switching to QA4 cleared the old plan and displayed Current / Not run; the period-run hint matched its button. Quick Calculator Basic 40/15/3 returned the independently referenced **9.5701 minutes**. The Erlang-A label problem M1 was independently reproduced, including its tooltip.

The fresh browser tab returned an empty captured error/warning list for the inspected flow. A bounded Docker log read (last 250 lines, since 30 minutes) found zero matches for Traceback, Internal Server Error, HTTP 500 or ERROR. This is not a claim that every historical log or path is error-free. The earlier preview tab had closed between turns; a new local tab was created without touching the existing GitHub tab.

Final `docker compose ps -a` printed API Up 8 hours; db Up 8 hours (healthy); migrate/bootstrap Exited (0) 8 hours ago; web Up 18 minutes (healthy). Final image and both health outputs still matched the authorized refresh above. Home was not visited or edited. Only web was recreated; no other Docker resource was removed.

## Aggregate limitation clarification

The earlier QA4 aggregate optimizer refusal is preserved. Its first observed error is unmatched IDs (`08:00-09:00` versus Setup's generated `segment_1`). Source inspection now also confirms that fixing IDs alone would not provide supported routing DES: `analysis_ingestion.py:30,158-159` identifies aggregate statistics, and `separate_optimization.py:506-516` explicitly refuses active lanes without empirical `service_samples_hours`. A variance does not uniquely supply a service-time distribution. Do not fabricate samples, rename labels silently, or promise an optimization result after only an ID edit. The supported event-upload path was exercised separately in QA5.

## Boundaries, unknowns and next action

- Backend/API clients/tests/Compose/Home/auth/global styles have no diff from HEAD for this phase's protected paths (final command exit 0). No application or test source was edited during the runtime/math audit; added this record and the proposed remediation plan, and refreshed the existing reconstruction records. Prior authorized frontend changes remain uncommitted.
- General M/G/c and M/G/c/K approximation accuracy across arbitrary service distributions is NOT TESTED by exact-limit checks. Real input distribution fit, operational-data accuracy, all possible parameter combinations, every independent queueing model variant, production behavior, native Excel and full-page accessibility remain UNKNOWN or NOT TESTED as applicable.
- Stochastic regression/conservation tests are not proof of every random trajectory. A successful API call is not a mathematical certificate. Native-language quality was not reviewed.
- Next proposed bounded work: [verified issue remediation plan](../plans/2026-10-15-verified-math-issues-remediation-plan.md). Mathematical repairs require explicit owner authorization under AGENTS.md. Preserve the existing Wq API contract and disclose its basis in the interface; do not silently replace it with a different population's mean.

Final repository checks: `git diff --check` exit 0; `git diff --cached --quiet` exit 0 (nothing staged); protected source diff exit 0. Only the report/plan and current reconstruction records were edited during this audit. Local use: open `http://localhost`, sign in with the Compose demo `admin@example.com` / `admin123`. From the worktree, `docker compose down` stops/removes the stack containers while retaining the named database volume (do not add `-v`); `docker compose up -d` starts it again without a rebuild. These stop/restart commands were provided as instructions, not executed during the audit; the only performed removal was the approved web recreation.

Artifact folder: `C:/Users/Administrator/.codex/visualizations/2026/10/14/01a13b2b-3883-7bb2-ad6c-05667dc49ecf/`. Evidence: `novaq_independent_math_audit.{py,json,log}`, `novaq-live-api-math-audit.{json,log}`, `novaq_live_api_math_audit.py`, `novaq-erlang-a-tagged-reference.json`, `novaq-readonly-workbook-audit.{json,log}`, `novaq_readonly_workbook_audit.py`, `novaq-math-regression*.log`, `reconstruction-docker-browser-audit.json`, `reconstruction-docker-final.png`, `novaq-erlang-a-caption-audit.png`. Support scripts are audit artifacts, not product features or committed tests.
