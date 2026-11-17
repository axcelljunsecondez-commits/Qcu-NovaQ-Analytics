---
name: 2026-11-09-upload-preview-rate-bucket
description: Upload follow-ups D1-D4 + T1/T2 (2026-11-09) — preview rate bucket, confirmation focus, missing-column 422, hour nowrap, Simulation hours/reason
metadata:
  type: project
---

Status: CLOSED. Round 2 committed as 05e4cfa8 and merged to origin/main via PR #46 (merge d87cb514); VERIFIED from git 2026-11-10. Earlier: round 2 (after Kyoya FAIL K-UF-1) implemented; owner decision "A1, B1" 2026-11-09 (REPORTED via parent).

- Authorization: owner "yes" (D1-D4 + text drafts) and "1 OK, 2 leave, 3 success only" on 2026-11-09 (REPORTED via parent).
- Checkout: `.claude/worktrees/upload-followups`, branch `fix/upload-followups-20261109`, HEAD 4b015684 (origin/main); 16 modified files, `git diff | sha256sum` = 4a0906b7... at handoff.
- D1: `upload_preview` bucket, RATE_LIMIT_UPLOAD_PREVIEW default 60 (= report_preview precedent); apply keeps `upload` 10. Added to .env.example + docker-compose.production.yml. No Render action needed (default).
- D3: shared_aggregate_setup raises existing ingestion message when neither/both schemas present (aliases applied first).
- D2 focus (title, Cancel->primary, confirmed success->alert); D4 nowrap CSS; T1 new key continuous.reason.model_choices_unanswered (old key left, spec 2026-10-29 references it); T2 setupHours only when dataset_id null.
- Observation for owner: unconfirmed apply success leaves focus on BODY (decision 3 limited focus to confirmed path).
- Gates: ruff/mypy clean; vitest 1040/1040; tsc/oxlint/build exit 0; frontend mutants 6/6 killed; browser CDP check 23/23 (1280+375). Full pytest: see handoff.
- Gotchas: Python read_text/write_text normalizes CRLF (restore CRLF); `-p no:logging` breaks caplog tests; gates run concurrently or during a usage-limit pause get starved (single tests 4600 s) -> run gates alone; CDP setFileInputFiles with same path fires no change; returnByValue of DOM node is falsy.
- Round 2: A1 = server fills horizon/dataset_id/scenario when only capacity/abandonment Setup gates refuse (probe via extracted `_read_plan_data`, reasons unchanged); frontend setupHours fallback REMOVED. B1 = Counter in shared_segments `_id_problems` (derive 100k rows 5.34 s, was >1000 s; 16k 22.64 s -> 0.94 s). N1 = `lib/focusAfterCancel.ts` (disabled primary unreachable in UI today; unit-tested).
- Gotcha: heredoc + python sometimes halves backslashes in written files -> write `\` via chr(92); `profile.py` script name shadows stdlib. Shared machine also runs Codex/other sessions: vitest took 25 min.
