"""Analysis workspace CRUD and ownership-scoped workflow endpoints."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analysis_schemas import STORED_SETUP, QueueSetup, setup_status, unknown_queue_setup
from backend.api.current_dataset import PLANNING, REVIEW, is_successfully_processed, resolve_current_dataset
from backend.api.datasets import _to_out as dataset_out
from backend.api.datasets import current_dataset_ids
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.scenarios import scenario_out
from backend.api.settings import Settings
from backend.api.shared_aggregate_upload import router as shared_aggregate_upload_router
from backend.data import uploads
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input
from backend.data.setup_derivation import SetupExportError, derive_setup, setup_diff, setup_workbook
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.data_processing import compute_kpis
from backend.queueing_engine.services.model_explanations import analyze_segments

router = APIRouter(prefix="/analyses", tags=["analyses"])
router.include_router(shared_aggregate_upload_router)


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    service_type: str | None = Field(default=None, max_length=100)
    location_label: str | None = Field(default=None, max_length=255)
    queue_setup: QueueSetup = Field(default_factory=unknown_queue_setup)


class AnalysisPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    service_type: str | None = Field(default=None, max_length=100)
    location_label: str | None = Field(default=None, max_length=255)
    queue_setup: QueueSetup | None = None


class AnalysisOut(BaseModel):
    id: int
    name: str
    service_type: str | None
    location_label: str | None
    queue_setup: QueueSetup
    setup_status: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _to_out(analysis: AnalysisProject) -> dict:
    # A stored Setup is read back without the new-input break checks.
    return AnalysisOut.model_validate({
        "id": analysis.id,
        "name": analysis.name,
        "service_type": analysis.service_type,
        "location_label": analysis.location_label,
        "queue_setup": analysis.queue_setup_json,
        "setup_status": analysis.setup_status,
        "archived_at": analysis.archived_at,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }, context=STORED_SETUP).model_dump(mode="json")


def own_analysis(db: Session, user: User, analysis_id: int) -> AnalysisProject:
    analysis = db.get(AnalysisProject, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@router.get("")
def list_analyses(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(AnalysisProject).where(AnalysisProject.user_id == user.id)
    if not include_archived:
        query = query.where(AnalysisProject.archived_at.is_(None))
    analyses = db.execute(query.order_by(AnalysisProject.updated_at.desc(), AnalysisProject.id.desc())).scalars()
    return {"analyses": [_to_out(item) for item in analyses]}


@router.post("", status_code=201)
def create_analysis(
    payload: AnalysisCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    analysis = AnalysisProject(
        user_id=user.id,
        name=payload.name.strip(),
        service_type=payload.service_type,
        location_label=payload.location_label,
        queue_setup_json=payload.queue_setup.model_dump(mode="json"),
        setup_status=setup_status(payload.queue_setup),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return {"analysis": _to_out(analysis)}


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return {"analysis": _to_out(own_analysis(db, user, analysis_id))}


@router.patch("/{analysis_id}")
def patch_analysis(
    analysis_id: int,
    payload: AnalysisPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    supplied = payload.model_fields_set
    if "name" in supplied:
        analysis.name = payload.name.strip()  # type: ignore[union-attr]
    if "service_type" in supplied:
        analysis.service_type = payload.service_type
    if "location_label" in supplied:
        analysis.location_label = payload.location_label
    if payload.queue_setup is not None:
        analysis.queue_setup_json = payload.queue_setup.model_dump(mode="json")
        analysis.setup_status = setup_status(payload.queue_setup)
    analysis.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    return {"analysis": _to_out(analysis)}


@router.post("/{analysis_id}/archive")
def archive_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    analysis.archived_at = datetime.now(timezone.utc)
    analysis.updated_at = analysis.archived_at
    db.commit()
    db.refresh(analysis)
    return {"analysis": _to_out(analysis)}


@router.get("/{analysis_id}/datasets")
def list_analysis_datasets(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    own_analysis(db, user, analysis_id)
    items = db.execute(
        select(Dataset)
        .where(Dataset.user_id == user.id, Dataset.analysis_id == analysis_id)
        .order_by(Dataset.id.desc())
    ).scalars().all()
    current = current_dataset_ids(db, user.id, [analysis_id])
    return {"datasets": [dataset_out(item, is_current=item.id in current) for item in items]}


@router.post("/{analysis_id}/datasets", status_code=201)
def upload_analysis_dataset(
    analysis_id: int,
    file: UploadFile = File(...),
    name: str | None = None,
    apply_setup: bool = False,
    purpose: Literal["planning", "review"] = "planning",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    if analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived analyses cannot accept uploads.")
    if purpose == REVIEW and apply_setup:
        # B10: a review-only file is for reading; it must never change the Setup.
        raise HTTPException(status_code=422, detail={"code": "review_cannot_change_setup"})
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")
    if apply_setup:
        return _apply_setup_upload(db, analysis, user, file.filename or "", data, name, settings)
    try:
        frame = uploads.sanitize_workbook(
            uploads.parse_upload(
                file.filename or "",
                data,
                settings.max_upload_bytes,
                xlsx_max_uncompressed_bytes=settings.xlsx_max_uncompressed_bytes,
                xlsx_max_zip_members=settings.xlsx_max_zip_members,
                xlsx_max_compression_ratio=settings.xlsx_max_compression_ratio,
                xlsx_max_worksheets=settings.xlsx_max_worksheets,
                max_rows=settings.upload_max_rows,
                max_columns=settings.upload_max_columns,
                max_cell_chars=settings.upload_max_cell_chars,
                max_dataframe_bytes=settings.upload_max_dataframe_bytes,
            )
        )
        stored = QueueSetup.model_validate(analysis.queue_setup_json, context=STORED_SETUP)
        records, provenance = normalize_analysis_input(frame, stored)
    except (uploads.UploadError, AnalysisIngestionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    safe_filename = uploads.safe_stem(file.filename or "upload")
    dataset = Dataset(
        user_id=user.id,
        analysis_id=analysis.id,
        name=(name or Path(safe_filename).stem)[:255],
        source_filename=safe_filename[:255],
        source_format=Path(safe_filename).suffix.lower().lstrip("."),
        row_count=len(records),
        normalized_json=records,
        validation_report_json={"ok": True, "message": "Input data is valid.", **provenance},
        purpose=purpose,
    )
    analysis.updated_at = datetime.now(timezone.utc)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    current = current_dataset_ids(db, user.id, [analysis.id])
    return {"dataset": dataset_out(dataset, include_normalized=True, is_current=dataset.id in current)}


def _upload_limits(settings: Settings) -> dict:
    return {
        "xlsx_max_uncompressed_bytes": settings.xlsx_max_uncompressed_bytes,
        "xlsx_max_zip_members": settings.xlsx_max_zip_members,
        "xlsx_max_compression_ratio": settings.xlsx_max_compression_ratio,
        "xlsx_max_worksheets": settings.xlsx_max_worksheets,
        "max_rows": settings.upload_max_rows,
        "max_columns": settings.upload_max_columns,
        "max_cell_chars": settings.upload_max_cell_chars,
        "max_dataframe_bytes": settings.upload_max_dataframe_bytes,
    }


def _read_setup_sheets(filename: str, data: bytes, settings: Settings) -> dict | None:
    """Setup workbook sheets (sanitized), or None for legacy files."""
    try:
        sheets = uploads.parse_upload_workbook(filename, data, settings.max_upload_bytes, **_upload_limits(settings))
    except uploads.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if sheets is None:
        return None
    return {key: None if frame is None else uploads.sanitize_workbook(frame) for key, frame in sheets.items()}


def _apply_setup_upload(db: Session, analysis: AnalysisProject, user: User, filename: str, data: bytes,
                        name: str | None, settings: Settings) -> dict:
    """Save the Setup derived from a three-sheet upload and its dataset in one commit."""
    sheets = _read_setup_sheets(filename, data, settings)
    if sheets is None:
        raise HTTPException(status_code=422, detail="apply_setup requires a workbook with an events sheet.")
    derivation = derive_setup(sheets, analysis.queue_setup_json)
    if derivation.errors or derivation.setup is None:
        raise HTTPException(status_code=422, detail=" ".join(derivation.errors))
    setup = QueueSetup.model_validate(derivation.setup)
    safe_filename = uploads.safe_stem(filename or "upload")
    records = derivation.records
    dataset = Dataset(
        user_id=user.id,
        analysis_id=analysis.id,
        name=(name or Path(safe_filename).stem)[:255],
        source_filename=safe_filename[:255],
        source_format=Path(safe_filename).suffix.lower().lstrip("."),
        row_count=len(records),
        normalized_json=records,
        validation_report_json={"ok": True, "message": "Input data is valid.", **derivation.provenance},
    )
    analysis.queue_setup_json = setup.model_dump(mode="json")
    analysis.setup_status = setup_status(setup)
    analysis.updated_at = datetime.now(timezone.utc)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    current = current_dataset_ids(db, user.id, [analysis.id])
    return {"dataset": dataset_out(dataset, include_normalized=True, is_current=dataset.id in current)}


@router.post("/{analysis_id}/datasets/preview")
def preview_analysis_dataset(
    analysis_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    """Show the Setup a three-sheet upload would derive. Nothing is stored."""
    analysis = own_analysis(db, user, analysis_id)
    if analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived analyses cannot accept uploads.")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")
    sheets = _read_setup_sheets(file.filename or "", data, settings)
    if sheets is None:
        return {"mode": "legacy"}
    saved = QueueSetup.model_validate(analysis.queue_setup_json or {}, context=STORED_SETUP).model_dump(mode="json")
    derivation = derive_setup(sheets, saved)
    diff = setup_diff(saved, derivation.setup) if derivation.setup is not None else []
    return {
        "mode": "multi_sheet",
        "derived_setup": derivation.setup,
        "saved_setup": saved,
        "diff": diff,
        "needs_confirmation": saved["queue_structure"] != "unknown" and bool(diff),
        "staff": derivation.staff_rows,
        "breaks": derivation.break_rows,
        "errors": derivation.errors,
    }


@router.get("/{analysis_id}/setup/workbook")
def export_setup_workbook(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The Setup's staff and breaks sheets, ready to re-upload with the events sheet."""
    analysis = own_analysis(db, user, analysis_id)
    try:
        content = setup_workbook(analysis.queue_setup_json or {})
    except SetupExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="novaq_setup_{analysis.id}.xlsx"'},
    )


