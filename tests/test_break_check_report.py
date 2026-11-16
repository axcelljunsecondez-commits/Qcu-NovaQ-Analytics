"""Option A break check (owner 2026-11-17) and the PR58 follow-ups K-PR58-1/2/4.

The plan save stores the break check it already computes; the plan and full reports print it. Labels are the
owner-approved English text (output/pdf-break-check-labels-approved.md, 2026-11-16). All operational inputs here
are synthetic, using isolated test databases.
"""
from __future__ import annotations

import io
import json
from copy import deepcopy

import pytest
from openpyxl import load_workbook

from backend.api.plan_breaks import BREAK_CHECK_BASIS
from backend.db.models import AnalysisProject, Job, Scenario
from backend.queueing_engine.simulation import simulation as engine
from backend.reports import plan_report
from backend.reports.plan_report import build_separate_plan_model, generate_plan_workbook, workbook_sheets
from backend.reports.report_pdf import generate_report_pdf, pdf_sections
from tests.helpers import csrf_header, make_sessionmaker
from tests.test_b8_full_report import pdf_text
from tests.test_break_apply_api import _stored_setup
from tests.test_current_uploaded_breaks import run as run_current
from tests.test_current_uploaded_breaks import setup as current_setup
from tests.test_plan_break_isolation import _prepared, _save_body
from tests.test_supervisor_schedule_api import _post

B = {
    "B1": "Break times: uploaded vs plan",
    "B1-tab": "Break check",
    "B2": ("This section compares your uploaded break times with the plan's moved break times. Both sides use the "
           "plan's simulation, where new customers go to an open line, with the same random runs. Counters per hour "
           "do not change."),
    "B3": "Wait, uploaded breaks (min)",
    "B4": "Wait, moved breaks (min)",
    "B5": "Average wait in line per period: uploaded vs moved breaks",
    "B6": ("Period values are averages of the simulation runs and have no range. The 95% range is shown for the whole "
           "day below."),
    "B7": "Simulated average wait (minutes)",
    "B8": "Change in average wait (minutes, 95% range)",
    "B10": "Busiest 15-minute load",
    "B10n": "The busiest 15-minute load is a formula estimate from all lanes together, not the simulation.",
    "B11": "Your breaks: uploaded vs plan",
    "B13": "Breaks the plan moved",
    "B14": "This plan keeps your uploaded break times. No break was moved.",
    "B15": "The break check is not saved with this plan. Check the plan and save it again to see it.",
    "B16": ('Both columns use the plan\'s break times. The effect of moving breaks is shown in "Break times: uploaded '
            'vs plan".'),
    "B17": "Plan break times",
}
B9 = {
    "shorter": "The paired runs indicate shorter waits.",
    "no_clear_difference": "No clear change in wait. A lower peak load does not prove shorter waits.",
    "unavailable": "Wait comparison is unavailable.",
    "longer": "The paired runs indicate longer waits. These changes cannot be applied.",
}
B12 = ["Cashier", "Break", "Current start", "New start", "Length (minutes)"]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _saved(db_engine, client):
    aid, baseline, request, preview = _prepared(db_engine, client)
    body = _save_body(db_engine, aid, request, preview)
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 201, response.text
    return aid, baseline, request, preview, body, response.json()["scenario"]


# ── A. The save stores the check it already ran ─────────────────────────────


def test_save_stores_the_break_check_it_computed_without_changing_the_schedule(db_engine, client):
    aid, baseline, _, preview, body, scenario = _saved(db_engine, client)
    results = scenario["results"]
    assert set(results) == {"schedule", "break_check"}
    assert results["schedule"] == body["results"]["schedule"]  # the verified schedule is unchanged
    check = results["break_check"]
    proposal = preview["breaks"]
    assert check["basis"] == BREAK_CHECK_BASIS
    assert check["max_shift_minutes"] == 120
    assert set(check) == {"basis", "max_shift_minutes", "des", "peak_rho", "slots_above_target", "moves",
                          "current_breaks", "proposed_breaks"}
    # Same seeds, same proposal as the preview the supervisor saw: nothing new was calculated.
    assert check["des"]["seeds"] == proposal["des"]["seeds"] == [42, 43, 44, 45, 46]
    for side in ("current", "proposed"):
        assert check["des"][side] == {key: proposal["des"][side][key] for key in ("summary", "periods", "replications")}
    assert check["des"]["comparison"] == proposal["des"]["comparison"]
    assert "paired_wait_change" in check["des"]["comparison"]
    for key in ("peak_rho", "slots_above_target", "moves", "current_breaks", "proposed_breaks"):
        assert check[key] == proposal[key], key
    # "Current" is the uploaded Setup, which the save never overwrites (PR58).
    assert [(b["queue_id"], b["scheduled_start_time"]) for b in check["current_breaks"]] == \
        [(b["queue_id"], b["scheduled_start_time"]) for b in baseline["breaks"]]
    assert _stored_setup(db_engine, aid) == baseline
    assert check["moves"], "the synthetic rush must move a break"


