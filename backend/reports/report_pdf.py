"""B8 PDF for managers and supervisors: the plan report (level 1) and the full report (level 2).

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §1: plain words with no rho or Wq symbols, each chart
followed by its own table, one layout for both line types. Rendered only from the report model, like the preview
and the workbook, so the three cannot disagree.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY, GOLD, LIGHT = colors.HexColor("#14213D"), colors.HexColor("#C9A227"), colors.HexColor("#E8EEF6")


def number(value: Any, digits: int = 2) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "n/a"
    if isinstance(value, int):  # counts (people, customers) are whole numbers
        return f"{value:,}"
    return f"{value:,.{digits}f}"


def percent(value: Any) -> str:
    return "n/a" if isinstance(value, bool) or not isinstance(value, (int, float)) else f"{value * 100:.1f}%"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("B8Title", parent=base["Title"], fontSize=22, textColor=NAVY, spaceAfter=4),
        "label": ParagraphStyle("B8Label", parent=base["Normal"], fontSize=11, textColor=GOLD, spaceAfter=12),
        "h2": ParagraphStyle("B8H2", parent=base["Heading2"], textColor=NAVY, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("B8Body", parent=base["Normal"], fontSize=10, leading=13, spaceAfter=6),
        "cell": ParagraphStyle("B8Cell", parent=base["Normal"], fontSize=8, leading=10),
        "head": ParagraphStyle("B8Head", parent=base["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold",
                               textColor=colors.white),
    }


def _table(styles: Mapping[str, ParagraphStyle], headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> Table:
    data = [[Paragraph(escape(str(text)), styles["head"]) for text in headers]]
    data += [[Paragraph(escape(str(cell)), styles["cell"]) for cell in row] for row in rows]
    # Match the chart width and keep longer provenance labels inside the printable page.
    table = Table(data, colWidths=[460 / len(headers)] * len(headers), repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _chart(title: str, labels: Sequence[str], series: Sequence[tuple[str, Sequence[float | None]]]) -> Flowable:
    drawing = Drawing(460, 190)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 40, 30, 400, 130
    chart.data = [list(values) for _, values in series]
    chart.categoryAxis.categoryNames = [label[:14] for label in labels]
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.valueMin = 0
    for index, colour in enumerate((NAVY, GOLD)[: len(series)]):
        chart.bars[index].fillColor = colour
    drawing.add(chart)
    drawing.add(String(40, 172, title, fontSize=9, fontName="Helvetica-Bold", fillColor=NAVY))
    if len(series) > 1:
        # Standard PDF fonts cannot draw arrows or squares, so the legend is words only.
        legend = "Bars: " + ", ".join(f"{'dark' if index == 0 else 'gold'} = {name}" for index, (name, _) in enumerate(series))
        drawing.add(String(40, 8, legend, fontSize=7, fontName="Helvetica", fillColor=colors.black))
    return drawing


def pdf_sections(model: Mapping[str, Any]) -> list[str]:
    """The PDF's section headings in order; the Reports page lists exactly these, and each is printed as written."""
    sections = ["Key results: now and with the plan", "By period"]
    if model.get("breaks"):
        sections.append("Breaks in the Setup")
    if model.get("report") == "full":
        sections += ["Decision", "Simulation key results", "Checks", "What is not included"]
    return sections


