# NovaQ result integrity — implementation and assessment

Date: 2026-09-06. This implements the later attached execution request, which superseded the initial assessment-only instruction. No commit, public deployment, live database migration, or real credential change was performed.

## Assessment and recommendation

The confirmed defects affected recommendations, savings, simulation assurance, and saved-result provenance. Their root causes have been addressed while retaining the engine/API/database/React architecture and existing response envelopes. The evidence supports continuing with controlled testing; it does **not** establish production readiness or real-world staffing accuracy.

The local Docker build, Postgres regressions and nginx smoke checks now pass (see follow-up below). The subsequent isolated HTTPS/recovery rehearsal also passed (details below). Next, verify any eventual public deployment and operational backups, and calibrate model estimates against observed arrivals/service times before using modeled savings to make staffing decisions. Keep shift scheduling, payroll savings, and modeled waiting/abandonment costs distinct.

## Confirmed issues, causes, and changes

| Area | Root cause | Implemented behavior |
|---|---|---|
| Staffing constraints | A heuristic searched over invalid candidates and a later adjustment could replace the chosen staffing. Utilization was not enforced as a final feasibility condition. | Exhaustive feasible integer search; final staffing obeys the utilization ceiling, server limit, and finite capacity. No feasible candidate produces an explicit unavailable recommendation. There is no minimum-utilization input in the existing contract; none was invented. |
| False savings | Missing optimized values were summed as zero, and unstable-baseline penalties could masquerade as comparable costs. | Savings require a nonempty, fully comparable set of matched rows with stable current/recommended results and finite costs. Incomplete results expose metadata and unavailable totals. React comparison/ROI views and exports use these semantics. Unknown utilization is unavailable. |
| Simulation coverage | Advanced parameters were lost while a generic exponential-service simulation was presented as validation. | Central model selection determines coverage. DES/Monte Carlo support M/M/1 and M/M/c only. K, theta and variance are preserved, unsupported models explicitly fail validation, and model/coverage/reason metadata reaches the UI. Duplicate labels are joined by internal row identity. |
| Erlang-A | A fixed waiting-state cutoff discarded most heavy-load probability mass. | Log-space birth/death recursion, adaptive tail mass/first-moment bounds of 1e-12, normalized probabilities, capacity and flow conservation checks, and explicit nonconvergence at 100000 states. W/Wq retain the legacy workload-per-served-throughput basis, now disclosed; they are not claimed as conditional or all-arrival waits. |
| Finite-capacity approximation | The M/G/c/K variance adjustment could exceed physical capacity (reproduced L≈118 for K=5). | Such approximation results explicitly fail rather than reporting stable impossible queues. This does not make the approximation exact. |
| Upload validation | Coercion erased malformed optional values and integer conversion truncated fractional values. | Row-specific validation before coercion; invalid supplied values, nonfinite values, fractional counts, negatives, and invalid K/c combinations are rejected. Empty optional cells remain absent. CSV/Excel parsing preserves literal malformed numeric strings. |
| Saved scenarios | Save used current controls while results could belong to an earlier calculation. What-if inputs were not fully recorded. | UI captures effective inputs, dataset identity, cost/options, factor, timestamp, and version; changed controls mark results stale and prevent saving. API recomputes snapshot results and verifies dataset/factor correspondence. Calculation edits return 409; renaming remains allowed. Legacy scenarios are explicitly unverified. |
| Authentication | Successful login mutation data overrode newer session query state. | Session query cache is authoritative. Login updates it; later session expiry/deactivation/role changes supersede it. Logout cancels queries and removes other cached data. Backend authorization remains enforced. |
| Production | Development defaults were being reused as deployment configuration. | Separate standalone production Compose, mandatory externally supplied credentials, private database/API, loopback web binding behind an external TLS proxy, Secure cookies, explicit HTTPS origins, JSON/comma CORS parsing, 5 MiB file cap and 6 MiB nginx multipart allowance. |
| Gates/report safety | Python 3.10 incompatibility, object-to-float typing, unsafe PDF markup and Excel formula interpretation. | timezone.utc compatibility; typed finite-number conversion; NumPy <2.3 for supported type syntax; explicit text escaping; Excel strings forced to text; CI 75% threshold and Postgres/nginx jobs. |

