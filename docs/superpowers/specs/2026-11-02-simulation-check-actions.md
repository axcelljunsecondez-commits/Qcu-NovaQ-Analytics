# Simulation check actions

Owner request: after Check the plan, show the saved outcome and explain why; remove
excess actions such as Return to Suggested plans. This is an authorized frontend
presentation change. The previous standalone Results-chart/plan-picker assessment
is not included. No commit, push or production publication is part of this task.

Base: released main 4dd9946588938d3d9bc3a5ae1c4c64f231b33179, tree
483daab32f8bdd85aa54f9daa87dc231fb58b88e. Owned worktree branch
codex/simulation-actions-20261102. Preserve root cleanup edits and chart-release checkout.

## Evidence and design

Chrome's bounded ORDER handoff verified separate ChecksView checkPlan runs MC,
validation and Decision, while a separate Run decision card repeats that final
action. The current decision card also adds Return to Suggested plans / Continue
to Reports; legacy shared adds Open the Decision page. These destinations remain
available in ordinary application navigation. The owner's latest request supersedes
Chrome's earlier preference to retain the in-card Suggested plans link.

- Before a usable saved outcome exists, keep Check the plan as the primary action.
- With a usable saved outcome, show its existing translated status as a primary
  button. Clicking it opens the saved explanation without rerunning any request.
  Retain the existing Check the plan action as a secondary rerun; no new Recheck copy.
- Remove the separate duplicate Decision CheckLine and its Run decision button.
- Remove in-card Suggested plans / Reports navigation and legacy Open Decision link.
- Keep the plain result, separate load-uncertainty warning, saved run-basis markers,
  missing/stale/error warnings visible. Do not hide them solely inside a dialog.
- Move the existing Details from the check body into an accessible native dialog,
  using existing native-dialog patterns and approved EN/TL labels, including Close.
  Preserve all rationale, saved evidence values, failed/insufficient periods and
  current report evidence. Keep page context and visible table/period summaries.
- Use existing system.mc_basis and separate scope details if statistical context
  is needed. The newly proposed explanatory note is not an approved EN/TL wording
  pair and must not be applied. Do not claim a 95% operational-success probability,
  a measured 5% operational risk, or an acceptable plan despite a failed check.
- Dialog: labelled heading, focus inside, native focus containment, Escape/Close,
  focus return to trigger, readable scrolling, no horizontal overflow on phones.
- During requests disable result/rerun actions. A failed request, stale evidence or
  a new analysis/plan must not present an old result as a newly successful check.
  Preserve API calls/order/defaults, result derivation, validation and stale contracts.

## Scope and acceptance

Editable application paths: frontend/src/components/queueSimulation/ChecksView.tsx,
optional private DecisionDetailsDialog.tsx in that directory, narrowly scoped
frontend/src/styles/global.css, frontend/src/pages/QueueSimulationPage.test.tsx and
optional focused dialog test. No backend, engine, locale, dependency, API, schema,
fixture or global instruction changes.

Behavioral verification must cover separate and legacy shared saved outcomes, opening
details without requests, one exact check chain per rerun, no duplicate/navigation
actions, failure and insufficient/stale states, preserved scope/basis warnings,
Escape/Close/focus return and EN/TL labels. Run all frontend gates and actual local
browser checks in isolation where supported. Independent findings-only review is
required for the final changed source. No mathematical correctness or production
verification claim arises from frontend checks.
