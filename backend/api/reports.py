"""Reports endpoints: PDF/Excel generation from datasets and scenarios."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, user_rate_limit
from backend.api.workflow import (
    SelectedPlanError,
    _latest_job,
    _require_selected_separate_plan,
    _require_setup_current,
    current_decision_for_report,
)
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.break_optimization import slot_inputs_from_setup, slot_rho
from backend.queueing_engine.services.data_processing import compute_kpis, process_segments
from backend.queueing_engine.services.model_explanations import analyze_segments
from backend.queueing_engine.services.optimization import (
    build_recommendations,
    summarize_optimization,
    unstable_current_reason,
)
from backend.reports.report_export import current_only_blocked_lines, generate_excel_report, generate_pdf_report
from backend.reports.separate_report import build_separate_report_model

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(user_rate_limit("report"))],
)

BASIS_ROI_REASON = (
    "ROI can't be declared: the current cost is calculated with the queueing formula and the "
    "plan's cost with simulation, so the two can't be subtracted."
)


def _clock(minutes: float) -> str:
    total = int(round(minutes))
    return f"{total // 60:02d}:{total % 60:02d}"


def _overloaded(row: dict) -> bool | None:
    """rho >= 1, or demand with nobody working; None when rho can't be judged."""
    rho = row.get("rho")
    if rho is not None:
        return rho >= 1
    if row.get("lambda", 0) > 0 and row.get("working", 1) <= 1e-9:
        return True
    return None


def overload_ranges(rows: list[dict]) -> list[tuple[str, str]] | None:
    """Merged overloaded slot ranges as (start, end) clocks; None if any slot is uncomputable."""
    ranges: list[list[float]] = []
    for row in sorted(rows, key=lambda item: item["start"]):
        flag = _overloaded(row)
        if flag is None:
            return None
        if not flag:
            continue
        if ranges and abs(ranges[-1][1] - row["start"]) < 1e-9:
            ranges[-1][1] = row["end"]
        else:
            ranges.append([row["start"], row["end"]])
    return [(_clock(low), _clock(high)) for low, high in ranges]


def separate_roi_reason(setup: dict, records: list | None) -> str:
    """Why a separate-queue report shows no savings/ROI: incompatible cost bases.

    Current cost is analytical per lane and the plan's cost is DES, so this holds
    whatever the break schedule; the slot overload screen is reported separately.
    """
    return BASIS_ROI_REASON


def separate_break_overload_note(setup: dict, records: list | None) -> str | None:
    """Pooled 15-minute slot screen of the current break schedule; None unless overloaded."""
    try:
        slots, shifts = slot_inputs_from_setup(setup, list(records or []))
        rows = slot_rho(slots, shifts, list((setup or {}).get("breaks") or []))
    except (ValueError, TypeError, KeyError):
        return None
    ranges = overload_ranges(rows)
    if not ranges:
        return None
    finite = [row["rho"] for row in rows if row.get("rho") is not None]
    peak = "∞" if any(row.get("rho") is None and (row.get("lambda") or 0) > 0 for row in rows)         else f"{max(finite):.2f}"
    spans = ", ".join(f"from {low} to {high}" for low, high in ranges)
    return (f"Note: {spans} the cashiers on duty during breaks cannot keep up with demand "
            f"(pooled 15-minute ρ = {peak}); the break optimizer addresses this.")


