# Replace the three tutorial videos with owner-supplied audio versions

Owner authorization (2026-10-22): replace all three old clips with the exact files
provided in Downloads. After the first clip's narrower scope was identified, the
owner explicitly repeated: "remove the old vids and replace this 3 new vids".

Use the supplied MP4 bytes without recompression or audio edits. All three must
be below the owner's 24 MiB limit. The analysis-workflow asset is now a start and
upload guide, not the earlier full analysis-to-reports walkthrough. Rename its
card and description in EN/TL to match, keeping its stable asset ID and existing
My Analyses shortcut. Preserve the existing metrics and simulation placements.

Update catalog byte counts, measured rounded durations, SHA-256 revisions and
posters from the new videos. Replace old downloadable VTT and displayed steps
with instructions timed to the actual replacement scenes. Do not proportionally
rescale old times or describe screen instructions as verified speech transcripts.
Change the app's No audio language line to Audio in English and May tunog in
Filipino; keep the accurate English captions/steps note. No autoplay.

The owner-supplied first clip still contains a small No audio note in its pixels,
although its large opening caption now says Welcome to NovaQ. Preserve the exact
approved media. Record that retained embedded note; do not claim it was removed.
Spoken-word accuracy is not independently established by track metadata or visual
instruction matching. The audio versions are owner supplied and owner approved.

Permitted scope: nine static tutorial files (MP4/VTT/WebP), tutorials.ts,
tutorialSteps.json, EN/TL tutorial strings, the existing tutorial test and these
specification/plan/verification documents: 17 files. Preserve native player and
Blob cleanup, CSP, routes, API, authentication, backend, mathematics, seed,
database, dependencies, workflows and Docker. No infrastructure is needed.

Acceptance: exact media hashes and <24 MiB; full audio/video decode; actual scene
timing/caption order and all 14/19/30 visual instruction scenes accounted for;
locale symmetry; focused and full frontend tests, typecheck, lint, audit, build;
actual browser no autoplay, audio-enabled controls, play/seek, downloads, cleanup,
light/dark and narrow layouts. For publication require a clean scoped candidate,
green exact-candidate CI, an actual updated Pages preview, current release controls
and recovery target, then separately record production and actual live behavior.
Keep Render auto-deploy off and production database unchanged.
