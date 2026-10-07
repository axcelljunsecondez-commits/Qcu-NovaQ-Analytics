"""Named Shared Queue API: the one thin adapter over the named-employee shared-queue modules.

Spec: docs/superpowers/specs/2026-09-30-shared-queue-named-api-ui-first-slice.md (A1-A6, OD-1 to OD-9,
numeric identity B1, identity status codes). This is the only file outside the enhancement modules
that may import them (A6; the isolation guard in tests/test_shared_segments.py names it).

The adapter authenticates, authorizes, validates the request shape, resolves the explicitly selected
dataset and its generation, maps fields onto the domain dataclasses, calls the domain, persists one
Job per run, and maps domain failures onto HTTP responses. It holds no queueing, DES, roster,
playback, attribution, or cost logic: every semantic rule is the domain's and is surfaced unchanged.

Nothing here touches ``/simulation/*``, ``/optimize/*``, the workflow evidence, Compare, Decision, or
Reports. Workforce cost stays backend-only: the named workforce-cost module is never imported.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Coroutine
from dataclasses import asdict, fields
from datetime import datetime, timezone
from numbers import Integral
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analyses import own_analysis
from backend.api.current_dataset import is_successfully_processed
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.scenarios import setup_fingerprint
from backend.api.settings import Settings
from backend.api.workflow import _job_out
from backend.db.models import AnalysisProject, Dataset, Job, User
from backend.db.session import get_db
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    SharedSegmentError,
    timeline_from_aggregate_rows,
    validate_timeline,
)
from backend.queueing_engine.services.shared_workforce import evaluate_roster
from backend.queueing_engine.simulation.shared_continuous_des import CLOSING_POLICIES
from backend.queueing_engine.simulation.shared_named_attribution import (
    NamedAttributionError,
    build_named_attribution,
)
from backend.queueing_engine.simulation.shared_named_des import (
    APPROVED_EMPLOYEE_POLICY,
    NAMED_ENGINE_VERSION,
    POLICY_MEANINGS,
    EmployeeDesPolicy,
    simulate_named_prescribed,
)
from backend.queueing_engine.simulation.shared_named_playback import (
    NamedPlaybackError,
    playback_from_named_replications,
    rebuild_named_inputs,
)
from backend.queueing_engine.simulation.shared_named_replications import (
    METHOD_VERSION,
    NO_VERDICT_REASON,
    named_inputs_digest,
    named_replication_row,
    replication_seed_sequence,
    run_named_replications,
    simulate_named_replication,
)


def _json_safe(value: Any) -> Any:
    """A non-finite float as its JSON token text (``NaN``, ``Infinity``, ``-Infinity``); everything else unchanged."""
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


class _FiniteValidationRoute(APIRoute):
    """Keep a request carrying NaN or ±Infinity a 422, as spec section 11 requires.

    FastAPI's default validation response echoes each offending input. A non-finite input cannot be
    encoded as JSON, so that 422 would otherwise become a 500. The response keeps FastAPI's validation
    list and shows a non-finite input as its JSON token text.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as error:
                return JSONResponse(status_code=422, content={"detail": _json_safe(jsonable_encoder(error.errors()))})

        return route_handler


router = APIRouter(prefix="/analyses", tags=["shared-named"], route_class=_FiniteValidationRoute)
logger = logging.getLogger("novaq.api.shared_named")

JOB_KIND = "shared_named_replications"
NAMED_API_VERSION = "novaq-shared-named-api-v1"
SEED_MAX = 9007199254740991  # 2**53 - 1: every seed survives a JavaScript number unchanged (OD-5)

# Provisional API limits (spec section 6.2). NOT PRODUCTION-APPROVED: each is the largest combination
# measured together against the local 524,288-byte result cap. They become final only when the
# production result cap and request and response limits are VERIFIED (OD-9). The persisted-size check
# against settings.result_jsonb_max_bytes stays as the backstop for input sets never measured.
N_MAX = 9  # replications
S_MAX = 52  # required-staffing segments
E_MAX = 24  # employees
R_MAX = 48  # roster shifts
AV_MAX = 3  # availability windows per employee
BR_MAX = 3  # break rules
BQ_MAX = 2  # breaks per break rule
BS_MAX = 2  # breaks per roster shift
# Run-time bound (spec section 22.8, owner-approved 2026-10-07): expected customers per run, that is replications
# x the sum of arrival rate x period hours over the horizon, measured to keep one request near 60 s on a
# Render-Free-like container. Checked after the demand is known and before any simulation.
C_MAX = 2900
LIMITS_STATUS = "provisional_not_production_approved"

