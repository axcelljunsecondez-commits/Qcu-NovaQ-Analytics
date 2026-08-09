"""Datasets endpoints: upload, list, retrieve, delete (own resources only)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_settings
from backend.api.settings import Settings
from backend.data import uploads
from backend.data.ingestion import to_segment_records, validate_and_normalize
from backend.db.models import Dataset, User
from backend.db.session import get_db

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetOut(BaseModel):
    id: int
    name: str
    source_filename: str
    source_format: str
    row_count: int
    validation: dict
    created_at: datetime
    normalized: list | None = None

    model_config = {"from_attributes": True}


def _to_out(dataset: Dataset, include_normalized: bool = False) -> dict:
    payload = {
        "id": dataset.id,
        "name": dataset.name,
        "source_filename": dataset.source_filename,
        "source_format": dataset.source_format,
        "row_count": dataset.row_count,
        "validation": dataset.validation_report_json,
        "created_at": dataset.created_at,
        "normalized": dataset.normalized_json if include_normalized else None,
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")

    try:
        df = uploads.parse_upload(file.filename or "", data, settings.max_upload_bytes)
        df = uploads.sanitize_workbook(df)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ok, message, normalized = validate_and_normalize(df)
    if not ok:
        raise HTTPException(status_code=422, detail=message)

    safe_filename = uploads.safe_stem(file.filename or "upload")
    extension = Path(safe_filename).suffix.lower().lstrip(".")
    records = to_segment_records(normalized)
    dataset = Dataset(
        user_id=user.id,
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
    return {"dataset": _to_out(dataset)}


@router.get("")
def list_datasets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    datasets = db.execute(
        select(Dataset).where(Dataset.user_id == user.id).order_by(Dataset.id.desc())
    ).scalars().all()
    return {"datasets": [_to_out(dataset) for dataset in datasets]}


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    dataset = _own_dataset(db, user, dataset_id)
    return {"dataset": _to_out(dataset, include_normalized=True)}


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
