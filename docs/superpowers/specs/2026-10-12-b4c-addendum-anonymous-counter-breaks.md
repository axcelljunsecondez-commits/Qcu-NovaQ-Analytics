# B4c addendum: breaks taken by any counter on a shared line

**Status:** APPROVED by the owner on 2026-10-12 (OD-B4c-A1) and implemented on `feat/ux-u1-shell` (uncommitted). Originally PROPOSED the same day. The owner answered OD-B4c-4 = A, OD-B4c-5 = A, OD-B4c-6 = A on 2026-10-12; this addendum states the exact rules. Implemented after approval.
**Parent spec:** `2026-10-09-b4c-shared-line-breaks.md` (approved 2026-10-09). This addendum **replaces its OD-B4c-1 answer** ("break schedule per counter number") and the "Counter 3 is not open" check, and keeps OD-B4c-2 = A (named-run break rules) and OD-B4c-3 = A (simulation only, said plainly).
**Plan:** step 12.
**Evidence labels:** VERIFIED (read in code on 2026-10-12, cited), PROPOSED, UNKNOWN, NOT TESTED.

## 1. Why the parent spec cannot be built as written (VERIFIED)

| Fact | Evidence |
|---|---|
| When staffing drops, the continuous engine closes idle counters first (highest number first) and only then drains busy ones, so the counters left open are not always 1..c. Example: 3 to 2 with counter 3 busy and counter 1 idle closes counter 1. | `backend/queueing_engine/simulation/shared_continuous_des.py:351-352` (`apply_capacity`), `TRANSITION_POLICY` |
| Changing that order would change every existing result of the exponential engine and its pin test, which the parent spec forbids. | `tests/test_shared_continuous_des_pin.py` |
| A shared Setup cannot hold breaks: `breaks` entries need a `queue_id` from `queue_ids`, the schema refuses breaks for shared lines, and unknown fields are refused. | `backend/api/analysis_schemas.py:74-100, 153, 104` (`extra="forbid"`) |
| New Setup fields are serialized only when set, so saving an unchanged Setup keeps its fingerprint (existing pattern). | `analysis_schemas.py:93-100` (`QueueBreak._omit_missing_name`); fingerprint `backend/api/scenarios.py:216-219` |

## 2. Setup (PROPOSED)

- New shared-line field `counter_breaks`: a list of `{scheduled_start_time, duration_minutes, break_name?}`. Each entry means "one counter takes a break of this length from this time". It is accepted only for shared lines (separate lines keep `breaks`, unchanged) and is omitted from the saved Setup when empty, so existing Setups keep their fingerprint. Saving a break changes the fingerprint and marks earlier results as needing recalculation (the existing rule; correct, because breaks change results).
- Setup page: a "Counter breaks" list for shared lines (start time, minutes, optional name), with the wording of OD-B4c-3: "Suggested counters do not account for breaks. The full-day run shows their effect."

## 3. Engine rules (PROPOSED)

Runs without breaks are unchanged (pin test and every existing engine test). Runs with breaks carry their own engine version (`+breaks-v1` appended; with recorded service times both suffixes).

1. **Which counter (OD-B4c-4 A).** A break becomes *due* at its scheduled time and waits in a first-in, first-out list. Whenever a counter is free (accepting and idle), due breaks are served before waiting customers: the lowest-numbered free counter starts the break. So a free counter at the due time goes at once; otherwise the next counter to finish its customer takes it. No cutoff before a break; the delay (actual start minus scheduled start) is recorded (OD-B4c-2 A, named-run rule P2).
2. **Length.** A break lasts its full length from its actual start (named-run rule). At its end the counter accepts customers again.
3. **Staffing (OD-B4c-5 A).** A counter on break still counts as staffed: the schedule's counter count includes it, so a break lowers the counters serving, and no other counter replaces it.
   - Staffing drops while a counter is on break: idle counters close first (highest number first, as today), then counters on break (highest number first; the break ends early, recorded `break_end` with reason `staffing_change`), then busy counters drain (as today).
   - Staffing rises: unchanged rule (draining counters reactivate first, then closed ones reopen, then new ones).
   - Draining counters take no break.
4. **Closing (named-run rule P7).** A break in progress ends at closing (`break_end`, reason `closing`); a due break not yet started is cancelled (`break_cancelled_at_closing`). A counter on break at closing does not join the DRAIN crew.
5. **Same instant order.** Service completions, then break ends, then staffing changes, then breaks becoming due, then arrivals; after each event, free counters take due breaks first, then waiting customers (first come, first served). A break due exactly at a staffing change therefore sees the new staffing.
6. **Counting.** Time on break counts as staffed (present) server-hours, not busy; a new total `break_server_hours` is reported. Utilization of present hours therefore includes break time in its denominator, stated in the result.
7. **Trace events.** `break_due`, `break_start`, `break_end` (reason `completed`, `staffing_change` or `closing`), `break_cancelled_at_closing`, each with the break id and scheduled time; the replay rebuilds counter states from these only and its consistency check covers them.

## 4. Refusals (OD-B4c-6 A)

Before a run, for the staffing source of that run (Current or the selected plan): if at a break's scheduled start the number of breaks scheduled to be under way (start <= t < start + length) exceeds the counters scheduled at t, or no counter is scheduled at t, that run is refused and names the break ("Break at 12:00 needs a counter, but the plan has 1 counter and 2 breaks at 12:00."). The other staffing source can still run. A break outside the operating hours is refused the same way. Nothing is skipped silently.

## 5. What the replay shows

D26 states from events: Available, Serving, On break, Closed / not staffed. "Finishing customers before break" does not apply to a specific counter under rule 1 (no counter is chosen until one is free); the replay shows "Break waiting for a free counter" with the waiting time instead. The scheduled break is shown separately from the actual one.

## 6. Unchanged (protected)

Queueing formulas, `model_selection.py`, optimizers, separate-lines breaks and their 3-minute rule, the named shared run, Monte Carlo, validation, the Decision and reports. Analytical results and Suggested plans keep ignoring breaks and say so (OD-B4c-3 A).

## 7. Tests (written before the engine code)

1. No breaks: pin test and every existing engine test unchanged; an empty `counter_breaks` saves the Setup with the same fingerprint as before.
2. Free counter at the due time: break starts on time and lasts its full length (hand-computed).
3. All counters busy: the first counter to finish takes the break; delay recorded; full length from the actual start; the waiting customer is served after the break starts on that counter.
4. Two counters, one break: service continues on the other counter; time-average counters serving drops by the break length.
5. Staffing drop during a break: idle closes first, then the counter on break (`staffing_change`), then busy drain.
6. Closing: a break in progress ends at closing; a due break not started is cancelled; a counter on break does not join the DRAIN crew.
7. Refusals of section 4, per staffing source, with the break named.
8. Replay states equal the engine's events; replay of a run with breaks and recorded service times together.
9. A real-route test: save a shared Setup with a break through `/analyses`, upload customer records, run the full day, replay the break.
10. Mutation testing of the break path.

## 8. Decision for the owner

- **OD-B4c-A1:** approve this addendum (sections 2-7).