Other implemented improvements: wait display in minutes, one-hour/one-operating-day assumptions and modeled-cost disclosures, bounded server search/segment counts/duration, database `/ready`, operations/backup guidance, and symmetric English/Tagalog additions.

## Regression tests added or extended

- `tests/test_result_integrity.py`: target utilization, server bounds, finite capacity, unavailable savings, Erlang-A capacity/flow/nonconvergence, optional-field validation, explicit unsupported simulation, finite-capacity approximation failure, and malformed simulation staffing.
- `tests/test_scenario_integrity.py`: forged outputs, immutable inputs/results, rename compatibility, legacy provenance, dataset-bound what-if and per-row server cost, wrong factor, malformed timestamp.
- `tests/test_report_integrity.py`: unavailable utilization/totals, PDF markup isolation, Excel formula safety.
- `tests/test_configuration_integrity.py`: both CORS representations, malformed origins, production configuration invariants.
- `tests/test_readiness.py`: database reachable/unavailable behavior.
- `frontend/src/auth/AuthProvider.test.tsx`: expiry, deactivation, role changes and logout supersede login state.
- `frontend/src/pages/OptimizePage.test.tsx`: stale saving, what-if snapshot, and infeasible aggregate rendering; all pre-existing cases retained.
- Existing optimizer/scenario tests updated for explicit unavailable values, hard feasibility and immutable calculations. Analysis/login fixtures updated for minutes and authoritative server state.
- `tests/conftest.py`: opt-in Postgres fixture with per-test random schemas and a dedicated `_test` database guard. CI uses the existing auth/dataset/scenario/report tests against it.
- `scripts/stack_smoke.py`: disposable nginx SPA/assets and route fallback, readiness, session/CSRF, >1 MiB upload acceptance, application/proxy upload rejection, optimization, verified scenario save, immutability, PDF/Excel and logout.

## Verification actually performed

Commands below ran from the repository root unless a frontend working directory is stated. The virtual environment was used because the global Python installation lacked the required test/tool dependencies. Unique temporary directories avoid the inaccessible pre-existing pytest temp/cache folders.

```powershell
$integrityTemp = Join-Path (Get-Location) ('.venv/tests-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests/ -x --tb=short -p no:cacheprovider --basetemp=$integrityTemp
```

Final complete run of the command above after the last boundary fix: **360 passed, 1 dependency deprecation warning, 177.44 seconds**. An earlier complete run had 346 passing tests. Subsequent full coverage run after additional fixes:

```powershell
$integrityTemp = Join-Path (Get-Location) ('.venv/tests-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests/ -x --tb=short -p no:cacheprovider --basetemp=$integrityTemp --cov=backend --cov-report=term:skip-covered --cov-fail-under=75
```

**358 passed; backend coverage 92.76%; 75% gate passed.** Warnings: Starlette/AnyIO deprecation and SQLite resource warnings under coverage. These are disclosed, not test failures.

```powershell
.\.venv\Scripts\python.exe -m ruff check . --no-cache
.\.venv\Scripts\python.exe -m mypy . --cache-dir=.venv/mypy-integrity
```

Ruff passed. Mypy passed, 70 source files, with informational notes about untyped function bodies. Initial legitimate typing failures were fixed; they were not suppressed. NumPy 2.5.2 stubs could not parse under the declared older target, so the requirements upper bound and local environment were corrected to NumPy 2.2.6. Ruff/mypy and their dependencies were installed into the existing ignored virtual environment for verification.

In `frontend/`:

```text
npm test
npm run typecheck
npm run lint
npm run build
```

**112 tests passed across 17 files.** Typecheck, lint and build passed. Vite warns that the chart bundle is large (about 4.66 MB minified / 1.39 MB gzip). A first full frontend run exposed two stale test fixtures; they were corrected to assert the intended minutes/server-session behavior, and the complete rerun passed.

```text
docker compose -p novaq-ci -f docker-compose.integration.yml config --quiet
```

Initial configuration validation passed, but Docker was initially unavailable. After the user started Docker, the image build, Postgres regressions and live nginx smoke test all passed locally; exact evidence follows below. No remote CI success is claimed. Python 3.13.13 was used for the full Windows suite and Python 3.11.16 for Docker integration. Python 3.10/3.12 execution and the remote dependency audit remain unverified here.

