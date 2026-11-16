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
from textwrap import wrap
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

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
                              setup: Mapping[str, Any], current_rows: Sequence[Mapping[str, Any]],
                              baseline_setup: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``setup`` is the plan's effective Setup; ``baseline_setup`` the Analysis Setup (uploaded breaks)."""
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
    breaks_view = _separate_breaks_view(snapshot, scenario.get("results") or {}, setup,
                                        setup if baseline_setup is None else baseline_setup)
    return {
        "report": "plan", "version": REPORT_VERSION, "line_type": "separate",
        "cover": _cover(analysis, "separate", str(scenario.get("name"))),
        "data": {"dataset_id": dataset.get("id"), "dataset_name": dataset.get("name"), "rows": records},
        "key_results": {
            "cost_now": cost_now, "cost_plan": _sum_or_none([row["cost_plan"] for row in periods]),
            "cost_basis": ("Optimizer simulation estimates of counter cost plus waiting cost at current and suggested staffing, "
                           "added over the periods. There is no comparable Current cost basis; savings are unavailable."),
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
        **breaks_view,
    }


# ── Break check (owner-approved labels 2026-11-16, English only, verbatim) ──

BREAKS_SETUP_TITLE = "Breaks in the Setup"
BREAKS_PLAN_TITLE = "Plan break times"  # B17
BREAK_CHECK_TITLE = "Break times: uploaded vs plan"  # B1
BREAK_CHECK_SHEET = "Break check"  # B1-tab
BREAK_CHECK_INTRO = ("This section compares your uploaded break times with the plan's moved break times. Both sides use "
                     "the plan's simulation, where new customers go to an open line, with the same random runs. Counters "
                     "per hour do not change.")  # B2
BREAK_CHECK_WAIT_UPLOADED = "Wait, uploaded breaks (min)"  # B3
BREAK_CHECK_WAIT_MOVED = "Wait, moved breaks (min)"  # B4
BREAK_CHECK_CHART = "Average wait in line per period: uploaded vs moved breaks"  # B5 (owner round 2)
BREAK_CHECK_HOURLY_CAPTION = ("Period values are averages of the simulation runs and have no range. The 95% range is "
                              "shown for the whole day below.")  # B6 (owner round 2)
BREAK_CHECK_WAIT = "Simulated average wait (minutes)"  # B7
BREAK_CHECK_CHANGE = "Change in average wait (minutes, 95% range)"  # B8
BREAK_CHECK_VERDICTS = {  # B9
    "shorter": "The paired runs indicate shorter waits.",
    "no_clear_difference": "No clear change in wait. A lower peak load does not prove shorter waits.",
    "unavailable": "Wait comparison is unavailable.",
    "longer": "The paired runs indicate longer waits. These changes cannot be applied.",
}
BREAK_CHECK_PEAK = "Busiest 15-minute load"  # B10
BREAK_CHECK_PEAK_CAPTION = ("The busiest 15-minute load is a formula estimate from all lanes together, not the "
                            "simulation.")  # B10n
BREAK_CHECK_ALL_BREAKS = "Your breaks: uploaded vs plan"  # B11
BREAK_CHECK_COLUMNS = ["Cashier", "Break", "Current start", "New start", "Length (minutes)"]  # B12
BREAK_CHECK_MOVES = "Breaks the plan moved"  # B13
BREAK_CHECK_NO_MOVES = "This plan keeps your uploaded break times. No break was moved."  # B14
BREAK_CHECK_NOT_SAVED = ("The break check is not saved with this plan. Check the plan and save it again to see "
                         "it.")  # B15
BREAK_CHECK_KEY_NOTE = ('Both columns use the plan\'s break times. The effect of moving breaks is shown in "Break '
                        'times: uploaded vs plan".')  # B16


def _clock_text(value: Any) -> str:
    text = str(value or "")
    return text[:5] if len(text) == 8 and text.endswith(":00") else text


def _separate_breaks_view(snapshot: Mapping[str, Any], results: Mapping[str, Any], plan_setup: Mapping[str, Any],
                          baseline_setup: Mapping[str, Any]) -> dict[str, Any]:
    """The breaks table heading and the stored break check; reads saved evidence only, never recalculates.

    Plans without the break descriptor (pre-PR58, or saved without break changes) keep the original table.
    """
    plan_breaks = [item for item in plan_setup.get("breaks") or [] if isinstance(item, Mapping)]
    baseline_breaks = [item for item in baseline_setup.get("breaks") or [] if isinstance(item, Mapping)]
    descriptor = "break_optimization" in snapshot
    stored = results.get("break_check") if descriptor else None
    check = stored if isinstance(stored, Mapping) else None
    differs = len(plan_breaks) != len(baseline_breaks) or any(
        plan.get("scheduled_start_time") != base.get("scheduled_start_time")
        for plan, base in zip(plan_breaks, baseline_breaks))
    # K-BC-1 (owner 2026-11-17): B17 only when the plan's breaks differ from the uploaded Setup.
    view: dict[str, Any] = {"breaks_title": BREAKS_PLAN_TITLE if descriptor and differs else BREAKS_SETUP_TITLE, "breaks_note": None, "break_check": None,
                            "key_results_note": None}
    if not descriptor or not plan_breaks:
        return view
    if check is None:
        view["breaks_note"] = BREAK_CHECK_NOT_SAVED
        return view
    if not check.get("moves"):
        view["breaks_note"] = BREAK_CHECK_NO_MOVES
        return view
    view["break_check"] = _break_check_section(check)
    view["key_results_note"] = BREAK_CHECK_KEY_NOTE
    return view


def _break_check_section(check: Mapping[str, Any]) -> dict[str, Any]:
    des = check.get("des") or {}
    current, proposed = des.get("current") or {}, des.get("proposed") or {}
    moved_by_time = {str(row.get("time")): _finite(row.get("mean_wait_minutes")) for row in proposed.get("periods") or []}
    periods = [{"time": row.get("time"), "wait_uploaded_minutes": _finite(row.get("mean_wait_minutes")),
                "wait_moved_minutes": moved_by_time.get(str(row.get("time")))} for row in current.get("periods") or []]
    paired = (des.get("comparison") or {}).get("paired_wait_change") or {}
    verdict = str(paired.get("verdict")) if paired.get("verdict") in BREAK_CHECK_VERDICTS else "unavailable"
    runs = []
    for before, after in zip(current.get("replications") or [], proposed.get("replications") or []):
        low, high = _finite(before.get("mean_wait_minutes")), _finite(after.get("mean_wait_minutes"))
        runs.append({"seed": before.get("seed"), "wait_uploaded_minutes": low, "wait_moved_minutes": high,
                     "difference_minutes": None if low is None or high is None else high - low})
    peak = check.get("peak_rho") or {}
    all_breaks = [{"cashier": item.get("queue_id"), "break": item.get("label"),
                   "current_start": _clock_text(item.get("current_start_time")),
                   "new_start": _clock_text(item.get("scheduled_start_time")),
                   "length_minutes": item.get("duration_minutes"), "moved": bool(item.get("shift_minutes"))}
                  for item in check.get("proposed_breaks") or [] if isinstance(item, Mapping)]
    return {
        "periods": periods,
        "wait_uploaded_minutes": _finite((current.get("summary") or {}).get("mean_wait_minutes")),
        "wait_moved_minutes": _finite((proposed.get("summary") or {}).get("mean_wait_minutes")),
        "peak_uploaded": _finite(peak.get("before")), "peak_moved": _finite(peak.get("after")),
        "change": {"mean": _finite(paired.get("mean")), "ci_lower": _finite(paired.get("ci_lower")),
                   "ci_upper": _finite(paired.get("ci_upper")), "n": paired.get("n")},
        "verdict": verdict, "verdict_text": BREAK_CHECK_VERDICTS[verdict],
        "breaks": sorted(all_breaks, key=lambda item: not item["moved"]),
        "moves": [{"cashier": item.get("queue_id"), "break": item.get("label"), "current_start": item.get("from"),
                   "new_start": item.get("to"), "length_minutes": item.get("duration_minutes")}
                  for item in check.get("moves") or [] if isinstance(item, Mapping)],
        "runs": runs,
        "seeds": list(des.get("seeds") or []),
        "basis": check.get("basis"),
        "max_shift_minutes": check.get("max_shift_minutes"),
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
    check = [BREAK_CHECK_SHEET] if model.get("break_check") else []
    return ["Overview", "Your data", "Plan", *check, "Formula check", "Plan search", *full, "Assumptions", "Provenance"]


# Not in the owner-approved list (2026-11-16): column headings needed by the tables. Built from approved text where
# possible ("Random seed" is simulation.seed; the others reuse B3/B4/B8 wording); listed for owner review.
BREAK_CHECK_ITEM = "Item"
BREAK_CHECK_SIDE_UPLOADED = "Uploaded breaks"
BREAK_CHECK_SIDE_MOVED = "Moved breaks"
BREAK_CHECK_RUN_SEED = "Random seed"
BREAK_CHECK_RUN_CHANGE = "Change in average wait (minutes)"
NOT_RECORDED = "not recorded"
CANNOT_KEEP_UP = "cannot keep up"


def _recorded(value: Any) -> Any:
    return NOT_RECORDED if value is None else value


def _write_break_check_sheet(sheet: Worksheet, check: Mapping[str, Any]) -> None:
    """Values only: the stored break check, as in the PDF section, plus each paired run."""
    _table(sheet, BREAK_CHECK_TITLE, ["Period", BREAK_CHECK_WAIT_UPLOADED, BREAK_CHECK_WAIT_MOVED],
           [[row["time"], _recorded(row["wait_uploaded_minutes"]), _recorded(row["wait_moved_minutes"])]
            for row in check["periods"]])
    change = check["change"]
    blocks: list[tuple[list[Any], list[list[Any]]]] = [
        ([BREAK_CHECK_ITEM, BREAK_CHECK_SIDE_UPLOADED, BREAK_CHECK_SIDE_MOVED], [
            [BREAK_CHECK_WAIT, _recorded(check["wait_uploaded_minutes"]), _recorded(check["wait_moved_minutes"])],
            [BREAK_CHECK_PEAK, CANNOT_KEEP_UP if check["peak_uploaded"] is None else check["peak_uploaded"],
             CANNOT_KEEP_UP if check["peak_moved"] is None else check["peak_moved"]]]),
        ([BREAK_CHECK_ITEM, "Value", "95% low", "95% high", "Runs"], [
            [BREAK_CHECK_CHANGE, _recorded(change["mean"]), _recorded(change["ci_lower"]),
             _recorded(change["ci_upper"]), change["n"]]]),
        ([check["verdict_text"]], []),
        ([BREAK_CHECK_PEAK_CAPTION], []),
        ([BREAK_CHECK_ALL_BREAKS], []),
        (BREAK_CHECK_COLUMNS, [[row["cashier"], row["break"], row["current_start"], row["new_start"], row["length_minutes"]]
                               for row in check["breaks"]]),
        ([BREAK_CHECK_MOVES], []),
        (BREAK_CHECK_COLUMNS, [[row["cashier"], row["break"], row["current_start"], row["new_start"], row["length_minutes"]]
                               for row in check["moves"]]),
        ([BREAK_CHECK_RUN_SEED, BREAK_CHECK_WAIT_UPLOADED, BREAK_CHECK_WAIT_MOVED, BREAK_CHECK_RUN_CHANGE],
         [[run["seed"], _recorded(run["wait_uploaded_minutes"]), _recorded(run["wait_moved_minutes"]),
           _recorded(run["difference_minutes"])] for run in check["runs"]]),
    ]
    for headers, rows in blocks:
        if len(headers) > 1 or rows:
            sheet.append([])
        sheet.append(list(headers))
        for row in rows:
            sheet.append(list(row))


def _format_report_workbook(workbook: Workbook) -> None:
    """Presentation only: never write data or formulas, or move their cell references."""
    widths = {
        "Overview": [42, 100], "Plan": [28, 14, 18, 16, 16, 18, 18, 18, 18, 18],
        "Plan search": [28, 14, 50, 18, 18, 18, 18, 18], "Simulation": [65, 24, 18],
        "Checks": [25, 65, 75], "Decision": [25, 110], "Assumptions": [42, 100], "Provenance": [42, 100],
        BREAK_CHECK_SHEET: [44, 26, 26, 18, 18],
        "Formula check": [28, 20, 22, 22, 26, 14, 24, 22, 20, 22, 24, 22, 24, 26, 60, 3],
    }
    panes = {"Your data": "B4", "Plan": "D4", "Plan search": "C4", "Formula check": "D5"}
    navy, text, muted = "142C49", "172B45", "4B5D73"
    header_fill = PatternFill("solid", fgColor=navy)
    alternate_fill = PatternFill("solid", fgColor="F1F5FA")
    rule = Border(bottom=Side(style="thin", color="D4A72C"))

    for sheet in workbook:
        formula = sheet.title == "Formula check"
        header = 4 if formula else 3
        if sheet.title == "Your data":
            sizes = [28 if cell.value == "time" else 26 if cell.value == "queue_id" else 22
                     for cell in sheet[header]]
        else:
            sizes = list(widths[sheet.title])
        if sheet.title == "Plan" and workbook["Overview"]["B6"].value == "separate":
            sizes[3:] = [24] * 7
        sizes.extend([20] * max(0, sheet.max_column - len(sizes)))
        for column, size in enumerate(sizes, 1):
            sheet.column_dimensions[get_column_letter(column)].width = size
        sheet.sheet_view.showGridLines = False
        sheet.sheet_view.zoomScale = 100
        sheet.freeze_panes = panes.get(sheet.title)

        # Only otherwise empty title/note cells are merged; the data grid stays intact.
        _merge_report_heading(sheet, 1, 6 if formula else sheet.max_column)
        if formula:
            _merge_report_heading(sheet, 2, 8)
            _merge_report_heading(sheet, 3, 8)
        section_rows: set[int] = set()
        if sheet.title == "Simulation":
            for row in range(4, sheet.max_row + 1):
                if sheet.cell(row, 1).value is not None and all(sheet.cell(row, c).value is None for c in (2, 3)):
                    _merge_report_heading(sheet, row, 3)
                    section_rows.add(row)

        for row in sheet:
            for cell in row:
                if cell.value is None:
                    continue
                numeric = cell.data_type == "f" or isinstance(cell.value, (int, float))
                cell.font = Font(name="Arial", size=11, color=text)
                cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="right" if numeric else "left", indent=1)
                if cell.row == header:
                    cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
                    cell.fill = header_fill
                    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left", indent=1)
                elif cell.row > header and cell.row not in section_rows and cell.row % 2 == 0:
                    cell.fill = alternate_fill
                if cell.row >= header and ((sheet.title == "Plan" and cell.column in (2, 3, 10))
                                           or (sheet.title == "Plan search" and cell.column == 2)):
                    cell.alignment = Alignment(wrap_text=True, vertical="center" if cell.row == header else "top", horizontal="center")
        sheet["A1"].font = Font(name="Arial", size=16, bold=True, color=navy)
        sheet["A1"].border = rule
        if formula:
            for row in (2, 3):
                sheet.cell(row, 1).font = Font(name="Arial", size=10, color=muted)
        for row in section_rows:
            sheet.cell(row, 1).font = Font(name="Arial", size=11, bold=True, color=navy)

        _format_report_numbers(sheet)
        merged_widths = {(area.min_row, area.min_col): sum(sizes[area.min_col - 1:area.max_col])
                         for area in sheet.merged_cells.ranges}
        for row in sheet:
            lines = 1
            for cell in row:
                if not isinstance(cell.value, str) or cell.data_type == "f":
                    continue
                size = merged_widths.get((cell.row, cell.column), sizes[cell.column - 1])
                capacity = max(6, int(size * 0.85 * 11 / (cell.font.sz or 11)) - 5)
                lines = max(lines, sum(max(1, len(wrap(part, width=capacity))) for part in cell.value.split("\n")))
            minimum = 36 if row[0].row == 1 else 48 if row[0].row == header else 24
            if sheet.title == "Decision" and row[0].row == 6:
                minimum = 42
            sheet.row_dimensions[row[0].row].height = min(409, max(minimum, lines * 16 + 10))


def _merge_report_heading(sheet: Worksheet, row: int, last_column: int) -> None:
    if last_column > 1 and all(sheet.cell(row, column).value is None for column in range(2, last_column + 1)):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_column)


