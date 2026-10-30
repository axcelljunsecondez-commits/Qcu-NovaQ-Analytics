# Shared upload: commit and local Docker activation

Date: 2026-10-30 (Asia/Shanghai). Status: COMPLETE for the owner-authorized local
Docker rebuild, activation and scoped runtime verification. The earlier download
blocker is resolved. No production release or push.

## Final resolution and active runtime

A new bounded transfer check downloaded the complete 2,383,376-byte community
index from the configured Alpine CDN. Gzip CRC/archive checks passed; Alpine
accepted that file offline with the pinned image's existing trusted keys.
An ordinary in-container `apk update --no-cache` then passed against both original
CDN repositories, reporting 27,618 packages. Official alternate mirrors also
completed host transfers, but no mirror override was needed or used.
This follows Alpine's documented [repository/index update process](https://docs.alpinelinux.org/user-handbook/0.1a/Working/apk.html).
The exact underlying reason for the earlier failed/truncated responses remains
UNKNOWN; no permanent network-reliability guarantee is claimed.

The unchanged original Dockerfile completed successfully on retry. No application
source, Dockerfile, repository configuration, TLS/signature check or dependency
pin was changed to obtain a passing build. The previously completed API image and
valid frontend build cache were reused. New active images:

| Service | Image | Image ID |
| --- | --- | --- |
| API | `novaq-local-api:20261030-shared-upload-e17ec525` | `sha256:db4437792d1c4002f847021c82cd4db3fd4bafd3ddfe5e09b2ebfede46871f63` |
| Web | `novaq-local-web:20261030-shared-upload-e17ec525` | `sha256:4004f96d3677c6a16273193ff886da62cb38b94775b1c3cc98ac02b25cfc89f2` |

Activated at `http://localhost/` by Compose `up --detach --no-deps --no-build
--pull never api web`, using the inspected existing Compose configuration and a
bounded image override. Only API/web were recreated:

- API container `f31d12cfb9f986e7a430b7dd2defa4e068959ad6a15041f4656862ea6f6819a7`.
- Web container `385ab92af8788245dec62802b93ecf4b3d1d27ff122fe03027ebf0e028331586`.
- Same DB container/volume, unchanged schema `0007`, same loopback ports and all
  10 complete table fingerprints. Environment, command/entrypoint, user, working
  directory, exposed ports, mounts, network and security/restart settings matched
  the recorded prior runtime. Migration/bootstrap were not rerun.

There were zero pending/running jobs before API/web were stopped. The database
still matched the completed backup/restore proof, so that proof/archive were
reused rather than repeated. The initial metadata preflight stopped before any
container mutation because Docker omitted an unset image Entrypoint key; the
helper was corrected to compare missing and null as unset, then the real checks
passed. No application API shape or validation expectation changed.

Executed final checks:

- Web health, API health/readiness and SPA deep routes returned 200; anonymous
  auth returned 401. Both new shared-upload POST routes are registered in the
  actual running API's OpenAPI document.
- All **89** served static files matched their exact image SHA256 values. All
  **96** backend files matched the sealed committed build context.
- Actual API and browser guest-calculator reference: explicitly synthetic
  lambda=2/hour, mu=3/hour, c=1; M/M/1 Wq=lambda/[mu*(mu-lambda)]=2/3 hour=40 minutes.
  The real Docker UI displayed 40 min, 66.6667% utilization and 1.3333 waiting.
  Captured browser error logs returned an empty array. This single analytical
  reference is not a general mathematical-correctness claim.
- All 10 database fingerprints remained unchanged after HTTP checks. The final
  post-browser comparison is recorded in `activation-final.json`.

New-image HTTP/static/backend verification is recorded in `http-verification.json`;
runtime identities/preservation in `activation-result.json`; successful packaging
in `build-web-retry-4.log`. Earlier failures below are historical, not the final
status. Authenticated operational uploads, new-image full-day runs, PostgreSQL
simultaneous-apply races and an operational rollback were NOT TESTED during this
activation. Their source/regression evidence remains separately recorded; no
company records were written for browser verification. Media playback, physical
touch and other browsers were not exercised.

## Authorization and source

