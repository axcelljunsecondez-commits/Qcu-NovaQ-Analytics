---
name: 2026-11-17-break-check-pdf
description: Option A break check stored at save + printed in PDF/Excel, plus PR58 follow-ups K-PR58-1..5 and 3 locale changes
metadata:
  type: project
---

Status: complete, UNCOMMITTED; awaiting Kyoya (2026-11-17).
Gates: pytest 3685p/124s/0f; ruff+mypy clean; vitest 1150/1150; tsc, oxlint, build ok. git diff sha256 92c400c4 (12 files) + untracked tests/test_break_check_report.py sha a3946884.
NovaMart sample: B8 -0.8809 (-1.9872..0.2253) n=5 no_clear_difference; 7 moves; save 1.29 s; plan PDF 5 pp, full PDF 10 pp; results 176,362 B of 524,288.
Checkout: NovaQ/.claude/worktrees/break-check-pdf, branch feat/break-check-pdf-20261117, start HEAD 37381fed5 (origin/main, PR58). UNCOMMITTED.
Spec (owner-approved labels): NovaQ/output/pdf-break-check-labels-approved.md
Changed: backend/api/{plan_breaks,scenarios,workflow,plan_reports}.py, backend/reports/{plan_report,report_pdf}.py,
frontend locales en/tl, RunBar.tsx, simulationContext.ts, QueueSimulationPage.test.tsx,
tests/test_break_check_report.py (new), tests/test_current_per_date_compact.py (v3 expectation per K-PR58-4).
node_modules = junction to sim-actions-integrate/frontend/node_modules (package-lock sha 2d1bea3c matches).
Design choices to flag: whole-day table headers "Item/Uploaded breaks/Moved breaks", Excel B8 headers
"Value/95% low/95% high/Runs", runs headers "Random seed/Change in average wait (minutes)" are NOT in approved list.
Breaks table kept in all states (B17 heading when plan breaks differ / no saved check). B14 only for descriptor+no moves.
_current_evidence_policy(setup=None) fails closed (v3 historical).
Sample driver: session scratchpad novamart_chain.py; outputs NovaQ/output/break-check-20261117/samples-novamart/.
No commit/push/deploy authorized.

Round 2 (owner 2026-11-17, Kyoya PASS on 92c400c4): B5/B6 'per period' text; break-check section replaces older breaks table in PDF (Excel had none); K-BC-1 B17 only when breaks differ; extra labels owner-approved. Diff sha 63295bcb, untracked test sha a8f1b495. pytest 3685p/124s; ruff/mypy clean; frontend not rerun (no frontend change). Samples regenerated: plan 5 pp, full 10 pp, save 1.26 s.
