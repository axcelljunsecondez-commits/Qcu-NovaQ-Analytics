# Combined video and homepage placement — local completion

Status: **COMPLETE locally**, 27 October 2026. This follows the owner's correction that the newer placement and supplied video were omitted from the preceding wording-only activation. No production action was taken.

## Actual implementation

- Homepage: hero and How It Works remain in the left spotlight column, with one combined lesson in the right column. Queue Types spans the full width below both columns. Its one disclosure reveals both diagrams side by side on desktop and stacked on phones, without Previous/Next controls. Disclosures start collapsed. How It Works retains its independent three-step loop.
- `ExpandablePanel.tsx` shares the existing linked ARIA state, inert collapsed content and in-place reveal styling with `ExpandableSlides.tsx` and `QueueTypesComparison.tsx`. No automatic scrolling or focus movement was introduced.
- Home and Help now use the same single combined lesson. The old part-selection cards are removed. Existing custom play/pause, seek, speed, sound, fullscreen, lazy Blob loading, cleanup, download and field-collection checklist remain.
- `frontend/public/queueing101/combined.mp4` is the owner's unchanged uploaded file: **23,641,116 bytes**, **266.3 seconds**, **1920×1080**, H.264/AAC, SHA-256 `97dd4cf89fa58093c63d88955dc1feb555f9a4b936eaf7bd6fd1b67e7b6bc597`. The displayed duration is **4:26**. `combined.webp` was extracted from that file. Old lesson files remain unchanged as historical assets.
- The shorter edit's separate caption timing and transcript were not verified. Old VTT/transcript links are therefore not attached to this file. The provided video contains visible English captions; sampled opening/middle/ending frames were inspected. Full narration/caption accuracy was not separately audited.
- Six symmetric EN/TL label pairs describe the combined lesson and side-by-side comparison. English headings and the approved PDF wording remain in place. During visual QA, PDF page 2 was checked directly: its separate underlined “How it works” heading had been accidentally appended to the Filipino diagram note by the earlier extraction. Only that stray heading was removed, and its requested/applied record now documents the extraction correction. The thirteen previously retained semantic conflicts are unchanged.

## Executed verification

- Full frontend suite: **88 test files, 729 tests passed**. The former two-media parameterized case now checks the single combined file; lifecycle, abort/unmount cleanup, byte/MIME validation, search, asset identity, navigation, disclosure semantics and no-pagination assertions remain covered.
- Initial focused checks: **26 tests passed**. After the PDF extraction correction: **15 affected tests passed**. `npm run typecheck`, `npm run lint`, and `npm run build` passed again. The existing large-bundle warning remains; no bundling refactor was part of this task.
- **47 actual candidate-browser checks passed** against a temporary nginx image connected to the existing local API, with no API mocking or authentication/data-changing requests. Verified full-width placement, both pictures simultaneously, no queue pagination, smooth reveal without viewport movement, independent workflow loop, lazy MP4 loading, real 1920×1080 video/audio decoding, 266.3-second duration, seek to 150 seconds, speed/pitch, controls below captions, EN/TL, widths 1280/390/320, light/dark, reduced motion and Help search/download.
- The first reduced-motion assertion required exactly `0s`; actual inspection showed the existing global accessibility rule uses `0.01ms`. The assertion was corrected to accept that near-zero duration. No application workaround was introduced. Real accessible disclosure names were also checked. Guest `/auth/me` requests return the expected 401; zero browser **page errors** were observed.
- **11 browser checks passed against activated `http://127.0.0.1/`**, including actual combined-video playback, placement, both diagrams/no pagination, approved English headline/Filipino text, corrected note, phone overflow and Help's combined lesson.
- Every one of the **86 candidate and actual-local HTTP files** matched the final dist build by SHA-256. `/healthz` and `/api/ready` returned 200; web is healthy.
- Existing local API/database container identities, images, configuration, mounts and ports were preserved. All **ten public table row fingerprints** matched before activation, after activation and after the final browser check: **zero changed tables**. A private pre-activation PostgreSQL backup was taken and its archive listing verified; rollback execution remains **NOT TESTED**.
- Backend, API, authentication, migration and mathematical source paths have no diff. No backend changes were made; the earlier same-checkout backend regression result (3,288 passed, 125 skipped, one expected failure) is historical evidence, not a newly executed backend suite for this presentation-only follow-up.

## Local delivery

Activated only `web` using `--no-deps --no-build --pull never`, preserving `127.0.0.1:80 → 8080`:

- Tag: `novaq-local-web:20261027-combined-homepage-48442ec8`
- Image: `sha256:4ae12e8c36884ae8205bd88c93a87a78a3ef913046cad8e0bf9ef06d38aa9879`
- Previous local wording image remains tagged for recovery. No migration, seed, commit, push or production deployment occurred.

Private logs, source-preservation patch, media evidence, screenshots, static hashes and database fingerprints: `C:/Users/Administrator/.codex/visualizations/2026/10/25/01a17357-870d-72d1-b868-9aad4a8b8cdf/homepage-placement-20261027/`. Do not publish its database backup. Temporary preview/browser resources are removed after verification; the active local stack remains running.
