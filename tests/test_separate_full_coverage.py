"""Separate-queue FULL COVERAGE: every configured lane stays active.

Approved rule: min_active_lanes == configured queue count, enforced through
the existing lane-bound mechanism (no new mathematics). A plan can never be
cheapened by closing a lane and rerouting its demand.
"""

from __future__ import annotations

from backend.queueing_engine.services.separate_optimization import (
    build_candidates,
    optimize_separate,
)
from tests.helpers import csrf_header, login
from tests.test_optimize_separate_save import _run, _save, _snapshot, _workspace

QUEUES = ["lane-a", "lane-b"]


def test_full_coverage_bound_equals_configured_queue_count():
    from backend.queueing_engine.services.separate_optimization import full_coverage_min_lanes

    setup = {"queue_structure": "separate_queues", "queue_ids": ["a", "b", "c"]}
    assert full_coverage_min_lanes(setup, None) == 3
    assert full_coverage_min_lanes(setup, 3) == 3
    for bad in (1, 2, 4):
        try:
            full_coverage_min_lanes(setup, bad)
        except ValueError as exc:
            assert "full coverage" in str(exc).lower()
        else:
            raise AssertionError(f"min_active_lanes={bad} must be rejected")


def test_lower_bound_leaves_only_the_full_lane_set():
    ids = ["a", "b", "c"]
    assert build_candidates(ids, min_lanes=len(ids)) == [
        {"active_queue_ids": ids, "inactive_queue_ids": []}]


def test_optimizer_never_evaluates_reduced_sets_under_full_coverage():
    samples = [0.05, 0.08, 0.10, 0.12]
    rows = [{"time": "08:00", "queue_id": q, "lambda": lam, "mu": 11.0, "c": 1,
             "service_samples_hours": list(samples)}
            for q, lam in (("lane-a", 4.0), ("lane-b", 2.0), ("lane-c", 1.0))]
    result = optimize_separate("08:00", rows, target=0.70, min_lanes=3,
                               des_replications={"replications": 2, "base_seed": 7,
                                                 "duration_hours": 4.0, "max_events": 500})
    assert result["overall"] == "OPTIMAL"
    assert [c["active_lane_count"] for c in result["candidates"]] == [3]
    assert result["optimum"]["inactive_queue_ids"] == []


def test_endpoint_keeps_every_configured_lane_active(db_engine, client):
    analysis_id, _, _ = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    response = _run(client, analysis_id, 0.70)
    assert response.status_code == 200, response.text
    schedule = response.json()["schedule"]
    assert schedule["overall"] == "COMPLETE"
    for period in schedule["periods"]:
        assert period["optimal_active_lanes"] == len(QUEUES)
        assert period["optimum"]["active_queue_ids"] == QUEUES
        assert period["optimum"]["inactive_queue_ids"] == []
        for candidate in period["candidates"]:
            assert candidate["inactive_queue_ids"] == []


def test_endpoint_rejects_lane_closing_bounds(db_engine, client):
    analysis_id, _, _ = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    response = client.post(
        f"/analyses/{analysis_id}/workflow/optimize/separate",
        headers=csrf_header(client),
        json={"target_utilization": 0.70, "min_active_lanes": 1},
    )
    assert response.status_code == 422
    assert "full coverage" in response.text.lower()


def test_save_requires_recorded_full_coverage(db_engine, client):
    analysis_id, dataset_id, row_count = _workspace(db_engine, "u@example.com")
    login(client, "u@example.com", "pw")
    schedule = _run(client, analysis_id, 0.70).json()["schedule"]
    settings, results = _snapshot(analysis_id, dataset_id, row_count, 0.70, schedule)
    for bound in (None, 1):
        bad = {**settings, "min_active_lanes": bound,
               "calculation": {**settings["calculation"],
                               "options": {**settings["calculation"]["options"],
                                           "min_active_lanes": bound}}}
        assert _save(client, "Closing", analysis_id, dataset_id, bad, results).status_code == 422
    assert _save(client, "Full", analysis_id, dataset_id, settings, results).status_code == 201
