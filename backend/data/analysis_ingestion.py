"""Analysis upload schema detection, normalization, and provenance."""

from __future__ import annotations

import pandas as pd

from backend.api.analysis_schemas import (
    AbandonmentMode,
    CapacityMode,
    QueueSetup,
    QueueStructure,
)
from backend.data.ingestion import (
    REQUIRED_COLUMNS,
    normalize_header_aliases,
    to_segment_records,
    validate_and_normalize,
)

EVENT_REQUIRED = {"arrival_time", "service_start", "service_end"}
EVENT_COLUMN_MEANINGS = {
    "arrival_time": "the time the customer joined the waiting line",
    "service_start": "the time the cashier actually begins serving the customer",
    "service_end": "the time the customer's service is completed",
}
AGGREGATE_REQUIRED = set(REQUIRED_COLUMNS)
DES_EMPIRICAL_SOURCE = "empirical"
DES_AGGREGATE_GATE = (
    "Parallel M/G/1 DES requires empirical service observations or an explicitly configured supported service distribution."
)


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
        meanings = "; ".join(f"{column} ({EVENT_COLUMN_MEANINGS[column]})" for column in missing)
        raise AnalysisIngestionError(f"Missing customer-event columns: {meanings}.")
    missing = sorted(AGGREGATE_REQUIRED - columns)
    raise AnalysisIngestionError(
        "Schema could not be identified. Missing aggregate columns: " + ", ".join(missing) + "."
    )


def _segment_label(segment, date_label: str) -> str:
    label = segment.id or f"{segment.start_time:%H:%M}-{segment.end_time:%H:%M}"
    return f"{date_label} {label} UTC"


def _minutes_since_midnight(value) -> float:
    return value.hour * 60.0 + value.minute + value.second / 60.0 + value.microsecond / 60000000.0


def _assign_event_segments(arrival_times: pd.Series, setup: QueueSetup) -> pd.DataFrame:
    """Assign events to configured half-open intervals or legacy hourly buckets."""
    if not setup.segments:
        return pd.DataFrame(
            {
                "segment_key": arrival_times.dt.floor("h").astype(str),
                "time_label": arrival_times.dt.strftime("%Y-%m-%d %H:00 UTC"),
                "segment_id": arrival_times.dt.strftime("%Y-%m-%d-%H"),
                "duration_hours": 1.0,
            },
            index=arrival_times.index,
        )

    ordered = sorted(setup.segments, key=lambda segment: segment.start_time)
    assignments: list[dict] = []
    for index, timestamp in arrival_times.items():
        event_time = timestamp.time()
        matching_index = next(
            (
                position
                for position, segment in enumerate(ordered)
                if segment.start_time <= event_time < segment.end_time
            ),
            None,
        )
        if matching_index is None:
            raise AnalysisIngestionError(
                f"Event at {timestamp.isoformat()} falls outside the configured analysis segments."
            )
        matching = ordered[matching_index]
        date_label = timestamp.strftime("%Y-%m-%d")
        duration_minutes = _minutes_since_midnight(matching.end_time) - _minutes_since_midnight(
            matching.start_time
        )
        assignments.append(
            {
                "index": index,
                "segment_key": f"{date_label}:{matching_index}",
                "time_label": _segment_label(matching, date_label),
                "segment_id": matching.id or f"{matching.start_time:%H:%M}-{matching.end_time:%H:%M}",
                "duration_hours": duration_minutes / 60.0,
            }
        )
    return pd.DataFrame(assignments).set_index("index").reindex(arrival_times.index)


