# B4b addendum: Representative day for shared lines

**Status:** APPROVED by the owner on 2026-10-12 (OD-B4b-A1 approved; OD-B4b-A2 = reuse the separate-lines wording) and implemented on `feat/ux-u1-shell` (uncommitted). Originally PROPOSED the same day. Owner chose OD-B4b-3 = A on 2026-10-12 (allow the Representative day basis for shared lines); this addendum states exactly what that changes. Implemented after approval.
**Parent specs:** `2026-10-09-b4b-recorded-service-times.md` (approved; its section 2 correction names this gap), `2026-09-18-separate-representative-day.md` (introduced the basis for separate lines only).
**Plan:** step 11 (B4b) cannot finish without it.
**Evidence labels:** VERIFIED (read in code or run on 2026-10-12, cited), PROPOSED, UNKNOWN, NOT TESTED.

## 1. Problem (VERIFIED)

| Fact | Evidence |
|---|---|
| Setup validation refuses `event_period_basis = representative_day` unless the line is separate. | `backend/api/analysis_schemas.py:147-151`; pinned by `tests/test_representative_day.py:49` |
| The Setup page shows the period-basis control and the operating-segments editor only for separate lines. | `frontend/src/pages/AnalysisSetupPage.tsx:299`, the segments card at line 303 |
| The basis needs operating segments. | `backend/data/analysis_ingestion.py:227-229` |
| So every shared customer-record upload is per-date (labels such as `2026-03-02 08:00 UTC`), and the full-day run refuses it (`per_date_data`). | Scratch analysis 4, browser check 2026-10-12 |
| The earlier spec limited the basis to separate lines because it solved a separate-lines problem (thin data per cashier); it gives no reason that excludes shared lines. | `2026-09-18-separate-representative-day.md`, "Problem" and "Behavior" |
| Ingestion already pools shared records correctly when the rule is bypassed: one row per segment, `lambda = arrivals / (segment hours x dates)`, durations pooled over all dates, `c` = the fixed counter count, `observation_days` recorded. | Read-only probe 2026-10-12: segment s1, 6 customers over 2 dates of 1 h, gives lambda 3.0; mean 9 min gives mu 6.667 (hand-checked) |
| A strict expected-failure test through the public routes (create, upload, run) fails today with exactly this refusal. | `tests/test_b4b_recorded_service.py::test_a_shared_customer_record_upload_runs_the_full_day_through_the_public_routes` |

## 2. Change (PROPOSED)

1. **Setup validation:** accept `representative_day` for shared lines too. It still requires operating segments (existing ingestion rule). Single-server and unknown structures stay per-date only. The default stays `per_date`, so no existing analysis changes.
2. **Setup page:** for shared lines, show the period-basis control and the operating-segments editor (start and end times only; the per-segment counter lists stay separate-lines only). Shared customer-record uploads still refuse varying staffing (unchanged, `analysis_ingestion.py:220`).
3. **Ingestion:** no change expected; its existing pooling is used as it is (section 1).
4. **Evidence:** no new rule. The Setup fingerprint hashes the whole Setup (`backend/api/scenarios.py:216-219`), so changing the basis already marks plans and runs made under the old Setup as needing recalculation, as it does for separate lines.
5. **Full-day run:** the B4b adapter already lays representative-day rows on the operating segments; the expected-failure mark is removed and the test must pass.

## 3. What representative day means (stated to the owner)

It replaces each date with the average day: arrivals at each segment's average rate over all dates, service times pooled from all dates. This is the input NovaQ already uses for separate lines and the usual average-rate input for staffing by period. It does not show day-to-day swings: a busy day's waits are understated and a quiet day's overstated. Per-date stays the default and remains available for the period-by-period run.

## 4. Unchanged (protected)

Queueing formulas, `model_selection.py`, the optimizers, the exponential continuous engine (pin test), separate-lines behavior, per-date behavior, Monte Carlo, validation, the Decision, reports, and the named shared run (it refuses rows with service-time variance, unchanged).

## 5. Places to check, each with a test (PROPOSED)

| Place | Expectation |
|---|---|
| `analysis_schemas.py` | Shared + representative day accepted with segments; refused without segments at upload (existing message); single-server stays refused. `test_representative_day.py:49` is updated: its "separate only" assertion becomes "not for single-server". |
| `analysis_ingestion.py` | A shared representative-day upload gives the pooled rows of section 1 (unit test with hand-computed values). |
| `data_dates.py:44` | Unchanged. Dates stored at upload (B11) come first, so a representative-day upload still shows its real date range; the label fallback at line 44 only applies to older files without stored dates. (Corrected 2026-10-12 after the test: the first draft expected no dates.) |
| `workflow.py:1976` observed-wait comparison | Uses `observation_days` for any structure; one shared test. |
| Legacy shared paths (Suggested plans, period-by-period run, Monte Carlo) | Accept segment-labelled rows; one end-to-end test through the public routes. UNKNOWN until tested. |
| `setup_derivation.py:308` | Derives separate Setups only; unchanged. |
| Setup page | Shared lines show the basis control and segment times; switching structure still clears the basis (existing `AnalysisSetupPage.tsx:120-123`). |

## 6. Decisions for the owner

- **OD-B4b-A1:** approve this addendum (sections 2-5).
- **OD-B4b-A2:** wording beside the basis control for shared lines: reuse the separate-lines wording as it is (recommended), or add a line that busy-day waits are understated.
