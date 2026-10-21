# Video tutorials: local implementation and verification

This frontend-only change implements the owner's three silent, simple-English
tutorials. It is based on `2fcc33e22639bf4f5e962e9dc7b00e0f50d3d1f2`.
The specification and plan are `2026-10-21-video-tutorials.md` and
`2026-10-21-video-tutorials-plan.md` in their corresponding Superpowers folders.

## Implementation

- Help lists the three videos between search and the existing written guides.
- Secondary Watch tutorial buttons open the matching clip on My Analyses,
  Analysis results, and the three Queue simulation pages.
- A native dialog provides controls, Close, Escape, restored focus, downloads
  and English text steps. Video elements mount only while the dialog is open.
  The media cleanup pauses playback. There is no autoplay or new player dependency.
- EN/TL controls explicitly identify English captions and steps. The source clips
  are saved-screenshot guides; a short note discloses possible screen differences.
- Same-origin `/tutorials/` files use stable names and content-revision query
  strings. A replacement requires updating the catalog, steps and asset digests.
- Tutorial text and links use existing theme tokens. A measured low-contrast
  light-theme pairing was corrected within these new tutorial styles only.

No backend, mathematical, seed, API, authentication, schema, proxy, dependency,
Docker or existing report-calculation file is changed.

## Verified media

| Clip | Duration | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| analysis-workflow.mp4 | 4:15 | 1,973,500 | 8495ebfe3a0c992321126225079fbe3779107ae49ddd477b8a8ca54d9b549b3e |
| key-metrics.mp4 | 2:33 | 1,470,909 | 6be08abb6cc290f5b771a7320f2c7df156235836102e9eb1823fea7358f4ab56 |
| queue-simulation.mp4 | 4:06 | 1,780,480 | 9899542501e8aa09c8be280627650260598389bb0b836c19563e20d51001a786 |

These are byte-identical copies of the previously verified H.264, 1600x900,
15-fps, audio-free clips. Each is below 25 MiB. Native browser downloads of all
three MP4s and their VTT files were compared byte-for-byte with the shipped files.

## Executed verification

- Full frontend: `npm test -- --pool=threads --reporter=verbose`: **83 files,
  695 tests passed**, exit 0, 588.22 seconds. The earlier default-pool attempt
  ended with no complete result across the restart; it is not counted as passed.
  This full run preceded the final tutorial-only CSS contrast correction. No
  functional TypeScript or test code changed after that full run.
- After that CSS correction: `npm run typecheck`, `npm run lint`, and
  `npm run build`: exit 0. The existing large-chunk build advisory remains.
- `npm audit --omit=dev --audit-level=high --json`, repeated on 2026-10-22:
  exit 0; zero vulnerabilities reported. No dependency file changed.
- Final built frontend in Edge: **48 public Help checks passed**, including
  real decoding, advancing playback, midpoint seeks, metadata, no autoplay,
  six native downloads, transcript disclosure, focus containment, Escape,
  search, and EN/TL controls.
- Layout/dialog checks at **1366x900, 375x812 and 812x375**, in light and dark
  themes: passed. No document/dialog horizontal overflow was detected. New
  public tutorial text/link contrast samples were at least 13.23:1.
- Final built frontend with explicit synthetic GET fixtures from the existing
  page tests: **63 contextual checks passed** across five page routes, two
  themes and two widths. The correct tutorial opened, its trigger fit the
  viewport, and route/focus were preserved. No mutation request, unexpected
  fixture request or uncaught browser error was recorded. These fixtures do
  not verify backend authentication, persistence or mathematical results.
- `git diff --check`: passed before staging. Final staged scope is reviewed
  separately before the commit.

Primary local evidence, under the primary checkout's ignored `output/`:

- `tutorial-release-2026-10-21/frontend-tests-threads.log`
- `tutorial-release-2026-10-21/final-build.log`
- `tutorial-release-2026-10-21/npm-audit-20261022.json`
- `playwright/tutorial-release-20261021/public-browser-verification-20261022.json`
- `playwright/tutorial-release-20261021/context-browser-verification-20261022.json`
- The corresponding `verify-public.js`, `verify-context.js`, raw outputs,
  downloaded assets and `verified22-*.jpg` screenshots.

## Preserved failures and limits

The original `SimpleHTTPRequestHandler` local server returned the full file as
200 to range requests. The browser reported `seekable=[0,0]` and midpoint seeks
returned to zero. A separate verification server serving the identical built
files with proper byte-range responses returned 206 and `seekable=[0,duration]`;
all three midpoint seeks then passed. This resolves the local delivery-harness
failure, not production behavior. The public Pages site also returned an actual
206 for a range of an existing WebP asset; that is not proof for the new MP4s.
New MP4 delivery/seeking on Pages remains a release verification step.

The in-app browser ignored requested viewport overrides; those attempts are not
counted as narrow-screen tests. The owner explicitly approved the separate
Playwright browser for local/preview verification. The first contextual harness
used `My analyses` instead of the actual `My Analyses` heading and timed out;
the raw failure was retained and the selector corrected against the actual DOM.

