"""Validated API schemas for Analysis queue setup."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueueStructure(str, Enum):
    shared_queue = "shared_queue"
    single_server = "single_server"
    separate_queues = "separate_queues"
    unknown = "unknown"


class CapacityMode(str, Enum):
    unlimited = "unlimited"
    finite = "finite"
    unknown = "unknown"


class AbandonmentMode(str, Enum):
    not_modeled = "not_modeled"
    modeled = "modeled"
    unknown = "unknown"


class QueueSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_structure: QueueStructure = QueueStructure.unknown
    fixed_server_count: int | None = Field(default=None, ge=1, le=100000)
    staffing_varies_by_period: bool = False
    capacity_mode: CapacityMode = CapacityMode.unknown
    total_system_capacity: int | None = Field(default=None, ge=1, le=100000)
    abandonment_mode: AbandonmentMode = AbandonmentMode.unknown
    patience_rate_per_hour: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_dependencies(self) -> QueueSetup:
        if self.queue_structure == QueueStructure.single_server:
            if self.staffing_varies_by_period:
                raise ValueError("A single-server queue cannot vary staffing by period.")
            if self.fixed_server_count not in (None, 1):
                raise ValueError("A single-server queue must have exactly one server.")
            self.fixed_server_count = 1
        if self.capacity_mode != CapacityMode.finite and self.total_system_capacity is not None:
            raise ValueError("Total system capacity is only valid for finite capacity.")
        if (
            self.capacity_mode == CapacityMode.finite
            and self.total_system_capacity is not None
            and self.fixed_server_count is not None
            and self.total_system_capacity < self.fixed_server_count
        ):
            raise ValueError("Total system capacity must include and be at least the server count.")
        if self.abandonment_mode != AbandonmentMode.modeled and self.patience_rate_per_hour is not None:
            raise ValueError("Patience rate is only valid when abandonment is modeled.")
        return self


def setup_status(setup: QueueSetup) -> str:
    if setup.queue_structure == QueueStructure.separate_queues:
        return "unsupported"
    if setup.queue_structure == QueueStructure.unknown:
        return "incomplete"
    if setup.capacity_mode == CapacityMode.finite and setup.total_system_capacity is None:
        return "incomplete"
    if setup.abandonment_mode == AbandonmentMode.modeled and setup.patience_rate_per_hour is None:
        return "incomplete"
    if setup.staffing_varies_by_period:
        return "ready_for_aggregate"
    if setup.fixed_server_count is None:
        return "incomplete"
    return "ready"


def unknown_queue_setup() -> QueueSetup:
    return QueueSetup()
