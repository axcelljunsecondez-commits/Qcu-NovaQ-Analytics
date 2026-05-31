"""FastAPI REST wrapper for NovaMart queue analytics.

Exposes M/M/1–M/G/c/K queueing models and staffing cost optimisation
as clean REST endpoints.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from data_processing import _classify_utilization_status
from optimization import optimize_segment
from queue_models import erlang_a, mgc, mgck, mm1, mmc, mmck


# ── Pydantic schemas ──────────────────────────────────────────────────────

class SegmentInput(BaseModel):
    lambda_: float = Field(..., alias="lambda")
    mu: float = Field(...)
    c: int = Field(default=1, ge=1)
    variance: Optional[float] = None
    K: Optional[int] = None
    theta: Optional[float] = None

    class Config:
        populate_by_name = True


class OptimizeInput(SegmentInput):
    server_cost_per_hr: float = Field(default=87.0, gt=0)
    wait_cost_per_min: float = Field(default=5.0, gt=0)
    max_servers: int = Field(default=20, ge=1)
    target_rho: float = Field(default=0.80, gt=0, lt=1)


class BatchInput(BaseModel):
    segments: list[SegmentInput]


class MetricsResponse(BaseModel):
    time: str = ""
    lambda_: Optional[float] = Field(None, alias="lambda")
    mu: Optional[float] = None
    c: Optional[int] = None
    model: Optional[str] = None
    rho: Optional[float] = None
    L: Optional[float] = None
    Lq: Optional[float] = None
    W: Optional[float] = None
    Wq: Optional[float] = None
    lambda_eff: Optional[float] = None
    abandonment_rate: Optional[float] = None
    stable: bool = False
    status: Optional[str] = None
    warning: Optional[str] = None
    theta: Optional[float] = None

    class Config:
        populate_by_name = True


class OptimizeResponse(BaseModel):
    optimal_c: Optional[int] = None
    current_c: Optional[int] = None
    total_cost_optimal: Optional[float] = None
    server_cost_optimal: Optional[float] = None
    waiting_cost_optimal: Optional[float] = None
    total_cost_current: Optional[float] = None
    savings: Optional[float] = None
    rho_improvement: Optional[float] = None
    rho_optimal: Optional[float] = None
    rho_current: Optional[float] = None
    Wq_optimal: Optional[float] = None
    Wq_current: Optional[float] = None
    warning: Optional[str] = None


# ── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="NovaMart Queue Analytics API",
    description=(
        "Exposes M/M/1–M/G/c/K queueing models and staffing cost "
        "optimizer as REST endpoints."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Internal helpers ──────────────────────────────────────────────────────

def _auto_select_model(inp: SegmentInput) -> dict:
    """Apply the same model-selection rules as ``process_segments()``."""
    lambda_ = inp.lambda_
    mu = inp.mu
    c = inp.c
    variance = inp.variance
    capacity = inp.K
    theta = inp.theta

    if theta is not None and theta > 0:
        metrics = erlang_a(lambda_, mu, c, theta)
        model_name = "M/M/c+M (Erlang-A)"
        theta_val = theta
    elif capacity is not None and variance is not None:
        metrics = mgck(lambda_, mu, c, variance, capacity)
        model_name = "M/G/c/K"
        theta_val = None
    elif capacity is not None:
        metrics = mmck(lambda_, mu, c, capacity)
        model_name = "M/M/c/K"
        theta_val = None
    elif variance is not None:
        metrics = mgc(lambda_, mu, c, variance)
        model_name = "M/G/c"
        theta_val = None
    elif c == 1:
        metrics = mm1(lambda_, mu)
        model_name = "M/M/1"
        theta_val = None
    else:
        metrics = mmc(lambda_, mu, c)
        model_name = "M/M/c"
        theta_val = None

    stable = bool(metrics.get("stable"))
    rho = metrics.get("rho")
    status = _classify_utilization_status(rho)

    return {
        "time": "",
        "lambda": lambda_,
        "mu": mu,
        "c": c,
        "model": model_name,
        "rho": rho,
        "L": metrics.get("L"),
        "Lq": metrics.get("Lq"),
        "W": metrics.get("W"),
        "Wq": metrics.get("Wq"),
        "lambda_eff": metrics.get("lambda_eff"),
        "abandonment_rate": metrics.get("abandonment_rate"),
        "stable": stable,
        "status": status,
        "warning": metrics.get("error"),
        "theta": theta_val,
    }


def _segment_to_record(inp: SegmentInput) -> dict:
    """Convert a validated ``SegmentInput`` to the dict format expected by
    ``optimize_segment()``."""
    return {
        "time": "",
        "lambda": inp.lambda_,
        "mu": inp.mu,
        "c": inp.c,
        "variance": inp.variance,
        "K": inp.K,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0"}


@app.post("/metrics", response_model=MetricsResponse)
def metrics(inp: SegmentInput):
    """Compute queueing metrics for a single segment."""
    if inp.lambda_ <= 0 or inp.mu <= 0:
        raise HTTPException(400, "lambda and mu must be positive")

    result = _auto_select_model(inp)
    return MetricsResponse(**result)


@app.post("/metrics/batch", response_model=list[MetricsResponse])
def metrics_batch(inp: BatchInput):
    """Compute queueing metrics for multiple segments."""
    results = []
    for seg in inp.segments:
        if seg.lambda_ <= 0 or seg.mu <= 0:
            raise HTTPException(400, "lambda and mu must be positive")
        results.append(MetricsResponse(**_auto_select_model(seg)))
    return results


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(inp: OptimizeInput):
    """Run cost-aware staffing optimisation for a single segment."""
    if inp.lambda_ <= 0 or inp.mu <= 0:
        raise HTTPException(400, "lambda and mu must be positive")

    record = _segment_to_record(inp)
    opt_result = optimize_segment(
        record,
        target_utilization=inp.target_rho,
        default_server_cost=inp.server_cost_per_hr,
        max_servers=inp.max_servers,
    )

    current_c = opt_result.get("c_current")
    optimal_c = opt_result.get("c_optimal")
    rho_current = opt_result.get("rho_current")
    rho_optimal = opt_result.get("rho_optimal")

    rho_improvement = None
    if rho_current is not None and rho_optimal is not None and rho_current != 0:
        rho_improvement = rho_current - rho_optimal

    return OptimizeResponse(
        optimal_c=optimal_c,
        current_c=current_c,
        total_cost_optimal=opt_result.get("cost_optimal"),
        server_cost_optimal=opt_result.get("cost_optimal"),
        waiting_cost_optimal=opt_result.get("waiting_cost_optimal"),
        total_cost_current=opt_result.get("cost_current"),
        savings=opt_result.get("delta_cost"),
        rho_improvement=rho_improvement,
        rho_optimal=rho_optimal,
        rho_current=rho_current,
        Wq_optimal=opt_result.get("Wq_optimal"),
        Wq_current=opt_result.get("Wq_current"),
        warning=opt_result.get("warning"),
    )


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