The owner requested "commit and rebuild to docker", then "resume" after the
automatic approval service hit a usage limit. Scope is the existing local NovaQ
Compose project `ux-workflow-audit`, API/web only, preserving its database,
application configuration and loopback ports. No migration, seeding, volume
cleanup or production change is authorized or needed.

Feature commit: `e17ec52548f7bd54f9d14424e4ff1699df40a81b`, branch
`codex/shared-queue-workflow-20261029`. Exactly 32 scoped source/test/spec/review
files were committed. The staged diff check passed after a reviewed EOF-only
blank-line cleanup. Existing `.claude/launch.json`, `.playwright-cli/` and
`output/` remain untracked and were excluded from the commit and sealed context.

[Implementation verification](2026-10-30-shared-queue-upload-simplification.md)
records the source suites: 3,331 backend passes / 125 skips / 1 existing xfail /
9 subtests, and 805 frontend passes across 92 files. These full suites were not
repeated solely for Docker activation. The existing whole-folder Ruff/mypy
failures from old output artifacts remain explained failures, not passing gates.

The build context is assembled from committed Git objects, excluding actual
environment files, backups, logs, local dependencies and private output.
Corrected context: 420 files, SHA256
`7a47840e41197a6752a99ec34aaa964e1287fea65568c825e4f2748727cf7723`.
Images carry the feature commit in `org.opencontainers.image.revision`.

## Preservation already verified

- Same PostgreSQL container: `e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a`;
  volume `ux-workflow-audit_pgdata`, loopback port 5432 and schema `0007`.
- Fresh binary-safe custom-format dump: 499,155 bytes before encryption. Windows
  DPAPI CurrentUser encryption/decryption matched. Restoring into an explicitly
  owned disposable database matched all 10 complete table row/content
  fingerprints and revision. The owned restore database was removed. After the
  interrupted engine restart, the same operational database still matched.
- Previous API/web images have distinct retained tags and a readable archive:
  284,889,088 bytes, SHA256
  `a999fff38d7d60789e56161c16b92030213c7022bbc2c74d1e1cdf4ad6fdd68e`;
  all 34 SHA256-addressed blobs checked. Image import/operational rollback was
  not rehearsed.
- PostgreSQL API regressions: **23 passed, 2 skipped**, 171.06 seconds. The two
  skipped cases deliberately force SQLite timestamp interleaving; they are not
  PostgreSQL concurrency passes. The owned `_test` database was removed and the
  operational database still matched the baseline.

## Historical blocked build attempts (superseded by final resolution)

API image built successfully:
`novaq-local-api:20261030-shared-upload-e17ec525`,
`sha256:db4437792d1c4002f847021c82cd4db3fd4bafd3ddfe5e09b2ebfede46871f63`.
Its unchanged Dockerfile installs the pinned production lock, executes
`pip check`, and removes packaging tools.

Web's Docker typecheck, lint and production bundle build passed. Oxlint reported
zero warnings/errors; the existing Vite chunk-size/timing notices were retained.
The web image did not finish: its unchanged final `apk upgrade --no-cache` step
failed with exit 99 after 385 seconds. The community index download reported
`v2 database format error`, followed by stale/unavailable-repository refusal.
The suggested force option was not used.

The first corrected-context packaging attempt was cancelled after prolonged
network inactivity; the next attempt reused the completed frontend build cache
and produced the explicit failed gate above. The API image was reused rather
than rebuilt. Logs retain each failed/cancelled attempt.

At that blocked checkpoint, the new Compose activation function was not called. Consequently new-image
served-asset comparison, new-image browser acceptance and new-pair runtime
verification remain NOT TESTED.

## Historical preservation of the previous runtime before successful activation

The previous API/web containers were restarted without recreation, on their
previous images. The new API image remains retained and inactive. Actual final
checks passed: web `/healthz`, proxied API `/api/health` and `/api/ready` returned
200; anonymous `/api/auth/me` returned 401. All 10 full table fingerprints and
revision `0007` matched the pre-build/restored baseline again. Database/container
IDs, images, environment, ports, mounts and Docker runtime configuration match
their recorded original values. Migration/bootstrap IDs, states and restart
counts are unchanged; neither one-shot service ran.