MODEL_SCOPE = (
    "Aggregate M/M/c demand only: the selected dataset's rows must be HH:MM-HH:MM clock ranges without "
    "variance, K, or theta, from a shared queue. Any other row is rejected and never reduced to M/M/c."
)

# Provenance fields that playback_from_named_replications reads to regenerate a replication. B1 requires
# each to come back from the database exactly as computed.
REQUIRED_PROVENANCE = (
    "method_version", "named_engine_version", "state_machine_version", "arrival_engine_version",
    "seed_scheme", "root_entropy", "replications", "closing_policy", "employee_policy",
)
# NamedPlaybackError checks that mean the stored run cannot be regenerated exactly (409); any other
# check is an engine or replay defect (500).
REGENERATION_CHECKS = frozenset({"regeneration_identity", "closing_policy", "stored_row"})


# ── Request schema (spec section 3) ─────────────────────────────────────────
#
# Field names equal the domain dataclass field names. The schema checks shape, finiteness, integer
# strictness, and minimum list lengths only; counts above the provisional limits are refused by
# _limit_problem (422 limit_exceeded) before any computation.


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


_Id = Field(min_length=1, max_length=64)


class HorizonIn(_Strict):
    start_minute: StrictInt
    end_minute: StrictInt


class StaffingSegmentIn(_Strict):
    segment_id: StrictStr = _Id
    start_minute: StrictInt
    end_minute: StrictInt
    servers: StrictInt


class AvailabilityWindowIn(_Strict):
    start_minute: StrictInt
    end_minute: StrictInt


class EmployeePayIn(_Strict):
    # Every key is required; null means "not supplied" and is never read as 0.
    regular_rate_per_hour: StrictFloat | None
    overtime_rate_per_hour: StrictFloat | None
    daily_regular_paid_minutes: StrictInt | None


class EmployeeIn(_Strict):
    employee_id: StrictStr = _Id  # pseudonymous; the domain's id pattern is authoritative
    availability: list[AvailabilityWindowIn] = Field(min_length=1)
    pay: EmployeePayIn


class ShiftRulesIn(_Strict):
    earliest_start_minute: StrictInt
    latest_end_minute: StrictInt
    min_shift_minutes: StrictInt
    max_shift_minutes: StrictInt
    boundary_granularity_minutes: StrictInt
    max_shifts_per_employee: StrictInt
    min_minutes_between_shifts: StrictInt | None


class BreakRequirementIn(_Strict):
    name: StrictStr = _Id
    duration_minutes: StrictInt
    paid: StrictBool
    earliest_start_offset_minutes: StrictInt
    latest_start_offset_minutes: StrictInt


class BreakRuleIn(_Strict):
    min_shift_minutes: StrictInt
    max_shift_minutes: StrictInt
    min_gap_minutes: StrictInt
    breaks: list[BreakRequirementIn]


class WorkforceRulesIn(_Strict):
    shift_rules: ShiftRulesIn
    break_rules: list[BreakRuleIn]
    register_count: StrictInt


class ScheduledBreakIn(_Strict):
    name: StrictStr = _Id
    start_minute: StrictInt


class ScheduledShiftIn(_Strict):
    employee_id: StrictStr = _Id
    start_minute: StrictInt
    end_minute: StrictInt
    breaks: list[ScheduledBreakIn]


class EmployeePolicyIn(_Strict):
    drain_crew: StrictStr
    drain_duration: StrictStr
    hard_cutoff_release: StrictStr
    breaks_at_closing: StrictStr
    break_delay: StrictStr
    employee_choice: StrictStr


class NamedWorkforceInput(_Strict):
    dataset_id: StrictInt = Field(ge=1)
    horizon: HorizonIn
    required_staffing: list[StaffingSegmentIn] = Field(min_length=1)
    employees: list[EmployeeIn] = Field(min_length=1)
    rules: WorkforceRulesIn
    roster: list[ScheduledShiftIn]
    closing_policy: StrictStr
    employee_policy: EmployeePolicyIn


