# NovaQ production deployment hardening report

Date: 2026-09-09

Release decision: **NO-GO for public traffic**

Functional implementation/rehearsal: **complete and passing**

Security release gate: **blocked by unsuppressed API base-image findings**

## 1. Executive summary

NovaQ now has a fail-closed production configuration, a dedicated single-host production Compose topology, one-shot migrations and administrator bootstrap, bounded database/runtime resources, layered rate limits, hardened uploads, sanitized error handling, request correlation, health/readiness checks, pinned application dependencies, production images, CI security checks, and a documented backup/restore rehearsal.

The functional repository work and representative local rehearsals pass. Public deployment remains NO-GO because the API image has unsuppressed Debian findings with no currently published fix, release-required source and migrations are still untracked, and the real external controls have not been evidenced: public TLS/DNS/renewal/redirect/HSTS, production SMTP, edge throttling and firewall policy, monitored encrypted off-host backups, alert delivery, and host secret-file permissions.

## 2. Deployment topology verified

The verified topology is:

`Internet -> external TLS proxy -> 127.0.0.1:8080 -> NovaQ nginx -> FastAPI -> private PostgreSQL`

`docker-compose.production.yml` publishes only web on `127.0.0.1:8080`. API and PostgreSQL have no host port. A fixed private bridge supports explicit proxy trust. The external TLS service is intentionally outside this repository and remains an operator responsibility.

## 3. Audit table

| Category | Status | Evidence | Risk / required action | Verification |
|---|---|---|---|---|
| Release artifact | FAIL | Required runtime, migration, Compose, scripts, and tests appear as `??` in `git status` | A clean clone does not contain the tested release; review and commit all required files | Clean-clone build and full gates |
| Production configuration | PASS | `Settings` rejects insecure/missing production values; preflight tests pass | Re-run against protected host configuration | `test_production_hardening.py`, Compose `config --quiet` |
| Secrets | PARTIAL | `_FILE` support, ignored secret material, no bootstrap secret in API | Inspect real file ownership/mode; run CI secret scan | CI gitleaks plus host inspection |
| Migrations | PASS | Dedicated migrate job; fresh/0001/0002 PostgreSQL upgrades reached `0003` | Back up before production migration | Real PostgreSQL migration-chain tests |
| HTTPS/proxy | EXTERNAL | Representative trusted-CA HTTPS path and Secure cookies passed | Configure and prove real certificate, renewal, redirect, HSTS, and forwarding chain | Public HTTPS smoke and certificate monitor |
| CORS/CSRF/sessions | PASS | Exact origins, mutation inventory, cookie parity, revocation tests | Retest on deployed public origin | API and HTTPS smoke tests |
| Rate/resource limits | PARTIAL | App 429/Retry-After, bounded compute/uploads, Compose CPU/memory/PID/concurrency | Configure external per-IP/connection/burst limits | Edge load test and alert review |
| Upload safety | PASS | CSV/XLSX only; size, ZIP, ratio, worksheet, row, column, cell, and memory bounds | Monitor rejection rates | Unit/API/stack smoke tests |
| Errors/logging | PASS | Sanitized envelope and validated request IDs; safe security events | Connect off-host log sink and alerts | Error/log tests and operator evidence |
| Health/readiness | PASS | `/health`, DB-backed `/ready`, nginx `/healthz` | External proxy must monitor `/api/ready` | Stack and HTTPS smoke tests |
| Backup/recovery | PARTIAL | Synthetic `pg_dump -Fc` isolated restore passed with matching tables/checksums | Schedule encrypted off-host backups and prove recent restore | Production backup record and quarterly rehearsal |
| Images/dependencies | FAIL | npm production audit 0; web and database scans 0; unsuppressed API scan reports 51 high and 3 critical Debian findings while Python packages report 0 | Do not release until patched upstream packages/base are available or a time-bounded security exception is approved | Blocking Trivy scan without `ignore-unfixed`, npm audit, CI pip-audit |
| Monitoring/alerts | EXTERNAL | Required signals and ownership checklist documented | Configure receivers and exercise alerts | Alert delivery drill |

## 4. Findings by severity

P0 blockers:

- Unsuppressed API image scan reports 54 OS-package findings (51 high, 3 critical), including three `perl-base` critical advisories with status `affected` or `fix_deferred` and no published fixed version. CI intentionally blocks them.
- Release-required untracked files make the current commit incomplete and unreproducible.
- Real public TLS and production SMTP are not configured or verified.
- No evidence yet of an encrypted, scheduled, off-host production backup with a recent isolated restore.

