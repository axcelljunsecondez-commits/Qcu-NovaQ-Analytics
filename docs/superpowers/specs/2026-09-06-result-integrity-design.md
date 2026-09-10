# NovaQ result integrity and production configuration

## Objective and working-tree safety

Implement the user's verified correctness and hardening request without replacing
the engine/API/database/React architecture. Preserve the 15 pre-existing modified
files and the untracked `.pytest_tmp/`, `pptx-output/`, and `reports/` directories.
An external temporary baseline contains their original bytes, hashes, and Git diff.
No real credentials, existing database, or running deployment will be changed.

## Analytical semantics

- `target_utilization` is the maximum allowed reported utilization, in `(0, 1]`.
  There is no existing minimum-utilization setting to invent. Nominal offered-load
  utilization remains the Erlang-A response contract; this ceiling is conservative
  for models with abandonment. Every recommendation must meet it and `max_servers`.
- Evaluate all feasible integer server counts. Apply `c <= K` only for the finite
  model selected by the existing centralized dispatcher. A post-search heuristic
  cannot override the optimum. Equal cost prefers the smaller feasible count.
- An infeasible row has null recommended count/cost/deltas and an explicit reason.
  A complete aggregate requires nonempty, matched, feasible rows with finite costs.
  Otherwise optimized aggregate cost and savings are null, not zero. Add completeness
  and comparable-row metadata; retain existing response names and envelopes.
- Erlang-A uses log-space probabilities with geometric bounds on omitted tail mass
  and first moment, relative tolerance `1e-12`, and a 100000-state safety budget.
  Non-convergence or failed physical invariants returns an explicit error.
  Throughput is computed from occupied servers and cannot exceed `c * mu`.
  Retain legacy `W`/`Wq` workload-per-served-throughput ratios, explicitly label their
  metric basis, and do not silently present them as all-arrival mean waits.

## Validation and reproducible calculations

- Uploads distinguish absent optional cells from invalid supplied values. Reject
  nonfinite values, invalid domains, and fractional integer parameters with row and
  column context before conversion; never silently change the selected model.
- Current DES and Monte Carlo support M/M/1 and M/M/c only. Use `select_model` to
  identify the requested family. Preserve all inputs and explicitly mark other
  models unsupported, including in plan validation; no positive validation claim
  may be derived from unsupported or missing results. Metadata is additive.
- Saving uses the actual completed request/result snapshot, not mutable form state.
  Any dataset/options/factor change makes prior results stale and unsavable.
- Keep existing scenario option keys and `results: {results: rows}`. Add
  `settings.calculation` with `schema_version: 1`,
  `engine_version: "novaq-2026-09-integrity-v1"`, `input_segments` (effective inputs),
  `options`, `what_if_multiplier`, and `calculated_at`; selected-model metadata can
  also be recorded. Validate correspondence on the server. Versioned calculation
  inputs/results cannot be patched after saving; renaming is allowed.
- Legacy scenarios remain readable. Missing provenance must be visible and must
  not be asserted reproducible. No database migration is needed for JSON metadata.
- The current-session query is the single frontend auth source. Login updates it;
  logout, expiry, deactivation, and refreshed roles supersede any old login result.

## Reports and deployment

- Propagate incomplete-result semantics into comparison, ROI, PDF, and Excel.
  Missing utilization is unavailable. Waits display in minutes, with model-basis
  notes where necessary. Preserve the user's staffing summaries and download fixes.
- Escape untrusted text before ReportLab markup parsing and prevent spreadsheet
  formula interpretation for exported text, including client-supplied scenarios.
- Keep a convenient development Compose stack, with local-only service exposure.
  Add a standalone production Compose configuration with mandatory credentials,
  private database/API services, secure cookies, and an explicit trusted TLS proxy
  boundary. Never silently deploy this configuration.
- Support documented JSON-array or comma-separated CORS origins with strict
  validation. The application file cap is 5 MiB; nginx permits 6 MiB request bodies
  for multipart overhead while the application enforces the exact file cap.
- Retain Python 3.10 compatibility by using `timezone.utc`, align lint targeting,
  and test supported runtimes. Add isolated Postgres and nginx smoke coverage in CI.

## Verification and deferred work

Write failing regressions before fixes, then run focused and subsystem tests and
the repository gates. Tests use isolated temporary databases and a separate Docker
project where available. Record exact commands and failures, including environment
limitations. Evaluate secondary improvements after the core work; avoid introducing
background jobs, employee scheduling, or new simulation families in this change.


## Follow-up: HTTPS and recovery rehearsal

Use a separate disposable project, test-only credentials and a short-lived local
certificate. Terminate TLS at nginx in front of the existing web/API path; use
production cookie/origin settings. Trust only the explicit rehearsal certificate
in the test client, never disable certificate verification or install a host CA.
Test Secure/HttpOnly cookie behavior, CORS, CSRF, uploads and exports over HTTPS.
Dump only the synthetic rehearsal database to a custom-format archive inside its
container. Restore into a new database, compare all application table contents,
then serve the restored database in a second API and verify login, saved inputs/
outputs and downloads. Never restore over the running user database.
Public TLS and real-data calibration require a supplied hostname and observed
records. Example workbooks do not establish operational accuracy or provenance.
