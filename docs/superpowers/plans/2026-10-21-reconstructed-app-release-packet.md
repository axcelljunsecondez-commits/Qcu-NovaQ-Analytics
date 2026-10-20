# Reconstructed application release candidate

Prepared 2026-10-21 (Asia/Shanghai). **Candidate preparation is authorized. Production cutover is NO-GO while required gates below remain open.**

The owner selected "Reconstructed application and approved fixes" for publication to novaq.site. This packet updates the October 14 packet for the actual current source and the October 20 production read-back. Historical records remain historical; they are not relabeled as fresh production verification.

## Candidate scope

- Base commit: `8e695d282047e4aed8f97cd0b2927944ece90d4c`, including the two committed selected Validation/Decision corrections. GitHub main was independently read as `0959a0feac80ecddd92bd6699d058c30b9504fa1`; it is an ancestor, 38 commits behind this base.
- The isolated candidate adds the exact 88 approved application, test and documentation files from `feat/ux-u1-shell`, plus this release packet. Original worktree/source/index are preserved. The local database `novaq_local.db`, raw research inputs, exports, backup files, credentials and generated output are excluded.
- Includes the reconstructed workflow, responsive overview and selectors, tooltip/focus refinements, Excel formatting, shared full-day report evidence, the previously approved priority/cost-unit/calculator-label corrections, and their tests and records.
- Rejected/proposed statistical-method documents are retained as explicitly historical/proposed records. No new estimator, Hoeffding gate, seed change or seed-stability correction is integrated. The seed-sensitive Decision strict xfail remains OPEN. The release must not be described as establishing operational safety or seed stability.
- No new application behavior is introduced by candidate assembly. The committed candidate SHA is recorded in Git and the PR after this packet is committed; this document does not invent it in advance.

## Verification evidence

- VERIFIED: 503 source/test/migration/dependency/contract files match the already executed isolated correction snapshot byte for byte. Managed checkout CRLF differences in 155 files were identified, verified as line-ending-only, and replaced with the existing tested source bytes. The original source remained unchanged. `Dockerfile.db` was absent from that test snapshot but is unchanged from the candidate base; its CI build is still required.
- Existing matching-source full-suite results: 3270 backend passed, 123 PostgreSQL skipped, 1 known xfailed, 9 subtests passed; frontend 683 tests in 82 files passed. These suites were not rerun during candidate assembly.
- Fresh isolated candidate checks executed October 20: `git diff --check` passed; Ruff passed; mypy reported no issues in 239 source files; six focused regression files passed **130 tests and 3 subtests**, with one existing dependency deprecation warning.
- Exact commands, timestamps, hashes, excluded paths, logs and JUnit: primary checkout `output/release-preflight-2026-10-20/`. Previous full-suite evidence: `output/selected-validation-decision-corrections-2026-10-19/evidence/`. These local evidence folders are not release inputs.
- Required exact-commit GitHub CI remains PENDING at packet creation. Prior PRs #30/#31 cover older candidates and cannot substitute for this commit.

## Production read-back (October 20, read-only)

| Component | VERIFIED observation |
|---|---|
| Render | Service `srv-daiikrbm8hqs73d15rtg`; deployed commit `43a54f78f960c81704e1065d1a0e12c675fd4e47`; Auto-Deploy Off; build `pip install -r requirements.txt`; migration-free start `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers --no-access-log` |
| Cloudflare Pages | Project `novaq-frontend`; production main `285b35ef960e539c447236141de780f40e446b74`; deployment `16a21277-f46d-4d48-9222-0f6343ff572a`; automatic deployments Disabled; build `npm run build`, root `frontend`, output `dist` |
| Supabase | Project `cltvswcopkjvnonjutre`; Table Editor read of `public.alembic_version` returned one row `0005` |
| Public readiness | `https://novaq.site/api/ready` displayed `{"status":"ready"}`. This does not verify candidate production behavior. |
| Backup | `novaq-sched-20261020T105906Z`: status OK, revision 0005, ten table-data entries; encrypted file 656608 bytes; SHA256 `4203ed8f5c3456611403a086c71cd7a561f60d4f598a69e397744dcade2376d4` matched its manifest. OneDrive cloud synchronization was not independently verified. |

The owner approved an isolated restore check. Its noninteractive attempt stopped at GPG decryption (`No pinentry`) before cluster creation. Restore success/table-count matching are **NOT VERIFIED**. The owner said they would run the interactive WSL check; the result is pending. No production backup or database mutation was performed by candidate preparation.

## Cutover gates and boundaries

1. Exact candidate CI: all required jobs must pass. Preserve known xfail/skip classifications. Do not merge a failed gate.
2. Verify encrypted backup freshness and successful isolated restore/application recovery evidence. A matching encrypted hash alone does not establish restorability.
3. Confirm actual migration connectivity/role and the reviewed maintenance sequence. Candidate head is `0007`; production is `0005`. Migrations add `datasets.purpose` (0006) and `analysis_projects.shared_closing_policy` (0007), with their documented checks/defaults. Old code cannot restart against 0007 under the exact-head startup guard; do not promise zero downtime or old-code rollback.
4. Obtain the separately reviewed owner GO for the exact production migration and Render/Pages cutover. Source preparation, a candidate branch push or a draft PR does not itself authorize production DDL/configuration changes.
5. Re-read main and live settings immediately before cutover. Use only a fast-forward main update; no force push, blind downgrade or restore over live data. Prefer fix-forward or the approved backup-first isolated recovery plan.
6. Follow the reviewed Render manual deployment and Pages production-build sequence, then verify the actual public candidate: readiness, signed-out routes/calculator, sign-in, an existing analysis through the reconstructed workflow, report exports and logout. Record actual SHAs/deployment IDs and observed results.

Native/manual checks and the existing seed-stability finding keep their recorded limitations. No blanket verification closure, operational-safety claim or production success is asserted by this packet.
