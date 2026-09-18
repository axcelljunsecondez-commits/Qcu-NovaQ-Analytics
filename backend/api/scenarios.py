"""Scenarios endpoints: CRUD over saved settings/results (own resources only)."""

from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analysis_schemas import unknown_queue_setup
from backend.api.deps import get_current_user, get_settings
from backend.api.optimization import OptimizeBatchRequest, SegmentInput, optimize_batch
from backend.api.settings import Settings
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.separate_optimization import (
    SEPARATE_DES_ENGINE_VERSION,
    full_coverage_min_lanes,
    optimize_separate_schedule,
    prune_separate_schedule,
    validate_des_replication_config,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    dataset_id: int | None = None
    analysis_id: int | None = None
    settings: dict = Field(default_factory=dict)
    results: dict = Field(default_factory=dict)


class ScenarioPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict | None = None
    results: dict | None = None


class ScenarioOut(BaseModel):
    id: int
    analysis_id: int | None
    dataset_id: int | None
    name: str
    settings: dict
    results: dict
    created_at: datetime
    provenance: str = "legacy_unverified"

    model_config = {"from_attributes": True}


def _check_size(results: dict, settings: Settings) -> None:
    import json as _json

    size = len(_json.dumps(results, ensure_ascii=False).encode("utf-8"))
    if size > settings.result_jsonb_max_bytes:
        raise HTTPException(status_code=413, detail="Results payload too large.")


def _to_out(scenario: Scenario) -> dict:
    payload = {
        "id": scenario.id,
        "analysis_id": scenario.analysis_id,
        "dataset_id": scenario.dataset_id,
        "name": scenario.name,
        "settings": scenario.settings_json,
        "results": scenario.results_json,
        "created_at": scenario.created_at,
        "provenance": "verified_snapshot" if scenario.settings_json.get("calculation") else "legacy_unverified",
    }
    return ScenarioOut.model_validate(payload).model_dump()


def _own_scenario(db: Session, user: User, scenario_id: int) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    if scenario.dataset_id is not None:
        dataset = db.get(Dataset, scenario.dataset_id)
        if dataset is None or dataset.user_id != user.id or dataset.analysis_id != scenario.analysis_id:
            raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def _same_result(left, right) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_result(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same_result(a, b) for a, b in zip(left, right))
    if (
        isinstance(left, (float, int))
        and not isinstance(left, bool)
        and isinstance(right, (float, int))
        and not isinstance(right, bool)
    ):
        return math.isfinite(left) and math.isfinite(right) and math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-10)
    return type(left) is type(right) and left == right


