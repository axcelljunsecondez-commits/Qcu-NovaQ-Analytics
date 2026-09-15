"""Model-aware workflow regressions (Approach A, additive only)."""
from backend.queueing_engine.services.model_selection import select_model


def test_select_model_authority_and_matrix():
    pooled = select_model(10.0, 4.0, 3)
    assert pooled["model_id"] == "mmc"
    assert "queue_structure" not in pooled
    sep = select_model(5.0, 4.0, 1, variance=0.0625, queue_structure="separate_queues")
    assert sep["model_id"] == "parallel_mg1"
    blocked = select_model(5.0, 4.0, 2, variance=0.0625, queue_structure="separate_queues")
    assert blocked["model_id"] == "separate_fifo_unsupported"


def test_separate_optimizer_blocked_no_fake_evidence():
    from backend.queueing_engine.services.optimization import optimize_segment
    res = optimize_segment({"time": "08:00", "lambda": 5.0, "mu": 4.0, "c": 1, "variance": 0.0625, "queue_structure": "separate_queues", "model_id": "parallel_mg1"})
    assert res["c_optimal"] is None
    assert res["optimized_stable"] is False
    assert res["feasibility_status"] == "INVALID_INPUT"
    assert "Parallel M/G/1" in (res.get("warning") or "")


def test_decision_never_adopts_from_current_des_only():
    from types import SimpleNamespace

    from backend.api.workflow import _derive_decision

    analysis = SimpleNamespace(setup_status="ready")
    evidence = {
        "selection": None,
        "des": {"id": 99, "params": {}, "result": {"provenance": "CURRENT", "results": []}},
        "mc": None,
        "validation": None,
    }
    d = _derive_decision(analysis, None, evidence)  # type: ignore[arg-type]
    assert d["status"] in ("insufficient_evidence", "revise")
    assert d["status"] != "adopt"
    assert "optimiz" not in d.get("recommendation", "").lower() or "not available" in d.get("recommendation", "").lower()


