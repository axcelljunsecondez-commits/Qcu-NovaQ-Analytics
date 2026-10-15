"""B8 full report (level 2): the plan report plus the Decision, the simulation and the checks, in plain words.

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §1 (available when today's Decision gate allows
export). Everything here quotes persisted evidence: the Decision's own headline, recommendation, rationale and
facts, the simulation's stored summary, and each check's stored settings and statuses. No verdict is re-derived.

Shared lines: the Decision is made from the period-by-period run (``workflow._derive_decision``), so that run is
the simulation shown; the full-day run is a preview without a pass or fail rule (OD-UX-13) and is listed under
"What is not included". Separate lines: the selected-plan chain (``reports._selected_report_chain``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

FULL_LABEL = "Plan checked by simulation, with the Decision"
SHARED_SOURCE = ("Period-by-period simulation: the evidence the Decision uses. The full-day run is a preview and "
                 "is not part of the Decision.")
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


def shared_full_sections(*, des: Mapping[str, Any] | None, mc: Mapping[str, Any] | None,
                         validation: Mapping[str, Any] | None, decision: Mapping[str, Any],
                         counter_breaks: bool) -> dict[str, Any]:
    """Full-report sections for one shared line from the current evidence (job views with params and result)."""
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
    not_included = ["The full-day run of the shared line is a preview: no pass or fail rule exists for it yet, so it "
                    "is not part of the Decision."]
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
        "decision": _decision(decision),
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
