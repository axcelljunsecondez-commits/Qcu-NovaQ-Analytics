# NovaQ Production Deployment Hardening Design

Date: 2026-09-09

## Objective and immutable boundaries

Prepare the existing FastAPI, React, PostgreSQL, and nginx application for the
single-host topology `Internet -> external TLS proxy -> 127.0.0.1:8080 -> NovaQ
nginx -> FastAPI -> PostgreSQL`. Queueing, model selection, optimization, DES,
Monte Carlo, comparison, report mathematics, ownership, roles, sessions, and CSRF
semantics remain unchanged.

Production readiness is evidence-based. Repository controls can be implemented
and rehearsed here; public DNS, a trusted TLS certificate and renewal, edge rate
limits, host firewall, encrypted off-host backups, alert delivery, secret-file
permissions, and real SMTP/Google credentials are external controls. Their lack
of operator evidence keeps the final decision at NO-GO for public traffic.

## Baseline evidence

- Branch: `rename/novaq`; working tree is intentionally dirty.
- Alembic chain is linear: `0001 -> 0002 -> 0003 (head)`.
- Baseline backend: 417 passed, one dependency deprecation warning.
- Baseline frontend: 22 files / 131 tests passed.
- Ruff, mypy, TypeScript, oxlint, and Vite production build passed.
- `0002`, `0003`, authentication/workspace runtime files, production Compose,
  operations documentation, and rehearsal automation are untracked. A clean
  clone of the current commit cannot start the intended release. This is P0.

## Audit table

| Category | Status | Evidence / risk | Required action | Verification |
|---|---|---|---|---|
| Release artifact | FAIL | Required migrations and runtime files are untracked; clean clone is incomplete (P0) | Preserve files and require a reviewed commit before release | `git ls-files`, clean-clone build |
| Configuration | PARTIAL | Some production validation exists; numeric bounds, database agreement, worker/pool settings, and secret files are incomplete | Central fail-closed validation and preflight | Unit tests and production preflight |
| Secrets | PARTIAL | `.env.*` ignored, but Compose injects long-lived secrets and admin password into API | Docker secret files, one-shot bootstrap, scanning | Ignore/build-context tests and scanners |
| Migrations | FAIL | API entrypoint runs migrations and bootstrap in every replica (P0/P1) | Dedicated one-shot migrate/bootstrap services | Compose inspection, fresh/existing DB rehearsals |
| TLS/proxy trust | EXTERNAL/PARTIAL | TLS is external; current forwarded headers can append spoofed values | Loopback-only web publish, fixed trusted proxy chain, representative TLS rehearsal | Compose inspection and HTTPS smoke |
| CORS | PARTIAL | Origins are validated, methods/headers are wildcard | Exact methods and request headers | Allowed/denied/preflight tests |
| CSRF | PASS/PARTIAL | Exact stateless families exist; inventory can drift | Route-inventory regression test | Mutation inventory test |
| Cookies/sessions | PARTIAL | Issuance is sound; deletion does not mirror Secure; cleanup absent | Matching deletion attributes and cleanup command | Cookie/session tests |
| Rate/resource controls | FAIL | No general application 429 control and incomplete container limits | Single-worker bounded limiter, strict payload bounds, container quotas; edge limits external | 429 and Compose tests |
| Uploads | FAIL | `.xls` advertised without `xlrd`; XLSX expansion and dataframe bounds absent; raw parser errors escape | Remove `.xls`; inspect ZIP/XLSX and bound rows/columns/cells/memory | Malicious-fixture tests |
| Errors | PARTIAL | Default unexpected errors are not structured with request ID | Sanitized global handler; preserve intentional errors | Exception/malformed/upload/report tests |
| Logging | PARTIAL | Request ID is unvalidated; security events and safe user ID incomplete | Validate IDs, structured safe events, no bodies/query/secrets | Log capture tests |
| Health | PARTIAL | Liveness/readiness exist; web health check absent | Bounded DB readiness and web health check | DB-down and public-path smoke |
| Database runtime | PARTIAL | Private in production; pool limits absent | Bounded pool/timeout/recycle settings | Settings/engine tests |
| Backup/recovery | PARTIAL/EXTERNAL | Synthetic custom-format restore exists; no operational encrypted off-host evidence | Harden rehearsal and document RPO/RTO/manifest/rotation | Isolated restore and record comparison |
| Frontend/nginx | FAIL | No CSP/security headers/compression/server token policy | Harden production nginx config and test workflows | Header, SPA, asset, GIS, report smoke |
| Images/startup | FAIL | API runs as root; unpinned base tag; coupled migration | Non-root pinned runtime, deterministic production lock, graceful bounded API | Image inspection and startup smoke |
| Supply chain | PARTIAL | Dependabot/pip-audit exist; frontend/image/secret scans incomplete | Add npm, image, and secret scans and both image builds | CI config and local scans where available |
| Observability | EXTERNAL/PARTIAL | Logs exist; rotation/retention/alerts are operator-owned | Document log and alert contract | Operator evidence checklist |

