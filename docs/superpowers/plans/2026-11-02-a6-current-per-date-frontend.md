# Plan — A6: frontend for per-date separate-lines Current runs

**Specs**
- `2026-10-30-current-separate-per-date-des`: §7.4 (A6), F13, K-CPD-4.
- `2026-11-02-current-per-date-compact-result`: §3, §6.7, §9 and §9.1.

**Base.** Branch `claude/cpd-compact` at `3bc3360f` (the C-PD and C-PD-C backend, Kyoya PASS). A6 ships with it in one PR.

**Approval.** The owner said "start a6" on 2026-11-02 (relayed by the parent session). The design comes from Chrome's ORDER (Vongola V2, read-only).

**Decisions the parent made on Chrome's ORDER points (2026-11-02)**
1. Locale values use the i18next form `{{dates}}`. The text the user sees is exactly spec §9.1.
2. *(Superseded on 2026-11-03: every entry is now `approved_owner_delegated_2026-11-03`; see the final sections.)* Draft wording is recorded in a new register, `docs/wording/2026-11-02-cpd-a6-draft-wording.json`. A test keeps the locale catalogs equal to it, and every entry is marked `draft_awaiting_owner_approval`.
3. W1 reads the date count from the 413 detail with `/(\d+) dates/`. A backend test pins that the detail contains "N dates", and the §9.1 English draft keeps that form.
4. N3 (the rate-limit text) is left out to keep new text to a minimum. A 429 shows `errors.server`.

**Wording.**
- W1–W3: verbatim from §9.1.
- N1 and N2: Chrome's drafts.
- Everything stays a draft until the owner approves it, and the backend constants keep their PLACEHOLDER text until then.
- No commit or push without approval.

## Steps

1. **Types, API, helpers.**
   - Add optional fields to `SimulationTrace`: `execution`, `days`, `seed_used`, `zero_arrival_lane_periods`, and `date` on rows, events and segments.
   - Add the types `CurrentCompactDay` and `CurrentDayDetail`, and the API call `getCurrentDay(analysisId, date)`.
   - Add `lib/currentPerDate.ts` with its tests.

2. **Wording.**
   - Add W1–W3 (§9.1), N1 and N2 to both the en and tl files, with `{{dates}}` and `{{count}}`.
   - Add the draft register and its catalog test.
   - Do not touch:
     - `docs/wording/2026-10-27-local-wording-application.json`
     - `frontend/src/lib/wordingPolicy.test.ts`
     - `frontend/src/lib/headingText.ts` and `headingText.test.ts`
     - `frontend/src/lib/translationKeys.test.ts`

3. **RunBar.**
   - The seed shown is `params.seed ?? result.seed_used`.
   - A per-date 413 shows W1, with the date count read from the detail. If the count cannot be read, show `errors.server`. Never show raw server text.

4. **simulationContext.** The basis for a separate-lines per-date Current run is `run_basis_continuous_per_date`, with the existing "No breaks" chip.

5. **Key results, compact branch.**
   - Show the DatePicker, N1, and N2 when the chosen date has zero-arrival entries.
   - The Longest Single Line table comes from the stored rows of the chosen date.
   - WaitByPeriod and the period table show only the periods whose label starts with the chosen date.
   - The More results table and the CSV cover only the chosen date.
   - The headline cards keep the summary of all dates.
   - Key results makes no fetch.

6. **Replay, compact branch.**
   - Query `['current-day', analysisId, jobId, date]` with `staleTime: Infinity`, `retry: false` and `refetchOnWindowFocus: false`. Do not prefetch other dates.
   - A 404 shows W3, a 409 shows W2, and anything else shows `errors.server`.
   - The playback is keyed by `jobId` plus date, and labelled `"${date} · ${hours}"`.

7. **Backend pin tests** (`tests/test_current_per_date_compact.py` only).
   - K-CPDC-1:
     - a date removed from the dataset in place gives 409;
     - a stored `days` list longer than the grouped dates gives 409.
   - The 413 detail contains "N dates".
   - A scratch mutant without the position check (`workflow.py:1656`) must fail these tests. It is never committed.
   - K-CPDC-2: no change, because there is no reproducer. It stays a residual P3.

8. **Gates.**
   - Frontend: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.
   - Backend: pytest on the file, then the full suite; `ruff check .`; `mypy .`.

9. **Browser check** (by the parent, who has the browser tools).
   - Setup: local SQLite and Vite, with a SYNTHETIC per-date file of 3 dates × 3 hourly segments × 3 lanes, one lane-hour missing on date 2.
   - Check at 375 and 1280 px, in light and dark, in EN and TL.
   - Replay makes one GET for each newly viewed date.
   - Each date shows its own "Trace capped" badge.
   - Trigger W1 with a small `RESULT_JSONB_MAX_BYTES`, and W2 with an edited digest.
   - The owner's xlsx may be read where it is; it is never copied into the repo.

10. **Review and approval.**
    - Kyoya reviews.
    - The owner approves the wording before release.
    - The commit is local, made only after Kyoya's PASS.

## Stop conditions

Stop and report if any of these happens:
- the rendering of a one-date run or a refusal changes;
- the approved wording test or the key-symmetry test fails;
- Replay fetches more than once per (job, date), or Key results fetches at all;
- raw server text appears in Tagalog for W1–W3;
- a gate fails and the cause is unknown;
- a backend 500 is reproduced (then stop and re-scope).

## Files Hayato may write

