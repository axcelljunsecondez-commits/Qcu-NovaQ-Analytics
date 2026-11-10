# One plain shared-queue simulation interface

Owner approval: remove Named Shared Queue from the visible One Shared workflow,
hide the Legacy/Named selection and names, keep the normal full-day simulation.
This supersedes the older UI requirement to preserve the mode selector/deep link.
No backend retirement or mathematical change is authorized by this approval.

Verified source: QueueSimulationPage imports/mounts the Named component for
mode=named, suppresses its workflow query, and renders SimulationModeSwitch on
shared analyses. SimulateRedirect forwards mode=named from the old workspace URL.
Named UI has no other production mount. shared_continuous.py imports shared_named
constants, so deleting backend modules is outside this frontend retirement.

Implement only:

- Remove the Named mount/import, mode selector/import and Named workflow bypass
  from QueueSimulationPage. All supported shared visits use the existing standard
  full-day/three-page flow. No replacement selector or new product wording.
- Canonicalize obsolete mode parameters (named/legacy) on simulation page URLs
  with history replacement. Keep pathname, other query values and hash. No
  automatic new simulation, check, plan selection or data/settings write.
- Old /analyses/:id/simulate links go to standard /simulation/results. Remove
  mode, preserve other query/hash values and take analysis identity from the route.
- Preserve Current/Suggested selection, saved evidence, full controls only on
  Key Results, compact status on Replay/Checks, existing warnings and all formulas.
- Retain Named components/API/tests, backend routes/domain code, saved Jobs,
  locale dictionaries and auth redirect sanitization. Removal of its visible entry
  point is not deletion of its independent regression coverage.

Writable scope: frontend/src/pages/QueueSimulationPage.tsx,
frontend/src/pages/QueueSimulationPage.test.tsx, frontend/src/router.tsx,
frontend/src/routerDataRedirect.test.tsx. Parent owns these task docs and new
output/plain-shared-simulation-20261102 evidence. Preserve all prior dirty work.

Acceptance: no mode fieldset or Legacy/Named label on any shared tab in EN/TL;
retired URLs reach the normal view with preserved analysis/plan/time/date/hash;
old routes normalize once without history loops; normal shared and separate
workflows remain functional; navigation performs no new run/check/selection write.
Named backend contracts/data and independent test files remain byte-for-byte intact.

Required checks: relevant page/router/cache/continuous behavioral regressions,
frontend type/lint/build and full suite; browser normal/retired URLs across tabs,
desktop/375px and EN/TL; protected source/previous work preservation and independent
review. Existing Named test deadline failures remain a recorded verification
blocker until actual evidence closes them. Do not remove tests or raise limits to
conceal them. A new full-suite attempt is justified by this newly approved source
change; stop dependent closure/release if required gates fail again.

Actual roles: parent supplies source-grounded investigation/design and can review
application/tests independently if it remains a non-implementer. Reuse Hayato after
his reported quota reset only if a fresh capability preflight succeeds; otherwise
qualified worker fallback must identify itself and verify access before writing.
No commit, push, Docker activation or deployment is part of this approval.
