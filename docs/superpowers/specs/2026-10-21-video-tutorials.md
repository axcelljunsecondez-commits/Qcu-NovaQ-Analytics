# Video tutorials

Owner request: deploy the three silent tutorials and their reviewed local placement.
The standalone preview is not application implementation. This spec bounds the
actual frontend change; production remains gated on the candidate checks.

Add the three verified, English-captioned videos to Help, below search and above
written guides. Add a secondary Watch tutorial button to My analyses, Analysis
results and the shared Queue simulation header. Preserve existing written Help,
selectors, primary actions, navigation and all analytical behavior.

Use a native modal video player with controls, playsInline, no autoplay, a visible
Close control, Escape dismissal, focus return, MP4/VTT downloads and English steps.
Mount media only after opening; pause it when closed/unmounted. Show video errors
with a download fallback. Keep the English-caption note visible in either locale.
Use existing theme tokens, responsive columns and a bounded, scrollable dialog.

Use same-origin static files under /tutorials with stable names. A content revision
in catalog URLs invalidates caches when files change; replacing a clip updates its
duration/revision/steps and verified asset digest, without moving its buttons.
Each MP4 must remain below 25 MiB. No new dependencies or third-party player.

The clips use saved screenshots, with labeled shared/separate examples. Keep the
short screenshot-example note. Do not claim new results, operational safety or
closed seed sensitivity. Named staff mode is outside the basic simulation guide.

Scope: frontend tutorial components/catalog/assets, four page entry points, EN/TL
strings, additive styles, focused tests and these spec/plan files. No backend,
mathematics, API, auth, database, proxy, Docker or production setting changes.

Acceptance: frontend regression/type/lint/build; symmetric locale keys; exact
media hashes and size; closed-player no source, correct mappings, Close/Escape and
unmount pause; real-browser playback/seek/download/focus, both themes and narrow
viewports. Local/CI proof is distinct from a successful production cutover.

## Approved seeking correction (2026-10-22)

The first actual Pages preview reproduced failed seeking in all three clips in a
fresh Edge context. Pages returned full 200 responses to Range requests; the
native seekable timeline stayed [0,0] after full buffering. Cached playback did
not reproduce that failure and cannot substitute for fresh-session verification.

The owner approved this bounded correction and verification on 2026-10-22:
load only the opened clip from its existing same-origin URL into a browser Blob;
check HTTP success and the catalog's expected MP4 size/type before using it. Show
the existing translated Loading state while downloading and the existing direct
download fallback on failure. Preserve the native controls, no autoplay, focus,
text steps and direct MP4/VTT links. Abort pending work, pause the video and revoke
the Blob URL on close/unmount; ignore late completions. Each clip must download
before playback starts. Its size remains below 25 MiB.

The owner explicitly expanded the file scope to the player and its tests,
`frontend/public/_headers`, `nginx/nginx.conf`, `nginx/production.conf`,
`tests/test_production_hardening.py`, and these spec/plan/verification documents:
nine files. Add only `media-src 'self' blob:` to all three existing CSP copies.
Pin equality and the remaining directives; do not broaden script, connect, frame
or other policy permissions. This is the sole approved configuration exception to
the original scope. No API bridge, routes, backend, mathematics, authentication,
database, dependency, Docker runtime or cloud setting change is included.

Acceptance additionally requires abort/revocation/late-completion and StrictMode
regressions, CSP parity, and actual corrected-app seeking on a range-incapable
server and an updated Pages preview, each in fresh contexts. A test-only DOM
feasibility experiment is not application implementation proof.