def normalize_analysis_input(
    frame: pd.DataFrame, setup: QueueSetup
) -> tuple[list[dict], dict]:
    """Return existing segment records plus transparent field provenance."""
    if frame is None or frame.empty:
        raise AnalysisIngestionError("No input rows were provided.")
    prepared = frame.copy()
    prepared.columns = [str(column).strip() for column in prepared.columns]
    aliased, column_mapping = normalize_header_aliases(list(prepared.columns))
    prepared.columns = aliased
    if prepared.columns.duplicated().any():
        raise AnalysisIngestionError("Duplicate column names are not allowed.")
    kind = _schema(set(prepared.columns))
    if kind == "aggregate":
        ok, message, normalized = validate_and_normalize(prepared)
        if not ok:
            raise AnalysisIngestionError(message)
        if setup.queue_structure == QueueStructure.separate_queues:
            if "queue_id" not in normalized.columns:
                raise AnalysisIngestionError(
                    "Separate-queue analysis requires a queue_id column with one queue label per row."
                )
            if "variance" not in normalized.columns or normalized["variance"].isna().any():
                raise AnalysisIngestionError(
                    "Separate-queue analysis requires service-time variance for every queue segment."
                )
            if normalized["c"].fillna(1).ne(1).any():
                raise AnalysisIngestionError(
                    "Separate-queue analysis requires one dedicated server per queue, so c must be 1 in every segment."
                )
            if normalized["K"].notna().any() if "K" in normalized.columns else False:
                raise AnalysisIngestionError(
                    "Separate-queue analysis currently requires unlimited capacity."
                )
            if normalized["theta"].notna().any() if "theta" in normalized.columns else False:
                raise AnalysisIngestionError(
                    "Separate-queue analysis currently does not support abandonment modeling."
                )
            normalized["c"] = 1
            normalized["queue_structure"] = QueueStructure.separate_queues.value
            normalized["model_id"] = "parallel_mg1"
            normalized["server_id"] = normalized["queue_id"].map(lambda value: f"server:{str(value).strip()}")
            normalized["service_time_source"] = "aggregate_statistics"
            normalized["des_capability"] = DES_AGGREGATE_GATE
            if normalized["queue_id"].map(lambda value: value is None or str(value).strip() == "").any():
                raise AnalysisIngestionError("queue_id values must be non-empty for separate-queue analysis.")
            unknown_queue_ids = sorted(
                set(normalized["queue_id"].map(lambda value: str(value).strip())) - set(setup.queue_ids)
            )
            if unknown_queue_ids:
                raise AnalysisIngestionError(
                    "Uploaded queue IDs are not configured for this Analysis: "
                    + ", ".join(unknown_queue_ids)
                    + "."
                )
            records = to_segment_records(normalized)
            fields = {column: "user_provided" for column in normalized.columns}
            return records, {
                "schema": kind,
                "field_provenance": fields,
                "column_mapping": column_mapping,
                "assumption_provenance": {"selected_model_assumptions": "model_assumption"},
            }
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
            "column_mapping": column_mapping,
                "assumption_provenance": {"selected_model_assumptions": "model_assumption"},
        }

    if setup.staffing_varies_by_period:
        raise AnalysisIngestionError(
            "Customer-event input requires a fixed server count. For varying staffing, upload aggregate data with c per segment."
        )
    if setup.fixed_server_count is None:
        raise AnalysisIngestionError("Enter the fixed server count before uploading customer-event data.")
    if setup.queue_structure == QueueStructure.separate_queues:
        if "queue_id" not in prepared.columns:
            raise AnalysisIngestionError(
                "Separate-queue customer-event analysis requires a queue_id column for every event."
            )
        if setup.capacity_mode == CapacityMode.finite:
            raise AnalysisIngestionError("Separate-queue analysis currently requires unlimited capacity.")
        if setup.abandonment_mode == AbandonmentMode.modeled:
            raise AnalysisIngestionError("Separate-queue analysis currently does not support abandonment modeling.")
        if prepared["queue_id"].map(lambda value: value is None or str(value).strip() == "").any():
            raise AnalysisIngestionError("queue_id values must be non-empty for separate-queue analysis.")
        unknown_queue_ids = sorted(
            set(prepared["queue_id"].map(lambda value: str(value).strip())) - set(setup.queue_ids)
        )
        if unknown_queue_ids:
            raise AnalysisIngestionError(
                "Uploaded queue IDs are not configured for this Analysis: "
                + ", ".join(unknown_queue_ids)
                + "."
            )
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
    working = _assign_event_segments(parsed["arrival_time"], setup)
    working["waiting_hours"] = waiting_hours
    working["service_hours"] = service_hours
    if setup.queue_structure == QueueStructure.separate_queues:
        working["queue_id"] = prepared["queue_id"].map(lambda value: str(value).strip())
    event_records: list[dict] = []
    fixed_server_count = setup.fixed_server_count
    total_system_capacity = setup.total_system_capacity
    patience_rate = setup.patience_rate_per_hour
    assert fixed_server_count is not None
    derived_statistics: list[dict] = []
    group_columns = ["segment_key"]
    if setup.queue_structure == QueueStructure.separate_queues:
        group_columns.append("queue_id")
    for group_key, group in working.groupby(group_columns, sort=True):
        segment = group["time_label"].iloc[0]
        duration_hours = float(group["duration_hours"].iloc[0])
        mean_service = float(group["service_hours"].mean())
        record: dict = {
            "time": str(segment),
            "segment_id": str(group["segment_id"].iloc[0]),
            "lambda": float(len(group)) / duration_hours,
            "mu": 1.0 / mean_service,
            "c": 1 if setup.queue_structure == QueueStructure.separate_queues else int(fixed_server_count),
            "variance": float(group["service_hours"].var(ddof=0)),
        }
        if setup.queue_structure == QueueStructure.separate_queues:
            record["queue_id"] = str(group["queue_id"].iloc[0])
            record["queue_structure"] = QueueStructure.separate_queues.value
            record["model_id"] = "parallel_mg1"
            record["server_id"] = f"server:{record['queue_id']}"
        record["service_time_source"] = DES_EMPIRICAL_SOURCE
        record["service_samples_hours"] = [float(value) for value in group["service_hours"].tolist()]
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
                "duration_minutes": duration_hours * 60.0,
                **({"queue_id": record["queue_id"]} if "queue_id" in record else {}),
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
    if setup.queue_structure == QueueStructure.separate_queues:
        fields["queue_id"] = "user_provided"
        fields["queue_structure"] = "user_provided"
        fields["model_id"] = "model_assumption"
    return event_records, {
        "schema": kind,
        "field_provenance": fields,
        "derived_fields": {
            "waiting_time": "service_start - arrival_time",
            "service_time": "service_end - service_start",
            "aggregation": "configured half-open intervals; default clock-hour buckets",
            "arrival_rate": "arrival_count / segment_duration_hours",
        },
        "derived_statistics": derived_statistics,
        "column_mapping": column_mapping,
                "assumption_provenance": {"selected_model_assumptions": "model_assumption"},
    }
