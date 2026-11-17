# 2026-11-10 remove dead review leftovers (K-SAI-5)

Status: complete (UNCOMMITTED), awaiting Kyoya TASTE via parent. Ownership released to parent.
Goal: remove dead CSS/code/orphaned locale keys left by PR49 removals (Kyoya K-SAI-5). Owner authorized "clean it up" 2026-11-10 (REPORTED by parent).
Checkout: .claude/worktrees/cleanup-leftovers, branch chore/remove-dead-review-leftovers-20261110, HEAD 9baeee43 (main/PR49), unchanged. Dirty identity: `git diff | sha256sum` = 584a2f60...20fa, 19 files, +3/-1181, nothing staged.
node_modules: junction -> .claude/worktrees/sim-actions-integrate/frontend/node_modules (package.json/lock identical modulo CRLF). Remove with `rmdir`, never rm -rf.

Method (reusable): import-graph reachability from src/main.tsx; locale orphans = keys quoted-literal in `git archive 9baeee43^1` src but not now, then filtered for template/concat heads, $t nesting, public, backend, register. Locale JSON is flat dotted keys, CRLF, JSON round-trip byte-identical. Vitest output is buffered under non-TTY; full run ~20 min.

Changes: deleted 10 files (ResultsChartTabs, ResultsCharts, BusyLevelCard(+test), SeparateScheduleCard, resultsTabs, busyLevel(+test), cashierWorkload(+test)); removed neighbourCounters(+its it-block), downloadSetupWorkbook(+downloadReport import), dayStrip/periodWarnings(+worse, BAND_ORDER, StripPeriod, PeriodWarning, 2 describe blocks); file-read* + 3 .supervisor-evidence CSS refs; 96 keys en+tl (2203->2107).
Kept: 6 wording-register keys; SimulationModeSwitch + Named; periodDemand.ts (dead pre-PR49); periodsNeedingAttention (KeyResults orphan, not on list); file-missing-choices CSS (dead pre-PR49); CSS used only by deleted components (busy-cell, busy-warnings, cv-*, hbar-legend*, hbar-marker, results-chart-list); 7 test mocks still name downloadSetupWorkbook.
Gates: typecheck 0, lint 0, vitest 109 files/1112 tests pass (1177.68 s), build 0, en/tl equal 2107. dist 45,259,747 B/88 -> 45,227,359 B/89 (new 538 B reports chunk).
Round 2 (parent cleared follow-ups): removed periodDemand(+test, 5 tests), periodsNeedingAttention/AttentionPeriod(+2 tests), file-missing-choices (3), busy-cell/busy-warnings, cv-tabs/tab-panel/ribbon/t/l/v/detail, hbar-legend*/hbar-marker, results-chart-list; narrowed :is(.status-badge, .busy-cell) -> .status-badge (same specificity), .hbar-fill-alt list, font-size :is list.
Still kept (unused, not authorized): busy-cell-time, busy-swatch, busy-period, chart-data-table, hbar-fill-alt (dead pre-PR49).
Round-2 gates: typecheck 0, lint 0, vitest 108 files/1105 pass (1100.13 s), build 0, en/tl 2107 equal; dist 45,225,408 B/89. Diff hash 5e1c3093...e4f9, 22 files +11/-1415.
Next: Kyoya review.