@pytest.mark.parametrize("with_descriptor", [True, False])
def test_a_client_sent_break_check_is_refused(db_engine, client, with_descriptor):
    aid, baseline, request, preview = _prepared(db_engine, client)
    body = _save_body(db_engine, aid, request, preview)
    if not with_descriptor:
        body["settings"]["calculation"].pop("break_optimization")
    body["results"]["break_check"] = {"basis": BREAK_CHECK_BASIS, "moves": []}
    response = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "The break check must be generated by the server."
    with make_sessionmaker(db_engine)() as db:
        assert db.query(Scenario).count() == 0
    assert _stored_setup(db_engine, aid) == baseline


def test_the_stored_break_check_counts_toward_the_result_size_limit(db_engine, client, app, monkeypatch):
    aid, _, request, preview, body, scenario = _saved(db_engine, client)

    def size(value) -> int:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    limit = max(size(body["results"]), size(body["settings"]), size(scenario["settings"]))
    assert limit < size(scenario["results"]), "precondition: only the stored break check exceeds the limit"
    monkeypatch.setattr(app.state.settings, "result_jsonb_max_bytes", limit)
    response = client.post("/scenarios", headers=csrf_header(client), json=_save_body(db_engine, aid, request, preview))
    assert response.status_code == 413, response.text
    with make_sessionmaker(db_engine)() as db:
        assert db.query(Scenario).count() == 1


# ── K-PR58-2: per-user compute limit on saves that verify suggested breaks ──


def test_saving_suggested_breaks_uses_the_compute_rate_limit(db_engine, client, app, monkeypatch):
    aid, _, request, preview = _prepared(db_engine, client)  # one compute request (preview)
    plain_preview = _post(client, aid, "preview", {**request, "allow_break_changes": False})  # two
    assert plain_preview.status_code == 200, plain_preview.text
    monkeypatch.setattr(app.state.settings, "rate_limit_compute", 3)
    body = _save_body(db_engine, aid, request, preview)
    assert client.post("/scenarios", headers=csrf_header(client), json=body).status_code == 201  # three
    limited = client.post("/scenarios", headers=csrf_header(client), json=body)
    assert limited.status_code == 429, limited.text
    assert "Retry-After" in limited.headers
    # A save without suggested breaks is not a compute request.
    plain = _save_body(db_engine, aid, request, plain_preview.json())
    plain["settings"]["calculation"].pop("break_optimization")
    assert client.post("/scenarios", headers=csrf_header(client), json=plain).status_code == 201


# ── Reports ─────────────────────────────────────────────────────────────────


def _select(client, aid, scenario_id):
    selected = client.post(f"/analyses/{aid}/workflow/selection", headers=csrf_header(client),
                           json={"scenario_id": scenario_id})
    assert selected.status_code == 200, selected.text


