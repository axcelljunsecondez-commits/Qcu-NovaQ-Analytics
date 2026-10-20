# Approved build and verification addendum

Date: 2026-10-19, Asia/Shanghai. **Historical selector-only image stage. Current status: final focus image built and isolated checks passed; subsequent local activation completed in the [activation record](2026-10-19-local-compose-focus-activation.md).** See the [current exact image verification](2026-10-19-approved-focus-image-verification.md). The record below retains the earlier failing image check and unapplied-proposal statements as historical evidence; both CSS repairs were subsequently implemented and verified.

Owner authorization: “I AUTHORIZE YOU AND APPROVE THE VERIFICATION-CLOSURE”. Execution covered the prepared frontend image build and isolated verification. No existing NovaQ container was started or replaced. No application source, mathematical behavior, API, schema, commit, push, or production deployment changed in this continuation.

This addendum supersedes the earlier NOT BUILT and unavailable-Docker statements in the [closure report](2026-10-19-verification-closure-and-remaining-status.md). Earlier test results remain timestamped execution records, not fresh passes.

## Candidate and actual checks

Evidence directory in the primary checkout: `output/playwright/verification-closure-20261019/`.

- Worktree HEAD: `0b9423ec66d32620ed91769ac35a10e51ffae2ec`, branch `feat/ux-u1-shell`, preserving its existing dirty source.
- All 256 frozen frontend/nginx source files matched both the worktree and copied build context before execution.
- Source manifest SHA256: `537e3aed4ccfef5daffa5589d58c8b1ae701d4420169099dc3ece0c3af76cd7e`.
- Built tag: `novaq-ux-selector-web:20261019-537e3aed4ccf`.
- Docker image inspect ID: `sha256:7aa1e0291ebe0f06e0faa56447ed8ef1fc8b1bab0462cf9ad1294e088a31196d`.
- Build exited 0 in 122.45 seconds, from 2026-10-18T22:12:51Z to 22:14:53Z (06:12–06:14 local on October 19). The Dockerfile ran typecheck, lint, and the production build. Lint reported zero warnings/errors. Vite retained its large-chunk warning. The existing Dockerfile's `apk upgrade` upgraded 22 packages; the complete versions and build output are retained, so source identity is not represented as bit-identical runtime reproducibility.
- The unchanged source had already passed 683 frontend tests in 82 files, typecheck, and lint. That full suite was not repeated in this continuation; the frozen-file comparison established which source was built.

Evidence: `approved-build-preflight.json`, `approved-build.log`, `approved-build-result.json`, and `frontend-final-summary.json`.

| Executed verification | Result and limits |
|---|---|
| Isolated image startup and Nginx configuration | PASS. `nginx -t` exited 0; `/healthz` returned 200 and `ok`. Existing unprivileged-user directive warning retained. |
| Image static assets | PASS. All 66 files extracted from the image matched the bytes served by the isolated Nginx container. Root and archived SPA deep-link fallbacks also matched the image index. This container had no connected application API; no integrated application smoke is inferred. |
| Built archived selector | PASS in the isolated host API fixture serving those extracted image assets. Archived route 2 displayed selected value 2 and exactly one option for record 2. The active list excluded other archived/foreign records. |
| Selector navigation | PASS. Selecting listed record 1 navigated to `/analyses/1/data`, selected value 1, retained one option 1, and focused `main-content`. |
| Theme/viewport sampling | Selector text/background contrast measured 15.6804 in light and 11.5358 in dark. At 1280x720 EN and 667x375 TL, sampled document scroll width equalled client width; selector font was 16px. This is scoped geometry/contrast evidence, not a whole-page usability pass. |
| Reduced motion | PASS for the sampled 667x375 TL page under explicit Chrome `reducedMotion: reduce` emulation. The media query matched; maximum sampled animation and transition durations were 0.00001 seconds. This closes that sampled browser-emulation gap, not OS-wide or physical-device verification. |
| Narrow keyboard focus | FAIL. The 667x375 TL/light page gave `#analysis-switcher` keyboard focus, but the workflow footer covered its centre. This is a newly verified finding and prevents candidate acceptance. |

Evidence: `candidate-image-verification.json`, `candidate-browser-verification.json`, `candidate-runtime/browser-cli.jsonl`, `candidate-runtime/browser-http.jsonl`, and the PNGs in `candidate-runtime/`. The only initial browser console error inspected was the expected unauthenticated `/api/auth/me` 401 before fixture login; it is not presented as an application crash.