Physical phones, Safari/iOS, qualified Filipino language review and universal
accessibility are not established by these Edge viewport tests. Existing seed
sensitivity, native Excel and unrelated manual findings remain separate. No
operational-safety claim is made.

## Release boundary

Local frontend verification is complete. Exact-candidate CI, Pages MP4 checks,
production cutover and live verification must be recorded separately. This
document does not claim that any version has been committed, pushed or deployed.
The release is frontend-only; it requires no Render redeployment or migration.

## Approved seeking correction and local verification (2026-10-22)

The sections above record the initial local candidate. Its actual Pages preview
`00a741bc` at commit `8942911e7a30e67a71014ef78a0de5b97176f526` failed midpoint
seeking for all three clips in a fresh Edge context: full 200 responses to Range
requests, a fully buffered file, seekable [0,0], and a seek returning to zero.
A cached response exposed a full timeline, so cached success cannot clear this
failure. The other 45 preview checks passed. Six downloads match the exact Git
candidate; VTT checkout differences are solely Windows CRLF versus Git LF.
The initial candidate's CI run 39638787562 completed all 11 jobs successfully;
that CI result does not close its actual preview failure.

The owner approved the nine-file correction and verification on 2026-10-22.
The native player now fetches only the opened clip as a Blob after checking HTTP
success, expected bytes and MP4 MIME type. It shows the existing translated
Loading text, preserves downloads and error fallback, aborts pending work, ignores
late completion, pauses and revokes the URL on close/unmount. The native controls
and media bytes remain unchanged. The selected file downloads before playback.

The only policy expansion is `media-src 'self' blob:` in Pages and both nginx
configurations. The hardening test pins equality and every remaining directive.
No API bridge, routes, backend, mathematics, authentication, database, dependency,
Docker runtime or cloud setting is changed by the correction.

Executed correction checks:

- Focused `Tutorials.test.tsx` plus `apiProxy.test.ts`: **2 files, 32 tests passed**,
  exit 0, 79.40 seconds. JSDOM media/dialog stubs verify lifecycle and fallback;
  native playback is separately verified below.
- Full corrected frontend suite: **83 files, 701 tests passed**, exit 0,
  779.15 seconds. No runtime or test source changed after this run.
- `npm run typecheck`, `npm run lint`, `npm run build`: exit 0. The existing
  large-chunk advisory remains. Production npm audit: exit 0, zero vulnerabilities.
- `python -m pytest tests/test_production_hardening.py::test_pages_headers_mirror_production_nginx -x --tb=short`:
  **1 passed**, exit 0, 4.28 seconds. An installed Starlette/AnyIO deprecation
  warning remains. No database fixture or database action was used by this test.
- `ruff check tests/test_production_hardening.py`: passed.
- The actual corrected build, with its actual built CSP, on a loopback static
  server without byte-range support: **54 browser checks passed** in a fresh Edge
  context. All three clips decoded, played and sought exactly to 127.5, 76.5 and
  123 seconds. No MP4 request preceded Watch. All 10 created Blob URLs were revoked
  exactly once after closing. No CSP violation or uncaught browser error occurred.
  Lifecycle instrumentation passed through the actual browser APIs; no test-only
  media source substitution or synthetic MP4 response was used.
- Light/dark checks at 1366x900, 375x812 and 812x375 passed, including bounded
  dialogs, keyboard/focus, search and EN/TL controls. Six native downloads match
  the actual build bytes and Git content (accounting for VTT line endings).
- Corrected-build contextual shortcuts: **63 checks passed**, with the same
  explicitly synthetic API GET fixtures described above. The mapping assertion
  follows the actual MP4 fetch plus Blob source and direct download path.
  Unexpected fixture requests, mutation requests and uncaught errors: zero.

The anonymous local auth GET is an explicit fixture, not backend proof. Physical
phones and Safari/iOS remain NOT TESTED. The isolated test-only Blob feasibility
experiment is retained separately and is not counted as implementation proof.

Correction evidence under the primary checkout's ignored `output/`:

- `tutorial-release-2026-10-21/seek-focused-tests.log`
- `tutorial-release-2026-10-21/seek-full-frontend.log`
- `tutorial-release-2026-10-21/seek-build.log`
- `tutorial-release-2026-10-21/seek-npm-audit.json`
- `playwright/tutorial-release-20261021/fresh-preview-diagnostic-20261022.txt`
- `playwright/tutorial-release-20261021/corrected-local-browser-verification-20261022.json`
- `playwright/tutorial-release-20261021/corrected-context-browser-verification-20261022.json`
- Corresponding scripts, raw outputs, native downloads and `seekfix22-*.jpg`.

Updated exact-candidate CI, an updated actual Pages preview, production cutover
and live checks remain separate release gates. They are not claimed complete by
this local verification record. Existing unrelated findings remain open.