def _format_report_numbers(sheet: Worksheet) -> None:
    """Formats describe existing units; percent-valued chart points are not scaled again."""
    header = 4 if sheet.title == "Formula check" else 3
    for row in sheet.iter_rows(min_row=header + 1):
        for cell in row:
            if cell.data_type != "f" and not isinstance(cell.value, (int, float)):
                continue
            column = cell.column
            if sheet.title == "Formula check":
                if column == 14:
                    cell.number_format = "0.00E+00"
                elif column == 7:
                    cell.number_format = "0.000000E+00"
                elif column == 9:
                    cell.number_format = "0.0%"
                elif column in (8, 10, 11, 12, 13) or column >= 17:
                    cell.number_format = "0.00000000"
            elif sheet.title == "Plan":
                cell.number_format = ("0.0%" if column in (4, 5) else "0" if column in (2, 3)
                                      else "0.0000" if column in (6, 7) else "#,##0.00")
            elif sheet.title == "Plan search":
                cell.number_format = ("0.0%" if column == 4 else "0" if column == 2
                                      else "0.0000" if column == 5 else "#,##0.00")
            elif sheet.title == "Overview":
                cell.number_format = "0.0000" if cell.row in (12, 13) else "#,##0.00"
            elif sheet.title == "Assumptions":
                name = sheet.cell(cell.row, 1).value
                cell.number_format = "0.0%" if name == "target_utilization" else "0" if name == "max_servers" else "#,##0.00"
            elif sheet.title == "Simulation":
                cell.number_format = "0.0000" if sheet.cell(cell.row, 3).value == "minutes" else "#,##0.00"
            elif sheet.title == BREAK_CHECK_SHEET:
                label = sheet.cell(cell.row, 1).value
                cell.number_format = ("0.0%" if label == BREAK_CHECK_PEAK else "0" if isinstance(cell.value, int)
                                      else "0.0000")
    if sheet.title == "Simulation":
        percent = False
        for row in range(4, sheet.max_row + 1):
            unit = sheet.cell(row, 2).value
            if isinstance(unit, str) and unit in ("percent", "minutes"):
                percent = unit == "percent"
            elif percent and isinstance(unit, (int, float)):
                sheet.cell(row, 2).number_format = '0.0"%"'


