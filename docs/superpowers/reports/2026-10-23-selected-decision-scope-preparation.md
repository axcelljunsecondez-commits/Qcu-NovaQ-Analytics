# Selected Separate Decision scope: preparation verification

Date: 2026-10-23. Status: specification preparation COMPLETE; application correction NOT IMPLEMENTED; numerical seed sensitivity OPEN; production deployment NO-GO under the repair-first instruction.

## Candidate and permitted work

Candidate: `C:/Users/Administrator/.codex/worktrees/novaq-release/NovaQ`, branch `codex/supervisor-schedule-20261023`, HEAD `151486ee04147f013857f69fe8ce77d899388660`. The primary checkout is a different checkout. This phase prepares a bounded correction and its tests; it does not authorize statistical integration or release.

New documents in this phase:

- `docs/superpowers/specs/2026-10-23-selected-decision-scope.md`
- `docs/superpowers/plans/2026-10-23-selected-decision-scope.md`
- This preparation record.

New supporting evidence is under `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/output/selected-decision-scope-spec-20261023/`. Existing supervisor changes and earlier research files are preserved. No source, tests, configuration, fixtures, database, Docker resources or Git history were changed by this preparation.

## Findings and proposed correction

| Item | Evidence and classification | Current disposition |
|---|---|---|
| CONTEXT-001 | VERIFIED source defect: `DecisionEndpoint.tsx:58` passes `separate:false`; its wrapper computes Separate context but does not pass it. The actual formatter therefore selects the Shared higher-cost sentence for a conditional Separate result. | OPEN. Proposed explicit line context and accurate selected facts. No repaired browser behavior claimed. |
| SCOPE-001 | VERIFIED copy: selected conditional recommendations and the Separate plain answer focus on accepting cost. The source retains DES mean-load metadata without a completed assessment of uncertainty in those means. Interpreting cost as the only remaining consideration is an INFERRED communication risk. | OPEN. Proposed saved-run wording and a visible unassessed-mean-load notice in UI and both final Separate report paths. |
| SEED-001 | Existing numerical finding, documented in the budget-study report and preserved strict-xfail regression. This phase executes no new DES/MC experiment. | OPEN. Proposed disclosure/context changes cannot close it. |

The current MC already varies load around a supplied mean. The missing assessment concerns uncertainty in that supplied mean. The proposal must not state that load variation was untested, invent interval results, import the offline three uncertain pairs into a live analysis, or change raw statuses/calculations.

## Executed preparation checks

Evidence paths below are relative to the output directory named above.

| Check | Actual result | Limit |
|---|---|---|
| `source_probe.cjs`, with `source-probe.json` / `.log` | PASS for reproducing the context finding from the actual TypeScript AST and actual transpiled formatter; process exit 0. | Confirms a defect, not a repaired regression. No browser or statistical execution. |
| `specification-check.json` at 2026-10-23T13:18:03Z | PASS: 15 existing referenced paths checked; proposed `backend/reports/selected_scope.py` explicitly absent/new; four probe-source hashes unchanged; both specification/plan documents free of trailing whitespace. | Document/source integrity, not application acceptance. |
| Same integrity check against the registered budget-study baseline | PASS: all 467 pinned source/test/configuration/fixture files unchanged. | Does not make the whole dirty worktree clean; earlier supervisor changes remain. |
| Read-only Git scope check at 2026-10-23T13:21:36Z | PASS: HEAD above unchanged; staging empty; `git diff --check` exit 0. Existing modified/untracked scope plus the new specification and plan observed. | `git diff --check` checks tracked diffs; new documents were checked separately. No commit, fetch or push. |

Specification SHA-256: `1dd5af87e5c5a6304c857e08b787811217c2e038136672c925ff9f0da8042b4c`.

Plan SHA-256: `eb816d01d53e0d311e7925c21ebaa405ac0c05db7abc9869bea2e940e9d4875d`.

The earlier document-write attempt was not executed because automatic approval review hit a usage limit. The normal reviewed write succeeded on resumption. This was a review-availability failure, not a determination that the action was unsafe.

## Remaining gates and recommendation

GO to review the concrete Phase-A scope: correct Separate context and qualify configured-run interpretations, including report parity. Implementation requires approval of that bounded scope, followed by the plan's behavioral, preservation, export, full regression and compiled-browser checks.

NOT TESTED in this preparation: corrected application behavior, corrected PDF/Excel output, compiled responsive/localized display, native/manual checks and production behavior. Application regression suites were not rerun because no application files changed. Previous research/test records retain their own dates and limitations.

NO-GO for claiming a numerical seed repair, operational safety, a new approved statistical method, raised run limits or production deployment under the current repair-first condition. No implementation, commit, push, rebuild or deployment occurred. No deviation from this preparation scope is claimed.
