---
name: 2026-11-16-followups-reports-pdf-cobalt
description: Owner #1 follow-ups K1 (Reports inconclusive periods), K2 (PDF per-pair rows Excel-only), K3 (missing-evidence hint), Cobalt leftovers 4a-4c, plus before/after owner sample exports
metadata:
  type: project
---

Status: complete, UNCOMMITTED (2026-11-16); awaiting Kyoya via parent. No commit/push/deploy authorized.

- Checkout: NovaQ/.claude/worktrees/followups, branch fix/followups-reports-pdf-cobalt-20261116, HEAD 2443005482a4 (origin/main), 13 modified files, no untracked; `git diff | sha256sum` = b36a9091fd79a8c3.
- Owner auth 2026-11-16 (REPORTED via parent): "start the #1 follow-ups"; PDF per-lane detail Excel only. No wording changed.
- K1: full_report.separate_full_sections decision gains additive `inadequate_periods` (raw from stored selected Decision, workflow.py ~3847; None if absent). ReportsPage maps separate -> decision.inadequate_periods.
- K2: per lane-period check rows get additive `excel_only: True`; report_pdf._full_pages skips them. Sample: full PDF 11 -> 5 pages (18 pairs); XLSX identical except timestamps/random generation tokens.
- K3: validation queue rows carry no simulation_supported/error (workflow.py ~3653-3693); ChecksView joins MC rows of the exact job (mcEvidence.id === validation.mc_job_id).
- Cobalt: .icon-btn removed from one selector list; MASTER s7 + plan step 4 dated notes; SupervisorSchedule Continue -> btn-primary.
- Gates: pytest full 3635p/125s (pre-annotation run) + 33p targeted after; ruff/mypy clean; vitest 110 files/1140; tsc/oxlint/build ok.
- Round 2 (owner 2026-11-16 "excel only for plan report too"): report_export separate PDF skips provenance keys with SELECTED_LOAD_ASSESSMENT_PREFIX (new const in selected_scope.py); Excel unchanged. Sample selected PDF 6 -> 3 pages. Diff sha 2fd2e202 (16 files).
- Round 2 gates: full pytest 3635p/125s exit 0 on final source; ruff/mypy clean; report tests 41p.
- NovaMart owner file (read in place, sha256 29781130): with SupervisorSchedule defaults (70%, breaks off) the plan check is INFEASIBLE at 11:00-12:00 (blockers break_changes_off, staffing_check) -> page disables Use this Plan -> no reports. BLOCKED pending owner choice; throwaway DBs deleted. Owner then chose 85% breaks off: still INFEASIBLE at 11:00-12:00 (same message) -> stopped, no exports; BEFORE summary removed per owner. Owner then chose breaks ON 85% max 120: COMPLETE, 7 moves applied, chain ran; Decision insufficient_evidence, 13/13 periods inadequate (60/60 checks); AFTER exports in output/followups-20261116/samples-novamart (full PDF 9 pp, plan PDF 4 pp, selected PDF 4 pp); now==plan columns (both on moved-break draft, supervisor_schedule.py 73-101).
- Owner Q "simulated vs with the plan identical": VERIFIED by design. Endpoint forces full_coverage=True (workflow.py ~2316); each period has one candidate = scheduled lanes (separate_optimization.py ~1952-1960, ~2073-2085; spec 2026-09-18-separate-representative-day Known limitation). plan_report.build_separate_plan_model reads both columns from by_count candidates, so they are the same dict. Counter changes for separate plans are unreachable until the lane-closing spec (draft) ships.
- Samples: NovaQ/output/followups-20261116/samples (generator in session scratchpad, SYNTHETIC names).
- node_modules junction frontend/node_modules -> sim-actions-integrate/frontend/node_modules; remove with rmdir before deleting worktree.