- Existing API: `6912dc0c0624c15bf0f70d91a4c3e858911aa2be72443305d0c9c7b97f592a03`,
  `novaq-local-api:20261024-bb585a45`.
- Existing web: `0e24c83236646d2c6d8a732fb10a2dfa91a8089b825ab76b43302082edc7b619`,
  `novaq-local-web:20261028-tooltips-0213beee8153`.
- Existing application: `http://localhost/`. It does **not** contain the newly
  committed shared-upload flow; that deployment remains blocked.

The first prior-runtime health attempts failed while nginx was waiting in its
stock optional IPv6 helper. Source inspection showed `apk manifest nginx` was
trying to obtain a checksum solely to decide whether to edit the distribution's
default configuration. NovaQ already supplies its own configuration. The exact
metadata-query child process was cancelled; the helper then skipped the default
IPv6 edit and nginx started normally. No build/package-validation gate was
bypassed. The custom configuration SHA256 is
`6c2fa45fdf4b1ed8498e04d45fbad911d4e77db996d5b284578326e3a63bff7c`,
identical in the running container and a network-disabled instance of its
original image. No persistent startup-command or configuration change was made.

Evidence at that earlier checkpoint: `blocked-final.json`; full private snapshots:
`existing-runtime-final.private.json`. The failed initial startup attempts remain
historical failures, superseded by these actually executed final health/data
checks. This is preservation of the prior runtime, not a tested new-image release
or an operational rollback rehearsal.

## Explained interruptions and limits

The original API build stopped after a stalled SciPy wheel download failed its
checksum. Official PyPI metadata for the exact wheel gives 37,741,314 bytes and
SHA256 `4eb6c25dd62ee8d5edf68a8e1c171dd71c292fdae95d8aeb3dd7d7de4c364082`,
matching the build's expected digest. The unchanged build succeeded on retry;
no dependency pin or checksum verification was removed. Docker Desktop then
reported `Wsl/Service/AttachDisk/CreateVm/ERROR_TIMEOUT` while attaching its
existing data disk; its engine recovered without deleting/resetting WSL data.

The first web attempt found a missing nginx COPY input in the parent's temporary
sealed context. The exact committed `nginx/nginx.conf` was added. All 419 previous
context files remained unchanged. Application source, lockfiles and Dockerfiles
were not edited to repair this preparation error.

The automatic approval failure occurred before an additional PostgreSQL test
command executed. It reported an account usage limit, not an unsafe-action
decision. The owner's resume was followed by the completed test run above.

Read-only repository probes confirmed that the CDN's headers were reachable but
full index downloads timed out from both Windows and a disposable container.
Alpine's own `https://mirrors.alpinelinux.org/mirrors.json` was inspected before
checking alternatives. The listed `ap.edge.kernel.org` hostname failed TLS
hostname validation; it was rejected. The primary `mirrors.edge.kernel.org`
probe reported an I/O error; the Singapore `mirror.freedif.org` probe remained
incomplete and was stopped. During those earlier probes no mirror passed the index gate; no mirror override
was used for the build, and TLS, signatures and repository-availability checks
were not disabled. Only the owned probe containers, with no mounts and automatic
removal enabled, were stopped.

The earlier blocked resume boundary, now completed: first establish a successful complete signed-index download from
the configured Alpine repositories. Then rerun the saved `docker_activation.py
build` phase; it checks and reuses the completed API image. Only after the new web
image passes may `activate` replace API/web with `--no-deps --no-build --pull
never`; then execute `verify-http` and actual new-image browser checks. Retained
backups and image archives must be checked rather than recreated unnecessarily.

Source-local browser verification remains separately recorded in the
implementation report. PostgreSQL simultaneous-apply races, production,
operational rollback, physical touch and other browsers are NOT TESTED here.
The existing selected-load/Decision seed-stability finding remains OPEN.

Reproducible private local evidence:
`output/shared-upload-simplification-20261030/docker/`, orchestrated by the
adjacent `docker_activation.py`. Private container/Compose snapshots and the
encrypted backup must not be committed. No secrets are reproduced in this report.