def _separate_lane_bound(value) -> int | None:
    """Coerce a saved lane bound mirroring endpoint integer parsing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("Invalid separate lane bound")


def _verify_separate_calculation(payload: ScenarioIn, dataset=None, analysis=None) -> None:
    """Verify a Separate-Queue DES optimization snapshot by deterministic rerun.

    The snapshot re-executes the same persisted evidence with the same
    replication seeds; any tampering with results, options, or dataset
    version fails verification. Trace payloads stay pruned on both sides.
    """
    snapshot = payload.settings.get("calculation")
    if not isinstance(snapshot, dict):
        raise ValueError("Unknown calculation schema or engine version")
    if snapshot.get("engine_version") != SEPARATE_DES_ENGINE_VERSION:
        raise ValueError("Unknown calculation schema or engine version")
    if not isinstance(snapshot.get("calculated_at"), str):
        raise ValueError("Calculation time must be an ISO timestamp")
    timestamp = datetime.fromisoformat(snapshot["calculated_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Calculation time requires a timezone")
    options = snapshot.get("options")
    required = ("target_utilization", "server_cost_per_hr", "customer_waiting_cost",
                "min_active_lanes", "max_active_lanes", "lambda_multiplier", "des")
    if not isinstance(options, dict) or any(key not in options for key in required):
        raise ValueError("Invalid separate calculation options")
    if any(payload.settings.get(key) != value for key, value in options.items()):
        raise ValueError("Saved settings differ from calculated options")
    if dataset is None or snapshot.get("dataset_id") != dataset.id:
        raise ValueError("Separate optimization snapshot requires its dataset.")
    if snapshot.get("dataset_row_count") != len(dataset.normalized_json or []):
        raise ValueError("Dataset changed since the optimization run.")
    setup = (analysis.queue_setup_json or {}) if analysis is not None else {}
    if setup.get("queue_structure") != "separate_queues":
        raise ValueError("Separate optimization requires a separate_queues analysis.")
    des_settings = validate_des_replication_config(options.get("des") or {})
    min_lanes = _separate_lane_bound(options.get("min_active_lanes"))
    if min_lanes is None:
        raise ValueError("Separate plans must record full coverage in min_active_lanes.")
    full_coverage_min_lanes(setup, min_lanes)
    try:
        target = float(options["target_utilization"])
        server_cost = float(options["server_cost_per_hr"])
        waiting_cost = float(options["customer_waiting_cost"])
        multiplier = float(options["lambda_multiplier"])
    except (TypeError, ValueError):
        raise ValueError("Invalid separate calculation options") from None
    schedule = optimize_separate_schedule(
        setup,
        dataset.normalized_json or [],
        target=target,
        server_cost=server_cost,
        waiting_cost=waiting_cost,
        max_lanes=_separate_lane_bound(options.get("max_active_lanes")),
        lambda_multiplier=multiplier,
        des_settings=des_settings,
        full_coverage=True,
    )
    expected = {"schedule": prune_separate_schedule(schedule)}
    if not _same_result(payload.results, expected):
        raise ValueError("Results do not match the calculation inputs")
    payload.results = expected


def _verify_calculation(payload: ScenarioIn, dataset=None, analysis=None) -> None:
    snapshot = payload.settings.get("calculation")
    if snapshot is None:
        return  # compatibility: readable/imported legacy results are explicitly unverified
    try:
        if not isinstance(snapshot, dict):
            raise ValueError("Unknown calculation schema or engine version")
        if snapshot.get("schema_version") == 2:
            _verify_separate_calculation(payload, dataset, analysis)
            return
        if (
            snapshot.get("schema_version") != 1
            or snapshot.get("engine_version") not in ("novaq-2026-09-integrity-v1", "novaq-2026-09-system-v2")
        ):
            raise ValueError("Unknown calculation schema or engine version")
        if not isinstance(snapshot.get("calculated_at"), str):
            raise ValueError("Calculation time must be an ISO timestamp")
        timestamp = datetime.fromisoformat(snapshot["calculated_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Calculation time requires a timezone")
        factor = float(snapshot["what_if_multiplier"])
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("Invalid what-if multiplier")
        options = snapshot["options"]
        if not isinstance(options, dict) or "segments" in options:
            raise ValueError("Invalid calculation options")
        request = OptimizeBatchRequest.model_validate({"segments": snapshot["input_segments"], **options})
        if not request.segments:
            raise ValueError("Snapshot has no segments")
        if any(payload.settings.get(key) != value for key, value in options.items()):
            raise ValueError("Saved settings differ from calculated options")
        if dataset is not None:
            source = [
                SegmentInput.model_validate({**row, "lambda": row["lambda"] * factor}).to_mapping()
                for row in dataset.normalized_json
            ]
            if not _same_result(source, [segment.to_mapping() for segment in request.segments]):
                raise ValueError("Input snapshot differs from the selected dataset and multiplier")
        expected = optimize_batch(request, _user=None)
        if snapshot.get("engine_version") == "novaq-2026-09-integrity-v1":
            # Compare legacy results without additive v2 metadata; never stamp them v2.
            added = {
                "feasibility_status",
                "constraints_passed",
                "violated_constraints",
                "selected_model",
                "model_selection_reason",
                "model_assumptions",
                "service_cv",
                "metric_provenance",
                "effective_constraints",
                "effective_costs",
                "explanation",
            }
            legacy = {"results": [{k: v for k, v in row.items() if k not in added} for row in expected["results"]]}
            if _same_result(payload.results, legacy):
                return
        if not _same_result(payload.results, expected):
            raise ValueError("Results do not match the calculation inputs")
        payload.results = expected
    except (ValueError, TypeError, KeyError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid calculation snapshot: {exc}") from exc


@router.post("", status_code=201)
def create_scenario(
    payload: ScenarioIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    dataset = None
    if payload.dataset_id is not None:
        dataset = db.get(Dataset, payload.dataset_id)
        if dataset is None or dataset.user_id != user.id:
            raise HTTPException(status_code=404, detail="Dataset not found.")
    analysis = db.get(AnalysisProject, payload.analysis_id) if payload.analysis_id is not None else None
    if payload.analysis_id is not None and (analysis is None or analysis.user_id != user.id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis is not None and analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived analyses cannot accept scenarios.")
    if dataset is not None and analysis is not None and dataset.analysis_id != analysis.id:
        raise HTTPException(status_code=404, detail="Dataset not found in this Analysis.")
    if analysis is None and dataset is not None and dataset.analysis_id is not None:
        analysis = db.get(AnalysisProject, dataset.analysis_id)
    if analysis is None:
        if dataset is None:
            analysis = (
                db.execute(
                    select(AnalysisProject).where(
                        AnalysisProject.user_id == user.id,
                        AnalysisProject.name == "Legacy scenarios",
                        AnalysisProject.setup_status == "legacy",
                    )
                )
                .scalars()
                .first()
            )
        if analysis is None:
            setup = unknown_queue_setup()
            analysis = AnalysisProject(
                user_id=user.id,
                name="Legacy scenarios" if dataset is None else dataset.name,
                queue_setup_json=setup.model_dump(mode="json"),
                setup_status="legacy",
            )
            db.add(analysis)
            db.flush()
        if dataset is not None:
            dataset.analysis_id = analysis.id
    _check_size(payload.results, settings)
    _check_size(payload.settings, settings)
    _verify_calculation(payload, dataset, analysis)
    scenario = Scenario(
        user_id=user.id,
        analysis_id=analysis.id,
        dataset_id=payload.dataset_id,
        name=payload.name,
        settings_json=payload.settings,
        results_json=payload.results,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return {"scenario": _to_out(scenario)}


@router.get("")
def list_scenarios(
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(Scenario).where(Scenario.user_id == user.id)
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        query = query.where(Scenario.analysis_id == analysis_id)
    scenarios = db.execute(query.order_by(Scenario.id.desc())).scalars().all()
    scenarios = [
        scenario
        for scenario in scenarios
        if scenario.dataset_id is None
        or (
            scenario.dataset is not None
            and scenario.dataset.user_id == user.id
            and scenario.dataset.analysis_id == scenario.analysis_id
        )
    ]
    return {"scenarios": [_to_out(scenario) for scenario in scenarios]}


@router.get("/{scenario_id}")
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return {"scenario": _to_out(_own_scenario(db, user, scenario_id))}


@router.patch("/{scenario_id}")
def patch_scenario(
    scenario_id: int,
    payload: ScenarioPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    scenario = _own_scenario(db, user, scenario_id)
    if payload.results is not None:
        _check_size(payload.results, settings)
    if (payload.settings is not None and payload.settings != scenario.settings_json) or (
        payload.results is not None and payload.results != scenario.results_json
    ):
        raise HTTPException(
            status_code=409, detail="Saved calculation inputs/results are immutable; create a new scenario."
        )
    if payload.name is not None:
        scenario.name = payload.name
    if payload.settings is not None:
        scenario.settings_json = payload.settings
    if payload.results is not None:
        _check_size(payload.results, settings)
        scenario.results_json = payload.results
    db.commit()
    db.refresh(scenario)
    return {"scenario": _to_out(scenario)}


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    scenario = _own_scenario(db, user, scenario_id)
    db.delete(scenario)
    db.commit()
    return {"detail": "Scenario deleted."}
