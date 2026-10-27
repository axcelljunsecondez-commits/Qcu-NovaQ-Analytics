# Local tooltip pointer and placement repair — 2026-10-28

Status: COMPLETE for the local shared-tooltip implementation and loopback frontend preview. No commit, push, production deployment, operational Docker activation, operational API/database start, or migration/seeding of application data was performed for this task. Disposable regression-test fixtures are separate from operational data. No approval to deploy this new change is inferred from the preceding frontend release.

## VERIFIED scope and baseline

- Worktree: `C:\Users\Administrator\.codex\worktrees\homepage-queueing-101\NovaQ`. Branch `codex/tooltip-pointer-boundaries-20261027`; base HEAD `0b094a7868e5af22087f2b64caa01fe49820fb60`. Changes remain uncommitted. No claim is made that a different local checkout or current GitHub main contains this uncommitted repair.
- Read-only published `/calculator` baseline: the first InfoTip wrapper was 209 px wide, its button 25.59375 px wide, blank-wrapper hover opened help, and help overlapped the input. The local repair measures matching 32 × 32 px wrapper/button rectangles on desktop; small/coarse-pointer targets are 44 × 44 px.
- All current custom `InfoTip` and `Tooltip` callers share the repaired behavior: calculator fields/result explanations, result summary/key-result explanations, sidebar controls/name hints and account name hints. Browser-owned `title` hints and Plotly data hover are outside this shared text-tooltip implementation.

## Actual changes

- `frontend/src/components/ui/useTooltipInteraction.ts`: require the actual child button/link as the trigger; distinguish pointer focus from keyboard focus; allow hover transfer to help text; close after a 100 ms leave grace; support explicit explanation pin/unpin, Escape, outside pointer/focus, scroll/resize dismissal and one visible tip at a time. Outside clicks are not cancelled or forwarded.
- `frontend/src/components/ui/TooltipPopup.tsx` and `tooltipPlacement.ts`: shared fixed portal surface; prefer explanations above fields and navigation hints beside controls; avoid the owning input when falling back, constrain viewport bounds, retain theme tokens, permit long-text scrolling and respect native dialog layering.
- `InfoTip.tsx`, `Tooltip.tsx`, `frontend/src/styles/global.css`: use the shared behavior, shrink the InfoTip wrapper to its actual button, provide intentional touch targets, remove conflicting old positioning rules, and respect reduced motion.
- `frontend/src/components/layout/Sidebar.tsx`: prefer the shown-sidebar toggle hint below its control; hidden-sidebar hints stay beside controls. `frontend/src/pages/QuickCalculatorPage.tsx`, `frontend/src/components/results/KeyResults.tsx` and `ResultsSummary.tsx` remove the obsolete guest/signed-in tooltip variant. Calculation/request functions, copy and translation resources are unchanged.
- Regression tests: `InfoTip.test.tsx`, `Tooltip.test.tsx`, `tooltipPlacement.test.ts`, and `frontend/src/components/layout/AppLayout.test.tsx`. Existing sidebar dismissal assertions are retained with `waitFor` for the intentional crossing grace; direct focus calls are wrapped with `act`.
- Specification/plan: `docs/superpowers/specs/2026-10-27-tooltip-pointer-boundaries.md` and `docs/superpowers/plans/2026-10-27-tooltip-pointer-boundaries.md`.

## Verification executed

| Check | Actual result |
| --- | --- |
| Focused UI/layout/calculator regression suite | 38 passed across 5 files |
| `npm test` | 745 passed across 90 files; 650.81 s |
| `npm run typecheck` | Exit 0 |
| `npm run lint` | Exit 0 |
| `npm run build` | Exit 0; existing large-chunk warning retained |
| `python -m pytest tests/ -x --tb=short` | 3288 passed, 125 skipped, 1 xfailed, 1 warning, 9 subtests passed in 2184.86s (0:36:24) |
| `ruff check .` | Passed |
| `mypy .` | No issues in 242 source files; untyped-body notes retained |
| Real Chromium/CSS checks | 66 assertions passed |
| Final diff/scope review | `git diff --check` passed; backend, backend tests, API bridge, translations, dependencies and deployment configuration have no diff |

Browser checks cover blank-area hover, actual trigger rectangles, above-field placement, first-click input access, description association, keyboard focus/Escape, hover-to-text transfer, click/touch pin/unpin, scroll/resize, one visible popup, sidebar/account actions, EN/TL × light/dark × 1280/390/320 px widths, reduced motion and touch emulation. Additional temporary DOM layout fixtures verified overflow clipping, native-dialog top-layer visibility, long-text scrolling and 200 percent root text size. These layout fixtures are not operational company records or analytical results.

PostgreSQL-dependent regression cases remain skipped because no dedicated `NOVAQ_TEST_DATABASE_URL` was supplied; see the skip guards in `tests/test_generation_identity_migration.py`, `test_postgres_migration_chain.py`, `test_startup_schema_guard.py`, `test_api_shared_named.py` and `test_supervisor_schedule_api.py`. The strict expected failure is the pre-existing selected-load seed-stability finding in `tests/test_selected_mc_load.py`; it is not a new tooltip failure or a repaired analytical defect.

Initial focused execution had 36 passed / 1 failed: the existing sidebar test asserted synchronous unmount before the new 100 ms leave grace. The assertion remains and now waits for dismissal; the final focused run passed 38/38, including an added stale-popup-hover/Escape regression. Browser harness setup initially attempted focus on an already-focused button and scroll on a non-scrollable viewport; setup was corrected before the 66 passing assertions. Early phone full-page captures dismissed help while changing capture geometry, and one viewport capture caught the opacity animation; final screenshots wait for the animation to finish and verify opacity 1. Superseded images are not final evidence. jsdom canvas warnings are retained in the full frontend log.

After frontend verification, only the placement helper's explanatory comment was clarified to describe the trigger/input envelope accurately; no runtime statement changed.

## Limits and handoff

- Preview: `http://127.0.0.1:5173/calculator`; the Vite server is bound to loopback and returned HTTP 200 at the final endpoint check. Docker was unavailable at preflight; the operational API (`127.0.0.1:8000/health`) and web (`127.0.0.1:80`) endpoints refused connections at that check. No operational database was started or accessed by this task. This preview demonstrates the frontend interaction; a connected authenticated workflow/calculation in Docker was NOT TESTED for this task.
- Signed-in browser checks used the existing `AppLayout.test.tsx` synthetic user shape and an empty analyses response. Guest auth was a local 401 fixture. No browser calculation was submitted. Backend regression tests use their disposable fixtures; no configured external database destination was inherited.
- Physical touch, assistive-technology/screen-reader execution, true browser zoom/pinch/pan, other browser engines and a production deployment of this repair are NOT TESTED. Emulated touch and 200 percent CSS root text size are separately identified above. No accessibility certification is claimed.
- The existing selected-load/Decision statistical issue documented in `handoff.md` is outside this tooltip scope and remains unresolved; this UI repair does not certify overall NovaQ analytical release readiness.
- Private reproducible evidence: `C:\Users\Administrator\.codex\visualizations\2026\10\25\01a17357-870d-72d1-b868-9aad4a8b8cdf\tooltip-interactions-20261027`. `frontend-full.log`, `focused-final.log`, `remaining-gates.json`, `backend-pytest.log`, `ruff.log`, `mypy.log`, `browser-checks.json`, `browser-edge-checks.json`, `preview-status.json`, browser scripts, and final screenshots `after-calculator-detail.png` / `after-phone-tl-dark-final.png`. Temporary QA browser sessions were closed; the loopback preview remains available.