## Design decisions

### Configuration and secrets

`Settings` validates all supported numeric values for type, finiteness, positivity,
and conservative upper bounds. Production requires HTTPS origins, Secure cookies,
SMTP, a non-demo bootstrap password when bootstrap is requested, a PostgreSQL
database configuration, and Google client ID only when Google is enabled.

Secrets support Docker-style `*_FILE` inputs. Production Compose mounts database,
SMTP, and bootstrap password secret files from paths supplied by the operator.
Only the one-shot bootstrap container receives the bootstrap password. Application
logs and diagnostics never print expanded Compose configuration or database URLs.

### Release sequence and runtime isolation

Production startup is: preflight and backup confirmation (operator) -> `migrate`
one-shot -> Alembic head verification -> `bootstrap-admin` one-shot -> API -> web
-> smoke tests. API startup never migrates or seeds. The API runs as an unprivileged
user, defaults to one worker, enforces a concurrency limit, and uses bounded DB
pool settings. API and PostgreSQL have no published host ports; only web binds to
`127.0.0.1:8080`. Containers drop capabilities, disallow privilege escalation,
have PID/CPU/memory limits, and use read-only filesystems plus narrow tmpfs mounts
where compatible.

### Proxy, CORS, CSRF, cookies, and rate limits

The production nginx configuration trusts only the fixed Docker bridge gateway
for the external proxy's client-IP header, forces the upstream scheme to HTTPS,
and replaces rather than appends forwarding headers. Uvicorn trusts forwarding
only from the fixed nginx container address. CORS allows credentials only for
configured exact HTTPS origins and the methods/headers actually used.

CSRF exemptions remain exactly `/analysis`, `/simulation`, and `/optimize` plus
their descendants, because they are authenticated stateless computations. All
other authenticated mutations remain protected. Google login retains a single-use
nonce and authenticated linking additionally requires CSRF. Session and CSRF
cookie deletion mirrors issuance attributes.

A conservative application fixed-window limiter returns 429 with `Retry-After`
for authentication, uploads, reports, optimization, DES/Monte Carlo, and admin
mutations. Authenticated buckets use the opaque session identity; anonymous
buckets use the trusted client address. The initial deployment remains one API
worker, making the in-process limiter coherent. The external TLS edge remains the
authoritative per-IP/connection/burst layer.

### Uploads and errors

Supported input formats are CSV and XLSX only. XLSX validation checks ZIP magic,
required workbook members, encryption, entry count, expanded bytes, compression
ratio, worksheets, then bounds parsed rows, columns, cell text, and estimated
dataframe memory. CSV uses the same post-parse bounds. User errors are stable and
sanitized; raw pandas/openpyxl/ZIP exceptions are logged only as server exceptions
when unexpected.

Unexpected errors return `{code, detail, request_id}` without internals. Request
IDs accept only short safe ASCII tokens; invalid IDs are replaced. Request logs
contain method, path without query, status, duration, request ID, and safe user ID
when resolved. Security-event logs contain event names and IDs, never credentials,
raw email/reset/session/CSRF/Google tokens, bodies, or sensitive query strings.

### Frontend, recovery, and supply chain

Production nginx adds immutable hashed-asset caching, revalidation for HTML,
compression, `server_tokens off`, nosniff, strict referrer policy, permissions
policy, and a CSP with no `unsafe-eval`. Inline styles are allowed because Plotly
and React chart rendering require style attributes; scripts remain restricted to
self and Google Identity Services. HSTS and certificates stay at the TLS edge.

Recovery uses `pg_dump -Fc`, encrypted/off-host operator storage, and isolated
`pg_restore --exit-on-error`. Synthetic CI verifies every public table plus login,
ownership, recomputation, and reports. Target RPO is 24 hours and RTO is 4 hours.

CI installs from a production lock, audits Python/npm dependencies, scans secrets
and both container images, builds both images, validates production Compose with
fixture secret files, and runs the PostgreSQL/TLS/restore rehearsal. Critical/high
findings cannot be silently ignored; acceptance requires a documented owner,
scope, expiry, and compensating control.
