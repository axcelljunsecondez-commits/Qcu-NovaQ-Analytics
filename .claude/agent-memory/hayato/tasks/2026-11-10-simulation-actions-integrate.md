---
name: 2026-11-10-simulation-actions-integrate
description: Integrate Codex commit 164d85ebf (simulation actions + review screens, unreviewed) onto origin/main 702a6aa1 in worktree sim-actions-integrate; gates + browser check; no commit
metadata:
  type: project
---

Status: complete (implementation side), uncommitted, handed to Kyoya via parent 2026-11-10. Parent commits after Kyoya + owner wording approval.

- Owner authorization 2026-11-10 (REPORTED via parent, verbatim): "do it here".
- Worktree `.claude/worktrees/sim-actions-integrate`, branch `feat/simulation-actions-integrate`, HEAD 702a6aa1, MERGE_HEAD 164d85ebf (merge in progress, `--no-commit`).
- Identity at handoff: `git diff --cached | sha256sum` 54bbcb92…; `git diff` (unstaged, ResultsSummary.test.tsx only) 5d016b06…; `git diff HEAD` 85a6f1c2…; 48 files, no backend/tests/wording/output files.
- Conflict: only AnalysisSetupPage.tsx (3 hunks). Kept Codex value lists + `<section aria-label>` + facts line; re-added main refs/handlers; `applyCard` ref typed HTMLElement (was div).
- Fix: ResultsSummary.test.tsx helper `source: ResultRow[] = rows` — TS2322 VERIFIED pre-existing at 164d85ebf (git archive extract typecheck).
- Gates: tsc 0, oxlint 0, build 0. vitest run 1: 2 timeouts (QueueSimulationPage A6/B13, 10 s, load; file alone 146/146); run 2: 111 files/1126 tests pass, 735.8 s.
- Findings: FileReadSummary + review step removed (D4 CSS dead, per-hour table no longer shown); setup workbook download step removed; aggregate template choice removed; Quick Calculator fewer/more removed; nav.capstone removed; results table shows only >80% rows.
- Browser (CDP, scratch SQLite, port 18791): all listed flows passed except per-date A6 screens NOT REACHABLE with owner workbook (derives representative day).
- Gotcha: in this Git Bash heredoc, `\\n` inside Python strings reached JS as a raw newline; use String.fromCharCode(10). Use scrollIntoView behavior 'instant' before CDP mouse clicks.

## Round 2 (2026-11-10, after Kyoya FAIL)
- K-SAI-1 closed by parent (owner approval in Codex session 01a18629); recorded in untracked `docs/superpowers/specs/2026-11-03-simplify-review-screens.md` (owner text verbatim, checked line-by-line against the excerpt).
- K-SAI-3: `SavedPlanPicker` optional `onSelected` (called in select mutation onSuccess); OptimizePage/SupervisorSchedule clear saved/used/selection-problem. 2 tests per page; both fail without the wiring.
- K-SAI-4: Pagination moves focus to the other button when the focused one becomes disabled (only if the pressed button had focus). New `ui/Pagination.test.tsx`; fails on the original component.
- K-SAI-2 (owner chose "Show FAIL + reason"): LegacyPlanChecks period-by-period rows judged by a local mirror of workflow.py row_passes; non-passing rows FAIL; reason text reuses `decision.status.insufficient_evidence` (+ server validation_reason) — no new keys. Test renamed/updated + agreement test; both fail on the staged ChecksView.
- Gates: tsc 0, oxlint 0, build 0, vitest 112 files/1133 tests (843.6 s). Staged untouched (54bbcb92…); MERGE_HEAD kept.
- Not done (per instructions): K-SAI-5 cleanup; nothing staged.
