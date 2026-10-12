"""B8 plan report routes (level 1): the report model as a page preview and as the Excel workbook.

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §3 (additive routes; existing report routes keep
their behaviour). The plan report is available exactly when the analysis has a selected plan whose evidence is
current (``workflow._selected_scenario_and_dataset``); otherwise it is refused with that check's own reason.
The PDF (and the full report, level 2) follow in plan step 15b.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.analyses import own_analysis
from backend.api.deps import get_current_user, user_rate_limit
from backend.api.workflow import _latest_job, _scenario_evidence, _selected_scenario_and_dataset
from backend.db.models import AnalysisProject, User
from backend.db.session import get_db
from backend.queueing_engine.services.model_explanations import analyze_segments
from backend.reports.plan_report import build_separate_plan_model, build_shared_plan_model, generate_plan_workbook

router = APIRouter(prefix="/analyses", tags=["plan-reports"])
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NO_PLAN = "Choose a plan in Suggested plans first."


def _plan_model(db: Session, user: User, analysis: AnalysisProject) -> dict[str, Any]:
    scenario, dataset, selection = _selected_scenario_and_dataset(db, user, analysis)
    if scenario is None or dataset is None:
        selection = selection or _latest_job(db, user, "workflow_selection", analysis.id)
        scenario_id = (selection.params_json or {}).get("scenario_id") if selection is not None else None
        if not isinstance(scenario_id, int):
            raise HTTPException(status_code=422, detail={"code": "no_selected_plan", "detail": NO_PLAN})
        refusal = _scenario_evidence(db, user, analysis, scenario_id).refusal
        raise HTTPException(status_code=422, detail={"code": "plan_not_current", "detail": refusal or NO_PLAN})
    setup = analysis.queue_setup_json or {}
    analysis_view = {"id": analysis.id, "name": analysis.name}
    scenario_view = {"id": scenario.id, "name": scenario.name, "generation": scenario.generation,
                     "settings": scenario.settings_json or {}, "results": scenario.results_json or {}}
    dataset_view = {"id": dataset.id, "name": dataset.name, "generation": dataset.generation,
                    "rows": dataset.normalized_json or []}
    if setup.get("queue_structure") == "separate_queues":
        frame, _, _ = analyze_segments(dataset.normalized_json or [], setup, dataset.validation_report_json or {})
        current = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
        return build_separate_plan_model(analysis=analysis_view, scenario=scenario_view, dataset=dataset_view,
                                         setup=setup, current_rows=current)
    return build_shared_plan_model(analysis=analysis_view, scenario=scenario_view, dataset=dataset_view, setup=setup)


@router.get("/{analysis_id}/reports/plan/preview")
def plan_report_preview(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report")),
) -> dict[str, Any]:
    """The plan report model; the workbook is rendered from the same model."""
    return {"model": _plan_model(db, user, own_analysis(db, user, analysis_id))}


@router.get("/{analysis_id}/reports/plan.xlsx")
def plan_report_workbook(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report")),
) -> Response:
    model = _plan_model(db, user, own_analysis(db, user, analysis_id))
    return Response(content=generate_plan_workbook(model).getvalue(), media_type=EXCEL_MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="novaq_plan_report_{analysis_id}.xlsx"'})
