# Tutorial integration and release plan

1. Start from verified clean 2fcc33e22639bf4f5e962e9dc7b00e0f50d3d1f2 in
   the attached release checkout; use codex/tutorial-video-guides-20261021.
2. Add catalog, public verified media/steps, native dialog and Help library.
3. Add the three contextual shortcuts, EN/TL strings and token-based styles.
4. Verify mappings, media lifecycle, localization, assets and existing frontend
   behavior. Run frontend tests, typecheck, lint, audit and build; preserve all gates.
5. Verify actual browser playback and responsive interaction when a supported
   browser-control route is available. Do not replace that proof with JSDOM stubs.
6. Review the final diff, protected-file scope and exact commit/CI evidence.
7. Prepare the bounded frontend-only production packet. Confirm current main,
   Pages settings/target and recovery build; keep Render and database untouched.
8. Publish only after required gates and authorizations are satisfied, then inspect
   public Help/video delivery, browser playback and retained release controls.

STOP deployment for failed/unexplained gates, unknown current deployment controls,
or missing real-browser evidence. Independent local preparation may continue.
No database migration or backend redeployment is required by this frontend scope.

## Approved correction after initial preview (2026-10-22)

The initial candidate is `8942911e7a30e67a71014ef78a0de5b97176f526`, PR 34.
Its actual Pages preview `00a741bc` reproduced failed seeking for all three clips
in a fresh context. Keep that failed evidence; do not publish that candidate.
The owner approved the nine-file Blob-loading/media-CSP correction in the spec.

1. Apply only the approved player, player tests, three CSP copies, existing
   hardening test, and spec/plan/verification document changes.
2. Verify no fetch before Watch, loading, HTTP/file/decode errors, request abort,
   late completion, Blob revocation, reopening, unmount and StrictMode cleanup.
   Pin the exact unchanged non-media CSP directives and all three policy copies.
3. Run focused regressions, full frontend tests, typecheck, lint, audit and build.
4. Test the actual built app on the isolated server without byte-range support
   using its actual built CSP. No test-only source replacement counts as proof.
   Verify real frames/seeking, downloads, focus, both themes and narrow widths.
5. Review the nine-file diff, commit/push the feature branch and obtain green
   exact-candidate CI. Build a new actual Pages preview and repeat fresh-context
   playback/seeking/download and responsive checks there.
6. Continue the already requested bounded frontend production release only when
   every required gate passes. Recheck main, recovery deployment and deployment
   controls first. Keep Render/database untouched and record live proof separately.
