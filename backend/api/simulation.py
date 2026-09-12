"""Simulation endpoints: DES, Monte Carlo, and plan validation wrappers."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.api.deps import get_current_user, user_rate_limit
from backend.queueing_engine.config import MC_DEFAULT_FAILURE_THRESHOLD, MC_DEFAULT_TRIALS, MC_FAILURE_RATE_CAP
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segments,
    simulate_segments,
    trace_simulate_segments,
    validate_with_simulation,
)

router = APIRouter(
    prefix="/simulation",
    tags=["simulation"],
    dependencies=[Depends(user_rate_limit("compute"))],
)


class DesRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    segments: list[dict] = Field(max_length=1000)
    sim_hours: float = Field(default=24.0, gt=0, le=168)
    queue_overload_threshold: int = Field(default=20, ge=1)
    seed: int | None = Field(default=42)
    carryover: bool = True


class TraceRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    segments: list[dict] = Field(max_length=1000)
    trace_hours: float = Field(default=1.0, gt=0, le=168)
    queue_overload_threshold: int = Field(default=20, ge=1)
    max_events: int = Field(default=10000, ge=1, le=10000)
    seed: int | None = Field(default=42)
    carryover: bool = True


class McRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    segments: list[dict] = Field(max_length=1000)
    num_trials: int = Field(default=MC_DEFAULT_TRIALS, ge=1, le=100000)
    failure_threshold: float = Field(default=MC_DEFAULT_FAILURE_THRESHOLD, gt=0, le=1)
    failure_rate_cap: float = Field(default=MC_FAILURE_RATE_CAP, gt=0, le=1)
    seed: int | None = Field(default=42)


class ValidateRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    segments: list[dict] = Field(max_length=1000)
    des_sim_hours: float = Field(default=24.0, gt=0, le=168)
    mc_trials: int = Field(default=MC_DEFAULT_TRIALS, ge=1, le=100000)
    mc_failure_threshold: float = Field(default=MC_DEFAULT_FAILURE_THRESHOLD, gt=0, le=1)
    failure_rate_cap: float = Field(default=MC_FAILURE_RATE_CAP, alias="mc_failure_rate_cap", gt=0, le=1)
    seed: int | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True, allow_inf_nan=False)


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


@router.post("/des/trace")
def des_trace(
    payload: TraceRequest,
    _user=Depends(get_current_user),
) -> dict:
    return trace_simulate_segments(
        payload.segments,
        trace_hours=payload.trace_hours,
        queue_overload_threshold=payload.queue_overload_threshold,
        max_events=payload.max_events,
        seed=payload.seed,
        carryover=payload.carryover,
    )


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
    return {"results": result.astype(object).where(pd.notna(result), None).to_dict("records")}
