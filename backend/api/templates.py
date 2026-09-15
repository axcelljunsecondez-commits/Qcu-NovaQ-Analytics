"""Upload template downloads and field guide, generated from the ingestion schema."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.api.deps import get_current_user, user_rate_limit
from backend.data.templates import (
    HEADER_ALIASES,
    example_rows,
    field_guide,
    template_columns,
    template_csv,
    template_workbook,
)
from backend.db.models import User

router = APIRouter(
    prefix="/templates",
    tags=["templates"],
    dependencies=[Depends(user_rate_limit("report"))],
)

StructureParam = Literal["shared_queue", "separate_queues"]
SchemaParam = Literal["aggregate", "events"]
FormatParam = Literal["csv", "xlsx"]

_FILENAMES = {
    ("shared_queue", "aggregate", "csv"): "novaq_shared_aggregate_template.csv",
    ("shared_queue", "aggregate", "xlsx"): "novaq_shared_aggregate_template.xlsx",
    ("separate_queues", "aggregate", "csv"): "novaq_separate_aggregate_template.csv",
    ("separate_queues", "aggregate", "xlsx"): "novaq_separate_aggregate_template.xlsx",
    ("shared_queue", "events", "csv"): "novaq_shared_events_template.csv",
    ("shared_queue", "events", "xlsx"): "novaq_shared_events_template.xlsx",
    ("separate_queues", "events", "csv"): "novaq_separate_events_template.csv",
    ("separate_queues", "events", "xlsx"): "novaq_separate_events_template.xlsx",
}


@router.get("/guide")
def template_guide(
    structure: StructureParam,
    schema: SchemaParam,
    user: User = Depends(get_current_user),
) -> dict:
    """Field guide, example rows, and columns for one template."""
    return {
        "structure": structure,
        "schema": schema,
        "columns": template_columns(structure, schema),
        "example_rows": example_rows(structure, schema),
        "field_guide": field_guide(structure, schema),
        "accepted_aliases": HEADER_ALIASES,
    }


@router.get("/download")
def download_template(
    structure: StructureParam,
    schema: SchemaParam,
    format: FormatParam = "csv",
    user: User = Depends(get_current_user),
) -> Response:
    """Download a clean entry template (headers only for CSV)."""
    if format == "csv":
        content = template_csv(structure, schema)
        media_type = "text/csv"
    elif format == "xlsx":
        content = template_workbook(structure, schema)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:  # pragma: no cover - Literal validation rejects first
        raise HTTPException(status_code=422, detail="Format must be csv or xlsx.")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{_FILENAMES[(structure, schema, format)]}"'},
    )
