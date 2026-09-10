"""Analysis upload schema detection, normalization, and provenance."""

from __future__ import annotations

import pandas as pd

from backend.api.analysis_schemas import (
    AbandonmentMode,
    CapacityMode,
    QueueSetup,
    QueueStructure,
)
from backend.data.ingestion import REQUIRED_COLUMNS, to_segment_records, validate_and_normalize

EVENT_REQUIRED = {"arrival_time", "service_start", "service_end"}
AGGREGATE_REQUIRED = set(REQUIRED_COLUMNS)


class AnalysisIngestionError(ValueError):
    """Safe validation message for an Analysis upload."""


def _schema(columns: set[str]) -> str:
    aggregate = AGGREGATE_REQUIRED <= columns
    event = EVENT_REQUIRED <= columns
    if aggregate and event:
        raise AnalysisIngestionError(
            "The file contains both aggregate and customer-event schemas; upload only one schema."
        )
    if aggregate:
        return "aggregate"
    if event:
        return "customer_events"
    present_event = EVENT_REQUIRED & columns
    if present_event:
        missing = sorted(EVENT_REQUIRED - columns)
        raise AnalysisIngestionError(f"Missing customer-event columns: {', '.join(missing)}.")
    missing = sorted(AGGREGATE_REQUIRED - columns)
    raise AnalysisIngestionError(
        "Schema could not be identified. Missing aggregate columns: " + ", ".join(missing) + "."
    )


