"""Persistent, ownership-scoped evidence for the Analysis workflow."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from typing import Any, cast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analyses import _to_out as analysis_out
from backend.api.analyses import own_analysis
from backend.api.analysis_schemas import QueueSetup, setup_status
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.scenarios import setup_fingerprint as _setup_fingerprint
from backend.api.settings import Settings
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.config import (
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    MC_DEFAULT_FAILURE_THRESHOLD,
)
from backend.queueing_engine.services.break_optimization import (
    DEFAULT_MAX_SHIFT_MINUTES,
    DEFAULT_TARGET_RHO,
    optimize_separate_breaks,
    place_breaks,
    slot_inputs_from_setup,
)
from backend.queueing_engine.services.data_processing import _weighted_wait, compute_kpis
from backend.queueing_engine.services.model_explanations import analyze_segments
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
    _period_current_active,
    _segment_window,
    des_day_start_minutes,
    evaluate_candidate_with_des,
    full_coverage_min_lanes,
    index_period_queues,
    optimize_separate_schedule,
    period_des_breaks,
    prune_separate_schedule,
    replication_seeds,
    resolve_des_breaks,
    run_routing_day_des,
    validate_des_replication_config,
)
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
    "workflow_validation_current",
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
    failure_threshold: float = Field(default=MC_DEFAULT_FAILURE_THRESHOLD, gt=0, le=1)
    failure_rate_cap: float = Field(default=0.05, gt=0, le=1)
    seed: int | None = 42


class SelectedMcRequest(WorkflowMcRequest):
    """Selected-plan MC: an omitted failure threshold means the plan's target."""

    failure_threshold: float | None = Field(default=None, gt=0, le=1)  # type: ignore[assignment]


class WorkflowValidationRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    des_sim_hours: float = Field(default=24.0, gt=0, le=168)
    mc_trials: int = Field(default=2000, ge=1, le=100000)
    mc_failure_threshold: float = Field(default=MC_DEFAULT_FAILURE_THRESHOLD, gt=0, le=1)
    mc_failure_rate_cap: float = Field(default=0.05, gt=0, le=1)
    seed: int | None = 42


class SeparateOptimizeDesConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    replications: StrictInt | None = None
    base_seed: StrictInt | None = None
    duration_hours: float | None = Field(default=None, gt=0)
    max_events: StrictInt | None = None


class SeparateOptimizeRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    dataset_id: int | None = None
    target_utilization: float = Field(default=0.70, ge=0.40, le=0.90)
    server_cost_per_hr: float = Field(default=DEFAULT_SERVER_COST_HR, gt=0)
    customer_waiting_cost: float = Field(default=DEFAULT_WAIT_COST_HR, ge=0)
    min_active_lanes: int | None = Field(default=None, ge=1)
    max_active_lanes: int | None = Field(default=None, ge=1)
    lambda_multiplier: float = Field(default=1.0, gt=0)
    des: SeparateOptimizeDesConfig = Field(default_factory=SeparateOptimizeDesConfig)


class SeparateBreakOptimizeDesConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    replications: StrictInt = Field(default=5, ge=1, le=20)
    base_seed: StrictInt = 42


class SeparateBreakOptimizeRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    dataset_id: int | None = None
    target_rho: float = Field(default=DEFAULT_TARGET_RHO, gt=0, le=1)
    max_shift_minutes: StrictInt = Field(default=DEFAULT_MAX_SHIFT_MINUTES, ge=0, le=240, multiple_of=15)
    des: SeparateBreakOptimizeDesConfig = Field(default_factory=SeparateBreakOptimizeDesConfig)


class SeparateBreakApplyRequest(BaseModel):
    """Re-run placement server-side; break times are never taken from the client."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    target_rho: float = Field(gt=0, le=1)
    max_shift_minutes: StrictInt = Field(ge=0, le=240, multiple_of=15)
    setup_hash: str = Field(min_length=1, max_length=128)
    dataset_id: StrictInt


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


def _separate_schedule_problem(scenario: Scenario) -> str | None:
    """Return None when a saved Separate plan is complete and selectable.

    Requires a supported schema-v2 snapshot, a COMPLETE schedule, and every
    period OPTIMAL with an estimated optimum lane count. Anything else is
    reported as a reason instead of becoming selectable.
    """
    calc = (scenario.settings_json or {}).get("calculation") or {}
    if (calc.get("schema_version") != 2
            or calc.get("engine_version") != SEPARATE_DES_ENGINE_VERSION):
        return "not a supported Separate optimization snapshot"
    schedule = (scenario.results_json or {}).get("schedule")
    if not isinstance(schedule, dict) or schedule.get("overall") != "COMPLETE":
        return "schedule is not COMPLETE"
    periods = schedule.get("periods")
    if not isinstance(periods, list) or not periods:
        return "schedule has no periods"
    for period in periods:
        label = period.get("time", "?") if isinstance(period, dict) else "?"
        if not isinstance(period, dict) or period.get("overall") != "OPTIMAL":
            return f"period {label} is not OPTIMAL"
        lanes = period.get("optimal_active_lanes")
        if isinstance(lanes, bool) or not isinstance(lanes, int) or lanes < 1:
            return f"period {label} has no optimal lane count"
        if (period.get("optimum") or {}).get("estimated_optimal") is not True:
            return f"period {label} lacks an estimated optimum"
    return None


SETUP_STALE_DETAIL = "Setup changed since this evidence was produced. Rerun Simulation."


def _job_setup_current(job: Job | None, analysis: AnalysisProject) -> bool:
    """True only when the job recorded the analysis's current Setup (fail-closed)."""
    if job is None:
        return False
    return (job.params_json or {}).get("setup_hash") == _setup_fingerprint(
        analysis.queue_setup_json
    )


def _require_setup_current(analysis: AnalysisProject, *jobs: Job) -> None:
    if not all(_job_setup_current(job, analysis) for job in jobs):
        raise HTTPException(status_code=409, detail=SETUP_STALE_DETAIL)


_SETUP_QUEUE_TYPE: dict[Any, str] = {"separate_queues": "separate", "shared_queue": "shared"}


def _legacy_snapshot_queue_type(snapshot: dict[str, Any]) -> str:
    """Queue type a legacy (non-v2) snapshot was calculated for.

    "separate" if any input segment is a separate-queue / parallel M/G/1 row,
    else "shared". It must equal the analysis's current queue_structure
    (separate_queues -> separate, shared_queue -> shared); any other
    structure, including unknown, is not verifiable.
    """
    segments = snapshot.get("input_segments") or []
    separate = any(
        isinstance(row, dict)
        and (row.get("queue_structure") == "separate_queues" or row.get("model_id") == "parallel_mg1")
        for row in segments
    )
    return "separate" if separate else "shared"


def _scenario_setup_problem(scenario: Scenario, analysis: AnalysisProject) -> str | None:
    """Return why a saved Scenario cannot describe the current Setup, if it cannot."""
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    setup = analysis.queue_setup_json or {}
    if snapshot.get("schema_version") == 2:
        if snapshot.get("setup_hash") != _setup_fingerprint(setup):
            return "stale for the current Setup"
        return None
    if _legacy_snapshot_queue_type(snapshot) != _SETUP_QUEUE_TYPE.get(setup.get("queue_structure")):
        return "not verifiable for the current Setup queue structure"
    return None


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
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    if snapshot.get("schema_version") == 2:
        problem = _separate_schedule_problem(scenario)
        if problem is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Separate plan is not selectable: {problem}.",
            )
        if scenario.dataset_id != _current_valid_dataset_id(db, user, analysis):
            raise HTTPException(
                status_code=422,
                detail="Separate plan is stale for the current dataset.",
            )
        if _scenario_setup_problem(scenario, analysis) is not None:
            raise HTTPException(
                status_code=422,
                detail="Separate plan is stale for the current Setup.",
            )
        return scenario
    if _scenario_setup_problem(scenario, analysis) is not None:
        raise HTTPException(
            status_code=422,
            detail="Scenario is not verifiable for the current Setup queue structure.",
        )
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


def _current_valid_dataset_id(db: Session, user: User, analysis: AnalysisProject) -> int | None:
    """Latest successfully processed dataset id, or None when absent."""
    candidates = db.execute(
        select(Dataset)
        .where(Dataset.user_id == user.id, Dataset.analysis_id == analysis.id)
        .order_by(Dataset.id.desc())
    ).scalars()
    match = next((item for item in candidates if (item.validation_report_json or {}).get("ok")), None)
    return match.id if match is not None else None


