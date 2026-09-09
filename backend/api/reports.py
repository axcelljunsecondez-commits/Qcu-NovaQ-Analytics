"""Reports endpoints: PDF/Excel generation from datasets and scenarios."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, user_rate_limit
from backend.db.models import AnalysisProject, Dataset, Scenario, User
from backend.db.session import get_db
from backend.queueing_engine.services.data_processing import compute_kpis, process_segments
from backend.queueing_engine.services.optimization import build_recommendations, summarize_optimization
from backend.reports.report_export import generate_excel_report, generate_pdf_report

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(user_rate_limit("report"))],
)

PDF_MEDIA_TYPE = "application/pdf"
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _own_dataset(db: Session, user: User, dataset_id: int, analysis_id: int | None = None) -> Dataset:
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id or (analysis_id is not None and dataset.analysis_id != analysis_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def _own_scenario(db: Session, user: User, scenario_id: int, analysis_id: int | None = None) -> Scenario:
    if analysis_id is not None:
        analysis = db.get(AnalysisProject, analysis_id)
        if analysis is None or analysis.user_id != user.id:
            raise HTTPException(status_code=404, detail="Analysis not found.")
    scenario = db.get(Scenario, scenario_id)
    if scenario is None or scenario.user_id != user.id or (analysis_id is not None and scenario.analysis_id != analysis_id):
        raise HTTPException(status_code=404, detail="Scenario not found.")
    if scenario.dataset_id is not None:
        dataset = db.get(Dataset, scenario.dataset_id)
        if (
            dataset is None
            or dataset.user_id != user.id
            or dataset.analysis_id != scenario.analysis_id
        ):
            raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def _comparison_rows(scenario: Scenario) -> list[dict]:
    results = scenario.results_json or {}
    rows = results.get("comparison", results.get("results"))
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise HTTPException(
            status_code=422, detail="Scenario has no comparison results to report on."
        )
    return rows


def _scenario_payload(scenario: Scenario) -> tuple[pd.DataFrame, dict, list[str]]:
    rows = _comparison_rows(scenario)
    comparison_df = pd.DataFrame(rows)
    kpis = summarize_optimization(rows)
    recommendations = build_recommendations(rows)
    recommendations.insert(0, "Analytical model estimates, not observed outcomes. Abandonment percentages are sensitivity assumptions; Erlang-A theta is a patience rate per hour.")
    snapshot = (scenario.settings_json or {}).get("calculation") or {}
    if snapshot:
        recommendations.append("Calculation engine: " + str(snapshot.get("engine_version")))
    for row in rows:
        if row.get("effective_constraints"):
            recommendations.append(str(row.get("time")) + " constraints: " + str(row["effective_constraints"]))
        if row.get("effective_costs"):
            recommendations.append(str(row.get("time")) + " configured cost assumptions: " + str(row["effective_costs"]))
        if row.get("explanation"):
            recommendations.append(str(row.get("selected_model")) + ": " + str(row["explanation"]))
    if not (scenario.settings_json or {}).get("calculation"):
        recommendations.insert(0, "Legacy scenario: these saved outputs have no verified calculation snapshot.")
    return comparison_df, kpis, recommendations


def _dataset_payload(dataset: Dataset) -> tuple[pd.DataFrame, dict, list[str]]:
    records = dataset.normalized_json or []
    results_df = process_segments(records)
    kpis = compute_kpis(results_df)
    comparison_df = pd.DataFrame(
        {
            "time": results_df["time"],
            "c_current": results_df["c"],
            "rho_current": results_df["rho"],
            "Wq_current": results_df["Wq"],
            "metric_provenance": "analytical",
            "selected_model": results_df["model"],
        }
    )
    return comparison_df, kpis, ["Analytical estimates from supplied aggregate rates, not observed waiting times or externally validated outcomes."]


@router.get("/datasets/{dataset_id}/{format}")
def dataset_report(
    dataset_id: int,
    format: str,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    dataset = _own_dataset(db, user, dataset_id, analysis_id)
    comparison_df, kpis, recommendations = _dataset_payload(dataset)
    return _build_report(format, kpis, {}, comparison_df, recommendations, f"novaq_datasets_{dataset_id}")


@router.get("/scenarios/{scenario_id}/{format}")
def scenario_report(
    scenario_id: int,
    format: str,
    analysis_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    scenario = _own_scenario(db, user, scenario_id, analysis_id)
    comparison_df, kpis, recommendations = _scenario_payload(scenario)
    return _build_report(format, {}, kpis, comparison_df, recommendations, f"novaq_scenarios_{scenario_id}")


def _build_report(
    format: str,
    current_kpis: dict,
    recommended_kpis: dict,
    comparison_df: pd.DataFrame,
    recommendations: list[str],
    filename_stem: str,
) -> Response:
    if format == "pdf":
        buffer = generate_pdf_report(
            current_kpis,
            recommended_kpis,
            comparison_df,
            recommendations,
        )
        return Response(
            content=buffer.getvalue(),
            media_type=PDF_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename_stem}.pdf"'},
        )
    if format == "excel":
        buffer = generate_excel_report(
            comparison_df, recommended_kpis, current_kpis=current_kpis
        )
        return Response(
            content=buffer.getvalue(),
            media_type=EXCEL_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename_stem}.xlsx"'},
        )
    raise HTTPException(status_code=404, detail="Unknown report format.")
