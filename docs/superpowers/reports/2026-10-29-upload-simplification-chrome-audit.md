# Upload-to-simulation simplification review — 2026-10-29

Status: source review COMPLETE; proposed product change NOT APPLIED.
Chrome supplied the initial source findings, then its turn failed at an account usage limit.
The primary agent completed the first review (sections "The three changes" to "Not inspected"
below). Chrome then ran a second, evidence-only pass on HEAD `0324ee4c` (revision 2, next
section). Revision 2 corrects the first review where noted; the first review is kept as history.

## Revision 2 — Chrome claim check (HEAD 0324ee4c)

Method: re-read every cited path at HEAD; ran the real parsing/ingestion/timeline functions
in-memory on the unchanged owner CSV and on in-memory variants (read-only scripts in the
session scratchpad, project `.venv`, nothing written to any database or file in the repo).
No browser walk of the live app was done in this pass (see "Not inspected").

### Claims in the three documents

| Claim | Label | Evidence / correction |
|---|---|---|
| CSV hash 236fc058…938e, 13 one-hour rows 05:00–18:00, c 2–5 | VERIFIED | recomputed; `time,lambda,mu,c`, CRLF |
| Non-XLSX planning files upload with applySetup false | VERIFIED | `AnalysisSetupPage.tsx:196` |
| Preview returns legacy for CSV | VERIFIED | `analyses.py:317-319`, `uploads.py:127-128`; probe printed `None` |
| apply_setup requires a workbook with an events sheet | VERIFIED | `analyses.py:273-274` |
| Workbook derivation produces separate_queues and approved unknown → unlimited/not_modeled defaults | VERIFIED | `setup_derivation.py:294-301`; 09-18 spec line 93. Line range corrected from 294–310 to 290–312 |
| Test "never previews a CSV upload" pins current behaviour | VERIFIED | `AnalysisSetupPage.test.tsx:170` |
| Template block precedes upload; manual entry is a closed disclosure | VERIFIED | `AnalysisSetupPage.tsx:252-293` |
| A saved fixed count that disagrees with CSV c rejects the upload | VERIFIED | `analysis_ingestion.py:181-188`; probe: fixed 5 and 3 both rejected |
| Full-day needs unlimited + not modeled + valid timeline + closing choice | VERIFIED | `shared_continuous.py:99-112, 270-328` |
| "Shared-queue users re-type … rates" (owner goal) | REPORTED, **corrected** | For a CSV the rates are read from the file; nothing asks for lambda/mu again. The repeated facts are the counter facts (required) and time segments (optional) |
| Derived Setup segments are needed for the full-day run | **Corrected → not needed** | The full-day timeline is built from dataset rows (`shared_continuous.py:130-136`). Setup segments drive display only: `AnalysesPage.tsx:28-34`, `RunBar.tsx:50`, `lib/replay.ts:15-26` |
| "Preserve … closing policy" as part of Setup | **Clarified** | The shared rule is `AnalysisProject.shared_closing_policy`, set by `PUT …/closing-policy`, not in the Setup fingerprint (`shared_continuous.py:421-432`) |
| Gaps/overlaps/bad clocks "are refused" | **Clarified** | Refused by the new path only. Today's legacy upload accepts a gap and a `5am` label (probe); the timeline check refuses both. The new path must decline and offer today's upload, not block it |
| Base HEAD e2dbe5d5 | **Updated** | Current HEAD 0324ee4c |
| Prototype at `output/upload-simplification-20261029/chrome-preview.html` | Kept as history | The new owner mockup is `output/upload-simplification/index.html` (new version only) |

### New findings

**F5 — The pre-upload banner asks for the one value that breaks this file.**
- Where: `/analyses/:id/data`, fresh shared analysis, any width/theme;
  `AnalysisSetupPage.tsx:219-227, 244-250`, `lib/setupStatus.ts:19`, `NewAnalysisPage.tsx:12-24`.
- Observed: the new Setup is `incomplete`, so the page shows "Your Setup is not complete." and
  "NovaQ still needs: Fixed server count …" with "Open Advanced settings", which focuses the
  `server-count` field. Entering any single count, then uploading the owner's file, returns
  "Aggregate c values must match the configured fixed server count." (probe).
- Label: VERIFIED (code + in-memory ingestion run). Effect on users: INFERRED.
- Why it matters: blocks reaching the first real result with the owner's own file.
- Suggestion: for a shared analysis without a planning file, do not list Fixed server count;
  after a read, list only real gaps (spec OD-5). Display only; server rule unchanged.
- Fit: consistent with U10 F4/F10 intent (name what is missing); changes which item is shown.
- Effort/risk: S, frontend display only.

