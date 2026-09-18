"""Analysis workspace CRUD and ownership-scoped workflow endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analysis_schemas import QueueSetup, setup_status, unknown_queue_setup
from backend.api.datasets import _to_out as dataset_out
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.scenarios import _to_out as scenario_out
from backend.api.settings import Settings
from backend.data import uploads
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.data_processing import compute_kpis
from backend.queueing_engine.services.model_explanations import analyze_segments

router = APIRouter(prefix="/analyses", tags=["analyses"])


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
    return AnalysisOut(
        id=analysis.id,
        name=analysis.name,
        service_type=analysis.service_type,
        location_label=analysis.location_label,
        queue_setup=QueueSetup.model_validate(analysis.queue_setup_json),
        setup_status=analysis.setup_status,
        archived_at=analysis.archived_at,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    ).model_dump(mode="json")


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
    ).scalars()
    return {"datasets": [dataset_out(item) for item in items]}


@router.post("/{analysis_id}/datasets", status_code=201)
def upload_analysis_dataset(
    analysis_id: int,
    file: UploadFile = File(...),
    name: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    if analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived analyses cannot accept uploads.")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")
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
        records, provenance = normalize_analysis_input(frame, QueueSetup.model_validate(analysis.queue_setup_json))
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
    )
    analysis.updated_at = datetime.now(timezone.utc)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return {"dataset": dataset_out(dataset, include_normalized=True)}


@router.get("/{analysis_id}/current")
def current_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    analysis = own_analysis(db, user, analysis_id)
    candidates = db.execute(
        select(Dataset)
        .where(Dataset.user_id == user.id, Dataset.analysis_id == analysis_id)
        .order_by(Dataset.id.desc())
    ).scalars()
    dataset = next((item for item in candidates if (item.validation_report_json or {}).get("ok")), None)
    if dataset is None:
        raise HTTPException(status_code=404, detail="This Analysis has no successfully processed dataset.")
    frame, explanations, selected_model = analyze_segments(
        dataset.normalized_json or [],
        analysis.queue_setup_json or {},
        dataset.validation_report_json or {},
    )
    rows = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    return {
        "analysis": _to_out(analysis),
        "dataset": dataset_out(dataset, include_normalized=True),
        "selected_model": selected_model,
        "rows": rows,
        "kpis": compute_kpis(frame),
        "explanations": explanations,
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
    return {"scenarios": [scenario_out(item) for item in consistent]}