def normalize_analysis_input(
    frame: pd.DataFrame, setup: QueueSetup
) -> tuple[list[dict], dict]:
    """Return existing segment records plus transparent field provenance."""
    if frame is None or frame.empty:
        raise AnalysisIngestionError("No input rows were provided.")
    prepared = frame.copy()
    prepared.columns = [str(column).strip() for column in prepared.columns]
    if prepared.columns.duplicated().any():
        raise AnalysisIngestionError("Duplicate column names are not allowed.")
    kind = _schema(set(prepared.columns))
    if setup.queue_structure == QueueStructure.separate_queues:
        raise AnalysisIngestionError(
            "Separate queues are not yet supported. Upload and analyze each queue separately."
        )
    if kind == "aggregate":
        ok, message, normalized = validate_and_normalize(prepared)
        if not ok:
            raise AnalysisIngestionError(message)
        if setup.queue_structure == QueueStructure.single_server and (normalized["c"] != 1).any():
            raise AnalysisIngestionError("A single-server Analysis requires c = 1 in every segment.")
        if (
            not setup.staffing_varies_by_period
            and setup.fixed_server_count is not None
            and (normalized["c"] != setup.fixed_server_count).any()
        ):
            raise AnalysisIngestionError(
                "Aggregate c values must match the configured fixed server count."
            )
        if setup.capacity_mode == CapacityMode.finite and setup.total_system_capacity is not None:
            if "K" in normalized and normalized["K"].notna().any():
                supplied = normalized["K"].dropna()
                if (supplied != setup.total_system_capacity).any():
                    raise AnalysisIngestionError(
                        "Aggregate K values must match the configured total system capacity."
                    )
            normalized["K"] = setup.total_system_capacity
        if (
            setup.abandonment_mode == AbandonmentMode.modeled
            and setup.patience_rate_per_hour is not None
        ):
            if "theta" in normalized and normalized["theta"].notna().any():
                supplied = normalized["theta"].dropna()
                if (supplied != setup.patience_rate_per_hour).any():
                    raise AnalysisIngestionError(
                        "Aggregate theta values must match the configured patience rate."
                    )
            normalized["theta"] = setup.patience_rate_per_hour
        records = to_segment_records(normalized)
        fields = {column: "user_provided" for column in normalized.columns}
        return records, {
            "schema": kind,
            "field_provenance": fields,
            "assumption_provenance": {"selected_model_assumptions": "model_assumption"},
        }

    if setup.staffing_varies_by_period:
        raise AnalysisIngestionError(
            "Customer-event input requires a fixed server count. For varying staffing, upload aggregate data with c per segment."
        )
    if setup.fixed_server_count is None:
        raise AnalysisIngestionError("Enter the fixed server count before uploading customer-event data.")
    if setup.capacity_mode == CapacityMode.finite and setup.total_system_capacity is None:
        raise AnalysisIngestionError("Enter total system capacity before modeling finite capacity.")
    if setup.abandonment_mode == AbandonmentMode.modeled and setup.patience_rate_per_hour is None:
        raise AnalysisIngestionError("Enter a positive patience rate before modeling abandonment.")

    parsed: dict[str, pd.Series] = {}
    for column in sorted(EVENT_REQUIRED):
        values = pd.to_datetime(prepared[column], errors="coerce", utc=True)
        if values.isna().any():
            row = int(values.isna().to_numpy().nonzero()[0][0]) + 1
            raise AnalysisIngestionError(f"Row {row}: {column} must be a valid timestamp.")
        parsed[column] = values
    invalid_start = parsed["service_start"] < parsed["arrival_time"]
    if invalid_start.any():
        row = int(invalid_start.to_numpy().nonzero()[0][0]) + 1
        raise AnalysisIngestionError(f"Row {row}: service_start cannot be before arrival_time.")
    invalid_end = parsed["service_end"] < parsed["service_start"]
    if invalid_end.any():
        row = int(invalid_end.to_numpy().nonzero()[0][0]) + 1
        raise AnalysisIngestionError(f"Row {row}: service_end cannot be before service_start.")

    waiting_hours = (parsed["service_start"] - parsed["arrival_time"]).dt.total_seconds() / 3600
    service_hours = (parsed["service_end"] - parsed["service_start"]).dt.total_seconds() / 3600
    if (service_hours <= 0).any():
        row = int((service_hours <= 0).to_numpy().nonzero()[0][0]) + 1
        raise AnalysisIngestionError(f"Row {row}: service duration must be greater than zero.")
    working = pd.DataFrame(
        {
            "segment": parsed["arrival_time"].dt.floor("h"),
            "waiting_hours": waiting_hours,
            "service_hours": service_hours,
        }
    )
    event_records: list[dict] = []
    fixed_server_count = setup.fixed_server_count
    total_system_capacity = setup.total_system_capacity
    patience_rate = setup.patience_rate_per_hour
    assert fixed_server_count is not None
    derived_statistics: list[dict] = []
    for segment, group in working.groupby("segment", sort=True):
        mean_service = float(group["service_hours"].mean())
        record: dict = {
            "time": segment.strftime("%Y-%m-%d %H:00 UTC"),
            "lambda": float(len(group)),
            "mu": 1.0 / mean_service,
            "c": int(fixed_server_count),
            "variance": float(group["service_hours"].var(ddof=0)),
        }
        if setup.capacity_mode == CapacityMode.finite:
            assert total_system_capacity is not None
            record["K"] = int(total_system_capacity)
        if setup.abandonment_mode == AbandonmentMode.modeled:
            assert patience_rate is not None
            record["theta"] = float(patience_rate)
        event_records.append(record)
        derived_statistics.append(
            {
                "time": record["time"],
                "mean_waiting_time_hours": float(group["waiting_hours"].mean()),
                "mean_service_time_hours": mean_service,
            }
        )

    fields = {
        "time": "data_derived",
        "lambda": "data_derived",
        "mu": "data_derived",
        "c": "user_provided",
        "variance": "data_derived",
    }
    if setup.capacity_mode == CapacityMode.finite:
        fields["K"] = "user_provided"
    if setup.abandonment_mode == AbandonmentMode.modeled:
        fields["theta"] = "user_provided"
    return event_records, {
        "schema": kind,
        "field_provenance": fields,
        "derived_fields": {
            "waiting_time": "service_start - arrival_time",
            "service_time": "service_end - service_start",
            "aggregation": "clock-hour of arrival_time",
        },
        "derived_statistics": derived_statistics,
        "assumption_provenance": {"selected_model_assumptions": "model_assumption"},
    }
