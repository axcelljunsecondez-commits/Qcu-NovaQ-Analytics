# Compact stored result for per-date separate-lines Current DES (C-PD-C, OD-C7 (ii))

Status: **APPROVED 2026-11-02 (owner: "okay proceed to all recommendation"): OD-C8 (i) sequenced, OD-C9 C-rows, OD-C10 (i), OD-C11 (i), OD-C12 (i), OD-C13 (i), OD-C14 (i), OD-C15 (i). OD-C6 wording open.** The owner asked for it on 2026-11-02: "start the spec". The investigation is by Chrome (Vongola V2 ORDER, read-only); the parent wrote it down. Nothing is implemented.

This spec follows spec `2026-10-30-current-separate-per-date-des` (C-PD), section 9a: OD-C7 = (iii) now, (ii) next.

Protected work:
- AGENTS.md §5: DES behaviour must not change.
- AGENTS.md §6: no data dropped.
- The frozen API contract: changes are additive only.

Base: HEAD `554d978d`. `b484d8f2` is C-PD, which exists only on this branch. Before integration, OD-C8 must be decided.

## 0. Integration precondition (VERIFIED by the parent, 2026-11-02)

- `origin/main` is at `4dd99465` ("Merge PR42: integrate charts and bounded Current input guard", 2026-11-02 04:14 +0800). Its commit `d8f89da6` adds `_validate_current_des_date_scope` (`origin/main:backend/api/workflow.py:690`, called at `:1462`).
- That guard answers the same defect (K-UC-13), and the owner approved it in another session: "Approve bounded input guard", recorded in `origin/main:docs/superpowers/specs/2026-11-01-chart-live-integration.md:45-56`.
- The guard refuses ambiguous multi-date per-date separate Current DES input with HTTP 422 "Current dataset records are invalid." (`origin/main:tests/test_current_des_per_date_scope.py:124-170`). A single-date file with a missing open lane keeps the old refusal (`:197`).
- C-PD (`b484d8f2`, OD-C1 (a) and OD-C2 (i), decided 2026-11-02 in this session) simulates those same inputs instead. The two conflict in `run_des_current` and in these tests. This branch's base `3ee8fe2c` is behind `origin/main`.
- `554d978d` duplicates `origin/main`'s `f23bfbd3` hunk byte-for-byte; the parent compared the two hunks. INFERRED: a rebase or merge resolves it cleanly. NOT TESTED.
- On `main` the defect is already closed by refusal (§6 met). C-PD and this spec improve that refusal into a usable result.
- Whether `4dd99465` is deployed on Render or Pages: UNKNOWN.

## 1. Problem (VERIFIED)

C-PD runs each date of a per-date separate-lines file as its own day. It stores one result containing:
- every date's rows;
- one segments entry per row;
- one trace, capped at `max_events` in total.

The code is `simulation.py:1087` `simulate_parallel_days_with_trace` and `workflow.py:1484` `_run_current_per_date_des`.

On a file of 14 dates × 13 hourly segments × 5 lanes, the stored result is 1.25–1.30 MB. That is over both the default cap (524,288 B, `settings.py:198`) and the reported production cap (786,432 B, REPORTED). Since OD-C7 (iii), such a run is refused with 413 `CURRENT_PER_DATE_TOO_LARGE_DETAIL` (`workflow.py:106`; the check is in `run_des_current`, `workflow.py:1439-1481`), and nothing is stored.

Goal: such a run is stored and usable, in Key results and in Replay by date (A6). The DES stays unchanged and no observation is lost.

## 2. Evidence

### 2.1 Byte breakdown (VERIFIED on SYNTHETIC data, committed code at `554d978d`)

The test data:
- 14 dates (2000-01-03 to 2000-01-16), 13 hourly segments from 08:00 to 21:00, 5 lanes;
- 6 to 14 customers per lane-hour, service 2 to 8 minutes;
- 910 records, seed 42, `max_events` 3000.

