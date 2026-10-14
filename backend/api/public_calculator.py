"""B2: the guest Quick calculator — the explicit analytical models without an account.

Spec: docs/superpowers/specs/2026-10-09-compact-workflow-ux-redesign.md §7.12 and §11 (B2; owner decision D1:
a guest calculator is accepted as a new unauthenticated compute surface). The response is built by the same
``analysis.model_response`` as ``POST /analysis/{model}``, so the numbers are identical. Nothing is stored and
no account, session or database is touched. Requests are limited per client by the ``guest_compute`` bucket of
``rate_limit.ResourceLimitMiddleware`` (behind the Pages bridge the client is the verified forwarded IP).
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.analysis import AnalysisRequest, model_response

router = APIRouter(prefix="/public/calculator", tags=["public-calculator"])


@router.post("/{model}")
def guest_calculate(model: str, payload: AnalysisRequest) -> dict:
    return model_response(model, payload)