**F6 — After upload the banner still names the wrong field.**
- Where: same page after the CSV upload; `analysis_schemas.py:292-303`, `workflow.py:1738,1830`.
- Observed: status stays `incomplete` (probe); the Decision lists "completed Setup"; the fix for
  this file is "Staffing varies by period" (→ `ready_for_aggregate`), but the banner says
  "Fixed server count". Saving a fixed count is not re-checked against the file
  (`analyses.py:128-149`), so a Setup can contradict the data.
- Label: VERIFIED code path; downstream effect of a contradicting fixed count: UNKNOWN.
- Why it matters: trusting the result enough to act; reaching Decision.
- Suggestion: derive the flag from the file (spec §6). Effort M (needs Step 1–2 backend).

**F7 — The workbook diff does not list counter breaks.**
- Where: `setup_derivation.py:41-45` (`DIFF_FIELDS`), candidate `290-312`.
- Observed: no `counter_breaks` in the diff list or the workbook candidate. A shared analysis
  applying an events workbook gets a `separate_queues` candidate (diff shows the structure
  change) and its counter breaks are not listed as changing.
- Label: VERIFIED in code; runtime NOT TESTED. Out of this proposal's scope (workbook path is
  unchanged); recorded for Hayato. The new endpoint's diff must include `counter_breaks`.
- Effort/risk: S to report; any fix touches protected derivation → separate spec.

### Counts (source-derived, not usability measurements)

Today 9 required inputs to a Decision-ready, full-day-eligible Setup for the owner's file
(8 on Data and Setup + closing rule); proposed 6. Visible controls before upload: 14 → 8.
Fields repeating the file: 5 → 0. Full table: spec §5.

## The three changes that matter

1. Let the shared-queue aggregate file supply its own periods and counter counts. The owner
   should not re-enter facts already present in time/lambda/mu/c.
2. Put upload and its read-back summary first. Move template downloads and manual entry
   into optional disclosures, and show the full setup editor only when requested.
3. Ask only for facts the file cannot establish. Reuse saved capacity, abandonment and
   closing choices; when unknown, ask explicitly. Keep employee-roster simulation optional.

The owner's idea is the source of this proposal: reuse the existing workbook apply pattern
for the supplied CSV and remove repeated input. No measured usability/conversion improvement
is claimed. A shorter path is a design expectation, not an experiment result.

## Evidence and scope

Branch: codex/shared-queue-workflow-20261029; base HEAD e2dbe5d57f859644849a5c445fceb099ff15bfa9.
Current repository source takes precedence over historical specs. The existing four-file
shared-queue repair is separate work and is preserved.

VERIFIED: an isolated browser session on the existing built app at
http://127.0.0.1:18766/analyses/1/data showed Get the Template first, Add your data second,
Review what NovaQ read third and Advanced settings fourth. The fixture had the owner's CSV
and explicit synthetic supported Setup choices. This was not the owner's authenticated live
analysis. Source inspection established the fresh-analysis behavior separately.

Input: Avg_total_data_of_14_days.csv, SHA-256
236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e.
It contains 13 one-hour rows, 05:00–18:00, with c ranging from 2 to 5.
Lambda and mu follow NovaQ's per-hour convention; c counts simultaneously staffed counters.
The file does not establish queue arrangement, capacity, abandonment, closing policy, named
employees, actual breaks, observation dates or the method used to produce the 14-day average.
No values are changed or re-averaged for this review.

## F1 — CSV does not receive the workbook's setup assistance

- Where: Data and Setup; frontend/src/pages/AnalysisSetupPage.tsx:190–211,
  backend/api/analyses.py:269–332 and backend/data/setup_derivation.py:290–312
  (ranges corrected in revision 2).
- Observed: non-XLSX planning files immediately upload with applySetup false. The existing
  preview returns legacy for CSV. apply_setup requires a workbook with an events sheet.
  The workbook derivation explicitly produces separate_queues and supplies approved defaults
  for missing capacity/abandonment in that workflow.
- Evidence: VERIFIED in source. The existing test named never previews a CSV upload pins
  the current behavior; it is not evidence that auto-setup already works for CSV.
- Effect: INFERRED extra effort and confusion when the CSV contains the periods and counts
  but Setup still asks for a fixed server count or a staffing-varies flag.
- Suggestion: an additive server preview/apply path for validated shared-queue aggregate
  files, retaining the chosen structure and deriving periods and staffing variation from c.
  Reuse the workbook's preview/diff/atomic-apply pattern, not its separate-queue defaults.
- Decision fit: advances memory.md's avoid-duplicate-input direction. Extends the owner’s
  2026-09-18 workbook rule; deliberately changes that specification's CSV-is-legacy boundary
  only for the new opt-in path. Old API behavior stays available.
- Effort/risk: M; backend and frontend behavior, persisted Setup and evidence invalidation.
  Requires the bounded specification/plan; no queueing math change is proposed.

