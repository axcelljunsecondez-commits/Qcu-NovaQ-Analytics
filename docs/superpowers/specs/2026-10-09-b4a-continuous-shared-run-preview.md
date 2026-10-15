# B4a: Continuous shared-line run (preview)

**Status:** APPROVED by the owner on 2026-10-09 (OD-B4a-1 = A separate nullable column, OD-B4a-2 = A reuse the named run's provisional limits, OD-B4a-3 = A five repeats by default). OD-UX-13 stays open. Docs only: implementation is plan step 10 and starts only after the owner's GO for that step.
**Parent spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (D24, D25, D28–D30, backend items B4a and B6, open decisions OD-UX-8 and OD-UX-13).
**Plan:** step 6 (this spec), step 10 (B4a + U7b implementation).
**Evidence labels:** VERIFIED (read in code at `ef05827e`, cited), REPORTED (from `memory.md` / `handoff.md`), PROPOSED, UNKNOWN, NOT TESTED.

## 1. Goal

One "Run full operation" button on Queue simulation runs the whole operating day of a shared line as one continuous simulation: no restart between periods; customers keep their place, waits and unfinished service across period boundaries; the day ends with the analysis's saved closing rule. Key results and the Replay come from the same run (D24, D28).

B4a is the **preview**: it covers only analyses the existing continuous engine supports, and is labelled as such. Recorded service times (B4b) and shared-line breaks (B4c) come later in their own specs.

## 2. What exists (VERIFIED)

| Fact | Evidence |
|---|---|
| A continuous shared M/M/c DES exists: piecewise-constant rates, staffing that may change between segments, no reset at boundaries, two closing policies `DRAIN` and `HARD_CUTOFF` with **no default**. Engine version `novaq-shared-continuous-des-v2`. | `backend/queueing_engine/simulation/shared_continuous_des.py:1-16, 40-64` |
| Model scope: Poisson arrivals, exponential service, FCFS, unlimited waiting room. Rows with `variance`, `K` or `theta`, or separate-queue rows, are rejected, never reduced to M/M/c. | `backend/queueing_engine/services/shared_segments.py:37-53, 373-403` |
| Aggregate rows `time, lambda, mu, c` with `HH:MM-HH:MM` labels map to one demand period and one staffing segment each. | `shared_segments.py:373-382` (`timeline_from_aggregate_rows`) |
| Replications: 1 to `MC_MAX_TRIALS` (100,000) with a seed and a closing policy; summaries per metric; the verdict is always `None` (no pass/fail rule exists). | `backend/queueing_engine/simulation/shared_replications.py:405-425, 323-324`; `backend/queueing_engine/config.py:39` |
| A replay builder checks the replayed trace against the engine's own totals. | `backend/queueing_engine/simulation/shared_playback.py:68, 210-243, 306-331` |
| The engine's results are pinned by `tests/test_shared_continuous_des_pin.py`; engine, playback and replication tests exist. | `tests/test_shared_continuous_des*.py`, `tests/test_shared_playback.py`, `tests/test_shared_replications.py` |
| No API route exposes the continuous engine for an ordinary (non-named) analysis. The named shared run is the only adapter; it takes an explicit dataset, a closing policy per run, persists one Job per run, caps expected customers per run at 2,900 (`limits_status = provisional_not_production_approved`) and refuses results above `RESULT_JSONB_MAX_BYTES`. | `backend/api/shared_named.py:1-14, 129-133, 580-640`; `backend/api/settings.py:198` |
| The Setup fingerprint is a hash of the whole `queue_setup`, and evidence is valid only for the fingerprint it recorded. | `backend/api/scenarios.py:216-219` |
| Uploads of customer records (events) always carry service-time variation, so they fall outside the M/M/c scope. | REPORTED (`memory.md`, compact-redesign section; spec §9.2) |
| Production result cap is 786,432 bytes on Render. | REPORTED (`memory.md`, named API/UI notes; owner-set, not verified here) |

## 3. Scope (PROPOSED)

In scope:

- Shared-line analyses whose current planning dataset (B10) is aggregate data with `HH:MM-HH:MM` rows and no `variance`, `K` or `theta`. Data entered by hand (B9) qualifies.
- Two staffing sources, matching the page's "Current | Suggested plan" switch:
  - **Current**: counters from the data (`c` per row);
  - **Suggested plan**: counters from the selected plan (`c_optimal` per row of the selected, current, verified scenario). Without a selected plan the Suggested option says "Choose a plan first" and links to Suggested plans.
- The saved closing rule (see §4, OD-B4a-1).
- Key results and Repeat the day (replications) from one request; Replay for any replication, regenerated from the stored seeds.

Out of scope, with the message the user sees:

| Case | Message (plain words) |
|---|---|
| Separate lines | "The full-day run is for one shared line. Separate lines already replay the whole day on the Replay page." |
| Customer-record uploads (variance) | "Your data has real service times. The full-day run uses them in a later update (B4b). Until then it needs counts per period." |
| Rows with `K` or `theta` | "Waiting-room limits and customers leaving are not in the full-day run yet." |
| Gaps or overlaps between periods, or periods crossing midnight | the engine's own validation messages, listed |
| No closing rule saved | "Choose what happens at closing time first." with the choice inline |

## 4. Decisions for the owner

### OD-B4a-1: where the closing rule is saved

D25 says the rule is saved per analysis and that changing it affects future runs only. Saving it inside `queue_setup` would change the Setup fingerprint (`scenarios.py:216-219`) and make every existing plan, simulation and check stale, which D25 does not want.

| Option | What it means |
|---|---|
| **A. New nullable column on the analysis (recommended)** | `analysis_projects.shared_closing_policy`, values `DRAIN` / `HARD_CUTOFF` / null (not chosen). Saved through its own CSRF-protected endpoint. Not part of the Setup fingerprint. Ships in the same migration as B10 if both are implemented together. |
| B. Inside `queue_setup`, excluded from the fingerprint | Changes the protected fingerprint function. Not recommended. |
| C. Inside `queue_setup`, fingerprint unchanged | Choosing or changing the rule makes all earlier results stale. Contradicts D25. Not recommended. |

Each run also records the rule it used (as the named run does), so changing the saved rule later never changes what a stored run says.

### OD-B4a-2 (= OD-UX-8): size and time limits

| Option | What it means |
|---|---|
| **A. Reuse the named run's limits (recommended)** | Expected customers per request (replications × sum of arrival rate × period hours) at most 2,900; stored result at most `RESULT_JSONB_MAX_BYTES`; replay traces are regenerated from seeds when opened instead of stored. These limits are the named run's provisional, not production-approved values (REPORTED), and B4a would carry the same status until measured. |
| B. Separate limits for B4a | Needs its own timing measurements on a production-like container before shipping. |

Example: a day of 13 one-hour periods at 40 customers per hour is about 520 expected customers, so the 2,900 cap allows about 5 repeats of that day in one request.

### OD-B4a-3: default number of repeated days

| Option | What it means |
|---|---|
| **A. 5 by default, changeable under Advanced (recommended)** | Fits typical days under the 2,900 cap; the page says how many were run. Ranges from 5 repeats are wide, and the page says so. |
| B. As many as the cap allows | Uses the full budget; run time varies with the day. |

### OD-UX-13 stays open

The replications return no verdict (`shared_replications.py:323-324`). Until the owner approves a pass/fail rule, the Checks and decision page shows ranges only and says that no Decision is available for the full-day run. The existing Decision for period-by-period checks is unchanged.

## 5. API (PROPOSED, additive)

All routes are under `/analyses/{id}/…`, require a session and, for writes, the CSRF header (not exempt), and are owner-checked with `own_analysis`.

- `PUT /analyses/{id}/closing-policy` `{ "closing_policy": "DRAIN" | "HARD_CUTOFF" }` → saves the rule (OD-B4a-1 A). `GET` returns it or null.
- `POST /analyses/{id}/continuous/compatibility` → `{ compatible, reasons[], expected_customers_per_day, plan_sources }` without running anything (the page shows this before Start, D24).
- `POST /analyses/{id}/continuous/runs` `{ plan: "current" | "suggested", replications, seed }` → runs and persists one Job (`kind = "shared_continuous_preview"`) with provenance: dataset id and generation, scenario id and generation (suggested), closing rule used, engine version, seed scheme, replications, inputs digest. Rate-limited with the existing per-user compute limit.
- `GET /analyses/{id}/continuous/runs`, `GET …/runs/{run_id}` → stored summaries.
- `GET …/runs/{run_id}/replications/{index}/playback` → replay regenerated from the stored seed and checked against the stored totals (`shared_playback.py`).

Not changed: `/simulation/*`, `/optimize/*`, workflow evidence, Compare, Decision, Reports (B8 adds report content later). The new Job kind is not part of evidence currentness or the Decision chain.

## 6. Frontend (PROPOSED, plan step 10, U7b)

- Run bar: hours, closing rule + "Change", status, "Preview · what does this mean?", Run full operation, Advanced (repeats, seed).
- Key results (D30): four headline cards Current → Suggested from the run's totals (average wait, longest line, customers served, not served at closing), two charts (people waiting through the day, average wait by period); the rest under More results.
- Replay: the regenerated trace with D29 motion rules.
- Every number carries "Simulated · preview"; no Decision words.

## 7. Tests (PROPOSED; written before the code)

1. Engine and pin tests unchanged and passing.
2. Compatibility: separate lines, events data, `K`/`theta`, gaps, no closing rule, no selected plan for Suggested → each refused with its code and nothing stored.
3. Current and Suggested map counters exactly from the data and from the selected scenario rows.
4. A stored run records the closing rule it used; changing the saved rule afterwards does not change the stored run.
5. Same seed and inputs → identical summaries and identical regenerated replay.
6. Limits: one over the expected-customer cap → refused before simulating; a result over the byte cap → refused and nothing stored.
7. Saving the closing rule does not change the Setup fingerprint, and existing evidence stays current.
8. Owner isolation and CSRF on every write.
9. Mutation testing of the adapter's mapping and refusals.

## 8. Risks

- Runtime on the production container is not measured for this adapter (NOT TESTED); OD-B4a-2 A inherits the named run's provisional status.
- The preview is M/M/c; real service times differ (B4b). The page must say so in plain words.

## 9. Acceptance

Owner answers (2026-10-09, in chat): OD-B4a-1 = **A, `analysis_projects.shared_closing_policy`** outside the Setup fingerprint; OD-B4a-2 = **A, the named run's limits** (2,900 expected customers per request, `RESULT_JSONB_MAX_BYTES`, replays regenerated), still provisional; OD-B4a-3 = **A, 5 repeats by default**, changeable under Advanced. OD-UX-13 stays open. Implementation is plan step 10, after U7a and after B10 (which defines the current planning dataset).
