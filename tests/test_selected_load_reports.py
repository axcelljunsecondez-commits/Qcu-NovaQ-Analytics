"""SEED-001 §3-§4: selected-load evidence through both selected full-report paths.

The B8 full report (``/analyses/{id}/reports/full*``) and the Separate report
(``/reports/analyses/{id}/selected/*``) quote the stored v1 assessment and refuse a
legacy (missing-method) chain. All records are synthetic SQLite fixtures.
"""

from __future__ import annotations

import io
import json
from copy import deepcopy

import pytest
from openpyxl import load_workbook

from backend.db.models import Job
from backend.queueing_engine.statistics.selected_load_uncertainty import SELECTED_LOAD_METHOD
from backend.reports.selected_scope import SELECTED_LOAD_ASSESSMENT_NOTICE
from tests.helpers import csrf_header, login, make_sessionmaker
from tests.test_b8_full_report import _separate_chain, pdf_text
from tests.test_separate_report import _api_workspace, _full_chain

LEGACY_NOTE = "Load estimate uncertainty: Not checked."


def _assessed_rows(validation_result):
    return [(period["time"], row) for period in validation_result["periods"] for row in period["queues"]
            if "load_assessment" in row]


def test_v1_chain_b8_full_report_quotes_the_assessment_in_preview_pdf_and_excel(db_engine, client):
    a = _separate_chain(client, db_engine)
    stored = client.get(f"/analyses/{a}/workflow").json()
    validation = stored["validation"]["result"]
    assert validation["selected_load_method"] == SELECTED_LOAD_METHOD
    pairs = _assessed_rows(validation)
    assert len(pairs) == validation["load_uncertainty"]["family_size"] > 0
    model = client.get(f"/analyses/{a}/reports/full/preview").json()["model"]
    assert model["decision"]["selected_load_method"] == SELECTED_LOAD_METHOD
    assert model["decision"]["load_uncertainty"] == stored["decision"]["result"]["load_uncertainty"]
    assert model["decision"]["scope_notice"] == SELECTED_LOAD_ASSESSMENT_NOTICE
    checks = model["checks"]
    assert [item["check"] for item in checks] == [
        "Simulation run", "Many variations", "Results check", "Results check", *["Results check"] * len(pairs)]
    # The summary detail row is one JSON object built from the stored objects (no nested JSON string).
    assert json.loads(checks[3]["settings"]) == {"selected_load_method": SELECTED_LOAD_METHOD,
                                                 "selected_load_family": validation["load_uncertainty"]}
    assert checks[3]["outcome"] == validation["verdict"]["status"]
    for item, (_, row) in zip(checks[4:], pairs, strict=True):
        assert json.loads(item["settings"]) == {**row["load_assessment"], "raw_mc_verdict": row["raw_mc_verdict"]}
        assert item["outcome"] == row["load_assessment"]["status"]
    text = " ".join(pdf_text(client.get(f"/analyses/{a}/reports/full.pdf").content).split())
    assert text.count(SELECTED_LOAD_ASSESSMENT_NOTICE) == 1
    assert LEGACY_NOTE not in text
    workbook = load_workbook(io.BytesIO(client.get(f"/analyses/{a}/reports/full.xlsx").content))
    sheet = workbook["Decision"]
    assert (sheet.cell(sheet.max_row, 1).value, sheet.cell(sheet.max_row, 2).value) == (
        "Current scope note", SELECTED_LOAD_ASSESSMENT_NOTICE)
    rows = [[cell.value for cell in row] for row in workbook["Checks"].iter_rows()]
    assert [row for row in rows if row[0] == "Results check"] == [
        [item["check"], item["settings"], item["outcome"]] for item in checks[2:]]


