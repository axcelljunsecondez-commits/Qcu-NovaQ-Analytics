"""PDF and Excel report generation for the QCU Queueing Dashboard."""

from __future__ import annotations

import io
import json
import math
from datetime import date
from xml.sax.saxutils import escape

import openpyxl
import pandas as pd

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _number(value: object) -> float | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def _money(value: object) -> str:
    number = _number(value)
    return f"₱{number:,.2f}" if number is not None else "N/A"


def _staff_count(value: object) -> str:
    """Render a staffing endpoint for report tables.

    Integers (including integral floats from mixed pandas columns) render
    exactly; missing values render N/A, never zero-filled and never the
    literal strings 'None'/'nan'. A genuine zero renders as '0'.
    """
    if isinstance(value, bool):
        return "N/A"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return value.strip()
    return "N/A"


def _utilization_status(rho: object) -> str:
    value = _number(rho)
    if value is None:
        return "Unavailable"
    if value > 1:
        return "Unstable"
    if value >= 0.9:
        return "Critical"
    if value > 0.8:
        return "Peak"
    if value >= 0.6:
        return "Normal"
    return "Lean"


def _status_color(status: str):
    return {
        "Lean": colors.HexColor("#E5E7EB"),
        "Normal": colors.HexColor("#22C55E"),
        "Peak": colors.HexColor("#F59E0B"),
        "Critical": colors.HexColor("#EF4444"),
        "Unstable": colors.HexColor("#991B1B"),
    }.get(status, colors.HexColor("#E5E7EB"))


def _status_fill(status: str) -> PatternFill:
    return PatternFill(
        fill_type="solid",
        fgColor={
            "Lean": "E5E7EB",
            "Normal": "22C55E",
            "Peak": "F59E0B",
            "Critical": "EF4444",
            "Unstable": "991B1B",
        }.get(status, "E5E7EB"),
    )


def _plural_cashier(count: int) -> str:
    return "cashier" if abs(count) == 1 else "cashiers"


def _merge_time_ranges(times: list[str]) -> list[str]:
    ranges: list[str] = []
    for time in times:
        start, sep, end = time.partition("-")
        last = ranges[-1] if ranges else ""
        last_start, last_sep, last_end = last.partition("-")
        if sep and last_sep and last_end == start:
            ranges[-1] = f"{last_start}-{end}"
        else:
            ranges.append(time)
    return ranges


def _staffing_change_lines(comparison_df: pd.DataFrame) -> list[str]:
    if "delta_c" not in comparison_df.columns:
        return []
    grouped: dict[int, list[str]] = {}
    for _, row in comparison_df.iterrows():
        delta = row.get("delta_c")
        if pd.isna(delta) or int(delta) == 0:
            continue
        grouped.setdefault(int(delta), []).append(str(row.get("time", "")))

    lines: list[str] = []
    for change in sorted(grouped, reverse=True):
        action = "Add" if change > 0 else "Reduce"
        count = abs(change)
        ranges = ", ".join(_merge_time_ranges(grouped[change]))
        lines.append(f"{action} {count} {_plural_cashier(count)}: {ranges}")
    return lines


def _staffing_summary(comparison_df: pd.DataFrame) -> list[tuple[str, str]]:
    if "delta_c" not in comparison_df.columns:
        return []
    if comparison_df["delta_c"].isna().any():
        return [("Staffing Adjustment", "Incomplete: staffing change unavailable")]
    added = int(sum(max(0, row.get("delta_c") or 0) for _, row in comparison_df.iterrows()))
    removed = int(sum(max(0, -(row.get("delta_c") or 0)) for _, row in comparison_df.iterrows()))
    net = removed - added
    peak = None
    if "c_optimal" in comparison_df.columns and not comparison_df.empty and comparison_df["c_optimal"].notna().all():
        peak = int(comparison_df["c_optimal"].max())

    if net > 0:
        net_label = f"{net} cashier-hours reduced"
    elif net < 0:
        net_label = f"{abs(net)} cashier-hours added"
    else:
        net_label = "No net staffing change"

    rows = [
        ("Net Staffing Change", net_label),
        ("Cashier-Hour Formula", f"{removed} removed - {added} added"),
    ]
    if peak is not None:
        rows.append(("Peak Optimized Requirement", f"{peak} {_plural_cashier(peak)}"))
    return rows


