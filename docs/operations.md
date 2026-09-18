# Deployment and verification

The default `docker-compose.yml` is for local development: web is localhost:80,
API is localhost:8000, Postgres is localhost:5432, and seed defaults are demo-only.
Python 3.10–3.13 is the declared support range; CI is configured to exercise these versions. A frozen historical
`requirements-lock.txt` is not the deployment dependency source.

## Production

Use the standalone `docker-compose.production.yml` with a separate project name.
Supply the non-secret settings through an access-controlled environment file
outside the repository. Point `NOVAQ_DB_PASSWORD_FILE`,
`NOVAQ_SMTP_PASSWORD_FILE`, and `NOVAQ_ADMIN_PASSWORD_FILE` at restrictive
secret files outside the checkout; never place their contents in the environment
file or command line. The API constructs its database URL for `db:5432` from the
matching PostgreSQL components and percent-encodes reserved characters. Never
reuse demo defaults.

```
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml config --quiet
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml build --pull
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml up -d db
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml run --rm migrate
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml run --rm bootstrap-admin
docker compose -p novaq-production --env-file /secure/novaq.env -f docker-compose.production.yml up -d api web
```

Deploy a host TLS proxy with a valid certificate and your public HTTPS hostname;
forward it to `127.0.0.1:8080`. This is an explicit infrastructure prerequisite,
not TLS supplied by this repository. Only that web port is published; API and
Postgres remain private. Configure HSTS and request/login throttling at the TLS
edge after validating the trusted client-IP chain. Cookies are always Secure in
production, so sign-in requires the HTTPS endpoint.

`ALLOWED_ORIGINS` accepts a JSON string array or comma-separated origins, without
paths or wildcard entries. Production origins must use HTTPS. The application
permits files up to 5 MiB; nginx permits 6 MiB request bodies to allow multipart
overhead. Keep those limits together when deliberately raising upload capacity.

`/health` is liveness; `/ready` verifies a database query. Monitor readiness, HTTP
5xx responses, request latency, resource utilization, and failed logins. CPU-bound
work remains synchronous and is bounded; a worker queue and distributed quotas
remain future work. Do not infer service-level guarantees from these limits.

## Backups and recovery

Schedule encrypted off-host Postgres backups with a retention policy. For the
production project, use `docker compose ... exec -T db pg_dump -U <user> -d <db>
-Fc` and capture the binary output using a binary-safe runner (avoid legacy
PowerShell text redirection). Keep credentials out of shell history/logs.

Restore a backup into a **new isolated database/project**, using `pg_restore`, and
verify sign-in, dataset counts, scenario snapshots, and report downloads before
accepting it as recoverable. Rehearse restoration periodically; a persistent
Docker volume alone is not a backup. Never test restore against live data.

## Analytical boundaries

`target_utilization` is a ceiling; there is no minimum target setting. The ceiling
uses the model's reported rho (nominal offered load for Erlang-A). The optimizer
searches at most 256 integer server counts. Infeasible or non-comparable plans
have unavailable savings, including unstable baselines with surrogate penalties.

Erlang-A bounds omitted mass and first moment at relative tolerance 1e-12 and
fails explicitly after 100000 states. Its legacy W/Wq are workload divided by
served throughput, **not conditional or all-arrival mean waits**; this basis is
explicitly exposed. DES/Monte Carlo support M/M/1 and M/M/c only; other models are
reported unsupported, not silently approximated as M/M/c.

Staffing and daily-cost summaries assume one-hour segments making up one operating
day. Validate that assumption for imported data. Waiting/abandonment costs are
modeled costs, not realized payroll savings. Per-segment server requirements do
not account for shifts/breaks and are not an executable employee schedule.
Separate Queue setup stores user-configured server break schedules. The Separate
routing DES (optimizer evaluation and selected-plan simulation) applies each break
only in the period whose operating segment contains its scheduled start: the lane
drains from 3 minutes before, rests for the full duration once empty, then returns.
Periods are simulated independently, so lane break state does not carry into the
next period's run. Separate optimization keeps every configured queue active
(full coverage).