## F2 — Optional preparation precedes the action for an already prepared file

- Where: Data and Setup; AnalysisSetupPage.tsx:254–295,
  components/analysis/SetupDataTemplates.tsx:57–115.
- Observed: template schema buttons, two download buttons and the guide come before upload.
  Manual entry is already a closed disclosure. The numbered read section can show Nothing
  to review yet before a file exists.
- Evidence: VERIFIED in source and the isolated desktop browser. The owner REPORTED too
  many unnecessary steps. No user timing or click-rate data were collected.
- Effect: INFERRED visual work before reaching the owner’s intended action, uploading an
  existing file. Downloads are useful alternatives, not requirements to upload.
- Suggestion: upload first; place templates and manual entry below as optional disclosures.
  Put the summary beside/below that upload when it exists, without an empty numbered step.
- Decision fit: revises the template-first presentation in compact-workflow spec §7.6,
  preserving template support, explicit file purpose and review-only isolation (D16/B10).
- Effort/risk: S for layout; M when connected to the new apply flow. Reuse approved labels.

## F3 — The setup editor exposes event and manual-period controls for aggregate input

- Where: AnalysisSetupPage.tsx:329–355; lib/setupStatus.ts:16–23;
  backend/data/analysis_ingestion.py:177–187.
- Observed: the same form includes customer-event period basis, fixed server count,
  staffing-varies checkbox and manual segments. The help itself says period basis is for
  customer-event uploads. A saved fixed count that disagrees with CSV c can reject the
  upload before a proposed after-upload frontend auto-fill could run.
- Evidence: VERIFIED in source. Event basis and named employee availability are not
  derivable from this CSV.
- Effect: INFERRED repeated typing and an avoidable setup/upload dependency loop.
- Suggestion: show uploaded periods/counts read-only; keep edits in Advanced settings.
  Show event-period controls only for customer-event workflows. Preview the candidate Setup
  on the server before saving; do not add a second CSV parser in the React page.
- Decision fit: preserves central validation, source provenance and protected model choice.
  Does not add mixed-duration aggregate totals or overnight support.
- Effort/risk: M. Confirmation is required before replacing conflicting saved facts.

## F4 — Hiding real model choices would turn simplification into an assumption

- Where: backend/api/shared_continuous.py:101–114, 279–327;
  frontend/src/components/queueSimulation/ContinuousRun.tsx;
  frontend/src/pages/QueueSimulationPage.tsx (named mode).
- Observed: full-day compatibility requires unlimited capacity, abandonment not modeled,
  a valid supported timeline and a closing choice. Named mode has roster-specific inputs.
- Evidence: VERIFIED in source; execution of supported and refusal paths is recorded in
  the separate shared-queue backend follow-up report. This audit did not rerun those tests.
- Effect: INFERRED confusion if named employee mode appears to be a prerequisite for a
  normal full-day run, or if missing choices are silently converted to supported defaults.
- Suggestion: keep standard Full-day run as the main path. Retain named mode under its
  optional route. Ask capacity/abandonment only when missing, with conditional numeric
  fields for finite capacity/modeled abandonment. Keep the existing explicit closing chooser
  on simulation; display saved choices without re-entry. Preserve unsupported-mode messages.
- Decision fit: preserves D25, B4a scope, B10, frozen analytical behavior and named contracts.
- Effort/risk: S for hierarchy; supporting finite capacity or abandonment in full-day DES is
  a separate mathematical feature and is outside this proposal.

## Concrete review material

- output/upload-simplification-20261029/chrome-preview.html: self-contained interactive
  before/proposed comparison using the exact CSV data and existing EN/TL labels.
- docs/superpowers/specs/2026-10-29-shared-queue-upload-simplification.md.
- docs/superpowers/plans/2026-10-29-shared-queue-upload-simplification-plan.md.

The HTML is a design prototype. Apply/Run demonstrations do not upload data, change Setup,
create plans or execute a simulation. Synthetic saved-setup examples are explicitly marked.
Prototype browser verification and artifact checks are recorded in verification.json.

## Verification actually performed

- PASS: build_preview.py checked the exact CSV hash, 13 expected hourly labels, exact c
  sequence and presence of every reused product label in both locale catalogs.
- PASS: verify_artifacts.py compared all 13 embedded CSV rows verbatim, checked 36 existing
  EN/TL keys, found no backend/network request code in the prototype, verified the earlier
  four repair file hashes unchanged, and ran git diff --check (exit 0).
- Browser observations: explicit purpose initially unselected; missing choices disabled
  apply; valid choices enabled it; saved replacement required confirmation; switching
  purpose cleared confirmation; review hid Setup and simulation and stated that planning
  data stays unchanged; synthetic finite capacity 20 stayed finite and blocked the run demo.
  The run demo asked for a closing choice and explicitly said no simulation had run.
