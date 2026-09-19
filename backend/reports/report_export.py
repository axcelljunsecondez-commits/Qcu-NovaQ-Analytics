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
from openpyxl.worksheet.worksheet import Worksheet
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
# Separate-Queue full report (selected plan)
# ──────────────────────────────────────────────────────────────────────────────

SEPARATE_DECISION_LABELS = {
    "adopt": "ADOPT",
    "conditional": "CONDITIONAL",
    "revise": "REVISE",
    "insufficient_evidence": "INSUFFICIENT EVIDENCE",
}


def separate_pdf_section_headings(model: dict) -> list[str]:
    """Single source for Separate PDF section headings (preview parity)."""
    decision = ((model.get("decision") or {}).get("status") or "insufficient_evidence")
    return [
        "Separate-Queue Optimization Report",
        f"Decision: {SEPARATE_DECISION_LABELS.get(decision, 'INSUFFICIENT EVIDENCE')}",
        str(model.get("staffing_title") or "Selected Staffing Schedule"),
        "Cost Evidence",
        "Validation",
        "Limitations",
        "Provenance",
    ]


def generate_separate_pdf_report(model: dict) -> io.BytesIO:
    """Generate the management PDF for one selected Separate plan.

    Renders only normalized model values: hours-to-minutes conversion and
    N/A wording happen here, identically for every consumer of the model.
    """
    from reportlab.platypus import Paragraph

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("SepTitle", parent=styles["Title"], fontSize=22, spaceAfter=6)
    subtitle_style = ParagraphStyle("SepSub", parent=styles["Normal"], fontSize=11, textColor=colors.grey)
    h2 = ParagraphStyle("SepH2", parent=styles["Heading2"], spaceBefore=18, spaceAfter=8)
    bullet_style = ParagraphStyle("SepBullet", parent=styles["Normal"], leftIndent=20, spaceAfter=8, fontSize=11)
    cell_style = ParagraphStyle("SepCell", parent=styles["Normal"], fontSize=8, leading=10)
    header_cell = ParagraphStyle("SepHeader", parent=cell_style, fontName="Helvetica-Bold")

    headings = separate_pdf_section_headings(model)
    overview = model.get("overview") or {}
    decision = model.get("decision") or {}
    schedule = model.get("schedule") or {}
    cost = model.get("cost") or {}

    def _table(headers: list[str], rows: list[list[str]], widths: list[float]):
        data = [[Paragraph(h, header_cell) for h in headers]]
        for row in rows:
            data.append([Paragraph(escape(cell), cell_style) for cell in row])
        tbl = Table(data, colWidths=widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5496")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D6E4F0")]),
        ]))
        return tbl

    def _na(value: object) -> str:
        return str(value) if value is not None else "N/A"

    def _pct(value: object) -> str:
        number = _number(value)
        return f"{number:.1%}" if number is not None else "N/A"

    def _minutes(value: object) -> str:
        number = _number(value)
        return f"{number * 60:.2f}" if number is not None else "N/A"

    elements: list = []
    elements.append(Paragraph(headings[0], title_style))
    elements.append(Paragraph(f"Generated: {date.today().isoformat()}", subtitle_style))
    elements.append(Paragraph(
        escape(f"Analysis: {_na(overview.get('analysis_name'))} "
               f"(ID {_na(overview.get('analysis_id'))}) · "
               f"Dataset: {_na(overview.get('dataset_name'))} "
               f"(ID {_na(overview.get('dataset_id'))})"),
        subtitle_style))
    elements.append(Paragraph(
        escape(f"Scenario: {_na(overview.get('scenario_name'))} "
               f"(ID {_na(overview.get('scenario_id'))})"),
        subtitle_style))
    elements.append(PageBreak())

    elements.append(Paragraph(headings[1], h2))
    elements.append(Paragraph(escape(str(decision.get("headline") or "No decision headline.")), bullet_style))
    elements.append(Paragraph(escape(str(decision.get("recommendation") or "")), bullet_style))
    for line in decision.get("rationale") or []:
        elements.append(Paragraph(escape(f"• {line}"), bullet_style))

    elements.append(Paragraph(headings[2], h2))
    elements.append(_table(
        ["Period", "Current Active", "Selected Active", "Adjustment", "Peak Mean Utilization"],
        [[str(p.get("time", "")),
          _staff_count(p.get("current_count")),
          _staff_count(p.get("optimal_active_lanes")),
          "N/A" if p.get("adjustment") is None else str(p.get("adjustment")),
          _pct(p.get("peak_utilization"))]
         for p in schedule.get("periods") or []],
        [1.1 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.4 * inch],
    ))

    elements.append(Paragraph(headings[3], h2))
    for label, value in [
        ("Current waiting cost (analytical)", _money(cost.get("current_waiting"))),
        ("Selected staffing cost", _money(cost.get("selected_staffing"))),
        ("Selected waiting cost (simulation)", _money(cost.get("selected_waiting"))),
        ("Selected total modeled cost", _money(cost.get("selected_total"))),
        ("Savings", "N/A"),
        ("ROI", "N/A"),
    ]:
        elements.append(Paragraph(escape(f"• {label}: {value}"), bullet_style))
    elements.append(Paragraph(
        escape("Current total modeled cost is N/A on a comparable basis; savings and ROI are not computed."),
        bullet_style))
    if cost.get("roi_unavailable_reason"):
        elements.append(Paragraph(escape(f"Why N/A: {cost['roi_unavailable_reason']}"), bullet_style))
    if cost.get("break_overload_note"):
        elements.append(Paragraph(escape(str(cost["break_overload_note"])), bullet_style))

    elements.append(Paragraph(headings[4], h2))
    validation = model.get("validation") or {}
    elements.append(Paragraph(
        escape(f"Overall verdict: {str(validation.get('verdict', 'N/A')).upper()}"), bullet_style))
    for period in validation.get("periods") or []:
        elements.append(Paragraph(
            escape(f"• {period.get('time')}: {str(period.get('status', '')).upper()}"), bullet_style))

    elements.append(Paragraph(headings[5], h2))
    for line in model.get("limitations") or []:
        elements.append(Paragraph(escape(f"• {line}"), bullet_style))

    elements.append(Paragraph(headings[6], h2))
    for key, value in (model.get("provenance") or {}).items():
        elements.append(Paragraph(escape(f"• {key}: {value}"), bullet_style))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_separate_excel_report(model: dict) -> io.BytesIO:
    """Detailed evidence workbook for one selected Separate plan.

    Numbers stay numeric with display formats; unavailable evidence is the
    string "N/A", never zero. Stored waits are hours; minutes conversion
    happens here, matching PDF and preview.
    """
    wb = openpyxl.Workbook()
    pct_fmt = "0.0%"
    money_fmt = '#,##0.00" ₱"'
    min_fmt = "0.00"

    def _put(ws, row: int, label: str, value: object, number_format: str | None = None,
             bold: bool = False) -> None:
        ws.cell(row=row, column=1, value=label).font = Font(bold=bold, size=11)
        cell = ws.cell(row=row, column=2)
        if value is None:
            cell.value = "N/A"
        else:
            cell.value = value
            if number_format:
                cell.number_format = number_format
        cell.font = Font(size=11)

    def _sheet(title: str, headers: list[str]) -> Worksheet:
        ws = wb.active if title == "Overview" else wb.create_sheet(title)
        if title == "Overview":
            ws.title = "Overview"
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=header).font = Font(bold=True)
        ws.column_dimensions["A"].width = 32
        ws.column_dimensions["B"].width = 24
        return ws

    overview = model.get("overview") or {}
    decision = model.get("decision") or {}
    schedule = model.get("schedule") or {}
    cost = model.get("cost") or {}
    current = model.get("current") or {}

    ws = _sheet("Overview", ["Field", "Value"])
    for idx, (label, value) in enumerate([
        ("Analysis", overview.get("analysis_name")),
        ("Dataset", overview.get("dataset_name")),
        ("Scenario", overview.get("scenario_name")),
        ("Scenario ID", overview.get("scenario_id")),
        ("Target", overview.get("target")),
        ("Decision", decision.get("status")),
        ("Evaluation method", (schedule.get("evaluation_method")
                               if "evaluation_method" in schedule else "DES_REPLICATIONS")),
    ], start=2):
        _put(ws, idx, label, value,
             number_format=pct_fmt if label == "Target" and value is not None else None)

    ws_cur = _sheet("Current", ["Time", "Queue", "Lambda", "Rho", "Wq, modeled (min)", "Model"])
    row_idx = 2
    for period in current.get("periods") or []:
        for queue in period.get("queues") or []:
            vals = [period.get("time"), queue.get("queue_id"), queue.get("lambda"),
                    queue.get("rho"),
                    (queue.get("Wq") * 60) if _number(queue.get("Wq")) is not None else None,
                    queue.get("model")]
            for col_idx, val in enumerate(vals, start=1):
                ws_cur.cell(row=row_idx, column=col_idx, value=val)
            if _number(queue.get("rho")) is not None:
                ws_cur.cell(row=row_idx, column=4).number_format = pct_fmt
            if _number(queue.get("Wq")) is not None:
                ws_cur.cell(row=row_idx, column=5).number_format = min_fmt
            row_idx += 1
    for col in ("A", "B", "C", "D", "E", "F"):
        ws_cur.column_dimensions[col].width = 18

    ws_sched = _sheet("Selected Staffing",
                      ["Time", "Current Active", "Selected Active", "Adjustment", "Peak Mean Utilization"])
    for idx, period in enumerate(schedule.get("periods") or [], start=2):
        ws_sched.cell(row=idx, column=1, value=period.get("time"))
        ws_sched.cell(row=idx, column=2, value=period.get("current_count"))
        optimal = period.get("optimal_active_lanes")
        ws_sched.cell(row=idx, column=3,
                      value=int(optimal) if isinstance(optimal, int) and not isinstance(optimal, bool)
                      else (int(optimal) if isinstance(optimal, float) and float(optimal).is_integer() else None))
        adjustment = period.get("adjustment")
        ws_sched.cell(row=idx, column=4, value=adjustment if _is_int(adjustment) else None)
        peak = period.get("peak_utilization")
        ws_sched.cell(row=idx, column=5, value=peak if _number(peak) is not None else "N/A")
        if _number(peak) is not None:
            ws_sched.cell(row=idx, column=5).number_format = pct_fmt
    for col in ("A", "B", "C", "D", "E"):
        ws_sched.column_dimensions[col].width = 20

    des = model.get("des") or {}
    ws_des = _sheet("DES", ["Time", "Queue", "Active", "Arrivals", "Served",
                            "Wq (min)", "Utilization", "Peak Mean Utilization", "Max Queue"])
    row_idx = 2
    for period in des.get("periods") or []:
        peak = None
        for cand in (schedule.get("periods") or []):
            if cand.get("time") == period.get("time"):
                peak = cand.get("peak_utilization")
        for lane in period.get("lanes") or []:
            wq = lane.get("Wq")
            rho = lane.get("rho")
            ws_des.cell(row=row_idx, column=1, value=period.get("time"))
            ws_des.cell(row=row_idx, column=2, value=lane.get("queue_id"))
            ws_des.cell(row=row_idx, column=3, value="yes" if lane.get("active") else ("no" if lane.get("active") is False else "N/A"))
            ws_des.cell(row=row_idx, column=4, value=lane.get("arrivals"))
            ws_des.cell(row=row_idx, column=5, value=lane.get("served"))
            ws_des.cell(row=row_idx, column=6,
                        value=(wq * 60) if _number(wq) is not None else "N/A")
            if _number(wq) is not None:
                ws_des.cell(row=row_idx, column=6).number_format = min_fmt
            ws_des.cell(row=row_idx, column=7,
                        value=rho if _number(rho) is not None else "N/A")
            if _number(rho) is not None:
                ws_des.cell(row=row_idx, column=7).number_format = pct_fmt
            ws_des.cell(row=row_idx, column=8,
                        value=peak if _number(peak) is not None else "N/A")
            if _number(peak) is not None:
                ws_des.cell(row=row_idx, column=8).number_format = pct_fmt
            ws_des.cell(row=row_idx, column=9, value=lane.get("max_queue"))
            row_idx += 1
    for col in ("A", "B", "C", "D", "E", "F", "G", "H", "I"):
        ws_des.column_dimensions[col].width = 18

    ws_mc = _sheet("MonteCarlo", ["Time", "Queue", "Lambda", "Trials", "Failure Rate",
                                  "Cap", "CI Lower", "CI Upper", "Status"])
    row_idx = 2
    mc = model.get("mc") or {}
    for lane in mc.get("lanes") or []:
        ci = lane.get("failure_rate_ci") or [None, None]
        for col_idx, val in enumerate(
                [lane.get("time"), lane.get("queue_id"), lane.get("lambda"),
                 mc.get("num_trials"), lane.get("failure_rate"),
                 mc.get("failure_rate_cap"), ci[0], ci[1], lane.get("status")], start=1):
            ws_mc.cell(row=row_idx, column=col_idx,
                       value=val if val is not None else "N/A")
        row_idx += 1

    ws_val = _sheet("Validation", ["Time", "Queue", "Rho", "Wq (min)",
                                   "Failure Rate", "Verdict"])
    row_idx = 2
    validation = model.get("validation") or {}
    for period in validation.get("periods") or []:
        for queue in period.get("queues") or []:
            wq = queue.get("Wq_sim")
            ws_val.cell(row=row_idx, column=1, value=period.get("time"))
            ws_val.cell(row=row_idx, column=2, value=queue.get("queue_id"))
            rho = queue.get("rho_sim")
            ws_val.cell(row=row_idx, column=3, value=rho if _number(rho) is not None else "N/A")
            if _number(rho) is not None:
                ws_val.cell(row=row_idx, column=3).number_format = pct_fmt
            ws_val.cell(row=row_idx, column=4,
                        value=(wq * 60) if _number(wq) is not None else "N/A")
            if _number(wq) is not None:
                ws_val.cell(row=row_idx, column=4).number_format = min_fmt
            ws_val.cell(row=row_idx, column=5,
                        value=queue.get("mc_failure_rate")
                        if _number(queue.get("mc_failure_rate")) is not None else "N/A")
            ws_val.cell(row=row_idx, column=6, value=queue.get("validation_verdict"))
            row_idx += 1

    ws_dec = _sheet("Decision", ["Field", "Value"])
    _put(ws_dec, 2, "Status", decision.get("status"))
    _put(ws_dec, 3, "Headline", decision.get("headline"))
    _put(ws_dec, 4, "Recommendation", decision.get("recommendation"))
    for idx, line in enumerate(decision.get("rationale") or [], start=5):
        _put(ws_dec, idx, f"Rationale {idx - 4}", line)
    after = 5 + len(decision.get("rationale") or [])
    _put(ws_dec, after, "Failed periods",
         ", ".join(decision.get("failed_periods") or []) or "N/A")

    ws_cost = _sheet("Cost", ["Metric", "Value"])
    _put(ws_cost, 2, "Current waiting cost (analytical)", cost.get("current_waiting"), money_fmt)
    _put(ws_cost, 3, "Current total modeled cost", cost.get("current_total"))
    _put(ws_cost, 4, "Selected staffing cost", cost.get("selected_staffing"), money_fmt)
    _put(ws_cost, 5, "Selected waiting cost (simulation)", cost.get("selected_waiting"), money_fmt)
    _put(ws_cost, 6, "Selected total modeled cost", cost.get("selected_total"), money_fmt)
    _put(ws_cost, 7, "Savings", cost.get("savings"))
    _put(ws_cost, 8, "ROI", cost.get("roi"))
    if cost.get("roi_unavailable_reason"):
        _put(ws_cost, 9, "Why N/A", cost.get("roi_unavailable_reason"))
    if cost.get("break_overload_note"):
        _put(ws_cost, 10, "Break overload note", cost.get("break_overload_note"))

    ws_lim = _sheet("Limitations", ["Limitation"])
    for idx, line in enumerate(model.get("limitations") or [], start=2):
        ws_lim.cell(row=idx, column=1, value=line)
    ws_lim.column_dimensions["A"].width = 120

    ws_prov = _sheet("Provenance", ["Field", "Value"])
    for idx, (label, key) in enumerate([
        ("Scenario ID", "scenario_id"),
        ("Analysis ID", "analysis_id"),
        ("Dataset ID", "dataset_id"),
        ("DES job ID", "des_job_id"),
        ("MC job ID", "mc_job_id"),
        ("Validation job ID", "validation_job_id"),
        ("Decision job ID", "decision_job_id"),
        ("Optimization engine", "optimization_engine"),
        ("Generated at", "generated_at"),
    ], start=2):
        _put(ws_prov, idx, label, (model.get("provenance") or {}).get(key))

    plans = model.get("comparison_plans") or []
    if plans:
        ws_plans = _sheet("Plans", ["Scenario", "Target", "Overall"])
        for idx, plan in enumerate(plans, start=2):
            ws_plans.cell(row=idx, column=1, value=plan.get("name"))
            target = plan.get("target")
            ws_plans.cell(row=idx, column=2, value=target if _number(target) is not None else "N/A")
            if _number(target) is not None:
                ws_plans.cell(row=idx, column=2).number_format = pct_fmt
            ws_plans.cell(row=idx, column=3, value=plan.get("overall"))

    buf = io.BytesIO()
    for sheet in wb:
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    wb.save(buf)
    buf.seek(0)
    return buf


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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
            f"• Average customer wait (modeled): {wq_current * 60:.1f} min → "
            f"{wq_opt * 60:.1f} min (optimized)"
        )
    elif wq_current is not None:
        bullets.append(f"• Average customer wait (modeled): {wq_current * 60:.1f} min (current)")
    else:
        bullets.append("• Average customer wait (modeled): N/A")

    if recommended_kpis:
        savings = recommended_kpis.get("total_savings")
        if savings is not None:
            bullets.append(f"• Estimated daily savings: ₱{savings:,.0f}")
        else:
            bullets.append("• Estimated daily savings: N/A")
            if recommended_kpis.get("roi_unavailable_reason"):
                bullets.append(f"• Why N/A: {recommended_kpis['roi_unavailable_reason']}")

    rho_current = current_kpis.get("avg_utilization", recommended_kpis.get("avg_utilization_current"))
    rho_opt = recommended_kpis.get("avg_utilization_optimized")
    if rho_current is not None and rho_opt is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} → {rho_opt:.0%}")
    elif rho_current is not None:
        bullets.append(f"• Utilization improvement: {rho_current:.0%} (current)")
    else:
        bullets.append("• Utilization improvement: N/A")
    return bullets


# ──────────────────────────────────────────────────────────────────────────────
# Shared PDF Report
# ──────────────────────────────────────────────────────────────────────────────


def generate_pdf_report(
    current_kpis: dict,    recommended_kpis: dict,
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
        "Curr Wq, modeled (min)",
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
        if recommended_kpis.get("total_savings") is None and recommended_kpis.get("roi_unavailable_reason"):
            labels_values.append(("Why Savings Is N/A", str(recommended_kpis["roi_unavailable_reason"])))

        avg_w_cur = recommended_kpis.get("avg_waiting_current")
        avg_w_opt = recommended_kpis.get("avg_waiting_optimized")
        if avg_w_cur is not None:
            labels_values.append(("Avg Wait Current, modeled (min)", f"{avg_w_cur * 60:.2f}"))
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
            labels_values.append(("Avg Wait Current, modeled (min)", f"{avg_w_cur * 60:.2f}"))
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
