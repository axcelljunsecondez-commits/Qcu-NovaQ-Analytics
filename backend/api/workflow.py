"""Persistent, ownership-scoped evidence for the Analysis workflow."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, cast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analyses import own_analysis
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.settings import Settings
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segments,
    simulate_segments_with_trace,
    validate_with_simulation,
)

router = APIRouter(prefix="/analyses", tags=["workflow"])

ENGINE_VERSION = "novaq-2026-09-unified-des-v1"
WORKFLOW_KINDS = {
    "workflow_selection",
    "workflow_des",
    "workflow_des_current",
    "workflow_mc",
    "workflow_mc_current",
    "workflow_validation",
    "workflow_decision",
}


class SelectionRequest(BaseModel):
    scenario_id: int


class WorkflowDesRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    sim_hours: float = Field(default=24.0, gt=0, le=168)
    queue_overload_threshold: int = Field(default=20, ge=1)
    max_events: int = Field(default=3000, ge=1, le=3000)
    seed: int | None = 42
    carryover: bool = True


class WorkflowMcRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    num_trials: int = Field(default=2000, ge=1, le=100000)
    failure_threshold: float = Field(default=0.8, gt=0, le=1)
    failure_rate_cap: float = Field(default=0.05, gt=0, le=1)
    seed: int | None = 42


class WorkflowValidationRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    des_sim_hours: float = Field(default=24.0, gt=0, le=168)
    mc_trials: int = Field(default=2000, ge=1, le=100000)
    mc_failure_threshold: float = Field(default=0.8, gt=0, le=1)
    mc_failure_rate_cap: float = Field(default=0.05, gt=0, le=1)
    seed: int | None = 42


def _finite_non_negative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0
    )


def _scenario_rows(scenario: Scenario) -> list[dict[str, Any]]:
    results = scenario.results_json or {}
    rows = results.get("results", results.get("comparison"))
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise HTTPException(status_code=422, detail="Scenario has no optimization results.")
    return rows


def _operationally_complete(rows: list[dict[str, Any]]) -> bool:
    return all(
        isinstance(row.get("c_current"), int)
        and row["c_current"] > 0
        and _finite_non_negative(row.get("rho_current"))
        and row.get("optimized_stable") is True
        and isinstance(row.get("c_optimal"), int)
        and row["c_optimal"] > 0
        and _finite_non_negative(row.get("rho_optimal"))
        and _finite_non_negative(row.get("Wq_optimal"))
        and _finite_non_negative(row.get("Lq_optimal"))
        for row in rows
    )


def _own_verified_scenario(
    db: Session, user: User, analysis: AnalysisProject, scenario_id: int
) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if (
        scenario is None
        or scenario.user_id != user.id
        or scenario.analysis_id != analysis.id
        or scenario.dataset_id is None
        or not (scenario.settings_json or {}).get("calculation")
    ):
        raise HTTPException(
            status_code=422,
            detail="Select a verified Scenario from this Analysis.",
        )
    dataset = db.get(Dataset, scenario.dataset_id)
    if (
        dataset is None
        or dataset.user_id != user.id
        or dataset.analysis_id != analysis.id
        or not (dataset.validation_report_json or {}).get("ok")
    ):
        raise HTTPException(status_code=422, detail="Scenario source Dataset is unavailable.")
    if not _operationally_complete(_scenario_rows(scenario)):
        raise HTTPException(status_code=422, detail="Scenario comparison evidence is incomplete.")
    return scenario


def _segments_for(scenario: Scenario, dataset: Dataset | None = None) -> list[dict[str, Any]]:
    rows = _scenario_rows(scenario)
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    source = snapshot.get("input_segments")
    if not isinstance(source, list) or len(source) != len(rows):
        raise HTTPException(status_code=422, detail="Scenario calculation inputs are incomplete.")
    segments: list[dict[str, Any]] = []
    for source_row, result_row in zip(source, rows):
        if not isinstance(source_row, dict):
            raise HTTPException(status_code=422, detail="Scenario calculation inputs are invalid.")
        segment = dict(source_row)
        segment["time"] = str(result_row.get("time", source_row.get("time", "Unknown")))
        segment["c"] = int(result_row["c_optimal"])
        if source_row.get("model_id") == "parallel_mg1" or source_row.get("queue_structure") == "separate_queues":
            if dataset is None:
                raise HTTPException(status_code=422, detail="Parallel M/G/1 DES source Dataset is unavailable.")
            segment_id = str(source_row.get("segment_id", ""))
            queue_id = str(source_row.get("queue_id", ""))
            evidence = next(
                (
                    row for row in (dataset.normalized_json or [])
                    if str(row.get("segment_id", "")) == segment_id
                    and str(row.get("queue_id", "")) == queue_id
                ),
                None,
            )
            if evidence is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Missing persisted empirical service evidence for {segment_id}/{queue_id}.",
                )
            for field in (
                "segment_id",
                "queue_id",
                "queue_structure",
                "model_id",
                "server_id",
                "service_time_source",
                "service_samples_hours",
            ):
                if field in evidence:
                    segment[field] = evidence[field]
            if segment.get("c") != 1:
                raise HTTPException(status_code=422, detail="Parallel M/G/1 DES requires one dedicated server per queue.")
        segments.append(segment)
    return segments


def _current_dataset(db: Session, user: User, analysis: AnalysisProject) -> Dataset:
    candidates = db.execute(
        select(Dataset)
        .where(Dataset.user_id == user.id, Dataset.analysis_id == analysis.id)
        .order_by(Dataset.id.desc())
    ).scalars()
    dataset = next(
        (item for item in candidates if (item.validation_report_json or {}).get("ok")),
        None,
    )
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="This Analysis has no successfully processed dataset.",
        )
    return dataset


def _current_segments_for(
    analysis: AnalysisProject, dataset: Dataset
) -> list[dict[str, Any]]:
    records = dataset.normalized_json or []
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=422, detail="This Analysis has no Current evidence.")
    segments: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            raise HTTPException(status_code=422, detail="Current dataset records are invalid.")
        segment = dict(row)
        segment["time"] = str(row.get("time", row.get("segment_id", "Unknown")))
        if segment.get("model_id") == "parallel_mg1" or segment.get("queue_structure") == "separate_queues":
            try:
                c_value = int(segment.get("c", 1))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail="Parallel M/G/1 DES requires one dedicated server per queue.",
                ) from None
            segment["c"] = c_value
            if segment.get("c") != 1:
                raise HTTPException(status_code=422, detail="Parallel M/G/1 DES requires one dedicated server per queue.")
        segments.append(segment)
    _ = analysis
    return segments


def _job_matches(job: Job, analysis_id: int, scenario_id: int | None = None) -> bool:
    params = job.params_json or {}
    if params.get("analysis_id") != analysis_id:
        return False
    return scenario_id is None or params.get("scenario_id") == scenario_id


def _latest_job(
    db: Session,
    user: User,
    kind: str,
    analysis_id: int,
    scenario_id: int | None = None,
) -> Job | None:
    jobs = db.execute(
        select(Job)
        .where(Job.user_id == user.id, Job.kind == kind, Job.status == "completed")
        .order_by(Job.id.desc())
    ).scalars()
    return next(
        (job for job in jobs if _job_matches(job, analysis_id, scenario_id)),
        None,
    )


def _job_out(job: Job | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "params": job.params_json or {},
        "result": job.result_json,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def _save_job(
    db: Session,
    user: User,
    kind: str,
    analysis: AnalysisProject,
    scenario: Scenario | None,
    params: dict[str, Any],
    result: dict[str, Any],
    settings: Settings,
    dataset_id: int | None = None,
) -> Job:
    if kind not in WORKFLOW_KINDS:
        raise ValueError("Unknown workflow evidence kind.")
    encoded = json.dumps(result, allow_nan=False, ensure_ascii=False).encode("utf-8")
    if len(encoded) > settings.result_jsonb_max_bytes:
        raise HTTPException(
            status_code=413,
            detail="Workflow evidence is too large. Reduce the playback event cap.",
        )
    now = datetime.now(timezone.utc)
    if scenario is None:
        scenario_id: int | None = None
        resolved_dataset_id: int | None = dataset_id
    else:
        scenario_id = scenario.id
        resolved_dataset_id = scenario.dataset_id
    job = Job(
        user_id=user.id,
        kind=kind,
        status="completed",
        params_json={
            "analysis_id": analysis.id,
            "scenario_id": scenario_id,
            "dataset_id": resolved_dataset_id,
            "engine_version": ENGINE_VERSION,
            **params,
        },
        result_json=result,
        tenant_id=user.tenant_id,
        finished_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _selected_scenario(
    db: Session, user: User, analysis: AnalysisProject
) -> tuple[Scenario | None, Job | None]:
    selection = _latest_job(db, user, "workflow_selection", analysis.id)
    if selection is None:
        return None, None
    scenario_id = (selection.params_json or {}).get("scenario_id")
    if not isinstance(scenario_id, int):
        return None, selection
    try:
        return _own_verified_scenario(db, user, analysis, scenario_id), selection
    except HTTPException:
        return None, selection


def _current_evidence(
    db: Session, user: User, analysis: AnalysisProject
) -> dict[str, Any]:
    scenario, selection = _selected_scenario(db, user, analysis)
    scenario_id = scenario.id if scenario is not None else None
    des = _latest_job(db, user, "workflow_des", analysis.id, scenario_id) if scenario_id else None
    des_current = _latest_job(db, user, "workflow_des_current", analysis.id)
    mc_current = _latest_job(db, user, "workflow_mc_current", analysis.id)
    mc = _latest_job(db, user, "workflow_mc", analysis.id, scenario_id) if scenario_id else None
    validation = (
        _latest_job(db, user, "workflow_validation", analysis.id, scenario_id)
        if scenario_id
        else None
    )
    decision = (
        _latest_job(db, user, "workflow_decision", analysis.id, scenario_id)
        if scenario_id
        else None
    )
    decision_stale = False
    if decision is not None:
        references = (decision.result_json or {}).get("evidence_ids") or {}
        decision_stale = (
            references.get("selection") != (selection.id if selection else None)
            or references.get("des") != (des.id if des else None)
            or references.get("validation") != (validation.id if validation else None)
        )
        if decision_stale:
            decision = None
    return {
        "analysis_id": analysis.id,
        "selection": _job_out(selection),
        "scenario": {
            "id": scenario.id,
            "name": scenario.name,
            "dataset_id": scenario.dataset_id,
            "provenance": "verified_snapshot",
        } if scenario else None,
        "des": _job_out(des),
        "des_current": _job_out(des_current),
        "mc": _job_out(mc),
        "mc_current": _job_out(mc_current),
        "validation": _job_out(validation),
        "decision": _job_out(decision),
        "decision_stale": decision_stale,
    }


def current_decision_for_report(
    db: Session, user: User, analysis_id: int, scenario_id: int
) -> dict[str, Any] | None:
    analysis = own_analysis(db, user, analysis_id)
    evidence = _current_evidence(db, user, analysis)
    scenario = evidence.get("scenario")
    decision = evidence.get("decision")
    if not scenario or scenario.get("id") != scenario_id or not decision:
        return None
    result = decision.get("result")
    return result if isinstance(result, dict) else None


@router.get("/{analysis_id}/workflow")
def get_workflow(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return _current_evidence(db, user, own_analysis(db, user, analysis_id))


@router.post("/{analysis_id}/workflow/selection")
def select_scenario(
    analysis_id: int,
    payload: SelectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    scenario = _own_verified_scenario(db, user, analysis, payload.scenario_id)
    job = _save_job(
        db, user, "workflow_selection", analysis, scenario, {},
        {"scenario_id": scenario.id, "scenario_name": scenario.name}, settings,
    )
    return {"selection": _job_out(job)}


def _require_selection(
    db: Session, user: User, analysis: AnalysisProject
) -> Scenario:
    scenario, _ = _selected_scenario(db, user, analysis)
    if scenario is None:
        raise HTTPException(status_code=409, detail="Select a Scenario in Compare first.")
    return scenario


@router.post(
    "/{analysis_id}/workflow/simulation/des",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_des(
    analysis_id: int,
    payload: WorkflowDesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    scenario = _require_selection(db, user, analysis)
    dataset = db.get(Dataset, scenario.dataset_id) if scenario.dataset_id is not None else None
    result = simulate_segments_with_trace(
        _segments_for(scenario, dataset),
        sim_hours=payload.sim_hours,
        queue_overload_threshold=payload.queue_overload_threshold,
        max_events=payload.max_events,
        seed=payload.seed,
        carryover=payload.carryover,
        queue_setup=analysis.queue_setup_json,
    )
    job = _save_job(
        db, user, "workflow_des", analysis, scenario,
        payload.model_dump(), result, settings,
    )
    return {"evidence": _job_out(job)}


@router.post(
    "/{analysis_id}/workflow/simulation/des/current",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_des_current(
    analysis_id: int,
    payload: WorkflowDesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    dataset = _current_dataset(db, user, analysis)
    segments = _current_segments_for(analysis, dataset)
    result = simulate_segments_with_trace(
        segments,
        sim_hours=payload.sim_hours,
        queue_overload_threshold=payload.queue_overload_threshold,
        max_events=payload.max_events,
        seed=payload.seed,
        carryover=payload.carryover,
        queue_setup=analysis.queue_setup_json,
    )
    result["provenance"] = "CURRENT"
    job = _save_job(
        db, user, "workflow_des_current", analysis, None,
        payload.model_dump(), result, settings, dataset_id=dataset.id,
    )
    return {"evidence": _job_out(job)}


@router.post(
    "/{analysis_id}/workflow/simulation/mc",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_mc(
    analysis_id: int,
    payload: WorkflowMcRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    scenario = _require_selection(db, user, analysis)
    result = {
        "results": mc_simulate_segments(
            _segments_for(scenario),
            num_trials=payload.num_trials,
            failure_threshold=payload.failure_threshold,
            failure_rate_cap=payload.failure_rate_cap,
            seed=payload.seed,
        )
    }
    job = _save_job(
        db, user, "workflow_mc", analysis, scenario,
        payload.model_dump(), result, settings,
    )
    return {"evidence": _job_out(job)}


@router.post(
    "/{analysis_id}/workflow/simulation/mc/current",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_mc_current(
    analysis_id: int,
    payload: WorkflowMcRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    dataset = _current_dataset(db, user, analysis)
    segments = _current_segments_for(analysis, dataset)
    result: dict[str, Any] = {
        "results": mc_simulate_segments(
            segments,
            num_trials=payload.num_trials,
            failure_threshold=payload.failure_threshold,
            failure_rate_cap=payload.failure_rate_cap,
            seed=payload.seed,
        )
    }
    result["provenance"] = "CURRENT"
    job = _save_job(
        db, user, "workflow_mc_current", analysis, None,
        payload.model_dump(), result, settings, dataset_id=dataset.id,
    )
    return {"evidence": _job_out(job)}


@router.post(
    "/{analysis_id}/workflow/simulation/validation",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_validation(
    analysis_id: int,
    payload: WorkflowValidationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    scenario = _require_selection(db, user, analysis)
    frame = validate_with_simulation(
        pd.DataFrame(_scenario_rows(scenario)),
        des_sim_hours=payload.des_sim_hours,
        mc_trials=payload.mc_trials,
        mc_failure_threshold=payload.mc_failure_threshold,
        failure_rate_cap=payload.mc_failure_rate_cap,
        seed=payload.seed,
    )
    rows = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    result = {"results": rows}
    job = _save_job(
        db, user, "workflow_validation", analysis, scenario,
        payload.model_dump(), result, settings,
    )
    return {"evidence": _job_out(job)}


def _cost_totals(rows: list[dict[str, Any]]) -> tuple[float, float] | None:
    current = [row.get("cost_current") for row in rows]
    optimal = [row.get("cost_optimal") for row in rows]
    if not all(_finite_non_negative(value) for value in [*current, *optimal]):
        return None
    return (
        sum(float(cast(int | float, value)) for value in current),
        sum(float(cast(int | float, value)) for value in optimal),
    )


def _derive_decision(
    analysis: AnalysisProject,
    scenario: Scenario | None,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    if analysis.setup_status not in {"ready", "ready_for_aggregate"}:
        missing.append("completed Setup")
    if scenario is None:
        missing.append("a verified Scenario selected in Compare")
    des = evidence.get("des")
    validation = evidence.get("validation")
    if des is None:
        missing.append("a completed DES and Live Playback run")
    if validation is None:
        missing.append("a completed Scenario Validation run")

    rows = _scenario_rows(scenario) if scenario is not None else []
    totals = _cost_totals(rows) if rows else None
    if scenario is not None and totals is None:
        missing.append("a complete modeled cost comparison")

    expected_times = [str(row.get("time", "")) for row in rows]
    des_rows = ((des or {}).get("result") or {}).get("results", [])
    if des is not None and (
        [str(row.get("time", "")) for row in des_rows] != expected_times
        or any(row.get("simulation_supported") is not True or row.get("error") for row in des_rows)
    ):
        missing.append("supported, error-free DES evidence for every interval")

    validation_rows = ((validation or {}).get("result") or {}).get("results", [])

    def _evidence_key(row: dict[str, Any]) -> tuple[str, str | None]:
        queue_id = row.get("queue_id")
        return (
            str(row.get("time", "")),
            queue_id if isinstance(queue_id, str) else None,
        )

    if validation is not None and (
        [_evidence_key(row) for row in validation_rows] != [_evidence_key(row) for row in rows]
    ):
        missing.append("validation evidence for every interval")

    evidence_ids = {
        "selection": evidence["selection"]["id"] if evidence.get("selection") else None,
        "des": des["id"] if des else None,
        "mc": evidence["mc"]["id"] if evidence.get("mc") else None,
        "validation": validation["id"] if validation else None,
    }
    if missing:
        return {
            "status": "insufficient_evidence",
            "headline": "Insufficient evidence to make a management recommendation.",
            "recommendation": "Complete the missing workflow evidence before making an adoption decision.",
            "rationale": [f"Missing: {item}." for item in missing],
            "missing_evidence": missing,
            "scenario_id": scenario.id if scenario else None,
            "scenario_name": scenario.name if scenario else None,
            "dataset_id": scenario.dataset_id if scenario else None,
            "evidence_ids": evidence_ids,
            "provenance_warning": (
                "Analytical estimates and simulated results are decision support, "
                "not observed future outcomes."
            ),
        }

    assert scenario is not None and totals is not None and validation is not None
    failure_cap_value = (validation.get("params") or {}).get("mc_failure_rate_cap")
    assert isinstance(failure_cap_value, (int, float)) and not isinstance(
        failure_cap_value, bool
    )
    failure_cap = float(failure_cap_value)

    def row_passes(row: dict[str, Any]) -> bool:
        failure_rate = row.get("mc_failure_rate")
        if not _finite_non_negative(failure_rate):
            return False
        return (
            row.get("simulation_supported") is True
            and not row.get("validation_reason")
            and row.get("sim_status") not in {"ERROR", "Critical", "Unstable"}
            and float(cast(int | float, failure_rate)) <= failure_cap
            and row.get("mc_failure_rate_adequate") is True
        )

    failed = [row for row in validation_rows if not row_passes(row)]
    current_cost, optimal_cost = totals
    savings = current_cost - optimal_cost
    server_delta = sum(int(row["c_optimal"]) - int(row["c_current"]) for row in rows)
    facts = {
        "current_modeled_cost": current_cost,
        "selected_modeled_cost": optimal_cost,
        "modeled_savings": savings,
        "server_delta": server_delta,
        "validation_intervals": len(validation_rows),
        "failed_intervals": len(failed),
        "failure_rate_cap": failure_cap,
    }
    if failed:
        status = "revise"
        headline = f'Do not adopt Scenario "{scenario.name}" yet.'
        recommendation = (
            f"Revise and re-test the plan because {len(failed)} of "
            f"{len(validation_rows)} validation intervals did not pass."
        )
    elif savings >= 0:
        status = "adopt"
        headline = f'Adopt Scenario "{scenario.name}".'
        recommendation = (
            f"All {len(validation_rows)} validation intervals passed and modeled "
            f"cost decreases by PHP {savings:,.2f} per modeled cycle."
        )
    else:
        status = "conditional"
        headline = f'Consider Scenario "{scenario.name}" conditionally.'
        recommendation = (
            f"All {len(validation_rows)} validation intervals passed, but modeled "
            f"cost increases by PHP {abs(savings):,.2f} per modeled cycle."
        )
    return {
        "status": status,
        "headline": headline,
        "recommendation": recommendation,
        "rationale": [
            f"Selected Scenario: {scenario.name} (ID {scenario.id}).",
            f"Net server change across intervals: {server_delta:+d}.",
            (
                f"Validation: {len(validation_rows) - len(failed)} of "
                f"{len(validation_rows)} intervals passed."
            ),
        ],
        "missing_evidence": [],
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "dataset_id": scenario.dataset_id,
        "evidence_ids": evidence_ids,
        "facts": facts,
        "provenance_warning": (
            "Analytical estimates and simulated results are decision support, "
            "not observed future outcomes."
        ),
    }


@router.post("/{analysis_id}/workflow/decision")
def create_decision(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    evidence = _current_evidence(db, user, analysis)
    scenario, _ = _selected_scenario(db, user, analysis)
    result = _derive_decision(analysis, scenario, evidence)
    if scenario is None:
        return {"decision": result, "persisted": False}
    job = _save_job(
        db, user, "workflow_decision", analysis, scenario,
        {"evidence_ids": result["evidence_ids"]}, result, settings,
    )
    return {"decision": result, "persisted": True, "evidence": _job_out(job)}
