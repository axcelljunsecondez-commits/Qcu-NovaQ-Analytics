# Current separate-lines DES on a per-date file uses every date (C-PD)

Status: **APPROVED 2026-11-02 (owner): OD-C1 = (a), OD-C2 = (i), OD-C3 = (i), OD-C4 = (i), OD-C5 = (i). OD-C6 (wording) open.** Backend implementation (plan Path A, A1-A5) authorized; frontend step A6 waits for OD-C6 and the chart-redesign merge. No commit or push without owner approval. Protected work under AGENTS.md §5 (discrete-event simulation behaviour) and §6 (data integrity).

Base: `main` at `3ee8fe2c`. Worktree `confident-cori-664a54`, branch `claude/confident-cori-664a54`. The defect predates `feat/ulit-chart-redesign` (`f8bcc380`); that branch does not touch the Current endpoints (VERIFIED: `git diff main...feat/ulit-chart-redesign -- backend/api/workflow.py` changes `run_mc` and `run_selected_mc` only). The frontend part of option (a) touches `ReplayView.tsx` and `simulationContext.ts`, which that branch also changes (section 7.4).

## 1. Problem (VERIFIED)

On a separate-lines analysis with `event_period_basis = per_date` and a customer-record file covering more than one date, **Run Current** (`POST /analyses/{id}/workflow/simulation/des/current`) simulates the records of one date, or a mix of dates, and stores the result as `provenance: "CURRENT"`. The other dates' records are dropped without a message. This breaks AGENTS.md §6: observations are dropped without notice, and a "day" is built from several dates.

How it happens:

1. Ingestion keeps one record per **date × segment × lane**, with the dated label `"<YYYY-MM-DD> <segment> UTC"` in `time`. It stamps the **Setup segment id**, the same on every date, in `segment_id` (`backend/data/analysis_ingestion.py:70-115`, `_assign_event_segments`, line 109).
2. `_current_segments_for` (`backend/api/workflow.py:662-688`) passes every stored record to the engine and does not group or filter by date.
3. `_parallel_schedule` (`backend/queueing_engine/simulation/simulation.py:664-735`) builds one schedule from the Setup segments. For each (segment, lane) it takes the **first** record whose `segment_id` and `queue_id` match, through `next(...)` (lines 689-695). Every other date's record for that pair is ignored. If date 1 has no record for a pair, the first match comes from a later date.

The first-match lookup was added in `79bce385` (2026-09-16, "feat: add separate queue DES execution"; VERIFIED with `git log -S`). The explicit per-date basis was added in `478b301e` (2026-09-18).

## 2. Evidence

### 2.1 Failing tests (VERIFIED, run 2026-10-30)

New file `tests/test_current_separate_per_date.py` (SYNTHETIC data: two dates, two hourly segments, lanes `a` and `b`; date 2 has 10 customers on lane `a` in `s1`). The tests accept either outcome a fix could give: every date's records are simulated, or the run is refused with a stated reason. They fail only on a partial or mixed-date result.

`python -m pytest tests/test_current_separate_per_date.py -q` on `3ee8fe2c`: **3 failed, 3 passed**.

