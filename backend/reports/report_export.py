"""PDF and Excel report generation for the QCU Queueing Dashboard."""

from __future__ import annotations

import io
from datetime import date

import openpyxl
import pandas as pd

from backend.queueing_engine.log import get_logger

logger = get_logger(__name__)
from openpyxl.styles import Font
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
    wq_current = current_kpis.get("avg_waiting_time")
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
            bullets.append(f"• Estimated weekly savings: ₱{savings:,.0f}")
        else:
            bullets.append("• Estimated weekly savings: N/A")

    rho_current = current_kpis.get("avg_utilization")
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
    segment_df: pd.DataFrame | None = None,
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
    segment_df : pd.DataFrame, optional
        Accepted for compatibility with the legacy comparison page's call
        pattern; not used in report content (retained as a dead parameter).

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

    for item in bullet_items:
        elements.append(Paragraph(item, bullet_style))

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
        "Curr Wq (min)",
        "Opt c",
        "Opt ρ",
        "Opt Wq (min)",
    ]
    table_data = [
        [Paragraph(h, header_cell) for h in headers]
    ]

    for _, row in comparison_df.iterrows():
        table_data.append(
            [
                Paragraph(str(row.get("time", "")), cell_style),
                Paragraph(str(row.get("c_current", "")), cell_style),
                Paragraph(
                    f"{row['rho_current']:.1%}" if pd.notna(row.get("rho_current")) else "N/A",
                    cell_style,
                ),
                Paragraph(
                    f"{row['Wq_current'] * 60:.2f}" if pd.notna(row.get("Wq_current")) else "N/A",
                    cell_style,
                ),
                Paragraph(str(row.get("c_optimal", "")), cell_style),
                Paragraph(
                    f"{row['rho_optimal']:.1%}" if pd.notna(row.get("rho_optimal")) else "N/A",
                    cell_style,
                ),
                Paragraph(
                    f"{row['Wq_optimal'] * 60:.2f}" if pd.notna(row.get("Wq_optimal")) else "N/A",
                    cell_style,
                ),
            ]
        )

    col_widths = [0.8 * inch, 0.6 * inch, 0.7 * inch, 0.9 * inch, 0.6 * inch, 0.7 * inch, 0.9 * inch]
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
    elements.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # PAGE 4 — Recommendations
    # ══════════════════════════════════════════════════════════════════════
    elements.append(Paragraph("Recommendations", h2))
    if recommendations:
        for rec in recommendations:
            elements.append(Paragraph(f"• {rec}", bullet_style))
    else:
        elements.append(Paragraph("No specific recommendations available.", bullet_style))

    doc.build(elements)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────────────────────────────────────
# Excel Report
# ──────────────────────────────────────────────────────────────────────────────


def generate_excel_report(
    comparison_df: pd.DataFrame,
    recommended_kpis: dict | None = None,
    segment_df: pd.DataFrame | None = None,
    current_kpis: dict | None = None,
) -> io.BytesIO:
    """Generate a two-sheet Excel workbook.

    Parameters
    ----------
    comparison_df : pd.DataFrame
        Segment-by-segment comparison (Page 4).
    recommended_kpis : dict, optional
        KPIs for the Summary sheet.
    segment_df : pd.DataFrame, optional
        Accepted for compatibility with the legacy comparison page's call
        pattern; not used in report content (retained as a dead parameter).
    current_kpis : dict, optional
        Current-metric KPIs (``compute_kpis`` output); used for the Summary
        sheet when no optimization KPIs exist (dataset reports).

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
        labels_values = [
            ("Metric", "Value"),
            ("Total Current Cost", f"₱{recommended_kpis.get('total_current_cost', 0):,.2f}"),
            ("Total Optimized Cost", f"₱{recommended_kpis.get('total_optimized_cost', 0):,.2f}"),
            ("Total Savings", f"₱{recommended_kpis.get('total_savings', 0):,.2f}"),
            ("Total Server Change", str(recommended_kpis.get("total_server_change", 0))),
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

    # Write header
    headers = list(comparison_df.columns)
    for col_idx, h in enumerate(headers, start=1):
        cell = ws_segments.cell(row=1, column=col_idx, value=h)
        cell.font = Font(bold=True)

    # Write data rows
    for row_idx, (_, row) in enumerate(comparison_df.iterrows(), start=2):
        for col_idx, h in enumerate(headers, start=1):
            val = row.get(h)
            cell = ws_segments.cell(row=row_idx, column=col_idx)
            # Format percentages and costs
            if h in ("rho_current", "rho_optimal") and val is not None:
                cell.value = val
                cell.number_format = pct_fmt
            elif h.startswith("cost_") and val is not None:
                cell.value = val
                cell.number_format = money_fmt
            elif h.startswith("Wq_") and val is not None:
                cell.value = val * 60  # convert to minutes
                cell.number_format = "0.00"
            else:
                cell.value = val if pd.notna(val) else None

    # Auto-fit column widths
    for col_idx, h in enumerate(headers, start=1):
        max_len = len(str(h))
        for row_idx in range(2, len(comparison_df) + 2):
            cell_val = ws_segments.cell(row=row_idx, column=col_idx).value
            if cell_val is not None:
                max_len = max(max_len, len(str(cell_val)))
        ws_segments.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 30)

    # Autofilter
    ws_segments.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(comparison_df) + 1}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
