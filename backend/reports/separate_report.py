"""Normalized Separate-Queue full-report model from persisted evidence.

Pure read-only normalization: analysis, dataset, scenario, schedule,
selected-plan DES/MC/validation/decision evidence, and Current baseline go
in; one plain-JSON model comes out. The same model feeds preview, PDF, and
Excel so the three surfaces cannot drift. Nothing here runs engines,
recalculates optima, or fabricates savings, ROI, or ADOPT.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_or_none(value: Any) -> float | None:
    if not _is_number(value):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def build_separate_report_model(chain: dict[str, Any]) -> dict[str, Any]:
    """Normalize one complete selected-plan evidence chain into a report model.

    All inputs are persisted evidence dicts; missing optional evidence
    renders as explicit N/A states, never zeros. Stored time values are
    hours; display layers convert to minutes.
    """
    analysis = chain.get("analysis") or {}
    dataset = chain.get("dataset") or {}
    scenario = chain.get("scenario") or {}
    schedule = chain.get("schedule") or {}
    current = chain.get("current") or {}
    des = chain.get("des") or {}
    mc = chain.get("mc") or {}
    validation = chain.get("validation") or {}
    decision = chain.get("decision") or {}
    comparison_plans = chain.get("comparison_plans") or []

    sched_periods: list[dict[str, Any]] = []
    selected_parts: dict[str, list[float]] = {"staffing": [], "waiting": [], "total": []}
    for period in schedule.get("periods") or []:
        if not isinstance(period, dict):
            continue
        optimum = period.get("optimum") or {}
        sched_periods.append({
            "time": period.get("time"),
            "current_active_lanes": list(period.get("current_active_lanes") or []),
            "current_count": len(period.get("current_active_lanes") or []),
            "optimal_active_lanes": optimum.get("active_lane_count")
            if _is_number(optimum.get("active_lane_count")) else period.get("optimal_active_lanes"),
            "adjustment": period.get("adjustment"),
            "peak_utilization": _finite_or_none(optimum.get("candidate_utilization")),
            "total_cost": _finite_or_none(optimum.get("total_cost")),
            "optimum": {
                "active_queue_ids": list(optimum.get("active_queue_ids") or []),
                "inactive_queue_ids": list(optimum.get("inactive_queue_ids") or []),
                "active_lane_count": optimum.get("active_lane_count"),
                "candidate_utilization": _finite_or_none(optimum.get("candidate_utilization")),
                "total_cost": _finite_or_none(optimum.get("total_cost")),
                "server_cost": _finite_or_none(optimum.get("server_cost")),
                "waiting_cost": _finite_or_none(optimum.get("waiting_cost")),
                "recommendation": optimum.get("recommendation"),
                "estimated_optimal": optimum.get("estimated_optimal"),
            },
        })
        for key, opt_key in (("staffing", "server_cost"), ("waiting", "waiting_cost"),
                             ("total", "total_cost")):
            value = _finite_or_none(optimum.get(opt_key))
            if value is not None:
                selected_parts[key].append(value)

    current_periods: list[dict[str, Any]] = []
    for period in current.get("periods") or []:
        if not isinstance(period, dict):
            continue
        queues = []
        for queue in period.get("queues") or []:
            if not isinstance(queue, dict):
                continue
            queues.append({
                "queue_id": queue.get("queue_id"),
                "lambda": _finite_or_none(queue.get("lambda")),
                "mu": _finite_or_none(queue.get("mu")),
                "rho": _finite_or_none(queue.get("rho")),
                "Wq": _finite_or_none(queue.get("Wq")),
                "model": queue.get("model"),
                "stable": queue.get("stable"),
            })
        current_periods.append({"time": period.get("time"), "queues": queues})
    kpis = current.get("kpis") or {}

    des_periods: list[dict[str, Any]] = []
    for period in des.get("periods") or []:
        if not isinstance(period, dict):
            continue
        lanes = []
        for lane in period.get("lanes") or []:
            if not isinstance(lane, dict):
                continue
            lanes.append({
                "queue_id": lane.get("queue_id"),
                "arrivals": lane.get("arrivals") if _is_number(lane.get("arrivals")) else None,
                "served": lane.get("served") if _is_number(lane.get("served")) else None,
                "waiting": lane.get("waiting") if _is_number(lane.get("waiting")) else None,
                "Wq": _finite_or_none(lane.get("Wq")),
                "rho": _finite_or_none(lane.get("rho")),
                "max_queue": lane.get("max_queue") if _is_number(lane.get("max_queue")) else None,
                "active": lane.get("active"),
            })
        trace = period.get("trace") or {}
        des_periods.append({
            "time": period.get("time"),
            "active_queue_ids": list(period.get("active_queue_ids") or []),
            "conservation": period.get("conservation"),
            "lanes": lanes,
            "trace": {
                "event_count": trace.get("event_count")
                if _is_number(trace.get("event_count")) else None,
                "truncated": trace.get("truncated"),
                "queue_ids": list(trace.get("queue_ids") or []),
            },
        })

    mc_lanes: list[dict[str, Any]] = []
    for lane in mc.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        mc_lanes.append({
            "time": lane.get("time"),
            "queue_id": lane.get("queue_id"),
            "lambda": _finite_or_none(lane.get("lambda")),
            "failure_rate": _finite_or_none(lane.get("failure_rate")),
            "failure_rate_ci": lane.get("failure_rate_ci"),
            "adequate": lane.get("adequate"),
            "status": lane.get("status"),
        })

    validation_periods: list[dict[str, Any]] = []
    for period in validation.get("periods") or []:
        if not isinstance(period, dict):
            continue
        queues = []
        for queue in period.get("queues") or []:
            if not isinstance(queue, dict):
                continue
            queues.append({
                "queue_id": queue.get("queue_id"),
                "rho_sim": _finite_or_none(queue.get("rho_sim")),
                "Wq_sim": _finite_or_none(queue.get("Wq_sim")),
                "served": queue.get("served") if _is_number(queue.get("served")) else None,
                "mc_failure_rate": _finite_or_none(queue.get("mc_failure_rate")),
                "validation_verdict": queue.get("validation_verdict"),
            })
        validation_periods.append({
            "time": period.get("time"),
            "active_queue_ids": list(period.get("active_queue_ids") or []),
            "status": period.get("status"),
            "queues": queues,
        })

    decision_status = decision.get("status")
    staffing_title = (
        "Selected Plan Requiring Revision"
        if decision_status == "revise"
        else "Selected Staffing Schedule"
    )
    truncated_any = any(p["trace"].get("truncated") is True for p in des_periods)

    # The optimizer marks a schedule whose candidates came from one continuous
    # operating day per replication (representative-day basis, finding K).
    continuous_day = schedule.get("utilization_basis") == "continuous-day DES"
    operating_day_hours = _finite_or_none(analysis.get("operating_day_hours"))
    if continuous_day:
        execution_limitation = (
            "Each optimization replication simulated the whole operating day as one continuous "
            "run; queues and breaks carried across period boundaries, and each period's "
            "utilization, waits and waiting cost come from that period's part of the day.")
    else:
        execution_limitation = (
            "Each optimized period was simulated independently from an empty initial state "
            "(period-independent execution); customer carryover between periods was not modeled.")
    limitations = [
        execution_limitation,
        "Optimized routing DES requires empirical service samples for every active lane.",
        "Replication count is a configurable product setting, not a statistical guarantee.",
        "Simulation estimates contain stochastic uncertainty; cost intervals are supporting evidence only.",
        "Current total modeled cost is not comparable to selected optimized total cost; "
        "savings and ROI are not computed.",
        "ADOPT is therefore unavailable under current Decision economics.",
        "Abandonment is not modeled in selected DES.",
    ]
    if truncated_any:
        limitations.append(
            "Visual trace may be truncated by the event cap while summary metrics "
            "represent the full simulation run."
        )

    des_cfg = schedule.get("des") or {}
    n_sched = len(sched_periods)

    def _complete_sum(key: str) -> float | None:
        parts = selected_parts[key]
        return sum(parts) if parts and len(parts) == n_sched and n_sched > 0 else None
    return {
        "overview": {
            "analysis_id": analysis.get("id"),
            "analysis_name": analysis.get("name"),
            "queue_structure": analysis.get("queue_structure"),
            "dataset_id": dataset.get("id"),
            "dataset_name": dataset.get("name"),
            "scenario_id": scenario.get("id"),
            "scenario_name": scenario.get("name"),
            "target": _finite_or_none(scenario.get("target")),
            "decision": decision.get("status"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "dataset": {
            "row_count": dataset.get("row_count") if _is_number(dataset.get("row_count")) else None,
            "periods": list(dataset.get("periods") or []),
            "queue_ids": list(analysis.get("queue_ids") or []),
            "queue_count": len(analysis.get("queue_ids") or []),
            "source_format": dataset.get("source_format"),
            "validation_ok": dataset.get("validation_ok"),
        },
        "queue_config": {
            "model": "one queue_id = one physical queue + one physical single server",
            "queue_ids": list(analysis.get("queue_ids") or []),
            "closure_policy": analysis.get("closure_policy"),
        },
        "current": {
            "periods": current_periods,
            "wait_mean": _finite_or_none(kpis.get("avg_waiting_time")),
            "wait_basis": "lambda-weighted analytical mean over Current rows",
            "peak_utilization": _finite_or_none(kpis.get("max_utilization")),
            "waiting_cost": _finite_or_none(kpis.get("total_waiting_cost")),
            "waiting_cost_basis": "Lq-based Current basis; excludes server cost",
            "models": list(current.get("models") or []),
        },
        "optimization": {
            "queue_structure": "separate_queues",
            "target": _finite_or_none(schedule.get("target_utilization")),
            "evaluation_method": schedule.get("evaluation_method"),
            "replications": des_cfg.get("replications"),
            "base_seed": des_cfg.get("base_seed"),
            "duration_hours": (operating_day_hours if continuous_day
                               else _finite_or_none(des_cfg.get("duration_hours"))),
            "routing_policy": "Arrivals were routed to the active queue with the smallest "
                              "live system size (waiting + in service), with seeded fair "
                              "handling of ties.",
            "arrival_method": "single conserved Poisson stream at total lambda",
            "service_sampling": "empirical per-lane resampling",
            "execution": ("continuous operating day per replication; queues and breaks "
                          "carry across periods" if continuous_day
                          else "period-independent; no cross-period carryover"),
        },
        "comparison_plans": [
            {"scenario_id": p.get("scenario_id"), "name": p.get("name"),
             "target": _finite_or_none(p.get("target")), "overall": p.get("overall")}
            for p in comparison_plans if isinstance(p, dict)
        ],
        "selected": {
            "scenario_id": scenario.get("id"),
            "name": scenario.get("name"),
            "target": _finite_or_none(scenario.get("target")),
            "engine_version": scenario.get("engine_version"),
            "calculated_at": scenario.get("calculated_at"),
            "dataset_id": scenario.get("dataset_id"),
        },
        "schedule": {"periods": sched_periods},
        "des": {
            "job_id": des.get("job_id"),
            "seed": des.get("seed"),
            "duration_hours": _finite_or_none(des.get("duration_hours")),
            "overall_conservation": des.get("overall_conservation"),
            "overall_status": des.get("overall_status"),
            "periods": des_periods,
        },
        "playback": {
            "note": "Visualization of the selected DES trace; not a separate analytical result.",
            "periods": [
                {"time": p["time"], "event_count": p["trace"].get("event_count"),
                 "truncated": p["trace"].get("truncated"),
                 "queue_ids": p["trace"].get("queue_ids")}
                for p in des_periods
            ],
        },
        "mc": {
            "job_id": mc.get("job_id"),
            "num_trials": mc.get("num_trials") if _is_number(mc.get("num_trials")) else None,
            "failure_threshold": _finite_or_none(mc.get("failure_threshold")),
            "failure_rate_cap": _finite_or_none(mc.get("failure_rate_cap")),
            "method": mc.get("method"),
            "demand_basis": "active-lane demand for downstream MC was based on "
                            "DES-measured routed throughput",
            "lanes": mc_lanes,
        },
        "validation": {
            "job_id": validation.get("job_id"),
            "verdict": validation.get("verdict"),
            "periods": validation_periods,
        },
        "decision": {
            "job_id": decision.get("job_id"),
            "status": decision_status,
            "headline": decision.get("headline"),
            "recommendation": decision.get("recommendation"),
            "rationale": list(decision.get("rationale") or []),
            "facts": decision.get("facts") or {},
            "failed_periods": list(decision.get("failed_periods") or []),
        },
        "staffing_title": staffing_title,
        "cost": {
            "current_waiting": _finite_or_none(kpis.get("total_waiting_cost")),
            "current_waiting_basis": "Lq-based Current basis; excludes server cost",
            "selected_staffing": _complete_sum("staffing"),
            "selected_waiting": _complete_sum("waiting"),
            "selected_total": _complete_sum("total"),
            "uncertainty_note": "Selected cost uncertainty is retained per period in the "
                                "optimization evidence and DES results above.",
            "current_total": None,
            "current_total_reason": "Current evidence has no server-cost basis; "
                                    "savings are not computed.",
            "savings": None,
            "savings_reason": "Current and optimized costs use incompatible modeled bases.",
            "roi": None,
            "roi_reason": "No valid investment basis is defined.",
        },
        "limitations": limitations,
        "provenance": {
            "analysis_id": analysis.get("id"),
            "dataset_id": dataset.get("id"),
            "scenario_id": scenario.get("id"),
            "des_job_id": des.get("job_id"),
            "mc_job_id": mc.get("job_id"),
            "validation_job_id": validation.get("job_id"),
            "decision_job_id": decision.get("job_id"),
            "optimization_engine": scenario.get("engine_version"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
