# Three audio tutorial replacements — local verification

Base: `dfd3277dac9f353834931d85b77b6936d90d091f`. Owner approved all three exact Downloads files, including the
shorter start/upload clip after its narrower scope was identified.

## Changes

Replaced the three active MP4s with byte-identical owner inputs; regenerated
posters from those actual videos; updated catalog SHA revisions, exact sizes and
rounded durations; replaced VTT and text steps with measured visual-scene times.
The first card is now Start and add data and its EN/TL description matches that
scope. The app language line now reads Audio / May tunog with the English-caption
note. The stable asset paths and all existing tutorial shortcuts are retained.

No player, CSS, CSP, API, authentication, backend, mathematics, simulation, seed,
schema, database, dependency, workflow or Docker file changed. The existing
runtime file safety cap remains 25 MiB; the shipped asset regression and release
checks enforce the owner's stricter <24 MiB condition for these replacements.

| Clip | Actual container duration | Catalog seconds | Bytes | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| analysis-workflow | 61.696 s | 62 | 1387977 | 5a27b75e8e02b7a651804404341e3d68990275752e27573c6d0c6874b85be62a |
| key-metrics | 91.232 s | 91 | 3664985 | 78ed2acb4af253902ee1d2dfffd1080520c600c2a42175cc432d9de5f800b5ff |
| queue-simulation | 144.916 s | 145 | 5112569 | 9cc2158fdb7da46f00795b0adc16a9608bc3446f99a8903c2efaca483a0ad370 |

## Actual verification

- All inputs: H.264 video and AAC stereo audio; full audio/video decode exited 0
  with no errors for each original input. Hash identity preserves that evidence
  for the application copies. First video is 852x480; the other two 1920x1080.
- Decoded all visual frames at their established 30 fps and matched the actual
  instruction scenes to prior source frames: 14 / 19 / 30, in order. The supplied
  first opening now says Welcome to NovaQ and uses an inspected actual input
  frame as its reference. Caption times come from measured frame transitions,
  not proportional scaling. Black lead-in/out is excluded from instruction cues.
- Full frontend: **83 files / 701 tests passed**, exit 0,
  603.79 seconds. Typecheck, lint and production build exited 0. Production
  npm audit exited 0, zero vulnerabilities. Build retains its large-chunk advisory.
- Actual local built app, loopback server without byte-range support, fresh Edge
  context: **57 browser checks passed**. All three decode audio
  and video, stay paused until Play, have native unmuted audio controls, seek to
  midpoint, and download their exact MP4/VTT files. All six downloads match build
  bytes. All 10 created Blob URLs revoked exactly once; zero CSP violations.
- Light/dark at 1366x900, 375x812 and 812x375: bounded dialogs, expected columns,
  no horizontal overflow, contrast checks, EN/TL labels and search passed. Native
  Close/Escape restore focus. Per clip, 24 Tab and 24 Shift+Tab steps never focus
  page content outside the native dialog; browser-toolbar focus is distinguished
  by document.hasFocus() false with BODY as activeElement.
- Existing contextual shortcuts: **63 browser checks passed**
  across five routes, two themes and two widths. These use explicitly synthetic
  GET fixtures, with zero mutation/unexpected requests and no uncaught errors;
  they do not establish production authentication or analytical correctness.

## Preserved failures and interpretation

Initial frame matching incorrectly classified black lead-in/out against content
frames, and used the old opening reference for the owner's changed first scene.
Those attempts are retained in initial-scene-timing-evidence.json and logs. Actual
black-frame rejection and the visually inspected replacement opening resolve the
matching failures; all scenes are subsequently accounted for in order.

The preparation script first stopped at Windows' default cp1252 decoding of a
UTF-8 locale file. Explicit UTF-8 reads corrected the local preparation; the final
diff retains only the three intended strings per language.

The initial local browser run failed an endpoint-only keyboard assertion after a
fixed count of Tabs. A 48-step diagnostic established that each outside state had
document.hasFocus() false and BODY active: browser chrome, not outside page
content. No app code was changed. The final browser test traces both directions,
rejects actual outside-page focus, and verifies Escape/focus return. The original
failed report and this diagnostic are retained. Its incomplete cleanup count was
captured after early test abort, before normal dialog Close, and is not claimed
as a passing cleanup result. Final normal-close cleanup passed independently.

The initial full frontend attempt exited 1 with 82 files / 646 tests passed and
one runner error: the threads worker for OptimizePage.test.tsx did not start.
That is not a complete suite pass. The missing module then passed all 55 tests
in isolation (36.85 s). After closing the owned local browser, the unchanged full
suite was rerun to the clean complete result above. No source, test expectation,
runner configuration or timeout was changed to resolve that execution failure.

## Limits and next gates

These are the exact owner-approved media. The first video's small embedded
No audio note and Part 1 of 5 header remain in its pixels, even though it has an
audio track and its large old silent opening instruction is replaced. The app
wording is corrected. Do not claim those embedded pixels were edited or removed.

Caption files describe the actual English on-screen instructions; they are not
independently verified word-for-word speech transcripts. Voice-over content was
owner supplied; spoken-word accuracy and physical speaker output are NOT TESTED.
Physical phones and Safari/iOS remain NOT TESTED. Existing statistical/native
Excel findings are separate and unchanged.

Local verification is complete. Exact-candidate CI, actual updated Pages preview,
production publication and live verification remain separate gates and must be
recorded outside this immutable candidate document. No release is claimed here.

Evidence under the primary checkout's ignored output/:

- tutorial-voiceover-update-2026-10-22/frontend-tests.log
- tutorial-voiceover-update-2026-10-22/frontend-tests-initial-worker-failed.log
- tutorial-voiceover-update-2026-10-22/optimize-isolated.log
- tutorial-voiceover-update-2026-10-22/frontend-build-gates.log
- tutorial-voiceover-update-2026-10-22/npm-audit.json
- tutorial-voiceover-update-2026-10-22/scene-timing-evidence.json
- tutorial-voiceover-update-2026-10-22/replacement-media.json
- playwright/tutorial-voiceover-20261022/local-public.json
- playwright/tutorial-voiceover-20261022/local-context.json
- playwright/tutorial-voiceover-20261022/local-download-hashes.json
- Corresponding raw outputs, focus-diagnostic.json, scripts and screenshots.