def test_v1_chain_separate_report_quotes_the_assessment_in_preview_pdf_and_excel(db_engine, client):
    analysis_id, _, scenario_id = _api_workspace(db_engine, "v1@example.com")
    login(client, "v1@example.com", "pw")
    headers = csrf_header(client)
    _full_chain(client, analysis_id, headers, scenario_id)
    stored = client.get(f"/analyses/{analysis_id}/workflow").json()
    validation = stored["validation"]["result"]
    pairs = _assessed_rows(validation)
    assert pairs
    model = client.get(f"/reports/analyses/{analysis_id}/selected/preview", headers=headers).json()["model"]
    assert model["decision"]["scope_notice"] == SELECTED_LOAD_ASSESSMENT_NOTICE
    for key in ("des", "mc", "validation", "decision"):
        assert model[key]["selected_load_method"] == SELECTED_LOAD_METHOD
        assert model[key]["load_uncertainty"] == stored[key]["result"]["load_uncertainty"]
    model_rows = {(period["time"], row["queue_id"]): row for period in model["validation"]["periods"]
                  for row in period["queues"]}
    for time, row in pairs:
        assert model_rows[(time, row["queue_id"])]["raw_mc_verdict"] == row["raw_mc_verdict"]
        assert model_rows[(time, row["queue_id"])]["load_assessment"] == row["load_assessment"]
    provenance = model["provenance"]
    keys = list(provenance)
    assert keys[0] == "analysis_id" and keys.index("generated_at") == 8
    assert keys[9:] == ["selected_load_method", "selected_load_family",
                        *[f"selected_load_assessment:{time}/{row['queue_id']}" for time, row in pairs]]
    assert json.loads(provenance["selected_load_family"]) == validation["load_uncertainty"]
    text = " ".join(pdf_text(client.get(f"/reports/analyses/{analysis_id}/selected/pdf", headers=headers).content).split())
    assert text.count(SELECTED_LOAD_ASSESSMENT_NOTICE) == 1
    assert LEGACY_NOTE not in text
    workbook = load_workbook(io.BytesIO(
        client.get(f"/reports/analyses/{analysis_id}/selected/excel", headers=headers).content))
    sheet = workbook["Decision"]
    assert (sheet.cell(sheet.max_row, 1).value, sheet.cell(sheet.max_row, 2).value) == (
        "Current scope note", SELECTED_LOAD_ASSESSMENT_NOTICE)
    prov_rows = [(row[0].value, row[1].value) for row in workbook["Provenance"].iter_rows(min_row=2)]
    assert prov_rows[8][0] == "Generated at"
    assert prov_rows[9:] == [(key, provenance[key]) for key in keys[9:]]


def _make_legacy(db_engine, client, analysis_id):
    """Remove the v1 method and assessment fields, as on a record saved before SEED-001."""
    slots = client.get(f"/analyses/{analysis_id}/workflow").json()
    snapshots = {}
    with make_sessionmaker(db_engine)() as db:
        for step in ("des", "mc", "validation", "decision"):
            job = db.get(Job, slots[step]["id"])
            assert job.result_json.get("selected_load_method") == SELECTED_LOAD_METHOD
            params = {k: v for k, v in (job.params_json or {}).items() if k != "selected_load_method"}
            result = {k: v for k, v in deepcopy(job.result_json or {}).items()
                      if k not in ("selected_load_method", "load_uncertainty")}
            for period in result.get("periods") or []:
                if isinstance(period, dict) and isinstance(period.get("queues"), list):
                    period["queues"] = [{k: v for k, v in row.items() if k not in ("raw_mc_verdict", "load_assessment")}
                                        for row in period["queues"]]
            job.params_json, job.result_json = params, result
            snapshots[job.id] = deepcopy((params, result))
        db.commit()
    assert len(snapshots) == 4
    return snapshots


@pytest.mark.parametrize("family", ["b8_full", "separate"])
def test_legacy_missing_method_chain_is_refused_by_both_report_paths(db_engine, client, family):
    if family == "b8_full":
        a = _separate_chain(client, db_engine)
        headers = csrf_header(client)
        paths = [f"/analyses/{a}/reports/full/preview", f"/analyses/{a}/reports/full.pdf",
                 f"/analyses/{a}/reports/full.xlsx"]
    else:
        a, _, scenario_id = _api_workspace(db_engine, "legacy@example.com")
        login(client, "legacy@example.com", "pw")
        headers = csrf_header(client)
        _full_chain(client, a, headers, scenario_id)
        paths = [f"/reports/analyses/{a}/selected/{name}" for name in ("preview", "pdf", "excel")]
    assert all(client.get(path, headers=headers).status_code == 200 for path in paths)
    snapshots = _make_legacy(db_engine, client, a)
    for path in paths:
        refused = client.get(path, headers=headers)
        assert refused.status_code == 409, (path, refused.status_code, refused.text)
        assert SELECTED_LOAD_ASSESSMENT_NOTICE not in refused.text and LEGACY_NOTE not in refused.text
    with make_sessionmaker(db_engine)() as db:  # historical records stay intact; nothing is rewritten
        for job_id, (params, result) in snapshots.items():
            job = db.get(Job, job_id)
            assert (job.params_json, job.result_json) == (params, result)