New UI saves include effective inputs, options, what-if factor, timestamp and
engine version. The API recomputes and verifies them, and makes saved calculation
inputs/results immutable. Legacy scenarios remain readable and explicitly
unverified; renaming is allowed but calculation edits require a new scenario.

## Integration checks

CI runs API regressions against a dedicated Postgres database, with a fresh random
schema per test. `NOVAQ_TEST_DATABASE_URL` must use a database ending in `_test`;
never point it at operational data. SQLite remains the default local test backend.
The separate `docker-compose.integration.yml` uses disposable database storage
and test-only credentials. Run `docker compose -p novaq-ci -f
docker-compose.integration.yml up -d --build --wait`, then
`python scripts/stack_smoke.py`. The smoke test uses only localhost:18080 and
creates test datasets/scenarios. Remove only that disposable project afterward.
These checks do not replace a real HTTPS deployment or restore rehearsal.

The M/G/c/K adjustment is an approximation; results exceeding physical queue
capacity now fail explicitly. M/G/c and priority-model approximations still need
independent calibration; no simulation assurance is provided for them.

Admin seeding is create-only: stronger environment credentials do not rotate an
existing account. Verify the existing administrator credentials explicitly during
deployment and use the documented seed reset procedure when rotation is needed.


## Local HTTPS and recovery rehearsal

Layer `docker-compose.rehearsal.yml` on `docker-compose.integration.yml`, always
using project `novaq-ci`. Set `NOVAQ_REHEARSAL_CERT_DIR` to an ignored temporary
directory containing a one-day localhost certificate (`localhost.crt`) and key
(`localhost.key`). CI shows the exact OpenSSL generation command. This test
certificate is never installed in the host trust store or used for production.

Run the layered stack, then `python scripts/stack_smoke.py --https --ca-file
<certificate-directory>/localhost.crt`. The client explicitly trusts that
certificate and verifies hostname/TLS. The API uses production Secure-cookie and
HTTPS-origin settings. Ports 18443 (TLS) and 18081 (restored API) are loopback only.

After the HTTPS smoke populates synthetic records, dump `novaq_test` with
`pg_dump -Fc` inside its container and restore into the new `novaq_restore_test`
database with `pg_restore --exit-on-error`. Never overwrite an existing database.
Run `scripts/compare_rehearsal_databases.py` inside a temporary API container on
the test network. It compares every public table and requires nonempty user,
dataset and scenario fixtures. Start the `restore` profile's `api-restored`
service, then run `python scripts/stack_smoke.py --restored` to verify login,
record access, recomputation, exports and logout after recovery.

The stack integration CI job includes this full sequence. The dump remains
inside the disposable database container, avoiding shell text conversion and
persistent copies of credentials. Remove only the `novaq-ci` project, its test
state, and the temporary certificate/key after the rehearsal. Successful recovery
of synthetic fixtures does not verify an operational backup or off-site retention.

## Observational validation source

The designated source is `DATA_FOR_QUEUEING.xlsx`, described by the owner as
14 days and 1,555 observed customer queue records. This is observational queue
data, not POS transaction data. Arrival uses the recorded Arrival field; service
duration uses Service End minus Service Start; observed wait uses Queue Waiting
(minutes). Preserve the workbook and audit missing/invalid timestamps, duplicates,
segment boundaries and staffing assumptions before comparing model outputs.
Do not substitute synthetic fixtures or example reports for this validation.
Record completeness, operating hours and actual staffed-server counts must be
established before interpreting arrivals per hour or model prediction error.

## Production release runbook (single-host MVP)

### Topology and responsibility boundary

