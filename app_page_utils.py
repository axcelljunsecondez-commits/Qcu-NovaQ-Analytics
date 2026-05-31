"""Shared Streamlit page helpers for the NovaMart dashboard."""

from __future__ import annotations

from io import StringIO

import pandas as pd

from config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
)

REQUIRED_COLUMNS = ["time", "lambda", "mu", "c"]
OPTIONAL_COLUMNS = ["variance", "K", "theta", "server_cost", "regular_hours", "ot_hours", "total_hours"]


def init_session_state() -> None:
    """Initialize workflow session keys used across pages."""
    import streamlit as st

    defaults = {
        "df": None,
        "current_data": None,
        "recommended_data": None,
        "comparison_data": None,
        "simulation_results": None,
        "waste_reduction_data": None,
        "cost_per_server_hr": DEFAULT_SERVER_COST_HR,
        "cost_per_wait_hr": DEFAULT_WAIT_COST_HR,
        "cost_per_abandonment": DEFAULT_ABANDONMENT_COST,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Upload must be a CSV or Excel file.")


def validate_and_normalize(df: pd.DataFrame) -> tuple[bool, str, pd.DataFrame]:
    """Validate the dashboard input schema and coerce numeric columns."""
    if df is None or df.empty:
        return False, "No input rows were provided.", pd.DataFrame()

    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}.", normalized

    numeric_columns = [column for column in REQUIRED_COLUMNS[1:] + OPTIONAL_COLUMNS if column in normalized.columns]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    required_numeric = ["lambda", "mu", "c"]
    invalid_required = [
        column
        for column in required_numeric
        if normalized[column].isna().any()
    ]
    if invalid_required:
        return False, f"Invalid numeric values in: {', '.join(invalid_required)}.", normalized

    if (normalized["lambda"] < 0).any():
        return False, "lambda must be greater than or equal to 0.", normalized
    if (normalized["mu"] <= 0).any():
        return False, "mu must be greater than 0.", normalized
    if (normalized["c"] <= 0).any():
        return False, "c must be greater than 0.", normalized

    normalized["time"] = normalized["time"].astype(str)
    normalized["c"] = normalized["c"].astype(int)
    if "K" in normalized.columns:
        capacity = normalized["K"].dropna()
        if not capacity.empty and (capacity < normalized.loc[capacity.index, "c"]).any():
            return False, "K must be greater than or equal to c.", normalized
        normalized["K"] = normalized["K"].astype("Int64")

    if "theta" in normalized.columns:
        theta_vals = normalized["theta"].dropna()
        if not theta_vals.empty and (theta_vals < 0).any():
            return False, "theta must be greater than or equal to 0.", normalized

    return True, "Input data is valid.", normalized


def to_segment_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to records with None in place of pandas NA values."""
    if df is None or df.empty:
        return []
    return df.astype(object).where(pd.notna(df), None).to_dict("records")


def dataframe_download(df: pd.DataFrame, filename: str, label: str) -> None:
    """Render a CSV download button for a DataFrame."""
    import streamlit as st

    if df is None or df.empty:
        return
    csv = df.to_csv(index=False)
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def inject_or_css():
    import streamlit as st
    st.markdown("""
    <style>
    .badge-mm1 { display: inline-block; background: #1B2A4A; color: #E8A838; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #E8A838; }
    .badge-mmc { display: inline-block; background: #1B2A4A; color: #5DADE2; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #5DADE2; }
    .badge-mgc { display: inline-block; background: #1B2A4A; color: #A569BD; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #A569BD; }
    .badge-mmc-k { display: inline-block; background: #1B2A4A; color: #58D68D; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #58D68D; }
    .badge-mgc-k { display: inline-block; background: #1B2A4A; color: #EC7063; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #EC7063; }
    .badge-erlang-a { display: inline-block; background: #1B2A4A; color: #F39C12; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 700; font-family: 'Inter', sans-serif; border: 1px solid #F39C12; }
    .model-legend { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
    [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06); padding: 1.75rem; }
    [data-testid="stMetric"]:hover { border-color: #E8A838; box-shadow: 0 12px 32px rgba(232, 168, 56, 0.12); }
    </style>
    """, unsafe_allow_html=True)

def pretty_metric(value, percent: bool = False, money: bool = False) -> str:
    """Format optional numeric values for Streamlit metric cards."""
    if value is None or pd.isna(value):
        return "N/A"
    if percent:
        return f"{float(value) * 100:.1f}%"
    if money:
        return f"₱{float(value):,.2f}"
    return f"{float(value):.2f}"
