"""Cached bridge for the legacy Streamlit app (temporary at root until Phase 2 Unit G).

Re-applies Streamlit's ``st.cache_data`` to the extracted, uncached domain
functions so the legacy app keeps its original caching behavior.
"""

from __future__ import annotations

import streamlit as st

from backend.queueing_engine.services.data_processing import (
    compute_kpis as _compute_kpis,
)
from backend.queueing_engine.services.data_processing import (
    get_unstable_messages as _get_unstable_messages,
)
from backend.queueing_engine.services.data_processing import (
    process_segments as _process_segments,
)
from backend.queueing_engine.simulation.simulation import (
    validate_with_simulation as _validate_with_simulation,
)

process_segments = st.cache_data(_process_segments)
validate_with_simulation = st.cache_data(_validate_with_simulation)
compute_kpis = st.cache_data(_compute_kpis)
get_unstable_messages = _get_unstable_messages