STATUS_LEGEND = [
    ("Lean", "< 60%"),
    ("Normal", "60%-80%"),
    ("Peak", "> 80%-< 90%"),
    ("Critical", ">= 90%"),
    ("Unstable", "> 100%"),
]

SEPARATE_OPTIMIZATION_BLOCKED_REASON = "BLOCKED — DEMAND ALLOCATION POLICY NOT DEFINED"


def current_only_blocked_lines() -> list[str]:
    """Current-only status lines for verified separate analyses.

    One adaptive framework: callers reuse the existing minute conversion
    (Wq*60) and staffing helpers (_staffing_summary/_staffing_change_lines);
    this helper only supplies BLOCKED / N-A wording so no c_optimal,
    savings, or ROI is fabricated. Missing values remain N/A, never zero.
    """
    return [
        f"Optimization: {SEPARATE_OPTIMIZATION_BLOCKED_REASON}",
        "Compare: NOT APPLICABLE (no verified optimized scenario)",
        "Decision: NOT AVAILABLE FOR OPTIMIZATION RECOMMENDATION",
    ]

# ──────────────────────────────────────────────────────────────────────────────
# PDF Report
# ──────────────────────────────────────────────────────────────────────────────


def _exec_summary_bullets(current_kpis: dict, recommended_kpis: dict) -> list[str]:
    """Build the executive-summary bullets from available KPI sets.

    Renders "current → optimized" when both sets are present, "current" only
    when no optimization data exists, and N/A otherwise. Savings lines are
    only emitted when optimization KPIs exist (avoids a bogus ₱0).
    """
    bullets: list[str] = []
    wq_current = current_kpis.get("avg_waiting_time", recommended_kpis.get("avg_waiting_current"))
    wq_opt = recommended_kpis.get("avg_waiting_optimized")
    if wq_current is not None and wq_opt is not None:
        bullets.append(
            f"• Average customer wait: {wq_current * 60:.1f} min → "
            f"{wq_opt * 60:.1f} min (optimized)"
        )
    elif wq_current is not None:
        bullets.append(f"• Average customer wait: {wq_current * 60:.1f} min (current)")
    else:
        bullets.append("• Average customer wait: N/A")

    if recommended_kpis:
        savings = recommended_kpis.get("total_savings")
        if savings is not None:
            bullets.append(f"• Estimated daily savings: ₱{savings:,.0f}")
        else:
            bullets.append("• Estimated daily savings: N/A")

    rho_current = current_kpis.get("avg_utilization", recommended_kpis.get("avg_utilization_current"))
    rho_opt = recommended_kpis.get("avg_utilization_optimized")
    if rho_current is not None and rho_opt is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} → {rho_opt:.0%}")
    elif rho_current is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} (current)")
    else:
        bullets.append("• Utilization improvement: N/A")
    return bullets


