---
name: 2026-11-10-banner-and-workbook-focus
description: Data and Setup page fixes (2026-11-10) — banner-only "Fixed server count, or tick Staffing varies…" label + workbook confirmation focus (D2 pattern)
metadata:
  type: project
---

Status: CLOSED. Committed as 2e104cfe and merged to origin/main via PR #47 (merge 702a6aa1); VERIFIED from git 2026-11-10. Earlier: complete (implementation), handed to Kyoya via parent 2026-11-10. Owner approval "approve both" + banner wording "i approve that, next" (REPORTED via parent).

- Checkout: `.claude/worktrees/banner-focus`, branch `fix/banner-and-workbook-focus-20261110`, HEAD d87cb514 (origin/main). Parent commits after Kyoya.
- Changed: `frontend/src/pages/AnalysisSetupPage.tsx`, `AnalysisSetupPage.test.tsx`, en/tl `translation.json` (+`setup.missing_server_count_or_varies`). `git diff | sha256sum` = 6970bf76… at handoff.
- Not touched (verified): `setupStatus.ts`, `bannerMissing` filter, wording record, `wordingPolicy.test.ts`.
- Implemented: `BANNER_FIELD_LABELS` (banner only; openMissing = button text and line-429 notice = server message, so no other "still needs" list). Workbook focus mirrors D2: title on open (role=status), Cancel -> focusAfterCancel(Upload and process, card), Replace -> notice focused when upload settles (isSuccess/isError effect).
- Gates: vitest 110 files/1052 tests; tsc, oxlint, build exit 0. Mutants 5/5 killed. CDP browser 26/26 at 1280 and 375 (scratch SQLite, owner xlsx read in place).
- Gotchas: user.upload re-focuses the input AFTER `change` (masks wrong focus moves; use input.focus()+fireEvent.change). Locale/test files CRLF in working tree. Worktree base lacks `docs/agents/` (read from main checkout).
- Next: Kyoya review; parent commit. Observation: focus is on BODY between Replace and the upload settling (button unmounts).