- At 375 pixels, EN/dark and TL/light labels were inspected; document scroll width was
  360, with no fact-card overflow. The exact CSV table was expanded and read back. At 768
  pixels, TL/light document scroll width was 753. Desktop EN initial/replacement/review
  states were inspected. Browser console warnings/errors: none returned.
- Two prototype layout defects found during this check were corrected: the phone language
  selector clipped its selected text, and the clock range needed its own fact-card row.
  A prototype review-success note was also corrected to explicitly preserve Setup; purpose
  changes now discard replacement confirmation. These are prototype-only changes.
- Screenshots were viewed inline through CUA. The used screenshot API returned no exported
  local screenshot path, so no saved browser-image artifact is claimed. The self-contained
  HTML is the deliverable. The temporary viewport was reset; the isolated app tab/server
  were closed/stopped. The loopback-only static prototype server on port 18767 was retained
  for review; no application or production service was activated.
- Full backend/frontend application gates: NOT RERUN because this phase changed only design
  artifacts and documentation. This is not verification of the proposed product behavior.

## Not inspected / unresolved

- The owner's authenticated live upload session, actual saved Setup and deployed parity:
  UNKNOWN. The inspected browser app used a disposable SQLite fixture.
- Real employee availability and breaks, queue/capacity/abandonment choices and the raw
  observations behind the average CSV: UNKNOWN.
- Full application behavior for this proposed flow: NOT TESTED because no application
  implementation has been made. Existing tests are not relabeled as tests of the proposal.
- No application source, locale, protected wording record, API, schema, mathematics, Docker,
  production setting, commit, stage or push was changed in this review.

Status: COMPLETE for the requested review and concrete proposal; automatic CSV Setup and
the simplified live UI remain PROPOSED.

## Revision 2 — mockup and verification (Chrome)

Mockup: `output/upload-simplification/index.html` (SHA-256 `ac38d354…cbb04a`, 57,744 bytes,
self-contained, no network). New version only: upload → read-back summary → missing
choices → save, with numbered badges 1–5 and a "What changed" list per stage. EN/TL and
light/dark switches; the real `frontend/src/styles/theme.css` is embedded verbatim. Product
text uses 66 existing locale keys (present in EN and TL, checked at build); 11 new strings are
drafts D1–D11 (EN + TL) marked "Draft — awaiting owner approval". The owner delegated
drafting; none of it is approved. Values come verbatim from the owner CSV (hash asserted
at build); min–max are file values, not calculations. No waits, costs or utilization shown.
Illustrative cases (saved-Setup conflict, unreadable file, outside quick setup) are labelled
and use real server message text from the probes. Address parameters jump to a state:
`?step=read|saved|confirm|review&lang=tl&theme=dark&case=conflict`.

Screenshots in the same folder: `375-en-light-1-upload`, `375-en-light-2-read`,
`375-tl-dark-3-saved`, `375-en-light-4-conflict-confirm`, `375-tl-light-5-review-only`,
`1280-en-light-2-read`, `1280-tl-dark-3-saved` (PNG, full page, DevTools emulation), and
`375-en-dark-missing-choices.jpg` (browser pane, earlier build; that section is unchanged).

Executed checks (mockup only; not application tests):
- Static parse: doctype, balanced tags, unique ids, one inline script, no external URLs: PASS.
- jsdom (`frontend/node_modules/jsdom`): 40/40 PASS. These cover script errors, every key
  resolving in EN and TL, symmetric key sets, the 13 table rows equal to the CSV rows, the
  strip equal to the c sequence, no preselected purpose, apply gating, finite/modeled number
  gating, "not sure", the confirm and cancel paths, review-only, switching purpose or file,
  invalid/outside cases, TL dynamic text, and a label on every input.
- Browser pane at 375 px: EN/TL × light/dark × start/all-open/saved, plus the conflict,
  invalid and outside cases. 15 states, scroll width 375 in every one, with no element
  past the edge (body overflow mask removed before measuring). No control shorter than 36 px.
- DevTools emulation (headless Chrome, throwaway profile in the session scratchpad):
  7 states at 375 and 1280, horizontalScroll false in all. A first attempt with a plain
  headless window was discarded because Windows enforces about 500 px minimum width.
- The pane viewport was reset to desktop, the tab closed and the loopback server stopped.

Not inspected / limits: the live app was not walked in this pass (no running stack started).
Real touch, screen readers and a Tagalog reader's review were NOT TESTED. Inter font is not
embedded (system fallback). Application gates were not run because no app code changed.

Status (revision 2): COMPLETE for the corrected proposal and mockup; implementation
PROPOSED and awaiting owner decisions OD-1…OD-8 (spec §10).