class NamedRunRequest(NamedWorkforceInput):
    replications: StrictInt = Field(ge=1)
    seed: StrictInt = Field(ge=0, le=SEED_MAX)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _limits(settings: Settings) -> dict[str, Any]:
    return {
        "max_replications": N_MAX,
        "max_required_staffing_segments": S_MAX,
        "max_employees": E_MAX,
        "max_roster_shifts": R_MAX,
        "max_availability_windows_per_employee": AV_MAX,
        "max_break_rules": BR_MAX,
        "max_breaks_per_break_rule": BQ_MAX,
        "max_breaks_per_roster_shift": BS_MAX,
        "max_expected_customers_per_run": C_MAX,
        "result_max_bytes": settings.result_jsonb_max_bytes,
        "status": LIMITS_STATUS,
    }


def _ineligible_reasons(analysis: AnalysisProject) -> list[str]:
    """The Setup gates (spec section 3). Unknown capacity or abandonment is never read as absent (OD-3)."""
    setup = analysis.queue_setup_json or {}
    reasons = []
    if setup.get("queue_structure") != "shared_queue":
        reasons.append("queue_structure_not_shared_queue")
    if setup.get("capacity_mode") != "unlimited":
        reasons.append("capacity_not_unlimited")
    if setup.get("abandonment_mode") != "not_modeled":
        reasons.append("abandonment_not_not_modeled")
    return reasons


def _require_eligible(analysis: AnalysisProject) -> None:
    reasons = _ineligible_reasons(analysis)
    if reasons:
        raise HTTPException(status_code=422, detail={"code": "ineligible_setup", "reasons": reasons})


def _selected_dataset(db: Session, user: User, analysis: AnalysisProject, dataset_id: int) -> Dataset:
    """The explicitly selected dataset of this analysis and user (OD-2); never the "current" one."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id or dataset.analysis_id != analysis.id:
        raise HTTPException(status_code=404, detail={"code": "dataset_not_found"})
    if not is_successfully_processed(dataset):
        raise HTTPException(status_code=422, detail={"code": "dataset_not_processed"})
    return dataset


def _limit_problem(body: NamedWorkforceInput, replications: int | None = None) -> dict[str, Any] | None:
    counts: list[tuple[str, int, int]] = []
    if replications is not None:
        counts.append(("replications", replications, N_MAX))
    counts += [
        ("required_staffing", len(body.required_staffing), S_MAX),
        ("employees", len(body.employees), E_MAX),
        ("roster", len(body.roster), R_MAX),
        ("break_rules", len(body.rules.break_rules), BR_MAX),
    ]
    counts += [("availability", len(item.availability), AV_MAX) for item in body.employees]
    counts += [("break_rules.breaks", len(rule.breaks), BQ_MAX) for rule in body.rules.break_rules]
    counts += [("roster.breaks", len(shift.breaks), BS_MAX) for shift in body.roster]
    for limit, value, maximum in counts:
        if value > maximum:
            return {"code": "limit_exceeded", "limit": limit, "value": value, "max": maximum}
    return None


def _require_within_limits(body: NamedWorkforceInput, replications: int | None = None) -> None:
    problem = _limit_problem(body, replications)
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)


def _expected_customers_per_replication(body: NamedWorkforceInput, demand_periods: list[DemandPeriod]) -> float:
    """Sum of arrival rate x hours of each demand period inside the operating horizon (spec section 22.8)."""
    start, end = body.horizon.start_minute, body.horizon.end_minute
    return math.fsum(
        period.arrival_rate_per_hour * max(0, min(end, period.end_minute) - max(start, period.start_minute)) / 60
        for period in demand_periods)


def _require_within_customer_bound(per_replication: float, replications: int) -> None:
    expected = per_replication * replications
    if expected > C_MAX:
        raise HTTPException(status_code=422, detail={
            "code": "limit_exceeded", "limit": "expected_customers", "value": round(expected, 1), "max": C_MAX,
            "replications": replications, "max_replications": math.floor(C_MAX / per_replication)})


def _domain_inputs(body: NamedWorkforceInput, demand_periods: list[DemandPeriod]) -> dict[str, Any]:
    """Field mapping only: the request in the recorded-snapshot shape, rebuilt by the domain's own mapping."""
    snapshot = {
        "horizon": body.horizon.model_dump(),
        "demand_periods": [asdict(period) for period in demand_periods],
        "required_staffing": [item.model_dump() for item in body.required_staffing],
        "employees": [item.model_dump() for item in body.employees],
        "rules": body.rules.model_dump(),
        "roster": [item.model_dump() for item in body.roster],
    }
    return rebuild_named_inputs(snapshot)