P1 before public traffic:

- Prove host firewall exposure and external client-IP, connection, request, and burst limits.
- Inspect root-owned secret files and remove/restrict the one-time bootstrap secret after use.
- Configure log shipping, retention, alert receivers, and perform an alert drill.

P2 follow-up:

- Move secrets to a managed secret store, add distributed quotas/job execution before scaling beyond one API worker, automate credential rotation, and add multi-host recovery if required.
- Reduce the large Plotly chart chunk (1,380.36 kB minified; 455.71 kB gzip).

## 5. Files changed

The hardening work spans production configuration/middleware under `backend/api/`, upload guards under `backend/data/`, database runtime and operations under `backend/db/` and `backend/operations/`, `Dockerfile.api`, `Dockerfile.db`, `frontend/Dockerfile`, `docker-compose.production.yml`, integration/rehearsal overlays, nginx production/rehearsal configuration, pinned dependency manifests, CI, scripts, tests, `.env.example`, README, and `docs/operations.md`.

The detailed design and plan are `docs/superpowers/specs/2026-09-09-production-deployment-hardening.md` and `docs/superpowers/plans/2026-09-09-production-deployment-hardening.md`. This report does not assert ownership of unrelated pre-existing dirty-tree changes.

## 6. Environment configuration

Production requires `NOVAQ_ENV=production`, an immutable `NOVAQ_RELEASE_ID`, PostgreSQL identity/secret inputs, administrator bootstrap identity/secret, `SECURE_COOKIES=1`, exact HTTPS origins and public URL, SMTP delivery/configuration, and conditional Google client ID. Auth TTLs, upload/result limits, DB pool/timeouts, worker count, concurrency, and rate limits have secure bounded defaults. Console email, demo credentials, wildcard origins/trust, non-HTTPS public URLs, NaN/infinite/out-of-range values, and more than one worker fail closed.

All supported values and classifications are documented in `.env.example` and `docs/operations.md`.

## 7. Database migration and release sequence

The production dependency chain is `db healthy -> migrate succeeds and verifies head -> bootstrap-admin succeeds -> api healthy -> web`. API startup performs configuration preflight, not schema mutation or seeding. The administrator bootstrap is create-only; existing credentials are never silently replaced.

Rollback is backup-first and forward-fix preferred. Migration `0003` allows Google-only accounts, so older code that assumes password hashes is not universally rollback-compatible.

## 8. Secrets and credentials

Database, SMTP, and bootstrap passwords are mounted as Docker secret files from paths outside the repository. The long-running API receives database and SMTP secrets but not the bootstrap administrator password. Logs avoid passwords, raw auth/session/CSRF/Google tokens, verification/reset links, SMTP secrets, and full database URLs. Secret/config/certificate/dump patterns are ignored and excluded from build contexts.

The real host must still prove ownership and mode (recommended root-owned `0600`), rotation, removal/restriction of the bootstrap secret, and CI gitleaks execution.

## 9. HTTPS and proxy trust

NovaQ nginx replaces forwarding headers and trusts only the fixed bridge gateway; Uvicorn trusts only NovaQ nginx. Production URLs are HTTPS and cookies are Secure. A trusted one-day localhost certificate verified the representative TLS path, hostname validation, HSTS at the rehearsal edge, Secure-cookie behavior, and no cookie leakage over HTTP.

The public proxy must still provide a valid certificate, renewal, TLS 1.2+, HTTP redirect, HSTS after validation, trusted client-IP derivation, throttling, access logs, and monitoring.

## 10. CORS, CSRF, cookies, and sessions

CORS uses exact credentialed origins, only the required methods, and only `Content-Type`, `X-CSRF-Token`, and `X-Request-ID`. Unknown origins receive no authorization header. Stateful mutations remain CSRF-protected; only documented stateless compute families are exempt and rate-limited. Google nonce and account-link CSRF protections remain in place.

Session cookies are HttpOnly/Secure/SameSite=Lax/Path=/; CSRF cookies are JavaScript-readable but otherwise match. Cookie deletion uses matching attributes. Expired, revoked, inactive-user, password-reset, and deactivation cases are tested. A preview/apply cleanup command exists for stale auth records.

