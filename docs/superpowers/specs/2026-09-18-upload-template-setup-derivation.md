# Upload Template with Setup Derivation — Specification (2026-09-18)

Revised 2026-09-18 with the user's decisions on the export, queue order,
outside-shift events and segments without `staff` (see "Revision").

## Problem (verified against the code and NovaMart `novaq_data.xlsx`)

- **An upload never writes Setup.**
  - A new analysis starts with an empty (`unknown`) Setup
    (`backend/api/datasets.py:102-109`).
  - An upload into an existing analysis leaves Setup unchanged
    (`backend/api/analyses.py:175-225`).
- **XLSX uploads read only the first worksheet** (`pd.read_excel` defaults,
  `backend/data/uploads.py:91`).
- **Setup facts are typed by hand.**
  - The separate-queue events template has four columns: `arrival_time`,
    `service_start`, `service_end`, `queue_id`.
  - Everything else is typed into Setup. For NovaMart that means 5 queue IDs,
    13 hourly segments each with its active cashiers, and 15 break rows.
  - The draft `novaq_upload_template.xlsx` carries this as a
    `setup_to_enter` guide sheet, so the same facts are entered twice.
- **Events alone cannot tell a break from an idle cashier.** The user
  reported that 764 of 1,455 NovaMart customers who waited more than 5 minutes
  had their cashier idle for more than 5 minutes during that wait. This figure
  has not been recomputed; a recount on 2026-09-18 with a different
  definition gave 1,265 of 1,517. Shifts and breaks must be stated in the
  file, not inferred from gaps.
- **Raw customer events are not stored.** A dataset keeps only per-period
  aggregates and service durations (`backend/data/analysis_ingestion.py:299-316`,
  `backend/db/models.py:131-150`), so NovaQ cannot export the events later.

## Approved product decisions (user, 2026-09-18)

1. **Setup comes from the file.** The file states only facts the data cannot
   show (shifts, breaks). NovaQ derives every other Setup field. No field is
   entered twice.
2. **`break_name` is an optional display label.** When it is blank, the label
   is "Break 1, 2, 3" in time order per queue. Break order comes from start
   time.
3. **Confirm before replacing.** When the analysis already has a saved Setup,
   show what NovaQ read next to the saved Setup, and replace it only after the
   user confirms. A new or `unknown` Setup is filled directly.
4. **Export staff and breaks.** After upload, the user can download a workbook
   with the `staff` and `breaks` sheets, filled from the analysis Setup, to
   check it and reuse it. Raw events are not stored, so they are not exported.
5. **`staff` and `breaks` sheets are optional.**
   - With no `staff` sheet, every queue works every segment (fixed staffing).
   - With no `breaks` sheet, there are no breaks.
   - A sheet with a header row but no data rows counts as absent.

## Template (separate queues, events)

One workbook with three sheets, matched by sheet name (case-insensitive,
trimmed):

| Sheet | Columns | Required |
|---|---|---|
| `events` | `arrival_time`, `service_start`, `service_end`, `queue_id` | yes |
| `staff` | `queue_id`, `shift_start`, `shift_end` | no |
| `breaks` | `queue_id`, `break_name`, `start`, `minutes` | no |

- Times in `staff` and `breaks` are wall-clock `HH:MM`. `HH:MM:SS` and Excel
  time cells are also accepted.
- `minutes` is a positive whole number.
- The downloaded template also keeps its `Example` and `Field Guide` sheets.
  They are ignored on upload.
- The shared-queue events template is unchanged (one sheet, no `staff` or
  `breaks`).

## Reading a workbook

- If the workbook has a sheet named `events`, use multi-sheet mode and read
  `events`, `staff` and `breaks` by name.
- Otherwise use legacy mode: read the first sheet exactly as today. Existing
  files behave the same.
- CSV uploads are always legacy (events only).
- Existing upload limits apply to each sheet read: rows, columns, cell size
  and parsed memory per sheet, plus the archive checks and worksheet count
  once per workbook.