def _current_dataset(db: Session, user: User, analysis: AnalysisProject) -> Dataset:
    dataset_id = _current_valid_dataset_id(db, user, analysis)
    if dataset_id is None:
        raise HTTPException(
            status_code=404,
            detail="This Analysis has no successfully processed dataset.",
        )
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:  # pragma: no cover - defensive against concurrent deletion
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
            "setup_hash": _setup_fingerprint(analysis.queue_setup_json),
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

    def current(job: Job | None) -> Job | None:
        # Evidence produced under a different (or unrecorded) Setup is absent.
        return job if _job_setup_current(job, analysis) else None

    des = current(_latest_job(db, user, "workflow_des", analysis.id, scenario_id)) if scenario_id else None
    des_current = current(_latest_job(db, user, "workflow_des_current", analysis.id))
    mc_current = current(_latest_job(db, user, "workflow_mc_current", analysis.id))
    mc = current(_latest_job(db, user, "workflow_mc", analysis.id, scenario_id)) if scenario_id else None
    validation = (
        current(_latest_job(db, user, "workflow_validation", analysis.id, scenario_id))
        if scenario_id
        else None
    )
    validation_current = current(_latest_job(db, user, "workflow_validation_current", analysis.id))
    selected_id = (selection.params_json or {}).get("scenario_id") if selection else None
    raw_decision = (
        _latest_job(db, user, "workflow_decision", analysis.id, selected_id)
        if isinstance(selected_id, int)
        else None
    )
    decision = raw_decision if scenario_id else None
    decision_stale = False
    if raw_decision is not None and not _job_setup_current(raw_decision, analysis):
        decision = None
        decision_stale = True
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
        "validation_current": _job_out(validation_current),
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


def _separate_validation_verdict(
    required_pairs: list[tuple[str, str]],
    mc_rows_by_pair: dict[tuple[str, str], dict[str, Any]],
    failure_cap: float,
) -> dict[str, Any]:
    """Aggregate per-queue validation verdicts with FAIL > insufficient > PASS.

    Each required (time, queue_id) pair is evaluated only against its own MC
    row. No pooled or averaged failure rate is computed. Missing, unsupported,
    errored, or inadequate rows make the overall evidence insufficient, never
    a pass and never zero.
    """
    failed: list[tuple[str, str]] = []
    inadequate: list[tuple[str, str]] = []
    rows: list[dict[str, Any]] = []
    for key in required_pairs:
        time_label, queue_id = key
        mc = mc_rows_by_pair.get(key)
        if mc is None:
            inadequate.append(key)
            continue
        failure_rate = mc.get("mc_failure_rate", mc.get("failure_rate"))
        adequate = mc.get("mc_failure_rate_adequate", mc.get("failure_rate_adequate"))
        verdict = "pass"
        if (
            mc.get("simulation_supported") is not True
            or not _finite_non_negative(failure_rate)
            or adequate is not True
        ):
            verdict = "inadequate"
            inadequate.append(key)
        elif float(cast(int | float, failure_rate)) > failure_cap:
            verdict = "fail"
            failed.append(key)
        rows.append({
            "time": time_label,
            "queue_id": queue_id,
            "selected_model": mc.get("selected_model"),
            "mc_failure_rate": failure_rate,
            "mc_failure_rate_adequate": adequate,
            "failure_rate_cap": failure_cap,
            "validation_verdict": verdict,
        })
    if failed:
        status = "fail"
    elif inadequate:
        status = "insufficient"
    else:
        status = "pass"
    return {"status": status, "failed": failed, "inadequate": inadequate,
            "total": len(required_pairs), "results": rows}


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


