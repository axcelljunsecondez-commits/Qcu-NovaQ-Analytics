# U10 — Annotated Help screenshots

Status: owner "go screenshots" 2026-10-14 (plan U10: "annotated Help screenshots in EN and TL"; spec 2026-10-09 §7.11: screenshots only after the screens pass verification). IMPLEMENTED and committed on `feat/ux-u1-shell` after `a3b541fa` (local, not pushed). The owner did not name a storage location; this spec chose the one below.

## 1. What the reader sees

Each Help guide with one main screen shows, after its What to do / Why / Next step summary, one picture of that screen with numbered orange outlines, then:

- the note "Sample screen with made-up data. The numbers match the list below." (`help.figure_note`);
- a numbered list, one item per outline (`help.guide.<topic>.figure_mark_<n>`).

The picture's alt text (`help.guide.<topic>.figure_alt`) names the screen and the outlined parts. The reader's language picks the picture: English or Tagalog screens.

| Guide | Screen (analysis 10 unless noted) | Marks |
| --- | --- | --- |
| start | New Analysis | name, how customers line up, continue |
| data | Data and setup | template card, file purpose, Upload and process |
| results | Analysis results | recorded wait, estimated wait, busy-level strip |
| plans | Suggested plans after Optimize | assumptions and limits, Optimize, name + Use this plan / Save without using |
| simulation | Queue simulation, Key results, Suggested plan | page tabs, closing rule, Run full operation, average wait card |
| checks | Checks and decision, Suggested plan | Decision with its basis, per-period table, Check the plan |
| downloads | Reports | Decision stamp, PDF, Excel, Your data only |

Problems has no picture: it covers several screens.

## 2. Storage and serving

- Files: `frontend/public/help-images/<en|tl>/<topic>.webp` (14 files, about 0.8 MB). Served as static files from the site root (`/help-images/...`) by Vite, nginx and Pages; the path does not overlap the `/help/:topic` route or the Pages `/api` function. The production CSP already allows `img-src 'self'` (`frontend/public/_headers:6`).
- Sizes: `HELP_FIGURES` in `frontend/src/lib/helpGuides.ts` records the mark count and the pixel size per language; the page sets `width`/`height` from it (no layout shift) and scales the picture to the column (`max-width: 100%`).

## 3. Capture

`frontend/scripts/help-screenshots.mjs` (no new dependency): starts the local Edge or Chrome headless, drives it through the DevTools protocol with Node's built-in WebSocket, signs in with credentials from `NOVAQ_HELP_EMAIL` / `NOVAQ_HELP_PASSWORD` (never stored), sets the language and the light theme in local storage, opens each screen, draws the numbered outlines over the live elements and saves the clipped area as WebP (quality 90).

- Refuses any host other than localhost, 127.0.0.1 or [::1].
- Viewport 1280 x 3000 at scale 1, so every marked area is on screen: capturing beyond the viewport re-lays out the page and moved the fixed sidebar over the content (first attempt, discarded).
- The clip spans the content column (left edge at the sidebar's right edge) from 34 px above the first marked element to 20 px below the last, at most 1300 px high, in whole pixels so the image size equals the recorded size.
- Data: a scratch copy of the dev database (`help_shots.db`, copied from `f2_check.db`) with the analyses named "SYNTHETIC ..." (generated in U10). Analysis 10: shared line, customer records, full-day run 70, Decision Revise. The Plans picture runs Optimize on that copy first.

Rerun after a screen changes:

```
NOVAQ_HELP_EMAIL=... NOVAQ_HELP_PASSWORD=... NOVAQ_HELP_ANALYSIS=10 node scripts/help-screenshots.mjs http://localhost:5174
```

then copy the printed sizes into `HELP_FIGURES` (the test fails until they match).

## 4. Help text corrected in the same change

Seen while writing the captions; both contradicted the current code:

- `help.guide.simulation.reading.body` and `continuous.preview_explained` said no Decision is made from the full-day run. Since OD-UX-13 (`a3b541fa`) the Decision uses the selected plan's latest full-day run made with the current data and setup. `help.guide.checks.decision.body` now states the rule.
- `continuous.preview_explained` said breaks are not included. The Setup's counter breaks have been passed to the full-day run since step 12 (`b2a667a8`; `backend/api/shared_continuous.py:322`).

## 5. Tests

`frontend/src/pages/HelpPage.test.tsx`: the picture, alt text, note and numbered list in English; the Tagalog picture and list; no picture for Problems; every listed file exists in both languages with the recorded size (read from the WebP header), with no extra files, and every mark has a caption in both languages and none beyond the count. Mutants 7/7 killed (fixed language, mark count, size, path, no figure, a Problems figure, mark numbering).

## 6. Limits

- The pictures are light theme only; in dark mode they sit on a dark card with a border.
- At phone width the text inside a picture is small; the numbered list carries the content.
- The browser's own "Choose File" button stays English in the Tagalog data picture.
- The pictures go stale when a screen changes; rerun the script.
- Finding (pre-existing, not changed): in Tagalog the Reports page still shows the Decision sentence ("Do not adopt Scenario ... yet.") in English: it is the server's headline (`ReportsPage.tsx:152`). The PDF/Excel section lists are also English, but they are the names inside the files as the server builds them (`ReportsPage.tsx:42`). Both are visible in `tl/downloads.webp`.
