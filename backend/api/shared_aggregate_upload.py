"""Owned, read-only shared-file preview and atomic explicit Setup+Dataset apply.

Existing upload endpoints, validation rules and schema are unchanged. Dataset
validation metadata stores only derived request identities for safe retries.
"""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import String, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from backend.api.analysis_schemas import STORED_SETUP, QueueSetup, setup_status
from backend.api.current_dataset import resolve_current_dataset
from backend.api.datasets import _to_out as dataset_out
from backend.api.deps import get_current_user, get_settings, user_rate_limit
from backend.api.settings import Settings
from backend.api.shared_aggregate_schemas import (
    SharedAggregateApplyIn,
    SharedAggregateApplyOut,
    SharedAggregatePreviewOut,
)
from backend.data import uploads
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input
from backend.data.shared_aggregate_setup import derive_shared_aggregate, digest, setup_digest
from backend.db.models import AnalysisProject, Dataset, User
from backend.db.session import get_db

router = APIRouter(tags=["analyses"])
APPLY_VERSION = "shared-aggregate-apply-v1"
PREVIEW_FIELDS = tuple(SharedAggregatePreviewOut.model_fields)


def _analysis(db: Session, user: User, analysis_id: int, *, lock: bool = False) -> AnalysisProject:
    from backend.api.analyses import own_analysis

    analysis = own_analysis(db, user, analysis_id)
    if lock:
        analysis = db.execute(select(AnalysisProject).where(
            AnalysisProject.id == analysis_id, AnalysisProject.user_id == user.id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one()
    if analysis.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived analyses cannot accept uploads.")
    return analysis


def _revision(db: Session, analysis: AnalysisProject) -> str:
    current = resolve_current_dataset(db, owner_id=analysis.user_id, analysis_id=analysis.id).dataset
    return digest({
        "setup": QueueSetup.model_validate(analysis.queue_setup_json, context=STORED_SETUP).model_dump(mode="json"),
        "updated_at": analysis.updated_at.isoformat(),
        "current_planning_dataset": None if current is None else {"id": current.id, "generation": current.generation},
    })


def _read(file: UploadFile, settings: Settings):
    from backend.api.analyses import _upload_limits

    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large.")
    try:
        frame = uploads.sanitize_workbook(uploads.parse_upload(
            file.filename or "", data, settings.max_upload_bytes, **_upload_limits(settings),
        ))
        multiple_sheets = False
        if (file.filename or "").lower().endswith(".xlsx"):
            # parse_upload has already applied archive/size/worksheet limits.
            # This slice must not silently ignore evidence on other worksheets.
            with pd.ExcelFile(io.BytesIO(data), engine="openpyxl") as workbook:
                multiple_sheets = len(workbook.sheet_names) > 1
    except uploads.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return frame, hashlib.sha256(data).hexdigest(), multiple_sheets


def _derive(frame, analysis: AnalysisProject, filename: str, db: Session, multiple_sheets: bool = False) -> dict[str, Any]:
    if multiple_sheets:
        return {
            "mode": "declined", "facts": None, "derived_setup": None,
            "saved_setup": QueueSetup.model_validate(analysis.queue_setup_json, context=STORED_SETUP).model_dump(mode="json"),
            "diff": [], "needs_confirmation": False, "unresolved": [], "conflicts": [],
            "reasons": [{"code": "multiple_sheets", "detail": "This path reads one aggregate worksheet. Use the existing workbook upload for files with additional sheets."}],
        }
    try:
        result = derive_shared_aggregate(frame, analysis.queue_setup_json, filename)
    except AnalysisIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result["mode"] == "shared_aggregate" and resolve_current_dataset(
        db, owner_id=analysis.user_id, analysis_id=analysis.id,
    ).dataset is not None:
        result["needs_confirmation"] = True
    return result


def _planning(purpose: str) -> None:
    if purpose != "planning":
        raise HTTPException(status_code=422, detail={"code": "review_cannot_change_setup"})


@router.post("/{analysis_id}/datasets/shared-aggregate/preview", response_model=SharedAggregatePreviewOut)
def preview_shared_aggregate(
    analysis_id: int,
    file: UploadFile = File(...),
    purpose: Literal["planning", "review"] = "planning",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    analysis = _analysis(db, user, analysis_id)
    _planning(purpose)
    frame, file_digest, multiple_sheets = _read(file, settings)
    result = _derive(frame, analysis, file.filename or "upload", db, multiple_sheets)
    result.update(file_digest=file_digest, setup_revision=_revision(db, analysis))
    return {key: result[key] for key in PREVIEW_FIELDS}


def _answered_setup(result: dict[str, Any], metadata: SharedAggregateApplyIn) -> QueueSetup:
    candidate = dict(result["derived_setup"])
    supplied = metadata.choices.model_dump(mode="json", exclude_unset=True)
    missing = [key for key in result["unresolved"] if supplied.get(key) is None]
    if missing:
        raise HTTPException(status_code=422, detail={"code": "missing_choices", "fields": missing})
    for mode, number in (("capacity_mode", "total_system_capacity"), ("abandonment_mode", "patience_rate_per_hour")):
        if result["saved_setup"][mode] != "unknown":
            if any(key in supplied and supplied[key] != candidate.get(key) for key in (mode, number)):
                raise HTTPException(status_code=422, detail={"code": "saved_choice_changed", "field": mode})
            continue
        for key in (mode, number):
            if key in supplied:
                candidate[key] = supplied[key]
    missing = [key for mode, key, value in (("capacity_mode", "total_system_capacity", "finite"),
                                           ("abandonment_mode", "patience_rate_per_hour", "modeled"))
               if candidate[mode] == value and candidate.get(key) is None]
    if missing:
        raise HTTPException(status_code=422, detail={"code": "missing_choices", "fields": missing})
    try:
        return QueueSetup.model_validate(candidate)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _duplicate(db: Session, analysis: AnalysisProject, fingerprint: str) -> dict | None:
    dataset = db.execute(select(Dataset).where(
        Dataset.user_id == analysis.user_id, Dataset.analysis_id == analysis.id, Dataset.purpose == "planning",
        Dataset.validation_report_json["shared_aggregate_apply"]["request_fingerprint"].as_string() == fingerprint,
    ).order_by(Dataset.id.desc())).scalars().first()
    if dataset is None:
        return None
    current = resolve_current_dataset(db, owner_id=analysis.user_id, analysis_id=analysis.id).dataset
    stored = dataset.validation_report_json["shared_aggregate_apply"]
    if current is None or current.id != dataset.id or setup_digest(analysis.queue_setup_json) != stored["applied_setup_digest"]:
        raise HTTPException(status_code=409, detail={"code": "setup_changed"})
    from backend.api.analyses import _to_out as analysis_out

    return {"dataset": dataset_out(dataset, include_normalized=True, is_current=True),
            "analysis": analysis_out(analysis), "duplicate": True}


@router.post("/{analysis_id}/datasets/shared-aggregate/apply", status_code=201, response_model=SharedAggregateApplyOut)
def apply_shared_aggregate(
    analysis_id: int,
    metadata: str = Form(...),
    file: UploadFile = File(...),
    purpose: Literal["planning", "review"] = "planning",
    name: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _rate_limit: None = Depends(user_rate_limit("upload")),
) -> dict:
    analysis = _analysis(db, user, analysis_id, lock=True)
    _planning(purpose)
    try:
        submitted = SharedAggregateApplyIn.model_validate_json(metadata)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    frame, file_digest, multiple_sheets = _read(file, settings)
    if submitted.file_digest != file_digest:
        raise HTTPException(status_code=409, detail={"code": "file_changed"})
    filename = uploads.safe_stem(file.filename or "upload")
    dataset_name = (name or Path(filename).stem)[:255]
    fingerprint = digest({"version": APPLY_VERSION, "analysis_id": analysis.id, "purpose": purpose,
                          "file_digest": file_digest, "original_setup_revision": submitted.setup_revision,
                          "choices": submitted.choices.model_dump(mode="json", exclude_unset=True),
                          "filename": filename, "name": dataset_name})
    duplicate = _duplicate(db, analysis, fingerprint)
    if duplicate is not None:
        return duplicate
    if _revision(db, analysis) != submitted.setup_revision:
        raise HTTPException(status_code=409, detail={"code": "setup_changed"})
    result = _derive(frame, analysis, filename, db, multiple_sheets)
    if result["mode"] != "shared_aggregate":
        raise HTTPException(status_code=422, detail={"code": "not_supported", "reasons": result["reasons"]})
    if result["conflicts"]:
        raise HTTPException(status_code=422, detail={"code": "setup_conflict", "reasons": result["conflicts"]})
    if result["needs_confirmation"] and not submitted.confirm_replace:
        raise HTTPException(status_code=409, detail={"code": "confirmation_required"})
    setup = _answered_setup(result, submitted)
    try:
        records, provenance = normalize_analysis_input(frame, setup)
    except AnalysisIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    applied = setup.model_dump(mode="json")
    # PostgreSQL has the row lock above. SQLite ignores FOR UPDATE, so also
    # compare-and-swap the fetched timestamp BEFORE inserting a dataset.
    previous_update = analysis.updated_at
    timestamp_matches = AnalysisProject.updated_at == previous_update
    if db.get_bind().dialect.name == "sqlite" and previous_update.microsecond == 0:
        # SQLite CURRENT_TIMESTAMP uses whole seconds while its ORM bind adds
        # .000000. Match both exact encodings of that same timestamp; do not
        # truncate nonzero microseconds or use rounded floating-point dates.
        timestamp_matches = or_(timestamp_matches, sql_cast(AnalysisProject.updated_at, String)
                                == previous_update.strftime("%Y-%m-%d %H:%M:%S"))
    next_update = datetime.now(timezone.utc)
    if next_update.replace(tzinfo=None) == previous_update.replace(tzinfo=None):
        next_update += timedelta(microseconds=1)
    changed = cast(CursorResult, db.execute(update(AnalysisProject).where(
        AnalysisProject.id == analysis.id, AnalysisProject.user_id == user.id,
        timestamp_matches,
        AnalysisProject.archived_at.is_(None),
    ).values(queue_setup_json=applied, setup_status=setup_status(setup),
             updated_at=next_update).execution_options(synchronize_session=False)))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "setup_changed"})
    dataset = Dataset(
        user_id=user.id, analysis_id=analysis.id, name=dataset_name, source_filename=filename[:255],
        source_format=Path(filename).suffix.lower().lstrip("."), row_count=len(records), normalized_json=records,
        validation_report_json={"ok": True, "message": "Input data is valid.", **provenance,
                                "shared_aggregate_apply": {
                                    "version": APPLY_VERSION, "file_digest": file_digest,
                                    "original_setup_revision": submitted.setup_revision,
                                    "request_fingerprint": fingerprint, "applied_setup_digest": setup_digest(applied),
                                }}, purpose="planning",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.refresh(analysis)
    from backend.api.analyses import _to_out as analysis_out

    return {"dataset": dataset_out(dataset, include_normalized=True, is_current=True),
            "analysis": analysis_out(analysis), "duplicate": False}
