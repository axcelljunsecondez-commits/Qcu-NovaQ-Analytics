"""Reports endpoints: PDF/Excel generation from datasets and scenarios."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.data_processing import compute_kpis, process_segments
from backend.queueing_engine.services.optimization import build_recommendations, summarize_optimization
from backend.reports.report_export import generate_excel_report, generate_pdf_report

router = APIRouter(prefix="/reports", tags=["reports"])

PDF_MEDIA_TYPE = "application/pdf"
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _own_dataset(db: Session, user: User, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def _own_scenario(db: Session, user: User, scenario_id: int) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def _comparison_rows(scenario: Scenario) -> list[dict]:
    results = scenario.results_json or {}
    rows = results.get("comparison", results.get("results"))
    if not isinstance(rows, list) or not rows:
        raise HTTPException(
            status_code=422, detail="Scenario has no comparison results to report on."
        )
    return rows


def _scenario_payload(scenario: Scenario) -> tuple[pd.DataFrame, dict, list[str]]:
    rows = _comparison_rows(scenario)
    comparison_df = pd.DataFrame(rows)
    kpis = summarize_optimization(rows)
    recommendations = build_recommendations(rows)
    return comparison_df, kpis, recommendations


def _dataset_payload(dataset: Dataset) -> tuple[pd.DataFrame, dict, list[str]]:
    records = dataset.normalized_json or []
    results_df = process_segments(records)
    kpis = compute_kpis(results_df)
    return results_df, kpis, []


@router.get("/datasets/{dataset_id}/{format}")
def dataset_report(
    dataset_id: int,
    format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    dataset = _own_dataset(db, user, dataset_id)
    comparison_df, kpis, recommendations = _dataset_payload(dataset)
    return _build_report(format, kpis, {}, comparison_df, recommendations)


@router.get("/scenarios/{scenario_id}/{format}")
def scenario_report(
    scenario_id: int,
    format: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    scenario = _own_scenario(db, user, scenario_id)
    comparison_df, kpis, recommendations = _scenario_payload(scenario)
    return _build_report(format, {}, kpis, comparison_df, recommendations)


def _build_report(
    format: str,
    current_kpis: dict,
    recommended_kpis: dict,
    comparison_df: pd.DataFrame,
    recommendations: list[str],
) -> Response:
    if format == "pdf":
        buffer = generate_pdf_report(
            current_kpis,
            recommended_kpis,
            comparison_df,
            recommendations,
        )
        return Response(content=buffer.getvalue(), media_type=PDF_MEDIA_TYPE)
    if format == "excel":
        buffer = generate_excel_report(comparison_df, recommended_kpis)
        return Response(content=buffer.getvalue(), media_type=EXCEL_MEDIA_TYPE)
    raise HTTPException(status_code=404, detail="Unknown report format.")
