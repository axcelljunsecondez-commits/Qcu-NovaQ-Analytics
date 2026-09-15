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
