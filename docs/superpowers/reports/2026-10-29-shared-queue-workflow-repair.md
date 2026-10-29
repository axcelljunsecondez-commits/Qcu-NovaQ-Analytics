# Shared-queue screenshot follow-up — 2026-10-29

Status: COMPLETE for the bounded local frontend repair and its verification; PARTIAL for
the original saved-runtime investigation and any extension of the full-day engine. This
report records the scoped follow-up to the owner's screenshots;
the earlier CSV diagnostic did not reproduce these selector-state transitions or the owner's
capacity/abandonment configuration.

Branch: `codex/shared-queue-workflow-20261029`; starting application HEAD `e2dbe5d5`.
Chrome owns the scoped frontend implementation. Root owns backend classification,
integration/browser verification and this report. No commit, push or deployment is requested.

Owner-requested backend follow-up: [actual backend diagnosis](2026-10-29-shared-queue-backend-followup.md).
It passed 161 backend tests and 37 HTTP checks without reproducing a backend defect. No backend
application change was made; the existing production/saved-runtime limits still apply.

## Findings and bounded repair

1. VERIFIED frontend state defect: `PlanChanges.Switcher` kept its initial selected id after
   the authoritative selection or available options changed. A removed dropdown choice could
   leave the browser visibly showing one option while React retained a different choice, and
   that old choice could revive when the option returned. Regression baseline: 3 failed,
   20 passed in `chrome-results-before.log` (two state cases plus missing selected feedback).
2. VERIFIED presentation gap: an already-selected plan intentionally disables Use for
   simulation. The screenshot is consistent with this condition. Existing approved
   `compare.selected_for_simulation` wording can identify the selected current plan without
   generating duplicate selection evidence. A backend persistence defect on first save is
   still UNKNOWN; it must be distinguished from this selected-state feedback.
3. VERIFIED engine scope: `_setup_reasons` blocks finite capacity or modeled abandonment;
   `_row_reasons` also blocks supplied K/theta. The owner's screenshots show the corresponding
   refusal, so absence of replay follows the absence of a successful run. The owner's exact
   saved setup and normalized rows have not been inspected. The fix preserves the scope gate
   and adds a Data and Setup recovery link using existing wording.
4. VERIFIED display gap: early compatibility rejection can withhold the horizon. Displaying
   "not set" in that case overstates what is known. Show the hours as unavailable with the
   existing locale strings; do not fabricate operating times.

## How Named Shared Queue is used

VERIFIED from `NamedSharedQueueSimulation.tsx`, `NamedWorkforceForm.tsx`,
`namedWorkforce.ts`, and `backend/api/shared_named.py`:

Named Shared Queue simulates a supplied employee roster serving one shared line. It identifies
employees by pseudonymous IDs and shows one replication's employee activity, breaks, playback
and operational attribution. It is a separate input workflow from Current/Suggested full-day
simulation. Its setup also requires unlimited capacity and abandonment not modeled; it does
not bypass the full-day capacity/abandonment limitation.

To use the existing screen:

1. Select a processed planning dataset explicitly. Demand must be aggregate `HH:MM-HH:MM`
   rows without variance, K or theta. The supplied CSV has those four aggregate columns;
   compatibility of a particular saved dataset depends on its normalized contents and setup.
2. Enter the operating horizon, the required counters for each staffing interval, register
   IDs, shift rules and applicable break rules. Required staffing is independently supplied;
   this version does not automatically copy it from an optimizer or the CSV.
3. Enter employee IDs, availability windows and the roster's actual shifts and placed breaks.
   Pay fields can explicitly be marked not supplied. Do not infer a real roster from aggregate
   arrival and service rates or enter real employee names in place of pseudonymous IDs.
4. Choose a closing policy and validate the inputs. Resolve reported problems. Run is enabled
   only for a runnable validation of the exact current form, valid replications/seed and limits.
   Editing the workforce form requires validation again.
5. Enter the replication count and seed, run, open the saved run, then select a replication to
   inspect its playback and attribution. This slice displays descriptive results with no
   staffing-plan pass/fail verdict and no workforce cost.

The owner supplied no actual employee roster or availability with this task. A named run using
the owner's real staffing is NOT TESTED; no roster or employee data has been invented. The
standard shared-queue mode is the tested path for the provided demand-rate CSV alone under
compatible explicit setup choices.

## Verification record (updated as checks finish)

- PASS: 9 focused existing backend B4a tests for unsupported configurations, missing closing
  rule/selection, and supported current/suggested staffing. Eighteen cases deselected; one
  Starlette/AnyIO deprecation warning; 23.83 seconds. Log:
  `output/shared-queue-workflow-20261029/backend-refusals.log`.
- Initial frontend recovery-link regression: 2 failed, 61 skipped before implementation.
- First focused repair run: 90 passed across ResultsPage, QueueSimulationPage and wording
  policy. Final horizon-specific cases: 2 passed, 61 intentionally skipped.
- PASS: final source `npm run typecheck`, `npm run lint`, `npm run build`, all exit 0.
  Vite retained the existing large-chunk warning. Logs: `typecheck.log`, `lint.log`, `build.log`
  in `output/shared-queue-workflow-20261029/`.
