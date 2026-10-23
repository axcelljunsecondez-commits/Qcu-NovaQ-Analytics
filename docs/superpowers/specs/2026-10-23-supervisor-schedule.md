# Supervisor schedule check and break review

APPROVED SPECIFICATION: owner approved the visual example, then selected "Full screen and combined workflow" on 2026-10-23. Local implementation only; no commit, push, rebuild or deployment authorization is inferred.

## Verified starting point
Base: 151486ee04147f013857f69fe8ce77d899388660. The separate staffing route evaluates the configured full-coverage schedule with existing DES; break placement is a separate greedy peak-load search. Its legacy Apply writes breaks without rerunning staffing feasibility. Source: backend/api/workflow.py, run_separate_optimize, run_separate_break_optimize, apply_separate_breaks; services/separate_optimization.py and break_optimization.py. Scenario saves independently rerun the current Setup (api/scenarios.py). A draft-break schedule therefore cannot be saved as a verified snapshot against the old Setup.

## Scope
Replace only the separate-queue Suggested plans screen with a supervisor-oriented settings -> check -> review -> confirmed break save flow. Shared-queue optimization is preserved. Keep existing legacy API contracts; add a separate supervisor preview/apply contract, no schema migration or new dependency. Use existing semantic tokens, English and Filipino, keyboard/focus support, light/dark and responsive layouts.

Settings: planning dataset; busy limit 40-90% with five percentage point slider moves and exact numeric entry (including 72.5); optional break changes (off by default); max move 0-240 minutes in 15-minute steps; existing costs and demand what-if retained under advanced settings. Blank input is invalid, never zero-filled. Seed remains 42. Existing staffing DES defaults and break comparison defaults (5 paired runs) remain unchanged and are disclosed separately.

## Additive API
POST /analyses/{id}/workflow/optimize/separate/supervisor/preview accepts the existing staffing options plus allow_break_changes and max_shift_minutes.
- Authorize the analysis and owned planning dataset; reject empty/invalid data.
- Break-off: evaluate current Setup without writing.
- Break-on: use existing placement/comparison; construct a validated in-memory Setup preserving order, cashier, length, name and original-start anchor; evaluate it through the existing full-coverage staffing evaluator.
- Demand what-if with moved breaks is explicitly unsupported: reject a multiplier other than 1 rather than compare different demand assumptions.
- Return schedule, engine identity, setup/dataset-bound deterministic preview hash, break evidence, eligibility and explicit blocking reasons. No persistent write or job/scenario creation.

POST .../supervisor/apply accepts that request and preview hash. It recomputes the authoritative preview; refuses changed inputs, Setup, dataset content/generation, changed results, non-current planning data or ineligible output. Immediately rechecks freshness and uses a conditional Setup update to refuse a concurrent Setup write. Only validated break start/anchor fields change. Return the recomputed schedule and updated analysis. A new upload after the final current-data check can naturally make evidence stale; no claim of serializable upload isolation is made.

## Eligibility / claim boundary
Apply requires actual moves, latest valid planning file, staffing overall COMPLETE, all 15-minute break slots at/below the chosen busy limit, conserved simulated customers, and an available paired wait interval not indicating longer waits. An interval crossing zero is shown as "No clear change in wait", requires explicit confirmation, and is not a shorter-wait claim. These are workflow guards using existing evidence, not a new optimizer, safety rule, statistical method or closure of seed sensitivity. No global optimum or operational safety claim.

One limit is passed explicitly to both existing evaluators; staffing uses replicated per-lane busy shares, while break placement uses pooled 15-minute load. Display both checks with their distinct basis. Never infer one check from the other. Display existing reasons when blocked.

## Review and persistence
Show check status, changed breaks, simulated wait and interval, and expandable schedule/evidence details. No change is saved by Check. Disable saving a plan while proposed break moves remain unapplied; failures/stale results disable use. Confirm explains earlier evidence becomes stale. Cancel/Escape restores trigger focus. After confirmed break save, invalidate Setup/Current/workflow/scenario caches and offer the existing verified scenario Save / Use this plan path (no automatic selection). Parameter or Setup changes invalidate the local result; async results must not become applicable after inputs change.

## Verification / acceptance
Test read-only preview, both break modes, exact percent entry, invalid/blank values, no moves, staffing/break/wait/conservation blockers, stale Setup/data/parameters and malicious proposed times, ownership/auth, confirmed write preserving all other Setup fields, evidence staleness, scenario save rerun, concurrent Setup refusal. Run repository backend/frontend/lint/type/build gates. Inspect actual local UI at 375/768/1024/1440, narrow landscape, zoom, keyboard, light/dark, EN/TL, reduced motion. Record actual outcomes and any unavailable gates; do not report mockup tests as implementation verification.

Protected: all queueing formulas, model selection, DES/MC methods, optimization objectives, CI definitions, exports, auth/CSRF, database schema and legacy contracts. Unrelated dirty worktrees and production untouched.

## Approved one-panel tabs amendment (2026-10-23)

Owner approved the interactive schedule-step-tabs visual with "like this execute this". Replace the stacked presentation with clickable 1 Settings / 2 Review / 3 Confirm tabs. Exactly one panel is visible and accessible at a time; inactive panels retain their field values but are hidden from focus and the accessibility tree. All three tabs remain inspectable before a check; Review and Confirm explain that a check is needed and offer a return to Settings rather than inventing results.

Check succeeds into Review. Review contains the existing evidence and a Continue to confirm action. Confirm contains the final break-save explanation/action and existing plan save/selection controls. The Confirm panel replaces the modal confirmation; entering it never writes, and the explicit Save break changes button still calls the unchanged rechecking endpoint. Back to review and Escape from Confirm return focus to the Review continuation. Arrow Left/Right, Home/End and a roving tab stop support keyboard navigation. Navigation alone must never calculate, apply, save or select. Input/Setup/data changes and failed requests keep all existing persistence guards. Preserve typed percentage, draft fields and checked evidence when navigating. No backend or analytical changes are authorized by this amendment.

Additional acceptance: single-panel visibility and focus isolation, prerequisite placeholders, mouse/keyboard tab navigation, retained values, stale/blocked saves, async freshness, confirmation cancel/back/Escape, actual checked apply and plan save/selection; both languages/themes at 375/768/1024/1440 px, narrow landscape, text scaling and reduced motion. Permitted additional edits: this spec/plan/verification record; SupervisorSchedule.tsx and its tests; dependent SetupChangeWorkflowCache.test.tsx navigation only; scoped global.css and symmetric EN/TL strings.
