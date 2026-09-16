"""Optimization endpoints: thin wrappers over optimize_segment(s)."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.deps import get_current_user, user_rate_limit
from backend.queueing_engine.config import (
    DEFAULT_MAX_SERVERS,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_TARGET_UTILIZATION,
    DEFAULT_WAIT_COST_HR,
)
from backend.queueing_engine.services.optimization import optimize_segment

router = APIRouter(
    prefix="/optimize",
    tags=["optimization"],
    dependencies=[Depends(user_rate_limit("compute"))],
)


class SegmentInput(BaseModel):
    time: str = "segment"
    lambda_: float = Field(alias="lambda", ge=0)
    mu: float = Field(gt=0)
    c: int = Field(ge=1)
    variance: float | None = Field(default=None, ge=0)
    K: int | None = Field(default=None, ge=1)
    theta: float | None = Field(default=None, ge=0)
    server_cost: float | None = Field(default=None, ge=0)
    queue_structure: str | None = None
    model_id: str | None = None

    model_config = ConfigDict(populate_by_name=True, allow_inf_nan=False)

    def to_mapping(self) -> dict:
        mapping: dict = {
            "time": self.time,
            "lambda": self.lambda_,
            "mu": self.mu,
            "c": self.c,
            "variance": self.variance,
            "K": self.K,
            "theta": self.theta,
            "queue_structure": self.queue_structure,
            "model_id": self.model_id,
        }
        if self.server_cost is not None:
            mapping["server_cost"] = self.server_cost
        return mapping


class ConstraintOptions(BaseModel):
    min_servers: int = Field(default=1, ge=1, le=256)
    max_servers: int = Field(default=DEFAULT_MAX_SERVERS, ge=1, le=256)
    max_wait_minutes: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_bounds(self):
        if self.min_servers > self.max_servers:
            raise ValueError("min_servers must not exceed max_servers")
        return self


class OptimizeRequest(ConstraintOptions):
    model_config = ConfigDict(allow_inf_nan=False)
    segment: SegmentInput
    server_cost_per_hr: float = Field(default=DEFAULT_SERVER_COST_HR, gt=0)
    target_utilization: float = Field(default=DEFAULT_TARGET_UTILIZATION, gt=0, le=1)
    max_servers: int = Field(default=DEFAULT_MAX_SERVERS, ge=1, le=256)
    customer_waiting_cost: float = Field(default=DEFAULT_WAIT_COST_HR, ge=0)
    cost_per_abandonment: float = Field(default=0.0, ge=0)
    abandonment_rate: float = Field(default=0.0, ge=0, le=1)


class OptimizeBatchRequest(ConstraintOptions):
    model_config = ConfigDict(allow_inf_nan=False)
    segments: list[SegmentInput] = Field(max_length=1000)
    server_cost_per_hr: float = Field(default=DEFAULT_SERVER_COST_HR, gt=0)
    target_utilization: float = Field(default=DEFAULT_TARGET_UTILIZATION, gt=0, le=1)
    max_servers: int = Field(default=DEFAULT_MAX_SERVERS, ge=1, le=256)
    customer_waiting_cost: float = Field(default=DEFAULT_WAIT_COST_HR, ge=0)
    cost_per_abandonment: float = Field(default=0.0, ge=0)
    abandonment_rate: float = Field(default=0.0, ge=0, le=1)


def _finite(value) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _safe_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


class OptimizationOut(BaseModel):
    feasibility_status: str = "INVALID_INPUT"
    constraints_passed: bool = False
    violated_constraints: list[str] = Field(default_factory=list)
    selected_model: str | None = None
    model_selection_reason: str | None = None
    model_assumptions: str | None = None
    service_cv: float | None = None
    metric_provenance: str = "analytical"
    effective_constraints: dict = Field(default_factory=dict)
    effective_costs: dict = Field(default_factory=dict)
    explanation: str = ""

    time: str
    lambda_: float | None = None
    mu: float | None = None
    c_current: int | None = None
    c_optimal: int | None
    rho_current: float | None
    rho_optimal: float | None
    Wq_current: float | None
    Wq_optimal: float | None
    Lq_current: float | None
    Lq_optimal: float | None
    cost_current: float | None
    cost_optimal: float | None
    delta_cost: float | None
    delta_Wq: float | None
    delta_Lq: float | None
    delta_c: int | None
    delta_rho: float | None
    waiting_cost_current: float | None
    waiting_cost_optimal: float | None
    abandonment_cost_current: float | None
    abandonment_cost_optimal: float | None
    cost_per_server: float | None
    current_stable: bool
    optimized_stable: bool
    recommendation: str
    warning: str | None

    model_config = ConfigDict(populate_by_name=True, allow_inf_nan=False)


def _to_out(result: dict) -> dict:
    return OptimizationOut(
        **{key: result[key] for key in ("feasibility_status", "constraints_passed", "violated_constraints", "selected_model", "model_selection_reason", "model_assumptions", "service_cv", "metric_provenance", "effective_constraints", "effective_costs", "explanation") if key in result},
        time=str(result.get("time", "")),
        lambda_=_finite(result.get("lambda")),
        mu=_finite(result.get("mu")),
        c_current=_safe_int(result.get("c_current")),
        c_optimal=result.get("c_optimal"),
        rho_current=_finite(result.get("rho_current")),
        rho_optimal=_finite(result.get("rho_optimal")),
        Wq_current=_finite(result.get("Wq_current")),
        Wq_optimal=_finite(result.get("Wq_optimal")),
        Lq_current=_finite(result.get("Lq_current")),
        Lq_optimal=_finite(result.get("Lq_optimal")),
        cost_current=_finite(result.get("cost_current")),
        cost_optimal=_finite(result.get("cost_optimal")),
        delta_cost=_finite(result.get("delta_cost")),
        delta_Wq=_finite(result.get("delta_Wq")),
        delta_Lq=_finite(result.get("delta_Lq")),
        delta_c=result.get("delta_c"),
        delta_rho=_finite(result.get("delta_rho")),
        waiting_cost_current=_finite(result.get("waiting_cost_current")),
        waiting_cost_optimal=_finite(result.get("waiting_cost_optimal")),
        abandonment_cost_current=_finite(result.get("abandonment_cost_current")),
        abandonment_cost_optimal=_finite(result.get("abandonment_cost_optimal")),
        cost_per_server=_finite(result.get("cost_per_server")),
        current_stable=bool(result.get("current_stable", False)),
        optimized_stable=bool(result.get("optimized_stable", False)),
        recommendation=str(result.get("recommendation", "")),
        warning=result.get("warning"),
    ).model_dump()


@router.post("")
def optimize(
    payload: OptimizeRequest,
    _user=Depends(get_current_user),
) -> dict:
    result = optimize_segment(
        payload.segment.to_mapping(),
        target_utilization=payload.target_utilization,
        default_server_cost=payload.server_cost_per_hr,
        max_servers=payload.max_servers,
        min_servers=payload.min_servers, max_wait_minutes=payload.max_wait_minutes,
        customer_waiting_cost=payload.customer_waiting_cost,
        cost_per_abandonment=payload.cost_per_abandonment,
        abandonment_rate=payload.abandonment_rate,
    )
    return _to_out(result)


@router.post("/batch")
def optimize_batch(
    payload: OptimizeBatchRequest,
    _user=Depends(get_current_user),
) -> dict:
    results = []
    for segment in payload.segments:
        result = optimize_segment(
            segment.to_mapping(),
            target_utilization=payload.target_utilization,
            default_server_cost=payload.server_cost_per_hr,
            max_servers=payload.max_servers,
        min_servers=payload.min_servers, max_wait_minutes=payload.max_wait_minutes,
            customer_waiting_cost=payload.customer_waiting_cost,
            cost_per_abandonment=payload.cost_per_abandonment,
            abandonment_rate=payload.abandonment_rate,
        )
        results.append(_to_out(result))
    return {"results": results}