PDF_MEDIA_TYPE = "application/pdf"
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _own_dataset(db: Session, user: User, dataset_id: int, analysis_id: int | None = None) -> Dataset:
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id or (analysis_id is not None and dataset.analysis_id != analysis_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def _own_scenario(db: Session, user: User, scenario_id: int, analysis_id: int | None = None) -> Scenario:
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id or (analysis_id is not None and scenario.analysis_id != analysis_id):
        raise HTTPException(status_code=404, detail="Scenario not found.")
    if scenario.dataset_id is not None:
        dataset = db.get(Dataset, scenario.dataset_id)
        if (
            dataset is None
            or dataset.user_id != user.id
            or dataset.analysis_id != scenario.analysis_id
        ):
            raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def _selected_report_chain(db: Session, user: User, analysis: AnalysisProject) -> dict:
    """Resolve the exact selected evidence chain for final reporting.

    Selection, scenario, DES, MC, validation, and decision must all belong
    to one scenario with intact job linkage; anything else blocks with an
    exact reason instead of a partial "complete" report.
    """
    try:
        plan = _require_selected_separate_plan(db, user, analysis)
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = plan["scenario"]
    des_job = _latest_job(db, user, "workflow_des", analysis.id, scenario.id)
    if des_job is None or (des_job.params_json or {}).get("engine") != "selected-plan-routing-des":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan DES before generating the final report.",
        )
    mc_job = _latest_job(db, user, "workflow_mc", analysis.id, scenario.id)
    if mc_job is None or (mc_job.params_json or {}).get("engine") != "selected-plan-measured-mc":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Monte Carlo before generating the final report.",
        )
    if (mc_job.params_json or {}).get("des_job_id") != des_job.id:
        raise HTTPException(
            status_code=409,
            detail="Monte Carlo evidence is stale for the latest selected-plan DES.",
        )
    validation_job = _latest_job(db, user, "workflow_validation", analysis.id, scenario.id)
    if validation_job is None:
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Validation before generating the final report.",
        )
    validation_params = validation_job.params_json or {}
    if (validation_params.get("des_job_id") != des_job.id
            or validation_params.get("mc_job_id") != mc_job.id):
        raise HTTPException(
            status_code=409,
            detail="Validation evidence is stale for the latest Simulation evidence.",
        )
    decision_job = _latest_job(db, user, "workflow_decision", analysis.id, scenario.id)
    if decision_job is None:
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Decision before generating the final report.",
        )
    decision_params = decision_job.params_json or {}
    if (decision_params.get("validation_job_id") != validation_job.id
            or decision_params.get("des_job_id") != des_job.id
            or decision_params.get("mc_job_id") != mc_job.id):
        raise HTTPException(
            status_code=409,
            detail="Decision evidence is stale for the latest Validation evidence.",
        )
    _require_setup_current(analysis, des_job, mc_job, validation_job, decision_job)
    for label, job in (("DES", des_job), ("Monte Carlo", mc_job),
                       ("Validation", validation_job), ("Decision", decision_job)):
        result = job.result_json or {}
        if result.get("scenario_id") != scenario.id:
            raise HTTPException(
                status_code=409,
                detail=f"{label} evidence belongs to a different scenario.",
            )
    decision_result = decision_job.result_json or {}
    if decision_result.get("scenario_id") != scenario.id:
        raise HTTPException(
            status_code=409,
            detail="Decision evidence belongs to a different scenario.",
        )
    return {
        "plan": plan,
        "scenario": scenario,
        "des_job": des_job,
        "mc_job": mc_job,
        "validation_job": validation_job,
        "decision_job": decision_job,
    }


