# Local homepage and Help integration — verification report

Status: **COMPLETE for the authorized local implementation and web activation.**

Local validation recorded on 2026-10-27. Homepage: http://localhost/ ; Help: http://localhost/help . During that local implementation/validation phase, no commit, push or production deployment was performed. Subsequent release preparation is recorded separately under `../plans/2026-10-27-homepage-release.md` and the pinned candidate's CI/Pages release packet.

## Scope and provenance

- Worktree: `C:\Users\Administrator\.codex\worktrees\homepage-queueing-101\NovaQ`.
- Branch: `codex/homepage-queueing-101`.
- Implementation base: `bb585a45faf8845007e8eea7afe7c8f40ec06435`. At the local verification recorded here, the feature changes were unstaged; subsequent release preparation pins the candidate commit and CI/Pages evidence separately.
- Refreshed `origin/main` matched that base. Root `main` was older (`6093d78a`); the existing `ux-workflow-audit` checkout contained unrelated work and was not edited.
- Implements the owner's approved Hero spotlight layout and explicit local-application request. The spec and plan are under `docs/superpowers/specs/2026-10-27-homepage-queueing-101.md` and `docs/superpowers/plans/2026-10-27-homepage-queueing-101.md`.

## Actual changes

The existing headline, analysis/auth destinations, calculator, Help and language/theme controls remain. The tagline is above the headline. How it works is a collapsed, smoothly expanding three-slide guide beneath the hero. Queue types is a separate two-slide guide beneath the lesson player, with separate queues first and shared queues second. Previous/Next wraps manually. The guides do not call scrolling, anchor navigation or focus-transfer APIs; a real-browser check sampled the transition while scrolled and verified that the viewport and trigger position stayed steady.

Home and Help share the same typed lesson components. Part 1 and Part 2 are the full approved media, displayed as 2:25 and 4:22. Media loads only after Play. The player follows the existing tutorial pattern: same-origin fetch, byte/type/size validation, abort on replacement, Blob playback for seeking, pause/revoke on cleanup. Playback controls are below the picture. Captions, the English transcript, downloads, playback speed, seeking and supported fullscreen are available. Narration and burned-in captions remain English, explicitly disclosed in EN and TL.

The collection checklist distinguishes field records from NovaQ upload templates and retains the observed/unknown distinction. Both downloadable field logs contain headers only. The fictional checkout examples are labeled as teaching illustrations, not company measurements or a staffing recommendation. No company observations or computed business results were invented.

Help retains its existing written guides and tutorial library. Its search-empty condition includes the new lessons. All 56 new `queueing101` keys and interpolation placeholders match across EN/TL. The styling is scoped and uses existing tokens; no dependency was added.

### Exact file scope