The supported topology is `Internet -> external TLS proxy -> 127.0.0.1:8080 ->
NovaQ nginx -> FastAPI -> private PostgreSQL`. Only `web` publishes a host port.
The external proxy owns the public certificate, automated renewal, TLS 1.2+, the
HTTP-to-HTTPS redirect, HSTS, trusted client-IP creation, connection/request burst
limits, and public access logs. NovaQ nginx trusts forwarded client IP only from
the fixed production bridge gateway (`172.30.0.1`) and replaces inbound forwarding
headers before proxying to the API. Uvicorn trusts only NovaQ nginx
(`172.30.0.10`). If the Docker subnet changes, update and rehearse both values.

### Configuration inventory

| Classification | Variables |
|---|---|
| Required secret-file paths | `NOVAQ_DB_PASSWORD_FILE`, `NOVAQ_SMTP_PASSWORD_FILE` when SMTP authenticates, and `NOVAQ_ADMIN_PASSWORD_FILE`; Compose mounts these as the service-level `POSTGRES_PASSWORD_FILE`/`SMTP_PASSWORD_FILE` values. `DATABASE_URL_FILE` is the supported API alternative for an external database. |
| Required production non-secrets | `NOVAQ_ENV=production`, `POSTGRES_USER`, `POSTGRES_DB`, `ADMIN_EMAIL`, `SECURE_COOKIES=1`, exact HTTPS `ALLOWED_ORIGINS`, HTTPS `PUBLIC_APP_URL`, `EMAIL_DELIVERY_MODE=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, `NOVAQ_RELEASE_ID` |
| Conditional | `GOOGLE_CLIENT_ID` when `GOOGLE_SIGN_IN_ENABLED=1`; `SMTP_USERNAME`; external database host/port/TLS parameters |
| Secure bounded defaults | Session/auth TTLs, upload/XLSX/dataframe/result limits, DB pool/timeout/recycle, one API worker, concurrency, graceful shutdown, and application rate limits |
| Development-only | Demo database/admin passwords, console email, HTTP origins, and direct API/database loopback ports |
| Deprecated/unsupported | `.xls`, production console email, wildcard CORS/proxy trust, and multiple API workers in the initial in-process-limiter topology |

Every supported variable and default is listed in `.env.example`. `Settings()` is
the preflight: invalid types, NaN/infinity, out-of-range numbers, HTTP production
origins, insecure cookies, console email, demo database credentials, wildcard
proxy trust, Google without a client ID, and incomplete PostgreSQL configuration
fail startup. Never print expanded Compose configuration where it could expose
secrets; use `docker compose ... config --quiet`.

### Secret files and release sequence

Create three root-owned files outside the checkout, mode `0600`: database
password, SMTP password, and a one-time bootstrap password of at least 12
characters. Point `NOVAQ_DB_PASSWORD_FILE`, `NOVAQ_SMTP_PASSWORD_FILE`, and
`NOVAQ_ADMIN_PASSWORD_FILE` at them from the protected host environment file. Do not put
secret contents in shell arguments, Compose YAML, logs, Git, backup names, or
tickets.

1. Record the reviewed commit and immutable `NOVAQ_RELEASE_ID`.
2. Run all CI/release gates and the quiet Compose preflight.
3. Confirm the latest encrypted off-host backup and successful restore age.
4. Build the API, web, and patched PostgreSQL images.
5. Start `db`; run the one-shot `migrate`; verify Alembic head.
6. Run `bootstrap-admin`; it is create-only and never rotates an existing user.
7. Start `api`, then `web`; wait for health checks.
8. Run public HTTPS smoke tests and inspect alerts before enabling traffic.

Production Compose enforces migrate -> bootstrap -> API -> web. The API entrypoint
performs configuration preflight only. After bootstrap, restrict or rotate the
bootstrap secret; it is not mounted into the API. A deliberate existing-admin
reset requires `--force-reset` during a maintenance window.

Rollback is backup-first, not `alembic downgrade`. Migration `0003` permits
Google-only users without a password, so an older application that assumes a
password is not rollback-compatible after such accounts exist. Prefer a forward
fix. If rollback is unavoidable, restore the pre-migration backup into an isolated
project, validate it, and cut over deliberately.

### Initial limits and uploads

The application returns `429` with `Retry-After` using a one-minute window:
authentication 10, uploads 10, reports 10, analytical computation 30, and admin
mutations 30 per session/client bucket. Production enforces one API worker and a
default concurrency limit of 32. Synchronous CPU-heavy work is bounded but these
limits are not throughput guarantees.

At the external TLS edge start with: password login 5/minute, Google nonce/login
10/minute, registration/resend/forgot/reset 3/minute, upload 5/minute, report
10/minute, optimization 20/minute, DES/Monte Carlo 5/minute, and admin mutations
20/minute per verified client IP. Apply a 6 MiB body limit, connection limits,
burst control, and short header/body timeouts. Tune from observed legitimate
traffic and 429 rates. Do not enable IP limits before proving proxy trust.

CSV and XLSX are the only uploads. The application payload limit is 5 MiB; nginx
allows 6 MiB multipart overhead. XLSX defaults are 50 MiB expanded, 1,000 ZIP
entries, 100:1 per-member compression, 20 worksheets, 100,000 rows, 100 columns,
32 KiB text cells, and 100 MiB estimated dataframe memory. Encrypted workbooks,
invalid magic/members, `.xls`, and unsafe expansions return sanitized errors.

### Health, logs, alerts, and session maintenance

`/health` is process liveness; `/ready` performs a bounded database query;
`/healthz` checks nginx. The external proxy should monitor public `/api/ready`.
SMTP and Google are never liveness dependencies. Migration failure prevents API
startup.

Production container logs use `json-file`, five 10 MiB files per service. Ship
them off-host for longer retention. API logs include runtime timestamp/severity,
event, request ID, method, query-free path, status, duration, and safe user ID.
They must never include bodies, passwords, raw verification/reset/session/CSRF/
Google tokens, SMTP secrets, or full database URLs. Invalid request IDs are
replaced.

The named operations owner must alert on readiness failure, elevated 5xx/latency,
repeated login failures/429s, SMTP failure, DB pool exhaustion, disk/volume
pressure, backup age/failure, migration failure, and restart loops. Run `python
-m backend.operations.cleanup_auth_records` to preview expired/revoked records;
add `--apply --retention-days 7` only after reviewing the preview.

### Backup, restore, and public GO evidence

Target RPO is 24 hours and RTO is 4 hours. Take a daily custom-format `pg_dump
-Fc`, encrypt before off-host transfer, retain seven daily/four weekly/three
monthly copies, and alert on age/failure. Record UTC timestamp, reviewed commit/
release ID, PostgreSQL version, Alembic revision, encrypted-object checksum,
object location, and isolated restore result. Encryption keys must be separate.

Use a binary-safe Linux runner or write the dump inside the database container;
do not use legacy PowerShell text redirection. Restore only into a new isolated
database/project with `pg_restore --exit-on-error --no-owner`. Compare every
public table and user -> Analysis -> dataset -> scenario ownership, then verify
login, Analysis opening, calculations, PDF/Excel downloads, and logout. Never
restore over the live database. CI proves mechanics with synthetic data; actual
scheduling, encryption, off-host retention, quarterly restores, and alert delivery
require operator evidence.

Public traffic remains NO-GO until every required source/migration is reviewed and
committed; a clean clone passes all gates; secret-file permissions are inspected;
real DNS/certificate/renewal/TLS/redirect/HSTS and SMTP are proven; edge limits and
firewall exposure are verified; scans have no unaccepted critical/high result;
and an encrypted off-host backup has a recent successful isolated restore. Any
exception requires an owner, rationale, compensating control, and expiry date.
