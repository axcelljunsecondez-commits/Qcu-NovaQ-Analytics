"""Staffing optimization page."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app_page_utils import (
    dataframe_download,
    init_session_state,
    pretty_metric,
    to_segment_records,
)
from backend.queueing_engine.config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_ABANDONMENT_RATE,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
)
from backend.queueing_engine.log import get_logger
from backend.queueing_engine.services.optimization import (
    DEFAULT_MAX_SERVERS,
    DEFAULT_TARGET_UTILIZATION,
    build_recommendations,
    optimize_segments,
    summarize_optimization,
)
from data_processing import (
    validate_with_simulation,
)
from i18n import t
from theme import (
    apply_dark_overrides,
    apply_theme,
    breadcrumb,
    skeleton_metric,
    toast,
)

logger = get_logger(__name__)

st.set_page_config(page_title="Optimization", layout="wide")
init_session_state()
apply_theme()
apply_dark_overrides()
breadcrumb(current_page=2)

st.title(t("page2.title"))
st.caption(t("page2.caption"))

source_df = st.session_state.get("df")
if source_df is None or source_df.empty:
    st.error("Current input data was not found. Complete Page 1 first.")
    st.stop()

settings = st.columns(2)
target_utilization = settings[0].slider(
    "Target utilization",
    min_value=0.10,
    max_value=0.95,
    value=float(DEFAULT_TARGET_UTILIZATION),
    step=0.05,
)
max_servers = settings[1].number_input(
    "Maximum servers",
    min_value=1,
    value=int(DEFAULT_MAX_SERVERS),
    step=1,
)

default_server_cost = st.session_state.get("sb_server_cost", DEFAULT_SERVER_COST_HR)
customer_waiting_cost = st.session_state.get("sb_wait_cost", DEFAULT_WAIT_COST_HR)
cost_per_abandonment = st.session_state.get("sb_abandon_cost", DEFAULT_ABANDONMENT_COST)
abandonment_rate = st.session_state.get("sb_abandon_rate", DEFAULT_ABANDONMENT_RATE)

@st.cache_data
def _cached_optimize_segments(segments_json, target_util, max_servers,
                               server_cost, wait_cost, abandon_cost, abandon_rate):
    return optimize_segments(
        json.loads(segments_json),
        target_utilization=target_util,
        max_servers=max_servers,
        default_server_cost=server_cost,
        customer_waiting_cost=wait_cost,
        cost_per_abandonment=abandon_cost,
        abandonment_rate=abandon_rate,
    )

segments = to_segment_records(source_df)
comparison_rows = _cached_optimize_segments(
    json.dumps(segments, default=str),
    target_utilization,
    int(max_servers),
    default_server_cost,
    customer_waiting_cost,
    cost_per_abandonment,
    abandonment_rate,
)
comparison_df = pd.DataFrame(comparison_rows)
kpis = summarize_optimization(to_segment_records(comparison_df))

validation_signature = json.dumps(
    {
        "segments": segments,
        "target_utilization": target_utilization,
        "max_servers": int(max_servers),
        "server_cost": default_server_cost,
        "wait_cost": customer_waiting_cost,
        "abandon_cost": cost_per_abandonment,
        "abandon_rate": abandonment_rate,
    },
    default=str,
)
if st.session_state.get("validation_signature") != validation_signature:
    st.session_state.pop("validated_comparison", None)
    st.session_state["validation_signature"] = validation_signature

run_validation = st.button(
    "▶ Run DES + MC Validation (10K trials)",
    type="secondary",
    use_container_width=True,
    help="Runs discrete-event simulation and 10 000-trial Monte Carlo on the optimized plan.",
)

if run_validation:
    with st.spinner("Running DES + Monte Carlo (10K trials)..."):
        validated_df = validate_with_simulation(comparison_df)
    st.session_state["validated_comparison"] = validated_df
    st.session_state["validation_signature"] = validation_signature

validated_df = st.session_state.get("validated_comparison")

if validated_df is None:
    st.info("Click **▶ Run DES + MC Validation** to validate the optimized staffing plan.")
    des_failures = 0
    mc_flags = 0
else:
    des_failures = validated_df["sim_status"].isin(["Critical", "Unstable"]).sum()
    mc_flags = validated_df["mc_failure_rate"].fillna(0).gt(0.05).sum()

metric_cols = st.columns(4)
metric_cols[0].metric("Current Cost", pretty_metric(kpis["total_current_cost"], money=True), help="Total cost at current server count")
metric_cols[1].metric("Optimized Cost", pretty_metric(kpis["total_optimized_cost"], money=True), help="Total cost at recommended server count")
metric_cols[2].metric("Savings", pretty_metric(kpis["total_savings"], money=True), help="Cost reduction from current to optimized plan")
metric_cols[3].metric("Server Change", str(kpis["total_server_change"]), help="Net change in total servers across all segments")

# ── Simulation-validation summary ────────────────────────────────────
if validated_df is None:
    st.info("Click **▶ Run DES + MC Validation** to validate the optimized staffing plan.")
elif des_failures > 0 or mc_flags > 0:
    st.warning(f"⚠️ DES flagged {des_failures} segment(s) Critical · MC flagged {mc_flags} segment(s) >5% failure rate")
else:
    toast("✅ Plan passed DES + MC validation (all segments stable)", "success")

st.subheader("Recommended Staffing")
_display = comparison_df.copy()
for _col in ("rho_current", "rho_optimal"):
    if _col in _display.columns:
        _display[_col] = _display[_col] * 100
st.dataframe(_display, column_config={
    "rho_current": st.column_config.ProgressColumn("ρ Current (%)", format="%.1f%%", min_value=0, max_value=100),
    "rho_optimal": st.column_config.ProgressColumn("ρ Optimal (%)", format="%.1f%%", min_value=0, max_value=100),
}, use_container_width=True)

for message in build_recommendations(to_segment_records(comparison_df)):
    st.info(message)

if st.button("Save Recommended Data", type="primary", use_container_width=True):
    st.session_state["recommended_data"] = comparison_df.copy()
    toast("Recommended staffing saved! Proceed to Simulation.", "success")

dataframe_download(comparison_df, "novamart_optimization.csv", "Download Optimization CSV")

# ── Save scenario ────────────────────────────────────────────────────────
st.subheader("Save this optimization as a scenario")
scenario_cols = st.columns([3, 1])
scenario_name = scenario_cols[0].text_input(
    "Scenario name",
    placeholder="e.g. Lean Weekend Plan",
    label_visibility="collapsed",
)
if scenario_cols[1].button("💾 Save Scenario", use_container_width=True):
    name = scenario_name.strip()
    if not name:
        st.warning("Please enter a scenario name.")
    else:
        if "saved_scenarios" not in st.session_state:
            st.session_state["saved_scenarios"] = []
        st.session_state["saved_scenarios"].append(
            {
                "name": name,
                "data": comparison_df.copy(),
                "kpis": kpis,
            }
        )
        st.success(f"Scenario '{name}' saved.")

# ═══════════════════════════════════════════════════════════════════════════
# WHAT-IF PANEL
# ═══════════════════════════════════════════════════════════════════════════
with st.expander("🔮 What-If Analysis", expanded=False):
    st.markdown("Adjust parameters below to see how changes affect the optimized plan.")

    wi_cols = st.columns(3)
    wi_arrival_mult = wi_cols[0].slider("Arrival λ multiplier", 0.5, 2.0, 1.0, 0.1, key="wi_arrival")
    wi_server_cost = wi_cols[1].slider("Server cost multiplier", 0.5, 2.0, 1.0, 0.1, key="wi_server")
    wi_wait_cost = wi_cols[2].slider("Wait cost multiplier", 0.5, 2.0, 1.0, 0.1, key="wi_wait")

    wi_source = source_df.copy()
    if "lambda" in wi_source.columns:
        wi_source["lambda"] = wi_source["lambda"] * wi_arrival_mult

    wi_segments = to_segment_records(wi_source)
    wi_rows = optimize_segments(
        wi_segments,
        target_utilization=target_utilization,
        default_server_cost=default_server_cost * wi_server_cost,
        max_servers=int(max_servers),
        customer_waiting_cost=customer_waiting_cost * wi_wait_cost,
        cost_per_abandonment=cost_per_abandonment,
        abandonment_rate=abandonment_rate,
    )
    wi_df = pd.DataFrame(wi_rows)
    if not wi_df.empty:
        wi_kpis = summarize_optimization(to_segment_records(wi_df))
        wi_cols2 = st.columns(4)
        wi_cols2[0].metric("What-If Cost", pretty_metric(wi_kpis["total_optimized_cost"], money=True),
                           delta=pretty_metric(wi_kpis["total_optimized_cost"] - kpis["total_optimized_cost"], money=True))
        wi_cols2[1].metric("What-If Savings", pretty_metric(wi_kpis["total_savings"], money=True),
                           delta=pretty_metric(wi_kpis["total_savings"] - kpis["total_savings"], money=True))
        wi_cols2[2].metric("What-If Servers", str(wi_kpis["total_server_change"]))
        wi_cols2[3].metric("What-If Utilization", pretty_metric(wi_kpis["avg_utilization_optimized"], percent=True), help="Fraction of time servers are busy. Above 85% → queues grow fast.")
    else:
        st.info("Adjust parameters to see what-if results.")
