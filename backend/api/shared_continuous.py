"""B4a: the continuous shared-line run (preview) for an ordinary analysis — the second thin adapter.

Spec: docs/superpowers/specs/2026-10-09-b4a-continuous-shared-run-preview.md (owner answers OD-B4a-1..3 = A).
B4b (docs/superpowers/specs/2026-10-09-b4b-recorded-service-times.md): a customer-record upload runs with its
recorded service durations, its periods laid out by the Setup's operating segments.
Like ``shared_named`` (A6), this module is allowed to import the shared-queue enhancement modules; the
isolation guard in tests/test_shared_segments.py names it. It authenticates, authorizes, picks the
staffing source (the current planning dataset's ``c``, or the selected plan's ``c_optimal``), maps rows
onto the engine's timeline, refuses what the engine does not cover, calls the engine, and persists one
Job per run. Every queueing rule is the engine's and is surfaced unchanged; the only arithmetic here is
the expected-customer bound (as the named run computes it) and the per-period counts of one replayed day.

Nothing here touches ``/simulation/*``, ``/optimize/*``, workflow evidence currentness, Compare, the
Decision or Reports. No pass/fail verdict exists (OD-UX-13 open), and none is produced.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analyses import own_analysis
from backend.api.current_dataset import CurrentDatasetStatus, resolve_current_dataset
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.scenarios import setup_fingerprint
from backend.api.settings import Settings
from backend.api.shared_named import C_MAX, LIMITS_STATUS, N_MAX, SEED_MAX
from backend.api.workflow import _job_out, _segments_for, _selected_scenario_and_dataset
from backend.data.analysis_ingestion import DES_EMPIRICAL_SOURCE
from backend.db.models import AnalysisProject, Dataset, Job, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    format_clock,
    parse_clock,
    timeline_from_aggregate_rows,
    validate_timeline,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    CLOSING_POLICIES,
    CLOSING_RULES,
    RECORDED,
    CounterBreak,
    resolve_service_samples,
)
from backend.queueing_engine.simulation.shared_playback import PlaybackConsistencyError, playback_from_replications
from backend.queueing_engine.simulation.shared_replications import NO_VERDICT_REASON, run_shared_replications
from backend.queueing_engine.simulation.simulation import RANDOM_SEED

router = APIRouter(prefix="/analyses", tags=["shared-continuous"])
logger = logging.getLogger("novaq.api.shared_continuous")

JOB_KIND = "shared_continuous_preview"
API_VERSION = "novaq-shared-continuous-preview-api-v1"
DEFAULT_REPLICATIONS = 5  # OD-B4a-3 A
EXPONENTIAL = "exponential"
PREVIEW_SCOPE = (
    "Preview: Poisson arrivals, first come first served, unlimited waiting room. Customer-record uploads use "
    "their recorded service durations (B4b); counts per period use exponential service (M/M/c). Counter breaks "
    "from the Setup are taken by the first free counter (B4c)."
)

Plan = Literal["current", "suggested"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClosingPolicyIn(_Strict):
    closing_policy: Literal["DRAIN", "HARD_CUTOFF"]


class RunIn(_Strict):
    plan: Plan
    replications: StrictInt = Field(default=DEFAULT_REPLICATIONS, ge=1, le=N_MAX)
    seed: StrictInt = Field(default=RANDOM_SEED, ge=0, le=SEED_MAX)


def _limits(settings: Settings) -> dict[str, Any]:
    return {"max_replications": N_MAX, "max_expected_customers_per_run": C_MAX,
            "result_max_bytes": settings.result_jsonb_max_bytes, "status": LIMITS_STATUS}


def _reason(code: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, **extra}


def _setup_reasons(setup: dict[str, Any]) -> list[dict[str, Any]]:
    """Setup gates, as the named run applies them; unknown capacity or abandonment is never read as absent."""
    structure = setup.get("queue_structure")
    if structure == "separate_queues":
        return [_reason("separate_lines")]
    if structure != "shared_queue":
        return [_reason("not_shared_line")]
    capacity, abandonment = setup.get("capacity_mode"), setup.get("abandonment_mode")
    if capacity not in ("unlimited", "unknown") or abandonment not in ("not_modeled", "unknown"):
        return [_reason("capacity_or_abandonment")]
    if capacity == "unknown" or abandonment == "unknown":
        # Still refused (unknown is never read as absent), but the user only has to answer the two questions.
        return [_reason("capacity_or_abandonment_unknown")]
    return []


def _row_reasons(rows: list[Any], recorded: bool = False) -> list[dict[str, Any]]:
    """What the engine's timeline mapping would reject, named so the page can say it in plain words.

    Recorded service durations replace the variance of a customer-record upload, so it is not refused there.
    """
    reasons = []
    if not recorded and any(isinstance(row, dict) and row.get("variance") is not None for row in rows):
        reasons.append(_reason("service_time_variation"))
    if any(isinstance(row, dict) and (row.get("K") is not None or row.get("theta") is not None) for row in rows):
        reasons.append(_reason("capacity_or_abandonment"))
    return reasons


def _timeline(rows: list[Any]) -> tuple[OperatingHorizon, list[DemandPeriod], list[StaffingSegment]]:
    periods, segments = timeline_from_aggregate_rows([row if isinstance(row, dict) else {} for row in rows])
    if not periods:
        raise SharedSegmentError(["The data has no periods."])
    horizon = OperatingHorizon(min(p.start_minute for p in periods), max(p.end_minute for p in periods))
    validate_timeline(horizon, periods, segments)
    return horizon, periods, segments


def _is_recorded(dataset_rows: list[Any]) -> bool:
    """A customer-record upload: its rows carry the durations customers took (``analysis_ingestion``)."""
    return any(isinstance(row, dict) and row.get("service_time_source") == DES_EMPIRICAL_SOURCE for row in dataset_rows)


def _recorded_reasons(setup: dict[str, Any], dataset_rows: list[Any]) -> list[dict[str, Any]]:
    """B4b runs one representative day whose every row carries recorded durations."""
    reasons = []
    if setup.get("event_period_basis") != "representative_day":
        reasons.append(_reason("per_date_data"))
    if not all(isinstance(row, dict) and row.get("service_time_source") == DES_EMPIRICAL_SOURCE
               and isinstance(row.get("service_samples_hours"), list) and row["service_samples_hours"]
               for row in dataset_rows):
        reasons.append(_reason("service_time_variation"))
    return reasons


def _setup_minute(value: object, where: str) -> int:
    """Minutes since midnight of a Setup time ``HH:MM`` or ``HH:MM:SS`` (whole minutes only)."""
    text = value if isinstance(value, str) else ""
    if len(text) == 8 and text[5:] == ":00":
        text = text[:5]
    try:
        return parse_clock(text)
    except SharedSegmentError:
        raise SharedSegmentError([f"{where} time {value!r} must be a whole minute such as 08:00."]) from None


def _setup_segments(setup: dict[str, Any]) -> list[tuple[str, int, int]]:
    """The Setup's operating segments as (id, start, end) in time order, with the id the upload labels rows by."""
    items = []
    for segment in setup.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        start = _setup_minute(segment.get("start_time"), "Operating segment start")
        end = _setup_minute(segment.get("end_time"), "Operating segment end")
        items.append((str(segment.get("id") or f"{format_clock(start)}-{format_clock(end)}"), start, end))
    if not items:
        raise SharedSegmentError(["The Setup has no operating segments to lay out the day."])
    return sorted(items, key=lambda item: item[1])