def generate_report_pdf(model: Mapping[str, Any]) -> io.BytesIO:
    """The plan or full report PDF, from the report model only."""
    styles = _styles()
    cover, key, periods = model["cover"], model["key_results"], model["periods"]
    full = model.get("report") == "full"
    now_label = "Current staffing (simulated)" if model.get("line_type") == "separate" else "Now"
    story: list[Flowable] = [
        Paragraph("NovaQ full report" if full else "NovaQ plan report", styles["title"]),
        Paragraph(escape(cover["label"]), styles["label"]),
        _table(styles, ["Item", "Value"], [
            ["Analysis", cover.get("analysis_name")], ["Plan", cover.get("plan_name")],
            ["Lines", "one shared line" if cover.get("line_type") == "shared" else "separate lines"],
            ["Generated (UTC)", cover.get("generated_at")],
        ]),
        Paragraph("Key results: now and with the plan", styles["h2"]),
        _table(styles, ["", now_label, "With the plan"], [
            ["Total cost", number(key.get("cost_now")) if key.get("cost_now") is not None else key.get("cost_now_unavailable"),
             number(key.get("cost_plan"))],
            ["Longest average wait in any period (minutes)", number(key.get("highest_wait_now_minutes")),
             number(key.get("highest_wait_plan_minutes"))],
        ]),
        Paragraph(escape(str(key.get("cost_basis"))), styles["body"]),
    ]
    changes = key.get("counter_changes") or []
    story.append(Paragraph("Counter changes: " + ("; ".join(f"{c['time']}: {c['from']} to {c['to']}" for c in changes)
                                                if changes else "none."), styles["body"]))

    labels = [str(row["time"]) for row in periods]
    story += [
        Paragraph("By period", styles["h2"]),
        KeepTogether([
            _chart("Counters now and with the plan", labels,
                   [(now_label, [row["counters_now"] for row in periods]), ("With the plan", [row["counters_plan"] for row in periods])]),
            _table(styles, ["Period", "Counters now", "With the plan", f"Busy: {now_label}" if model.get("line_type") == "separate" else "Busy now", "Busy with the plan"],
                   [[row["time"], row["counters_now"], row["counters_plan"], percent(row["busy_now"]), percent(row["busy_plan"])]
                    for row in periods]),
            Paragraph("A busy share above 100% means customers arrive faster than the counters can serve them.", styles["body"]),
        ]),
        Spacer(1, 10),
        KeepTogether([
            _chart("Average wait in line, minutes (no bar: counters cannot keep up)", labels,
                   [(now_label, [row["wait_now_minutes"] for row in periods]),
                    ("With the plan", [row["wait_plan_minutes"] for row in periods])]),
            _table(styles, ["Period", f"Wait: {now_label} (min)" if model.get("line_type") == "separate" else "Wait now (min)",
                            "Wait with the plan (min)", f"Cost: {now_label}" if model.get("line_type") == "separate" else "Cost now", "Cost with the plan"],
                   [[row["time"], number(row["wait_now_minutes"]), number(row["wait_plan_minutes"]),
                     number(row["cost_now"]), number(row["cost_plan"])] for row in periods]),
        ]),
    ]
    breaks = model.get("breaks") or []
    if breaks:
        story += [Paragraph("Breaks in the Setup", styles["h2"]), _table(
            styles, ["Line", "Start", "Minutes", "Name"],
            [[item.get("queue_id", "any free counter"), item.get("scheduled_start_time"), item.get("duration_minutes"),
              item.get("break_name") or ""] for item in breaks])]

    if full:
        story += _full_pages(model, styles)
    else:
        story.append(Paragraph("This is a calculated result, not yet checked by simulation.", styles["body"]))
    headings = [item.text for item in story if isinstance(item, Paragraph) and item.style is styles["h2"]]
    assert headings == pdf_sections(model), headings
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                      title="NovaQ full report" if full else "NovaQ plan report").build(story)
    buffer.seek(0)
    return buffer


def _full_pages(model: Mapping[str, Any], styles: Mapping[str, ParagraphStyle]) -> list[Flowable]:
    decision, simulation = model["decision"], model["simulation"]
    story: list[Flowable] = [PageBreak(), Paragraph("Decision", styles["h2"]),
                             Paragraph(escape(str(decision.get("headline"))), styles["body"]),
                             Paragraph(escape(str(decision.get("recommendation"))), styles["body"])]
    if decision.get("scope_notice"):
        story.append(Paragraph(escape(str(decision["scope_notice"])), styles["body"]))
    story += [Paragraph("• " + escape(str(line)), styles["body"]) for line in decision.get("rationale") or []]
    story += [Paragraph("Simulation key results", styles["h2"]), Paragraph(escape(simulation["source"]), styles["body"]),
              _table(styles, ["Result", "Value"], [
                  [item["label"], f"{number(item['value'])} {item['unit']}" if item["value"] is not None else "not recorded by this run"]
                  for item in simulation["headlines"]])]
    for chart in simulation["charts"]:
        points = chart["points"]
        if not points:
            story.append(Paragraph(f"{chart['title']}: not run.", styles["body"]))
            continue
        rows = [[point["label"], number(point["value"])] for point in points]
        title = chart["title"] + (f" (allowed: {number(chart['limit'], 1)}%)" if chart.get("limit") is not None else "")
        story.append(KeepTogether([_chart(title, [p["label"] for p in points], [(chart["unit"], [p["value"] for p in points])]),
                                   _table(styles, ["Period", str(chart["unit"]).capitalize()], rows)]))
    story += [Paragraph("Checks", styles["h2"]),
              _table(styles, ["Check", "Settings", "Outcome"], [[c["check"], c["settings"], c["outcome"]] for c in model["checks"]]),
              Paragraph("What is not included", styles["h2"])]
    story += [Paragraph("• " + escape(line), styles["body"]) for line in model["not_included"] if line]
    return story