def generate_plan_workbook(model: Mapping[str, Any]) -> io.BytesIO:
    """The plan report's "check the math" workbook, from the report model only."""
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    cover, key = model["cover"], model["key_results"]
    separate = model.get("line_type") == "separate"
    _table(overview, "Full report" if model.get("report") == "full" else "Plan report", ["Item", "Value"], [
        ["Report", cover.get("label")], ["Analysis", cover.get("analysis_name")], ["Lines", cover.get("line_type")],
        ["Plan", cover.get("plan_name")], ["Generated (UTC)", cover.get("generated_at")],
        ["Cost at current staffing (optimizer simulation)" if separate else "Total cost now",
         key.get("cost_now") if key.get("cost_now") is not None else key.get("cost_now_unavailable")],
        ["Total cost with the plan", key.get("cost_plan")], ["Cost basis", key.get("cost_basis")],
        ["Highest wait at current staffing (simulated, min)" if separate else "Highest wait now (min)", key.get("highest_wait_now_minutes")],
        ["Highest wait with the plan (min)", key.get("highest_wait_plan_minutes")],
    ])
    data_rows = model["data"]["rows"]
    columns = [key for key in ("time", "queue_id", "lambda", "mu", "c", "variance", "K", "theta")
               if any(isinstance(row, Mapping) and row.get(key) is not None for row in data_rows)]
    _table(workbook.create_sheet("Your data"), "Your data (the planning file)" if separate else "Saved calculation inputs", columns,
           [[row.get(column) for column in columns] for row in data_rows if isinstance(row, Mapping)])
    _table(workbook.create_sheet("Plan"), "Optimizer simulation at current and suggested staffing" if separate else "Now and with the plan, by period", [
        "Period", "Counters now", "Counters with the plan", "Busy at current staffing (simulated)" if separate else "Busy share now", "Busy share with the plan",
        "Wait at current staffing (simulated, min)" if separate else "Wait now (min)", "Wait with the plan (min)",
        "Cost at current staffing (simulated)" if separate else "Cost now", "Cost with the plan", "Model"],
        [[row["time"], row["counters_now"], row["counters_plan"], row["busy_now"], row["busy_plan"],
          row["wait_now_minutes"], row["wait_plan_minutes"], row["cost_now"], row["cost_plan"], row["model"]]
         for row in model["periods"]])
    if model.get("break_check"):
        _write_break_check_sheet(workbook.create_sheet(BREAK_CHECK_SHEET), model["break_check"])
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
        if decision.get("scope_notice"):
            workbook["Decision"].append(["Current scope note", decision["scope_notice"]])
    _table(workbook.create_sheet("Assumptions"), "Assumptions", ["Setting", "Value"],
           [[name, value if not isinstance(value, (dict, list)) else str(value)] for name, value in model["assumptions"].items()])
    _table(workbook.create_sheet("Provenance"), "Provenance", ["Item", "Value"],
           [[name, value] for name, value in model["provenance"].items()])
    assert workbook.sheetnames == workbook_sheets(model)
    _format_report_workbook(workbook)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