def _recorded_timeline(setup: dict[str, Any], rows: list[Any], dataset_rows: list[Any], plan: Plan) -> dict[str, Any]:
    """Lay the plan's rows on the Setup's operating segments, with each segment's recorded durations.

    A segment without customers in the data has no row: its arrival rate is 0 and its durations come from
    the nearest recorded period (OD-B4b-2 A). Its server count is the Setup's fixed count for Current
    staffing; a plan has none for it, so a plan run names those segments and does not run.
    """
    segments = _setup_segments(setup)
    ids = [segment_id for segment_id, _, _ in segments]
    by_id = {str(row.get("time")): row for row in rows if isinstance(row, dict)}
    unknown = [key for key in by_id if key not in ids]
    if unknown:
        raise SharedSegmentError([f"Period {key} is not one of the Setup's operating segments ({', '.join(ids)})."
                                  for key in unknown])
    samples = {str(row["time"]): [float(value) for value in row["service_samples_hours"]]
               for row in dataset_rows if str(row.get("time")) in ids}
    placeholders = [DemandPeriod(segment_id, start, end, 0.0, 1.0) for segment_id, start, end in segments]
    resolved, fallbacks = resolve_service_samples(placeholders, samples)
    missing = [segment_id for segment_id in ids if segment_id not in by_id]
    periods: list[DemandPeriod] = []
    staffing: list[StaffingSegment] = []
    for (segment_id, start, end), durations in zip(segments, resolved):
        row = by_id.get(segment_id)
        if row is None:
            periods.append(DemandPeriod(segment_id, start, end, 0.0, len(durations) / math.fsum(durations)))
            servers = setup.get("fixed_server_count")
        else:
            periods.append(DemandPeriod(segment_id, start, end, row.get("lambda"), row.get("mu")))  # type: ignore[arg-type]
            servers = row.get("c")
        if isinstance(servers, float) and servers.is_integer():
            servers = int(servers)
        staffing.append(StaffingSegment(segment_id, start, end, servers))  # type: ignore[arg-type]
    horizon = OperatingHorizon(segments[0][1], max(end for _, _, end in segments))
    validate_timeline(horizon, periods, staffing)
    return {"timeline": (horizon, periods, staffing), "samples": samples, "fallbacks": fallbacks,
            "missing_plan_periods": missing if plan == "suggested" else []}