The result was built exactly as `run_des_current` builds it: `_run_current_per_date_des`, then provenance, then `_run_summary`.

Total size: 1,300,557 B (Hayato measured 1,253,317 B and Kyoya 1,260,055 B on their own SYNTHETIC data). Without the trace: 767,409 B.

| Key | Bytes | Note |
|---|---|---|
| results | 564,067 | 910 rows, average 620 B per row |
| trace | 533,159 | 3,000 events, average 177.7 B. Only dates 1 and 2 have events, because of the total cap (OD-C3 (i)). |
| segments | 177,462 | 910 entries. Every key is also in the matching row. |
| summary | 23,461 | 182 periods |
| days | 2,187 | 14 entries |
| other scalars | < 300 | |

The trace and segments together are 54% of the result. Of the per-row fields:
- 4 have a single value on every row: `selected_model`, `metric_provenance`, `queue_structure`, `simulation_supported`;
- `error` and `Lq_sim` are null on every supported row;
- `final_Lq` equals `waiting`;
- `throughput` equals `served` divided by the duration;
- `server_id` equals `"server:"` plus `queue_id`.

Uncapped, each date has 1,771 to 2,084 events, 26,605 in total.

### 2.2 Size per option

Sizes for N up to 14 are VERIFIED by slicing one uncapped run; a slice equals a direct 3-date run byte for byte. Sizes beyond 14 are INFERRED by linear extrapolation at 65 rows per date.

| Option | N = 1 | N = 14 | Per date | Max N at 524,288 | Max N at 786,432 |
|---|---|---|---|---|---|
| Today (`b484d8f2`) | 399,987 | 1,300,557 | 54,785 | 1 | 4 |
| Today, no trace | 55,289 | 767,409 | 54,785 | 9 | 14 |
| A: drop redundant, null and constant fields, keep trace | 370,609 | 889,643 | 25,433 | 1 | 9 |
| A, no trace | 25,911 | 356,495 | 25,433 | 20 | 30 |
| B: lossless columnar rows and columnar trace | 97,708 | 389,841 | 19,230 | 20 | 34 |
| B, no trace | 20,100 | 270,005 | 19,230 | 27 | 40 |
| C-rows: key row objects plus per-date digests, no trace or segments | 21,408 | 293,638 | 20,943 | 25 | 37 |
| C-columnar: key rows, no trace | 9,847 | 129,972 | 9,243 | 56 | 85 |
| C, totals only (summary, days and digests) | 2,298 | 26,965 | 1,897 | about 276 | about 414 |
| D: one job per date, 3,000 events each | 375,236 per job | 14 jobs | | each job fits | each job fits |
| E: raise the cap | | needs at least 1.31 MB | | | |

### 2.3 Reproducibility (VERIFIED locally: Windows, Python 3.13.13, SimPy 4.1.2)

- With the same inputs, seed and `max_events`, the 14-date result is the same every time: hash `5ed9f91751a5e84a`. This held in three processes, with `PYTHONHASHSEED` set to 0, to 12345 and to random, and on a repeat within one process.
- Each date run alone (`simulate_parallel_days_with_trace([(date, records)], ..., [date_seed(seed, i)], cap)`) equals that date's slice of the 14-date run: rows, trace and days, for all 14 dates.
- The recorder cap never changes the simulation. The capped rows equal the uncapped rows, and the capped trace is a prefix of the uncapped trace.
- Why, from the code:
  - each date has one `random.Random(seed)` (`simulation.py:781`);
  - customer ids restart for each call (`:782`);
  - SimPy breaks ties by insertion order, which is deterministic;
  - set iteration is used only for membership tests or over sorted values;
  - dict order is insertion order.
