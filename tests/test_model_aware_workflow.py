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
