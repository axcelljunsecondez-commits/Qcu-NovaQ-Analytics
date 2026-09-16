"""Dedicated-queue lifecycle contract for future Parallel M/G/1 DES."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class DedicatedQueueState(str, Enum):
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    INACTIVE = "INACTIVE"


class QueueReactivationPolicyError(RuntimeError):
    """Raised when a draining queue is scheduled active again."""


def dedicated_server_id(queue_id: str) -> str:
    """Return the stable server identity dedicated to one queue."""
    return f"server:{queue_id}"


def scheduled_active_queue_ids(queue_setup: Mapping, segment: Mapping) -> frozenset[str]:
    """Resolve scheduled activity from setup, never from workload rows."""
    if queue_setup.get("queue_structure") != "separate_queues":
        return frozenset()
    queue_ids = frozenset(str(queue_id) for queue_id in queue_setup.get("queue_ids", []))
    if not queue_setup.get("staffing_varies_by_period", False):
        return queue_ids
    active = segment.get("active_queue_ids")
    if active is None:
        raise ValueError("Variable separate-queue staffing requires active_queue_ids for every segment.")
    return frozenset(str(queue_id) for queue_id in active)


def apply_scheduled_activity(
    lifecycles: Mapping[str, DedicatedQueueLifecycle],
    queue_setup: Mapping,
    segment: Mapping,
) -> dict[str, DedicatedQueueState]:
    """Apply one authoritative segment activity map to dedicated queues."""
    active_ids = scheduled_active_queue_ids(queue_setup, segment)
    return {
        queue_id: lifecycle.transition_for_segment(queue_id in active_ids)
        for queue_id, lifecycle in lifecycles.items()
    }


@dataclass
class DedicatedQueueLifecycle:
    """State contract for one queue and its permanently dedicated server.

    The future DES supplies the authoritative ``active`` flag for each
    structured segment. This object deliberately does not route or transfer
    customers between queues.
    """

    queue_id: str
    server_id: str
    state: DedicatedQueueState = DedicatedQueueState.ACTIVE
    waiting_customer_ids: deque[str] = field(default_factory=deque)
    in_service_customer_id: str | None = None

    def __post_init__(self) -> None:
        if self.server_id != dedicated_server_id(self.queue_id):
            raise ValueError("Dedicated server identity must be server:{queue_id}.")

    @property
    def accepts_arrivals(self) -> bool:
        return self.state == DedicatedQueueState.ACTIVE

    def transition_for_segment(self, active: bool) -> DedicatedQueueState:
        """Apply the next segment's activity without reassigning customers."""
        if active:
            if self.state == DedicatedQueueState.DRAINING:
                raise QueueReactivationPolicyError(
                    f"Queue {self.queue_id} is still draining when scheduled active again."
                )
            if self.state == DedicatedQueueState.INACTIVE:
                self.state = DedicatedQueueState.ACTIVE
            return self.state

        if self.state == DedicatedQueueState.ACTIVE:
            self.state = DedicatedQueueState.DRAINING
        self._finish_if_empty()
        return self.state

    def enqueue(self, customer_id: str) -> bool:
        """Append a new customer only while the queue is active."""
        if not self.accepts_arrivals:
            return False
        self.waiting_customer_ids.append(customer_id)
        return True

    def begin_service(self) -> str | None:
        """Take the oldest waiting customer for this queue's server."""
        if self.in_service_customer_id is not None or not self.waiting_customer_ids:
            return None
        self.in_service_customer_id = self.waiting_customer_ids.popleft()
        return self.in_service_customer_id

    def complete_service(self) -> str | None:
        """Complete the current service and close a drained queue if empty."""
        completed = self.in_service_customer_id
        self.in_service_customer_id = None
        self._finish_if_empty()
        return completed

    def _finish_if_empty(self) -> None:
        if (
            self.state == DedicatedQueueState.DRAINING
            and not self.waiting_customer_ids
            and self.in_service_customer_id is None
        ):
            self.state = DedicatedQueueState.INACTIVE


__all__ = [
    "DedicatedQueueLifecycle",
    "DedicatedQueueState",
    "QueueReactivationPolicyError",
]
