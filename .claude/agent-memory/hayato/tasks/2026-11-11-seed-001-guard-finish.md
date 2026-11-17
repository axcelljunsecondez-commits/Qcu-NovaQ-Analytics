# 2026-11-11 SEED-001 correctness guard — finish non-held scope (+ OQ-1/OQ-2 owner answers)

Status: complete (UNCOMMITTED, unstaged; awaiting Kyoya via parent). No stage/commit/push/deploy done.

- Checkout: C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ/.claude/worktrees/seed-001-integrate
- Branch feat/seed-001-guard-20261111, HEAD 6d46a01a4, MERGE_HEAD ddb1560a3 kept (merge --no-commit open).
- Staged baseline (git diff --cached | sha256sum) = 727d44dc...4250, unchanged. My work is unstaged + 1 untracked test file.
- frontend/node_modules = junction to sim-actions-integrate/frontend/node_modules (identical package.json + lock hashes).
- Owner answers 2026-11-11 (via parent): OQ-1 (a) missing_evidence [] + approved recommendation sentence in selected Decision
  "insufficient" branch only; OQ-2 time+lane only when guard FAIL and raw MC pass; OQ-3 keep stale text; OQ-4 keep scope details.

Changed: backend/api/{reports.py (I001), workflow.py (OQ-1 branch only)}, backend/reports/{full_report.py (I001, R-3),
separate_report.py (R-4)}; tests/{test_b8_full_report.py, test_selected_plan_decision.py, test_separate_report.py},
new tests/test_selected_load_reports.py; frontend api/{types.ts (SELECTED_LOAD_METHOD_V1 const + optional types), workflow.ts,
reports.ts}, ChecksView.tsx, DecisionEndpoint.tsx, ReportsPage.tsx, 3 test files, en/tl locale (1 key each).
Constant lives in api/types.ts because tests vi.mock api/workflow wholesale.

Evidence (NovaQ/output/seed-001-repair-20261110/evidence): assessment_storage_scan_v2.py + assessment-storage-scan-v2.{json,log}
(default cap: 210 pairs persisted, 220 refused 413 at DES; fixture static 10 lanes), report_pdf_layout_v1.py + report-pdf-layout-v1*.{pdf,json},
hayato-pg-focused-v1.log (INVALID: WSL distro stopped; Git Bash mangled /mnt/c path -> use MSYS_NO_PATHCONV=1),
hayato-pg-focused-v2.log (PG18 473 passed), hayato-full-backend-v1.log.
WSL PG: cluster 18/novaq_test :55432, keepalive script in old session a9650a77 scratchpad/wslpg (03_keepalive.sh, run as root).

Next: Kyoya review of the unstaged diff; Reports page shows "insufficient_none" for v1 inconclusive (facts lack periods) - owner/Chrome call.
