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
