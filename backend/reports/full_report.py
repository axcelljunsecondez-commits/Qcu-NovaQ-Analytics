"""B8 full report (level 2): the plan report plus the Decision, the simulation and the checks, in plain words.

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §1 (available when today's Decision gate allows
export). Everything here quotes persisted evidence: the Decision's own headline, recommendation, rationale and
facts, the simulation's stored summary, and each check's stored settings and statuses. No verdict is re-derived.

Shared lines: follow the current Decision's recorded full-day or period-by-period basis (OD-UX-13), without
mixing their evidence. Separate lines: the selected-plan chain (``reports._selected_report_chain``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from backend.reports.selected_scope import selected_scope_notice

FULL_LABEL = "Plan checked by simulation, with the Decision"
SHARED_SOURCE = "Period-by-period simulation: the evidence used by this Decision."
NOT_RECORDED = "not recorded by this run"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _percent(value: Any) -> str:
    number = _finite(value)
    return "not set" if number is None else f"{number * 100:g}%"


def _decision(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: result.get(key) for key in (
        "status", "headline", "recommendation", "rationale", "missing_evidence", "provenance_warning", "facts")}


def _headlines(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    wait = _finite(summary.get("average_wait_hours"))
    return [
        {"label": "Average wait in line", "value": None if wait is None else wait * 60, "unit": "minutes"},
        {"label": "Longest line", "value": summary.get("longest_line"), "unit": "people"},
        {"label": "Customers served", "value": summary.get("served"), "unit": "customers"},
        {"label": "Still in line or being served at closing", "value": summary.get("in_system_at_close"), "unit": "people"},
    ]


def _wait_chart(summary: Mapping[str, Any]) -> dict[str, Any]:
    points = []
    for period in summary.get("periods") or []:
        wait = _finite(period.get("average_wait_hours"))
        points.append({"label": str(period.get("time")), "value": None if wait is None else wait * 60})
    return {"title": "Simulated average wait in line, by period", "unit": "minutes", "points": points}


def _failure_chart(rows: Sequence[Mapping[str, Any]], cap: Any) -> dict[str, Any]:
    points = [{"label": str(row.get("time")) + ("" if row.get("queue_id") is None else f" · {row.get('queue_id')}"),
               "value": None if _finite(row.get("failure_rate")) is None else float(row["failure_rate"]) * 100}
              for row in rows]
    return {"title": "Share of variations that failed, by period", "unit": "percent",
            "limit": None if _finite(cap) is None else float(cap) * 100, "points": points}


def _within(rows: Sequence[Mapping[str, Any]]) -> str:
    passed = sum(1 for row in rows if str(row.get("status")).upper() == "PASS")
    return f"{passed} of {len(rows)} within the allowed failure share"


def _shared_full_day_sections(run: Mapping[str, Any], mc: Mapping[str, Any] | None,
                              decision: Mapping[str, Any], counter_breaks: bool) -> dict[str, Any]:
    """Read the saved run's aggregates and the Decision's verdicts; derive no new verdict or simulation."""
    result, params = run.get("result") or {}, run.get("params") or {}
    summary = result.get("summary") or {}
    customers = (summary.get("customers") or {}).get("per_replication") or {}
    metrics = summary.get("metrics") or {}
    waiting = (summary.get("waiting_time") or {}).get("customer_weighted_mean_hours") or {}
    wait = _finite(waiting.get("value"))
    headlines = [
        {"label": "Average wait of served customers (all repeated days)",
         "value": None if wait is None else wait * 60, "unit": "minutes"},
        {"label": "Longest line (average per day)",
         "value": _finite((metrics.get("max_queue_in_horizon") or {}).get("mean")), "unit": "people"},
        {"label": "Customers served (average per day)",
         "value": _finite((customers.get("served") or {}).get("mean")), "unit": "customers"},
        {"label": "Customers not served (average per day)",
         "value": _finite((customers.get("unserved") or {}).get("mean")), "unit": "customers"},
    ]
    labels = params.get("period_labels") or {}
    points = []
    for segment in (result.get("period_utilization") or {}).get("segments") or []:
        mean = _finite((segment.get("summary") or {}).get("mean"))
        points.append({"label": str(labels.get(segment.get("segment_id"), segment.get("segment_id"))),
                       "value": None if mean is None else mean * 100})
    mc_rows = ((mc or {}).get("result") or {}).get("results") or []
    mc_params = (mc or {}).get("params") or {}
    periods = (decision.get("facts") or {}).get("periods") or []
    outcome = "not recorded by this Decision"
    if periods:
        counts = {status: sum(p.get("verdict") == status for p in periods) for status in ("pass", "fail", "insufficient")}
        outcome = (f"{counts['pass']} passed, {counts['fail']} failed, {counts['insufficient']} without enough evidence "
                   f"of {len(periods)} recorded periods (as counted by the Decision)")
    recorded = lambda key: params.get(key) if params.get(key) is not None else "not recorded"
    checks = [
        {"check": "Simulation run", "outcome": "done",
         "settings": (f"Full-day run {run['id']}; {recorded('replications')} repeated days; seed {recorded('seed')}; "
                      f"closing rule {recorded('closing_policy')}; service model {recorded('service_model')}")},
        {"check": "Many variations", "outcome": _within(mc_rows) if mc else "not run",
         "settings": (f"{mc_params.get('num_trials', 'not recorded')} trials; a trial fails when counters are busier than "
                      f"{_percent(mc_params.get('failure_threshold'))}; allowed failure share {_percent(mc_params.get('failure_rate_cap'))}")},
        {"check": "Results check", "outcome": outcome,
         "settings": "Full-day busy shares against plan targets and Many variations; no period-by-period validation is used."},
    ]
    not_included = ["Period-by-period simulation and its validation are not used for this full-day Decision."]
    if counter_breaks:
        not_included.append("Suggested counters do not account for the counter breaks in the Setup.")
    return {
        "decision": _decision(decision),
        "simulation": {"source": "Full-day simulation: the saved repeated days used by this Decision.",
                       "basis": "full_day_run", "headlines": headlines,
                       "charts": [{"title": "Average busy share by period (across repeated days)", "unit": "percent", "points": points},
                                  _failure_chart(mc_rows, mc_params.get("failure_rate_cap"))]},
        "checks": checks,
        "not_included": not_included + [str(decision.get("provenance_warning") or "")],
    }


def shared_full_sections(*, des: Mapping[str, Any] | None, mc: Mapping[str, Any] | None,
                         validation: Mapping[str, Any] | None, decision: Mapping[str, Any],
                         counter_breaks: bool, full_day: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Full-report sections for one shared line from the current evidence (job views with params and result)."""
    if decision.get("basis") == "full_day_run":
        if full_day is None or full_day.get("id") != (decision.get("evidence_ids") or {}).get("continuous"):
            raise ValueError("A full-day Decision requires its matching saved run.")
        return _shared_full_day_sections(full_day, mc, decision, counter_breaks)
    summary = ((des or {}).get("result") or {}).get("summary") or {}
    mc_rows = ((mc or {}).get("result") or {}).get("results") or []
    mc_params, des_params = (mc or {}).get("params") or {}, (des or {}).get("params") or {}
    val_params = (validation or {}).get("params") or {}
    facts = decision.get("facts") or {}
    if facts.get("validation_intervals") is not None:
        validation_outcome = (f"{int(facts['validation_intervals']) - int(facts.get('failed_intervals') or 0)} of "
                              f"{facts['validation_intervals']} periods passed (as counted by the Decision)")
    else:
        validation_outcome = "not assessed by the Decision; missing: " + ", ".join(decision.get("missing_evidence") or [])
    checks = [
        {"check": "Simulation run", "settings": f"{des_params.get('sim_hours')} simulated hours per period, seed {des_params.get('seed')}",
         "outcome": "done" if des else "not run"},
        {"check": "Many variations", "outcome": _within(mc_rows) if mc else "not run",
         "settings": (f"{mc_params.get('num_trials')} trials; a trial fails when counters are busier than "
                      f"{_percent(mc_params.get('failure_threshold'))}; allowed failure share {_percent(mc_params.get('failure_rate_cap'))}")},
        {"check": "Results check", "outcome": validation_outcome if validation else "not run",
         "settings": (f"{val_params.get('des_sim_hours')} simulated hours, {val_params.get('mc_trials')} trials, "
                      f"allowed failure share {_percent(val_params.get('mc_failure_rate_cap'))}")},
    ]
    not_included = ["A full-day run is not used for this period-by-period Decision."]
    if counter_breaks:
        not_included.append("Suggested counters do not account for the counter breaks in the Setup.")
    return {
        "decision": _decision(decision),
        "simulation": {"source": SHARED_SOURCE, "headlines": _headlines(summary), "basis": summary.get("basis"),
                       "charts": [_wait_chart(summary), _failure_chart(mc_rows, mc_params.get("failure_rate_cap"))]},
        "checks": checks,
        "not_included": not_included + [str(decision.get("provenance_warning") or "")],
    }