def _counter_breaks(setup: dict[str, Any], horizon: OperatingHorizon, staffing: list[StaffingSegment]
                    ) -> tuple[list[CounterBreak], list[dict[str, Any]]]:
    """The Setup's counter breaks for the engine, or why this run's staffing cannot hold them (B4c addendum s4).

    A break is refused when it starts outside the operating hours, or when at its start more breaks are
    under way (start <= t < start + length) than counters are scheduled. Nothing is skipped silently.
    """
    entries = [entry for entry in setup.get("counter_breaks") or [] if isinstance(entry, dict)]
    windows = [(_setup_minute(entry.get("scheduled_start_time"), "Counter break start"),
                int(entry.get("duration_minutes") or 0)) for entry in entries]
    outside, unstaffed = [], []
    breaks = []
    for index, (start, minutes) in enumerate(windows, start=1):
        clock = format_clock(start)
        if not horizon.start_minute <= start < horizon.end_minute:
            outside.append(f"Break at {clock} is outside the operating hours "
                           f"{format_clock(horizon.start_minute)}-{format_clock(horizon.end_minute)}.")
            continue
        counters = next(int(item.servers) for item in staffing if item.start_minute <= start < item.end_minute)
        under_way = sum(1 for other, length in windows if other <= start < other + length)
        if under_way > counters:
            unstaffed.append(f"Break at {clock} needs a counter, but this staffing has {counters} counter(s) and "
                             f"{under_way} break(s) at {clock}.")
            continue
        breaks.append(CounterBreak(f"break_{index}", (start - horizon.start_minute) / 60, minutes / 60))
    reasons = []
    if outside:
        reasons.append(_reason("breaks_outside_hours", problems=outside))
    if unstaffed:
        reasons.append(_reason("breaks_not_staffed", problems=unstaffed))
    return breaks, reasons