| Test | Result | What it shows |
|---|---|---|
| `test_ingestion_repeats_the_setup_segment_id_on_every_date` | PASS | The precondition: 8 records, segment ids `{s1, s2}`, 4 dated labels. |
| `test_current_des_uses_every_date_or_refuses` | **FAIL** | The 4 records of 2026-08-04 are missing from the result (date 2's λ = 10 is never simulated). |
| `test_current_des_never_builds_one_day_from_several_dates` | **FAIL** | With date 1's `s2/b` removed, the result holds three date-1 rows and `2026-08-04 s2 UTC / b`, so the "day" mixes the two dates. |
| `test_current_des_route_uses_every_date_or_refuses` | **FAIL** | Through the public routes (create, upload, run): HTTP 200 with date-1 rows only. |
| `test_current_monte_carlo_evaluates_every_date_record` | PASS | Current Many variations covers all 8 records; date 2 lane `a` has λ = 10. |
| `test_current_validation_route_covers_every_date` | PASS | Current validation requires and reports all 8 date × segment × lane pairs. |

Kyoya's probes (`…/scratchpad/kyoya2/perdate_probe.py`, `perdate_probe2.py`, outputs `*.out`) show the same two symptoms with the same synthetic events.

### 2.2 Owner's file (VERIFIED in memory; nothing copied into the repo)

`C:\Users\Administrator\Desktop\NOVAQ_FILES ONLY\NOVAMART_DATA_UPLOAD.xlsx`: 1,600 events, 14 dates (2000-01-03 to 2000-01-16), 5 lanes. Read in a scratch process with NovaQ's own functions:

- **Apply Setup path is not exposed.** `derive_setup` on the workbook gives `event_period_basis = representative_day`, 13 segments, 60 pooled records (`backend/data/setup_derivation.py:309-313`: a file with more than one date derives Representative day).
- **Per-date path is exposed.** With the derived Setup and only the basis changed to `per_date`, ingestion gives **774 records**. `_parallel_schedule` uses **60 of them (714 dropped, 92%)**: 57 from 2000-01-03, 2 from 2000-01-04, 1 from 2000-01-06, plus 5 zero-rate fillers for lanes that are closed. The simulated "day" is built from three dates.
- **UNKNOWN:** whether any stored analysis, local or production, holds a multi-date per-date separate-lines Current DES run. This session did not read any database.

A per-date multi-date upload happens when the file is uploaded as a dataset against a saved per-date Setup (the schema default is `per_date`, `backend/api/analysis_schemas.py:134`), without applying the derived Setup, or after the basis is changed back to per date.

## 3. Reach (step 3 of the task)

| Path | Affected? | Evidence |
|---|---|---|
| Current DES (`des/current`) | **Yes** | Section 2.1. |
| Current Many variations (`mc/current`) | No | `mc_simulate_segments` evaluates each record on its own and keeps its dated `time` label (`simulation.py:1354-1377`). Test PASS. |
| Current validation (`validation/current`) | No | Required pairs come from `analyze_segments` over the same records. The verdict reads the Current MC rows keyed by (dated label, lane) (`workflow.py:1597-1613`). Test PASS. It does not read Current DES. |
| Suggested-plan checks on per-date plans | No | B13 groups periods by date with `per_date_days` and runs each date as its own day (`separate_optimization.py:1710-1734`, `workflow.py:2846-2990`). |
| Decision, reports | No | No backend reader of `workflow_des_current` other than `workflow.py` and `evidence_status.py` (VERIFIED by grep). |
| Queue simulation page | **Yes, as a reader** | `currentRun()` feeds the Key results "Current" card, Replay and the run bar (`frontend/src/components/queueSimulation/*`). The Current card is compared with a Suggested per-date run that covers every date. |
| Representative day; single-date per-date | No (INFERRED) | One record per (segment, lane), so the first match is the only match. |
| Per-date without operating segments | No | Already refused: "Parallel M/G/1 DES requires structured QueueSetup.segments." (`simulation.py:676`). |

Out of scope, noted for a separate check: shared-lines Current DES on a per-date file runs every record in sequence and carries the final queue of a date's last period into the next date's first period (`_simulate_segments_core`, `simulation.py:939-985`, `carryover=True`). INFERRED from code; NOT TESTED.

## 4. Options

### (a) Simulate each date as its own day

Group the records by date, as B13 does for plans, and run today's Current engine (`_simulate_parallel_segments_core`: dedicated lanes, one Poisson stream per lane at its recorded λ, empirical service resampling, `drain_existing`) once per date. Each date starts empty, with its own seed (`date_seed(seed, i)`). The result keeps every date's rows and adds a per-date list.

### (b) Refuse per-date separate Current with a stated reason

When the records for one (segment, lane) come from more than one date, the engine returns its usual unsupported result (`_parallel_capability_error`) with a reason that names the basis and the way out, for example: "Current simulation of separate lines needs one record per segment and lane. This file has N dates on the One period per calendar date basis. Use Representative day, or upload one date." Current Many variations and Current validation stay available.

### Comparison

| | (a) each date | (b) refuse |
|---|---|---|
| §6: every observation used or refused openly | Yes, all dates used | Yes, refused openly |
| User gets a Current simulation | Yes | No, for multi-date per-date files |
| Matches the Suggested per-date run (B13) | Yes: same day-per-date, same seeds | No Current card to compare |
| Engine semantics | Unchanged per day; adds a loop over dates | Unchanged; adds a refusal |
| Open lane with no record on a date | **Needs a rule (OD-C2).** On the owner's file all 14 dates have one (66 of 840 open lane-hours). | Not reached |
| API shape | Additive (`days`, `execution`, event `date`) | Unchanged (existing unsupported-row shape) |
| Frontend | Date picker for Current Key results and Replay (reuse B13's `DatePicker`/`dayPeriods`); new en+tl strings | One new reason string (en+tl) |
| Size | Medium: engine loop, result merge, trace, frontend, tests | Small |
| Free-tier cost | Up to 14× the simulated customers of today's (partial) run on the owner's file; NOT MEASURED | None |

## 5. Recommendation

**(a)**, with the (b) guard kept inside the engine as a second check: `_parallel_schedule` refuses any input with more than one record for the same (segment, lane), instead of taking the first. Under (a) it receives one date at a time, so the guard never fires on a correct call. It stops any future caller from silently dropping records.

Reasons: it uses every observation, it matches the B13 rule already approved for plans ("each calendar date is its own continuous day, starting empty"), and it keeps the Current card comparable with the Suggested per-date run.

If the owner wants the defect closed first, **(b) can ship on its own as an interim step**: the guard plus the refusal reason. (a) then replaces the refusal for per-date files with segments.

## 6. Rules for option (a) (PROPOSED)

1. **When.** A separate-lines Current run whose Setup has `event_period_basis = per_date` and operating segments that lay out a day (`per_date_continuous(setup)`, `separate_optimization.py:1694`). Representative-day and single-date runs follow the same path with one date. Their numbers must stay identical (one date, `date_seed(seed, 0) == seed`).
2. **Grouping.** By date with the existing `per_date_days(setup, labels, rows_by_label)`. It reads the date from NovaQ's own label and the segment from `segment_id`, and refuses a date that has no records for a configured segment (OD-B13-2, already approved for plans). For Current this refusal is OD-C5.
3. **Per date.** `_parallel_schedule` receives that date's records only. Each date starts empty and uses seed `date_seed(seed, date_index)`. The DES clock starts at 0 for each date.
4. **Open lane with no record on a date.** Decided by OD-C2. Today `_parallel_schedule` refuses with "Missing empirical segment/queue record for {segment}/{lane}" (`simulation.py:697-698`).
5. **No fallback.** A date is never filled with another date's record. A date that cannot be laid out is never simulated over a default horizon.
6. **Trace cap.** One recorder across all dates. The total event cap stays `max_events`, and `truncated` keeps its meaning. Whether later dates may lose their replay events is OD-C3.

## 7. Output (PROPOSED, additive only)

### 7.1 Result

- `results`: one row per date × segment × lane, with today's row fields. The `time` label is the dated label already stored.
- `segments`: as today, one entry per date × segment × lane context.
- `total_hours`: the sum of every date's day hours. Today it is one day.
- New `execution`: `"current_per_date_days"`. New `days`: `[{date, arrivals, served, waiting_at_close, in_service_at_close, customer_conservation, day_hours}]`, summed on the server.
- `summary` (`_run_summary`) keeps `basis: "per_period"`, because Current rows carry no `admitted` or `in_system_at_close`. Customer totals for a day come from `days`.

### 7.2 Trace events

Each event gets a new `date` field. Times stay on that date's clock (0 at the day's first segment), as in the Suggested per-date replay.

### 7.3 Parameters (for versioning, section 8)

`params.current_des_basis = "per_date_days_v1"` on every separate-lines Current DES job written after the fix.

### 7.4 Frontend (a separate step, after the backend)

Current Key results and Replay get the date picker that per-date Suggested runs already use (`dayPeriods`, `DatePicker`, address `date=`). The run-basis text for Current per-date reads like `simulation.run_basis_continuous_per_date`. Every new string goes in both `en` and `tl` (AGENTS.md i18n). The owner writes the wording (memory: owner writes wording), so the slots are listed, not drafted. These files are also changed on `feat/ulit-chart-redesign`. The frontend step should start from that branch after it merges, or be rebased onto it.

## 8. Versioning of stored Current runs

Stored separate-lines Current DES jobs record only `params.engine_version = "novaq-2026-09-unified-des-v1"`, shared by every workflow job (`workflow.py:98, 776`). Engine-version and Current-DES-accounting checks are switched off on purpose (`_current_evidence_policy`, `workflow.py:888-925`: `workflow_engine=None`, `current_des_accounting=None`). `evidence_status.py:463` (`AccountingRequirement`) and `:674-676` already provide an unused hook. It applies a recorded params marker only to the listed job kinds and only to results with separate rows. So a stored defective run would still show as Current after the fix. Section 7 of AGENTS.md says it must not. OD-C4 decides how to retire it.

## 9. Owner decisions

Decided by the owner on 2026-11-02: OD-C1 (a), OD-C2 (i), OD-C3 (i), OD-C4 (i), OD-C5 (i). OD-C6 is open.

| ID | Question | Options | Recommended |
|---|---|---|---|
| **OD-C1** | Which fix? | (a) each date as its own day; (b) refuse; (b) now and (a) next | **(a)**, with the engine guard (section 5) |
| **OD-C2** | (a) only. A lane the Setup schedules open in a segment has no customer record on a date, while other lanes served customers in that segment on that date. | (i) Treat it as **zero arrivals** for that lane and hour, and list every such lane-hour in the result (`zero_arrival_lane_periods`). (ii) Refuse that date, so the whole run is refused. (iii) Simulate the lane as closed for that hour. | **(i)**, listed openly. It is a new data rule (AGENTS.md §6), so it needs this approval. The staff sheet is one schedule for every date, so whether the lane was staffed on that date is **UNKNOWN**. (ii) would refuse every date of the owner's file. |
| **OD-C3** | (a) only. The trace cap across dates. | (i) One total cap (`max_events`, as today): later dates may have no replay events; the page says so. (ii) The cap applies per date: the stored result grows up to N times and can reach the 413 size limit (`result_jsonb_max_bytes`). | **(i)** |
| **OD-C4** | Stored separate-lines Current DES runs made before the fix | (i) Every separate-lines Current DES run without `current_des_basis` stops being Current (switch on the existing `current_des_accounting` hook). Unaffected runs (Representative day, one date) also need one rerun. (ii) Only runs whose dataset has more than one date on the per-date basis stop being Current. This needs a dataset read inside the protected currentness path. (iii) Keep them Current. | **(i)**. It is simple, uses the existing hook, and does not guess which runs were affected. Current MC and Current validation are unchanged, so they need no version change. |
| **OD-C5** | (a) only. A date with no records for a whole configured segment | (i) Refuse the run and name the date and segment (as B13, OD-B13-2). (ii) Leave that date out and list it. | **(i)**, the same as plans |
| **OD-C6** | Wording for the new reason (b) or date picker and notices (a), en + tl | Owner text, placed verbatim | Owner writes it |

## 9a. ORDER review (Chrome, 2026-11-02) and corrections

Chrome, Vongola V2 ORDER stage, read-only on `3ee8fe2c`, confirmed sections 1 to 3 against the source and corrected the plan as follows. Where these differ from sections 6, 7 and 10 and from plan A2 and A3, these govern.

- **Gate (F4, F5, VERIFIED).** `per_date_continuous` does not check for separate lines. The per-date path also requires `queue_structure == "separate_queues"` and every record `service_time_source == "empirical"`. Otherwise today's single call is unchanged, so separate aggregate data keeps today's HTTP 200 refusal.
- **Zero arrivals only in the per-date path (F9).** The OD-C2 λ = 0 records are added in the per-date runner, using that date's label. They are not added in `_parallel_schedule` for every caller. Representative-day and legacy callers keep today's "Missing empirical segment/queue record" refusal. The empty-samples check is relaxed only when λ = 0. This is safe because a customer is served from its own arrival period's samples (`simulation.py:809-810`, `:834`).
- **Date tag (F6).** Closed-lane filler rows carry `time = segment_id`, not a dated label. The per-date path therefore adds an additive `date` key to every results row, segments entry and trace event. `time` never changes.
- **Byte identity (F7).** Representative day never takes the new path, so its result stays byte-identical. A single-date per-date result is identical after removing only the added keys (`date`, `execution`, `days`, `zero_arrival_lane_periods`). Single-date runs that today's code refuses change as OD-C2 and OD-C5 intend.
- **Summary basis (F12).** The per-date result adds no top-level `admitted`, `in_system_at_close` or `periods`, so `_run_summary` keeps `basis: "per_period"`.
- **Second path (F2).** The engine guard also reaches scenario-bound `run_des` and the legacy `/simulation/des*` endpoints. Duplicate separate input there now gets the existing unsupported-row refusal. This is tested and reported as a behaviour change.
- **OD-C4 effect (F11, VERIFIED).** A stored separate Current DES job without the marker gives `des_current: null` from GET workflow. The page shows Not run, with no rerun message. That message belongs to OD-C6.
- **Release order (F13, INFERRED).** Until the frontend step A6 ships, Replay would play a multi-date trace whose clock restarts at 0 for each date, and the Key results card would mix dates. The backend must not be released ahead of A6.
- **Stored-result size (F3).** On SYNTHETIC data, one date of 13 hourly segments × 5 lanes measured 65 rows: 38,817 B of results, 11,245 B of segments and about 156.5 B per trace event. Extrapolated to 14 dates (INFERRED), rows and segments alone come to about 700,868 B before the trace. `_save_job` refuses results over `result_jsonb_max_bytes` with HTTP 413 (`workflow.py:755-760`). The default cap is 524,288 B (`backend/api/settings.py:198`); production is 786,432 B (REPORTED). The 413 message ("Reduce the playback event cap") would be misleading. Plan A7 measures this. **OD-C7** decides it.

| ID | Question | Options | Recommended |
|---|---|---|---|
| **OD-C7** | A per-date Current result on a file the size of the owner's would exceed the stored-result cap (F3, to be measured in A7). | (i) Raise `RESULT_JSONB_MAX_BYTES` on Render (owner's deployment setting; free-tier database size limits apply). (ii) Store a compact per-date result, for example without the duplicate `segments` list or null fields. This changes the stored shape, so it needs its own plan. (iii) Keep (a) for files that fit, and refuse larger ones before simulating, with a clear reason instead of the misleading 413. (iv) Switch to option (b) for all multi-date per-date files. | Decide after the A7 measurement. |