## 11. Rate limiting and resource controls

The application uses one-minute buckets and returns `429` with `Retry-After`: authentication 10, upload 10, report 10, compute 30, and admin mutation 30 by session/client bucket. Production is intentionally one worker with concurrency 32 because the limiter is in-process. Compose bounds CPU, memory, PIDs, writable temporary filesystems, and graceful shutdown.

External initial rates and body/connection/burst guidance are documented in `docs/operations.md`; these edge controls are not yet verified.

## 12. Upload and file validation

Only `.csv` and `.xlsx` are accepted; unsupported legacy `.xls` advertising was removed. Application upload size stays 5 MiB and nginx permits 6 MiB multipart overhead. XLSX defaults enforce 50 MiB expanded size, 1,000 members, 100:1 ratio, 20 sheets, 100,000 rows, 100 columns, 32 KiB cells, and 100 MiB dataframe estimate. Signatures, member paths/types, encrypted/unsafe workbooks, parser errors, schemas, and formula-injection output are handled safely.

## 13. Error handling and logging

Unexpected failures return a stable `internal_error` envelope with a correlation ID; deliberate HTTP/auth/validation errors retain their status and structure. Production responses do not expose tracebacks, SQL, paths, parser internals, environment data, or credentials. Logs include timestamp/severity/event/request ID/method/query-free path/status/duration and safe user ID. Invalid or oversized request IDs are replaced.

## 14. Health and readiness

`/health` is lightweight process liveness. `/ready` performs a bounded database query and fails when PostgreSQL is unavailable. `/healthz` checks nginx. Compose uses API readiness and web health to order startup. SMTP and Google are deliberately excluded from liveness. The external proxy should monitor public `/api/ready`.

## 15. Database runtime and persistence

PostgreSQL is private, uses non-demo secret input, has a persistent volume, bounded shutdown, and Compose CPU/memory/PID limits. SQLAlchemy has bounded pool size, overflow, acquisition/connect timeouts, stale-connection recycling/pre-ping, and rollback/close behavior. A named volume is documented as persistence only, never as backup.

## 16. Backup and restore evidence

A synthetic PostgreSQL 16.14 database was dumped with custom format, checksum `fda06613cb38d2c2b889935115d45e642413b68c394fdaf18a6063d5af1c1a9c`, and migration revision `0003`. It was restored with `pg_restore --exit-on-error` into isolated `novaq_restore_test`. All public table row counts/checksums matched, and restored login, Analysis/dataset/scenario access, deterministic recomputation, PDF/Excel export, and logout passed.

Production target: RPO 24 hours, RTO 4 hours, daily encrypted off-host backup, seven daily/four weekly/three monthly copies, backup-failure alerts, and quarterly isolated restore rehearsal. Those operational controls remain external and unproven.

## 17. Frontend production hardening and gates

The multi-stage Node/nginx build uses `npm ci`, the lockfile, a non-root nginx user, read-only runtime, patched Alpine packages, CSP/security headers, immutable asset caching, non-cacheable HTML, SPA fallback, gzip, and `server_tokens off`. Same-origin `/api` remains unchanged. The vulnerable MapLibre dependency was removed and the required Plotly distribution is limited to Cartesian charts.

Final gates: 22 Vitest files / 131 tests passed; typecheck passed; lint passed; production build passed. The Plotly chunk-size warning is P2 performance work, not a correctness/security gate.

## 18. Backend image and startup

The API uses pinned Python `3.11.14-slim-trixie` by digest, applies current Debian security updates, installs the exact production lock without dependency resolution, verifies dependencies, removes unused pip/setuptools/wheel, and runs as UID/GID 10001. The image has safe Python environment options, no test suite/toolchain, read-only runtime, bounded tmpfs/resources, and graceful SIGTERM handling.

The rebuilt image completed successfully and the tested production/rehearsal startup chain reached healthy API and web services.

## 19. Dependency and supply-chain checks

`npm audit --omit=dev`: 0 vulnerabilities. The full development tree has two moderate findings; policy blocks high/critical and production npm dependencies are clean. Trivy 0.65.0 with the current database and no ignore option reports web Alpine packages 0 and the patched custom PostgreSQL Alpine packages/binaries 0. The API Python package set reports 0, and all fixable Debian findings were removed, but the final unsuppressed Debian 13.6 result still reports 51 high and 3 critical OS-package findings with no published fix. The critical entries are `CVE-2026-13221`, `CVE-2026-42496`, and `CVE-2026-8376` in `perl-base`; statuses are `affected` or `fix_deferred`. This is an explicit P0, not an accepted or hidden exception.

