# Archived analysis selector correction plan

**Status: selector correction and final CSS image build/isolated verification complete.** Focused regressions: 3 passed; final full source frontend: 683 tests / 82 files, typecheck/lint passed. Final image's 32 immediate-resize cases, sidebar and selector switching passed. See the [exact image execution and remaining status](../reports/2026-10-19-approved-focus-image-verification.md). Subsequent [local activation](../reports/2026-10-19-local-compose-focus-activation.md) completed; commit and push remain unexecuted; native/statistical limits remain explicit.

Specification: `../specs/2026-10-19-archived-analysis-selector.md`.

1. Preserve the dirty baseline and capture the archived route/title/select mismatch.
2. Add regression cases for a successfully loaded current record absent from the default list; observe their failure before changing application code.
3. Include that authorized current record once in the selector, preserving existing navigation.
4. Run affected and full frontend tests, typecheck and lint. Record all actual results and any failed attempts.
5. Reconcile earlier verification items in the new closure report; retain genuine failures and unavailable native checks.
6. Stop before a new build/rebuild, commit or push. Present exact remaining work for approval. The exact final image now has approved isolated runtime/browser evidence; the subsequent local activation is recorded separately.
