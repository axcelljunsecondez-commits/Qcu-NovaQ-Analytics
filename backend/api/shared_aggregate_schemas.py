"""Additive contracts for shared aggregate preview and atomic apply."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from backend.api.analysis_schemas import AbandonmentMode, CapacityMode
from backend.api.datasets import DatasetOut


class SharedAggregateChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capacity_mode: CapacityMode | None = None
    total_system_capacity: StrictInt | None = Field(default=None, ge=1, le=100000)
    abandonment_mode: AbandonmentMode | None = None
    patience_rate_per_hour: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class SharedAggregateApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    setup_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_replace: StrictBool = False
    choices: SharedAggregateChoices = Field(default_factory=SharedAggregateChoices)


class SharedAggregateRow(BaseModel):
    time: str
    lambda_: float = Field(alias="lambda")
    mu: float
    c: int


class SharedAggregateFacts(BaseModel):
    filename: str
    row_count: int
    start_time: str
    end_time: str
    counter_min: int
    counter_max: int
    lambda_min: float
    lambda_max: float
    mu_min: float
    mu_max: float
    rows: list[SharedAggregateRow]


class SharedAggregatePreviewOut(BaseModel):
    mode: Literal["shared_aggregate", "declined"]
    file_digest: str
    setup_revision: str
    facts: SharedAggregateFacts | None
    derived_setup: dict[str, Any] | None
    saved_setup: dict[str, Any]
    diff: list[dict[str, Any]]
    needs_confirmation: bool
    unresolved: list[Literal["capacity_mode", "abandonment_mode"]]
    conflicts: list[dict[str, Any]]
    reasons: list[dict[str, Any]]


class SharedAggregateApplyOut(BaseModel):
    dataset: DatasetOut
    analysis: dict[str, Any]
    duplicate: bool