def arrivals_by_period(records: list) -> list[dict]:
    """B12: customers arriving per hour in each period, every line summed, in period order.

    The browser must not add these up itself. A period whose rows carry no finite arrival
    rate reports None rather than a partial sum.
    """
    order: list[str] = []
    sums: dict[str, float | None] = {}
    for row in records or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("time", row.get("segment_id", "")))
        if label not in sums:
            order.append(label)
            sums[label] = 0.0
        raw = row.get("lambda")
        try:
            value = float(raw) if raw is not None else math.nan
        except (TypeError, ValueError):
            value = math.nan
        total = sums[label]
        sums[label] = None if total is None or not math.isfinite(value) or value < 0 else total + value
    return [{"time": label, "arrivals_per_hour": sums[label]} for label in order]


def busiest_period(periods: list[dict]) -> dict | None:
    """B12: the period with the most arrivals per hour (first one on a tie), or None."""
    known = [period for period in periods if period["arrivals_per_hour"] is not None]
    if not known:
        return None
    return max(known, key=lambda period: period["arrivals_per_hour"])


def reviewable_dataset(db: Session, user: User, analysis: AnalysisProject, dataset_id: int) -> Dataset:
    """B3: any successfully processed file of this analysis, for read-only results.

    A review-only file is allowed here; plans, selection and Decision stay on the planning file.
    """
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id or dataset.analysis_id != analysis.id:
        raise HTTPException(status_code=404, detail="Dataset not found in this Analysis.")
    if not is_successfully_processed(dataset):
        raise HTTPException(status_code=409, detail={"code": "dataset_not_processed"})
    return dataset