def _selected_report_model(db: Session, user: User, analysis: AnalysisProject) -> dict:
    """Assemble persisted evidence into the normalized Separate report model."""
    chain = _selected_report_chain(db, user, analysis)
    plan = chain["plan"]
    scenario = chain["scenario"]
    setup = plan["setup"]
    dataset = plan["dataset"]
    records = dataset.normalized_json or []
    frame, _, _ = analyze_segments(records, setup, dataset.validation_report_json or {})
    rows = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    grouped: dict[str, list] = {}
    order: list[str] = []
    for row in rows:
        label = str(row.get("time", "Unknown"))
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(row)
    current_periods = []
    for label in order:
        queues = []
        for row in grouped[label]:
            if not isinstance(row.get("queue_id"), str):
                continue
            queues.append({
                "queue_id": row.get("queue_id"),
                "lambda": row.get("lambda"),
                "mu": row.get("mu"),
                "rho": row.get("rho"),
                "Wq": row.get("Wq"),
                "model": row.get("model"),
                "stable": row.get("stable"),
            })
        current_periods.append({"time": label, "queues": queues})
    kpis = compute_kpis(frame)
    models = sorted({str(row.get("model")) for row in rows if row.get("model")})
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    options = snapshot.get("options") or {}
    des_result = chain["des_job"].result_json or {}
    mc_result = chain["mc_job"].result_json or {}
    mc_params = chain["mc_job"].params_json or {}
    validation_result = chain["validation_job"].result_json or {}
    decision_result = chain["decision_job"].result_json or {}
    schedule = (scenario.results_json or {}).get("schedule") or {}
    sibling_plans = []
    for item in db.execute(
        select(Scenario).where(
            Scenario.user_id == user.id, Scenario.analysis_id == analysis.id)
    ).scalars():
        calc = (item.settings_json or {}).get("calculation") or {}
        if calc.get("schema_version") != 2:
            continue
        item_schedule = (item.results_json or {}).get("schedule") or {}
        sibling_plans.append({
            "scenario_id": item.id,
            "name": item.name,
            "target": ((calc.get("options") or {}).get("target_utilization")),
            "overall": item_schedule.get("overall"),
        })
    sibling_plans.sort(key=lambda item: item["scenario_id"] or 0)
    mc_lanes = []
    for row in mc_result.get("results") or []:
        if not isinstance(row, dict):
            continue
        mc_lanes.append({
            "time": row.get("time"),
            "queue_id": row.get("queue_id"),
            "lambda": row.get("lambda"),
            "failure_rate": row.get("failure_rate"),
            "failure_rate_ci": [row.get("failure_rate_ci_lower"),
                                row.get("failure_rate_ci_upper")],
            "adequate": row.get("failure_rate_adequate"),
            "status": row.get("status"),
        })
    model = build_separate_report_model({
        "analysis": {
            "id": analysis.id,
            "name": analysis.name,
            "queue_structure": setup.get("queue_structure"),
            "queue_ids": [str(q) for q in setup.get("queue_ids", [])],
            "closure_policy": setup.get("separate_queue_closure_policy"),
        },
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "row_count": len(records),
            "periods": order,
            "source_format": dataset.source_format,
            "validation_ok": bool((dataset.validation_report_json or {}).get("ok")),
        },
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "target": options.get("target_utilization"),
            "engine_version": snapshot.get("engine_version"),
            "calculated_at": snapshot.get("calculated_at"),
            "dataset_id": dataset.id,
        },
        "schedule": schedule,
        "current": {
            "periods": current_periods,
            "kpis": {
                "avg_waiting_time": kpis.get("avg_waiting_time"),
                "max_utilization": kpis.get("max_utilization"),
                "total_waiting_cost": kpis.get("total_waiting_cost"),
            },
            "models": models,
        },
        "des": {
            "job_id": chain["des_job"].id,
            "seed": (des_result.get("seed")),
            "duration_hours": des_result.get("duration_hours"),
            "overall_conservation": des_result.get("overall_conservation"),
            "overall_status": des_result.get("overall_status"),
            "arrival_method": des_result.get("arrival_method"),
            "routing_policy": des_result.get("routing_policy"),
            "service_sampling_method": des_result.get("service_sampling_method"),
            "execution": des_result.get("execution"),
            "periods": [
                {
                    "time": p.get("time"),
                    "active_queue_ids": p.get("active_queue_ids"),
                    "conservation": p.get("conservation"),
                    "lanes": [
                        {"queue_id": lane.get("queue_id"),
                         "arrivals": lane.get("arrivals"),
                         "served": lane.get("served"),
                         "waiting": lane.get("waiting"),
                         "Wq": lane.get("Wq_sim"),
                         "rho": lane.get("rho_sim"),
                         "max_queue": lane.get("max_queue"),
                         "active": lane.get("active")}
                        for lane in (p.get("results") or []) if isinstance(lane, dict)
                    ],
                    "trace": {
                        "event_count": (p.get("trace") or {}).get("event_count"),
                        "truncated": (p.get("trace") or {}).get("truncated"),
                        "queue_ids": sorted({
                            str(lane.get("queue_id"))
                            for lane in (p.get("results") or [])
                            if isinstance(lane, dict) and lane.get("queue_id")}),
                    },
                }
                for p in (des_result.get("periods") or []) if isinstance(p, dict)
            ],
        },
        "mc": {
            "job_id": chain["mc_job"].id,
            "num_trials": mc_params.get("num_trials"),
            "failure_threshold": mc_params.get("failure_threshold"),
            "failure_rate_cap": mc_params.get("failure_rate_cap"),
            "method": mc_result.get("method"),
            "lanes": mc_lanes,
        },
        "validation": {
            "job_id": chain["validation_job"].id,
            "verdict": (validation_result.get("verdict") or {}).get("status"),
            "periods": [
                {
                    "time": p.get("time"),
                    "active_queue_ids": p.get("active_queue_ids"),
                    "status": p.get("status"),
                    "queues": [
                        {"queue_id": q.get("queue_id"),
                         "rho_sim": q.get("rho_sim"),
                         "Wq_sim": q.get("Wq_sim"),
                         "served": q.get("served"),
                         "mc_failure_rate": q.get("mc_failure_rate"),
                         "validation_verdict": q.get("validation_verdict")}
                        for q in (p.get("queues") or []) if isinstance(q, dict)
                    ],
                }
                for p in (validation_result.get("periods") or []) if isinstance(p, dict)
            ],
        },
        "decision": {
            "job_id": chain["decision_job"].id,
            "status": decision_result.get("status"),
            "headline": decision_result.get("headline"),
            "recommendation": decision_result.get("recommendation"),
            "rationale": decision_result.get("rationale"),
            "facts": decision_result.get("facts"),
            "failed_periods": decision_result.get("failed_periods"),
        },
        "comparison_plans": sibling_plans,
    })
    model["cost"]["roi_unavailable_reason"] = separate_roi_reason(setup, records)
    model["cost"]["break_overload_note"] = separate_break_overload_note(setup, records)
    return model