- PASS: full `npm test`: **752 passed across 90 files**, exit 0, 773.60 seconds. Log:
  `output/shared-queue-workflow-20261029/frontend-full-tests.log`. The existing jsdom
  canvas-not-implemented messages appeared; no tests failed. Passed-file counts appeared
  at completion after a quiet interval; that interval was not classified as a test failure.
  Worker-process inspection was read-only.
- No numerical backend change was made; the full backend suite, Ruff and mypy were not
  rerun for this frontend-only repair. The 9 focused backend tests above are the actual
  newly executed backend regression evidence.

## Actual browser walkthrough

VERIFIED against the freshly built candidate served at `127.0.0.1:18766` in a unique disposable
SQLite database. Both fixtures uploaded the owner's unchanged CSV. Fixture 1 used unlimited
capacity and abandonment not modeled; fixture 2 used explicitly SYNTHETIC finite capacity 20
and abandonment not modeled. These are diagnostic settings, not assertions about the owner's
real operation or saved analysis. The CSV SHA-256 remained
`236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e`.

- Saved `One save test` once using Save without using. It appeared as the only saved option;
  choosing it enabled Use for simulation. Selection succeeded and the new selected-state
  message appeared with the intentionally disabled action. No second save was needed.
- Calculated/saved `Second plan test` using Use this plan. The Results list immediately
  contained both plans, the newer plan was identified as selected, and switching to the first
  and back to the second succeeded with the proper status each time.
- The supported suggested full-day run completed (`Done`), and Replay loaded its clock at
  05:00. The repair did not enable unsupported configurations or change DES input semantics.
- Switching to fixture 2 showed the capacity/abandonment refusal, `Operating hours:
  Unavailable`, and a disabled run. The new Data and Setup link navigated to
  `/analyses/2/data`, where the configured finite-capacity value 20 was visible. No setting
  was changed to bypass the refusal.
- In dark mode at 375 x 812, the selected-status text remained visible and wrapped within
  the page. Read-back: viewport width 375, document scroll width 360; no page-level horizontal
  overflow was observed. Existing tabular presentation was not redesigned.
- Browser warning/error log read-back was empty. The server log contained two successful
  scenario-creation POSTs (one per intentionally saved test plan), no ERROR/traceback/5xx
  matches through completion. Screenshots of the selected status and corrected refusal were
  displayed in this chat; no claim of a separate screenshot file is made.
- One browser observation used a region name shared by a parent section and its table and
  raised a strict-locator error after selection had succeeded. Inspecting the uniquely named
  status verified the action; it was not an application error.
- The owned test tab was closed, viewport override reset and temporary server stopped.
  Logs and the uniquely named disposable database remain as local evidence. No operational
  database, Docker container or production application was changed by this walkthrough.

## Evidence and scope

Actual implementation files:

- `frontend/src/components/results/PlanChanges.tsx`: synchronize the selector's lifetime with
  authoritative analysis/selection, discard removed drafts, and explain a usable selected plan
  with the existing approved locale key. The no-reselect rule remains.
- `frontend/src/components/queueSimulation/ContinuousRun.tsx`: correct withheld-hours display
  and link unsupported capacity/abandonment configurations to the same analysis setup.
- `frontend/src/pages/ResultsPage.test.tsx` and `QueueSimulationPage.test.tsx`: behavioral
  regressions for selector changes, stale/removed choices, successful switching, and blocked
  recovery without enabling unsupported requests or requesting nonexistent playback.

No save/cache defect was reproduced, so `OptimizePage.tsx` and `useSelectedPlan.ts` are
unchanged. No Named UI, employee policy, simulation formula or locale text was edited. The
actual final diff and file hashes are saved as `frontend.patch` and `source-identity.json`
under the integrated artifact directory. The branch remains at `e2dbe5d5` with local,
uncommitted changes; no changes were staged, committed, pushed or deployed by this repair.

Remaining unknowns and limits:

- The owner's real saved setup, dataset normalization and selected-plan evidence still have
  not been read from an authenticated runtime. The CSV test does not prove deployment parity.
- The screenshot's inability to create a full-day run remains an engine-scope limitation for
  finite capacity/modeled abandonment. These features were not implemented. If the operator's
  real situation fits unlimited capacity and abandonment not modeled, those truthful settings
  can be reviewed in Data and Setup; otherwise this needs a separately authorized analytical
  feature specification. No operational settings were changed here.
- The reported need for a second save was not reproduced in the fresh browser workspace.
  The selector-state bugs and missing selected-state feedback were independently reproduced
  and repaired. Do not relabel that as a proven backend save repair.
- Actual local Docker activation, authenticated production checks and a Named run using the
  owner's real roster remain NOT TESTED. The temporary browser fixtures were cleaned up as
  described above; their retained local evidence is not a deployed fix.

Specification: `../specs/2026-10-29-shared-queue-workflow-repair.md`.
Plan: `../plans/2026-10-29-shared-queue-workflow-repair-plan.md`.
Initial Chrome logs: `output/shared-queue-debug-20261029/chrome-*.log`.
Integrated artifacts: `output/shared-queue-workflow-20261029/`.

The existing `.claude/launch.json`, `.playwright-cli/`, output directories and earlier diagnostic
report remain preserved. No backend, schema, numerical model, API contract, saved operational
data, locale catalog or approved wording record is in the implementation edit scope.