The API fixture used a new task-owned SQLite database and synthetic owner/foreign records, with the same existing helper inputs of 4 arrivals/hour, 6 services/hour/counter, 2 counters, 08:00–09:00. It never connected to the application database. The fixture served the exact image-extracted assets; this is isolated candidate behavior, not activation on the owner's existing stack.

## New finding and bounded proposal

VERIFIED: `.workflow-footer` is `position: sticky`, bottom 12px, z-index 20 (`frontend/src/styles/global.css`, around lines 3042–3055). At widths below 1024px its contents occupy two grid rows (around lines 4194–4208). In the measured 667x375 TL/light case its height was 135px and its top was 228px. The focused selector's rectangle was x=39, y=261.1875, width=589, height=45. `document.elementFromPoint` at its centre returned a footer link, not the selector. Native Tab focus did not scroll it clear.

PROPOSED experiment only: a temporary page stylesheet returned the footer to normal flow when viewport height was at most 480px. The same keyboard sequence then left the selector focused with its centre unobscured, and document widths still matched. The temporary stylesheet was removed and computed footer position returned to sticky. No application file or built image contains this proposal.

Reviewable artifacts:

- `output/playwright/verification-closure-20261019/PROPOSED-short-viewport-footer.diff` in the primary checkout: the exact one-file CSS proposal, not applied.
- `candidate-runtime/archived-landscape-tl-focused.png`: actual candidate with the obstruction.
- `candidate-runtime/PROPOSED-landscape-footer.png`: clearly marked temporary proposal preview.
- [Proposed specification](../specs/2026-10-19-short-viewport-focus.md) and [proposed plan](../plans/2026-10-19-short-viewport-focus-plan.md).

The 480px breakpoint is a proposed implementation choice tested only in the stated runtime sample. It is not a validated universal cutoff. Existing source approval for the selector was explicitly limited to its component and test; the additional CSS scope has not been applied or silently added to the image candidate. No second rebuild is inferred from approval of the prepared build.

## Preservation and cleanup

- The previous web archive remains 38,289,920 bytes, SHA256 `477edc378d18bd7b70c8117d695c2f2a7cf5aeb21551b3b21f99b74338532f80`.
- The new candidate archive is 38,289,408 bytes, SHA256 `a16c9334b696ce2470a5baf1a6db2a2c67bba94688b51ba365a8150a11af6b44`. Loading/restoring it remains NOT TESTED.
- The isolated container `14fd9f3cd94a3a6f0662324bbe83c59c68c62f703d390f240007f3e4e206e871` was identity-checked, stopped, and removed. Its logs, image, archive, and extracted assets were retained.
- The named verification Chrome session was closed. Only the identity-verified synthetic fixture process, PID 15584, was stopped; its database was retained.
- Existing NovaQ web/API/database container IDs, images, states, restart counts, and mounts matched the before records after cleanup. All three remain exited. Their exit reason is UNKNOWN; no restart or recreation was performed.

## Remaining status

| Item | Current classification |
|---|---|
| Prepared frontend image build and isolated selector check | VERIFIED completed. Existing-stack activation remains unexecuted. |
| Short-viewport focused-control obstruction | VERIFIED failure, OPEN. Exact proposed CSS scope and runtime preview prepared; source not modified. Hold activation. |
| Seed-sensitive Decision | VERIFIED prior failed execution; OPEN. Literature research does not waive it. No mathematical/statistical repair was authorized or implemented here. |
| Reduced motion | Sampled Chrome emulation VERIFIED; broader OS/device behavior NOT TESTED. |
| Native Excel | NOT TESTED. Native setup gates still cannot be observed in this thread; no registration retry loop was repeated. |
| Physical touch and true 200% browser zoom | NOT TESTED. Viewport resizing and reduced-motion emulation do not establish these behaviors. |
| Qualified Filipino review | NOT TESTED. The language rendered, but no qualified human review was obtained. |
| Native PDF font fidelity | NOT TESTED. A browser attempt to open a retained synthetic PDF was refused by the tool's file-protocol restriction; no native viewer/glyph proof was obtained. |
| Default fork-pool reliability | UNKNOWN; the successful earlier suite used the explicitly recorded thread pool. |
| Production, fresh-host recovery, actual application rollback, owner PostgreSQL restore | Outside this local verification scope; NOT TESTED. |

No blanket verification closure or waiver is recorded. The required keyboard check failed, so the candidate activation path is held under `AGENTS.md` Mandatory Stop Conditions. The next bounded implementation is the proposed footer correction, followed by its stated regression matrix and separately reviewed rebuild/activation.