**Frontend**
- `frontend/src/api/types.ts`
- `frontend/src/api/workflow.ts`
- `frontend/src/lib/currentPerDate.ts` and `currentPerDate.test.ts` (new)
- `frontend/src/lib/longestLine.ts` (only to widen the parameter type)
- In `frontend/src/components/queueSimulation/`: `simulationContext.ts`, `KeyResultsView.tsx`, `KeyResultsView.test.tsx`, `ReplayView.tsx`, `ReplayView.test.tsx` (new) and `RunBar.tsx`
- `frontend/src/pages/QueueSimulationPage.test.tsx`
- `frontend/public/locales/en/translation.json` and `frontend/public/locales/tl/translation.json`
- `frontend/src/lib/cpdDraftWording.test.ts` (new)

**Docs and backend tests**
- `docs/wording/2026-11-02-cpd-a6-draft-wording.json` (new)
- `tests/test_current_per_date_compact.py`

**Not authorized:** any `backend/*.py` file.

## Owner wording decisions after the browser check (2026-11-03, owner: "a a")

Both items are drafts until the owner approves the text. Hayato applies them only after Kyoya's A6 review returns, and Kyoya then reviews the change.

- **1a: N2 gets a singular form.**
  - Replace `simulation.current_zero_arrival_note` with `simulation.current_zero_arrival_note_one` and `simulation.current_zero_arrival_note_other`.
  - EN, one: "On this date, {{count}} open queue period had no customer records; it is shown with zero arrivals."
  - EN, other: the current text.
  - TL, both forms: the current TL text, unchanged as the owner chose.
  - Parent note for the owner: for one item, TL "ipinapakita ito" would be more exact than "ipinapakita ang mga ito".
- **2a: per-date longest-line sentence.**
  - Add `charts.longest_take_current_date_one` and `charts.longest_take_current_date_other`. They are used only for a compact multi-date Current run with a chosen date (`LongestLineTable.tsx:83`). In every other case `charts.longest_take_current` stays as it is.
  - EN, one: "Longest line on {{date}}: {{count}} person, at {{where}}."
  - EN, other: "Longest line on {{date}}: {{count}} people, at {{where}}."
  - TL, both forms: "Pinaka Mahabang Pila noong {{date}}: {{count}} na tao, sa {{where}}."
  - `charts.longest_take_current*` is not in `docs/wording/2026-10-27-local-wording-application.json` (VERIFIED: 0 records), so this does not touch the approved wording record.
- Both locale files stay symmetric. The draft register and `cpdDraftWording.test.ts` are updated to match.

**Owner decision (2026-11-03, "do all recommendation"):** for the N2 singular, TL takes the more exact form. It is still a draft awaiting the owner's approval of the text.

- `simulation.current_zero_arrival_note_one`, TL: "Sa petsang ito, {{count}} bukas na queue period ang walang rekord ng customer; ipinapakita ito na walang pagdating."
- `simulation.current_zero_arrival_note_other`, TL: unchanged ("…ipinapakita ang mga ito na walang pagdating.").

**Owner delegation (2026-11-03, verbatim):** "commit you can decide the accurate word need for me, i go to work make it precise"

The parent finalizes the A6 wording as described below. The commit still waits for Kyoya's PASS, as the V2 workflow requires and the owner agreed earlier.

- W1, W2, W3, N1 and the 2a per-date longest-line sentence: kept as drafted, after the parent checked each one against the code:
  - N1: the cards are computed over every stored row of every date (`_run_summary`), and the tables and the chart filter to the chosen date.
  - W1: fewer dates is a real remedy, because the compact result fits about 25 dates under the default cap.
- N2: the `_one` and `_other` forms, as recorded above. EN one is "…{{count}} open queue period had no customer records; it is shown with zero arrivals." TL one is "…ipinapakita ito…".
- Backend `CURRENT_PER_DATE_TOO_LARGE_DETAIL`, `CURRENT_DAY_DETAIL_NOT_FOUND_DETAIL` and `CURRENT_DAY_DETAIL_MISMATCH_DETAIL` get the final EN text of W1, W3 and W2. W1's EN text keeps the "{dates} dates" pattern that the frontend parses and the pin test checks.
- In the draft register, each entry's status becomes `approved_owner_delegated_2026-11-03`.

**Parent correction (2026-11-03), after Kyoya's A6 review (PASS for the reviewed code):**
- **Tagalog plural rule (VERIFIED by Kyoya):** `Intl.PluralRules('tl')` resolves to `fil` and selects "one" for 1, 2, 3, 5, 10 and more. A TL `_one` text would therefore also show for 2, 3 or 5 periods.
  - So TL `simulation.current_zero_arrival_note_one` = TL `_other` (the existing text, "…ipinapakita ang mga ito…").
  - The "ipinapakita ito" choice is withdrawn.
  - EN `_one` stays: English uses "one" only for 1.
- **2a:** `frontend/src/components/queueSimulation/LongestLineTable.tsx` and its test are added to the files Hayato may write, because the chosen date has to be passed in from `KeyResultsView`.
- **K-A6-1:** the follow-up puts the final EN text in the backend W1–W3 constants. In the same change, the register statuses and `cpdDraftWording.test.ts` move to `approved_owner_delegated_2026-11-03`. After that, the spec, the code, the register and the test agree.
- **K-A6-3:** a check-only probe of `_run_summary` (a closed middle lane splitting a dated period). It is reported, and no backend summary code changes in this step.