@router.get("/{analysis_id}/current")
def current_analysis(
    analysis_id: int,
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    dataset: Dataset | None
    if dataset_id is not None:
        dataset = reviewable_dataset(db, user, analysis, dataset_id)
        is_current = dataset.id in current_dataset_ids(db, user.id, [analysis.id])
    else:
        dataset = resolve_current_dataset(db, owner_id=user.id, analysis_id=analysis_id).dataset
        is_current = True
    if dataset is None:
        raise HTTPException(status_code=404, detail="This Analysis has no successfully processed dataset.")
    frame, explanations, selected_model = analyze_segments(
        dataset.normalized_json or [],
        analysis.queue_setup_json or {},
        dataset.validation_report_json or {},
    )
    rows = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    periods = arrivals_by_period(dataset.normalized_json or [])
    return {
        "analysis": _to_out(analysis),
        "dataset": dataset_out(dataset, include_normalized=True, is_current=is_current),
        "selected_model": selected_model,
        "rows": rows,
        "kpis": compute_kpis(frame),
        "explanations": explanations,
        "arrivals_by_period": periods,
        "busiest_period": busiest_period(periods),
    }


@router.get("/{analysis_id}/scenarios")
def list_analysis_scenarios(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    own_analysis(db, user, analysis_id)
    items = db.execute(
        select(Scenario)
        .where(Scenario.user_id == user.id, Scenario.analysis_id == analysis_id)
        .order_by(Scenario.id.desc())
    ).scalars()
    consistent = [
        item
        for item in items
        if item.dataset_id is None
        or (item.dataset is not None and item.dataset.user_id == user.id and item.dataset.analysis_id == analysis_id)
    ]
    return {"scenarios": [scenario_out(db, user, item) for item in consistent]}
