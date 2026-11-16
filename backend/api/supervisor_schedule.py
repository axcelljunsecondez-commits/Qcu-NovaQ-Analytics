"""Supervisor check/review/apply orchestration; existing analytical services unchanged."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.orm import Session

from backend.api.analyses import _to_out as analysis_out
from backend.api.analyses import own_analysis
from backend.api.current_dataset import is_for_planning
from backend.api.deps import get_current_user, user_rate_limit
from backend.api.plan_breaks import break_plan_blockers, setup_with_proposed_breaks
from backend.api.scenarios import setup_fingerprint
from backend.api.workflow import SeparateOptimizeRequest, _current_valid_dataset_id
from backend.db.models import AnalysisProject, Dataset, User
from backend.db.session import get_db
from backend.queueing_engine.services.break_optimization import optimize_separate_breaks
from backend.queueing_engine.services.separate_optimization import (
    full_coverage_min_lanes,
    optimize_separate_schedule,
    prune_separate_schedule,
    separate_engine_version,
    validate_des_replication_config,
)

router = APIRouter(prefix="/analyses", tags=["workflow"])
STALE = "The setup, data or check settings changed. Check the schedule again."


class SupervisorPreviewRequest(SeparateOptimizeRequest):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    dataset_id: StrictInt
    allow_break_changes: StrictBool = False
    max_shift_minutes: StrictInt = Field(default=120, ge=0, le=240, multiple_of=15)


class SupervisorApplyRequest(SupervisorPreviewRequest):
    preview_hash: str = Field(min_length=64, max_length=64)


def _dataset(db: Session, user: User, analysis: AnalysisProject, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id or dataset.analysis_id != analysis.id:
        raise HTTPException(status_code=404, detail="Dataset not found in this Analysis.")
    if not is_for_planning(dataset) or not (dataset.validation_report_json or {}).get("ok"):
        raise HTTPException(status_code=422, detail="Choose a successfully processed planning file.")
    if not isinstance(dataset.normalized_json, list) or not dataset.normalized_json:
        raise HTTPException(status_code=422, detail="This Analysis has no Current evidence.")
    return dataset


def _binding(dataset: Dataset) -> dict[str, Any]:
    # Content as well as row identity: do not trust an unchanged integer id alone.
    return {
        "id": dataset.id, "generation": dataset.generation,
        "records": dataset.normalized_json, "validation": dataset.validation_report_json,
        "purpose": dataset.purpose, "row_count": dataset.row_count,
    }


def _check(
    analysis: AnalysisProject, dataset: Dataset, payload: SupervisorPreviewRequest, *, current: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    setup = deepcopy(analysis.queue_setup_json or {})
    if setup.get("queue_structure") != "separate_queues":
        raise HTTPException(status_code=422, detail="Separate optimization requires a separate_queues analysis.")
    draft = deepcopy(setup)
    breaks = None
    try:
        settings = validate_des_replication_config(
            {key: value for key, value in payload.des.model_dump().items() if value is not None}
        )
        settings["server_cost"] = payload.server_cost_per_hr
        settings["waiting_cost"] = payload.customer_waiting_cost
        full_coverage_min_lanes(setup, payload.min_active_lanes)
        if payload.allow_break_changes:
            if payload.lambda_multiplier != 1:
                raise ValueError("Break changes require demand multiplier 1. Check demand changes with break changes off.")
            breaks = optimize_separate_breaks(
                setup, dataset.normalized_json, target=payload.target_utilization,
                max_shift_minutes=payload.max_shift_minutes,
                replications=5, base_seed=settings["base_seed"],
            )
            draft = setup_with_proposed_breaks(setup, breaks)
        schedule = prune_separate_schedule(optimize_separate_schedule(
            draft, dataset.normalized_json, target=payload.target_utilization,
            server_cost=payload.server_cost_per_hr, waiting_cost=payload.customer_waiting_cost,
            max_lanes=payload.max_active_lanes, lambda_multiplier=payload.lambda_multiplier,
            des_settings=settings, full_coverage=True,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    blockers: list[str] = []
    if not payload.allow_break_changes:
        blockers.append("break_changes_off")
    elif breaks is not None:
        blockers.extend(break_plan_blockers(breaks, schedule))
    if schedule["overall"] != "COMPLETE" and "staffing_check" not in blockers:
        blockers.append("staffing_check")
    if not current:
        blockers.append("not_current_data")
    result = {
        "schedule": schedule, "engine_version": separate_engine_version(draft),
        "breaks": breaks, "setup_hash": setup_fingerprint(setup),
        "dataset_id": dataset.id, "can_apply": not blockers, "blockers": blockers,
    }
    result["preview_hash"] = setup_fingerprint({
        "request": payload.model_dump(), "setup": setup, "dataset": _binding(dataset), "result": result,
    })
    return result, draft


@router.post(
    "/{analysis_id}/workflow/optimize/separate/supervisor/preview",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def preview_supervisor_schedule(
    analysis_id: int, payload: SupervisorPreviewRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    dataset = _dataset(db, user, analysis, payload.dataset_id)
    result, _ = _check(analysis, dataset, payload, current=dataset.id == _current_valid_dataset_id(db, user, analysis))
    return result


@router.post(
    "/{analysis_id}/workflow/optimize/separate/supervisor/apply",
    dependencies=[Depends(user_rate_limit("compute"))],
)
def apply_supervisor_schedule(
    analysis_id: int, payload: SupervisorApplyRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    dataset = _dataset(db, user, analysis, payload.dataset_id)
    original = deepcopy(analysis.queue_setup_json)
    original_updated = analysis.updated_at
    data_binding = setup_fingerprint(_binding(dataset))
    request = SupervisorPreviewRequest.model_validate(payload.model_dump(exclude={"preview_hash"}))
    result, draft = _check(analysis, dataset, request, current=dataset.id == _current_valid_dataset_id(db, user, analysis))
    if payload.preview_hash != result["preview_hash"]:
        raise HTTPException(status_code=409, detail=STALE + " (preview)")
    if not result["can_apply"]:
        raise HTTPException(status_code=409, detail="This check cannot be applied. Review the check results.")
    # Re-read after computation; confirmation must describe the latest checked baseline/data.
    db.refresh(analysis)
    db.refresh(dataset)
    if (analysis.queue_setup_json != original or analysis.updated_at != original_updated
            or setup_fingerprint(_binding(dataset)) != data_binding
            or dataset.id != _current_valid_dataset_id(db, user, analysis)):
        raise HTTPException(status_code=409, detail=STALE + " (freshness)")
    return {**result, "can_apply": False, "analysis": analysis_out(analysis),
            "moves_applied": len(result["breaks"]["moves"]), "plan_setup": draft,
            "destination": "suggested_plan_draft"}
