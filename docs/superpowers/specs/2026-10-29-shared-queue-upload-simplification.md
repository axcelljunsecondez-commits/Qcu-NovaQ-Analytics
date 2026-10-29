# Shared-queue upload simplification — specification

Date: 2026-10-29 (revision 2, Chrome evidence pass on HEAD `0324ee4c`).
Status: APPROVED SPECIFICATION (owner, 2026-10-29), NOT IMPLEMENTED. The owner reviewed
the mockup and decided OD-1 to OD-8 in chat: "all recommendations" (§10). Drafted wording
remains "Draft — awaiting owner approval" until the owner's wording review.

Related: [audit](../reports/2026-10-29-upload-simplification-chrome-audit.md),
[plan](../plans/2026-10-29-shared-queue-upload-simplification-plan.md),
mockup `output/upload-simplification/index.html` (new version only, owner's real CSV).

## 1. Owner request (credit)

The owner asked (REPORTED): reuse the workbook's apply-from-file behaviour for the supplied
aggregate CSV, stop asking for facts the file already has, and reduce what Data and Setup
shows at once — "I removed the not needed, it's so overwhelming to user". The flow the owner
wants: upload first, NovaQ reads the file, the user confirms one summary, NovaQ asks only for
what the file cannot tell. Decisions marked **(owner)** below come from that request.

## 2. What happens today (verified)

Acceptance input: `Avg_total_data_of_14_days.csv` in `Daily data mmc/`, SHA-256
`236fc05861b4a59ce3216c41fb52b3c529aec6b6f57003f610bd4cc3a91f938e` (VERIFIED, recomputed
2026-10-29). Columns `time,lambda,mu,c`; 13 one-hour rows 05:00-06:00 … 17:00-18:00;
c = 3,5,5,5,5,5,2,3,5,5,5,5,2; lambda 5.0000–12.7857 customers/hour; mu 4.3068–5.3242
customers/hour per counter. Units per NovaQ convention; the method used to produce the
"14-day average" is UNKNOWN.

Facts below were VERIFIED by reading source and by running the real ingestion functions
in-memory on the unchanged file (read-only probe, nothing written; §9 of the audit).

| # | Behaviour | Evidence |
|---|---|---|
| T1 | A new shared analysis is created with `fixed_server_count: null`, `staffing_varies_by_period: false`, capacity and abandonment `unknown`, no segments. | `frontend/src/pages/NewAnalysisPage.tsx:12-24` |
| T2 | That Setup's status is `incomplete` before any upload, so Data and Setup shows "Your Setup is not complete. NovaQ still needs: Fixed server count" with a button that focuses the fixed-count field. | `backend/api/analysis_schemas.py:292-303`; `AnalysisSetupPage.tsx:219-227, 244-250`; `lib/setupStatus.ts:19` |
| T3 | If the user follows that prompt and types any single count before uploading, the owner's CSV is **rejected**: "Aggregate c values must match the configured fixed server count." (probe: 5 and 3 both rejected). | `backend/data/analysis_ingestion.py:181-188`; probe |
| T4 | With the Setup left as created, the CSV uploads (13 records, provenance `user_provided`) with no preview: any non-`.xlsx` planning file goes straight to `POST …/datasets` with `apply_setup` false. | `AnalysisSetupPage.tsx:196`; probe |
| T5 | The read-back card ("Here's what NovaQ read from your file") is filled only by the workbook preview; for a CSV the preview endpoint returns `{"mode": "legacy"}` and the page shows nothing about periods or counters. | `AnalysisSetupPage.tsx:200, 296-312`; `backend/api/analyses.py:317-319`; `backend/data/uploads.py:127-128` |
| T6 | After the upload the Setup is still `incomplete` (fixed count missing). The Decision lists "completed Setup" as missing until it is `ready` or `ready_for_aggregate`. The right fix for this file is to tick "Staffing varies by period", but the banner names "Fixed server count". | `backend/api/workflow.py:1738, 1830`; probe (`varies=true` → `ready_for_aggregate`) |
| T7 | Saving the Setup does not re-check it against the current file, so a fixed count that contradicts the file's c can be saved. | `backend/api/analyses.py:128-149` |
| T8 | The full-day run refuses while capacity or abandonment is `unknown` and tells the user to go back to Data and Setup → Advanced and set them (a round trip). | `backend/api/shared_continuous.py:99-112`; `ContinuousRun.tsx:186-193`; locale `continuous.reason.capacity_or_abandonment_unknown` |
| T9 | The full-day timeline comes from the dataset rows, not from `QueueSetup.segments`; the owner's file passes it (13 periods, 05:00–18:00, c sequence unchanged). Setup segments are used for display: My analyses operating window, the period-run bar's operating hours and the replay clock origin. | `shared_continuous.py:130-136`; `AnalysesPage.tsx:28-34`; `lib/replay.ts:15-26`; `RunBar.tsx:50`; probe |
| T10 | The legacy aggregate upload does not check the time labels: a file with a gap or a label such as `5am` is accepted, and is refused only later by the full-day timeline check. A non-integer c is rejected at upload. | probe (gap, `5am`, `c=2.5`) |
| T11 | Rates are read from the file; the CSV path never asks the user to retype lambda or mu. Only Manual entry (an alternative to a file) types them. | `AnalysisSetupPage.tsx:293`; `ManualEntry.tsx` |
| T12 | The shared closing rule is stored on the analysis (`shared_closing_policy`), set by `PUT …/closing-policy`, and is not part of the Setup fingerprint. It is chosen on the simulation page. | `backend/api/shared_continuous.py:421-432`; `backend/db/models.py:134` |
| T13 | The workbook preview/apply derives `separate_queues`, and when capacity/abandonment are unknown it applies `unlimited`/`not_modeled` (09-18 approved rule). Its diff list has no `counter_breaks` entry. | `backend/data/setup_derivation.py:41-45, 290-312`; 09-18 spec line 93 |

So the repeated or misdirected input for this file is the counter facts (fixed count /
staffing-varies), optionally the time segments (Make periods), and the two model questions
answered only after a refusal. Rates are not retyped (T11) — correct the earlier wording
that said they were.

## 3. Target outcome

After choosing a planning CSV, NovaQ reads it on the server, shows the file's own facts in
one summary, asks only for the choices the file cannot establish, and saves the file and the
derived Setup together with one action. No manual entry of time segments, fixed c or the
staffing-varies flag. Choices already saved are reused, shown, and editable.

## 4. Field-by-field map of Data and Setup (shared queue)

"CSV" = established by the owner's 4-column file. Counts are of controls in source today.

| Control today | Where | CSV provides? | Still needed from user? | Proposal |
|---|---|---|---|---|
| Setup-incomplete banner + "Open Advanced settings" | page top, before upload | — | No, for shared aggregate the count comes from the file | Do not list Fixed server count while a shared analysis has no planning file; after a read, list only real gaps (OD-5) |
| Template: Totals and Rates / Customer Events, Download CSV, Download XLSX, View Example (5) | Step 1 | — | Optional | Disclosure **below** upload, existing title `template.prepare_title` |
| File purpose: planning / review (2 radios) | Step 2 | No | Yes (D16/B10) | Keep, first, nothing preselected |
| File input | Step 2 | — | Yes | Keep |
| "Upload and process" button | Step 2 | — | Planning: no (read is read-only); review: yes | Planning reads on choose; review keeps the button (OD-3) |
| Manual entry (disclosure) | Step 2 | — | Optional | Keep, below upload; its output takes the same read path |
| Review what NovaQ read | Step 3 | — | — | Filled for CSV from the new preview (§6) |
| Queue structure (read-only) | Advanced | No — 4 columns do not prove it | Already chosen at creation | Show read-only in the summary |
| Customer data periods (period basis) + help | Advanced | Not used by aggregate files | No | Hide when the planning file is aggregate; keep for event files (OD-8) |
| Counter breaks editor | Advanced | No | Optional | Keep in Advanced; saved breaks are checked against the file's hours in the preview |
| Fixed server count | Advanced | Yes (c) | No | Derived: constant c → that value; varying c → null |
| Staffing varies by period | Advanced | Yes (distinct c) | No | Derived |
| Time segments, Make periods (3 inputs + button), Add segment | Advanced | Yes (time) | No | Derived from validated rows; editable in Advanced |
| Capacity mode (+ total customers) | Advanced | No (no K column) | Yes, if unknown | Ask inline with the existing plain question (OD-1, OD-2) |
| Abandonment (+ patience rate) | Advanced | No (no theta column) | Yes, if unknown | Ask inline with the existing plain question (OD-1, OD-2) |
| Save | Advanced | — | — | One primary apply action in the main flow; Advanced keeps its own Save |
| Closing rule | Simulation page | No | Yes, before a full-day run | Optionally asked in the same card (OD-4); stays editable on the simulation page |

## 5. Steps and inputs for the owner's CSV (counts only)

New shared analysis already created. Counted from source; no timing or usability data exist,
so no usability claim is made. "Input" = one user choice or click that changes state.

| Path | Today | Proposed |
|---|---|---|
| Numbered sections on Data and Setup | 4 (template, add data, review, advanced) | 3 stages (upload, check, answer and save); templates, manual entry, Advanced are disclosures |
| Interactive controls visible before upload (Advanced closed) | 14 (header help, banner button, 5 template, purpose help + 2 radios, file, process, manual, Advanced) | 8 (header help, purpose help + 2 radios, file, 2 disclosures, Advanced) — 9 when Review only is chosen and its button appears |
| Required inputs to a Decision-ready Setup and a full-day-eligible run | 8 on Data and Setup: purpose, file, process, open Advanced, tick staffing varies, capacity, abandonment, Save — plus 1 closing choice on the simulation page = **9** | purpose, file, capacity, abandonment, Save = 5, plus 1 closing choice (here or on the simulation page) = **6** |
| Same, when capacity/abandonment are already saved | purpose, file, process, open Advanced, tick, Save + closing = 7 | purpose, file, Save + closing = 4 |
| Same, when a fixed count was saved first (T3) | at least: purpose, file, process (refused), open Advanced, tick staffing varies, capacity, abandonment, Save, process again = 9, plus closing = 10 | purpose, file, capacity, abandonment, Save, confirm replacement + closing = 7 |
| Optional retyping to show operating hours (Make periods) | 3 inputs + 1 button + Save | 0 (derived) |
| Fields that repeat what the file says | fixed count, staffing flag, segment start/count/length (5) | 0 |

## 6. Proposed flow

1. **Upload first.** Purpose question (unchanged, nothing preselected), then file. Template
   and Manual entry are disclosures below. **(owner)**
2. **Read, store nothing.** For a planning CSV/XLSX that matches the first slice (§7), choosing
   the file calls the new read-only preview. Pending: existing `common.loading`. Choosing
   another file or purpose discards the pending preview and ignores a late response.
3. **One summary of uploaded facts** (existing title `analyses.upload_read_title`): file name
   and row count; operating hours from the validated bounds; segment count; counters open
   (min–max and "varies by period" yes/no); arrival and service rate ranges as written in the
   file; an expandable per-hour table using the Manual-entry column labels; queue structure
   marked as coming from the analysis, not the file. Labelled as file contents, not results.
   **(owner)**
4. **Only the missing choices.** Capacity and abandonment only when `unknown`; each answer
   shows the exact Setup value it saves. "I'm not sure" keeps `unknown` and says the full-day
   run stays unavailable. Finite/modeled answers require their number (total customers /
   patience rate) and show the existing "not in the full-day run yet" note. Saved choices are
   shown as facts with a Change link to Advanced. Never select unlimited/not modeled on the
   user's behalf (OD-1). Optional closing rule here (OD-4).
5. **One apply.** One primary button saves Dataset + Setup atomically. If the saved Setup
   differs from the candidate, the existing confirmation (`analyses.upload_confirm_title`,
   `…_help`, `…_confirm`, `common.cancel`) lists saved → proposed values; Cancel writes nothing.
   Double-submit guarded; one dataset per confirmed apply.
6. **Done.** Success note, then links to Analysis results and the Full-day run. The summary
   stays visible; Advanced settings shows the saved values for editing.
7. **Review only** uploads as today (explicit button), never derives or changes Setup, never
   shows replacement UI (B10).

## 7. Scope, cases and what stays unchanged

First slice: an analysis already `shared_queue`; planning purpose; aggregate `time, lambda, mu,
c` only; contiguous, same-day, one-hour `HH:MM-HH:MM` rows. Reason for one hour: shared
aggregate rows of unequal length are not duration-weighted in costs/totals (REPORTED in
handoff U4 task 4.6; protected math, not changed here).

| Case | Proposed behaviour |
|---|---|
| Valid, varying c (owner file) | 13 segments `05:00-06:00` … `17:00-18:00`, `staffing_varies_by_period` true, `fixed_server_count` null; per-hour c stays in dataset records only |
| Valid, constant c | `fixed_server_count` = that c, varies false |
| Unreadable file (missing column, malformed rate, non-integer c, size/limit) | Existing upload/ingestion messages under the upload, `analyses.upload_read_errors`; nothing saved. Server messages are English only today (VERIFIED literals) — TL shows English detail (UNKNOWN whether acceptable; OD-6) |
| Readable but outside the slice (gap, overlap, overnight, bad label such as `5am`, non-hour rows, K/theta/variance columns) | Preview declines with a reason and offers today's upload unchanged (T10: legacy accepts some of these). Supplied K/theta/variance are never dropped and never silently re-modelled |
| Saved fixed count differs | Not an upload error any more on this path: preview shows saved → proposed; apply needs confirmation (today T3 rejects) |
| Saved segments differ | Diff + confirmation |
| Saved counter breaks outside the file's hours or exceeding counters | Shown as a conflict before apply using the existing break rules (`breaks_outside_hours`, `breaks_not_staffed`); never erased |
| Saved finite capacity / modeled abandonment | Kept and shown; the existing note says full-day does not include them |
| Switching purpose, file or analysis | Clear preview, answers and confirmation; ignore stale responses |
| Saved Setup changed in another tab before apply | Apply refuses on revision mismatch; user re-reads |
| Review-only file | Unchanged from today |

Unchanged: the workbook preview/apply path and its 09-18 defaults; separate queues;
`POST …/datasets` (legacy CSV) and `…/datasets/preview` request/response shapes; model
selection; ingestion validation; engine, DES, MC and optimizer; Named mode; closing-rule
storage; staleness and current-dataset rules.

## 8. Backend boundary (Hayato)

Additive endpoint pair (names illustrative, final in the plan): read-only preview and atomic
apply for the shared aggregate slice.

- Preview returns: file facts (name, rows, bounds, per-row time/lambda/mu/c as validated),
  candidate Setup, saved Setup, saved → candidate diff **including `counter_breaks`**, unresolved
  choices, conflict reasons, a saved-Setup revision/digest and a file digest. No writes.
- Apply re-reads the submitted file, re-validates with the same functions, checks the revision
  and replacement intent, rejects review purpose, and commits Dataset + Setup in one
  transaction with today's owner/archive/limit/CSRF/staleness rules. Never trust
  browser-derived values.
- Reuse: `uploads.parse_upload`/`sanitize_workbook`, `normalize_analysis_input` (protected
  ingestion validation), `timeline_from_aggregate_rows` + `validate_timeline` (VERIFIED to
  reject gaps and bad labels), `setup_diff` pattern. Do not reuse the workbook candidate
  (it derives `separate_queues`). Additional storage/provenance fields need review first.

## 9. Compatibility with earlier decisions

- Extends the 09-18 "no fact entered twice" and preview/confirm/apply pattern to a new opt-in
  shared path. Deliberately **differs** from its unknown → unlimited/not modeled default (OD-1).
- Revises the template-first order of compact-workflow §7.6 steps 1–3; templates stay.
- Consistent with §7.6 step 5 (closing choice on Data and Setup) if OD-4 = ask here; D25 kept
  (no preselection, saved per analysis, future runs only).
- Preserves D16/B10, B4a full-day scope, immutable evidence, central model selection, units.
- Wording: reuse existing EN/TL keys; new text only as owner-approved drafts (OD-6); do not
  touch `docs/wording/` or `wordingPolicy.test.ts`.

## 10. Owner decisions

DECIDED 2026-10-29 by the owner in chat, after viewing `output/upload-simplification/index.html`:
"all recommendations". Every row below is decided as its Recommendation column. For OD-2 this
includes "No known limit" → Unlimited. For OD-6 the drafts are accepted as drafts and stay
subject to the owner's later wording review; English-only server error details in TL are
accepted for this slice.

| ID | Question | Recommendation (DECIDED) |
|---|---|---|
| OD-1 | Unknown capacity/abandonment on this path: ask, or apply the 09-18 workbook default (unlimited / not modeled) with a visible Change? | Ask. Two taps; the file has no evidence either way; keeps "unknown is never read as absent" (T8) |
| OD-2 | Reuse the existing, currently unused plain questions `setup.capacity*` / `setup.abandonment*` (from the removed onboarding wizard) with mapping: No known limit → Unlimited; Yes, there is a limit → Finite + number; I'm not sure → Unknown; No, customers wait → Not modeled; Yes, customers leave → Modeled + rate; I don't know → Unknown | Approve, but confirm "No known limit" is acceptable for Unlimited |
| OD-3 | Read a planning file as soon as it is chosen (no "Upload and process" click)? | Yes for planning (read-only); keep the explicit button for review-only, because that upload writes |
| OD-4 | Ask the closing rule in the same card, with "Decide later"? | Yes: it is required before the first full-day run and §7.6 step 5 already placed it here; saved via the existing endpoint only after apply succeeds |
| OD-5 | Hide "Fixed server count" from the pre-upload banner for shared analyses with no planning file? | Yes: following it makes the owner's file fail (T3) |
| OD-6 | Approve or replace the draft EN/TL strings (mockup "Draft wording" table), and accept English-only server error details in TL | Approve drafts after review by a Tagalog reader; server-message translation is a separate task |
| OD-7 | First slice limited to one-hour contiguous rows? | Yes (unequal rows are not duration-weighted) |
| OD-8 | Hide "Customer data periods" in Advanced while the planning file is aggregate? | Yes; it has no effect on aggregate files |

## 11. Acceptance checks

- Owner CSV (hash above, unchanged): 13 hourly segments 05:00–18:00, c sequence unchanged,
  varies true, fixed null; expected rows read independently from the file in the test.
- Constant-c fixture → fixed count. Gap, overlap, overnight, `5am`, non-hour, non-integer c,
  malformed rate → declined or refused with reasons, no writes, no generated demand.
- Saved fixed count, segments, counter breaks: preview shows diff/conflict; apply needs the
  saved revision and intent; Cancel/stale revision leaves Dataset and Setup unchanged.
- Known finite/modeled settings kept; unknown stays unknown until answered; K/theta/variance
  never dropped or silently re-modelled.
- Workbook, legacy CSV, review-only, named, ownership, archive, limits, CSRF and staleness
  regressions pass unchanged.
- UI at 375/768/desktop, both themes and languages: no page overflow; labels, errors,
  pending state, focus and keyboard work; only file-missing facts require entry.
- Full-day run works on the saved planning dataset when supported; unsupported capacity /
  abandonment stays refused. The preview never runs a simulation.
