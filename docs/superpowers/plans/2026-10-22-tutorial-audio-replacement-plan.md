# Three audio tutorial replacements — implementation and release plan

1. Verify clean released base dfd3277d and remote main; use the isolated release
   checkout on codex/tutorial-voiceover-20261022. Preserve all other worktrees.
2. Pin exact Downloads inputs, size, audio/video metadata and full decoder results.
   Resolve first clip scope with the owner; preserve the exact approved files.
3. Measure every actual decoded scene against existing instruction frame sources;
   explicitly handle black lead-in/out and the modified Welcome opening. Inspect
   the frames and retain failed matching diagnostics until their cause is resolved.
4. Replace assets, catalog, matching caption/step times, posters and EN/TL labels.
   Update the existing asset regression to enforce the owner's <24 MiB checks.
5. Execute required frontend checks and native local browser tests on the actual
   build without server byte-range support. No production/auth/math inference.
6. Review exact scope, commit/push only this candidate, and obtain green CI. Build
   and test an actual new Pages preview in fresh browser contexts.
7. Recheck live main, Pages controls, prior production recovery target and Render
   Off; publish the authorized replacement only after the gates pass. Keep the
   bounded automatic production enable/main-fast-forward/disable sequence.
8. Verify actual live assets, playback, audio controls, seek and download hashes;
   retain deployment controls and write the evidence closure. Stop on failed gates.