def test_current_only_report_marks_blocked_not_zero(db_engine, client):
    import io

    import openpyxl

    from backend.api.reports import _separate_current_payload
    from backend.db.models import Dataset
    from tests.helpers import create_user, login, make_sessionmaker

    user = create_user(db_engine, "current-only-reports@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        dataset = Dataset(
            user_id=user.id,
            analysis_id=None,
            name="Separate current",
            source_filename="segments.csv",
            source_format="csv",
            row_count=1,
            normalized_json=[{
                "time": "08:00",
                "queue_id": "Q1",
                "queue_structure": "separate_queues",
                "model_id": "parallel_mg1",
                "lambda": 5.0,
                "mu": 4.0,
                "c": 1,
                "variance": 0.0625,
            }],
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.commit()
        dataset_id = dataset.id
        comparison_df, kpis, recommendations = _separate_current_payload(dataset)
    joined = "\n".join(recommendations)
    assert "BLOCKED" in joined and "DEMAND ALLOCATION POLICY NOT DEFINED" in joined
    assert "NOT APPLICABLE" in joined
    assert "NOT AVAILABLE" in joined
    assert "N/A" in joined
    assert "c_optimal" not in comparison_df.columns
    assert "c_optimal" not in kpis
    assert "total_savings" not in kpis
    assert "roi" not in " ".join(str(k).lower() for k in kpis)
    login(client, "current-only-reports@example.com", "pw")
    pdf = client.get(f"/reports/datasets/{dataset_id}/pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content[:4] == b"%PDF"
    excel = client.get(f"/reports/datasets/{dataset_id}/excel")
    assert excel.status_code == 200, excel.text
    wb = openpyxl.load_workbook(io.BytesIO(excel.content))
    rec_text = " ".join(
        str(cell.value or "") for row in wb["Recommendations"].iter_rows() for cell in row
    )
    assert "BLOCKED" in rec_text
    assert "DEMAND ALLOCATION POLICY NOT DEFINED" in rec_text
    assert "NOT APPLICABLE" in rec_text
    assert "NOT AVAILABLE" in rec_text
    headers = [cell.value for cell in wb["Segments"][1]]
    assert "c_optimal" not in headers
    assert "total_savings" not in headers


def test_current_des_fallback_provenance(db_engine, client):
    from backend.db.models import AnalysisProject, Dataset
    from tests.helpers import create_user, csrf_header, login, make_sessionmaker

    user = create_user(db_engine, "current-des-owner@example.com", "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id,
            name="Current DES branch",
            queue_setup_json={
                "queue_structure": "separate_queues",
                "queue_ids": ["queue_a"],
                "fixed_server_count": 1,
                "staffing_varies_by_period": False,
                "capacity_mode": "unlimited",
                "total_system_capacity": None,
                "abandonment_mode": "not_modeled",
                "patience_rate_per_hour": None,
                "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}],
                "separate_queue_closure_policy": "drain_existing",
            },
            setup_status="ready",
        )
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            analysis_id=analysis.id,
            name="Current empirical",
            source_filename="events.csv",
            source_format="csv",
            row_count=1,
            normalized_json=[{
                "time": "s1",
                "segment_id": "s1",
                "queue_id": "queue_a",
                "queue_structure": "separate_queues",
                "model_id": "parallel_mg1",
                "server_id": "server:queue_a",
                "lambda": 4.0,
                "mu": 4.0,
                "c": 1,
                "variance": 0.0025,
                "service_time_source": "empirical",
                "service_samples_hours": [0.05, 0.1],
            }],
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.commit()
        analysis_id = analysis.id
    login(client, "current-des-owner@example.com", "pw")
    r = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/current",
        headers=csrf_header(client),
        json={"sim_hours": 1, "max_events": 100},
    )
    assert r.status_code == 200, r.text
    assert r.json()["evidence"]["result"]["provenance"] == "CURRENT"
    assert "c_optimal" not in r.json()["evidence"]["result"]


def _seed_separate_current_analysis(db_engine, email="des-current-evidence@example.com"):
    from backend.db.models import AnalysisProject, Dataset
    from tests.helpers import create_user, make_sessionmaker

    user = create_user(db_engine, email, "pw")
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id,
            name="Current DES evidence",
            queue_setup_json={
                "queue_structure": "separate_queues",
                "queue_ids": ["queue_a"],
                "fixed_server_count": 1,
                "staffing_varies_by_period": False,
                "capacity_mode": "unlimited",
                "total_system_capacity": None,
                "abandonment_mode": "not_modeled",
                "patience_rate_per_hour": None,
                "segments": [{"id": "s1", "start_time": "07:00:00", "end_time": "08:00:00", "active_queue_ids": None}],
                "separate_queue_closure_policy": "drain_existing",
            },
            setup_status="ready",
        )
        db.add(analysis)
        db.flush()
        dataset = Dataset(
            user_id=user.id,
            analysis_id=analysis.id,
            name="Current empirical",
            source_filename="events.csv",
            source_format="csv",
            row_count=1,
            normalized_json=[{
                "time": "s1",
                "segment_id": "s1",
                "queue_id": "queue_a",
                "queue_structure": "separate_queues",
                "model_id": "parallel_mg1",
                "server_id": "server:queue_a",
                "lambda": 4.0,
                "mu": 4.0,
                "c": 1,
                "variance": 0.0025,
                "service_time_source": "empirical",
                "service_samples_hours": [0.05, 0.1],
            }],
            validation_report_json={"ok": True, "message": "Input data is valid."},
        )
        db.add(dataset)
        db.commit()
        return analysis.id


def test_des_current_exposed_in_workflow_evidence_separate_from_des(db_engine, client):
    from tests.helpers import csrf_header, login

    analysis_id = _seed_separate_current_analysis(db_engine)
    login(client, "des-current-evidence@example.com", "pw")
    run = client.post(
        f"/analyses/{analysis_id}/workflow/simulation/des/current",
        headers=csrf_header(client),
        json={"sim_hours": 1, "max_events": 100},
    )
    assert run.status_code == 200, run.text
    job_id = run.json()["evidence"]["id"]
    evidence = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert evidence["scenario"] is None
    assert evidence["des"] is None
    assert evidence["des_current"] is not None
    assert evidence["des_current"]["id"] == job_id
    assert evidence["des_current"]["kind"] == "workflow_des_current"
    assert evidence["des_current"]["result"]["provenance"] == "CURRENT"


def test_missing_des_current_stays_null_not_fabricated(db_engine, client):
    from tests.helpers import login

    analysis_id = _seed_separate_current_analysis(db_engine, "des-current-absent@example.com")
    login(client, "des-current-absent@example.com", "pw")
    evidence = client.get(f"/analyses/{analysis_id}/workflow").json()
    assert evidence["des"] is None
    assert evidence["des_current"] is None


def test_decision_ignores_des_current_key():
    from types import SimpleNamespace

    from backend.api.workflow import _derive_decision

    analysis = SimpleNamespace(setup_status="ready")
    evidence = {
        "selection": None,
        "des": None,
        "des_current": {"id": 7, "params": {}, "result": {"provenance": "CURRENT", "results": []}},
        "mc": None,
        "validation": None,
    }
    d = _derive_decision(analysis, None, evidence)  # type: ignore[arg-type]
    assert d["status"] == "insufficient_evidence"
    assert d["evidence_ids"]["des"] is None
