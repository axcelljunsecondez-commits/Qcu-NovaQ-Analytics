# Shared DES automatic replications — implementation plan

Date: 2026-10-29. Scope: the owner's repeated instruction to remove repetition management
and use the separate-DES one-action pattern while preserving shared-queue mathematics.

1. Save current hashes/diff for existing dirty files and protected backend/engine sources.
   Keep earlier plan-selection/recovery fixes and all unrelated untracked files intact.
2. Add meaningful helper/page regressions first: absent repetition input, unchanged default
   request, server default/limit variations, exact customer-budget boundaries, impossible
   day, invalid metadata, reproducible seed and retained metric/replay/Decision behavior.
   Demonstrate the new expectations fail on the baseline.
3. Derive automatic count from compatibility metadata in the existing frontend helper.
   Remove editable count state/input only. Keep seed validation and existing API payload.
   Use existing localized limit error for a day above the cap; never trim data or simulate
   unsupported configurations. No new production wording or locale changes.
4. Run focused tests, then full frontend tests/typecheck/lint/build. Run backend/engine
   regression gates as applicable and record every failure/skipped check accurately.
5. Use an isolated local database with the unchanged owner CSV for browser execution.
   Check one click, no count field even in Advanced, retained key metrics/replay and
   responsive display. Verify numerical engine pins and protected-file preservation;
   do not claim global mathematical correctness from software tests alone.
6. Review exact diff and write the actual report. No staging/commit/push/deployment.

Stop affected work for an unexplained failed gate, changed analytical semantics or unowned
changes that cannot be isolated. This change does not implement the separate proposed
CSV auto-Setup workflow; retain its pending status.