Modified:

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/HelpPage.tsx`
- `frontend/src/signInFlow.test.tsx` — preserves existing navigation checks and adapts diagram assertions to the approved collapsed slides.
- `frontend/public/locales/en/translation.json`
- `frontend/public/locales/tl/translation.json`

Added:

- `frontend/src/components/home/ExpandableSlides.tsx`
- `frontend/src/components/learning/{QueueingLessons,LessonPlayer,CollectionChecklist}.tsx`
- `frontend/src/components/learning/QueueingLessons.test.tsx`
- `frontend/src/pages/HomePageLearning.test.tsx`
- `frontend/src/lib/{queueingLessons.ts,queueingLessonContent.json}`
- `frontend/src/styles/queueing101.css`
- `frontend/public/queueing101/{part1,part2}.{mp4,vtt,webp}`
- `frontend/public/queueing101/{customer-field-log,counter-availability-log}.csv`
- This report, the spec/plan and `2026-10-27-queueing-lesson-assets.json` in this reports directory.

At local verification, `git diff --check` passed and `git diff --cached --name-only` was empty. A protected-path comparison against the implementation base returned exit 0 for backend, existing backend tests, nginx, Compose, dependency manifests/lockfile, HTTP/auth source. The full status list contained only the listed application, test and documentation scope. Browser helpers, screenshots, private backup and local activation artifacts are outside the Git worktree.

## Executed verification

| Check | Actual result |
| --- | --- |
| Locked dependency installation | `npm ci` completed; no manifest or lockfile changes. |
| Focused frontend coverage | 35 passed in 4 files. |
| Full frontend suite | `npm test -- --pool=threads --maxWorkers=1 --testTimeout=15000`: **725 passed in 86 files**, exit 0. Repeated after the final CSS correction: 725 passed again, 312.16 seconds; see `frontend-final-css-gate.log`. |
| Type check | `npm run typecheck` passed; final `npm run build` also ran `tsc -b` successfully. |
| Frontend lint | `npm run lint`: passed. |
| Final production build | `npm run build`: passed, 300 modules. |
| Backend suite | Project venv Python `-m pytest tests/ -x --tb=short`: **3,288 passed, 125 skipped, 1 xfailed**, 9 subtests passed, exit 0; 2,187.97 seconds. |
| Python lint | Project venv Python `-m ruff check .`: passed. |
| Python types | Project venv Python `-m mypy .`: passed, 242 source files. |
| Full media integrity | Both MP4 hashes match the original full files; FFmpeg decoded both complete files with exit 0 and empty error output. |
| Actual app browser tests | The initial integration passed 70 checks on development, compiled preview and localhost. After the diagram CSS correction, the **final candidate passed 90 checks on the compiled preview and 90 on the activated localhost Docker web app**. These repeat the same behavior; do not add their counts as distinct coverage. |
| Docker static-content comparison | All **84** files in the new image exactly matched `frontend/dist` by SHA-256. |
| Live HTTP | `http://localhost/healthz`: 200; `http://localhost/api/ready`: 200. Web and database containers were healthy. |
| Data/config preservation | All 10 public-table row counts/content fingerprints matched before startup, after API startup and after browser verification. Existing API/database container IDs, images, full Config/HostConfig hashes, ports and mounts were identical. |

Browser coverage includes actual audio/video decoding, full-file duration, Blob seeking, speed/pitch, no media request before Play, controls below the picture, both guide transitions, wrapping in both directions, stable slide height, inactive/closed content being inert, checklist Escape/focus restoration, header-only downloads, Help search and retained guides, EN/TL, painted light/dark themes, widths 320/375/768/1024/1440, reduced motion and no uncaught browser script errors. The final 20 additional checks assert that both diagrams use the card's available width, retain their aspect ratio and keep labels inside their viewBox in each language/theme/width combination. Mobile separate/shared diagrams were also inspected in the browser, including a 375px Filipino dark-theme viewport screenshot. These are actual React pages without mocked API or operational records.

### Test limits and inherited findings

- **NOT TESTED:** the 125 skipped backend cases require a dedicated PostgreSQL test database/native PostgreSQL behavior via `NOVAQ_TEST_DATABASE_URL`, which was not configured for this run. This includes 5 shared API cases, 91 generation-identity migration variants, 3 migration-chain cases, 24 startup-schema variants and 2 supervisor concurrency cases. They were not run against the user's live local database.
- **VERIFIED existing expected failure:** `tests/test_selected_mc_load.py:147` marks `test_novamart_failing_lanes_are_stable_across_base_seeds` as strict xfail for the known seed-sensitive Decision/MC uncertainty finding. This task does not resolve it. Passing this suite does not independently prove queueing mathematics correct.
- The build emitted a large-chunk warning for the existing simulation bundle. Vitest reported the JSDOM canvas-method limitation; pytest reported an AnyIO alias deprecation. No gate failed on the final candidate.
- **NOT TESTED:** a new full signed-in operational workflow, learner comprehension/user research, other browsers, production, or runtime rollback restoration. Existing sign-in/navigation regression tests passed; the live browser run exercised the public pages and existing API readiness.

## Local activation and recovery

Only `web` was recreated, using Compose `up -d --no-deps --no-build --pull never web` with the original runtime's Compose files and an additional image-only override. No migrate/bootstrap service ran. Existing API/database containers were started without recreation. Repository Compose files, published ports, inherited nginx configuration, API image/settings, database volume and dependencies were unchanged.