def test_plan_report_prints_the_saved_break_check(db_engine, client):
    aid, baseline, _, _, _, scenario = _saved(db_engine, client)
    _select(client, aid, scenario["id"])
    preview = client.get(f"/analyses/{aid}/reports/plan/preview")
    assert preview.status_code == 200, preview.text
    out = preview.json()
    model = out["model"]
    check = model["break_check"]
    stored = scenario["results"]["break_check"]
    assert out["contents"]["pdf"] == ["Key results: now and with the plan", "By period", B["B1"]]
    assert out["contents"]["excel"] == ["Overview", "Your data", "Plan", B["B1-tab"], "Formula check", "Plan search",
                                        "Assumptions", "Provenance"]
    assert model["breaks_title"] == B["B17"] and model["breaks_note"] is None
    assert model["key_results_note"] == B["B16"]
    assert model["breaks"] == scenario["settings"]["calculation"]["plan_breaks"]
    paired = stored["des"]["comparison"]["paired_wait_change"]
    assert check["change"] == {key: paired[key] for key in ("mean", "ci_lower", "ci_upper", "n")}
    assert check["verdict"] == paired["verdict"] and check["verdict_text"] == B9[paired["verdict"]]
    assert check["wait_uploaded_minutes"] == stored["des"]["current"]["summary"]["mean_wait_minutes"]
    assert check["wait_moved_minutes"] == stored["des"]["proposed"]["summary"]["mean_wait_minutes"]
    assert (check["peak_uploaded"], check["peak_moved"]) == (stored["peak_rho"]["before"], stored["peak_rho"]["after"])
    assert [row["time"] for row in check["periods"]] == [row["time"] for row in stored["des"]["current"]["periods"]]
    assert [run["seed"] for run in check["runs"]] == stored["des"]["seeds"]
    for run, before, after in zip(check["runs"], stored["des"]["current"]["replications"],
                                  stored["des"]["proposed"]["replications"]):
        assert run["difference_minutes"] == after["mean_wait_minutes"] - before["mean_wait_minutes"]
    moved = [row["moved"] for row in check["breaks"]]
    assert moved == sorted(moved, reverse=True) and any(moved)  # moved first
    assert len(check["moves"]) == len(stored["moves"])

    pdf = client.get(f"/analyses/{aid}/reports/plan.pdf")
    assert pdf.status_code == 200, pdf.text
    text = _flat(pdf_text(pdf.content))
    for slot in ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B10", "B10n", "B11", "B13", "B16"):
        assert _flat(B[slot]) in text, slot
    assert _flat(B9[paired["verdict"]]) in text
    # Owner 2026-11-17: B11/B13 replace the older breaks table, under either heading.
    assert "Breaks in the Setup" not in text and B["B17"] not in text
    assert "Your breaks: uploaded vs plan" in text
    for column in B12:
        assert column in text
    assert f"n = {paired['n']}" in text

    workbook = load_workbook(io.BytesIO(client.get(f"/analyses/{aid}/reports/plan.xlsx").content))
    assert workbook.sheetnames == out["contents"]["excel"]
    sheet = workbook[B["B1-tab"]]
    values = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    assert values[0][0] == B["B1"]
    assert values[2][:3] == ["Period", B["B3"], B["B4"]]
    labels = [row[0] for row in values]
    for slot in ("B7", "B8", "B10", "B10n", "B11", "B13"):
        assert B[slot] in labels, slot
    assert B9[paired["verdict"]] in labels
    # openpyxl stores floats to 15 significant digits (last-place rounding only).
    assert list(values[labels.index(B["B7"])][1:3]) == pytest.approx(
        [check["wait_uploaded_minutes"], check["wait_moved_minutes"]], rel=1e-14)
    assert list(values[labels.index(B["B8"])][1:5]) == pytest.approx(
        [paired["mean"], paired["ci_lower"], paired["ci_upper"], paired["n"]], rel=1e-14)
    run_header = labels.index("Random seed")
    assert [row[0] for row in values[run_header + 1:]] == stored["des"]["seeds"]
    assert all(cell.data_type != "f" for row in sheet.iter_rows() for cell in row)  # values only
    assert _stored_setup(db_engine, aid) == baseline