def _expected_customers_per_day(periods: list[DemandPeriod]) -> float:
    """Sum of arrival rate x period hours (the named run's run-time measure, spec section 22.8)."""
    return math.fsum(p.arrival_rate_per_hour * (p.end_minute - p.start_minute) / 60 for p in periods)


def _period_labels(segments: list[StaffingSegment], rows: list[Any], recorded: bool) -> dict[str, str]:
    """Which plan (or data) period each staffing segment of the run is (OD-UX-13).

    Recorded runs lay the rows on the Setup's segments, whose ids are the rows' labels
    (``_recorded_timeline``). Estimated runs make one segment per row, in row order
    (``timeline_from_aggregate_rows``).
    """
    labels = [str(row.get("time")) for row in rows if isinstance(row, dict)]
    if recorded:
        return {segment.segment_id: segment.segment_id for segment in segments if segment.segment_id in labels}
    if len(segments) != len(labels):
        return {}
    return {segment.segment_id: label for segment, label in zip(segments, labels)}


def _assess(db: Session, user: User, analysis: AnalysisProject, plan: Plan) -> dict[str, Any]:
    """Everything a run of ``plan`` needs, or every reason it cannot run. Runs nothing."""
    setup = analysis.queue_setup_json or {}
    out: dict[str, Any] = {"plan": plan, "dataset": None, "scenario": None, "timeline": None,
                           "expected_customers_per_day": None, "horizon": None, "service_model": None,
                           "service_samples": None, "service_fallbacks": [], "counter_breaks": [],
                           "period_labels": {}}
    reasons = _setup_reasons(setup)
    rows: list[Any] | None = None
    if not reasons:
        if plan == "current":
            resolution = resolve_current_dataset(db, owner_id=user.id, analysis_id=analysis.id)
            if resolution.status is not CurrentDatasetStatus.CURRENT:
                reasons.append(_reason("no_planning_dataset", status=resolution.status.value))
            else:
                out["dataset"] = resolution.dataset
                rows = list((resolution.dataset.normalized_json if resolution.dataset else None) or [])
        else:
            scenario, dataset, _ = _selected_scenario_and_dataset(db, user, analysis)
            if scenario is None or dataset is None:
                reasons.append(_reason("no_selected_plan"))
            else:
                out["scenario"], out["dataset"] = scenario, dataset
                try:
                    rows = _segments_for(scenario, dataset)
                except HTTPException as error:
                    reasons.append(_reason("plan_inputs_invalid", detail=str(error.detail)))
    if rows is not None:
        dataset_rows = list(out["dataset"].normalized_json or [])
        recorded = _is_recorded(dataset_rows)
        out["service_model"] = RECORDED if recorded else EXPONENTIAL
        row_reasons = _row_reasons(rows, recorded) + (_recorded_reasons(setup, dataset_rows) if recorded else [])
        reasons += row_reasons
        if not row_reasons:
            try:
                if recorded:
                    laid_out = _recorded_timeline(setup, rows, dataset_rows, plan)
                    if laid_out["missing_plan_periods"]:
                        reasons.append(_reason("plan_missing_periods", periods=laid_out["missing_plan_periods"]))
                    else:
                        out["timeline"] = laid_out["timeline"]
                        out["service_samples"] = laid_out["samples"]
                        out["service_fallbacks"] = laid_out["fallbacks"]
                else:
                    out["timeline"] = _timeline(rows)
                if out["timeline"] is not None:
                    out["period_labels"] = _period_labels(out["timeline"][2], rows, recorded)
                    out["expected_customers_per_day"] = _expected_customers_per_day(out["timeline"][1])
                    horizon = out["timeline"][0]
                    out["horizon"] = {"start_minute": horizon.start_minute, "end_minute": horizon.end_minute}
                    out["counter_breaks"], break_reasons = _counter_breaks(setup, horizon, out["timeline"][2])
                    reasons += break_reasons
            except SharedSegmentError as error:
                reasons.append(_reason("timeline_invalid", problems=error.problems))
    if analysis.shared_closing_policy not in CLOSING_POLICIES:
        reasons.append(_reason("no_closing_policy"))
    out["reasons"] = reasons
    return out