def generate_pdf_report(
    current_kpis: dict,
    recommended_kpis: dict,
    comparison_df: pd.DataFrame,
    recommendations: list[str] | None = None,
) -> io.BytesIO:
    """Generate a multi-page PDF report.

    Parameters
    ----------
    current_kpis : dict
        KPIs from ``compute_kpis()`` (Page 1).
    recommended_kpis : dict
        KPIs from ``compute_comparison_kpis()`` (Page 2).
    comparison_df : pd.DataFrame
        Segment-by-segment comparison rows (Page 4).
    recommendations : list of str, optional
        Recommendation messages from ``build_recommendations()``.

    Returns
    -------
    io.BytesIO
        In-memory PDF file.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    # ── Custom styles ────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=22, spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=11, textColor=colors.grey
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=18, spaceAfter=8)
    bullet_style = ParagraphStyle(
        "Bullet", parent=styles["Normal"], leftIndent=20, spaceAfter=8, fontSize=11
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"], fontSize=8, leading=10
    )
    header_cell = ParagraphStyle(
        "HeaderCell", parent=cell_style, fontName="Helvetica-Bold"
    )

    elements: list = []

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 1 — Title
    # ══════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("QCU Queue Analysis Report", title_style))
    elements.append(Paragraph(f"Generated: {date.today().isoformat()}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("<hr/>", ParagraphStyle("HR", fontSize=2)))
    elements.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 2 — Executive Summary
    # ══════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("Executive Summary", h2))

    bullet_items = _exec_summary_bullets(current_kpis, recommended_kpis)
    if recommended_kpis.get("comparison_complete") is False:
        bullet_items.append("Comparison incomplete: aggregate savings are unavailable.")
    bullet_items.append("Staffing totals assume one-hour segments. Modeled costs are not payroll savings or employee schedules.")

    for item in bullet_items:
        elements.append(Paragraph(escape(item), bullet_style))

    staffing_summary = _staffing_summary(comparison_df)
    staffing_lines = _staffing_change_lines(comparison_df)
    if staffing_summary:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Staffing Adjustment Summary", h2))
        for label, value in staffing_summary:
            elements.append(Paragraph(escape(f"• {label}: {value}"), bullet_style))
        for line in staffing_lines:
            elements.append(Paragraph(escape(f"• {line}"), bullet_style))

    elements.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 3 — Segment Comparison Table
    # ══════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("Segment Comparison", h2))

    # Build table data
    headers = [
        "Time",
        "Curr c",
        "Curr ρ",
        "Curr Status",
        "Curr Wq (min)",
        "Opt c",
        "Opt ρ",
        "Opt Status",
        "Opt Wq (min)",
    ]
    table_data = [
        [Paragraph(h, header_cell) for h in headers]
    ]

    for _, row in comparison_df.iterrows():
        table_data.append(
            [
                Paragraph(escape(str(row.get("time", ""))), cell_style),
                Paragraph(_staff_count(row.get("c_current")), cell_style),
                Paragraph(
                    f"{row['rho_current']:.1%}" if pd.notna(row.get("rho_current")) else "N/A",
                    cell_style,
                ),
                Paragraph(_utilization_status(row.get("rho_current")), cell_style),
                Paragraph(
                    f"{row['Wq_current'] * 60:.2f}" if pd.notna(row.get("Wq_current")) else "N/A",
                    cell_style,
                ),
                Paragraph(_staff_count(row.get("c_optimal")), cell_style),
                Paragraph(
                    f"{row['rho_optimal']:.1%}" if pd.notna(row.get("rho_optimal")) else "N/A",
                    cell_style,
                ),
                Paragraph(_utilization_status(row.get("rho_optimal")), cell_style),
                Paragraph(
                    f"{row['Wq_optimal'] * 60:.2f}" if pd.notna(row.get("Wq_optimal")) else "N/A",
                    cell_style,
                ),
            ]
        )

    col_widths = [
        0.75 * inch,
        0.55 * inch,
        0.65 * inch,
        0.75 * inch,
        0.8 * inch,
        0.55 * inch,
        0.65 * inch,
        0.75 * inch,
        0.8 * inch,
    ]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5496")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D6E4F0")]),
            ]
        )
    )
    elements.append(tbl)

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Utilization Status Legend", h2))
    legend_data = [[Paragraph("Status", header_cell), Paragraph("ρ Range", header_cell)]]
    for status, threshold in STATUS_LEGEND:
        legend_data.append([Paragraph(status, cell_style), Paragraph(threshold, cell_style)])
    legend = Table(legend_data, colWidths=[1.2 * inch, 1.4 * inch], repeatRows=1)
    legend.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5496")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    for row_idx, (status, _) in enumerate(STATUS_LEGEND, start=1):
        legend.setStyle(TableStyle([("BACKGROUND", (0, row_idx), (0, row_idx), _status_color(status))]))
    elements.append(legend)
    elements.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 4 — Recommendations
    # ══════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("Recommendations", h2))
    if recommendations:
        for rec in recommendations:
            elements.append(Paragraph(escape(f"• {rec}"), bullet_style))
    else:
        elements.append(Paragraph("Run an optimization and save it as a scenario to get staffing recommendations.", bullet_style))

    doc.build(elements)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────────────────────────────────────
# Excel Report
# ──────────────────────────────────────────────────────────────────────────────


def generate_excel_report(
    comparison_df: pd.DataFrame,
    recommended_kpis: dict | None = None,
    current_kpis: dict | None = None,
    recommendations: list[str] | None = None,
) -> io.BytesIO:
    """Generate an Excel workbook with summary, segment, and recommendation evidence.

    Parameters
    ----------
    comparison_df : pd.DataFrame
        Segment-by-segment comparison (Page 4).
    recommended_kpis : dict, optional
        KPIs for the Summary sheet.
    current_kpis : dict, optional
        Current-metric KPIs (``compute_kpis`` output); used for the Summary
        sheet when no optimization KPIs exist (dataset reports).
    recommendations : list of str, optional
        Decision or analytical recommendation messages.

    Returns
    -------
    io.BytesIO
        In-memory ``.xlsx`` file.
    """
    wb = openpyxl.Workbook()

    # ── Sheet 1: Summary ─────────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = "Summary"

    bold_font = Font(bold=True, size=12)
    value_font = Font(size=12)
    pct_fmt = "0.0%"
    money_fmt = '#,##0.00" ₱"'

    labels_values: list[tuple[str, str]] = []

    if recommended_kpis:
        server_change = recommended_kpis.get("total_server_change")
        labels_values = [
            ("Metric", "Value"),
            ("Total Current Cost", _money(recommended_kpis.get("total_current_cost"))),
            ("Total Optimized Cost", _money(recommended_kpis.get("total_optimized_cost"))),
            ("Total Savings", _money(recommended_kpis.get("total_savings"))),
            ("Total Server Change", str(server_change) if server_change is not None else "N/A"),
        ]

        avg_w_cur = recommended_kpis.get("avg_waiting_current")
        avg_w_opt = recommended_kpis.get("avg_waiting_optimized")
        if avg_w_cur is not None:
            labels_values.append(("Avg Wait Current (min)", f"{avg_w_cur * 60:.2f}"))
        if avg_w_opt is not None:
            labels_values.append(("Avg Wait Optimized (min)", f"{avg_w_opt * 60:.2f}"))

        util_cur = recommended_kpis.get("avg_utilization_current")
        util_opt = recommended_kpis.get("avg_utilization_optimized")
        if util_cur is not None:
            labels_values.append(("Avg Utilization Current", f"{util_cur:.1%}"))
        if util_opt is not None:
            labels_values.append(("Avg Utilization Optimized", f"{util_opt:.1%}"))

        impr = recommended_kpis.get("avg_utilization_improvement")
        if impr is not None:
            labels_values.append(("Utilization Improvement", f"{impr:.1%}"))

        impr_pct = recommended_kpis.get("waiting_time_improvement_pct")
        if impr_pct is not None:
            labels_values.append(("Waiting Time Improvement", f"{impr_pct:.1f}%"))

        staffing_summary = _staffing_summary(comparison_df)
        if staffing_summary:
            labels_values.append(("", ""))
            labels_values.append(("Staffing Adjustment Summary", ""))
            labels_values.extend(staffing_summary)
            for line in _staffing_change_lines(comparison_df):
                labels_values.append(("Schedule Action", line))

            labels_values.append(("", ""))
            labels_values.append(("Utilization Status Legend", ""))
            labels_values.extend(
                (f"{status} Status", threshold) for status, threshold in STATUS_LEGEND
            )

    elif current_kpis:
        avg_w_cur = current_kpis.get("avg_waiting_time")
        if avg_w_cur is not None:
            labels_values.append(("Avg Wait Current (min)", f"{avg_w_cur * 60:.2f}"))
        util_cur = current_kpis.get("avg_utilization")
        if util_cur is not None:
            labels_values.append(("Avg Utilization Current", f"{util_cur:.1%}"))

    for row_idx, (label, value) in enumerate(labels_values, start=1):
        cell_lbl = ws_summary.cell(row=row_idx, column=1, value=label)
        cell_lbl.font = bold_font if row_idx == 1 else Font(size=11)
        cell_val = ws_summary.cell(row=row_idx, column=2, value=value)
        cell_val.font = value_font if row_idx == 1 else Font(size=11)

    ws_summary.column_dimensions["A"].width = 32
    ws_summary.column_dimensions["B"].width = 22

    # ── Sheet 2: Segments ───────────────────────────────────────────────
    ws_segments = wb.create_sheet("Segments")

    export_df = comparison_df.copy()
    if "rho_current" in export_df.columns:
        insert_at = export_df.columns.get_loc("rho_current") + 1
        export_df.insert(
            insert_at,
            "rho_current_status",
            export_df["rho_current"].map(_utilization_status),
        )
    if "rho_optimal" in export_df.columns:
        insert_at = export_df.columns.get_loc("rho_optimal") + 1
        export_df.insert(
            insert_at,
            "rho_optimal_status",
            export_df["rho_optimal"].map(_utilization_status),
        )

    # Write header
    headers = list(export_df.columns)
    for col_idx, h in enumerate(headers, start=1):
        cell = ws_segments.cell(row=1, column=col_idx, value=h)
        cell.font = Font(bold=True)

    # Write data rows
    for row_idx, (_, row) in enumerate(export_df.iterrows(), start=2):
        for col_idx, h in enumerate(headers, start=1):
            val = row.get(h)
            cell = ws_segments.cell(row=row_idx, column=col_idx)
            # Format percentages and costs
            if isinstance(val, (dict, list)):
                cell.value = json.dumps(val, ensure_ascii=False, sort_keys=True)
            elif h in ("rho_current", "rho_optimal") and val is not None:
                cell.value = val
                cell.number_format = pct_fmt
            elif h.startswith("cost_") and val is not None:
                cell.value = val
                cell.number_format = money_fmt
            elif h.startswith("Wq_") and val is not None:
                cell.value = val * 60  # convert to minutes
                cell.number_format = "0.00"
            elif h.endswith("_status") and val is not None:
                cell.value = val
                cell.fill = _status_fill(str(val))
            else:
                cell.value = val if pd.notna(val) else None

    # Auto-fit column widths
    for col_idx, h in enumerate(headers, start=1):
        max_len = len(str(h))
        for row_idx in range(2, len(export_df) + 2):
            cell_val = ws_segments.cell(row=row_idx, column=col_idx).value
            if cell_val is not None:
                max_len = max(max_len, len(str(cell_val)))
        ws_segments.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 30)

    # Autofilter
    ws_segments.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(export_df) + 1}"

    if recommendations:
        ws_recommendations = wb.create_sheet("Recommendations")
        header = ws_recommendations.cell(row=1, column=1, value="Recommendation Evidence")
        header.font = Font(bold=True, size=12)
        for row_idx, message in enumerate(recommendations, start=2):
            ws_recommendations.cell(row=row_idx, column=1, value=message)
        ws_recommendations.column_dimensions["A"].width = 100

    buf = io.BytesIO()
    # Force all strings to text even when a scenario supplies a formula prefix.
    for sheet in wb:
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    wb.save(buf)
    buf.seek(0)
    return buf
