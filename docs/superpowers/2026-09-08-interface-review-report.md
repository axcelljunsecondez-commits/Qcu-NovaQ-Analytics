# Interface review and local Docker rebuild

## Scope

Reviewed the system in the disposable `novaq-system-ci` stack using a synthetic software-test fixture (lambda 5/hour, mu 10/hour, two current servers). This is not observational validation. No workbook was edited or imported. The user subsequently requested a rebuild of the main local Docker Compose stack.

## Browser findings and corrections

- Verified sign-in, optimizer controls, a 40% target with minimum 2/maximum 4 and five-minute wait limit, saving the result, and stale-save blocking after an input change.
- Verified that those four constraints carried to the validation page within the same application session.
- Reproduced an impossible zero-wait plan correctly returning no recommendation, but displaying literal `null` and a misleading zero-cashier summary. The UI now uses an em dash and suppresses staffing totals for stale or incomplete results. The warning covers every enabled constraint, including wait limits.
- Ran a two-hour seeded DES and the Filipino validation flow. Simulated wait values now display minutes with an explicit bilingual column label. The residual-risk verdict no longer claims that a DES status failure means the MC allowance was exceeded, or that the plan necessarily improves results.
- Verified bilingual controls and method disclosures, saved-scenario listing, and successful PDF download. No console errors were reported during that review. PDF/Excel API paths also passed the isolated HTTP smoke checks.

## Verification

Backend: 375 passed in 273.09 seconds. Existing AnyIO deprecation and pytest-cache permission warnings were reported. Ruff passed; mypy passed 73 checked files. Frontend type checking and lint passed. The isolated production frontend image built successfully, retaining the known large chart-bundle warning.

Earlier frontend runs had worker startup and asynchronous UI timing failures. The shared test helper now permits a bounded five-second asynchronous wait instead of one second; assertions are unchanged. Final suite and Docker outcomes are recorded below after completion.

## Changed files in this follow-up

- `frontend/src/pages/OptimizePage.tsx`: unavailable staffing display and translated constraint warning.
- `frontend/src/pages/SimulationPage.tsx`: simulated wait conversion and unit label.
- Both locale JSON files: unavailable-state, wait-unit and distinct DES/MC verdict wording.
- The two page test files: unavailable summary, minute conversion and verdict regressions.
- `frontend/src/test/setup.ts`: bounded asynchronous test wait.
- `frontend/src/pages/LoginPage.tsx`: wait for the authenticated React context before navigating into protected routes. Repeated login test failures persisted beyond the increased timeout; the previous immediate navigation could run ahead of query observer notification. Focused login/authentication regression run passed all 8 tests after this correction.
- Dated interface spec, plan and this report.

The API, analytical formulas, stored scenario shapes and observational records were not changed in this follow-up. Public HTTPS deployment and empirical validation are not claimed.

The main local Compose rebuild was authorized by the user and completed successfully. Its first readiness check returned HTTP 200 with `{"status":"ready"}`, and the homepage returned HTTP 200 with the SPA root. The existing persistent database volume was preserved. The disposable `novaq-system-ci` project and its test storage/network were removed. A final rebuild includes the login correction; final verification follows.

## Final outcome

`npm test -- --pool=threads --maxWorkers=1 --testTimeout=15000`: **114 passed in 17 files**, 157.73 seconds. The thread worker pool avoids the Windows fork-worker startup failures encountered in earlier runs. Final frontend typecheck and lint passed. The final `docker compose up -d --build --wait --wait-timeout 180` exited successfully, with database/API/web running and the updated login bundle included. The final homepage and readiness checks both returned HTTP 200. NovaQ is available locally at `http://localhost`; bindings remain loopback-only. No public deployment was performed.
