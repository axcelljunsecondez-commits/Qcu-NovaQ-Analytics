"""Analytical model endpoints: thin adapters over the queueing engine."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user, user_rate_limit
from backend.queueing_engine.models.queue_models import erlang_a, mgc, mgck, mm1, mmc, mmck

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(user_rate_limit("compute"))],
)

MODELS = {"mm1", "mmc", "mgc", "mmck", "mgck", "erlang_a"}

_ATTRS = {"lambda": "lambda_"}
REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "mm1": ("lambda", "mu"),
    "mmc": ("lambda", "mu", "c"),
    "mgc": ("lambda", "mu", "c", "variance"),
    "mmck": ("lambda", "mu", "c", "K"),
    "mgck": ("lambda", "mu", "c", "variance", "K"),
    "erlang_a": ("lambda", "mu", "c", "theta"),
}


class AnalysisRequest(BaseModel):
    lambda_: float = Field(alias="lambda", ge=0)
    mu: float = Field(gt=0)
    c: int | None = Field(default=None, ge=1)
    variance: float | None = Field(default=None, ge=0)
    K: int | None = Field(default=None, ge=1)
    theta: float | None = Field(default=None, ge=0)

    model_config = {"populate_by_name": True, "allow_inf_nan": False}


def _get_param(payload: AnalysisRequest, name: str):
    return getattr(payload, _ATTRS.get(name, name))


def _run_model(name: str, payload: AnalysisRequest) -> dict:
    if name not in MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {name}.")
    missing = [param for param in REQUIRED_PARAMS[name] if _get_param(payload, param) is None]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Model {name} requires parameters: {', '.join(missing)}.",
        )
    if name == "mm1":
        return mm1(payload.lambda_, payload.mu)
    if name == "mmc":
        return mmc(payload.lambda_, payload.mu, cast(int, payload.c))
    if name == "mgc":
        return mgc(payload.lambda_, payload.mu, cast(int, payload.c), cast(float, payload.variance))
    if name == "mmck":
        return mmck(payload.lambda_, payload.mu, cast(int, payload.c), cast(int, payload.K))
    if name == "mgck":
        return mgck(
            payload.lambda_,
            payload.mu,
            cast(int, payload.c),
            cast(float, payload.variance),
            cast(int, payload.K),
        )
    return erlang_a(payload.lambda_, payload.mu, cast(int, payload.c), cast(float, payload.theta))


@router.post("/{model}")
def analyze(
    model: str,
    payload: AnalysisRequest,
    _user=Depends(get_current_user),
) -> dict:
    return {**_run_model(model, payload), "metric_provenance": "analytical", "selected_model": model, "model_selection_reason": "Explicit model requested by the user."}