- `seed = None` is **not** reproducible: two runs differ. The Current run bar sends `null` by default (`RunBar.tsx:15, 22`; `lib/simulationEvidence.ts:12-16`).
- Across platforms and versions: NOT TESTED. Production runs Python 3.11.16 on Alpine (musl) (`Dockerfile.api:1`). `math.log` comes from the platform's libm, so a different libm, Python or SimPy could change a value (INFERRED). A stored fingerprint must therefore be checked on every regeneration.

### 2.4 Time and memory (local only; Render NOT TESTED)

- A 14-date run with the total cap of 3,000 events: median 0.857 s.
- One date regenerated with its own cap of 3,000: 0.068 s, plus 0.0125 s to encode the JSON. The response is 373,397 B with 1,796 events.
- An uncapped 14-date run: 3.62 s under tracemalloc, peak memory 11.0 MB.

## 3. Consumers of a stored `workflow_des_current` result (VERIFIED by reading the code; frontend as on `origin/main`)

| Consumer | Fields read |
|---|---|
| `_run_summary` (`workflow.py:2257`) | Top-level `admitted`, `in_system_at_close` and `periods`, which must stay absent. From rows: `time`, `max_queue`, `served`, `Wq_sim`. |
| `evidence_status` `_has_separate_rows`, `_all_rows_unsupported`, `job_record` (`:635-690`) | From rows: `queue_structure`, `simulation_supported`. From params: `current_des_basis`, `dataset_id`, `dataset_generation`, `setup_hash`. |
| GET workflow (`workflow.py:1215, 1277`; `_job_out` `:725`) | The whole result and params, on every page load. |
| Reports, Decision, Current validation | None. Grep finds no reader in `backend/` outside `workflow.py`. |
| RunBar (the POST response) | From rows: `time`, `error`, `simulation_supported`. From params: `seed`. |
| KeyResultsView (`main`) | All of `summary`. Rows through `currentMatrix` (`lib/longestLine.ts:82`): `time`, `queue_id`, `segment_id`, `error`, `simulation_supported`, `max_queue`, `rho_sim`. The More results table. The CSV download uses every row field. |
| ReplayView, SeparateSimulationPlayback, `lib/simulationPlayback` | From segments: `queue_id`, `server_id`, `simulation_supported`, `error`, `time`, `queue_structure`. From events: `t`, `type`, `customer_id`, `server_id`, `queue_id`. Also `total_hours`, `trace_hours`, `event_count`, `truncated`, `abandonment_supported`. |

## 4. Options

- **(A) Drop redundant and null fields.** This removes fields, so it is not additive. With the trace kept, it still fits only 1 date under the default cap and 9 under 786,432, because the 3,000-event trace alone (533 KB) is larger than the default cap.
- **(B) Lossless columnar rows and trace.** It needs decoders in `_run_summary`, in `evidence_status` and in the frontend. `_has_separate_rows` would no longer see rows, so `evidence_status.py` would change, and that is the protected currentness path.
- **(C) Compact per-date numbers, with one date regenerated on request.** Store compact numbers for each date. When a date is opened, rebuild its full rows and trace from its recorded seed and check them against stored fingerprints (section 2.3).
  - **C-rows** keeps `results` as row objects, so `_run_summary` and `evidence_status` need no change.
  - **C-columnar** holds about twice as many dates, but needs the decoder changes of (B).
- **(D) One job per date.** `_latest_job` returns one job per kind, and 14 commits are not atomic. GET workflow's `des_current` would become a list, which is not additive. Each run would store 14 × 375 KB.
- **(E) Raise `RESULT_JSONB_MAX_BYTES`.** This is the owner's deployment setting. GET workflow would then send about 1.3 MB on every page load, and every run would add a row of that size; no job pruning was found in `backend/`. The Supabase Free storage limit is UNKNOWN.

