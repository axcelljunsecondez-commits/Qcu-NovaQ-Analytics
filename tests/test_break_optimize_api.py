"""Separate-queue break optimizer endpoint: schedules, slot rho, DES proof.

Spec: docs/superpowers/specs/2026-09-18-separate-break-optimizer.md.
"""

from __future__ import annotations

import pandas as pd

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.db.models import AnalysisProject, Dataset
from backend.queueing_engine.services import break_optimization as bo
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

SHARED_NOTE = "Break optimization is available for separate queues."


def _setup(**over) -> dict:
    base = {
        "queue_structure": "separate_queues",
        "fixed_server_count": 2,
        "staffing_varies_by_period": False,
        "capacity_mode": "unlimited",
        "abandonment_mode": "not_modeled",
        "event_period_basis": "representative_day",
        "segments": [{"id": None, "start_time": f"{h:02d}:00:00", "end_time": f"{h + 1:02d}:00:00",
                      "active_queue_ids": None} for h in range(8, 13)],
        "queue_ids": ["a", "b"],
        # Both breaks stacked in the 10:00 rush: nobody works 10:00-10:30.
        "breaks": [{"queue_id": "a", "scheduled_start_time": "10:00:00", "duration_minutes": 30},
                   {"queue_id": "b", "scheduled_start_time": "10:00:00", "duration_minutes": 30}],
    }
    base.update(over)
    return QueueSetup.model_validate(base).model_dump(mode="json")


def _events() -> pd.DataFrame:
    rows = []
    for date in ("2026-08-03", "2026-08-04"):
        for hour in range(8, 13):
            gap = 10 if hour == 10 else 20
            for minute in range(0, 60, gap):
                for queue, offset in (("a", 0), ("b", 5)):
                    start = pd.Timestamp(f"{date}T{hour:02d}:{minute + offset:02d}:00Z")
                    rows.append({"arrival_time": start.isoformat(), "service_start": start.isoformat(),
                                 "service_end": (start + pd.Timedelta(minutes=4)).isoformat(),
                                 "queue_id": queue})
    return pd.DataFrame(rows)


def _workspace(db_engine, email="brk@example.com", setup=None) -> tuple[int, dict]:
    setup = setup or _setup()
    records, provenance = normalize_analysis_input(_events(), QueueSetup.model_validate(setup))
    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Breaks", queue_setup_json=setup,
                                   setup_status="ready")
        db.add(analysis)
        db.flush()
        db.add(Dataset(user_id=user.id, analysis_id=analysis.id, name="Events", source_filename="e.csv",
                       source_format="csv", row_count=len(records), normalized_json=records,
                       validation_report_json={"ok": True, "message": "Input data is valid.", **provenance}))
        db.commit()
        return analysis.id, setup


def _run(client, analysis_id, body=None):
    return client.post(f"/analyses/{analysis_id}/workflow/optimize/separate/breaks",
                       headers=csrf_header(client), json=body or {})


def test_break_optimize_returns_schedules_rho_and_des(db_engine, client):
    analysis_id, _ = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    response = _run(client, analysis_id, {"des": {"replications": 2, "base_seed": 7}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "improved"
    assert body["target_rho"] == 0.85 and body["max_shift_minutes"] == 120
    assert [b["scheduled_start_time"] for b in body["current_breaks"]] == ["10:00:00", "10:00:00"]
    assert len(body["proposed_breaks"]) == 2 and body["moves"]
    assert len(body["slots"]) == 20
    rush = next(slot for slot in body["slots"] if slot["start"] == "10:00")
    assert rush["rho_before"] is None and rush["working_before"] == 0
    assert rush["rho_after"] is not None
    assert body["peak_rho"]["before"] is None and body["peak_rho"]["after"] is not None
    des = body["des"]
    assert des["seeds"] == [7, 8]
    for schedule in ("current", "proposed"):
        assert len(des[schedule]["replications"]) == 2
        assert des[schedule]["summary"]["customer_conservation"] is True
        assert des[schedule]["summary"]["mean_wait_minutes"] is not None
        assert [p["time"] for p in des[schedule]["periods"]][0] == "08:00-09:00"
    assert des["comparison"]["runs"] == 2
    assert len(body["notes"]) == 2


def test_break_optimize_runs_existing_day_des_with_same_seeds(db_engine, client, monkeypatch):
    calls = []
    original = bo.run_routing_day_des

    def spy(windows, *, tie_order, seed, max_events, breaks=None):
        calls.append((seed, sorted((b["queue_id"], round(b["start_hours"], 6)) for b in breaks or [])))
        return original(windows, tie_order=tie_order, seed=seed, max_events=max_events, breaks=breaks)

    monkeypatch.setattr(bo, "run_routing_day_des", spy)
    analysis_id, _ = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    body = _run(client, analysis_id, {"des": {"replications": 3, "base_seed": 42}}).json()
    assert [seed for seed, _ in calls] == [42, 43, 44, 42, 43, 44]
    current, proposed = calls[0][1], calls[3][1]
    assert current == [("a", 2.0), ("b", 2.0)]                 # 10:00 is 2 h after the 08:00 origin
    expected = sorted((b["queue_id"], round((int(b["scheduled_start_time"][:2]) * 60
                                            + int(b["scheduled_start_time"][3:5]) - 480) / 60, 6))
                      for b in body["proposed_breaks"])
    assert proposed == expected and proposed != current


def test_break_optimize_does_not_change_setup(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    assert _run(client, analysis_id, {"des": {"replications": 1}}).status_code == 200
    with make_sessionmaker(db_engine)() as db:
        assert db.get(AnalysisProject, analysis_id).queue_setup_json == setup


def test_break_optimize_rejects_shared_queue(db_engine, client):
    user = create_user(db_engine, "shared@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(user_id=user.id, name="Shared", setup_status="ready",
                                   queue_setup_json={"queue_structure": "shared_queue", "fixed_server_count": 2})
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id
    login(client, "shared@example.com", "pw")
    response = _run(client, analysis_id)
    assert response.status_code == 422
    assert response.json()["detail"] == SHARED_NOTE


def test_break_optimize_rejects_per_date_and_missing_breaks(db_engine, client):
    analysis_id, setup = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    for change, message in (({"event_period_basis": "per_date"},
                             "Break optimization requires the representative day basis."),
                            ({"breaks": []}, "This Analysis has no configured breaks to move.")):
        with make_sessionmaker(db_engine)() as db:
            db.get(AnalysisProject, analysis_id).queue_setup_json = {**setup, **change}
            db.commit()
        response = _run(client, analysis_id)
        assert response.status_code == 422
        assert response.json()["detail"] == message


def test_break_optimize_request_bounds(db_engine, client):
    analysis_id, _ = _workspace(db_engine)
    login(client, "brk@example.com", "pw")
    for bad in ({"target_rho": 0}, {"target_rho": 1.01}, {"max_shift_minutes": 20},
                {"max_shift_minutes": 255}, {"max_shift_minutes": -15},
                {"des": {"replications": 0}}, {"des": {"replications": 21}}):
        assert _run(client, analysis_id, bad).status_code == 422, bad
    assert _run(client, analysis_id, {"target_rho": 1.0, "max_shift_minutes": 0,
                                      "des": {"replications": 1}}).status_code == 200


def test_break_optimize_requires_auth(client):
    assert client.post("/analyses/1/workflow/optimize/separate/breaks", json={}).status_code in (401, 403)