**Decided 2026-11-02 (owner): OD-C7 = (iii) now, then (ii) as the next spec.** The A7 measurement (SYNTHETIC, 14 dates × 13 segments × 5 lanes) is 1,253,317 B (Hayato) and 1,260,055 B (Kyoya) with the default 3,000 events, and about 730 KB with no trace. Both caps are exceeded. Under (iii), a per-date Current result over `result_jsonb_max_bytes` is refused with its own reason, not the "Reduce the playback event cap" message, and nothing is stored. The wording is owner text (OD-C6).

**K-CPD-2 (Kyoya, P3).** The λ = 0 empty-samples relaxation must reach only the zero-arrival records generated in the per-date path. Representative-day and legacy callers keep HEAD's "Missing empirical service samples" refusal. This applies the section 9a rule above; it is not a new decision.

**Owner answers before commit (2026-11-02):** (1) commit with the placeholder text in `CURRENT_PER_DATE_TOO_LARGE_DETAIL`; the owner's en and tl wording comes before release (K-CPD-7, OD-C6). (2) The refusal runs after simulating, because the size is known only then; accepted (K-CPD-8). (3) The pre-existing `mypy .` error at `backend/api/shared_continuous.py:447` is fixed as a separate small change. (4) One local commit authorized; no push.

Reviews: Kyoya (Vongola V2 TASTE) gave PASS for A0-A5 and PASS for the A7b/A7c/K-CPD-5 follow-up. Still open: K-CPD-3 (a refused date is not named), K-CPD-4 (A6 must key replay by date), F13 (no backend release before A6), and OD-C7 (ii) compact storage, which gets its own spec.

## 10. Tests (implementation gate)

- The six tests in `tests/test_current_separate_per_date.py` pass. The three RED tests pass by the approved option, and the three PASS tests stay green.
- Engine guard: a direct `_parallel_schedule` call with two records for one (segment, lane) is refused with a reason (a mutant that restores `next(...)` fails).
- (a): every date appears in `results` and `days`. Two dates with equal inputs give different arrivals (`date_seed`). Each date's conservation holds. A representative-day run and a single-date per-date run give byte-identical `results` and `trace` before and after (regression snapshot). OD-C2 and OD-C5 behaviour as decided.
- OD-C4: a stored separate Current DES job without the marker is not Current. A new job is Current. Shared-lines Current DES jobs are unchanged.
- Gates: `python -m pytest tests/ -x --tb=short`, `ruff check .`, `mypy .`, and `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` in `frontend/` when the frontend changes.
- Mutation check of the new rules, as in earlier protected steps.
