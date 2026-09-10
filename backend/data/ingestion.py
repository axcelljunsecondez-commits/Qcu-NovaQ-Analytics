"""Data ingestion: pure input parsing, validation, and normalization."""

from __future__ import annotations

import math

import pandas as pd

from backend.queueing_engine.config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
)

REQUIRED_COLUMNS = ["time", "lambda", "mu", "c"]
OPTIONAL_COLUMNS = ["variance", "K", "theta", "server_cost", "regular_hours", "ot_hours", "total_hours"]


def sample_segments() -> pd.DataFrame:
    """Return sample data matching the current four-column input contract."""
    return pd.DataFrame(
        {
            "time": ["08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00"],
            "lambda": [30.0, 45.0, 50.0, 18.0],
            "mu": [12.0, 12.0, 12.0, 20.0],
            "c": [3, 4, 4, 1],
            "variance": [pd.NA, pd.NA, 0.006, pd.NA],
            "K": [12, 15, 15, pd.NA],
        }
    )


def read_uploaded_table(uploaded_file) -> pd.DataFrame:
    """Read a CSV or Excel upload into a DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Upload must be a CSV or XLSX file.")


def validate_and_normalize(df: pd.DataFrame) -> tuple[bool, str, pd.DataFrame]:
    """Validate the dashboard input schema and coerce numeric columns."""
    if df is None or df.empty:
        return False, "No input rows were provided.", pd.DataFrame()

    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}.", normalized

    if normalized.columns.duplicated().any():
        return False, "Duplicate column names are not allowed.", normalized
    numeric_columns = [column for column in REQUIRED_COLUMNS[1:] + OPTIONAL_COLUMNS if column in normalized.columns]
    for column in numeric_columns:
        converted: list[float | None] = []
        for position, value in enumerate(normalized[column], start=1):
            absent = value is None or value is pd.NA or (not isinstance(value, str) and pd.isna(value)) or (isinstance(value, str) and not value.strip())
            if absent and column in OPTIONAL_COLUMNS:
                converted.append(None)
                continue
            error = None
            try:
                number = float(value)
                if absent or isinstance(value, bool) or type(value).__name__ == "bool_" or not math.isfinite(number):
                    error = "must be a finite number"
                elif column in ("c", "K") and (not number.is_integer() or not 1 <= number <= 100000):
                    error = "must be an integer between 1 and 100000"
                elif column in ("mu", "total_hours") and number <= 0:
                    error = "must be greater than 0"
                elif number < 0:
                    error = "must be greater than or equal to 0"
            except (TypeError, ValueError, OverflowError):
                number = 0.0
                error = "must be a finite number"
            if error:
                return False, f"Row {position}: {column} {error}.", normalized
            converted.append(number)
        normalized[column] = converted
    for position, value in enumerate(normalized["time"], start=1):
        if value is None or pd.isna(value) or not str(value).strip():
            return False, f"Row {position}: time must be a nonempty label.", normalized
    normalized["time"] = normalized["time"].astype(str)
    normalized["c"] = normalized["c"].astype(int)
    if "K" in normalized.columns:
        for position, (capacity, servers) in enumerate(zip(normalized["K"], normalized["c"]), start=1):
            if pd.notna(capacity) and capacity < servers:
                return False, f"Row {position}: K must be greater than or equal to c.", normalized
        normalized["K"] = normalized["K"].astype("Int64")

    return True, "Input data is valid.", normalized


def to_segment_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to records with None in place of pandas NA values."""
    if df is None or df.empty:
        return []
    return df.astype(object).where(pd.notna(df), None).to_dict("records")


__all__ = [
    "DEFAULT_ABANDONMENT_COST",
    "DEFAULT_SERVER_COST_HR",
    "DEFAULT_WAIT_COST_HR",
    "OPTIONAL_COLUMNS",
    "REQUIRED_COLUMNS",
    "read_uploaded_table",
    "sample_segments",
    "to_segment_records",
    "validate_and_normalize",
]
