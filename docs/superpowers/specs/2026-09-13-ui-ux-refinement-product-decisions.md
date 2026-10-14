# NovaQ UI/UX Refinement Product Decisions

**Status:** Approved product baseline
**Date:** 2026-09-13
**Scope:** Constraints for the planned full UI/UX refinement
**Implementation status:** Not started by this document

## Purpose

This document resolves the product questions that must be settled before NovaQ's full UI/UX refinement. These decisions are authoritative for subsequent specifications, plans, copy, interaction design, tests, and report presentation.

They do not authorize changes to queueing formulas, centralized model selection, optimizer mathematics, simulation behavior, persisted evidence, or production API contracts.

## 1. Onboarding

Onboarding is required once for a first-time authenticated user. A user who has completed onboarding must not be forced through it again. The same onboarding experience must be replayable voluntarily from Help without resetting completion state.

Onboarding must be placed deliberately inside the authenticated entry flow and must collect real user preferences that the application can honor. The interface must not claim that a preference was captured when it saves a placeholder such as `operation_type: "other"` or an empty terminology object.

## 2. Queue behavior and supported scope

The product decision is separate FIFO cashier queues. Priority-class queueing is outside the current capstone scope and must not be represented as supported.

The current repository does not yet satisfy the separate-queue decision: the analysis schema labels separate queues unsupported and the current DES/playback contract is a shared FIFO queue. This is an explicit product/implementation conflict, not permission to relabel the shared implementation as separate. Until a separately approved analytical feature specification implements and verifies separate FIFO queues end to end, UI refinement must disclose the current limitation, must not claim separate-queue execution, and must not silently map priority or separate-queue input to shared FIFO.

## 3. Optimization objective

The current optimizer minimizes configured total cost among candidates that satisfy the enabled stability, utilization, wait-time, and server constraints. This behavior remains authoritative.

A user-facing short-wait preset is a constraint profile. Its copy must explain which targets it tightens. It must not be described as an independent minimum-wait objective unless a mathematically distinct objective function is separately specified, implemented, tested, and approved.

Candidate output must be described as model-recommended or proposed until it has passed the required simulation, validation, and Decision stages.

## 4. Cost horizon, projections, and ROI

NovaQ reports modeled cost for the explicitly analyzed operating period.

Monthly and annual values are projections. Whenever shown, the interface and export must disclose:

- the analyzed base period;
- the scaling factor or operating-day assumptions;
- excluded days or holidays;
- that the values are modeled projections rather than observed costs; and
- that modeled staffing cost is not automatically equivalent to payroll or cash savings.

NovaQ must not label a cost difference as ROI unless an explicit investment cost is defined. Without investment cost, the product may describe modeled cost difference, projected savings, or payback inputs as appropriate, but not return on investment.

## 5. Report preview fidelity

The report preview must correspond exactly to the sections available in the selected generated export format.

A preview section may be added only after:

1. its underlying data or calculation exists;
2. its provenance and units are defined;
3. the export generator includes it;
4. the relevant format is covered by tests; and
5. the UI preview is derived from, or validated against, that export contract.

The UI must not promise simulation validation, ROI, methodology, appendices, or other sections that are absent from the generated file.

## Required downstream acceptance criteria

Any subsequent UI/UX refinement specification and implementation plan must:

- identify every affected route, component, translation key, test, and export format;
- keep analytical truth and user-facing claims aligned;
- preserve the centralized model-selection and optimizer contracts;
- keep simulation playback and aggregate DES evidence equivalent;
- distinguish observed, modeled, optimized, simulated, and projected values;
- preserve unknown user input instead of inventing assumptions; and
- verify report-preview fidelity for PDF and Excel independently.

## Explicitly unresolved for later parts

The following implementation choices are resolved by the later repository-grounded refinement specification and plan, not by this decision record alone:

- the final page/component layout and visual system;
- the exact projection controls and disclosed scaling formula;
- whether generated reports will be expanded or their previews reduced; and
- the implementation sequence and regression-test plan.
