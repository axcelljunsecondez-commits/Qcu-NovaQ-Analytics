"""Datasets endpoints: upload, list, retrieve, delete (own resources only)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.analysis_schemas import unknown_queue_setup
from backend.api.current_dataset import resolve_current_dataset
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.settings import Settings
from backend.data import uploads
from backend.data.data_dates import data_dates
from backend.data.ingestion import to_segment_records, validate_and_normalize
from backend.db.models import AnalysisProject, Dataset, User
from backend.db.session import get_db

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetOut(BaseModel):
    id: int
    analysis_id: int | None
    name: str
    source_filename: str
    source_format: str
    row_count: int
    validation: dict
    created_at: datetime
    generation: str | None = None
    normalized: list | None = None
    # B10: what the upload is for, and whether it is the analysis's current planning dataset.
    purpose: str = "planning"
    is_current: bool | None = None
    # B11: first and last date the data covers, or None ("Data period unavailable").
    data_dates: dict | None = None

    model_config = {"from_attributes": True}


def current_dataset_ids(db: Session, owner_id: int, analysis_ids) -> set[int]:
    """The current planning dataset of each given analysis (B10 rule, ``resolve_current_dataset``)."""
    found: set[int] = set()
    for analysis_id in {value for value in analysis_ids if value is not None}:
        dataset_id = resolve_current_dataset(db, owner_id=owner_id, analysis_id=analysis_id).dataset_id
        if dataset_id is not None:
            found.add(dataset_id)
    return found


def _to_out(dataset: Dataset, include_normalized: bool = False, is_current: bool | None = None) -> dict:
    payload = {
        "id": dataset.id,
        "analysis_id": dataset.analysis_id,
        "name": dataset.name,
        "source_filename": dataset.source_filename,
        "source_format": dataset.source_format,
        "row_count": dataset.row_count,
        "validation": dataset.validation_report_json,
        "created_at": dataset.created_at,
        "generation": dataset.generation,
        "normalized": dataset.normalized_json if include_normalized else None,
        "purpose": dataset.purpose or "planning",
        "is_current": is_current,
        "data_dates": data_dates(dataset.validation_report_json, dataset.normalized_json),
    }
    return DatasetOut.model_validate(payload).model_dump()


def _own_dataset(db: Session, user: User, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


@router.post("", status_code=201)
def create_dataset(
    file: UploadFile = File(...),
    name: str | None = None,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")

    try:
        df = uploads.parse_upload(
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
        df = uploads.sanitize_workbook(df)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ok, message, normalized = validate_and_normalize(df)
    if not ok:
        raise HTTPException(status_code=422, detail=message)

    safe_filename = uploads.safe_stem(file.filename or "upload")
    extension = Path(safe_filename).suffix.lower().lstrip(".")
    records = to_segment_records(normalized)
    analysis = db.get(AnalysisProject, analysis_id) if analysis_id is not None else None
    if analysis_id is not None and (analysis is None or analysis.user_id != user.id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis is None:
        setup = unknown_queue_setup()
        analysis = AnalysisProject(
            user_id=user.id,
            name=(name or Path(safe_filename).stem)[:255],
            queue_setup_json=setup.model_dump(mode="json"),
            setup_status="legacy",
        )
        db.add(analysis)
        db.flush()
    dataset = Dataset(
        user_id=user.id,
        analysis_id=analysis.id,
        name=(name or Path(safe_filename).stem)[:255],
        source_filename=safe_filename[:255],
        source_format=extension,
        row_count=len(records),
        normalized_json=records,
        validation_report_json={"ok": True, "message": "Input data is valid."},
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    current = current_dataset_ids(db, user.id, [dataset.analysis_id])
    return {"dataset": _to_out(dataset, is_current=dataset.id in current)}


@router.get("")
def list_datasets(
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(Dataset).where(Dataset.user_id == user.id)
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        query = query.where(Dataset.analysis_id == analysis_id)
    datasets = db.execute(query.order_by(Dataset.id.desc())).scalars().all()
    current = current_dataset_ids(db, user.id, [dataset.analysis_id for dataset in datasets])
    return {"datasets": [_to_out(dataset, is_current=dataset.id in current) for dataset in datasets]}


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    dataset = _own_dataset(db, user, dataset_id)
    current = current_dataset_ids(db, user.id, [dataset.analysis_id])
    return {"dataset": _to_out(dataset, include_normalized=True, is_current=dataset.id in current)}


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    dataset = _own_dataset(db, user, dataset_id)
    db.delete(dataset)
    db.commit()
    return {"detail": "Dataset deleted."}
