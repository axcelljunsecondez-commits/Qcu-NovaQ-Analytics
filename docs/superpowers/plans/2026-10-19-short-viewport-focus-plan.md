# Short-viewport focus correction plan

**Status: steps 1–6 complete for source preparation, owner-approved rebuild and isolated verification.** Fresh source: 683 tests / 82 files, typecheck/lint and 32 immediate-resize cases passed. Final image: Nginx, 66 static files, 32 immediate-resize cases, sidebar and selector switching passed. Subsequent owner-authorized local activation and scoped smoke completed; see the [activation record](../reports/2026-10-19-local-compose-focus-activation.md). See the [image execution and remaining status](../reports/2026-10-19-approved-focus-image-verification.md). No commit/push performed.

[Proposed specification](../specs/2026-10-19-short-viewport-focus.md).

1. Bound the application file scope to `frontend/src/styles/global.css` for the verified focused-control obstruction only, under the owner's existing UX-fix authorization.
2. Preserve the existing dirty source and the current candidate image/archive. Capture the failing native-Tab visibility case; the current evidence already records this failure.
3. Apply the exact short-height footer rule in the reviewed proposal, preserving all workflow actions and labels.
4. Execute the specification's theme, language, viewport, keyboard, and reduced-motion matrix. Any failure remains a blocker and must be explained.
5. Run applicable frontend gates and inspect the complete scoped diff. Do not change mathematics, API/auth behavior, or unrelated source.
6. Prepare a new exact source manifest and image-build request. Obtain the owner's requested approval before another rebuild, commit, push, or existing-container replacement. Keep the seed-sensitive Decision and native/manual gates explicitly open.