@router.get("/analyses/{analysis_id}/selected/preview")
def selected_report_preview(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Preview the normalized Separate full-report model (same builder as exports)."""
    analysis = db.get(AnalysisProject, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {"model": _selected_report_model(db, user, analysis)}


@router.get("/analyses/{analysis_id}/selected/{format}")
def selected_report(
    analysis_id: int,
    format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Export the Separate full report as PDF or Excel from the same model."""
    from backend.reports.report_export import (
        generate_separate_excel_report,
        generate_separate_pdf_report,
    )

    analysis = db.get(AnalysisProject, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    model = _selected_report_model(db, user, analysis)
    if format == "pdf":
        buffer = generate_separate_pdf_report(model)
        return Response(
            content=buffer.getvalue(),
            media_type=PDF_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="novaq_separate_{analysis_id}.pdf"'},
        )
    if format == "excel":
        buffer = generate_separate_excel_report(model)
        return Response(
            content=buffer.getvalue(),
            media_type=EXCEL_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="novaq_separate_{analysis_id}.xlsx"'},
        )
    raise HTTPException(status_code=404, detail="Unknown report format.")


def _comparison_rows(scenario: Scenario) -> list[dict]:
    results = scenario.results_json or {}
    rows = results.get("comparison", results.get("results"))
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise HTTPException(
            status_code=422, detail="Scenario has no comparison results to report on."
        )
    return rows


def _scenario_payload(scenario: Scenario) -> tuple[pd.DataFrame, dict, list[str]]:
    rows = _comparison_rows(scenario)
    comparison_df = pd.DataFrame(rows)
    kpis = summarize_optimization(rows)
    kpis["roi_unavailable_reason"] = unstable_current_reason(rows)
    recommendations = build_recommendations(rows)
    recommendations.insert(0, "Analytical model estimates, not observed outcomes. Abandonment percentages are sensitivity assumptions; Erlang-A theta is a patience rate per hour.")
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    if snapshot:
        recommendations.append("Calculation engine: " + str(snapshot.get("engine_version")))
    for row in rows:
        if row.get("effective_constraints"):
            recommendations.append(str(row.get("time")) + " constraints: " + str(row["effective_constraints"]))
        if row.get("effective_costs"):
            recommendations.append(str(row.get("time")) + " configured cost assumptions: " + str(row["effective_costs"]))
        if row.get("explanation"):
            recommendations.append(str(row.get("selected_model")) + ": " + str(row["explanation"]))
    if not (scenario.settings_json or {}).get("calculation"):
        recommendations.insert(0, "Legacy scenario: these saved outputs have no verified calculation snapshot.")
    return comparison_df, kpis, recommendations


def _decision_recommendations(decision: dict | None) -> list[str]:
    if decision is None:
        return [
            "Management recommendation unavailable: complete Decision for the "
            "currently selected and simulated Scenario."
        ]
    messages = [
        str(decision.get("headline", "Management recommendation unavailable.")),
        str(decision.get("recommendation", "")),
    ]
    rationale = decision.get("rationale")
    if isinstance(rationale, list):
        messages.extend(str(item) for item in rationale)
    warning = decision.get("provenance_warning")
    if warning:
        messages.append(str(warning))
    return [message for message in messages if message]


def _separate_current_payload(dataset: Dataset) -> tuple[pd.DataFrame, dict, list[str]]:
    """Current-only payload for verified separate-queue analyses.

    Returns Current analytical (process_segments + compute_kpis) with optional
    Current-DES noted separately; optimization is BLOCKED, compare/decision
    are N/A, missing values are N/A never zero. No c_optimal, savings, or ROI
    is fabricated. Reuses the same minute conversion (Wq*60 at display) and
    staffing helpers via report_export; pooled path below is unchanged.
    """
    records = dataset.normalized_json or []
    results_df = process_segments(records)
    kpis = compute_kpis(results_df)
    comparison_df = pd.DataFrame(
        {
            "time": results_df["time"],
            "c_current": results_df["c"],
            "rho_current": results_df["rho"],
            "Wq_current": results_df["Wq"],
            "metric_provenance": "analytical",
            "selected_model": results_df["model"],
        }
    )
    recommendations = [
        "Analytical estimates from supplied aggregate rates, not observed waiting times or externally validated outcomes.",
        *current_only_blocked_lines(),
        "Current-DES: available via the Current-DES fallback when supported; never counted as optimized evidence.",
        "Missing values are N/A, never zero.",
    ]
    return comparison_df, kpis, recommendations


def _dataset_payload(dataset: Dataset) -> tuple[pd.DataFrame, dict, list[str]]:
    records = dataset.normalized_json or []
    if any(record.get("queue_structure") == "separate_queues" for record in records if isinstance(record, dict)):
        return _separate_current_payload(dataset)
    results_df = process_segments(records)
    kpis = compute_kpis(results_df)
    comparison_df = pd.DataFrame(
        {
            "time": results_df["time"],
            "c_current": results_df["c"],
            "rho_current": results_df["rho"],
            "Wq_current": results_df["Wq"],
            "metric_provenance": "analytical",
            "selected_model": results_df["model"],
        }
    )
    return comparison_df, kpis, ["Analytical estimates from supplied aggregate rates, not observed waiting times or externally validated outcomes."]


@router.get("/datasets/{dataset_id}/{format}")
def dataset_report(
    dataset_id: int,
    format: str,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    dataset = _own_dataset(db, user, dataset_id, analysis_id)
    comparison_df, kpis, recommendations = _dataset_payload(dataset)
    return _build_report(format, kpis, {}, comparison_df, recommendations, f"novaq_datasets_{dataset_id}")


@router.get("/scenarios/{scenario_id}/{format}")
def scenario_report(
    scenario_id: int,
    format: str,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    scenario = _own_scenario(db, user, scenario_id, analysis_id)
    comparison_df, kpis, recommendations = _scenario_payload(scenario)
    if analysis_id is not None:
        recommendations = _decision_recommendations(
            current_decision_for_report(db, user, analysis_id, scenario.id)
        )
    return _build_report(format, {}, kpis, comparison_df, recommendations, f"novaq_scenarios_{scenario_id}")


def _build_report(
    format: str,
    current_kpis: dict,
    recommended_kpis: dict,
    comparison_df: pd.DataFrame,
    recommendations: list[str],
    filename_stem: str,
) -> Response:
    if format == "pdf":
        buffer = generate_pdf_report(
            current_kpis,
            recommended_kpis,
            comparison_df,
            recommendations,
        )
        return Response(
            content=buffer.getvalue(),
            media_type=PDF_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename_stem}.pdf"'},
        )
    if format == "excel":
        buffer = generate_excel_report(
            comparison_df,
            recommended_kpis,
            current_kpis=current_kpis,
            recommendations=recommendations,
        )
        return Response(
            content=buffer.getvalue(),
            media_type=EXCEL_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename_stem}.xlsx"'},
        )
    raise HTTPException(status_code=404, detail="Unknown report format.")
