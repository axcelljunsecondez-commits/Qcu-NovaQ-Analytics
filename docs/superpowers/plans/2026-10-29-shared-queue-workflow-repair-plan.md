# Shared-queue workflow repair plan

Spec: `../specs/2026-10-29-shared-queue-workflow-repair.md`.
Branch: `codex/shared-queue-workflow-20261029`, starting HEAD `e2dbe5d5`.

1. Preserve current changes; reproduce the single-save/selected-plan screenshots and classify
   each result. Chrome writes failing tests for stale frontend selection where established.
2. Chrome applies the smallest selector-state repair, reusing the existing selected-status
   wording. Do not change backend selection gates or create duplicate records.
3. Chrome adds a Data and Setup recovery link to capacity/abandonment refusal. Root verifies
   the backend refusal predicates and explains the Named workflow without inventing inputs.
4. Run focused tests, then all frontend gates sequentially as resources allow. Root reruns
   focused backend refusal tests outside the Windows sandbox if its socketpair blocks.
5. Root builds the actual browser candidate, uploads the unchanged owner CSV into a fresh
   disposable workspace, saves one plan, switches saved plans, verifies selected-state
   feedback and the blocked full-day setup link. Capture actual results and limitations.
6. Review exact diff, source/test/locale boundaries, preserved hashes and final branch. Write
   an evidence-based report. No commit, push, Docker activation or production release.