def _employee_policy(body: NamedWorkforceInput) -> EmployeeDesPolicy:
    return EmployeeDesPolicy(**body.employee_policy.model_dump())


def _check_inputs(body: NamedWorkforceInput, dataset: Dataset) -> dict[str, Any]:
    """R2 steps 4-8. Returns the stage that failed (or None), its problems, and what was established."""
    outcome: dict[str, Any] = {
        "stage_failed": None, "problems": [], "demand_periods": None, "roster_report": None, "inputs": None,
    }

    def failed(stage: str, problems: list[str]) -> dict[str, Any]:
        outcome["stage_failed"], outcome["problems"] = stage, problems
        return outcome

    try:
        demand_periods, _discarded_staffing = timeline_from_aggregate_rows(dataset.normalized_json or [])
    except SharedSegmentError as error:
        return failed("demand", error.problems)
    outcome["demand_periods"] = demand_periods
    inputs = _domain_inputs(body, demand_periods)
    outcome["inputs"] = inputs

    # Authoritative domain validation (OD-4): the timeline, then the workforce rules and the roster.
    problems: list[str] = []
    try:
        validate_timeline(inputs["horizon"], inputs["demand_periods"], inputs["required_staffing"])
    except SharedSegmentError as error:
        problems += error.problems
    try:
        outcome["roster_report"] = evaluate_roster(
            inputs["horizon"], inputs["employees"], inputs["rules"], inputs["roster"],
            required_staffing=inputs["required_staffing"],
        )
    except SharedSegmentError as error:
        problems += error.problems
    if problems:
        return failed("workforce", problems)

    # Additional structural check only (OD-4): the engine's own validation and the X4 precondition, with
    # no customers and no random numbers. Its result is discarded.
    try:
        simulate_named_prescribed(
            inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
            [], closing_policy=body.closing_policy, employee_policy=_employee_policy(body),
            required_staffing=inputs["required_staffing"], max_trace_events=0,
        )
    except SharedSegmentError as error:
        return failed("engine", error.problems)
    return outcome


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _typed(value: Any) -> Any:
    """A comparison form that keeps what JSON storage can change: int, float bits, and bool are distinct.

    Arrays compare equal whether they are lists or tuples (JSON has only arrays, and the input digest
    treats them identically). Anything else is kept as is, so a value of an unexpected type differs.
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, Integral):
        return ("int", int(value))
    if isinstance(value, float):
        return ("float", value.hex())
    if isinstance(value, (list, tuple)):
        return ("array", [_typed(item) for item in value])
    if isinstance(value, dict):
        return ("object", {key: _typed(item) for key, item in value.items()})
    return value


def _differing_keys(expected: dict[str, Any], actual: Any) -> list[str]:
    if not isinstance(actual, dict):
        return ["<row>"]
    return sorted(str(key) for key in set(expected) | set(actual) if _typed(expected.get(key)) != _typed(actual.get(key)))


def _persistence_identity_checks(pre: dict[str, Any], persisted: Any) -> list[dict[str, Any]]:
    """B1 step 5-6: what differs between the computed run and the database's representation of it."""
    expected_provenance = pre["provenance"]
    try:
        provenance = persisted["provenance"]
        rows = persisted["replications"]
        fingerprint = named_inputs_digest(
            provenance["inputs"], provenance["closing_policy"], provenance["employee_policy"])
    except (KeyError, TypeError, SharedSegmentError) as error:
        return [{"check": "persisted_structure", "message": f"The persisted run cannot be read back: {error}."}]

    checks: list[dict[str, Any]] = []
    recorded = expected_provenance["inputs_sha256"]
    if fingerprint != recorded:
        checks.append({"check": "inputs_fingerprint", "message": "The persisted inputs no longer reproduce the "
                       "recorded inputs_sha256.", "computed": recorded, "persisted": fingerprint})
    if _typed(provenance.get("inputs_sha256")) != _typed(recorded):
        checks.append({"check": "recorded_fingerprint", "message": "The persisted inputs_sha256 differs.",
                       "computed": recorded, "persisted": provenance.get("inputs_sha256")})
    expected_rows = pre["replications"]
    if not isinstance(rows, list) or len(rows) != len(expected_rows):
        checks.append({"check": "stored_row_count", "message": "The persisted run has a different number of rows."})
    else:
        for index, (expected, actual) in enumerate(zip(expected_rows, rows)):
            differing = _differing_keys(expected, actual)
            if differing:
                checks.append({"check": "stored_row", "replication_index": index, "fields": differing,
                               "message": f"Replication {index}'s persisted row differs from the computed row."})
    for key in REQUIRED_PROVENANCE:
        if _typed(expected_provenance.get(key)) != _typed(provenance.get(key)):
            checks.append({"check": "provenance", "field": key,
                           "message": f"The persisted provenance field {key} differs from the computed value."})
    return checks