def separate_full_sections(*, des: Mapping[str, Any], mc: Mapping[str, Any], validation: Mapping[str, Any],
                           decision: Mapping[str, Any]) -> dict[str, Any]:
    """Full-report sections for separate lines from the selected-plan chain (jobs as params and result)."""
    summary = (des.get("result") or {}).get("summary") or {}
    mc_rows = (mc.get("result") or {}).get("results") or []
    mc_params, des_params = mc.get("params") or {}, des.get("params") or {}
    verdict = (validation.get("result") or {}).get("verdict") or {}
    total = int(verdict.get("total") or 0)
    failed, inadequate = len(verdict.get("failed") or []), len(verdict.get("inadequate") or [])
    basis = "the whole day as one continuous run" if summary.get("basis") == "continuous_day" else "each period on its own"
    checks = [
        {"check": "Simulation run", "outcome": "done",
         "settings": f"Selected-plan simulation of {basis}, seed {des_params.get('seed')}, {des_params.get('load_replications')} paired load runs"},
        {"check": "Many variations", "outcome": _within(mc_rows),
         "settings": (f"{mc_params.get('num_trials')} trials; a trial fails when a line is busier than "
                      f"{_percent(mc_params.get('failure_threshold'))}; allowed failure share {_percent(mc_params.get('failure_rate_cap'))}")},
        {"check": "Results check", "settings": f"allowed failure share {_percent((validation.get('params') or {}).get('failure_rate_cap'))}",
         "outcome": f"{verdict.get('status')}: {total - failed - inadequate} of {total} line-periods passed, {failed} failed, {inadequate} without enough data"},
    ]
    return {
        "decision": {**_decision(decision), "scope_notice": selected_scope_notice(decision)},
        "simulation": {"source": f"Selected-plan simulation of {basis}.", "headlines": _headlines(summary),
                       "basis": summary.get("basis"),
                       "charts": [_wait_chart(summary), _failure_chart(mc_rows, mc_params.get("failure_rate_cap"))]},
        "checks": checks,
        "not_included": [str(decision.get("provenance_warning") or "")],
    }


def full_model(plan_model: Mapping[str, Any], sections: Mapping[str, Any]) -> dict[str, Any]:
    """The full report: the plan report's model with the level-2 sections."""
    cover = {**plan_model["cover"], "label": FULL_LABEL, "level": "full"}
    return {**plan_model, "report": "full", "cover": cover, **sections}