def _plan_view(assessment: dict[str, Any]) -> dict[str, Any]:
    scenario: Scenario | None = assessment["scenario"]
    dataset: Dataset | None = assessment["dataset"]
    return {
        "compatible": not assessment["reasons"],
        "reasons": assessment["reasons"],
        "expected_customers_per_day": assessment["expected_customers_per_day"],
        "horizon": assessment["horizon"],
        "dataset_id": dataset.id if dataset is not None else None,
        "scenario_id": scenario.id if scenario is not None else None,
        "scenario_name": scenario.name if scenario is not None else None,
        "service_model": assessment["service_model"],
        "service_fallbacks": assessment["service_fallbacks"],
        "counter_breaks": len(assessment["counter_breaks"]),
    }


def _inputs_sha256(inputs: Any) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def _run_job(db: Session, user: User, analysis: AnalysisProject, run_id: int) -> Job:
    job = db.get(Job, run_id)
    if (job is None or job.user_id != user.id or job.kind != JOB_KIND or job.status != "completed"
            or (job.params_json or {}).get("analysis_id") != analysis.id):
        raise HTTPException(status_code=404, detail={"code": "run_not_found"})
    return job


def _currentness(db: Session, user: User, analysis: AnalysisProject, job: Job) -> dict[str, Any]:
    """Whether the Setup, the data and (for a plan run) the selected plan are still the ones the run used."""
    params = job.params_json or {}
    resolution = resolve_current_dataset(db, owner_id=user.id, analysis_id=analysis.id)
    current = resolution.dataset
    plan_selected = None
    if params.get("plan") == "suggested":
        scenario, _, _ = _selected_scenario_and_dataset(db, user, analysis)
        plan_selected = (scenario is not None and scenario.id == params.get("scenario_id")
                         and scenario.generation == params.get("scenario_generation"))
    return {
        "setup_matches_current": params.get("setup_hash") == setup_fingerprint(analysis.queue_setup_json),
        "dataset_is_current": (current is not None and current.id == params.get("dataset_id")
                               and current.generation == params.get("dataset_generation")),
        "plan_is_selected": plan_selected,
    }


def _by_period(playback: dict[str, Any], provenance: dict[str, Any]) -> list[dict[str, Any]]:
    """Arrivals, served customers and their mean wait for each demand period of one replayed day.

    A customer belongs to the last period starting at or before its arrival, so every arrival is
    counted exactly once. The mean wait is over customers of that period who started service.
    """
    horizon_start = provenance["inputs"]["horizon"]["start_minute"]
    periods = [{"period_id": item["period_id"], "start_hours": (item["start_minute"] - horizon_start) / 60,
                "end_hours": (item["end_minute"] - horizon_start) / 60, "arrivals": 0, "served": 0,
                "unserved": 0, "_waits": []} for item in provenance["inputs"]["demand_periods"]]
    periods.sort(key=lambda item: item["start_hours"])
    for customer in playback["customers"]:
        owner = next((p for p in reversed(periods) if p["start_hours"] <= customer["arrival_hours"]), periods[0])
        owner["arrivals"] += 1
        if customer["status"] == "departed":
            owner["served"] += 1
        else:
            owner["unserved"] += 1
        if customer["wait_hours"] is not None:
            owner["_waits"].append(customer["wait_hours"])
    for period in periods:
        waits = period.pop("_waits")
        period["mean_wait_hours"] = math.fsum(waits) / len(waits) if waits else None
    return periods


# ── Routes (spec section 5) ─────────────────────────────────────────────────


