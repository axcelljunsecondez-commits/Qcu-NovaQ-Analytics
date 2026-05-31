"""Current vs optimized comparison page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_page_utils import dataframe_download, init_session_state, inject_or_css, pretty_metric, to_segment_records
from costing import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    compute_all_costs,
    compute_cost_summary,
)
from log import get_logger
from optimization import build_recommendations, summarize_optimization
from report_export import generate_excel_report, generate_pdf_report

logger = get_logger(__name__)

st.set_page_config(page_title="Comparison", layout="wide")
init_session_state()
inject_or_css()

# Initialise saved-scenarios list if missing
if "saved_scenarios" not in st.session_state:
    st.session_state["saved_scenarios"] = []

st.title("Comparison")
st.caption("Review the current and optimized staffing scenario side by side.")

comparison_df = st.session_state.get("validated_comparison")
if comparison_df is None:
    comparison_df = st.session_state.get("recommended_data")
if comparison_df is None or comparison_df.empty:
    st.error("Recommended data was not found. Complete Page 2 first.")
    st.stop()

st.session_state["comparison_data"] = comparison_df.copy()
kpis = summarize_optimization(to_segment_records(comparison_df))

# ── Prepare PDF / Excel export bytes (built once, behind the scenes) ─────
current_data = st.session_state.get("current_data")
segment_df_for_export = current_data if current_data is not None and not current_data.empty else comparison_df

recs = build_recommendations(comparison_df.to_dict("records"))
pdf_bytes = generate_pdf_report(
    current_kpis=kpis if current_data is not None else {},
    recommended_kpis=kpis,
    comparison_df=comparison_df,
    segment_df=segment_df_for_export,
    recommendations=recs,
)
xl_bytes = generate_excel_report(
    comparison_df=comparison_df,
    segment_df=segment_df_for_export,
    recommended_kpis=kpis,
)

# ═══════════════════════════════════════════════════════════════════════════
# COMPARISON VIEW
# ═══════════════════════════════════════════════════════════════════════════
metric_cols = st.columns(4)
metric_cols[0].metric("Current Cost", pretty_metric(kpis["total_current_cost"], money=True), help="Total cost under current staffing plan")
metric_cols[1].metric("Optimized Cost", pretty_metric(kpis["total_optimized_cost"], money=True), help="Total cost under optimized staffing plan")
metric_cols[2].metric("Savings", pretty_metric(kpis["total_savings"], money=True), help="Cost difference between current and optimized plan")
metric_cols[3].metric("Avg Utilization Change", pretty_metric(kpis["avg_utilization_improvement"], percent=True), help="Change in average utilization after optimization")

st.subheader("Scenario Comparison")
_comp_display = comparison_df.copy()
for _col in ("rho_current", "rho_optimal", "sim_rho", "mc_rho_mean"):
    if _col in _comp_display.columns:
        _comp_display[_col] = _comp_display[_col] * 100
_cc = {
    "rho_current": st.column_config.ProgressColumn("ρ Current (%)", format="%.1f%%", min_value=0, max_value=100),
    "rho_optimal": st.column_config.ProgressColumn("ρ Optimal (%)", format="%.1f%%", min_value=0, max_value=100),
}
if "sim_rho" in _comp_display.columns:
    _cc["sim_rho"] = st.column_config.ProgressColumn("ρ DES (%)", format="%.1f%%", min_value=0, max_value=100)
if "sim_status" in _comp_display.columns:
    _cc["sim_status"] = st.column_config.Column("DES Status")
if "sim_max_queue" in _comp_display.columns:
    _cc["sim_max_queue"] = st.column_config.NumberColumn("Max Queue")
if "mc_failure_rate" in _comp_display.columns:
    _comp_display["mc_failure_rate"] = _comp_display["mc_failure_rate"] * 100
    _cc["mc_failure_rate"] = st.column_config.ProgressColumn("MC Fail %", format="%.1f%%", min_value=0, max_value=100)
if "mc_Wq_ci" in _comp_display.columns:
    _cc["mc_Wq_ci"] = st.column_config.Column("Wq (95% CI)")
st.dataframe(_comp_display, column_config=_cc, use_container_width=True)

chart_cols = st.columns(2)
with chart_cols[0]:
    utilization_df = comparison_df.set_index("time")[["rho_current", "rho_optimal"]]
    st.bar_chart(utilization_df)
with chart_cols[1]:
    server_df = comparison_df.set_index("time")[["c_current", "c_optimal"]]
    st.bar_chart(server_df)

st.subheader("Waiting-Time Comparison")
st.line_chart(comparison_df.set_index("time")[["Wq_current", "Wq_optimal"]])

st.subheader("Cost Breakdown")
cost_per_server_hr = st.session_state.get("sb_server_cost", DEFAULT_SERVER_COST_HR)
cost_per_wait_hr = st.session_state.get("sb_wait_cost", DEFAULT_WAIT_COST_HR)
cost_per_abandonment = st.session_state.get("sb_abandon_cost", DEFAULT_ABANDONMENT_COST)
abandonment_rate = st.session_state.get("sb_abandon_rate", 0.10)

df_current = comparison_df.rename(columns={"c_current": "c", "rho_current": "rho", "Wq_current": "Wq", "Lq_current": "Lq"})
df_optimal = comparison_df.rename(columns={"c_optimal": "c", "rho_optimal": "rho", "Wq_optimal": "Wq", "Lq_optimal": "Lq"})

current_cost_summary = compute_cost_summary(
    df_current,
    cost_per_server_hr=cost_per_server_hr,
    cost_per_wait_hr=cost_per_wait_hr,
    cost_per_abandonment=cost_per_abandonment,
    abandonment_rate=abandonment_rate,
)
optimal_cost_summary = compute_cost_summary(
    df_optimal,
    cost_per_server_hr=cost_per_server_hr,
    cost_per_wait_hr=cost_per_wait_hr,
    cost_per_abandonment=cost_per_abandonment,
    abandonment_rate=abandonment_rate,
)

cost_metrics = st.columns(4)
cost_metrics[0].metric("Current Total", pretty_metric(current_cost_summary["total_cost"], money=True), help="Total cost under current staffing")
cost_metrics[1].metric("Optimized Total", pretty_metric(optimal_cost_summary["total_cost"], money=True), help="Total cost under optimized staffing")
savings = (current_cost_summary["total_cost"] or 0) - (optimal_cost_summary["total_cost"] or 0)
cost_metrics[2].metric("Savings", pretty_metric(savings, money=True), help="Cost reduction from optimization")
cost_metrics[3].metric("Avg Cost/Segment (Opt)", pretty_metric(optimal_cost_summary["avg_cost_per_segment"], money=True), help="Average optimized cost per time segment")

cost_current_df = compute_all_costs(df_current, cost_per_server_hr, cost_per_wait_hr, cost_per_abandonment, abandonment_rate)
cost_optimal_df = compute_all_costs(df_optimal, cost_per_server_hr, cost_per_wait_hr, cost_per_abandonment, abandonment_rate)
cost_compare = pd.DataFrame({
    "time": comparison_df["time"],
    "Current Server": cost_current_df["server_cost"],
    "Optimal Server": cost_optimal_df["server_cost"],
    "Current Wait": cost_current_df["wait_cost"],
    "Optimal Wait": cost_optimal_df["wait_cost"],
    "Current Total": cost_current_df["total_cost"],
    "Optimal Total": cost_optimal_df["total_cost"],
})
st.dataframe(cost_compare, use_container_width=True)

# ── Simulation-validation overview ────────────────────────────────────
if "sim_status" in comparison_df.columns:
    st.subheader("Simulation Validation (DES + MC 10K)")
    sim_cols = st.columns(4)

    des_fail = int(comparison_df["sim_status"].isin(["Critical", "Unstable"]).sum())
    mc_fail = int(comparison_df["mc_failure_rate"].fillna(0).gt(0.05).sum())
    max_queue = int(comparison_df["sim_max_queue"].fillna(0).max())
    avg_mc_fail = float(comparison_df["mc_failure_rate"].fillna(0).mean())

    sim_cols[0].metric("DES Critical", str(des_fail), help="Segments where DES status was Critical or Unstable")
    sim_cols[1].metric("MC Flags (>5%)", str(mc_fail), help="Segments where >5% of MC trials exceeded ρ threshold")
    sim_cols[2].metric("Max Queue (DES)", str(max_queue), help="Highest queue depth observed in DES simulation")
    sim_cols[3].metric("Avg MC Failure Rate", pretty_metric(avg_mc_fail, percent=True), help="Mean failure rate across all segments")

# ── ROI Projection ────────────────────────────────────────────────────
st.subheader("📈 ROI Projection")
roi_cols = st.columns(4)
legal_holidays = roi_cols[0].number_input("Legal holidays per year", min_value=0, max_value=30, value=12, key="roi_holidays")

daily_savings = savings or 0
thirty_day = daily_savings * 30
operating_days = 365 - legal_holidays
annual_savings = daily_savings * operating_days

roi_cols[1].metric("Daily Savings", pretty_metric(daily_savings, money=True), help="Daily cost savings from optimized plan")
roi_cols[2].metric("30-Day Savings", pretty_metric(thirty_day, money=True), help="Projected savings over 30 days")
roi_cols[3].metric("Annual Savings", pretty_metric(annual_savings, money=True), help=f"Projected savings over {operating_days} operating days (365 − {legal_holidays} holidays)")

dataframe_download(comparison_df, "novamart_comparison.csv", "Download Comparison CSV")

# ── Report export buttons ────────────────────────────────────────────
export_col1, export_col2 = st.columns(2)
export_col1.download_button(
    "📥 Download PDF",
    pdf_bytes,
    "novamart_report.pdf",
    "application/pdf",
    use_container_width=True,
)
export_col2.download_button(
    "📊 Download Excel",
    xl_bytes,
    "novamart_report.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO COMPARISON — Conditional expander
# ═══════════════════════════════════════════════════════════════════════════

scenarios = st.session_state.get("saved_scenarios", [])
if scenarios:
    with st.expander("📁 Compare Saved Scenarios", expanded=False):
        names = [s["name"] for s in scenarios]
        selected = st.multiselect(
            "Select scenarios to compare (minimum 2)",
            options=names,
            default=names[: min(2, len(names))],
        )

        if len(selected) < 2:
            st.info("Select at least two scenarios to display the comparison.")
        else:
            chosen = [s for s in scenarios if s["name"] in selected]

            fig = go.Figure()
            colors_seq = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B"]

            for idx, sc in enumerate(chosen):
                sc_df = sc["data"]
                if "time" in sc_df.columns and "Wq_optimal" in sc_df.columns:
                    wq_min = sc_df["Wq_optimal"] * 60
                    fig.add_trace(
                        go.Bar(
                            name=sc["name"],
                            x=sc_df["time"],
                            y=wq_min,
                            marker_color=colors_seq[idx % len(colors_seq)],
                        )
                    )

            fig.update_layout(
                barmode="group",
                xaxis_title="Time Segment",
                yaxis_title="Avg Wait (min)",
                height=400,
                legend_title="Scenario",
            )
            st.plotly_chart(fig, use_container_width=True)

            summary_rows = []
            for sc in chosen:
                sk = sc.get("kpis", {})
                summary_rows.append(
                    {
                        "Scenario": sc["name"],
                        "Avg Wq (min)": (
                            f"{sk.get('avg_waiting_optimized', 0) * 60:.2f}"
                            if sk.get("avg_waiting_optimized") is not None
                            else "N/A"
                        ),
                        "Avg ρ": (
                            f"{sk.get('avg_utilization_optimized', 0):.1%}"
                            if sk.get("avg_utilization_optimized") is not None
                            else "N/A"
                        ),
                        "Total Cost": (
                            f"₱{sk.get('total_optimized_cost', 0):,.0f}"
                            if sk.get("total_optimized_cost") is not None
                            else "N/A"
                        ),
                        "Savings": (
                            f"₱{sk.get('total_savings', 0):,.0f}"
                            if sk.get("total_savings") is not None
                            else "N/A"
                        ),
                    }
                )
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)