## Derived Setup (multi-sheet mode)

| Setup field | Derived from |
|---|---|
| `queue_structure` | `separate_queues` (the `events` sheet has `queue_id`) |
| `queue_ids` | Row order of the `staff` sheet when it is present. Otherwise distinct `events.queue_id` in order of first appearance. |
| `segments` | With `staff`: hourly boundaries from the earliest shift start to the latest shift end, plus any shift start or end that is not on the hour. Without `staff`: whole hours from the first arrival's hour to the next full hour after the last arrival (NovaMart: 05:00 to 18:00, since the last arrival is 17:59). `id` = `HH:MM-HH:MM`. |
| `segments[].active_queue_ids` | With `staff`: the queues whose shift covers the whole segment. Without `staff`: `null`. |
| `staffing_varies_by_period` | True when some segment lacks a configured queue |
| `fixed_server_count` | Number of queues when staffing is fixed. When staffing varies: the saved value (`null` for a new analysis). |
| `event_period_basis` | `representative_day` when arrivals span more than one date, otherwise `per_date` |
| `breaks` | `breaks` sheet rows: `queue_id`, `start` → `scheduled_start_time`, `minutes` → `duration_minutes`, and `break_name` (blank → `null`) |
| `capacity_mode`, `abandonment_mode` | Kept when already set, together with `total_system_capacity` and `patience_rate_per_hour`. When `unknown`: `unlimited` and `not_modeled`. |

Breaks stay breaks. They do not create extra segments; the existing break
lifecycle handles 15- and 30-minute breaks.

## Validation (exact reasons, never silent drops)

All errors are collected and returned together. Row numbers are worksheet
row numbers; the header is row 1. Exact messages:

**Workbook**
- `The workbook has more than one sheet named {sheet}.`
- `The {sheet} sheet is missing columns: {columns}.`
- `The events sheet has no rows.`

**Staff**
- `Staff sheet row {r}: queue_id is empty.`
- `Staff sheet row {r}: {column} must be a time in HH:MM.`
- `Staff sheet row {r}: shift_start must be before shift_end.`
- `The staff sheet lists {queue} more than once (rows {r1} and {r2}).`
- `The staff sheet has no row for: {queues}.`
- `The staff sheet lists queues with no events: {queues}.`

**Breaks**
- `Breaks sheet row {r}: queue_id {queue} is not in the events sheet.`
- `Breaks sheet row {r}: start must be a time in HH:MM.`
- `Breaks sheet row {r}: minutes must be a positive whole number.`
- `Breaks sheet row {r}: break_name must be at most 50 characters.`
- `Breaks sheet row {r}: the {queue} break at {HH:MM} for {m} minutes is outside its shift {HH:MM}–{HH:MM}.`
  Without `staff`, the ending reads `outside the operating day {HH:MM}–{HH:MM}.`
- `Breaks sheet rows {r1} and {r2} overlap for {queue}.`

**Events and segments**
- `{n} events for {queue} arrive outside its shift {HH:MM}–{HH:MM}.`
  - Only `arrival_time` is checked.
  - Service may end after the shift, consistent with the `drain_existing`
    closure policy (`analysis_schemas.py:30-31`).
- `Events that arrive at or after 23:00 cannot be placed in an hourly segment.`
  This applies only without `staff`.
- `Segment {id} has no queue on shift.` This is the existing rule that each
  segment has at least one active queue.
- An unparsable arrival returns the existing ingestion message verbatim, for
  example `Row {n}: arrival_time must be a valid timestamp.`

**Setup and apply**
- `The derived Setup is invalid: {reason}.` The derived Setup must pass the
  existing `QueueSetup` validation.
- The derived Setup is dry-run through `normalize_analysis_input`. Any
  existing ingestion error is returned verbatim.
- `apply_setup requires a workbook with an events sheet.`

