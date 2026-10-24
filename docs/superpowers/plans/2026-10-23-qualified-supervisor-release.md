# Qualified configured-run supervisor release

Status: PREPARING; production NO-GO until the remaining gates pass. This plan does not assert a completed commit, CI run, deployment, current-backup restore or numerical seed repair.

## Owner decision and product scope

On 2026-10-23 the owner selected: "Allow the qualified configured-run application to proceed through release gates, explicitly accepting SEED-001 as OPEN."

This supersedes the earlier repair-first release timing in the supervisor release-closure plan. It changes the release claim, not the numerical evidence: SEED-001 remains OPEN, seed 42 remains unchanged, and no seed-stability or operational-safety guarantee is made. The visible uncertainty disclosure and configured-run wording are required. The owner has not authorized bypassing another failed gate.

Release content is the approved supervisor Settings/Review/Confirm and combined break workflow plus the verified Separate Decision context/scope corrections. Associated dated specifications, plans and evidence reports preserve their historical status and dates. Source calculations, RNG/statistics, thresholds/caps, schemas, auth contracts and unrelated work are protected.

## Candidate and observed production baseline

- Candidate checkout: C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ.
- Candidate branch: codex/supervisor-schedule-20261023; current HEAD 151486ee04147f013857f69fe8ce77d899388660, with uncommitted approved changes.
- Current GitHub main was read with git ls-remote without updating local refs: 151486ee04147f013857f69fe8ce77d899388660.
- Primary-checkout main is older, 6093d78a5874d8cbdfa0026e9c25bdb5ddc70881; do not reset or release that checkout.
- Pages project novaq-frontend production deployment 3000fea9-312c-43dc-a8a3-bd19748dff7b reports main commit 151486ee04147f013857f69fe8ce77d899388660, successful 2026-10-22. Source configuration confirms production automatic deployments disabled and preview_deployment_setting=none.
- Render service srv-daiikrbm8hqs73d15rtg reports live backend 2fcc33e22639bf4f5e962e9dc7b00e0f50d3d1f2, deployment dep-dbc3qr6q1p3s73c6vcm0. Auto-Deploy and PR Previews are Off. Start Command is the required one-worker, migration-free uvicorn command with --no-proxy-headers and --no-access-log.
- Read-only diff from that live backend commit to candidate HEAD lists no changes under backend, migrations, requirements.txt or requirements-production.lock. The pending backend edits belong to the uncommitted candidate.
- Public https://novaq.site/api/ready returned 200 with {"status":"ready"}; HSTS was max-age=2592000. This proves current readiness only, not the new candidate, schema revision or signed-in flows.

## Completed local gates

Detailed authority: docs/superpowers/reports/2026-10-23-selected-decision-scope-implementation.md and supervisor-schedule-verification.md. Source hashes must still match these tested bytes at commit time.

- Full backend: 3288 passed, 125 skipped, 1 retained strict xfail, 9 subtests passed; exit 0.
- Frontend: 711 passed / 84 files; typecheck, lint and local build passed.
- Ruff passed; mypy passed / 242 source files.
- Compiled UI: 48 EN/TL, light/dark, four-width cases plus six actual phone viewport visibility cases passed. PDF/Excel preservation and actual note rendering passed within the recorded bounds.
- Earlier same-source supervisor PostgreSQL concurrency/save verification passed 17 cases; modeled cost/save/report checks passed 91 cases plus 3 subtests. These are dated earlier results, not a new execution here.
- Current npm production audit: zero reported vulnerabilities, exit 0.
- Current pinned Python-package audit: all 52 packages audited, zero vulnerabilities, no skipped packages, exit 0. The initial resolver-mode run failed because uvloop cannot build on Windows. The successful --no-deps --disable-pip audit checks exact lockfile entries without Linux installation/resolution; required Linux CI remains pending.

## Remaining gates and concrete actions

1. Review/pin the complete itemized source/document manifest. The owner's prior separate commit/push/rebuild approval rule remains in force. Proposed action: one local scoped commit, push only codex/supervisor-schedule-20261023, and create a draft PR against main to run the configured CI. Do not push main, merge, enable automatic deploys or change production settings through this approval. CI includes its existing disposable image builds/scans; it does not replace local NovaQ containers.
2. Authenticate the actual write path when needed. GitHub CLI currently has no authenticated session. The GitHub connector can read but reports push=false; the existing browser is signed in. Do not infer push permission from a visible browser session or expose credentials.
3. Required CI/clean-candidate gates: all configured Python versions, coverage, frontend, secret scan, dependency/image scans, production preflight, PostgreSQL and disposable HTTPS/stack/recovery checks. Investigate unexplained failures; do not relabel skips or SEED-001 xfail as a pass.
4. Backup/recovery: today's novaq-sched-20261023T040023Z.dump.gpg is nonempty (833375 bytes), reports revision 0007 and ten table-data entries; encrypted SHA-256 4828d27e9b3e6c9fcf47ea060b02be52dbc978f45e92d26f28cea3555ac25d4f matches its manifest. This is local encrypted-object verification. Current OneDrive online presence is not independently verified. Keep the earlier owner's separate-key confirmation as REPORTED, not a new check.
5. Retain the recent 2026-10-20 restore evidence precisely: original 0005 backup restored successfully, counts matched, then isolated migration to 0007 and 19 container-local application checks passed; the owner accepted that boundary, retaining the failed Windows loopback probe. It is not a new restore of today's backup or a rehearsal of this new commit. Review this bounded evidence against the documented recovery policy before cutover; a fresh restore, if required, needs its own concrete scope and local passphrase handoff. Never restore over live data.
6. Render dependency provenance: observed Build Command is pip install -r requirements.txt, whose dependency ranges are unpinned. Auditing requirements-production.lock does not establish packages installed by that different command. PROPOSED smallest correction, only after CI and cutover approval: pip install --no-deps -r requirements-production.lock && pip check. First verify the configured Python runtime supports the locked set and validate the pinned Linux build. Do not silently change production configuration.
7. Finish non-secret production settings checks: actual Python runtime, one instance/worker, production mode/proxy settings, migration head/current readiness, edge/TLS/redirect behavior and usable rollback/recovery references. Do not read or print secrets. Native Excel and native-language certification remain disclosed limits; file checks do not certify them.
8. Prepare the exact-SHA cutover packet only after required gates pass. Proposed order is backend first, verify readiness/compatibility, then frontend, then public and signed-in smoke including supervisor preview/save, Decision qualifier, reports and logout using authorized test data. No production schema migration is proposed by these source changes. Never mutate a real analysis merely to manufacture a smoke result.

## Evidence and boundaries

New preparation evidence: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/supervisor-release-readiness-20261023/. Previous local-verification evidence is retained separately. No source has changed since those passing application gates during this release review.

Docker Desktop's Linux engine is currently unavailable. This read-only probe created no resource. Do not ask for or perform an existing-stack rebuild unless a remaining justified gate actually needs it; CI's disposable Linux stack is separate.

No main update, production configuration change, migration, commit, push, PR or deployment has occurred in this preparation. A passing local gate or existing live-site readiness is not proof of successful cutover. Final GO requires recorded passing gates and the exact candidate authorization; known SEED-001 remains OPEN in the release record.