Additional focused runs reproduced failures before fixes and then passed: initial engine/ingestion regressions, unsupported simulation, scenario forgery/immutability, report safety, authentication transitions, and stale UI saving. Locale verification confirmed all 206 keys match between en/tl and every pre-existing translation value remains unchanged.

## Remaining limitations and follow-up priorities

1. The disposable Postgres/nginx checks have now passed locally. Validate the actual public HTTPS path, Secure cookies, external secrets, firewall, backups and restores before deployment. Existing seeded credentials are create-only and require deliberate rotation.
2. Validate operational assumptions against observed data. Daily/cashier-hour summaries assume one-hour intervals making up one operating day. The snapshots reproduce this model, not an executable shift schedule or realized payroll benefit.
3. DES/Monte Carlo do not validate Erlang-A, finite capacity, or general service distributions. Erlang-A has a finite numerical state budget. M/G/c and M/G/c/K remain approximations. The legacy priority helper also needs independent numerical review before use; it is outside the six-model API/UI workflow.
4. Legacy imported scenarios remain accepted for compatibility and labeled unverified. They cannot acquire verified provenance merely by being renamed; calculation changes require a new scenario. Verification is tied to the recorded engine version, not a promise of bitwise reproduction across future dependency versions.
5. Endpoint count/trial/duration limits are not an aggregate CPU quota. Extreme rates or concurrent requests can still be expensive. Background workers, cancellation, rate limiting and load testing remain needed before an exposed multi-user rollout.
6. Large-list pagination, complete legacy-string translation, smaller chart bundles, distributed login throttling and deployed monitoring are deferred. Readiness and request logging provide hooks; they are not an installed monitoring service.
7. Unit/API tests and static gates are strong evidence for these regressions, but do not replace independent numerical benchmarks for every advanced approximation or observation of business outcomes.

## Working-tree safety

Before edits, the original 15 modified files were copied byte-for-byte with SHA-256 hashes, the HEAD hash and a binary working-tree patch into:

`C:/Users/ADMINI~1/AppData/Local/Temp/novaq-integrity-baseline-djm4rx1n`

No commit, reset, checkout, stash, user-file deletion, live database change, or secret-file modification was performed. Pre-existing untracked `.pytest_tmp/`, `pptx-output/`, and `reports/` were left alone. Report download names/extensions, staffing summaries/status columns, styles and their existing tests were preserved. Where these files were extended, their original content was compared with the saved baseline and the existing tests were retained.

| Pre-existing modified file | Preservation result |
|---|---|
| backend/api/reports.py | Original changes retained; extended for this request |
| backend/reports/report_export.py | Original changes retained; extended for this request |
| frontend/public/locales/en/translation.json | Original changes retained; extended for this request |
| frontend/public/locales/tl/translation.json | Original changes retained; extended for this request |
| frontend/src/api/reports.ts | Unchanged byte-for-byte from the starting copy |
| frontend/src/auth/AuthProvider.tsx | Original changes retained; extended for this request |
| frontend/src/pages/ComparisonPage.test.tsx | Unchanged byte-for-byte from the starting copy |
| frontend/src/pages/ComparisonPage.tsx | Original changes retained; extended for this request |
| frontend/src/pages/OptimizePage.test.tsx | Original changes retained; extended for this request |
| frontend/src/pages/OptimizePage.tsx | Original changes retained; extended for this request |
| frontend/src/pages/ReportsPage.test.tsx | Unchanged byte-for-byte from the starting copy |
| frontend/src/pages/ReportsPage.tsx | Unchanged byte-for-byte from the starting copy |
| frontend/src/styles/global.css | Unchanged byte-for-byte from the starting copy |
| tests/test_report_export.py | Unchanged byte-for-byte from the starting copy |
| tests/test_reports_api.py | Unchanged byte-for-byte from the starting copy |

## Files changed by this execution

This inventory excludes files whose only changes predated the request (listed above).

