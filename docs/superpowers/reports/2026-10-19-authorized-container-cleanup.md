# Authorized stopped-container cleanup

Date: 2026-10-19, Asia/Shanghai. **Cleanup scope: COMPLETE. Overall verification closure remains PARTIAL.**

Owner request: “delete the containter not needed or do the image 1 complete the verification before we clean up”. The assistant first reviewed verification completion and retained data, then removed only the explicitly reviewed stopped candidates. Current application, setup jobs and builder were excluded.

## Verification completion checked before removal

These are reviewed historical executions, not newly rerun suites:

- Excel layout smoke: actual container log JSON verifies 102 source matches and four workbook payload/formatting cases. Saved host logs/payload evidence remain. Native Excel recalculation is still NOT TESTED.
- Final report verifier `-r2`: actual container log verifies 102 source/config matches, full-day mapping and four PDF/XLSX render cases.
- Earlier report verifier: its log contains successful output and later import-path/temporary-directory harness failures. These failed attempts were retained and were **not** reclassified as passing based on its final container exit code. The final r2 verification superseded that harness setup.
- PostgreSQL fixture: saved result exit 0, selected cases 123; JUnit XML independently contains 123 cases and zero failures/errors/skips. The fixture's retained volume was not removed.
- Archive startup fixture: actual logs retain internal health/readiness 200. That historical isolated test does not establish application rollback, PostgreSQL restore or fresh-host recovery.

No application dependency changed, so these completed checks were not needlessly rerun. The native/manual and known seed-sensitive Decision gates were not waived.

## Actual removal and preserved data

20 exact-ID stopped containers were removed with separate `docker container rm <full-id>` commands. No force, volume-removal option, prune, Compose down, rebuild or application restart was used. Every removal returned exit 0 and its expected ID. Execution: 2026-10-19T05:46:35.042497Z to 05:46:48.684256Z (13:46 local).

Before deletion, inspection records, stdout/stderr logs, writable-layer diffs and changed Nginx/runtime-entrypoint configuration files were preserved. Bind-mounted evidence paths were checked to exist. Candidate writable-layer changes contained the reviewed mount stubs, PID/socket/cache files and copied configuration, with no unexpected application-data path found. Older `novaq` and `novaq-u10` databases use retained named volumes; `novaq_stage3` was configured with tmpfs database storage. No volume was deleted.

Removed:

- `novaq-excel-layout-smoke-d2daf9c43cbc` (`c376a653c585`)
- `novaq-report-archive-startup-20261017` (`0d03f0f75189`)
- `novaq-report-pgtest-20261017` (`20d65dc2b83a`)
- `novaq-report-verify-20261017-746d67703409-r2` (`0b1aa02ca985`)
- `novaq-report-verify-20261017-746d67703409` (`648a47cd19ac`)
- `novaq-u10-api-1` (`cfa6863aa480`)
- `novaq-u10-web-1` (`946a0a2f4ea1`)
- `novaq-u10-bootstrap-admin-1` (`26c0203ee30f`)
- `novaq-u10-migrate-1` (`9f0ac4565e3f`)
- `novaq-u10-db-1` (`727c3f889b56`)
- `novaq_stage3-web-1` (`522c79a332f3`)
- `novaq_stage3-api-1` (`85a31d19a48b`)
- `novaq_stage3-bootstrap-admin-1` (`0fb66383fa0a`)
- `novaq_stage3-migrate-1` (`ed3a8f7859c5`)
- `novaq_stage3-db-1` (`74c6831c58aa`)
- `novaq-api-1` (`a915be6f1b3f`)
- `novaq-bootstrap-admin-1` (`33e5a88e6307`)
- `novaq-web-1` (`edf336b47601`)
- `novaq-migrate-1` (`b356e7a28acb`)
- `novaq-db-1` (`c8706d00ab8e`)

## Final executed checks

- Exactly six containers remain: current `ux-workflow-audit-web-1`, `api-1`, `db-1`, `migrate-1`, `bootstrap-admin-1`, and `buildx_buildkit_default`.
- Web/database running and healthy; existing API running, with actual proxied health/readiness HTTP 200. Migration/bootstrap remain completed/stopped. All six retained IDs/images/configuration/mounts/start times/restart counts matched the before snapshot; no application restart.
- Image inventory unchanged (72 listed ID/repository/tag/digest entries; this is not asserted to be 72 unique images). All 20 volumes and all seven networks retained with unchanged inventories.
- Web `/healthz`, `/api/health`, `/api/ready` each returned 200 after cleanup.
- All 79 preserved evidence-file hashes and selected original host evidence hashes rechecked after removal. Final source/HEAD/staging checks are recorded separately in `final-source-preservation.json`.
- No commit, push, production access, mathematical/source-data change, or additional verification waiver.

Evidence in primary checkout: `output/docker-cleanup-2026-10-19/`: plan, before/after inventories, `approved-cleanup-targets.json`, `verification-completion.json`, per-container saved logs/diffs/configuration, `host-evidence-hashes.json`, `preserved-evidence-manifest.json`, `cleanup-result.json`, and `final-source-preservation.json`.

Historical reports describing these QA containers as retained refer to their earlier execution dates. Their logs/files now remain in this cleanup evidence directory; the containers themselves are removed. Historical container-inspection helpers cannot be replayed against deleted IDs without preparing new test resources. No claim of tested container restoration is made.