| Item | Verified value |
| --- | --- |
| New web image | `novaq-local-web:20261027-queueing101-v2-bb585a45` |
| Docker image ID | `sha256:1552aca863d83739859801be0eb1c893ce7c21463742871333bef6592c06f7ae` |
| New web container | `61ebfeaa952c40d1fec5f564aba78291226c7eb9093340809abc4b3835325609` |
| Previous web image retained | `novaq-local-web:20261024-bb585a45`, `sha256:bc898f55adab7b2e30151c610531f3d536cab76cf7582798da1fb7723491361f` |
| Existing API container retained | `6912dc0c0624c15bf0f70d91a4c3e858911aa2be72443305d0c9c7b97f592a03` |
| Existing API image retained | `novaq-local-api:20261024-bb585a45` |
| Existing database container retained | `e7830fab049112dae8382aa27fc58ce87fc9ddfa587d82d982bf842c9f073b2a` |
| Existing database volume retained | `ux-workflow-audit_pgdata` |
| Web binding | `127.0.0.1:80` to container `8080/tcp` |

A fresh custom-format database backup was created before web replacement, outside Git. Size: 499,006 bytes; SHA-256 `8c15a6dc52894675bdb8336ad7ae02a7ebc75f910639bfe87a38feaee66f855a`. `pg_restore --list` succeeded. This verifies archive readability, **not a restore rehearsal**. The previous web image is retained; no rollback was executed.

Private backup and fingerprint records:
`C:\Users\Administrator\.codex\visualizations\2026\10\25\01a17357-870d-72d1-b868-9aad4a8b8cdf\local-activation-20261027`.

The image-only override, packaging Dockerfile, activation guard, browser helper/logs and screenshots are in:
`C:\Users\Administrator\.codex\visualizations\2026\10\25\01a17357-870d-72d1-b868-9aad4a8b8cdf\local-app-verification-20261027`.

To return to the retained previous web image, omit this task's last override and use the original two-file runtime configuration, targeting only web:

```powershell
docker compose --project-name ux-workflow-audit `
  -f 'C:\Users\Administrator\Desktop\QUEUING_THEORY_NOVAMART\NovaQ\.claude\worktrees\ux-workflow-audit\docker-compose.yml' `
  -f 'C:\Users\Administrator\Desktop\QUEUING_THEORY_NOVAMART\NovaQ\output\local-release-update-20261024\activation.compose.yml' `
  up -d --no-deps --no-build --pull never web
```

This recovery command is documented, **NOT TESTED by executing a rollback in this task**. Confirm image presence and configuration before a future use.

## Failures encountered and resolved before completion

- New test code initially supplied an unsupported Testing Library `exact` option; removed it and reran successfully.
- Two focused assertions exposed an ambiguous disclosure accessible name. Added explicit title/description ARIA references, then all 35 focused cases and the complete 725-test suite passed.
- A browser assertion required literal `0s` for reduced motion, while the existing global rule uses `0.01ms`. Corrected the assertion to accept that near-zero duration with zero slide animations. Reset the media-emulation fixture explicitly on each run; subsequent actual-app runs passed.
- Final mobile visual review caught a broad guide-SVG selector shrinking the queue illustrations to icon dimensions. Restricted the selector to the disclosure/navigation chevrons, rebuilt, and added 20 diagram size/label checks. The final 725-test frontend rerun and both final 90-check browser runs passed before completion. The illustration component itself was unchanged.
- One compiled-browser CLI invocation passed the filename argument incorrectly; corrected the invocation. The compiled and final localhost runs passed.
- Initial web packaging correctly stopped because the repository ignores `frontend/dist` in Docker contexts. Repackaged the verified build from a separate artifact context, preserving the repository configuration. The resulting image matched all 84 compiled files exactly.
- Docker Desktop initially lacked an available engine and later interrupted API/database containers (exit 255, not reported as OOM). No web activation was performed during those interruptions. After the existing engine/API/database became available, readiness, backup/preservation checks and guarded web activation succeeded. The underlying Desktop interruption cause is **UNKNOWN**; no Docker settings or backend fixes were invented or applied.

No remaining blocker was observed for this homepage/Help change at final verification. Unrelated statistical/tooling findings and the explicitly untested coverage above remain outside this task.