| | A | B | C-rows (recommended) | C-columnar | D | E |
|---|---|---|---|---|---|---|
| Dates at 524,288 / 786,432 | 1 / 9 (20 / 30 without trace) | 20 / 34 | 25 / 37 | 56 / 85 | each job fits | any, up to the cap |
| Additive contract | no | yes (new keys) | yes (a new `execution` value; runs of 2+ dates were never released) | yes | no | yes |
| `evidence_status` change | no | yes | no | yes | yes | no |
| Every date replayable | no | partly (total cap) | yes (each date has its own cap) | yes | yes | partly (total cap) |
| DES unchanged | yes | yes | yes (same core, same seeds) | yes | yes | yes |
| New endpoint | no | no | yes (read-only GET) | yes | no | no |
| GET workflow payload at 14 dates | about 0.9 MB | about 0.39 MB | about 0.29 MB | about 0.13 MB | changes shape | about 1.3 MB |
| Size of change | S | M | M | M+ | L | config only |

## 5. Recommendation

**C-rows** for per-date runs with two or more dates, plus a read-only day-detail endpoint.
- One-date and Representative-day runs keep today's shape (C-PD §9a).
- Runs larger than C-rows can hold stay refused under OD-C7 (iii).
- C-columnar is the follow-up if more than about 25 dates must fit under the default cap.

## 6. Rules (PROPOSED)

1. **Scope.** The compact path is used only when all of these hold: separate lines; `per_date_continuous`; every record empirical; two or more dates (OD-C10). Otherwise behaviour is exactly as at the integrated base.
2. **The simulation is unchanged.** It uses the same `_simulate_parallel_segments_core`, the same zero-arrival records and `date_seed(seed_used, i)` for each date. Each date gets its own trace recorder with cap `max_events`. That recorder is used only to compute the date's fingerprint and event count; no events are stored (OD-C11).
3. **Seed.** When the request seed is null, the server draws an integer (with `secrets`) and records it as `result.seed_used`, and `params.seed` keeps the request's value (OD-C12). When a seed is given, `seed_used = seed`.
4. **Stored result**, with `execution` set to `"current_per_date_days_compact"`:
   - `results`: one object per date × segment × lane, with exactly these fields: `time`, `date`, `segment_id`, `queue_id`, `queue_structure`, `simulation_supported`, `arrivals`, `served`, `waiting`, `in_service`, `max_queue`, `Wq_sim`, `rho_sim`. Each value is identical to the full row.
   - `trace = []`, `segments = []`, `event_count = 0`, `truncated = false`.
   - `trace_hours`, `total_hours`, `abandonment_supported`, `zero_arrival_lane_periods`, `provenance` and `summary`: as today.
   - `days[i]`: today's fields, plus:
     - `rows_digest` and `trace_digest`: sha256 of canonical JSON (`sort_keys`, separators `(",", ":")`, `allow_nan=False`) of that date's full rows and of its own-cap trace;
     - `event_count` and `truncated`.
   - `seed_used`.
   - No top-level `admitted`, `in_system_at_close` or `periods` (C-PD F12).
5. **Summary.** The compact `summary` equals the full run's `summary`, because `_run_summary` reads only the kept fields.
6. **Refusals** keep today's unsupported-row shape for every record. A refusal is never compacted.
7. **Day detail endpoint:** `GET /analyses/{analysis_id}/workflow/simulation/des/current/days/{date}`.
   - **Auth.** `get_current_user` and `own_analysis`. The job is chosen exactly as `_current_evidence` chooses it: `current(_latest_job(..., "workflow_des_current", ...))`, with `_evidence_is_current` (dataset, `setup_hash`, generation tokens when enforced, dependencies).
   - **Not found.** If the job is not current, not compact, or the date is not in `days`, return 404 (wording slot W3).
   - **Inputs.** The records of `db.get(Dataset, params.dataset_id)`, through `_current_segments_for`; `analysis.queue_setup_json`; grouping with `per_date_days`. The date's index must equal its stored position, otherwise return 409.
   - **Run.** `simulate_parallel_days_with_trace([(date, records)], setup, params.sim_hours, [date_seed(seed_used, i)], params.max_events)`.
   - **Check.** `rows_digest`, `trace_digest`, arrivals, served and conservation must all equal `days[i]`. On any mismatch, return 409 and serve nothing (OD-C13, wording slot W2).
   - **Response.** Today's SimulationTrace shape for that date, plus:
     - `date` and `job_id`;
     - `days: [days[i]]` and that date's `zero_arrival_lane_periods`;
     - `summary` computed by `_run_summary` for that date;
     - `execution` set to `"current_per_date_day_detail"`.
     
     Nothing is stored, and there is no 413 path.
   - **Rate limit.** `user_rate_limit("compute")` (OD-C14). It is a GET, so CSRF does not apply.
