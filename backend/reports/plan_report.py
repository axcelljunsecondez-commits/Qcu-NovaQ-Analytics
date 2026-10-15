"""B8 plan report (level 1): one report model, rendered as the page preview and the Excel workbook.

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §1, §3-§4 (owner answers 2026-10-09). The plan
report is available once a current, verified plan is selected; it is a calculated result, not yet checked by
simulation, so it uses no Decision words. Everything here reads persisted evidence (the selected scenario, its
saved calculation snapshot and the dataset it was verified against); the only recomputation is the optimizer's
list of counter counts for plans saved before that list was stored, labelled as recomputed and used only when it
chooses the same counts as the saved plan.
"""

from __future__ import annotations

import io
import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from backend.queueing_engine.services.model_selection import select_model
from backend.reports.formula_check import NOT_AVAILABLE, formula_row, write_formula_sheet

REPORT_VERSION = "novaq-plan-report-v1"
COVER_LABEL = "Calculated result · not yet checked by simulation"
FAILED_LIMITS = {
    "model_stability": "counters cannot keep up",
    "target_utilization": "busier than the target",
    "analytical_metrics": "no finite wait",
    "max_wait_minutes": "wait above the limit",
    "server_capacity_bounds": "outside the counter limits",
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _minutes(hours: Any) -> float | None:
    value = _finite(hours)
    return None if value is None else value * 60


def _sum_or_none(values: Sequence[Any]) -> float | None:
    numbers = [_finite(value) for value in values]
    return None if not numbers or any(value is None for value in numbers) else math.fsum(numbers)  # type: ignore[arg-type]


def _max_or_none(values: Sequence[Any]) -> float | None:
    numbers = [value for value in (_finite(item) for item in values) if value is not None]
    return max(numbers) if numbers else None


def _counter_changes(periods: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"time": row["time"], "from": row["counters_now"], "to": row["counters_plan"]}
            for row in periods if row["counters_now"] != row["counters_plan"]]


