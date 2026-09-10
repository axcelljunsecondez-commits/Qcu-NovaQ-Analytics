# System remediation implementation plan

1. Preserve current changes and establish backend/frontend baselines.
2. Add regression cases reproducing missing hard constraints, capped DES, duration override, and incomplete MC metadata/default mismatch.
3. Implement additive engine/API options and result metadata; propagate effective settings through snapshots, UI, comparison and exports.
4. Consolidate defaults, disclose cost/abandonment assumptions and model/metric provenance; benchmark supported model paths.
5. Run backend suite, Ruff, mypy, frontend tests/typecheck/lint/build and available isolated integration checks. Do not mutate the running stack.
6. Record the 20-item matrix, mathematical changes, configuration inventory, actual tests, changed files and deferred data/research work.