Local Windows `pip-audit -r requirements-production.lock` could not construct its temporary environment because locked Linux-only `uvloop` rejects Windows. This is an environment limitation, not recorded as a pass; CI runs pip-audit on Linux. CI builds API, web, and database images, scans them with Trivy without ignoring unfixed findings, scans secrets with gitleaks, runs npm audit, validates Compose, and receives Dependabot updates. The API scan is expected to block until upstream findings are remediated or a formal exception is approved.

## 20. Test and rehearsal results

- Backend: 440 passed, 3 skipped, 2 warnings. The skips are conditional PostgreSQL tests when no test URL is supplied.
- Dedicated live PostgreSQL migration chain: 3 passed (fresh, `0001`, and `0002` starting states to `0003`).
- Ruff: passed. Mypy: passed across 92 source files. `git diff --check`: passed (line-ending notices only).
- Frontend: 22 files / 131 tests passed; typecheck, lint, and build passed.
- Production Compose quiet preflight: passed with fixture secret files.
- HTTP stack smoke: passed SPA/assets/readiness/auth+CSRF/uploads/snapshots/PDF/Excel/rate limits.
- HTTPS rehearsal: passed TLS trust/hostname, Secure cookies, HTTP non-leakage, allowed/denied CORS, security headers, and full workflow.
- Restore smoke: passed login, records, deterministic scenario, PDF/Excel, logout; all table counts/checksums matched.
- Production API, web, and custom database image builds: passed. Web and database unsuppressed high/critical scans: 0. API application packages: 0; API OS scan: blocked by 51 high and 3 critical unfixed/deferred findings.
- Custom database privilege-drop compatibility and a disposable PostgreSQL 16 startup/readiness probe passed.

The disposable `novaq-ci` stack and volumes were removed after verification.

## 21. Required operator actions

1. Review and commit every release-required untracked file; verify from a clean clone and immutable release ID.
2. Create protected external secret files, inspect ownership/mode, and verify existing administrator access without silently resetting it.
3. Configure production SMTP and test registration verification, resend, forgot-password, reset, and failure alerts.
4. Configure public DNS/TLS/renewal/TLS 1.2+/redirect/HSTS and run the public HTTPS smoke suite.
5. Verify firewall exposure and external trusted-client-IP, body, connection, burst, and per-route limits.
6. Schedule encrypted off-host backups and demonstrate a recent isolated restore within RPO/RTO.
7. Configure log shipping, dashboards, and alert receivers; exercise readiness, 5xx, auth, SMTP, DB pool, disk, backup, migration, and restart-loop alerts.
8. Refresh/rebuild the API base when Debian publishes fixes, then require an unsuppressed Trivy result of zero; otherwise obtain a named, time-bounded written security exception with owner and compensating controls.
9. Run CI, including Linux pip-audit and gitleaks, on the reviewed commit and record the green run.

## 22. Remaining limitations

CPU-heavy computations remain synchronous. The in-process limiter is correct only for the enforced single-worker topology and resets on restart. No throughput/SLA claim is made. Operational HA, managed secrets, distributed quotas/job execution, automated credential rotation, and production backup infrastructure are outside this MVP. Google login is disabled unless deliberately configured. The large chart chunk should be optimized later.

## 23. Production GO/NO-GO decision

**NO-GO for public traffic.** Functional implementation and representative rehearsal are complete, but the release policy explicitly blocks deployment while the API image has unaccepted high/critical findings, required source is untracked, and real external TLS, SMTP, edge/firewall controls, monitored encrypted off-host backups, alert delivery, secret-file permissions, clean-clone reproduction, and the final CI run lack evidence.

Once all Section 21 evidence is recorded and no new P0/high/critical finding exists, the same checklist can be used for a GO decision.

## 24. Mathematical scope confirmation

This production-hardening work did not change queueing formulas, centralized model-selection behavior, optimizer mathematics, DES mathematics, Monte Carlo mathematics, Comparison calculations, or PDF/Excel report mathematics. Existing numerical and result-integrity tests remained green. Chart presentation changed only to remove a vulnerable mapping dependency; source values and calculations were not changed.