def _cover(analysis: Mapping[str, Any], line_type: str, plan_name: str) -> dict[str, Any]:
    return {"label": COVER_LABEL, "level": "plan", "analysis_name": analysis.get("name"), "line_type": line_type,
            "plan_name": plan_name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# ── Shared line ─────────────────────────────────────────────────────────────


def _shared_candidates(stored: Mapping[str, Any], segment: Mapping[str, Any], options: Mapping[str, Any]
                       ) -> tuple[list[dict[str, Any]] | None, str]:
    """Every counter count the optimizer tried for one period: stored with the plan, or recomputed for older plans."""
    if isinstance(stored.get("candidates"), list):
        return stored["candidates"], "stored"
    from backend.queueing_engine.config import (
        DEFAULT_MAX_SERVERS,
        DEFAULT_SERVER_COST_HR,
        DEFAULT_TARGET_UTILIZATION,
        DEFAULT_WAIT_COST_HR,
    )
    from backend.queueing_engine.services.optimization import optimize_segment

    # The defaults are OptimizeBatchRequest's, so an option absent from the snapshot means what it meant then.
    recomputed = optimize_segment(
        segment,
        target_utilization=float(options.get("target_utilization", DEFAULT_TARGET_UTILIZATION)),
        default_server_cost=float(options.get("server_cost_per_hr", DEFAULT_SERVER_COST_HR)),
        max_servers=int(options.get("max_servers", DEFAULT_MAX_SERVERS)),
        min_servers=int(options.get("min_servers", 1)), max_wait_minutes=options.get("max_wait_minutes"),
        customer_waiting_cost=float(options.get("customer_waiting_cost", DEFAULT_WAIT_COST_HR)),
        cost_per_abandonment=float(options.get("cost_per_abandonment", 0.0)),
        abandonment_rate=float(options.get("abandonment_rate", 0.0)))
    if recomputed.get("c_optimal") != stored.get("c_optimal"):
        return None, "unavailable"
    return recomputed.get("candidates"), "recomputed"


def build_shared_plan_model(*, analysis: Mapping[str, Any], scenario: Mapping[str, Any], dataset: Mapping[str, Any],
                            setup: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = (scenario.get("settings") or {}).get("calculation") or {}
    options = snapshot.get("options") or {}
    inputs = snapshot.get("input_segments") or []
    results = (scenario.get("results") or {}).get("results") or []
    periods, formula_rows, search_rows = [], [], []
    sources = set()
    for segment, row in zip(inputs, results):
        lam, mu = _finite(segment.get("lambda")), _finite(segment.get("mu"))
        variance, capacity, theta = segment.get("variance"), segment.get("K"), segment.get("theta")
        now, plan = row.get("c_current"), row.get("c_optimal")
        periods.append({
            "time": row.get("time"), "lambda": lam, "mu": mu, "counters_now": now, "counters_plan": plan,
            "busy_now": _finite(row.get("rho_current")), "busy_plan": _finite(row.get("rho_optimal")),
            "wait_now_minutes": _minutes(row.get("Wq_current")), "wait_plan_minutes": _minutes(row.get("Wq_optimal")),
            "cost_now": _finite(row.get("cost_current")), "cost_plan": _finite(row.get("cost_optimal")),
            "model": row.get("selected_model"),
        })
        for staffing, counters, lq, wq in (("Now", now, row.get("Lq_current"), row.get("Wq_current")),
                                           ("Plan", plan, row.get("Lq_optimal"), row.get("Wq_optimal"))):
            if not isinstance(counters, int) or lam is None or mu is None:
                continue
            selected = select_model(lam, mu, counters, variance, capacity, theta)
            metrics = selected.get("metrics") or {}
            steps = None
            if metrics.get("blocking_probability") is not None:
                steps = f"{NOT_AVAILABLE}; share turned away {metrics['blocking_probability']:.6g} (K = {capacity})"
            elif metrics.get("abandonment_rate") is not None:
                steps = f"{NOT_AVAILABLE}; share who leave {metrics['abandonment_rate']:.6g} (theta = {theta}/hour)"
            formula_rows.append(formula_row(period=str(row.get("time")), staffing=staffing, model=selected["name"],
                                            lam=lam, mu=mu, c=counters, variance=variance, novaq_lq=lq,
                                            novaq_wq_hours=wq, steps=steps))
        scaled = {**segment, "lambda": lam}
        candidates, source = _shared_candidates(row, scaled, options)
        sources.add(source)
        for candidate in candidates or []:
            chosen = candidate.get("servers") == plan
            failed = [FAILED_LIMITS.get(item, item) for item in candidate.get("failed_limits") or []]
            search_rows.append({
                "time": row.get("time"), "counters": candidate.get("servers"),
                "result": "chosen" if chosen else ("meets the limits" if candidate.get("feasible") else "fails: " + ", ".join(failed)),
                "busy": _finite(candidate.get("rho")), "wait_minutes": _minutes(candidate.get("Wq")),
                "counter_cost": _finite(candidate.get("server_cost")), "waiting_cost": _finite(candidate.get("waiting_cost")),
                "total_cost": _finite(candidate.get("total_cost")),
            })
    cost_now = _sum_or_none([row["cost_now"] for row in periods])
    return {
        "report": "plan", "version": REPORT_VERSION, "line_type": "shared",
        "cover": _cover(analysis, "shared", str(scenario.get("name"))),
        "data": {"dataset_id": dataset.get("id"), "dataset_name": dataset.get("name"), "rows": list(inputs)},
        "key_results": {
            "cost_now": cost_now, "cost_plan": _sum_or_none([row["cost_plan"] for row in periods]),
            "cost_basis": "Counter cost plus waiting cost per hour, added over the periods (NovaQ's queue model).",
            "cost_now_unavailable": None if cost_now is not None else
            "Today's total cost is not available because counters can't keep up in at least one period today.",
            "highest_wait_now_minutes": _max_or_none([row["wait_now_minutes"] for row in periods]),
            "highest_wait_plan_minutes": _max_or_none([row["wait_plan_minutes"] for row in periods]),
            "counter_changes": _counter_changes(periods),
        },
        "periods": periods,
        "breaks": [dict(item) for item in setup.get("counter_breaks") or []],
        "formula_check": formula_rows,
        "plan_search": {"method": "NovaQ's queue model for every counter count from the minimum to the maximum",
                        "source": "unavailable" if "unavailable" in sources else ("recomputed" if "recomputed" in sources else "stored"),
                        "rows": search_rows},
        "assumptions": {**options, "what_if_multiplier": snapshot.get("what_if_multiplier")},
        "provenance": _provenance(analysis, scenario, dataset, snapshot),
    }


# ── Separate lines ──────────────────────────────────────────────────────────


def _lane_count(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _wait_hours(candidate: Mapping[str, Any] | None) -> float | None:
    waiting = ((candidate or {}).get("evidence") or {}).get("waiting_time") or {}
    return _finite(waiting.get("mean"))


def build_separate_plan_model(*, analysis: Mapping[str, Any], scenario: Mapping[str, Any], dataset: Mapping[str, Any],
                              setup: Mapping[str, Any], current_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    snapshot = (scenario.get("settings") or {}).get("calculation") or {}
    options = snapshot.get("options") or {}
    schedule = (scenario.get("results") or {}).get("schedule") or {}
    records = list(dataset.get("rows") or [])
    variance_of = {(str(row.get("time")), str(row.get("queue_id"))): row.get("variance") for row in records
                   if isinstance(row, Mapping)}
    periods, search_rows = [], []
    for period in schedule.get("periods") or []:
        candidates = [item for item in period.get("candidates") or [] if isinstance(item, Mapping)]
        now_count, plan_count = _lane_count(period.get("current_active_lanes")), _lane_count(period.get("optimal_active_lanes"))
        by_count = {item.get("active_lane_count"): item for item in candidates}
        now, plan = by_count.get(now_count), by_count.get(plan_count)
        periods.append({
            "time": period.get("time"), "counters_now": now_count, "counters_plan": plan_count,
            "busy_now": _finite((now or {}).get("candidate_utilization")), "busy_plan": _finite((plan or {}).get("candidate_utilization")),
            "wait_now_minutes": _minutes(_wait_hours(now)), "wait_plan_minutes": _minutes(_wait_hours(plan)),
            "cost_now": _finite((now or {}).get("total_cost")), "cost_plan": _finite((plan or {}).get("total_cost")),
            "model": "simulation (separate lines)",
        })
        for item in candidates:
            uncertainty = item.get("cost_uncertainty") or {}
            search_rows.append({
                "time": period.get("time"), "counters": item.get("active_lane_count"),
                "result": "chosen" if item.get("active_lane_count") == plan_count else str(item.get("status") or "").lower().replace("_", " "),
                "busy": _finite(item.get("candidate_utilization")), "wait_minutes": _minutes(_wait_hours(item)),
                "counter_cost": _finite(item.get("server_cost")), "waiting_cost": _finite(item.get("waiting_cost")),
                "total_cost": _finite(item.get("total_cost")),
                "total_cost_ci": [_finite(uncertainty.get("ci_lower")), _finite(uncertainty.get("ci_upper"))],
                "reason": item.get("reason"),
            })
    formula_rows = [formula_row(
        period=str(row.get("time")), staffing=f"Now, line {row.get('queue_id')}", model=str(row.get("model")),
        lam=row.get("lambda"), mu=row.get("mu"), c=row.get("c"),
        variance=variance_of.get((str(row.get("time")), str(row.get("queue_id")))),
        novaq_lq=row.get("Lq"), novaq_wq_hours=row.get("Wq")) for row in current_rows]
    cost_now = _sum_or_none([row["cost_now"] for row in periods])
    return {
        "report": "plan", "version": REPORT_VERSION, "line_type": "separate",
        "cover": _cover(analysis, "separate", str(scenario.get("name"))),
        "data": {"dataset_id": dataset.get("id"), "dataset_name": dataset.get("name"), "rows": records},
        "key_results": {
            "cost_now": cost_now, "cost_plan": _sum_or_none([row["cost_plan"] for row in periods]),
            "cost_basis": "Mean simulated counter cost plus waiting cost per period, added over the periods.",
            "cost_now_unavailable": None if cost_now is not None else
            "Today's simulated cost is missing for at least one period.",
            "highest_wait_now_minutes": _max_or_none([row["wait_now_minutes"] for row in periods]),
            "highest_wait_plan_minutes": _max_or_none([row["wait_plan_minutes"] for row in periods]),
            "counter_changes": _counter_changes(periods),
        },
        "periods": periods,
        "breaks": [dict(item) for item in setup.get("breaks") or []],
        "formula_check": formula_rows,
        "formula_check_note": "Separate-line plans are chosen by simulation; the formulas check today's lines (M/G/1 each).",
        "plan_search": {"method": "Simulation of every number of open lanes", "source": "stored", "rows": search_rows},
        "assumptions": {**options},
        "provenance": _provenance(analysis, scenario, dataset, snapshot),
    }


def _provenance(analysis: Mapping[str, Any], scenario: Mapping[str, Any], dataset: Mapping[str, Any],
                snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION, "analysis_id": analysis.get("id"), "scenario_id": scenario.get("id"),
        "scenario_generation": scenario.get("generation"), "dataset_id": dataset.get("id"),
        "dataset_generation": dataset.get("generation"), "engine_version": snapshot.get("engine_version"),
        "calculated_at": snapshot.get("calculated_at"),
    }


# ── Workbook ────────────────────────────────────────────────────────────────


def _table(sheet, title: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    sheet.append([title])
    sheet["A1"].font = Font(bold=True, size=13)
    sheet.append([])
    sheet.append(list(headers))
    for cell in sheet[3]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(list(row))


def workbook_sheets(model: Mapping[str, Any]) -> list[str]:
    """The workbook's sheets in order; the Reports page lists exactly these (and the workbook asserts them)."""
    full = ["Simulation", "Checks", "Decision"] if model.get("report") == "full" else []
    return ["Overview", "Your data", "Plan", "Formula check", "Plan search", *full, "Assumptions", "Provenance"]


def generate_plan_workbook(model: Mapping[str, Any]) -> io.BytesIO:
    """The plan report's "check the math" workbook, from the report model only."""
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    cover, key = model["cover"], model["key_results"]
    _table(overview, "Full report" if model.get("report") == "full" else "Plan report", ["Item", "Value"], [
        ["Report", cover.get("label")], ["Analysis", cover.get("analysis_name")], ["Lines", cover.get("line_type")],
        ["Plan", cover.get("plan_name")], ["Generated (UTC)", cover.get("generated_at")],
        ["Total cost now", key.get("cost_now") if key.get("cost_now") is not None else key.get("cost_now_unavailable")],
        ["Total cost with the plan", key.get("cost_plan")], ["Cost basis", key.get("cost_basis")],
        ["Highest wait now (min)", key.get("highest_wait_now_minutes")],
        ["Highest wait with the plan (min)", key.get("highest_wait_plan_minutes")],
    ])
    data_rows = model["data"]["rows"]
    columns = [key for key in ("time", "queue_id", "lambda", "mu", "c", "variance", "K", "theta")
               if any(isinstance(row, Mapping) and row.get(key) is not None for row in data_rows)]
    _table(workbook.create_sheet("Your data"), "Your data (the planning file)", columns,
           [[row.get(column) for column in columns] for row in data_rows if isinstance(row, Mapping)])
    _table(workbook.create_sheet("Plan"), "Now and with the plan, by period", [
        "Period", "Counters now", "Counters with the plan", "Busy share now", "Busy share with the plan",
        "Wait now (min)", "Wait with the plan (min)", "Cost now", "Cost with the plan", "Model"],
        [[row["time"], row["counters_now"], row["counters_plan"], row["busy_now"], row["busy_plan"],
          row["wait_now_minutes"], row["wait_plan_minutes"], row["cost_now"], row["cost_plan"], row["model"]]
         for row in model["periods"]])
    write_formula_sheet(workbook.create_sheet("Formula check"), model["formula_check"], title="Formula check")
    search = model["plan_search"]
    _table(workbook.create_sheet("Plan search"), f"Plan search: {search['method']} ({search['source']})", [
        "Period", "Counters", "Result", "Busy share", "Wait (min)", "Counter cost", "Waiting cost", "Total cost"],
        [[row["time"], row["counters"], row["result"], row["busy"], row["wait_minutes"], row["counter_cost"],
          row["waiting_cost"], row["total_cost"]] for row in search["rows"]])
    if model.get("report") == "full":
        simulation = model["simulation"]
        sheet = workbook.create_sheet("Simulation")
        _table(sheet, f"Simulation: {simulation['source']}", ["Result", "Value", "Unit"],
               [[item["label"], item["value"], item["unit"]] for item in simulation["headlines"]])
        for chart in simulation["charts"]:
            sheet.append([])
            sheet.append([chart["title"] + (f" (allowed {chart['limit']}%)" if chart.get("limit") is not None else "")])
            sheet.append(["Period", chart["unit"]])
            for point in chart["points"]:
                sheet.append([point["label"], point["value"]])
        _table(workbook.create_sheet("Checks"), "Checks", ["Check", "Settings", "Outcome"],
               [[item["check"], item["settings"], item["outcome"]] for item in model["checks"]])
        decision = model["decision"]
        _table(workbook.create_sheet("Decision"), "Decision", ["Item", "Text"],
               [["Status", decision.get("status")], ["Headline", decision.get("headline")],
                ["What to do", decision.get("recommendation")]]
               + [["Reason", line] for line in decision.get("rationale") or []]
               + [["Not included", line] for line in model.get("not_included") or [] if line])
    _table(workbook.create_sheet("Assumptions"), "Assumptions", ["Setting", "Value"],
           [[name, value if not isinstance(value, (dict, list)) else str(value)] for name, value in model["assumptions"].items()])
    _table(workbook.create_sheet("Provenance"), "Provenance", ["Item", "Value"],
           [[name, value] for name, value in model["provenance"].items()])
    assert workbook.sheetnames == workbook_sheets(model)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
