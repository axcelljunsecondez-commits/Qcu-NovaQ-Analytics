# Excel export readability repair

APPROVED SPECIFICATION: owner said “go” after the concrete proposal to repair widths, wrapping, row heights and numeric display formats in the plan/full-report exporter. Eleven native Excel screenshots establish clipping in shared Overview, Your data, Plan, Formula check, Plan search, Decision, Assumptions and Provenance.

Scope: presentation only in `backend/reports/plan_report.py`, plus a focused regression file and this spec/plan/report. Keep the existing openpyxl application generator; this is a repository repair, not replacement of the workbook through a different authoring system. Do not edit existing owner workbooks or the formula writer.

Requirements:

1. Apply consistent legible typography, restrained high-contrast headers, readable column widths and wrapped text to both shared/separate, plan/full exports. Give long descriptions enough row height. Keep existing sheet names/order, row/column coordinates, text, typed values, formulas, blank/zero/unstable semantics and evidence intact.
2. Size period columns for complete time labels. Keep formula helpers visible and all formula strings unchanged. Freeze useful table headers/identifier columns on wide detail sheets; avoid shrinking text to fit.
3. Display waits/costs with sensible decimals and busy shares as percentages. Formula audit results retain higher precision; tiny formula differences remain visible in scientific notation. Saved percent-valued simulation chart data must not be multiplied again by a percentage format. Numeric formatting must never stringify or alter values.
4. Use presentation metadata only: fonts, fills, alignment, dimensions, numeric formats, panes and merges of otherwise empty title/section cells. No added/deleted/reordered data, formulas or report sections. No mathematical, API, database, authentication, frontend, PDF or workflow change.

Verification: reproduce clipping with focused regressions, generate before/after exports from the same captured SYNTHETIC route models, compare every nonempty cell coordinate/type/value/formula and sheet order exactly, independently re-evaluate existing formula checks, render all representative sheets and inspect them, and run repository gates. Record native Excel recalculation separately; renderer QA does not establish native behavior.

The running API is not replaced under this source-formatting approval. Prepare a concrete candidate only after verification if local activation is needed; retain the current image/archive and all unrelated work. No commit, push, production change or Docker cleanup is included.
