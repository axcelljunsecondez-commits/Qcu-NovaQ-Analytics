"""Scenarios endpoints: CRUD over saved settings/results (own resources only)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_settings
from backend.api.settings import Settings
from backend.db.models import Scenario, User
from backend.db.session import get_db

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioIn(BaseModel):
    name: str
    dataset_id: int | None = None
    settings: dict = {}
    results: dict = {}


class ScenarioPatch(BaseModel):
    name: str | None = None
    settings: dict | None = None
    results: dict | None = None


class ScenarioOut(BaseModel):
    id: int
    dataset_id: int | None
    name: str
    settings: dict
    results: dict
    created_at: datetime

    model_config = {"from_attributes": True}


def _check_size(results: dict, settings: Settings) -> None:
    import json as _json

    size = len(_json.dumps(results, ensure_ascii=False).encode("utf-8"))
    if size > settings.result_jsonb_max_bytes:
        raise HTTPException(status_code=413, detail="Results payload too large.")


def _to_out(scenario: Scenario) -> dict:
    payload = {
        "id": scenario.id,
        "dataset_id": scenario.dataset_id,
        "name": scenario.name,
        "settings": scenario.settings_json,
        "results": scenario.results_json,
        "created_at": scenario.created_at,
    }
    return ScenarioOut.model_validate(payload).model_dump()


def _own_scenario(db: Session, user: User, scenario_id: int) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


@router.post("", status_code=201)
def create_scenario(
    payload: ScenarioIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    if payload.dataset_id is not None:
        from backend.db.models import Dataset

        dataset = db.get(Dataset, payload.dataset_id)
        if dataset is None or dataset.user_id != user.id:
            raise HTTPException(status_code=404, detail="Dataset not found.")
    _check_size(payload.results, settings)
    scenario = Scenario(
        user_id=user.id,
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    scenarios = db.execute(
        select(Scenario).where(Scenario.user_id == user.id).order_by(Scenario.id.desc())
    ).scalars().all()
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