| File | Reason |
|---|---|
| [.github/workflows/ci.yml](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.github/workflows/ci.yml) | Runtime matrix, 75% gate, dependency installation, Postgres and disposable stack jobs. |
| [.gitignore](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.gitignore) | Ignore local deployment secret-file variants. |
| [README.md](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/README.md) | Link deployment/verification guidance. |
| [backend/api/account.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/account.py) | Python 3.10-compatible UTC handling. |
| [backend/api/auth.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/auth.py) | Python 3.10-compatible UTC handling. |
| [backend/api/main.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/main.py) | Database readiness endpoint. |
| [backend/api/optimization.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/optimization.py) | Finite inputs and request/search bounds; nullable output typing; allow zero per-row cost. |
| [backend/api/reports.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/reports.py) | Validate report row containers and disclose legacy provenance; preserve download changes. |
| [backend/api/scenarios.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/scenarios.py) | Verify reproducible snapshots and make calculation data immutable. |
| [backend/api/settings.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/settings.py) | CORS parsing and production settings validation. |
| [backend/api/simulation.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/api/simulation.py) | Finite request limits and JSON-safe optional validation output. |
| [backend/data/ingestion.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/data/ingestion.py) | Strict row-specific numeric/domain validation before conversion. |
| [backend/data/uploads.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/data/uploads.py) | Preserve invalid numeric strings during CSV/Excel parsing. |
| [backend/queueing_engine/models/queue_models.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/queueing_engine/models/queue_models.py) | Adaptive Erlang-A convergence and physical-capacity approximation guard. |
| [backend/queueing_engine/services/optimization.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/queueing_engine/services/optimization.py) | Exhaustive feasible search and honest comparable totals/recommendations. |
| [backend/queueing_engine/simulation/simulation.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/queueing_engine/simulation/simulation.py) | Explicit model coverage, preserve parameters, match by row and reject invalid staffing. |
| [backend/reports/report_export.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/backend/reports/report_export.py) | Safe nullable summaries, minute displays, markup/formula safety and assumptions. |
| [docker-compose.integration.yml](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docker-compose.integration.yml) | Disposable database/API/nginx test stack. |
| [docker-compose.production.yml](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docker-compose.production.yml) | Separate private-services production configuration requiring external secrets/TLS. |
| [docker-compose.yml](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docker-compose.yml) | Loopback development ports and configurable development cookie/CORS settings. |
| [docs/operations.md](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docs/operations.md) | Deployment, scientific limits, backup/restore and integration procedures. |
| [docs/superpowers/2026-09-06-result-integrity-report.md](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docs/superpowers/2026-09-06-result-integrity-report.md) | This evidence and handoff report. |
| [docs/superpowers/plans/2026-09-06-result-integrity-plan.md](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docs/superpowers/plans/2026-09-06-result-integrity-plan.md) | Implementation sequence and verification plan. |
| [docs/superpowers/specs/2026-09-06-result-integrity-design.md](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/docs/superpowers/specs/2026-09-06-result-integrity-design.md) | Explicit result, model coverage and snapshot semantics. |
| [frontend/public/locales/en/translation.json](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/public/locales/en/translation.json) | English integrity/assumption/coverage labels; existing values retained. |
| [frontend/public/locales/tl/translation.json](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/public/locales/tl/translation.json) | Matching Tagalog labels; existing values retained. |
| [frontend/src/api/types.ts](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/api/types.ts) | Nullable recommendations and additive model/coverage metadata. |
| [frontend/src/auth/AuthProvider.test.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/auth/AuthProvider.test.tsx) | Authentication-state transition regressions. |
| [frontend/src/auth/AuthProvider.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/auth/AuthProvider.tsx) | Authoritative session state and logout cache handling. |
| [frontend/src/components/charts/Charts.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/components/charts/Charts.tsx) | Handle nullable staffing types. |
| [frontend/src/lib/comparison.ts](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/lib/comparison.ts) | Shared complete/comparable totals helper. |
| [frontend/src/lib/radar.ts](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/lib/radar.ts) | Nullable staffing input type. |
| [frontend/src/pages/AnalysisPage.test.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/AnalysisPage.test.tsx) | Assert wait display in minutes. |
| [frontend/src/pages/AnalysisPage.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/AnalysisPage.tsx) | Minute display and Erlang-A metric-basis disclosure. |
| [frontend/src/pages/ComparisonPage.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/ComparisonPage.tsx) | Hide invalid financial aggregates/charts and disclose legacy provenance. |
| [frontend/src/pages/LoginPage.test.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/LoginPage.test.tsx) | Mock authenticated server session after successful login. |
| [frontend/src/pages/OptimizePage.test.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/OptimizePage.test.tsx) | Stale result, what-if snapshot and infeasible-total regressions. |
| [frontend/src/pages/OptimizePage.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/OptimizePage.tsx) | Capture calculation inputs, stale-save protection, honest totals and assumptions. |
| [frontend/src/pages/SimulationPage.tsx](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/frontend/src/pages/SimulationPage.tsx) | Forward model parameters and show unsupported validation coverage. |
| [nginx/nginx.conf](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/nginx/nginx.conf) | 6 MiB multipart request body allowance. |
| [pyproject.toml](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/pyproject.toml) | Consistent Python 3.10 lint/type targets. |
| [requirements.txt](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/requirements.txt) | Compatible NumPy typing/runtime constraint. |
| [scripts/stack_smoke.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/scripts/stack_smoke.py) | HTTP workflow smoke checks against the disposable nginx stack. |
| [tests/conftest.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/conftest.py) | Dedicated Postgres test database and isolated schemas; SQLite default retained. |
| [tests/helpers.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/helpers.py) | Python 3.10-compatible UTC fixture handling. |
| [tests/test_auth_api.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_auth_api.py) | Python 3.10-compatible UTC test handling. |
| [tests/test_configuration_integrity.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_configuration_integrity.py) | CORS/production configuration regressions. |
| [tests/test_optimization.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_optimization.py) | Correct expected constraint and unavailable-aggregate semantics. |
| [tests/test_readiness.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_readiness.py) | Healthy/unavailable database readiness tests. |
| [tests/test_report_integrity.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_report_integrity.py) | Unsafe markup/formula and invalid-total regressions. |
| [tests/test_result_integrity.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_result_integrity.py) | Optimizer, queue invariants, ingestion and simulation regressions. |
| [tests/test_scenario_integrity.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_scenario_integrity.py) | Snapshot forgery, immutability, provenance and dataset/factor tests. |
| [tests/test_scenarios_api.py](C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/tests/test_scenarios_api.py) | Retain rename compatibility while treating calculations as immutable. |