8. **No fallback.** A date that cannot be regenerated exactly is refused. It is never approximated or filled from another date (§6).

## 7. Versioning

- `current_des_basis` becomes `"per_date_days_v2"` on every separate-lines Current DES job. In `_current_evidence_policy`, v2 is current and v1 is historical (OD-C15).
- v1 jobs exist only where `b484d8f2` ran, which is local only. Jobs written by `main` have no marker; under OD-C8 (i) they are no longer Current.
- The compact shape uses a new `execution` value, and the frontend chooses how to display a result by `result.execution`.

## 8. Owner decisions

| ID | Question | Options | Recommended |
|---|---|---|---|
| **OD-C8** | `origin/main`'s guard of 2026-11-01/02 conflicts with C-PD OD-C1 (a) and OD-C2 (i). It gives 422 for multi-date files and keeps the old refusal for a single-date file with a missing lane. | (i) C-PD replaces it when merged: rewrite `main`'s guard tests to the approved behaviour and record the change in the 11-01 spec. (ii) Keep the guard and drop C-PD (a); then this compact spec is not needed. | **(i), sequenced.** Keep `main`'s guard in production until C-PD, this spec and A6 are ready, then replace it in **one** PR. Until then `main` stays safe by refusal. |
| **OD-C9** | Storage design | A, B, C-rows, C-columnar, D, E | **C-rows** |
| **OD-C10** | Which runs are compact | (i) two or more dates only; (ii) every per-date run | **(i)**: one-date runs keep today's shape |
| **OD-C11** | Replay event cap | (i) each date has its own `max_events` in day detail (replaces OD-C3 (i) for compact runs); (ii) keep one total cap | **(i)**: every date can be replayed |
| **OD-C12** | Unseeded runs | (i) the server draws a seed and records it as `seed_used`; (ii) per-date Current requires a seed; (iii) unseeded compact runs have no day detail | **(i)**. This changes how the random generator is seeded, so it needs approval. It is statistically the same as `Random(None)` (INFERRED). |
| **OD-C13** | The regenerated date does not match its fingerprint | (i) refuse with 409 and ask for a rerun; (ii) serve it with a warning | **(i)** |
| **OD-C14** | Day-detail rate limit | (i) the existing compute limit, with caching in the page; (ii) a new setting | **(i)** |
| **OD-C15** | Version marker | (i) v2 is current and v1 is historical; (ii) keep v1 current and choose by `execution` | **(i)** |
| **OD-C6** | Wording | Owner text, en and tl | Slots in section 9 |

## 9. Wording slots (owner writes all text; nothing is drafted here)

- **W1:** 413 when the compact result still exceeds the cap (the existing `CURRENT_PER_DATE_TOO_LARGE_DETAIL`).
- **W2:** 409 when a day's detail cannot be reproduced.
- **W3:** 404 when there is no current run, or the date is not in the run.
- **W4:** the date picker label for Current.
- **W5:** the loading and error states while a date loads.
- **W6:** the note that each date has its own replay event limit.
- **W7:** the chip that shows a server-drawn seed.
- **W8:** the CSV download of the chosen date.
- **W9:** the C-PD A6 slots: the run basis, the zero-arrival lane notice, and naming a refused date (K-CPD-3).

### 9.1 Drafted wording (relayed from the parent session on 2026-11-02, at the owner's request "draft it")

