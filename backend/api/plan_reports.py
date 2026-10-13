"""B8 plan report routes (level 1): the report model as a page preview and as the Excel workbook.

Spec: docs/superpowers/specs/2026-10-09-b8-reports-pdf-excel.md §3 (additive routes; existing report routes keep
their behaviour). The plan report is available exactly when the analysis has a selected plan whose evidence is
current (``workflow._selected_scenario_and_dataset``); otherwise it is refused with that check's own reason.
The full report (level 2, plan step 15b) adds the Decision, the simulation and the checks; it is available exactly
when today's Decision gate allows export: for separate lines the selected-plan chain (``reports._selected_report_chain``,
whose own statuses and reasons are kept), for one shared line a current Decision for the selected plan
(``workflow.current_decision_for_report``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.analyses import own_analysis
from backend.api.deps import get_current_user, user_rate_limit
from backend.api.workflow import (
    _current_evidence,
    _latest_job,
    _scenario_evidence,
    _selected_scenario_and_dataset,
    current_decision_for_report,
)
from backend.db.models import AnalysisProject, User
from backend.db.session import get_db
from backend.queueing_engine.services.model_explanations import analyze_segments
from backend.reports.full_report import full_model, separate_full_sections, shared_full_sections
from backend.reports.plan_report import (
    build_separate_plan_model,
    build_shared_plan_model,
    generate_plan_workbook,
    workbook_sheets,
)
from backend.reports.report_pdf import generate_report_pdf, pdf_sections

router = APIRouter(prefix="/analyses", tags=["plan-reports"])
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MEDIA_TYPE = "application/pdf"
NO_DECISION = "Make the Decision on the Checks and decision page first."
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
    _rate_limit: None = Depends(user_rate_limit("report_preview")),
) -> dict[str, Any]:
    """The plan report model; the files are rendered from the same model, with the contents listed here."""
    return _preview(_plan_model(db, user, own_analysis(db, user, analysis_id)))


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


def _full_model(db: Session, user: User, analysis: AnalysisProject) -> dict[str, Any]:
    plan = _plan_model(db, user, analysis)
    setup = analysis.queue_setup_json or {}
    if setup.get("queue_structure") == "separate_queues":
        from backend.api.reports import _selected_report_chain

        chain = _selected_report_chain(db, user, analysis)
        jobs = {name: {"params": chain[f"{name}_job"].params_json or {}, "result": chain[f"{name}_job"].result_json or {}}
                for name in ("des", "mc", "validation", "decision")}
        sections = separate_full_sections(des=jobs["des"], mc=jobs["mc"], validation=jobs["validation"],
                                          decision=jobs["decision"]["result"])
    else:
        decision = current_decision_for_report(db, user, analysis.id, plan["provenance"]["scenario_id"])
        if decision is None:
            raise HTTPException(status_code=422, detail={"code": "no_current_decision", "detail": NO_DECISION})
        evidence = _current_evidence(db, user, analysis)
        sections = shared_full_sections(des=evidence["des"], mc=evidence["mc"], validation=evidence["validation"],
                                        decision=decision, counter_breaks=bool(setup.get("counter_breaks")))
    return full_model(plan, sections)


def _preview(model: dict[str, Any]) -> dict[str, Any]:
    contents = {"pdf": pdf_sections(model), "excel": workbook_sheets(model)}
    # What the full report adds, from the same rules, so the page can mark it "after the checks".
    full = {**model, "report": "full"}
    after = {"pdf": [item for item in pdf_sections(full) if item not in contents["pdf"]],
             "excel": [item for item in workbook_sheets(full) if item not in contents["excel"]]}
    return {"model": model, "contents": contents, "after_checks": after}


def _file(content: bytes, media_type: str, name: str) -> Response:
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{analysis_id}/reports/plan.pdf")
def plan_report_pdf(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report")),
) -> Response:
    model = _plan_model(db, user, own_analysis(db, user, analysis_id))
    return _file(generate_report_pdf(model).getvalue(), PDF_MEDIA_TYPE, f"novaq_plan_report_{analysis_id}.pdf")


@router.get("/{analysis_id}/reports/full/preview")
def full_report_preview(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report_preview")),
) -> dict[str, Any]:
    """The full report model; the PDF and the workbook are rendered from the same model."""
    return _preview(_full_model(db, user, own_analysis(db, user, analysis_id)))


@router.get("/{analysis_id}/reports/full.pdf")
def full_report_pdf(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report")),
) -> Response:
    model = _full_model(db, user, own_analysis(db, user, analysis_id))
    return _file(generate_report_pdf(model).getvalue(), PDF_MEDIA_TYPE, f"novaq_full_report_{analysis_id}.pdf")


@router.get("/{analysis_id}/reports/full.xlsx")
def full_report_workbook(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limit: None = Depends(user_rate_limit("report")),
) -> Response:
    model = _full_model(db, user, own_analysis(db, user, analysis_id))
    return _file(generate_plan_workbook(model).getvalue(), EXCEL_MEDIA_TYPE, f"novaq_full_report_{analysis_id}.xlsx")