def _reread_result_json(db: Session, job_id: int) -> Any:
    """The persisted result as the database returns it, read inside the current transaction.

    A column select returns the database's value, never the ORM identity map's object (B1 step 4).
    """
    return db.execute(select(Job.result_json).where(Job.id == job_id)).scalar_one()


def _safe(evidence: Any) -> Any:
    """Refusal evidence as JSON; anything that cannot be encoded is shown as its repr, never dropped."""
    try:
        return json.loads(json.dumps(evidence, allow_nan=False, default=str))
    except (TypeError, ValueError):
        return {"repr": repr(evidence)[:2000]}


def _refuse(status: int, failure: dict[str, Any], code: str) -> NoReturn:
    raise HTTPException(status_code=status, detail={
        "code": code, "check": failure.get("check"), "message": failure.get("message"),
        "evidence": _safe(failure.get("evidence") or {}),
    })


def _named_job(db: Session, user: User, analysis: AnalysisProject, run_id: int) -> Job:
    job = db.get(Job, run_id)
    if (job is None or job.user_id != user.id or job.kind != JOB_KIND or job.status != "completed"
            or (job.params_json or {}).get("analysis_id") != analysis.id):
        raise HTTPException(status_code=404, detail={"code": "run_not_found"})
    return job


def _setup_matches_current(job: Job, analysis: AnalysisProject) -> bool:
    return (job.params_json or {}).get("setup_hash") == setup_fingerprint(analysis.queue_setup_json)


# ── Routes (spec section 4) ─────────────────────────────────────────────────


