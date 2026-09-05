"""Simulation endpoints: DES, Monte Carlo, and plan validation wrappers."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segments,
    simulate_segments,
    validate_with_simulation,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


class DesRequest(BaseModel):
    segments: list[dict]
    sim_hours: float = Field(default=24.0, gt=0)
    queue_overload_threshold: int = Field(default=20, ge=1)
    seed: int | None = Field(default=42)
    carryover: bool = True


class McRequest(BaseModel):
    segments: list[dict]
    num_trials: int = Field(default=2000, ge=1, le=100000)
    failure_threshold: float = Field(default=0.75, gt=0, le=1)
    failure_rate_cap: float = Field(default=0.10, gt=0, le=1)
    seed: int | None = Field(default=42)


class ValidateRequest(BaseModel):
    segments: list[dict]
    des_sim_hours: float = Field(default=24.0, gt=0)
    mc_trials: int = Field(default=2000, ge=1, le=100000)
    mc_failure_threshold: float = Field(default=0.75, gt=0, le=1)
    failure_rate_cap: float = Field(default=0.10, alias="mc_failure_rate_cap", gt=0, le=1)
    seed: int | None = Field(default=None)

    model_config = {"populate_by_name": True}


@router.post("/des")
def des(
    payload: DesRequest,
    _user=Depends(get_current_user),
) -> dict:
    results = simulate_segments(
        payload.segments,
        sim_hours=payload.sim_hours,
        queue_overload_threshold=payload.queue_overload_threshold,
        seed=payload.seed,
        carryover=payload.carryover,
    )
    return {"results": results}


@router.post("/mc")
def mc(
    payload: McRequest,
    _user=Depends(get_current_user),
) -> dict:
    results = mc_simulate_segments(
        payload.segments,
        num_trials=payload.num_trials,
        failure_threshold=payload.failure_threshold,
        seed=payload.seed,
        failure_rate_cap=payload.failure_rate_cap,
    )
    return {"results": results}


@router.post("/validate")
def validate(
    payload: ValidateRequest,
    _user=Depends(get_current_user),
) -> dict:
    if not payload.segments:
        raise HTTPException(status_code=422, detail="At least one segment is required.")
    comparison = pd.DataFrame(payload.segments)
    result = validate_with_simulation(
        comparison,
        des_sim_hours=payload.des_sim_hours,
        mc_trials=payload.mc_trials,
        mc_failure_threshold=payload.mc_failure_threshold,
        seed=payload.seed,
        failure_rate_cap=payload.failure_rate_cap,
    )
    return {"results": result.where(pd.notna(result), None).to_dict("records")}
