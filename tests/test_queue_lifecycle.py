"""Tests for the separate-queue closure contract, without DES execution."""

from collections import deque

import pytest

from backend.queueing_engine.simulation.queue_lifecycle import (
    DedicatedQueueLifecycle,
    DedicatedQueueState,
    QueueReactivationPolicyError,
    apply_scheduled_activity,
    dedicated_server_id,
    scheduled_active_queue_ids,
)


def test_active_queue_accepts_arrivals_and_preserves_fifo():
    queue = DedicatedQueueLifecycle("queue_a", "server:queue_a")
    assert queue.accepts_arrivals is True
    assert queue.enqueue("a-1") is True
    assert queue.enqueue("a-2") is True
    assert queue.begin_service() == "a-1"
    assert queue.waiting_customer_ids == deque(["a-2"])


def test_closing_queue_enters_draining_and_rejects_new_arrivals():
    queue = DedicatedQueueLifecycle("queue_a", "server:queue_a")
    queue.enqueue("a-1")
    queue.enqueue("a-2")
    assert queue.begin_service() == "a-1"
    assert queue.transition_for_segment(active=False) == DedicatedQueueState.DRAINING
    assert queue.accepts_arrivals is False
    assert queue.enqueue("a-3") is False
    assert list(queue.waiting_customer_ids) == ["a-2"]


def test_draining_does_not_interrupt_service_and_becomes_inactive_when_empty():
    queue = DedicatedQueueLifecycle("queue_a", "server:queue_a")
    queue.enqueue("a-1")
    queue.enqueue("a-2")
    queue.begin_service()
    queue.transition_for_segment(active=False)
    assert queue.in_service_customer_id == "a-1"
    assert queue.server_id == "server:queue_a"
    assert queue.complete_service() == "a-1"
    assert queue.state == DedicatedQueueState.DRAINING
    assert queue.begin_service() == "a-2"
    assert queue.complete_service() == "a-2"
    assert queue.state == DedicatedQueueState.INACTIVE


def test_inactive_queue_can_reactivate_but_draining_reactivation_requires_policy():
    queue = DedicatedQueueLifecycle("queue_a", "server:queue_a")
    assert queue.transition_for_segment(active=False) == DedicatedQueueState.INACTIVE
    assert queue.transition_for_segment(active=True) == DedicatedQueueState.ACTIVE
    queue.enqueue("a-1")
    queue.transition_for_segment(active=False)
    with pytest.raises(QueueReactivationPolicyError, match="still draining"):
        queue.transition_for_segment(active=True)


def test_unrelated_active_queue_is_not_affected_and_no_transfer_exists():
    queue_a = DedicatedQueueLifecycle("queue_a", "server:queue_a")
    queue_b = DedicatedQueueLifecycle("queue_b", "server:queue_b")
    queue_a.enqueue("a-1")
    queue_a.transition_for_segment(active=False)
    assert queue_a.state == DedicatedQueueState.DRAINING
    assert queue_b.state == DedicatedQueueState.ACTIVE
    assert list(queue_b.waiting_customer_ids) == []
    assert queue_a.server_id != queue_b.server_id
    assert list(queue_a.waiting_customer_ids) == ["a-1"]


def test_schedule_resolves_fixed_staffing_from_configured_queue_set():
    setup = {"queue_structure": "separate_queues", "queue_ids": ["a", "b"], "staffing_varies_by_period": False}
    assert scheduled_active_queue_ids(setup, {"active_queue_ids": ["a"]}) == frozenset({"a", "b"})


def test_fixed_staffing_keeps_zero_workload_queue_active():
    setup = {"queue_structure": "separate_queues", "queue_ids": ["a", "b"], "staffing_varies_by_period": False}
    queues = {queue_id: DedicatedQueueLifecycle(queue_id, dedicated_server_id(queue_id)) for queue_id in setup["queue_ids"]}
    states = apply_scheduled_activity(queues, setup, {"lambda_by_queue": {"a": 1.0}})
    assert states == {"a": DedicatedQueueState.ACTIVE, "b": DedicatedQueueState.ACTIVE}


def test_schedule_resolves_variable_staffing_only_from_active_queue_ids():
    setup = {"queue_structure": "separate_queues", "queue_ids": ["a", "b"], "staffing_varies_by_period": True}
    assert scheduled_active_queue_ids(setup, {"active_queue_ids": ["a"]}) == frozenset({"a"})
    with pytest.raises(ValueError, match="requires active_queue_ids"):
        scheduled_active_queue_ids(setup, {})


def test_activity_schedule_transitions_removed_queue_and_preserves_server_identity():
    setup = {"queue_structure": "separate_queues", "queue_ids": ["a", "b", "c"], "staffing_varies_by_period": True}
    queues = {queue_id: DedicatedQueueLifecycle(queue_id, dedicated_server_id(queue_id)) for queue_id in setup["queue_ids"]}
    queues["c"].enqueue("c-1")
    first = apply_scheduled_activity(queues, setup, {"active_queue_ids": ["a", "b", "c"]})
    second = apply_scheduled_activity(queues, setup, {"active_queue_ids": ["a", "b"]})
    assert first == {"a": DedicatedQueueState.ACTIVE, "b": DedicatedQueueState.ACTIVE, "c": DedicatedQueueState.ACTIVE}
    assert second == {"a": DedicatedQueueState.ACTIVE, "b": DedicatedQueueState.ACTIVE, "c": DedicatedQueueState.DRAINING}
    assert queues["c"].server_id == "server:c"