def test_the_break_check_leaves_existing_report_numbers_byte_identical(db_engine, client):
    """The plan schedule and the key results come from the plan; the check only adds its own section."""
    aid, baseline, _, _, _, scenario = _saved(db_engine, client)
    _select(client, aid, scenario["id"])
    with_check = client.get(f"/analyses/{aid}/reports/plan/preview").json()["model"]
    plain = deepcopy(scenario)
    del plain["results"]["break_check"]
    with make_sessionmaker(db_engine)() as db:
        db.get(Scenario, scenario["id"]).results_json = plain["results"]
        db.commit()
    without = client.get(f"/analyses/{aid}/reports/plan/preview").json()["model"]
    assert without["break_check"] is None and without["breaks_note"] == B["B15"]
    for key in ("key_results", "periods", "plan_search", "formula_check", "assumptions", "breaks"):
        assert json.dumps(with_check[key], sort_keys=True) == json.dumps(without[key], sort_keys=True), key
    with_check["cover"] = without["cover"]
    books = [load_workbook(generate_plan_workbook(model)) for model in (with_check, without)]
    for name in ("Overview", "Your data", "Plan", "Formula check", "Plan search", "Assumptions"):
        assert [list(row) for row in books[0][name].iter_rows(values_only=True)] == \
            [list(row) for row in books[1][name].iter_rows(values_only=True)], name


def _model(*, baseline_breaks, plan_breaks=None, descriptor=True, check=None):
    baseline = {"queue_structure": "separate_queues", "breaks": baseline_breaks}
    plan = {**baseline, "breaks": baseline_breaks if plan_breaks is None else plan_breaks}
    calculation = {"schema_version": 2, "engine_version": "x", "options": {}}
    if descriptor:
        calculation["break_optimization"] = {"max_shift_minutes": 120}
    results = {"schedule": {"periods": [{"time": "10:00-11:00", "current_active_lanes": 1, "optimal_active_lanes": 1,
                                         "candidates": []}]}}
    if check is not None:
        results["break_check"] = check
    return build_separate_plan_model(
        analysis={"id": 1, "name": "A"}, scenario={"id": 2, "name": "P", "settings": {"calculation": calculation},
                                                   "results": results},
        dataset={"id": 3, "name": "D", "rows": []}, setup=plan, current_rows=[], baseline_setup=baseline)


BREAK = {"queue_id": "a", "scheduled_start_time": "10:00:00", "duration_minutes": 30}
MOVED = {**BREAK, "scheduled_start_time": "11:00:00", "original_start_time": "10:00:00"}


def _check(*, moves=True, wait_uploaded=2.5, peak_after=0.8, verdict="shorter", period_wait=None):
    proposed = {**BREAK, "label": "Break 1", "current_start_time": "10:00:00",
                "scheduled_start_time": "11:00:00" if moves else "10:00:00", "shift_minutes": 60 if moves else 0}
    side = lambda wait, period: {"summary": {"mean_wait_minutes": wait}, "periods": [  # noqa: E731
        {"time": "10:00-11:00", "mean_wait_minutes": period}],
        "replications": [{"seed": 42, "mean_wait_minutes": wait}, {"seed": 43, "mean_wait_minutes": wait}]}
    return {"basis": BREAK_CHECK_BASIS, "max_shift_minutes": 120, "des": {
        "seeds": [42, 43], "current": side(wait_uploaded, period_wait), "proposed": side(1.5, 1.25),
        "comparison": {"paired_wait_change": {"mean": -1.0, "ci_lower": -1.5, "ci_upper": -0.5, "n": 2,
                                              "verdict": verdict}}},
        "peak_rho": {"before": None, "after": peak_after}, "slots_above_target": {"before": 1, "after": 0},
        "moves": [{"queue_id": "a", "label": "Break 1", "from": "10:00", "to": "11:00", "duration_minutes": 30}]
        if moves else [], "current_breaks": [BREAK], "proposed_breaks": [proposed]}


def _render(model):
    model = {**model, "cover": {"label": "x", "analysis_name": "A", "plan_name": "P", "line_type": "separate",
                                "generated_at": "t"}, "key_results": {"cost_basis": "c"}}
    text = _flat(pdf_text(generate_report_pdf(model).getvalue()))
    return text, load_workbook(generate_plan_workbook(model)).sheetnames