@router.get("/{analysis_id}/closing-policy")
def get_closing_policy(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    return {
        "closing_policy": analysis.shared_closing_policy,
        "choices": [{"value": value, "meaning": CLOSING_RULES[value]} for value in CLOSING_POLICIES],
    }


@router.put("/{analysis_id}/closing-policy")
def put_closing_policy(
    analysis_id: int,
    body: ClosingPolicyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Save the rule for future runs. It is not part of the Setup fingerprint; stored runs keep their own."""
    analysis = own_analysis(db, user, analysis_id)
    analysis.shared_closing_policy = body.closing_policy
    db.commit()
    return {"closing_policy": analysis.shared_closing_policy}


@router.post("/{analysis_id}/continuous/compatibility")
def continuous_compatibility(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """Whether each staffing source can run, and why not, before anything runs (D24)."""
    analysis = own_analysis(db, user, analysis_id)
    return {
        "closing_policy": analysis.shared_closing_policy,
        "plans": {plan: _plan_view(_assess(db, user, analysis, plan)) for plan in ("current", "suggested")},
        "default_replications": DEFAULT_REPLICATIONS,
        "default_seed": RANDOM_SEED,
        "limits": _limits(settings),
        "preview": True,
        "model_scope": PREVIEW_SCOPE,
        "verdict": None,
        "verdict_reason": NO_VERDICT_REASON,
    }


@router.post("/{analysis_id}/continuous/runs")
def create_continuous_run(
    analysis_id: int,
    body: RunIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """Run the whole operating day ``replications`` times and persist one Job."""
    analysis = own_analysis(db, user, analysis_id)
    if analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail={"code": "analysis_archived"})
    assessment = _assess(db, user, analysis, body.plan)
    if assessment["reasons"]:
        raise HTTPException(status_code=422, detail={
            "code": "not_compatible", "plan": body.plan, "reasons": assessment["reasons"]})
    horizon, periods, segments = assessment["timeline"]
    per_day = assessment["expected_customers_per_day"]
    expected = per_day * body.replications
    if expected > C_MAX:  # before any simulation (OD-B4a-2 A)
        raise HTTPException(status_code=422, detail={
            "code": "limit_exceeded", "limit": "expected_customers", "value": round(expected, 1), "max": C_MAX,
            "replications": body.replications, "max_replications": math.floor(C_MAX / per_day)})
    closing_policy = str(analysis.shared_closing_policy)  # _assess refused a run with no rule chosen
    samples = assessment["service_samples"]
    if samples is not None:  # the stored run carries its durations, so they alone must fit (before simulating)
        size = len(json.dumps(samples, allow_nan=False).encode("utf-8"))
        if size > settings.result_jsonb_max_bytes:
            raise HTTPException(status_code=413, detail={
                "code": "evidence_too_large", "bytes": size, "max_bytes": settings.result_jsonb_max_bytes})
    try:
        result = run_shared_replications(horizon, periods, segments, replications=body.replications,
                                         seed=body.seed, closing_policy=closing_policy, service_samples=samples,
                                         counter_breaks=assessment["counter_breaks"] or None)
    except SharedSegmentError as error:
        raise HTTPException(status_code=422, detail={
            "code": "not_compatible", "plan": body.plan,
            "reasons": [_reason("timeline_invalid", problems=error.problems)]}) from None

    try:  # measured exactly as workflow._save_job measures evidence
        encoded = json.dumps(result, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        logger.exception("event=shared_continuous_result_not_serializable analysis_id=%s", analysis.id)
        raise HTTPException(status_code=500, detail={"code": "result_not_serializable"}) from None
    if len(encoded) > settings.result_jsonb_max_bytes:
        raise HTTPException(status_code=413, detail={
            "code": "evidence_too_large", "bytes": len(encoded), "max_bytes": settings.result_jsonb_max_bytes})

    dataset: Dataset = assessment["dataset"]
    scenario: Scenario | None = assessment["scenario"]
    provenance = result["provenance"]
    job = Job(
        user_id=user.id,
        kind=JOB_KIND,
        status="completed",
        params_json={
            "analysis_id": analysis.id,
            "plan": body.plan,
            "scenario_id": scenario.id if scenario is not None else None,
            "scenario_generation": scenario.generation if scenario is not None else None,
            "dataset_id": dataset.id,
            "dataset_generation": dataset.generation,
            "replications": body.replications,
            "seed": body.seed,
            "closing_policy": closing_policy,
            "expected_customers_per_day": per_day,
            "service_model": assessment["service_model"],
            "counter_breaks": len(assessment["counter_breaks"]),
            # OD-UX-13: run segment id -> plan period label, for the full-day Decision.
            "period_labels": assessment["period_labels"],
            # Server keys, written after the request keys so no request value can replace them.
            "api_version": API_VERSION,
            "engine_version": provenance["engine_version"],
            "method_version": provenance["method_version"],
            "root_entropy": provenance["root_entropy"],
            "inputs_sha256": _inputs_sha256(provenance["inputs"]),
            "setup_hash": setup_fingerprint(analysis.queue_setup_json),
            "limits_status": LIMITS_STATUS,
            "preview": True,
        },
        result_json=result,
        tenant_id=user.tenant_id,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"evidence": _job_out(job), **_currentness(db, user, analysis, job)}


@router.get("/{analysis_id}/continuous/runs")
def list_continuous_runs(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """This analysis's runs, newest first, in compact form."""
    analysis = own_analysis(db, user, analysis_id)
    jobs = db.execute(
        select(Job).where(Job.user_id == user.id, Job.kind == JOB_KIND, Job.status == "completed")
        .order_by(Job.id.desc())
    ).scalars()
    runs = []
    for job in jobs:
        params = job.params_json or {}
        if params.get("analysis_id") != analysis.id:
            continue
        runs.append({
            "id": job.id, "created_at": job.created_at, "plan": params.get("plan"),
            "scenario_id": params.get("scenario_id"), "dataset_id": params.get("dataset_id"),
            "replications": params.get("replications"), "seed": params.get("seed"),
            "closing_policy": params.get("closing_policy"), "engine_version": params.get("engine_version"),
            # Runs stored before B4b had no recorded mode, so they are exponential.
            "service_model": params.get("service_model") or EXPONENTIAL,
            **_currentness(db, user, analysis, job),
        })
    return {"runs": runs}


@router.get("/{analysis_id}/continuous/runs/{run_id}")
def get_continuous_run(
    analysis_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    analysis = own_analysis(db, user, analysis_id)
    job = _run_job(db, user, analysis, run_id)
    return {"evidence": _job_out(job), **_currentness(db, user, analysis, job)}


@router.get("/{analysis_id}/continuous/runs/{run_id}/replications/{replication_index}/playback")
def continuous_playback(
    analysis_id: int,
    run_id: int,
    replication_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("compute")),
) -> dict[str, Any]:
    """Regenerate one repeated day from its stored seed, check it against the stored row, and replay it."""
    analysis = own_analysis(db, user, analysis_id)
    job = _run_job(db, user, analysis, run_id)
    stored: dict[str, Any] = job.result_json if isinstance(job.result_json, dict) else {}
    provenance: dict[str, Any] = stored["provenance"] if isinstance(stored.get("provenance"), dict) else {}
    total = provenance.get("replications")
    if not isinstance(total, int) or not 0 <= replication_index < total:
        raise HTTPException(status_code=404, detail={"code": "replication_not_found"})
    try:
        playback = playback_from_replications(stored, replication_index)
    except PlaybackConsistencyError as error:
        logger.warning("event=shared_continuous_regeneration_mismatch run_id=%s", job.id)
        raise HTTPException(status_code=409, detail={"code": "regeneration_identity", "message": str(error)}) from None
    return {
        "replication_index": replication_index,
        "playback": playback,
        "by_period": _by_period(playback, provenance),
        "preview": True,
    }