@router.post(
    "/{analysis_id}/workflow/simulation/validation/current",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_validation_current(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Validate the current separate-queue operation from persisted MC evidence.

    No optimized scenario is required or fabricated: required rows are the
    Current analytical (time, queue_id) entities and verdicts aggregate from
    the persisted Current-MC rows with FAIL > insufficient > PASS precedence.
    """
    analysis = own_analysis(db, user, analysis_id)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(
            status_code=422,
            detail="Current validation is only supported for separate-queue analyses.",
        )
    dataset = _current_dataset(db, user, analysis)
    mc_job = _latest_job(db, user, "workflow_mc_current", analysis.id)
    if mc_job is None:
        raise HTTPException(
            status_code=404,
            detail="Run Current Monte Carlo before validating the current operation.",
        )
    mc_params = mc_job.params_json or {}
    if mc_params.get("dataset_id") != dataset.id:
        raise HTTPException(
            status_code=409,
            detail="Current Monte Carlo evidence is stale for this dataset. Rerun Current Monte Carlo.",
        )
    _require_setup_current(analysis, mc_job)
    failure_cap = mc_params.get("failure_rate_cap")
    if (
        not isinstance(failure_cap, (int, float))
        or isinstance(failure_cap, bool)
        or not math.isfinite(float(failure_cap))
    ):
        raise HTTPException(
            status_code=422,
            detail="Current Monte Carlo evidence has no usable failure cap.",
        )
    frame, _, _ = analyze_segments(
        dataset.normalized_json or [],
        setup,
        dataset.validation_report_json or {},
    )
    required = [
        (str(row.get("time", "")), str(row.get("queue_id", "")))
        for _, row in frame.iterrows()
        if isinstance(row.get("queue_id"), str) and row.get("queue_id").strip()
    ]
    mc_rows = ((mc_job.result_json or {}).get("results") or [])
    mc_by_pair = {
        (str(row.get("time", "")), str(row.get("queue_id", ""))): row
        for row in mc_rows
        if isinstance(row, dict) and isinstance(row.get("queue_id"), str)
    }
    verdict = _separate_validation_verdict(required, mc_by_pair, float(failure_cap))
    result: dict[str, Any] = {
        "results": verdict.pop("results"),
        "verdict": verdict,
        "mc_job_id": mc_job.id,
        "provenance": "CURRENT",
    }
    job = _save_job(
        db, user, "workflow_validation_current", analysis, None,
        {"mc_job_id": mc_job.id}, result, settings, dataset_id=dataset.id,
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


@router.post(
    "/{analysis_id}/workflow/optimize/separate",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_separate_optimize(
    analysis_id: int,
    payload: SeparateOptimizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Optimize staffing period-by-period for a separate-queue analysis.

    Queue structure branches here: shared-queue analyses are rejected so the
    shared optimizer path is never forced through separate logic. Periods
    group persisted dataset rows by time label with current lanes resolved
    from the authoritative queue setup; every candidate ranking uses
    DES_REPLICATIONS evidence. Trace payloads are pruned for transfer.
    """
    analysis = own_analysis(db, user, analysis_id)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(
            status_code=422,
            detail="Separate optimization requires a separate_queues analysis.",
        )
    if payload.dataset_id is not None:
        dataset = db.get(Dataset, payload.dataset_id)
        if dataset is None or dataset.user_id != user.id or dataset.analysis_id != analysis.id:
            raise HTTPException(status_code=404, detail="Dataset not found in this Analysis.")
    else:
        dataset = _current_dataset(db, user, analysis)
    records = dataset.normalized_json or []
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=422, detail="This Analysis has no Current evidence.")
    try:
        des_settings = validate_des_replication_config(
            {key: value for key, value in payload.des.model_dump().items() if value is not None}
        )
        full_coverage_min_lanes(setup, payload.min_active_lanes)
        schedule = optimize_separate_schedule(
            setup,
            records,
            target=payload.target_utilization,
            server_cost=payload.server_cost_per_hr,
            waiting_cost=payload.customer_waiting_cost,
            max_lanes=payload.max_active_lanes,
            lambda_multiplier=payload.lambda_multiplier,
            des_settings=des_settings,
            full_coverage=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"schedule": prune_separate_schedule(schedule)}


@router.post(
    "/{analysis_id}/workflow/optimize/separate/breaks",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_separate_break_optimize(
    analysis_id: int,
    payload: SeparateBreakOptimizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Propose moved break start times for a separate-queue analysis.

    Read-only: the Setup is never written. Placement lowers the day's peak
    15-minute utilization; the existing continuous-day routing DES runs the
    current and proposed break schedules under identical seeds.
    """
    analysis = own_analysis(db, user, analysis_id)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(status_code=422, detail="Break optimization is available for separate queues.")
    if payload.dataset_id is not None:
        dataset = db.get(Dataset, payload.dataset_id)
        if dataset is None or dataset.user_id != user.id or dataset.analysis_id != analysis.id:
            raise HTTPException(status_code=404, detail="Dataset not found in this Analysis.")
    else:
        dataset = _current_dataset(db, user, analysis)
    records = dataset.normalized_json or []
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=422, detail="This Analysis has no Current evidence.")
    try:
        result = optimize_separate_breaks(
            setup,
            records,
            target=payload.target_rho,
            max_shift_minutes=payload.max_shift_minutes,
            replications=payload.des.replications,
            base_seed=payload.des.base_seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**result, "setup_hash": _setup_fingerprint(analysis.queue_setup_json), "dataset_id": dataset.id}


BREAK_SETUP_STALE_DETAIL = "Setup changed since this proposal was made. Run the break optimizer again."
BREAK_DATA_STALE_DETAIL = "The data changed since this proposal was made. Run the break optimizer again."
BREAK_NOTHING_DETAIL = "Nothing to apply: no break moves."


@router.post(
    "/{analysis_id}/workflow/optimize/separate/breaks/apply",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def apply_separate_breaks(
    analysis_id: int,
    payload: SeparateBreakApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Write the break optimizer's proposed start times into the Setup.

    Placement (no DES) re-runs on the current Setup and latest valid dataset,
    which must be the ones the proposal was made on. Only each break's
    ``scheduled_start_time`` changes; queue, duration, name, and list order
    stay exactly as configured. Earlier evidence then fails its setup_hash.
    """
    analysis = own_analysis(db, user, analysis_id)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(status_code=422, detail="Break optimization is available for separate queues.")
    if payload.setup_hash != _setup_fingerprint(analysis.queue_setup_json):
        raise HTTPException(status_code=409, detail=BREAK_SETUP_STALE_DETAIL)
    if payload.dataset_id != _current_valid_dataset_id(db, user, analysis):
        raise HTTPException(status_code=409, detail=BREAK_DATA_STALE_DETAIL)
    records = _current_dataset(db, user, analysis).normalized_json or []
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=422, detail="This Analysis has no Current evidence.")
    breaks = list(setup.get("breaks") or [])
    try:
        slots, shifts = slot_inputs_from_setup(setup, records)
        placed = place_breaks(slots, shifts, breaks, [str(q) for q in setup.get("queue_ids") or []],
                              target=payload.target_rho, max_shift_minutes=payload.max_shift_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not placed["moves"]:
        raise HTTPException(status_code=409, detail=BREAK_NOTHING_DETAIL)
    # proposed_breaks is in Setup list order (place_breaks sorts by original index).
    updated = [
        {**entry, "scheduled_start_time": proposed["scheduled_start_time"]} if proposed["shift_minutes"] else entry
        for entry, proposed in zip(breaks, placed["proposed_breaks"], strict=True)
    ]
    try:
        validated = QueueSetup.model_validate({**setup, "breaks": updated})
    except ValueError as exc:  # pragma: no cover - placement keeps valid clock times
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    analysis.queue_setup_json = validated.model_dump(mode="json")
    analysis.setup_status = setup_status(validated)
    analysis.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    return {"analysis": analysis_out(analysis), "moves_applied": len(placed["moves"])}


def _json_number(value: Any) -> float | None:
    """Finite float for API transfer, else None (never NaN/inf, never zero-filled)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sum_all(values: Any) -> float | None:
    """Sum only when every value is present; a single missing value voids the total."""
    nums = [_json_number(value) for value in values]
    if not nums or any(value is None for value in nums):
        return None
    return math.fsum(value for value in nums if value is not None)


# A period's observed wait is flagged only when it is BOTH this many times the
# modeled wait AND at least this many minutes longer (presentation only).
OBSERVED_WAIT_FLAG_RATIO = 2.0
OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES = 5.0


def _observed_wait_summary(
    records: list[Any], validation: dict[str, Any], frame: pd.DataFrame
) -> dict[str, Any]:
    """Per-period modeled vs observed wait (hours) for Current presentation.

    Modeled is the lambda-weighted analytical wait of the period's Current
    rows (the figure Current/Comparison display). Observed comes from the
    persisted event-upload derived_statistics, weighting queues by arrival
    count (lambda x hours x observation days). Aggregate uploads carry no
    statistics, so nothing is observed: never zero-filled. Any statistic that
    does not match a Current record leaves that period's observed wait unknown.
    """
    base = {"ratio": OBSERVED_WAIT_FLAG_RATIO,
            "min_gap_minutes": OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES}
    stats = validation.get("derived_statistics")
    if not isinstance(stats, list) or not stats:
        return {"available": False, "periods": [], "flagged_any": False,
                "day_modeled_wait": None, "day_observed_wait": None, **base}
    days = 1.0
    if validation.get("period_basis") == "representative_day":
        days_value = _json_number(validation.get("observation_days"))
        days = days_value if days_value is not None and days_value > 0 else float("nan")
    lambdas: dict[tuple[str, str | None], Any] = {}
    for record in records:
        if isinstance(record, dict):
            queue = record.get("queue_id")
            lambdas[(str(record.get("time")), queue if isinstance(queue, str) else None)] = record.get("lambda")
    by_period: dict[str, list[tuple[float, float] | None]] = {}
    for stat in stats:
        if not isinstance(stat, dict):
            continue
        label = str(stat.get("time"))
        queue = stat.get("queue_id")
        lam = _json_number(lambdas.get((label, queue if isinstance(queue, str) else None)))
        minutes = _json_number(stat.get("duration_minutes"))
        wait = _json_number(stat.get("mean_waiting_time_hours"))
        entry = None
        if lam is not None and minutes is not None and wait is not None and math.isfinite(days):
            entry = (lam * (minutes / 60.0) * days, wait)
        by_period.setdefault(label, []).append(entry)
    order: list[str] = []
    if not frame.empty and "time" in frame:
        for value in frame["time"]:
            if str(value) not in order:
                order.append(str(value))
    periods = []
    for label in order:
        modeled = _weighted_wait(frame[frame["time"].astype(str) == label])
        entries = by_period.get(label)
        observed = None
        if entries and all(entry is not None for entry in entries):
            pairs = [entry for entry in entries if entry is not None]
            weight = math.fsum(w for w, _ in pairs)
            if weight > 0:
                observed = math.fsum(w * m for w, m in pairs) / weight
        modeled = _json_number(modeled)
        flagged = (
            observed is not None
            and modeled is not None
            and observed > OBSERVED_WAIT_FLAG_RATIO * modeled
            and (observed - modeled) * 60.0 > OBSERVED_WAIT_FLAG_MIN_GAP_MINUTES
        )
        periods.append({"time": label, "modeled_wait": modeled,
                        "observed_wait": observed, "flagged": flagged})
    all_entries = [entry for entries in by_period.values() for entry in entries]
    day_observed = None
    if all_entries and all(entry is not None for entry in all_entries):
        day_pairs = [entry for entry in all_entries if entry is not None]
        day_weight = math.fsum(w for w, _ in day_pairs)
        if day_weight > 0:
            day_observed = math.fsum(w * m for w, m in day_pairs) / day_weight
    return {"available": True, "periods": periods,
            "flagged_any": any(period["flagged"] for period in periods),
            "day_modeled_wait": _json_number(_weighted_wait(frame)) if not frame.empty else None,
            "day_observed_wait": day_observed, **base}


@router.get("/{analysis_id}/workflow/observed-wait")
def observed_wait(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Modeled vs observed Current wait per period (read-only presentation)."""
    analysis = own_analysis(db, user, analysis_id)
    dataset = _current_dataset(db, user, analysis)
    validation = dataset.validation_report_json or {}
    frame, _, _ = analyze_segments(
        dataset.normalized_json or [], analysis.queue_setup_json or {}, validation)
    return {"analysis_id": analysis.id, "dataset_id": dataset.id,
            **_observed_wait_summary(dataset.normalized_json or [], validation, frame)}


@router.get("/{analysis_id}/workflow/comparison/separate")
def separate_comparison(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Compare Current evidence with saved Separate optimal plans.

    Read-only over persisted evidence: the current dataset/setup plus
    immutable schema-v2 schedules. Nothing is reoptimized and no DES, MC,
    or validation runs. Stale or incomplete plans are flagged, never
    silently compared or made selectable by this payload.
    """
    analysis = own_analysis(db, user, analysis_id)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(
            status_code=422,
            detail="Separate comparison requires a separate_queues analysis.",
        )
    dataset = _current_dataset(db, user, analysis)
    records = dataset.normalized_json or []
    frame, _, _ = analyze_segments(records, setup, dataset.validation_report_json or {})
    kpis = compute_kpis(frame)
    observed = _observed_wait_summary(records, dataset.validation_report_json or {}, frame)
    observed_by_time = {period["time"]: period for period in observed["periods"]}
    order: list[str] = []
    grouped: dict[str, list] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        label = str(row.get("time", row.get("segment_id", "Unknown")))
        grouped.setdefault(label, []).append(row)
        if label not in order:
            order.append(label)
    current_periods = []
    for label in order:
        sub = frame[frame["time"] == label] if not frame.empty else frame
        lambdas = [_json_number(row.get("lambda")) for _, row in sub.iterrows()]
        finite_lambdas = [value for value in lambdas if value is not None]
        rhos = [_json_number(row.get("rho")) for _, row in sub.iterrows()]
        finite_rhos = [value for value in rhos if value is not None]
        current_periods.append({
            "time": label,
            "active_lanes": _period_current_active(setup, grouped[label]),
            "lambda_total": math.fsum(finite_lambdas) if finite_lambdas else None,
            "wait_mean": _weighted_wait(sub),
            "observed_wait": (observed_by_time.get(label) or {}).get("observed_wait"),
            "observed_flag": bool((observed_by_time.get(label) or {}).get("flagged")),
            "util_max": max(finite_rhos) if finite_rhos else None,
        })
    plans = []
    items = db.execute(
        select(Scenario)
        .where(Scenario.user_id == user.id, Scenario.analysis_id == analysis.id)
        .order_by(Scenario.id.asc())
    ).scalars()
    for scenario in items:
        calc = (scenario.settings_json or {}).get("calculation") or {}
        if calc.get("schema_version") != 2:
            plans.append({
                "scenario_id": scenario.id, "name": scenario.name,
                "dataset_id": scenario.dataset_id, "target": None,
                "evaluation_method": None, "replications": None, "base_seed": None,
                "overall": None, "stale": scenario.dataset_id != dataset.id,
                "wait_basis_kind": None,
                "valid": False, "valid_reason": "not a Separate optimization snapshot",
                "periods": [], "totals": None,
            })
            continue
        schedule = (scenario.results_json or {}).get("schedule") or {}
        setup_problem = _scenario_setup_problem(scenario, analysis)
        stale = scenario.dataset_id != dataset.id or setup_problem is not None
        problem = _separate_schedule_problem(scenario)
        if setup_problem is not None:
            problem = setup_problem
        if scenario.dataset_id != dataset.id:
            problem = "stale for the current dataset"
        detail_periods = []
        for period in schedule.get("periods") or []:
            if not isinstance(period, dict):
                continue
            optimum = period.get("optimum") or {}
            evidence = optimum.get("evidence") or {}
            waiting = evidence.get("waiting_time") or {}
            total = (evidence.get("costs") or {}).get("total") or {}
            waiting_cost = (evidence.get("costs") or {}).get("waiting") or {}
            detail_periods.append({
                "time": period.get("time"),
                "current_active_lanes": period.get("current_active_lanes"),
                "optimal_active_lanes": period.get("optimal_active_lanes"),
                "adjustment": period.get("adjustment"),
                "peak_util": _json_number(optimum.get("candidate_utilization")),
                "wait_mean": _json_number(waiting.get("mean")),
                "wait_ci": ([_json_number(waiting.get("ci_lower")),
                             _json_number(waiting.get("ci_upper"))]
                            if waiting.get("ci_lower") is not None
                            or waiting.get("ci_upper") is not None else None),
                "waiting_cost_mean": _json_number(waiting_cost.get("mean")),
                "total_cost_mean": _json_number(total.get("mean")),
                "total_cost_ci": ([_json_number(total.get("ci_lower")),
                                   _json_number(total.get("ci_upper"))]
                                  if total.get("ci_lower") is not None
                                  or total.get("ci_upper") is not None else None),
                "status": period.get("overall"),
            })
        weights = []
        for period, detail in zip(schedule.get("periods") or [], detail_periods):
            evidence = ((period.get("optimum") or {}).get("evidence") or {}) if isinstance(period, dict) else {}
            weights.append(_json_number(evidence.get("total_lambda")))
        lane_ints = [v for v in (d["optimal_active_lanes"] for d in detail_periods)
                     if isinstance(v, int) and not isinstance(v, bool)]
        lane_total = (math.fsum(lane_ints)
                      if detail_periods and len(lane_ints) == len(detail_periods) else None)
        weighted: list[tuple[float, float]] = []
        for weight, detail in zip(weights, detail_periods):
            w = _json_number(weight)
            m = _json_number(detail["wait_mean"])
            if w is not None and m is not None:
                weighted.append((w, m))
        wait_denom = math.fsum(w for w, _ in weighted)
        wait_mean = (math.fsum(w * m for w, m in weighted) / wait_denom
                     if wait_denom > 0 else None)
        peaks = [p for p in (_json_number(d["peak_util"]) for d in detail_periods)
                 if p is not None]
        totals = {
            "lane_periods": lane_total,
            "wait_mean": wait_mean,
            "peak_util": max(peaks) if peaks else None,
            "waiting_cost_mean": _sum_all(d["waiting_cost_mean"] for d in detail_periods),
            "total_cost_mean": _sum_all(d["total_cost_mean"] for d in detail_periods),
        }
        des = schedule.get("des") or {}
        plans.append({
            "scenario_id": scenario.id, "name": scenario.name,
            "dataset_id": scenario.dataset_id,
            "target": _json_number((calc.get("options") or {}).get(
                "target_utilization", (scenario.settings_json or {}).get("target_utilization"))),
            "evaluation_method": schedule.get("evaluation_method"),
            "replications": des.get("replications"),
            "base_seed": des.get("base_seed"),
            "overall": schedule.get("overall"),
            "wait_basis_kind": "simulation",
            "stale": stale,
            "valid": problem is None,
            "valid_reason": problem,
            "periods": detail_periods,
            "totals": totals,
        })
    selection = _latest_job(db, user, "workflow_selection", analysis.id)
    selected_id = (selection.params_json or {}).get("scenario_id") if selection else None
    return {
        "analysis_id": analysis.id,
        "queue_structure": "separate_queues",
        "current": {
            "dataset_id": dataset.id,
            "periods": current_periods,
            "wait_mean": _json_number(kpis.get("avg_waiting_time")),
            "wait_basis": "lambda-weighted analytical mean over Current rows",
            "wait_basis_kind": "analytical",
            "observed_wait_available": observed["available"],
            "observed_wait_flagged_any": observed["flagged_any"],
            "observed_wait_ratio": observed["ratio"],
            "observed_wait_min_gap_minutes": observed["min_gap_minutes"],
            "util_max": _json_number(kpis.get("max_utilization")),
            "waiting_cost": _json_number(kpis.get("total_waiting_cost")),
            "waiting_cost_basis": "Lq-based Current basis; excludes server cost",
            "total_cost": None,
            "total_cost_reason": "Current evidence has no server-cost basis; savings are not computed.",
        },
        "plans": plans,
        "selected_scenario_id": selected_id if isinstance(selected_id, int) else None,
    }


class SelectedDesRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    seed: int | None = 42
    # Paired replications whose mean routed arrivals set the Monte Carlo
    # lane loads (bounded like the break optimizer's DES replications).
    load_replications: StrictInt = Field(default=20, ge=1, le=20)


class SelectedPlanError(ValueError):
    """Selected-plan simulation cannot be built or executed honestly."""


def _selected_schedule_options(scenario: Scenario) -> dict[str, Any]:
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    options = snapshot.get("options") or {}
    if not isinstance(options, dict):
        raise SelectedPlanError("Selected scenario has no optimization options.")
    return options


def _require_selected_separate_plan(
    db: Session, user: User, analysis: AnalysisProject
) -> dict[str, Any]:
    """Resolve the selected schema-v2 plan into runnable simulation inputs.

    The selection job points at exactly one scenario; that scenario must
    verify (complete, current dataset) and its persisted per-period active
    lane IDs must resolve against the CURRENT setup. Anything else blocks
    with an exact reason — never a silent substitution.
    """
    selection = _latest_job(db, user, "workflow_selection", analysis.id)
    if selection is None:
        raise HTTPException(
            status_code=409,
            detail="Select a saved optimal plan in Comparison before running optimized simulation.",
        )
    scenario_id = (selection.params_json or {}).get("scenario_id")
    if not isinstance(scenario_id, int):
        raise HTTPException(
            status_code=409,
            detail="Select a saved optimal plan in Comparison before running optimized simulation.",
        )
    try:
        scenario = _own_verified_scenario(db, user, analysis, scenario_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"Selected plan is not runnable: {exc.detail}",
        ) from exc
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") != "separate_queues":
        raise SelectedPlanError("Selected-plan simulation requires a separate_queues analysis.")
    if setup.get("separate_queue_closure_policy", "drain_existing") != "drain_existing":
        raise SelectedPlanError("Selected-plan simulation requires the drain_existing closure policy.")
    configured = {str(queue_id) for queue_id in setup.get("queue_ids", [])}
    schedule = (scenario.results_json or {}).get("schedule") or {}
    for period in schedule.get("periods") or []:
        optimum = (period or {}).get("optimum") or {}
        active = optimum.get("active_queue_ids") or []
        if len(active) != optimum.get("active_lane_count"):
            raise SelectedPlanError(
                f"Period {period.get('time', '?')} active IDs do not match its optimal lane count.")
        unknown = [queue_id for queue_id in active if str(queue_id) not in configured]
        if unknown:
            raise SelectedPlanError(
                f"Period {period.get('time', '?')} references lanes missing from the current "
                f"setup: {', '.join(str(q) for q in unknown)}. The setup changed since saving.")
    dataset = db.get(Dataset, scenario.dataset_id)
    options = _selected_schedule_options(scenario)
    try:
        multiplier = float(options.get("lambda_multiplier", 1.0))
        des_config = validate_des_replication_config(options.get("des") or {})
        target = options.get("target_utilization")
        server_cost = float(options.get("server_cost_per_hr", DEFAULT_SERVER_COST_HR))
        waiting_cost = float(options.get("customer_waiting_cost", DEFAULT_WAIT_COST_HR))
    except (TypeError, ValueError) as exc:
        raise SelectedPlanError(f"Selected scenario options are invalid: {exc}") from exc
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise SelectedPlanError("Selected scenario demand multiplier is invalid.")
    return {
        "scenario": scenario,
        "schedule": schedule,
        "dataset": dataset,
        "setup": setup,
        "options": options,
        "target": target,
        "server_cost": server_cost,
        "waiting_cost": waiting_cost,
        "multiplier": multiplier,
        "duration_hours": des_config["duration_hours"],
        "max_events": des_config["max_events"],
    }


def _run_selected_plan_des(plan: dict[str, Any], seed: int | None,
                           execute=None) -> dict[str, Any]:
    """Execute each persisted period optimum independently (period-independent
    semantics, matching the optimizer's evidence model: no carryover, no
    cross-period transitions, empty queues at each period start).

    Reuses the proven single-run routing DES evaluator per period — same
    conserved arrivals, same live-system-size routing with seeded fair ties,
    same empirical service sampling. No optimizer calls.

    Representative-day analyses run one continuous day instead
    (``_run_selected_plan_day_des``) with the same output shape.
    """
    if execute is None and (plan.get("setup") or {}).get("event_period_basis") == "representative_day":
        return _run_selected_plan_day_des(plan, seed)
    executor = execute or evaluate_candidate_with_des
    scenario = plan["scenario"]
    schedule = plan["schedule"]
    records = plan["dataset"].normalized_json or []
    try:
        des_breaks = resolve_des_breaks(plan.get("setup"))
    except ValueError as exc:
        raise SelectedPlanError(str(exc)) from exc
    periods_out: list[dict[str, Any]] = []
    all_conserved = True
    for index, sched_period in enumerate(schedule.get("periods") or []):
        time_label = str(sched_period.get("time", f"period_{index + 1}"))
        optimum = sched_period.get("optimum") or {}
        active = [str(queue_id) for queue_id in (optimum.get("active_queue_ids") or [])]
        inactive = [str(queue_id) for queue_id in (optimum.get("inactive_queue_ids") or [])]
        by_id = index_period_queues(records, time_label)
        try:
            period_breaks = (period_des_breaks(plan.get("setup"), list(by_id.values()))
                             if des_breaks is not None else None)
        except ValueError as exc:
            raise SelectedPlanError(str(exc)) from exc
        queues_by_id: dict[str, dict] = {}
        for queue_id in active + inactive:
            row = by_id.get(queue_id)
            if row is None:
                raise SelectedPlanError(
                    f"Missing dataset evidence for {time_label}/{queue_id}.")
            scaled = dict(row)
            try:
                lam = float(row.get("lambda", 0.0)) * plan["multiplier"]
            except (TypeError, ValueError) as exc:
                raise SelectedPlanError(
                    f"Invalid arrival rate for {time_label}/{queue_id}.") from exc
            if not math.isfinite(lam) or lam < 0:
                raise SelectedPlanError(
                    f"Invalid arrival rate for {time_label}/{queue_id}.")
            scaled["lambda"] = lam
            queues_by_id[queue_id] = scaled
        seg_seed = (seed + index) if seed is not None else None
        candidate: dict[str, Any] = {"time": time_label, "available_queue_ids": active + inactive,
                                     "active_queue_ids": active, "inactive_queue_ids": inactive}
        if period_breaks is not None:
            candidate["breaks"] = period_breaks
        result = executor(
            candidate,
            queues_by_id, duration_hours=plan["duration_hours"], seed=seg_seed,
            target=plan["target"], server_cost=plan["server_cost"],
            waiting_cost=plan["waiting_cost"], max_events=plan["max_events"])
        if result.get("status") in ("INVALID_INPUT", "UNSUPPORTED"):
            raise SelectedPlanError(
                f"Period {time_label} cannot be simulated: {result.get('reason')}")
        if result.get("status") not in ("FEASIBLE", "INFEASIBLE"):
            raise SelectedPlanError(
                f"Period {time_label} returned unexpected status {result.get('status')!r}.")
        conserved = result.get("customer_conservation") is True
        all_conserved = all_conserved and conserved
        evaluations = result.get("evaluations") or []
        lane_rows = []
        for item in evaluations:
            lane_rows.append({
                "time": time_label,
                "queue_id": item.get("queue_id"),
                "server_id": item.get("server_id"),
                "lambda": _json_number(item.get("lambda")),
                "lambda_routed": _json_number(item.get("lambda_routed_sim")),
                "mu": _json_number(item.get("mu")),
                "c": 1,
                "arrivals": item.get("arrivals"),
                "served": item.get("served"),
                "waiting": item.get("waiting"),
                "in_service": item.get("in_service"),
                "abandoned": None,
                "Wq_sim": _json_number(item.get("Wq")),
                "rho_sim": _json_number(item.get("rho")),
                "max_queue": item.get("max_queue"),
                "active": bool(item.get("active")),
                "simulation_supported": True,
                "error": None,
                "metric_provenance": "simulated",
                "customer_conservation": conserved,
            })
        events = result.get("trace_events") or []
        lane_segments = []
        for item in evaluations:
            lane_segments.append({
                "segment_id": f"{time_label}:{item.get('queue_id')}",
                "time": time_label,
                "queue_id": item.get("queue_id"),
                "lambda": _json_number(item.get("lambda")),
                "mu": _json_number(item.get("mu")),
                "c": 1,
                "selected_model": "Parallel M/G/1 (routing)",
                "simulation_supported": True,
                "error": None,
                "queue_structure": "separate",
                "initial_queue_depth": 0,
                "final_queue_depth": item.get("waiting"),
                "server_id": item.get("server_id"),
            })
        periods_out.append({
            "time": time_label,
            "active_queue_ids": active,
            "inactive_queue_ids": inactive,
            "evaluation_status": result.get("status"),
            "conservation": conserved,
            "total_lambda": _json_number(result.get("total_lambda")),
            "total_cost": _json_number(result.get("total_cost")),
            "server_cost": _json_number(result.get("server_cost")),
            "waiting_cost": _json_number(result.get("waiting_cost")),
            "results": lane_rows,
            "trace": {
                "results": lane_rows,
                "trace": events,
                "trace_hours": plan["duration_hours"],
                "total_hours": plan["duration_hours"],
                "event_count": len(events),
                "truncated": bool(result.get("trace_truncated")),
                "abandonment_supported": False,
                "segments": lane_segments,
            },
        })
    return {
        "provenance": "SELECTED",
        "engine_version": ENGINE_VERSION,
        "execution": "selected-plan routing DES (period-independent, no carryover)",
        "arrival_method": "single conserved Poisson stream at total lambda",
        "routing_policy": "shortest system size with seeded fair ties",
        "service_sampling_method": "empirical per-lane resampling",
        "scenario_id": scenario.id,
        "analysis_id": scenario.analysis_id,
        "dataset_id": scenario.dataset_id,
        "target_utilization": plan["target"],
        "seed": seed,
        "duration_hours": plan["duration_hours"],
        "max_events": plan["max_events"],
        "periods": periods_out,
        "overall_conservation": all_conserved,
        "overall_status": "COMPLETED" if all_conserved else "ERROR",
    }


@router.post(
    "/{analysis_id}/workflow/simulation/des/selected",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_selected_des(
    analysis_id: int,
    payload: SelectedDesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Run routing-capable DES for the selected immutable Separate plan.

    One request executes the whole persisted schedule (period-independent).
    No optimizer, ranking, or candidate search runs here.
    """
    analysis = own_analysis(db, user, analysis_id)
    try:
        plan = _require_selected_separate_plan(db, user, analysis)
        result = _run_selected_plan_des(plan, payload.seed)
        _attach_mean_routed_loads(plan, payload.seed, payload.load_replications, result)
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = plan["scenario"]
    job = _save_job(
        db, user, "workflow_des", analysis, scenario,
        {"seed": payload.seed, "engine": "selected-plan-routing-des",
         "periods": len(result["periods"]),
         "load_replications": payload.load_replications},
        result, settings,
    )
    return {"evidence": _job_out(job)}


def _attach_mean_routed_loads(plan: dict[str, Any], seed: int | None, count: int,
                              stored: dict[str, Any]) -> None:
    """Add each lane's mean routed arrivals over ``count`` paired replications.

    Replication 0 is ``stored`` itself (its trace and playback stay exactly as
    produced); the rest rerun the same plan with the next seeds of
    ``replication_seeds``. A lane absent from a run received no arrivals there.
    Only ``results`` rows gain ``arrivals_mean``/``lambda_routed_mean`` (as
    copies); the stored trace payload is untouched.
    """
    seeds: list[int | None] = (list(replication_seeds(seed, count)) if seed is not None
                               else [None] * count)
    runs = [stored] + [_run_selected_plan_des(plan, extra) for extra in seeds[1:]]
    totals: dict[tuple[str, str], float] = {}
    for run in runs:
        for period in run.get("periods") or []:
            for row in period.get("results") or []:
                key = (str(period.get("time")), str(row.get("queue_id")))
                totals[key] = totals.get(key, 0.0) + float(row.get("arrivals") or 0)
    for period in stored.get("periods") or []:
        duration = period.get("duration_hours") or stored.get("duration_hours") or 0.0
        rows = []
        for row in period.get("results") or []:
            mean = totals.get((str(period.get("time")), str(row.get("queue_id"))), 0.0) / len(runs)
            rows.append({**row, "arrivals_mean": mean,
                         "lambda_routed_mean": (mean / duration) if duration > 0 else None})
        period["results"] = rows
    stored["load_replications"] = {
        "count": count,
        "seeds": seeds,
        "basis": f"mean routed arrivals over {count} paired DES replications",
    }


def _run_selected_plan_day_des(plan: dict[str, Any], seed: int | None) -> dict[str, Any]:
    """Execute the selected representative-day plan as one continuous day.

    Periods map to their configured operating segments on the DES clock
    (origin = earliest segment start); each period activates its persisted
    optimum lanes; breaks come from the setup at their wall-clock offsets.
    Lane rows keep the period-independent output shape; costs are not
    computed in this mode and stay null.
    """
    scenario = plan["scenario"]
    setup = plan.get("setup") or {}
    records = plan["dataset"].normalized_json or []
    try:
        des_breaks = resolve_des_breaks(setup)
        origin = des_day_start_minutes(setup)
        windows_by_key = {key: (low, high) for key, low, high in
                          (_segment_window(seg) for seg in setup.get("segments") or []
                           if isinstance(seg, dict))}
    except ValueError as exc:
        raise SelectedPlanError(str(exc)) from exc
    if origin is None:
        raise SelectedPlanError("A representative day needs configured operating segments.")
    windows: list[dict[str, Any]] = []
    for sched_period in plan["schedule"].get("periods") or []:
        label = str(sched_period.get("time"))
        if label not in windows_by_key:
            raise SelectedPlanError(f"Period {label} does not match a configured operating segment.")
        low, high = windows_by_key[label]
        queues = {}
        for queue_id, row in index_period_queues(records, label).items():
            scaled = dict(row)
            scaled["lambda"] = float(row.get("lambda") or 0.0) * plan["multiplier"]
            queues[queue_id] = scaled
        windows.append({
            "time": label, "start_hours": (low - origin) / 60.0, "end_hours": (high - origin) / 60.0,
            "active_queue_ids": [str(q) for q in ((sched_period.get("optimum") or {})
                                                  .get("active_queue_ids") or [])],
            "queues_by_id": queues,
        })
    tie_order = [str(q) for q in setup.get("queue_ids", [])]
    try:
        day = run_routing_day_des(windows, tie_order=tie_order, seed=seed,
                                  max_events=plan["max_events"], breaks=des_breaks)
    except ValueError as exc:
        raise SelectedPlanError(str(exc)) from exc
    conserved = day["customer_conservation"] is True
    periods_out = []
    for window, period in zip(sorted(windows, key=lambda w: w["start_hours"]), day["periods"]):
        label = period["time"]
        lane_rows = []
        for lane in period["lanes"]:
            if not lane["active"] and not lane["arrivals"]:
                continue
            lane_rows.append({
                "time": label, "queue_id": lane["queue_id"], "server_id": lane["server_id"],
                "lambda": _json_number(lane["lambda"]),
                "lambda_routed": _json_number(lane["lambda_routed_sim"]),
                "mu": None, "c": 1, "arrivals": lane["arrivals"], "served": lane["served"],
                "waiting": None, "in_service": None, "abandoned": None,
                "Wq_sim": _json_number(lane["Wq"]), "rho_sim": _json_number(lane["rho"]),
                "max_queue": lane["max_queue"], "active": bool(lane["active"]),
                "simulation_supported": True, "error": None,
                "metric_provenance": "simulated", "customer_conservation": conserved,
            })
        events = [e for e in day["trace_events"] if e.get("segment_id") == label]
        periods_out.append({
            "time": label,
            "active_queue_ids": window["active_queue_ids"],
            "inactive_queue_ids": [q for q in tie_order if q not in window["active_queue_ids"]],
            "evaluation_status": "FEASIBLE" if conserved else "ERROR",
            "conservation": conserved,
            "duration_hours": period["duration_hours"],
            "total_lambda": _json_number(sum(float(r["lambda"] or 0.0) for r in lane_rows)),
            "total_cost": None, "server_cost": None, "waiting_cost": None,
            "results": lane_rows,
            "trace": {
                "results": lane_rows, "trace": events,
                "trace_hours": period["duration_hours"], "total_hours": day["day_hours"],
                "event_count": len(events), "truncated": bool(day["trace_truncated"]),
                "abandonment_supported": False,
                "segments": [{"segment_id": f"{label}:{r['queue_id']}", "time": label,
                              "queue_id": r["queue_id"], "lambda": r["lambda"], "mu": None, "c": 1,
                              "selected_model": "Parallel M/G/1 (routing)",
                              "simulation_supported": True, "error": None,
                              "queue_structure": "separate", "initial_queue_depth": None,
                              "final_queue_depth": None, "server_id": r["server_id"]}
                             for r in lane_rows],
            },
        })
    return {
        "provenance": "SELECTED",
        "engine_version": ENGINE_VERSION,
        "execution": "selected-plan continuous-day routing DES (queues and breaks carry across periods)",
        "arrival_method": "Poisson stream per period at the period's total lambda",
        "routing_policy": "shortest system size with seeded fair ties",
        "service_sampling_method": "empirical per-lane resampling for the arrival period",
        "scenario_id": scenario.id,
        "analysis_id": scenario.analysis_id,
        "dataset_id": scenario.dataset_id,
        "target_utilization": plan["target"],
        "seed": seed,
        "duration_hours": day["day_hours"],
        "max_events": plan["max_events"],
        "periods": periods_out,
        "admitted": day["admitted"],
        "served": day["served"],
        "overall_conservation": conserved,
        "overall_status": "COMPLETED" if conserved else "ERROR",
    }


def _selected_mc_segments(plan: dict[str, Any], des_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Monte Carlo lane segments at DES-measured operating points.

    Each active lane is evaluated at its mean simulated routed throughput
    over the DES evidence's paired load replications, with service moments
    from its empirical samples — the same Parallel M/G/1
    mathematics as Current MC, applied to the selected schedule's measured
    loads. Inactive lanes have no arrivals and are not evaluated.
    """
    records = plan["dataset"].normalized_json or []
    segments: list[dict[str, Any]] = []
    for period in des_result.get("periods") or []:
        time_label = str(period.get("time", "Unknown"))
        by_id = index_period_queues(records, time_label)
        for row in period.get("results") or []:
            if not row.get("active"):
                continue
            queue_id = row.get("queue_id")
            samples = (by_id.get(str(queue_id)) or {}).get("service_samples_hours") or []
            clean = [float(sample) for sample in samples
                     if isinstance(sample, (int, float)) and not isinstance(sample, bool)
                     and math.isfinite(float(sample)) and float(sample) > 0]
            if not clean:
                raise SelectedPlanError(
                    f"Missing service samples for Monte Carlo lane {time_label}/{queue_id}.")
            mean_service = math.fsum(clean) / len(clean)
            mean_load = _json_number(row.get("lambda_routed_mean"))
            if mean_load is None:
                raise SelectedPlanError(
                    f"Missing mean routed load for Monte Carlo lane {time_label}/{queue_id}.")
            segments.append({
                "time": time_label,
                "queue_id": queue_id,
                "lambda": mean_load,
                "mu": 1.0 / mean_service,
                "variance": statistics.variance(clean) if len(clean) >= 2 else 0.0,
                "c": 1,
                "queue_structure": "separate_queues",
            })
    return segments


@router.post(
    "/{analysis_id}/workflow/simulation/mc/selected",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_selected_mc(
    analysis_id: int,
    payload: SelectedMcRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Run Monte Carlo for the selected plan at its DES-measured loads.

    Requires a selected-plan DES run for the same scenario first; the MC
    lanes, loads, and identity all derive from that evidence. Existing MC
    trial/threshold/CI semantics are reused unchanged.
    """
    analysis = own_analysis(db, user, analysis_id)
    try:
        plan = _require_selected_separate_plan(db, user, analysis)
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = plan["scenario"]
    des_job = _latest_job(db, user, "workflow_des", analysis.id, scenario.id)
    if des_job is None:
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan DES before Monte Carlo for this scenario.",
        )
    des_params = des_job.params_json or {}
    if des_params.get("engine") != "selected-plan-routing-des":
        raise HTTPException(
            status_code=409,
            detail="Latest DES evidence is not a selected-plan run for this scenario.",
        )
    _require_setup_current(analysis, des_job)
    load = (des_job.result_json or {}).get("load_replications")
    if not isinstance(load, dict) or not isinstance(load.get("count"), int):
        raise HTTPException(
            status_code=409,
            detail="Selected-plan DES evidence has no mean routed loads. Rerun selected-plan DES.",
        )
    target = _json_number(plan["target"])
    if "failure_threshold" in payload.model_fields_set and payload.failure_threshold is not None:
        failure_threshold, threshold_source = float(payload.failure_threshold), "user"
    elif target is not None and 0 < target <= 1:
        failure_threshold, threshold_source = target, "plan_target"
    else:
        failure_threshold, threshold_source = MC_DEFAULT_FAILURE_THRESHOLD, "default"
    try:
        segments = _selected_mc_segments(plan, des_job.result_json or {})
        rows = mc_simulate_segments(
            segments,
            num_trials=payload.num_trials,
            failure_threshold=failure_threshold,
            seed=payload.seed,
            failure_rate_cap=payload.failure_rate_cap,
        )
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = {
        "provenance": "SELECTED",
        "engine_version": ENGINE_VERSION,
        "method": "analytical parameter perturbation at DES-measured lane loads",
        "scenario_id": scenario.id,
        "analysis_id": analysis.id,
        "dataset_id": scenario.dataset_id,
        "des_job_id": des_job.id,
        "results": rows,
    }
    job = _save_job(
        db, user, "workflow_mc", analysis, scenario,
        {**payload.model_dump(), "des_job_id": des_job.id,
         "engine": "selected-plan-measured-mc",
         "failure_threshold": failure_threshold,
         "failure_threshold_source": threshold_source,
         "load_replications": load["count"],
         "load_seeds": load.get("seeds"),
         "lambda_basis": load.get("basis")},
        result, settings,
    )
    return {"evidence": _job_out(job)}


def validate_selected_plan(schedule: dict[str, Any], des_result: dict[str, Any],
                           mc_rows: list[dict[str, Any]], failure_cap: float) -> dict[str, Any]:
    """Validate a selected plan from persisted DES and MC evidence only.

    Required evidence derives from the schedule's persisted active lane IDs
    per period — never from array positions or regenerated subsets. Each
    period reuses the verified FAIL > insufficient > pass verdict over its
    (time, queue_id) pairs; DES runs that are unconserved or unevaluable
    make their period insufficient (errored evidence, never a pass). The
    overall verdict applies the same precedence across all required pairs,
    so one failing period or lane can never be averaged away.
    """
    sched_periods = schedule.get("periods") or []
    des_by_time = {str(p.get("time")): p for p in (des_result.get("periods") or [])
                   if isinstance(p, dict)}
    mc_by_pair = {(str(row.get("time", "")), str(row.get("queue_id", ""))): row
                  for row in mc_rows or []
                  if isinstance(row, dict) and isinstance(row.get("queue_id"), str)}
    periods_out: list[dict[str, Any]] = []
    required_pairs: list[tuple[str, str]] = []
    overall_mc: dict[tuple[str, str], dict[str, Any]] = {}
    for sched in sched_periods:
        if not isinstance(sched, dict):
            continue
        time_label = str(sched.get("time", "Unknown"))
        optimum = sched.get("optimum") or {}
        active = [str(q) for q in (optimum.get("active_queue_ids") or [])]
        des_period = des_by_time.get(time_label)
        des_lanes = {(str(item.get("queue_id"))): item
                     for item in ((des_period or {}).get("results") or [])
                     if isinstance(item, dict)}
        des_ok = (
            des_period is not None
            and des_period.get("conservation") is True
            and all(q in des_lanes and des_lanes[q].get("simulation_supported") is True
                    for q in active)
        )
        des_reason = None
        if des_period is None:
            des_reason = "No selected-plan DES evidence for this period."
        elif des_period.get("conservation") is not True:
            des_reason = "Selected-plan DES evidence failed customer conservation."
        elif not des_ok:
            des_reason = "Selected-plan DES evidence is missing active lanes."
        pairs = [(time_label, q) for q in active]
        required_pairs.extend(pairs)
        if des_ok:
            verdict = _separate_validation_verdict(pairs, mc_by_pair, failure_cap)
            overall_mc.update({key: mc_by_pair[key] for key in pairs if key in mc_by_pair})
        else:
            verdict = {"status": "insufficient", "failed": [], "inadequate": list(pairs),
                       "total": len(pairs), "results": []}
        queue_rows = []
        for item in verdict.pop("results"):
            lane = des_lanes.get(item["queue_id"], {})
            queue_rows.append({
                **item,
                "rho_sim": _json_number(lane.get("rho_sim")),
                "Wq_sim": _json_number(lane.get("Wq_sim")),
                "served": lane.get("served"),
            })
        periods_out.append({
            "time": time_label,
            "active_queue_ids": active,
            "status": verdict["status"],
            "des_ok": des_ok,
            "des_reason": des_reason,
            "queues": queue_rows,
        })
    overall = _separate_validation_verdict(required_pairs, overall_mc, failure_cap)
    return {"periods": periods_out, "verdict": overall}


@router.post(
    "/{analysis_id}/workflow/simulation/validation/selected",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def run_selected_validation(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Validate the selected plan from its persisted DES and MC evidence.

    Consumes only evidence already persisted for exactly the selected
    scenario: the DES job, the MC job derived from that DES job, and the
    immutable schedule. Nothing is re-optimized, rerun, or recomputed.
    """
    analysis = own_analysis(db, user, analysis_id)
    try:
        plan = _require_selected_separate_plan(db, user, analysis)
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = plan["scenario"]
    des_job = _latest_job(db, user, "workflow_des", analysis.id, scenario.id)
    if des_job is None or (des_job.params_json or {}).get("engine") != "selected-plan-routing-des":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan DES before validating this scenario.",
        )
    mc_job = _latest_job(db, user, "workflow_mc", analysis.id, scenario.id)
    if mc_job is None or (mc_job.params_json or {}).get("engine") != "selected-plan-measured-mc":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Monte Carlo before validating this scenario.",
        )
    if (mc_job.params_json or {}).get("des_job_id") != des_job.id:
        raise HTTPException(
            status_code=409,
            detail="Monte Carlo evidence is stale for the latest selected-plan DES. Rerun Monte Carlo.",
        )
    _require_setup_current(analysis, des_job, mc_job)
    failure_cap = (mc_job.params_json or {}).get("failure_rate_cap")
    if (
        not isinstance(failure_cap, (int, float))
        or isinstance(failure_cap, bool)
        or not math.isfinite(float(failure_cap))
    ):
        raise HTTPException(
            status_code=422,
            detail="Selected Monte Carlo evidence has no usable failure cap.",
        )
    des_result = des_job.result_json or {}
    mc_rows = ((mc_job.result_json or {}).get("results") or [])
    outcome = validate_selected_plan(
        plan["schedule"], des_result, mc_rows, float(failure_cap))
    result = {
        "provenance": "SELECTED",
        "engine_version": ENGINE_VERSION,
        "scenario_id": scenario.id,
        "analysis_id": analysis.id,
        "dataset_id": scenario.dataset_id,
        "des_job_id": des_job.id,
        "mc_job_id": mc_job.id,
        "failure_rate_cap": float(failure_cap),
        "periods": outcome["periods"],
        "verdict": outcome["verdict"],
    }
    job = _save_job(
        db, user, "workflow_validation", analysis, scenario,
        {"des_job_id": des_job.id, "mc_job_id": mc_job.id,
         "failure_rate_cap": float(failure_cap)},
        result, settings,
    )
    return {"evidence": _job_out(job)}


def _derive_selected_decision(*, scenario: dict[str, Any], schedule: dict[str, Any],
                              des_result: dict[str, Any],
                              validation_result: dict[str, Any],
                              failure_cap: float) -> dict[str, Any]:
    """Decide a selected Separate plan from persisted evidence only.

    Rule table (from the frozen shared Decision semantics):
      missing/inconsistent evidence            -> INSUFFICIENT EVIDENCE
      validation FAIL                          -> REVISE (failed periods listed)
      validation INSUFFICIENT                  -> INSUFFICIENT EVIDENCE
      validation PASS + conserved DES          -> CONDITIONAL, because the
        adopt/conditional split keys off modeled savings and Separate plans
        have no comparable Current cost basis. ADOPT is unreachable until
        such a basis exists; this is stated in the rationale, never hidden.
    A validation PASS paired with unconserved DES is an evidence
    inconsistency, never a success. Staffing counts are described, never
    recomputed; no replacement schedule is produced.
    """
    name = scenario.get("name", "Unnamed plan")
    periods = schedule.get("periods") or []
    verdict = validation_result.get("verdict") or {}
    status = verdict.get("status")
    failed = verdict.get("failed") or []
    inadequate = verdict.get("inadequate") or []
    total = verdict.get("total")
    failed_times = sorted({str(pair[0]) for pair in failed
                           if isinstance(pair, (list, tuple)) and pair})
    inadequate_times = sorted({str(pair[0]) for pair in inadequate
                               if isinstance(pair, (list, tuple)) and pair})
    lane_delta: int | None = None
    deltas = []
    for period in periods:
        optimal = period.get("optimal_active_lanes")
        current = period.get("current_active_lanes")
        if isinstance(optimal, int) and isinstance(current, list):
            deltas.append(optimal - len(current))
    if deltas and len(deltas) == len(periods):
        lane_delta = sum(deltas)
    facts = {
        "selected_target": schedule.get("target_utilization"),
        "validation_checks": total,
        "failed_checks": len(failed),
        "inadequate_checks": len(inadequate),
        "failure_rate_cap": failure_cap,
        "lane_delta": lane_delta,
        "periods": len(periods),
    }
    base = {
        "scenario_id": scenario.get("id"),
        "scenario_name": name,
        "dataset_id": scenario.get("dataset_id"),
        "facts": facts,
        "failed_periods": failed_times,
        "inadequate_periods": inadequate_times,
        "provenance": "SELECTED",
        "provenance_warning": (
            "Analytical estimates and simulated results are decision support, "
            "not observed future outcomes."
        ),
    }
    conserved = des_result.get("overall_conservation") is True
    if not conserved:
        return {
            **base,
            "status": "insufficient_evidence",
            "headline": "Insufficient evidence to make a management recommendation.",
            "recommendation": (
                "Selected-plan DES evidence failed customer conservation; "
                "validation cannot be trusted. Rerun Simulation before deciding."
            ),
            "rationale": [
                f"Selected Scenario: {name} (ID {scenario.get('id')}).",
                "DES customer conservation failed: evidence is inconsistent.",
            ],
            "missing_evidence": ["trustworthy DES evidence with customer conservation"],
        }
    if status not in ("pass", "fail", "insufficient"):
        return {
            **base,
            "status": "insufficient_evidence",
            "headline": "Insufficient evidence to make a management recommendation.",
            "recommendation": "Complete the missing workflow evidence before making an adoption decision.",
            "rationale": [
                f"Selected Scenario: {name} (ID {scenario.get('id')}).",
                f"Validation verdict is missing or unrecognized: {status!r}.",
            ],
            "missing_evidence": ["a completed Scenario Validation run"],
        }
    if status == "fail":
        passed = total - len(failed) if isinstance(total, int) else None
        return {
            **base,
            "status": "revise",
            "headline": f'Do not adopt Scenario "{name}" yet.',
            "recommendation": (
                f"Revise and re-test the plan because {len(failed)} of "
                f"{total} validation checks did not pass "
                f"({', '.join(failed_times) if failed_times else 'unspecified periods'})."
            ),
            "rationale": [
                f"Selected Scenario: {name} (ID {scenario.get('id')}).",
                f"Validation: {passed} of {total} checks passed."
                if passed is not None else "Validation checks failed.",
                f"Failed periods: {', '.join(failed_times) if failed_times else 'unspecified'}.",
            ],
            "missing_evidence": [],
        }
    if status == "insufficient":
        return {
            **base,
            "status": "insufficient_evidence",
            "headline": "Insufficient evidence to make a management recommendation.",
            "recommendation": "Complete the missing workflow evidence before making an adoption decision.",
            "rationale": [
                f"Selected Scenario: {name} (ID {scenario.get('id')}).",
                f"Inadequate periods: {', '.join(inadequate_times) if inadequate_times else 'unspecified'}.",
            ],
            "missing_evidence": ["complete validation evidence for every active lane"],
        }
    return {
        **base,
        "status": "conditional",
        "headline": f'Consider Scenario "{name}" conditionally.',
        "recommendation": (
            f"All {total} validation checks passed, but modeled savings are "
            f"unavailable for Separate plans (no comparable Current cost basis); "
            f"adopt only with cost acceptance."
        ),
        "rationale": [
            f"Selected Scenario: {name} (ID {scenario.get('id')}).",
            f"Validation: {total} of {total} checks passed.",
            "Modeled savings unavailable: no Current server-cost basis for comparison.",
            f"Net lane change across periods: {lane_delta:+d}."
            if lane_delta is not None else "Net lane change unavailable.",
        ],
        "missing_evidence": [],
    }


@router.post(
    "/{analysis_id}/workflow/decision/selected",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def create_selected_decision(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Decide the selected Separate plan from its persisted evidence chain.

    Verifies the exact scenario/DES/MC/validation identity chain, applies
    the frozen Decision taxonomy to the validation verdict, and persists a
    scenario-scoped decision job. Nothing is re-optimized or rerun.
    """
    analysis = own_analysis(db, user, analysis_id)
    # Evidence recorded under another Setup is reported as such before the
    # (then also stale) plan is resolved, so the user learns to rerun.
    selection = _latest_job(db, user, "workflow_selection", analysis.id)
    selected_id = (selection.params_json or {}).get("scenario_id") if selection else None
    if isinstance(selected_id, int):
        for kind in ("workflow_des", "workflow_mc", "workflow_validation"):
            prior = _latest_job(db, user, kind, analysis.id, selected_id)
            if prior is not None:
                _require_setup_current(analysis, prior)
    try:
        plan = _require_selected_separate_plan(db, user, analysis)
    except SelectedPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = plan["scenario"]
    des_job = _latest_job(db, user, "workflow_des", analysis.id, scenario.id)
    if des_job is None or (des_job.params_json or {}).get("engine") != "selected-plan-routing-des":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan DES before deciding for this scenario.",
        )
    mc_job = _latest_job(db, user, "workflow_mc", analysis.id, scenario.id)
    if mc_job is None or (mc_job.params_json or {}).get("engine") != "selected-plan-measured-mc":
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Monte Carlo before deciding for this scenario.",
        )
    if (mc_job.params_json or {}).get("des_job_id") != des_job.id:
        raise HTTPException(
            status_code=409,
            detail="Monte Carlo evidence is stale for the latest selected-plan DES. Rerun Monte Carlo.",
        )
    validation_job = _latest_job(db, user, "workflow_validation", analysis.id, scenario.id)
    if validation_job is None:
        raise HTTPException(
            status_code=404,
            detail="Run selected-plan Validation before deciding for this scenario.",
        )
    validation_params = validation_job.params_json or {}
    if (validation_params.get("des_job_id") != des_job.id
            or validation_params.get("mc_job_id") != mc_job.id):
        raise HTTPException(
            status_code=409,
            detail="Validation evidence is stale for the latest Simulation evidence. Rerun Validation.",
        )
    _require_setup_current(analysis, des_job, mc_job, validation_job)
    validation_result = validation_job.result_json or {}
    if validation_result.get("scenario_id") != scenario.id:
        raise HTTPException(
            status_code=409,
            detail="Validation evidence belongs to a different scenario.",
        )
    failure_cap = (mc_job.params_json or {}).get("failure_rate_cap")
    decision = _derive_selected_decision(
        scenario={"id": scenario.id, "name": scenario.name,
                  "dataset_id": scenario.dataset_id},
        schedule=plan["schedule"],
        des_result=des_job.result_json or {},
        validation_result=validation_result,
        failure_cap=float(failure_cap) if isinstance(failure_cap, (int, float)) else 0.0,
    )
    selection = _latest_job(db, user, "workflow_selection", analysis.id)
    decision["evidence_ids"] = {
        "selection": selection.id if selection else None,
        "des": des_job.id,
        "mc": mc_job.id,
        "validation": validation_job.id,
    }
    job = _save_job(
        db, user, "workflow_decision", analysis, scenario,
        {"validation_job_id": validation_job.id, "des_job_id": des_job.id,
         "mc_job_id": mc_job.id},
        decision, settings,
    )
    return {"decision": decision, "persisted": True, "evidence": _job_out(job)}


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
    if (analysis.queue_setup_json or {}).get("queue_structure") == "separate_queues":
        # Separate plans are decided only from the selected-plan evidence chain;
        # the shared rules here must never produce or persist a verdict for them.
        result = _derive_decision(analysis, None, {**evidence, "des": None, "validation": None})
        missing = "the selected-plan Decision (POST /workflow/decision/selected)"
        result["missing_evidence"] = [missing]
        result["rationale"] = [f"Missing: {missing}."]
        return {"decision": result, "persisted": False}
    result = _derive_decision(analysis, scenario, evidence)
    if scenario is None:
        return {"decision": result, "persisted": False}
    job = _save_job(
        db, user, "workflow_decision", analysis, scenario,
        {"evidence_ids": result["evidence_ids"]}, result, settings,
    )
    return {"decision": result, "persisted": True, "evidence": _job_out(job)}