def test_report_states_follow_the_owner_table():
    # Breaks off / no moves: existing breaks table and B14.
    no_moves = _model(baseline_breaks=[BREAK], check=_check(moves=False))
    assert (no_moves["breaks_title"], no_moves["breaks_note"], no_moves["break_check"]) == \
        ("Breaks in the Setup", B["B14"], None)
    assert pdf_sections(no_moves)[2:] == ["Breaks in the Setup"]
    text, sheets = _render(no_moves)
    assert B["B14"] in text and B["B1"] not in text and B["B1-tab"] not in sheets
    # A PR58-era plan with saved plan breaks but no break check: B17 + B15, no wait figures.
    older = _model(baseline_breaks=[BREAK], plan_breaks=[MOVED])
    assert (older["breaks_title"], older["breaks_note"], older["break_check"], older["key_results_note"]) == \
        (B["B17"], B["B15"], None, None)
    text, sheets = _render(older)
    assert pdf_sections(older)[2:] == [B["B17"]]
    assert _flat(B["B15"]) in text and B["B7"] not in text and B["B16"] not in text and B["B1-tab"] not in sheets
    # Pre-PR58 (no descriptor): unchanged, even if a stray break_check were present.
    legacy = _model(baseline_breaks=[BREAK], descriptor=False, check=_check())
    assert (legacy["breaks_title"], legacy["breaks_note"], legacy["break_check"], legacy["key_results_note"]) == \
        ("Breaks in the Setup", None, None, None)
    assert pdf_sections(legacy)[2:] == ["Breaks in the Setup"]
    # Setup has no breaks: no section at all.
    none = _model(baseline_breaks=[], check=_check(moves=False))
    assert pdf_sections(none) == ["Key results: now and with the plan", "By period"]
    assert none["breaks_note"] is None and none["break_check"] is None
    # K-BC-1: a PR58-era plan whose saved breaks equal the uploaded Setup keeps the Setup heading, with B15.
    same = _model(baseline_breaks=[BREAK], plan_breaks=[dict(BREAK)])
    assert (same["breaks_title"], same["breaks_note"], same["break_check"]) == ("Breaks in the Setup", B["B15"], None)
    assert pdf_sections(same)[2:] == ["Breaks in the Setup"]
    text, _ = _render(same)
    assert _flat(B["B15"]) in text and B["B17"] not in text
    # Moves with a saved check: only B1 (its B11/B13 tables); the older breaks table is not printed.
    moved = _model(baseline_breaks=[BREAK], plan_breaks=[MOVED], check=_check())
    assert pdf_sections(moved)[2:] == [B["B1"]]
    text, _ = _render(moved)
    assert B["B17"] not in text and "Breaks in the Setup" not in text
    assert B["B11"] in text and B["B13"] in text
    assert workbook_sheets(moved) == ["Overview", "Your data", "Plan", "Break check", "Formula check", "Plan search",
                                      "Assumptions", "Provenance"]


def test_missing_means_print_not_recorded_and_an_unbounded_load_cannot_keep_up():
    model = _model(baseline_breaks=[BREAK], plan_breaks=[MOVED], check=_check(wait_uploaded=None, period_wait=None))
    check = model["break_check"]
    assert check["wait_uploaded_minutes"] is None and check["peak_uploaded"] is None
    text, _ = _render(model)
    assert "not recorded" in text and "cannot keep up" in text and "80.0%" in text
    assert "1.2500" in text and "-1.0000 (-1.5000 to -0.5000), n = 2" in text  # 4 dp
    workbook = load_workbook(generate_plan_workbook({**model, "cover": {}, "key_results": {}}))
    rows = list(workbook["Break check"].iter_rows(values_only=True))
    assert rows[3][:3] == ("10:00-11:00", "not recorded", 1.25)
    peak = next(row for row in rows if row[0] == B["B10"])
    assert peak[1:3] == ("cannot keep up", 0.8)


@pytest.mark.parametrize("verdict", sorted(B9))
def test_each_verdict_prints_its_supervisor_sentence(verdict):
    model = _model(baseline_breaks=[BREAK], plan_breaks=[MOVED], check=_check(verdict=verdict))
    assert model["break_check"]["verdict_text"] == B9[verdict]
    assert _flat(B9[verdict]) in _render(model)[0]


def test_an_unknown_or_missing_verdict_is_unavailable():
    check = _check()
    del check["des"]["comparison"]["paired_wait_change"]["verdict"]
    model = _model(baseline_breaks=[BREAK], plan_breaks=[MOVED], check=check)
    assert model["break_check"]["verdict_text"] == B9["unavailable"]


