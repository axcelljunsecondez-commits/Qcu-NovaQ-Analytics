# Run-header placement plan

1. Verify current checkout/source and preserve previous cleanup hashes/diff.
2. Hayato implements only approved placement/component-prop and meaningful tests.
   Owner follow-up supersedes full controls on every tab: controls only on Results,
   compact read-only status on Replay/Checks. Preserve drafts and validity warnings.
3. Verify actual DOM order on separate/shared results/replay/checks, one visible
   context, Results-only controls, draft/pending state, loading/error/no-plan
   navigation and request/navigation contracts. Keep first candidate evidence
   labelled superseded; an interrupted earlier suite is not a passing final gate.
4. Run frontend tests/type/lint/build with task-owned logs and unchanged dependencies.
5. Parent inspects final source/diff and actual built local browser. Do not ask an
   unavailable reviewer to retry before its reported reset. Name any qualified
   non-implementing reviewer fallback; no native-adapter or independent browser claim.
6. Report local result, exact checks and limitations. Preserve completed prior task
   artifacts; new output belongs under output/simulation-header-20261102. No release.
