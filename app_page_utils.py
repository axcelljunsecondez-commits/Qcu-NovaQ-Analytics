"""
app_page_utils.py — Shared page helpers for the Queueing Theory Dashboard.

St-coupled helpers live here; pure data-pipeline helpers are re-exported from
the framework-free data layer (backend.data.ingestion).
"""

from __future__ import annotations

import pandas as pd

from backend.data.ingestion import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    pretty_metric,
    read_uploaded_table,
    sample_segments,
    to_segment_records,
    validate_and_normalize,
)
from backend.queueing_engine.config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
)


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