def test_labels_are_the_owner_approved_text():
    assert plan_report.BREAK_CHECK_TITLE == B["B1"] and plan_report.BREAK_CHECK_SHEET == B["B1-tab"]
    assert plan_report.BREAK_CHECK_INTRO == B["B2"] and plan_report.BREAK_CHECK_KEY_NOTE == B["B16"]
    assert plan_report.BREAK_CHECK_VERDICTS == B9 and plan_report.BREAK_CHECK_COLUMNS == B12
    assert (plan_report.BREAK_CHECK_NO_MOVES, plan_report.BREAK_CHECK_NOT_SAVED, plan_report.BREAKS_PLAN_TITLE) == \
        (B["B14"], B["B15"], B["B17"])


# ── K-PR58-1: Setups with breaks keep refusing gapped or out-of-order segments ──

CONTIGUOUS_REFUSAL = "Current breaks require chronological, contiguous operating segments."


@pytest.mark.parametrize("second", [{"id": "s2", "start_time": "10:00", "end_time": "11:00"},
                                    {"id": "s0", "start_time": "07:00", "end_time": "08:00"}],
                         ids=["gapped", "out_of_order"])
def test_breaks_with_gapped_or_unordered_segments_are_refused_with_the_documented_message(monkeypatch, second):
    config = current_setup()
    config["segments"].append(second)
    result = run_current(monkeypatch, config)
    assert result["results"]
    assert all(row["simulation_supported"] is False for row in result["results"])
    assert {row["error"] for row in result["results"]} == {CONTIGUOUS_REFUSAL}
    assert result["trace"] == []
    without = current_setup([])
    without["segments"].append(second)
    assert not any(row.get("error") == CONTIGUOUS_REFUSAL for row in run_current(monkeypatch, without)["results"])
    assert engine.CURRENT_BREAK_POLICY == "scheduled_windows_nonpreemptive_v1"


# ── K-PR58-4: v3 Current results need a rerun only when the Setup has breaks ──


def test_v3_current_results_are_historical_when_the_setup_has_breaks(db_engine, client):
    from backend.api import workflow as workflow_api
    from backend.api.evidence_status import ReasonCode
    from backend.db.models import User

    aid, _, _, _ = _prepared(db_engine, client)
    current = client.post(f"/analyses/{aid}/workflow/simulation/des/current", headers=csrf_header(client),
                          json={"sim_hours": 1, "seed": 7, "max_events": 3000})
    assert current.status_code == 200, current.text
    job_id = current.json()["evidence"]["id"]
    assert client.get(f"/analyses/{aid}/workflow").json()["des_current"]["id"] == job_id
    with make_sessionmaker(db_engine)() as db:
        job = db.get(Job, job_id)
        assert job.params_json["current_des_basis"] == "current_break_windows_v4"
        job.params_json = {**job.params_json, "current_des_basis": "per_date_days_v3"}
        db.commit()
        analysis = db.get(AnalysisProject, aid)
        assert analysis.queue_setup_json["breaks"]
        context = workflow_api._evidence_context(db, db.get(User, analysis.user_id), analysis)
        policy = workflow_api._current_evidence_policy(setup=analysis.queue_setup_json)
        assessment = workflow_api._assess_evidence(db, db.get(Job, job_id), context, policy)
        assert not assessment.is_current
        assert [reason.code for reason in assessment.reasons if reason.subject == "Current DES accounting"] == \
            [ReasonCode.VERSION_HISTORICAL]
    assert client.get(f"/analyses/{aid}/workflow").json()["des_current"] is None


def test_v3_is_current_only_for_a_setup_without_breaks():
    from backend.api.workflow import CURRENT_DES_BASIS, _current_evidence_policy

    def family(setup):
        requirement = _current_evidence_policy(setup=setup).current_des_accounting
        assert requirement is not None
        return requirement.family

    assert family({"breaks": []}).classify("per_date_days_v3") == "current"
    assert family({}).classify("per_date_days_v3") == "current"
    assert family({"breaks": [BREAK]}).classify("per_date_days_v3") == "historical"
    assert family(None).classify("per_date_days_v3") == "historical"  # unknown Setup fails closed
    for setup in ({}, {"breaks": [BREAK]}, None):
        assert family(setup).classify(CURRENT_DES_BASIS) == "current"
        assert family(setup).classify("per_date_days_v1") == "historical"
        assert family(setup).classify("per_date_days_v2") == "historical"