## Upload flow

Normalization depends on Setup (`normalize_analysis_input(frame, setup)`,
`analyses.py:207`), so Setup must be settled before events are stored.

1. **Preview.** `POST /analyses/{id}/datasets/preview` parses the file.
   Nothing is stored. It returns:
   - `mode`: `multi_sheet` or `legacy`
   - the derived Setup, the saved Setup, and a per-field diff
   - `needs_confirmation`: the saved `queue_structure` is not `unknown` and
     the diff is not empty
   - the rows read from `staff` and `breaks`
   - validation errors

   Legacy files return `mode: legacy` with no derived Setup.
2. **Show.** The frontend shows "Here's what NovaQ read from your file":
   queues, shifts, segments, breaks and basis. If `needs_confirmation`, it
   shows the changes and asks the user to confirm. Otherwise it applies
   directly.
3. **Apply.** `POST /analyses/{id}/datasets` with `apply_setup=true`
   re-derives the Setup from the file on the server, saves it, and stores the
   normalized dataset in one transaction. Without `apply_setup`, the endpoint
   behaves exactly as today.

## Export

`GET /analyses/{id}/setup/workbook` returns a workbook with two sheets. The
path is under the analysis because the export uses only the Setup.

- **`staff`:** one row per queue, in Setup `queue_ids` order. The shift is the
  queue's continuous run of active segments.
  - When the segments have no `active_queue_ids` (fixed staffing without a
    `staff` sheet), the sheet has headers only, so a re-upload derives the
    same Setup.
  - A queue with more than one active run cannot be exported:
    `Cannot export {queue}: it has more than one shift.`
- **`breaks`:** one row per Setup break, in Setup order. A missing
  `break_name` is exported blank.
- **Non-separate analyses:** `The setup workbook is available for separate queues.`

**Round-trip:** the original `events` sheet plus the exported `staff` and
`breaks` sheets, uploaded into a new analysis, derive an identical Setup.

## Schema change

`QueueBreak` gains `break_name: str | None` (max 50 characters). Existing
Setups without it stay valid.

## Unchanged (protected)

Legacy single-sheet and CSV uploads, the shared-queue template, aggregate
templates, queueing formulas, DES and break lifecycle, representative-day
pooling, optimizer, Decision rules, reports.

## Acceptance

- NovaMart as a three-sheet file (1,600 events, 5 staff rows, 15 break rows)
  uploaded into a new analysis produces:
  - `separate_queues`, `cashier_1..5`, 13 hourly segments 05:00–18:00
  - 05:00 → cashiers 1–3; 06:00–17:00 → all 5; 17:00 → cashiers 4–5
  - `staffing_varies_by_period = true`, `representative_day`, 15 breaks
  - No manual Setup entry.
- It is the same Setup as the draft `setup_to_enter` sheet.
- Round-trip: the original `events` sheet plus the exported `staff` and
  `breaks`, uploaded into a new analysis, derive an identical Setup.
- A legacy four-column file and a CSV behave exactly as before.
- Upload into an analysis with a different saved Setup does not change it
  until confirmed.
- Each validation rule returns its exact message and never drops rows
  silently.

## Out of scope

- Detecting breaks from event gaps.
- `staff` and `breaks` for shared queues.
- The break optimizer itself (built separately).
- Storing raw customer events (own column + migration), and therefore
  exporting an `events` sheet.

## Revision (user, 2026-09-18)

1. **Export:** the export is `staff` + `breaks` only; raw events are not
   stored. Round-trip = original events + exported `staff`/`breaks`.
2. **Queue order:** `staff` row order when present, else first appearance in
   `events`.
3. **Outside shift:** only an `arrival_time` outside the queue's shift is an
   error. Service may end after the shift.
4. **Segments without `staff`:** they end at the next full hour after the last
   arrival. Headers-only `staff`/`breaks` sheets count as absent.
