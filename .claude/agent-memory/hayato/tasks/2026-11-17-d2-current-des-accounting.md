---
name: 2026-11-17-d2-current-des-accounting
description: D2 Current separate-lanes DES accounting fix (busy time by occurrence, Wq over started, censored counts, basis v5) in worktree d2-fix
metadata:
  type: project
---

Status: complete, UNCOMMITTED (2026-11-17); awaiting Kyoya (TASTE). No commit/push/deploy authorized.

- Checkout: NovaQ/.claude/worktrees/d2-fix, branch fix/d2-current-accounting-20261117, HEAD c2316ed4 (= origin/main).
- Scope/handoff: NovaQ/output/d2-fix-20261117/handoff.md (Chrome). Owner auth 2026-11-17 "fix it after this"; v5 basis,
  K-PR58-4 no-break exemption removed, OD-D2-1 yes, OD-D2-2 later, OD-D2-3 no wording; D5/D10 NOT authorized.
- Changed: simulation.py (core accounting, _window_busy_hours, COMPACT_ROW_FIELDS, summarize_simulation),
  workflow.py (basis v5, historical set, policy, _wait_and_line weights by started), version tests in
  test_break_check_report / test_current_per_date_compact / test_current_separate_per_date, 2 snapshot fixtures
  (patched: only busy_time/rho_sim/Wq_sim + new fields; row s2/b draining 0 -> 0.000342 h, Wq 0.0 -> None).
- New: tests/test_current_des_accounting.py (FIFO oracle with break windows), tests/test_current_des_trace_identity.py
  + fixture current_des_trace_identity_c2316ed4.json (written BEFORE engine edit; sha 5ac449fb...).
- Spec: docs/superpowers/specs/2026-11-17-d2-current-des-accounting.md. types.ts NOT changed (optional).
- Evidence: output/d2-fix-20261117/ (prefix_synthetic_c2316ed4.json, novamart_acceptance_post_fix.json,
  snapshot_field_diff_*.json). NovaMart 4 seeds match handoff table; traces identical; max dev <= 1.0e-6 h.
- Open: handoff's "tag p0 = 0.819636" for case 2 not found anywhere (archive gives 0.663437 = this fix); UNKNOWN source.
- K-D2-1 (Kyoya P3) fixed: summarize_simulation uses Wq_sim*started when wait_sum missing (compact rows); None if neither. Gate 3710p/124s; diff sha 7d062587.
- Next action: Kyoya re-check of K-D2-1 via parent.