Status of each item: **Approved by owner delegation on 2026-11-03 ("you can decide the accurate word"); the code constants take the final English text.** Use the text exactly as given and keep the `{dates}` placeholder. The backend detail stays in English. The A6 frontend maps each case by status or code to the en and tl locale keys, and never shows raw server text in Tagalog. Until 2026-11-03 the code constants held `PLACEHOLDER` text; they now hold the final English text.

- **W1 (413, result too large).** Approved by owner delegation on 2026-11-03 ("you can decide the accurate word"); the code constants take the final English text.
  - EN: "This Current run is too large to save: it covers {dates} dates. Upload a file with fewer dates."
  - TL: "Masyadong malaki para i-save ang Current run na ito: {dates} na petsa ang saklaw nito. Mag-upload ng file na may mas kaunting petsa."
- **W3 (404, date not found).** Approved by owner delegation on 2026-11-03 ("you can decide the accurate word"); the code constants take the final English text.
  - EN: "This date is not in the latest Current run. Run Current again."
  - TL: "Wala ang petsang ito sa pinakabagong Current run. Patakbuhin muli ang Current."
- **W2 (409, cannot be rebuilt exactly).** Approved by owner delegation on 2026-11-03 ("you can decide the accurate word"); the code constants take the final English text.
  - EN: "This date of the Current run can't be rebuilt exactly, so it isn't shown. Run Current again."
  - TL: "Hindi ma-rebuild nang eksakto ang petsang ito ng Current run, kaya hindi ito ipinapakita. Patakbuhin muli ang Current."

Remedy check for W1 (parent session question). Fewer dates is not the only remedy. A Representative-day Setup pools the dates into one day and never takes the per-date path (VERIFIED: C-PD spec §3, and `setup_derivation.py:309-313` derives Representative day for a workbook with more than one date). Applying the Setup from the workbook is enough; F3 notes that saving a new basis asks for the file to be uploaded again. Raising the cap is the owner's deployment setting. Whether to name either remedy in the text is the owner's choice; nothing was added to the draft.

## 10. Tests (implementation gate)

- **Compact run:**
  - every record's (time, queue_id) appears exactly once;
  - `summary` equals the full run's summary;
  - `days` totals equal the row sums;
  - the SYNTHETIC 14 × 13 × 5 result is at most 524,288 B;
  - no trace or segments are stored.
- **Determinism:** the day detail for every date equals that date's slice of an uncapped full run, repeated in subprocesses with `PYTHONHASHSEED` set to 0 and to 12345.
- **Fingerprint:** changing a stored digest, `seed_used` or a dataset value gives 409, and nothing is served.
- **Seed:**
  - a null request seed gives an integer `seed_used`, and `params.seed` stays null;
  - two runs with the same `seed_used` give the same digests.
- **Scope:** byte-identical snapshots before and after for:
  - a one-date per-date run;
  - Representative day;
  - shared lines;
  - aggregate separate;
  - the legacy callers.
- **Evidence:**
  - a v1 job is not Current; a v2 job is Current;
  - day detail of a non-current job, or of another user's or another analysis's job, gives 404;
  - a generation token mismatch under enforcement gives 404.
- **Day detail:** it is rate-limited and never writes a Job.
- **Mutants:**
  - no digest check;
  - `seed` used instead of `seed_used`;
  - a total cap used in day detail;
  - the date index off by one;
  - segments kept in the compact result;
  - the marker left at v1.
- **Gates:** `python -m pytest tests/ -x --tb=short`, `python -m ruff check .` and `python -m mypy .`; the frontend gates in A6.

## 11. Out of scope

- The A6 frontend. It is a separate step, starts from `origin/main` (not from `f8bcc380`, which is behind `main`), and waits for the OD-C6 wording.
- The shared-lines per-date carry-over.
- The id-less segment mismatch and records on Setup-closed lanes.
- The production cap value and Render timing.
- C-columnar.