@router.get("/{analysis_id}/shared-named/contract")
def named_contract(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """R1: eligibility, approved selections, provisional limits, and versions. Nothing is persisted."""
    analysis = own_analysis(db, user, analysis_id)
    reasons = _ineligible_reasons(analysis)
    return {
        "eligible": not reasons,
        "ineligible_reasons": reasons,
        "closing_policies": list(CLOSING_POLICIES),
        "employee_policy": {
            item.name: {"approved": getattr(APPROVED_EMPLOYEE_POLICY, item.name), "meaning": POLICY_MEANINGS[item.name]}
            for item in fields(EmployeeDesPolicy)
        },
        "limits": _limits(settings),
        "seed": {"min": 0, "max": SEED_MAX},
        "versions": {
            "named_api_version": NAMED_API_VERSION,
            "method_version": METHOD_VERSION,
            "named_engine_version": NAMED_ENGINE_VERSION,
        },
        "verdict": None,
        "verdict_reason": NO_VERDICT_REASON,
        "model_scope": MODEL_SCOPE,
    }


@router.post("/{analysis_id}/shared-named/validate")
def validate_named_inputs(
    analysis_id: int,
    body: NamedWorkforceInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """R2: validate the inputs against the selected dataset's demand and the domain rules. Nothing is persisted."""
    analysis = own_analysis(db, user, analysis_id)
    _require_eligible(analysis)
    dataset = _selected_dataset(db, user, analysis, body.dataset_id)
    _require_within_limits(body)
    outcome = _check_inputs(body, dataset)
    periods = outcome["demand_periods"]
    per_replication = None if periods is None else _expected_customers_per_replication(body, periods)
    if per_replication is not None:  # not even one replication fits the run-time bound (section 22.8)
        _require_within_customer_bound(per_replication, 1)
    return {
        "runnable": outcome["stage_failed"] is None,
        "stage_failed": outcome["stage_failed"],
        "problems": outcome["problems"],
        "demand": None if periods is None else {
            "dataset_id": dataset.id, "demand_periods": [asdict(period) for period in periods],
            "expected_customers_per_replication": per_replication},
        "roster_report": outcome["roster_report"],
        "limits": _limits(settings),
    }


@router.post("/{analysis_id}/shared-named/runs")
def create_named_run(
    analysis_id: int,
    body: NamedRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """R3: run seeded named replications and persist one verified Job (B1)."""
    analysis = own_analysis(db, user, analysis_id)
    _require_eligible(analysis)
    dataset = _selected_dataset(db, user, analysis, body.dataset_id)
    if analysis.archived_at is not None:  # OD-7: before any computation
        raise HTTPException(status_code=409, detail={"code": "analysis_archived"})
    _require_within_limits(body, body.replications)

    outcome = _check_inputs(body, dataset)
    if outcome["stage_failed"] is not None:
        raise HTTPException(status_code=422, detail={
            "code": "named_input_invalid", "stage": outcome["stage_failed"], "problems": outcome["problems"]})
    _require_within_customer_bound(
        _expected_customers_per_replication(body, outcome["demand_periods"]), body.replications)
    inputs = outcome["inputs"]
    try:
        result = run_named_replications(
            inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
            replications=body.replications, seed=body.seed, closing_policy=body.closing_policy,
            employee_policy=_employee_policy(body), required_staffing=inputs["required_staffing"],
        )
    except SharedSegmentError as error:
        raise HTTPException(status_code=422, detail={
            "code": "named_input_invalid", "stage": "engine", "problems": error.problems}) from None

    try:  # measured exactly as workflow._save_job measures evidence
        encoded = json.dumps(result, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        logger.exception("event=shared_named_result_not_serializable analysis_id=%s", analysis.id)
        raise HTTPException(status_code=500, detail={"code": "result_not_serializable"}) from None
    if len(encoded) > settings.result_jsonb_max_bytes:
        raise HTTPException(status_code=413, detail={
            "code": "evidence_too_large", "bytes": len(encoded), "max_bytes": settings.result_jsonb_max_bytes})

    provenance = result["provenance"]
    # B1 step 2: the pre-persistence fingerprint must be the one the run recorded.
    if named_inputs_digest(provenance["inputs"], provenance["closing_policy"],
                           provenance["employee_policy"]) != provenance["inputs_sha256"]:
        logger.error("event=shared_named_digest_inconsistent analysis_id=%s", analysis.id)
        raise HTTPException(status_code=500, detail={"code": "inputs_digest_inconsistent"})

    job = Job(
        user_id=user.id,
        kind=JOB_KIND,
        status="completed",
        params_json={
            "analysis_id": analysis.id,
            "scenario_id": None,
            "dataset_id": dataset.id,
            "replications": body.replications,
            "seed": body.seed,
            "closing_policy": body.closing_policy,
            # Server keys, written after the request keys so no request value can replace them.
            "named_api_version": NAMED_API_VERSION,
            "engine_version": provenance["method_version"],
            "method_version": provenance["method_version"],
            "named_engine_version": provenance["named_engine_version"],
            "state_machine_version": provenance["state_machine_version"],
            "arrival_engine_version": provenance["arrival_engine_version"],
            "inputs_sha256": provenance["inputs_sha256"],
            "root_entropy": provenance["root_entropy"],
            "dataset_generation": dataset.generation,  # OD-2: the selected row's G-A token, as stored
            "setup_hash": setup_fingerprint(analysis.queue_setup_json),
        },
        result_json=result,
        tenant_id=user.tenant_id,
        finished_at=datetime.now(timezone.utc),
    )
    # B1 steps 3-6: insert, re-read the database's representation in the same transaction, and commit
    # only on exact agreement. On any difference nothing is committed and no run id is exposed.
    try:
        db.add(job)
        db.flush()
        checks = _persistence_identity_checks(result, _reread_result_json(db, job.id))
    except BaseException:
        db.rollback()
        raise
    if checks:
        db.rollback()
        logger.warning("event=shared_named_persistence_identity_mismatch analysis_id=%s checks=%s",
                       analysis.id, [item["check"] for item in checks])
        raise HTTPException(status_code=422, detail={"code": "persistence_identity_mismatch", "checks": _safe(checks)})
    db.commit()
    db.refresh(job)
    return {"evidence": _job_out(job)}


@router.get("/{analysis_id}/shared-named/runs")
def list_named_runs(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """R4: this analysis's named runs, newest first, in compact form."""
    analysis = own_analysis(db, user, analysis_id)
    jobs = db.execute(
        select(Job)
        .where(Job.user_id == user.id, Job.kind == JOB_KIND, Job.status == "completed")
        .order_by(Job.id.desc())
    ).scalars()
    runs = []
    for job in jobs:
        params = job.params_json or {}
        if params.get("analysis_id") != analysis.id:
            continue
        provenance = (job.result_json or {}).get("provenance") or {}
        runs.append({
            "id": job.id,
            "created_at": job.created_at,
            "dataset_id": params.get("dataset_id"),
            "replications": params.get("replications"),
            "seed": params.get("seed"),
            "root_entropy": params.get("root_entropy"),
            "closing_policy": params.get("closing_policy"),
            "inputs_sha256": params.get("inputs_sha256"),
            "method_version": params.get("method_version"),
            "named_engine_version": params.get("named_engine_version"),
            "runtime": provenance.get("runtime"),
            "setup_matches_current": _setup_matches_current(job, analysis),
        })
    return {"runs": runs}


@router.get("/{analysis_id}/shared-named/runs/{run_id}")
def get_named_run(
    analysis_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """R5: the stored run, unchanged."""
    analysis = own_analysis(db, user, analysis_id)
    job = _named_job(db, user, analysis, run_id)
    return {"evidence": _job_out(job), "setup_matches_current": _setup_matches_current(job, analysis)}


@router.get("/{analysis_id}/shared-named/runs/{run_id}/replications/{replication_index}")
def named_replication(
    analysis_id: int,
    run_id: int,
    replication_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """R6: regenerate replication i, validate it, and return its playback and attribution. Nothing is persisted."""
    analysis = own_analysis(db, user, analysis_id)
    job = _named_job(db, user, analysis, run_id)
    stored: dict[str, Any] = job.result_json if isinstance(job.result_json, dict) else {}
    provenance: dict[str, Any] = stored["provenance"] if isinstance(stored.get("provenance"), dict) else {}
    total: Any = provenance.get("replications")
    if not _whole(total) or not 0 <= replication_index < total:
        raise HTTPException(status_code=404, detail={
            "code": "replication_not_found", "max_index": total - 1 if _whole(total) else None})

    # Step 3: the protected regeneration and refusal contract, unchanged.
    try:
        playback = playback_from_named_replications(stored, replication_index)
    except NamedPlaybackError as error:
        if error.failure.get("check") in REGENERATION_CHECKS:
            _refuse(409, error.failure, "regeneration_identity")
        logger.error("event=shared_named_playback_check_failed run_id=%s check=%s", job.id, error.failure.get("check"))
        _refuse(500, error.failure, "playback_check_failed")

    # Step 4: the approved D6 regeneration for attribution, guarded by the stored row (OD-1).
    inputs = rebuild_named_inputs(provenance["inputs"])
    regenerated = simulate_named_replication(
        inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
        seed_sequence=replication_seed_sequence(provenance["root_entropy"], replication_index),
        closing_policy=provenance["closing_policy"], employee_policy=EmployeeDesPolicy(**provenance["employee_policy"]),
        required_staffing=inputs["required_staffing"], max_trace_events=0,
    )
    row = named_replication_row(regenerated, replication_index)
    stored_row = stored["replications"][replication_index]
    differing = sorted(key for key in set(row) | set(stored_row) if row.get(key) != stored_row.get(key))
    if differing:
        raise HTTPException(status_code=409, detail={
            "code": "regeneration_identity", "check": "attribution_stored_row", "fields": differing,
            "message": f"The regenerated replication {replication_index} differs from the stored row.",
            "evidence": {"fields": differing}})

    # Step 5.
    try:
        attribution = build_named_attribution(regenerated, inputs["employees"])
    except NamedAttributionError as error:
        logger.error("event=shared_named_attribution_check_failed run_id=%s check=%s", job.id, error.failure.get("check"))
        _refuse(500, error.failure, "attribution_check_failed")

    playback_provenance = playback["provenance"]
    return {
        "replication_index": replication_index,
        "playback": playback,
        "attribution": attribution,
        "regeneration": {
            "runtime_matches_recorded": playback_provenance["runtime_matches_recorded"],
            "runtime_recorded": playback_provenance["runtime_recorded"],
            "runtime_current": playback_provenance.get("runtime"),
            "basis": playback_provenance["regeneration_basis"],
        },
    }
