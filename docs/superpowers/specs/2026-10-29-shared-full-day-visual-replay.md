# Shared queue: full-day results and visual replay

Date: 2026-10-29. Owner direction: remove the period-by-period replay and use a visual
simulation of one complete operating day. This supersedes B4a's retained older shared
run panel. It does not authorize changing queueing models or simulation algorithms.

## Verified source and scope

QueueSimulationPage currently renders ContinuousSection and an older-run panel for shared
queues. ContinuousReplay has clock, playback controls and counts, but no queue-floor visual.
The existing continuous playback API already returns independently checked events, customer
timelines and server-state intervals (shared_playback.build_playback). Nothing needs to be
invented, simulated in the browser, or added to the backend response.

## Required outcome

- Shared-queue Results and Replay use only saved full-day runs. Remove the older shared
  RunBar/results/replay panel, including its Run period by period action. An unsupported or
  missing full-day run stays explicitly refused/not run; no fallback replay is substituted.
- Retain the existing Key Results, Replay and Checks/Decision navigation. Keep ChecksView
  connected outside the retired panel so removing it does not delete the Decision workflow.
  Existing check algorithms, historical evidence and server choice of Decision basis remain.
- Retain separate-queue and single-server behavior. Named employee mode is unchanged.
- Add a shared queue-floor visual to ContinuousReplay, driven by its existing day/time/seed
  selection and controls. Show arrivals, the one FIFO waiting line, actual serving counters,
  counter availability/break/closure, completed customers and customers unserved at closing.
- Every customer/counter identity and state comes from the selected playback's verified
  timelines. Use half-open recorded intervals, correct closing outcomes and one continuous
  clock across periods. Reconcile the visual against recorded event counts. Missing or
  inconsistent timelines display the existing unavailable state; no synthetic dots/IDs.
- Keep internal automatic replications, provenance, metric summaries and actual playback-day
  identification. The floor depicts one recorded execution; it does not animate an average
  or stitch multiple days/independent periods together.

## Presentation and protected boundaries

Reuse existing live-floor CSS, customer tokens, counter cards, state labels and both locale
catalogs. Reuse existing reduced-motion behavior; pause/seek has no decorative entry motion.
Use bounded customer-token lists with a truthful remaining count. Do not add dependencies.
No new product wording is necessary. DRAINING counters still serving customers display the
existing Serving label and retain their exact recorded state for inspection; they are never
shown as available. Closed counters are derived from gaps in the server's recorded intervals.

Permitted frontend scope: QueueSimulationPage, ContinuousRun, a new ContinuousQueueFloor
view, API types for existing response fields, a read-only timeline projection helper and
their tests; minimal scoped CSS if needed. Also this spec, plan, report and owned evidence.
Backend/API contracts, data, formulas, statistical methods, seeds, Decision/report algorithms
and previously repaired plan-selection behavior stay unchanged. No release/commit/push.

## Verification

Cover absence of the old shared panel on all three pages, no legacy DES requests, preserved
separate/single-server and Checks/Decision behavior, and full-day empty/refused states.
Exercise actual customer IDs and counter states across period boundaries, DRAIN and hard
cutoff, breaks, end of service, forward/backward seek and missing/inconsistent timelines.
Retain legacy renderer component tests separately from current shared-page expectations.
Run focused/full frontend gates, relevant fixed DES/replay numerical checks, compare protected
hashes and the unchanged owner-CSV numerical result, and inspect the real built local replay
at desktop/phone widths and both themes. Historical gate results must stay labeled historical.
