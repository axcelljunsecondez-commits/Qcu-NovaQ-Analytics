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