After the final simulation staffing-boundary fix, the focused command
`python -m pytest tests/test_result_integrity.py tests/test_simulation.py tests/test_simulation_api.py -x --tb=short -p no:cacheprovider --basetemp=<unique .venv directory>` passed **87 tests** using the same virtual environment. `git diff --check` and Ruff passed.

Final repeated mypy and frontend lint checks also passed after the last changes. The 92.76% coverage figure belongs to the preceding 358-test coverage run; the final 360-test run was not coverage-instrumented.

## Docker integration follow-up — 2026-09-06

After Docker became available, all previously blocked local integration checks passed. Docker access required execution outside the filesystem sandbox. The pre-existing `novaq` project was running three containers before and after these checks; it was not rebuilt, restarted or migrated. Only the separate `novaq-ci` project was created and removed. No application source changes were needed during this follow-up.

### Commands and evidence

```powershell
docker version
docker compose ls
docker compose -p novaq-ci -f docker-compose.integration.yml up -d --build --wait --wait-timeout 180
.\.venv\Scripts\python.exe -B scripts/stack_smoke.py
```

Both API and web images built successfully. Postgres and API health checks passed. The smoke script passed: nginx SPA and built JavaScript assets, client-side route fallback, readiness, session authentication and CSRF enforcement, 2 MiB upload acceptance, application 5 MiB and nginx 6 MiB rejection boundaries, constrained optimization, dataset-bound verified snapshot creation, immutable results, PDF/Excel downloads, and logout.

The exact Postgres test invocation used a read-only repository mount and an ephemeral runner:

```powershell
docker compose -p novaq-ci -f docker-compose.integration.yml run --rm --no-deps --entrypoint /bin/sh --volume "${PWD}:/workspace:ro" --workdir /workspace --env NOVAQ_TEST_DATABASE_URL=postgresql+psycopg://novaq_test:integration-only@db:5432/novaq_test --env PYTHONDONTWRITEBYTECODE=1 api -c "python -m pip install -q 'pytest~=9.0' 'httpx~=0.28' && python -m pytest tests/test_auth_api.py tests/test_datasets_api.py tests/test_scenarios_api.py tests/test_scenario_integrity.py tests/test_reports_api.py tests/test_readiness.py -x --tb=short -p no:cacheprovider --basetemp=/tmp/novaq-pg-tests"
```

**66 passed in 84.27 seconds** against PostgreSQL **16.14**, under Linux Python **3.11.16**. Each test used its own schema within the disposable `novaq_test` database. Two dependency deprecation warnings concerned Starlette/httpx and AnyIO; no test failed. These credentials are public, disposable test fixtures, not production secrets.

```powershell
docker compose -p novaq-ci -f docker-compose.integration.yml ps
docker compose -p novaq-ci -f docker-compose.integration.yml exec -T api python --version
docker compose -p novaq-ci -f docker-compose.integration.yml exec -T db psql -U novaq_test -d novaq_test -t -c "SELECT version();"
docker compose -p novaq-ci -f docker-compose.integration.yml exec -T web nginx -t
docker compose -p novaq-ci -f docker-compose.integration.yml down -v
docker compose ls
```

nginx configuration validation passed. The test API and database had no published host ports; only test web port `127.0.0.1:18080` was exposed. Cleanup removed only the test containers/network and their disposable database state. Final Compose inventory showed the original `novaq` project still **running(3)**.

These checks cover the local HTTP integration path. They do not establish a public TLS deployment, certificate configuration, production secret rotation, backup restoration, production load capacity, or real-world model accuracy. The next deployment gates are those infrastructure checks and real-data calibration.


## Isolated HTTPS and recovery follow-up — 2026-09-06

The owner confirmed no public HTTPS URL exists yet and authorized an isolated
rehearsal. This verification used synthetic infrastructure fixtures only. It did
not use or substitute for the designated observational workbook.

### Outcomes

- nginx terminated HTTPS at `https://localhost:18443` using a one-day local
  certificate. The client verified the hostname/certificate against an explicit
  trust file. Certificate verification was never disabled; no host CA was installed.
- API production settings required Secure cookies and the HTTPS origin. Full
  workflow passed, including Secure cookies, HTTP cookie exclusion on the same
  hostname, accepted/rejected CORS origins, CSRF, uploads, snapshots and reports.
- Custom-format `pg_dump` completed. `pg_restore --exit-on-error --no-owner`
  restored into a newly created `novaq_restore_test` database, not the source.
- All six public tables matched by canonical JSON SHA-256 and row count before
  restored-app activity: users 1, sessions 1, datasets 1, scenarios 1, jobs 0,
  alembic_version 1. The source was the idle synthetic test database.
- Archive SHA-256 was `62cf4987f43d9062111fd7396da50c9f09e7196a11843ed25d3b702bf8ca2fb4`.
- A separate API connected to the restored database passed login, dataset access,
  exact scenario recomputation, PDF/Excel downloads and logout. Its readiness
  check and nginx configuration check passed.
- No application/engine code changed in this follow-up. Reusable test scripts,
  Compose/TLS fixtures, CI and documentation were extended.

### Executed commands

The certificate directory was `.venv/https-rehearsal-01a07238` in this repository,
created specifically for this rehearsal. `NOVAQ_REHEARSAL_CERT_DIR` pointed to its
absolute path. The test image `novaq-ci-api` was built in the preceding integration
run. Relevant commands actually executed:

```powershell
docker run --rm --entrypoint openssl --volume "${rehearsalCertDir}:/certs" novaq-ci-api req -x509 -newkey rsa:2048 -nodes -sha256 -days 1 -keyout /certs/localhost.key -out /certs/localhost.crt -subj /CN=localhost -addext subjectAltName=DNS:localhost -addext basicConstraints=critical,CA:TRUE
docker compose -p novaq-ci -f docker-compose.integration.yml -f docker-compose.rehearsal.yml up -d --no-build --wait --wait-timeout 180
.\.venv\Scripts\python.exe -B scripts/stack_smoke.py --https --ca-file .venv/https-rehearsal-01a07238/localhost.crt
docker exec novaq-ci-db-1 pg_dump -U novaq_test -d novaq_test -Fc -f /tmp/novaq-rehearsal.dump
docker exec novaq-ci-db-1 createdb -U novaq_test novaq_restore_test
docker exec novaq-ci-db-1 pg_restore -U novaq_test --exit-on-error --no-owner -d novaq_restore_test /tmp/novaq-rehearsal.dump
docker exec novaq-ci-db-1 sha256sum /tmp/novaq-rehearsal.dump
docker compose -p novaq-ci -f docker-compose.integration.yml -f docker-compose.rehearsal.yml run --rm --no-deps --entrypoint python --volume "${PWD}:/workspace:ro" --env PYTHONDONTWRITEBYTECODE=1 api /workspace/scripts/compare_rehearsal_databases.py
docker compose -p novaq-ci -f docker-compose.integration.yml -f docker-compose.rehearsal.yml --profile restore up -d --no-build --wait --wait-timeout 60 api-restored
.\.venv\Scripts\python.exe -B scripts/stack_smoke.py --restored
docker exec novaq-ci-tls-1 nginx -t
```

Every command above succeeded. The updated scripts passed Ruff and mypy. The
updated CI workflow now repeats the HTTPS and recovery sequence after its HTTP
smoke check; no remote CI run is claimed.

### Files added/extended in this follow-up

| File | Reason |
|---|---|
| docker-compose.rehearsal.yml | Local TLS service, production cookie settings, separate restored API and readiness. |
| nginx/rehearsal-tls.conf | Isolated TLS 1.2/1.3 proxy using mounted temporary certificate. |
| scripts/stack_smoke.py | HTTPS/CORS/Secure-cookie and restored-record modes with fixed local destinations. |
| scripts/compare_rehearsal_databases.py | Whole-table row/hash comparison restricted to the two synthetic test databases. |
| .github/workflows/ci.yml | Repeatable HTTPS and backup/restore workflow and complete test-project cleanup. |
| docs/operations.md | Rehearsal procedure and observational-data provenance/method requirements. |
| docs/superpowers/specs/2026-09-06-result-integrity-design.md | Follow-up isolation and evidence requirements. |
| docs/superpowers/plans/2026-09-06-result-integrity-plan.md | HTTPS/recovery/observational validation execution sequence. |
| docs/superpowers/2026-09-06-result-integrity-report.md | Executed evidence and remaining input requirements. |

### Observational validation status

The owner designated `DATA_FOR_QUEUEING.xlsx` as the source of truth and described
1,555 observations across 14 days. This count and field availability have not yet
been independently verified because the workbook has not been located in the
accessible project/user folders searched. Its full path was requested. No
analytical accuracy, simulation calibration, measured waiting-time error, or
real-world staffing conclusion is claimed yet. The source must be described as
**observational queue data, not POS transaction data**.

An actual public URL/certificate, operational backup restoration and real-data
calibration remain separate from these successful isolated rehearsals. The live
`novaq` containers were observed still using older all-interface port bindings
(80/8000/5432); the hardened repository configuration has not been applied to that
running stack. No live restart, credential rotation or database mutation was
performed as part of this rehearsal.


### Follow-up closeout status

The updated scripts passed Ruff and mypy, the CI workflow parsed successfully,
and the layered Compose configuration validated. The expanded filename search
included ignored files and accessible user folders; the designated observational
workbook was still not found. Other spreadsheets were not substituted.

Docker became unavailable after the successful HTTPS/recovery checks. The
attempted `docker compose ... --profile restore down -v` failed because the
Docker Desktop Linux engine pipe was absent. A subsequent availability check
confirmed the same condition. **This rehearsal's cleanup is pending**, not
complete: its containers/database dump and ignored one-day certificate directory
may remain until Docker is available again. The earlier HTTP/Postgres rehearsal
was cleaned up successfully; this note applies to the later HTTPS/recovery run.
The current live-stack status cannot be confirmed while Docker is offline.

Remaining inputs/actions: provide the actual `DATA_FOR_QUEUEING.xlsx` file or its
full local path; restore Docker availability to finish scoped rehearsal cleanup.
No observed-data validation results have been fabricated or inferred from examples.
