# B4c: Breaks on a standard shared line (continuous run)

**Status:** APPROVED by the owner on 2026-10-09 (OD-B4c-1 = A per-counter break schedule in the shared Setup, OD-B4c-2 = A the named shared run's approved break rules, OD-B4c-3 = A simulation only, said plainly). This changes simulation behaviour: implementation is plan step 12 and needs the owner's GO for that step.
**Parent spec:** `docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md` (D26, backend item B4c). Builds on B4a and B4b (both approved 2026-10-09).
**Plan:** step 6 (this spec), step 12 (implementation).
**Evidence labels:** VERIFIED (read in code at `ef05827e`, cited), PROPOSED, UNKNOWN, NOT TESTED.

## 1. Goal

Let a shared-line analysis say when counters take breaks, and show in the full-day run what really happens: a counter finishes its customer, goes on break, comes back; the replay shows the counter states of D26 (Available, Serving, Finishing customers before break, On break, Closed / not staffed) from simulation events only, with the scheduled break shown separately.

## 2. What exists (VERIFIED)

| Fact | Evidence |
|---|---|
| A shared Setup cannot hold breaks: the schema refuses them for anything but separate lines. | `backend/api/analysis_schemas.py:152-153` |
| The anonymous continuous engine changes capacity only through staffing segments: a decrease closes idle servers first (highest number first) and otherwise lets the highest-numbered busy servers drain; there is no per-counter break. | `backend/queueing_engine/simulation/shared_continuous_des.py:77-84` (TRANSITION_POLICY) |
| The named shared engine already has owner-approved break rules for a shared line: no pre-break cutoff (a due break waits for the current service to end, and the delay is recorded, P2); a break lasts its full duration from its actual start; at closing a break in progress ends and pending breaks are cancelled (P7). | `backend/queueing_engine/simulation/shared_named_des.py:84-124`; `backend/queueing_engine/simulation/shared_employee_states.py:119, 398-400, 531` |
| Separate lines use a different rule: a lane drains for 3 minutes before a scheduled break. | `backend/queueing_engine/config.py:28-30` |
| Analytical results and the shared optimizer work per period and have no notion of breaks. | `backend/queueing_engine/services/optimization.py:185-200`; spec §3.4 |

## 3. Decisions for the owner

### OD-B4c-1: how breaks are entered

| Option | What it means |
|---|---|
| **A. Break schedule per counter in the shared Setup (recommended)** | A new list in the shared Setup: counter number, start time, minutes. Because breaks change results, saving them changes the Setup and marks earlier results stale (the existing fingerprint rule, correct here). |
| B. Only as fewer counters in a period | No new input; the user lowers the counter count for the break period. No "Finishing customers before break" or "On break" states can be shown, and breaks shorter than a period cannot be expressed. |

### OD-B4c-2: what happens when a break is due

| Option | What it means |
|---|---|
| **A. Same rules as the named shared run (recommended)** | No pre-break cutoff: a counter serving a customer finishes that service, then starts its break; the delay is recorded. The break lasts its full length from its actual start. At closing a break in progress ends and pending breaks are cancelled. These rules are already approved for shared lines. |
| B. Separate-lines rule | The counter stops taking new customers 3 minutes before the scheduled break. |

### OD-B4c-3: how breaks relate to plans

| Option | What it means |
|---|---|
| **A. Simulation only, said plainly (recommended)** | Analytical results and suggested plans keep ignoring breaks (as today) and say so: "Suggested counters do not account for breaks. The full-day run shows their effect." |
| B. Reduce counters in the analytical model during breaks | Changes analytical math and the optimizer: its own spec. |

## 4. Engine change (PROPOSED)

- Per-counter break events in the anonymous continuous engine: at a break's due time the named counter (by number in the staffing in force) stops taking new customers; if serving it finishes first (Finishing customers before break); then On break for the full length; then back to accepting if still scheduled.
- A counter number above the staffing in force at the break time is refused at validation ("Counter 3 is not open at 12:00").
- Runs without breaks are unchanged: the pin test and all existing engine tests pass. Runs with breaks carry their own engine version string.
- Trace events: `break_due`, `break_start`, `break_end`, `break_cancelled_at_closing`, with the counter number and the scheduled time, so the replay builds D26 states from events only.

## 5. Tests (PROPOSED; written before the code)

1. No breaks: identical results to today (pin test and engine tests).
2. Idle counter at break time: break starts on time, lasts its full length.
3. Busy counter: break starts at that service's completion; delay recorded; full length from actual start.
4. Break overlapping closing: in progress ends at closing; not yet started is cancelled.
5. Counter number not open at the break time: refused with the message above.
6. Replay states equal the engine's events (consistency check extended to breaks).
7. Setup with shared breaks: saving changes the fingerprint; separate-line break validation unchanged.
8. Mutation testing of the break path.

## 6. Risks

- Changes simulation behaviour and the Setup schema for shared lines; needs separate authorization and a full regression.
- Interaction with B4b sampling must be tested together (a counter finishing before break uses the sampled duration of its current customer).

## 7. Acceptance

Owner answers (2026-10-09, in chat): OD-B4c-1 = **A**, OD-B4c-2 = **A**, OD-B4c-3 = **A**. Implementation is plan step 12, after B4b.
