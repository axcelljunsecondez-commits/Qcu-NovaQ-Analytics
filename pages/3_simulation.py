"""Simulation page with DES (SimPy) and Monte Carlo tabs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_page_utils import dataframe_download, init_session_state, inject_or_css, pretty_metric, to_segment_records
from simulation import (
    SIM_HOURS_PER_SEGMENT,
    MC_DEFAULT_TRIALS,
    mc_simulate_segments,
    mc_summarize_simulation,
    simulate_segments,
    summarize_simulation,
)


st.set_page_config(page_title="Simulation", layout="wide")
init_session_state()
inject_or_css()

st.title("Simulation")
st.caption("Run SimPy discrete-event or Monte Carlo simulation to validate staffing decisions.")

source_option = st.radio(
    "Simulation source",
    ["Optimized staffing", "Current input"],
    horizontal=True,
)

if source_option == "Optimized staffing":
    recommended = st.session_state.get("recommended_data")
    if recommended is None or recommended.empty:
        st.error("Recommended data was not found. Complete Page 2 first, or choose Current input.")
        st.stop()
    simulation_input = recommended.rename(
        columns={"c_optimal": "c", "rho_optimal": "rho"}
    )[["time", "lambda", "mu", "c"]]
else:
    simulation_input = st.session_state.get("df")
    if simulation_input is None or simulation_input.empty:
        st.error("Current input data was not found. Complete Page 1 first.")
        st.stop()

settings = st.columns(3)
sim_hours = settings[0].number_input(
    "DES hours per segment",
    min_value=0.25,
    value=float(SIM_HOURS_PER_SEGMENT),
    step=0.25,
)
queue_threshold = settings[1].number_input("Queue overload threshold", min_value=1, value=20, step=1)
seed_text = settings[2].text_input("Random seed", value="42")
seed = None if seed_text.strip() == "" else int(seed_text)

tab_des, tab_mc = st.tabs(["DES (SimPy)", "Monte Carlo"])

# ── DES Tab ──────────────────────────────────────────────────────────────────

with tab_des:
    if st.button("Run DES Simulation", type="primary", use_container_width=True, key="des_run"):
        results = simulate_segments(
            to_segment_records(simulation_input),
            sim_hours=sim_hours,
            queue_overload_threshold=int(queue_threshold),
            seed=seed,
        )
        st.session_state["simulation_results"] = pd.DataFrame(results)

    results_df = st.session_state.get("simulation_results")
    if results_df is not None and not results_df.empty:
        summary = summarize_simulation(to_segment_records(results_df))
        metric_cols = st.columns(4)
        metric_cols[0].metric("Avg Utilization", pretty_metric(summary["avg_rho"], percent=True), help="Mean simulated server utilization across segments")
        metric_cols[1].metric("Max Utilization", pretty_metric(summary["max_rho"], percent=True), help="Highest simulated utilization among stable segments")
        metric_cols[2].metric("Avg Lq", pretty_metric(summary["avg_Lq"]), help="Mean queue length across all segments")
        metric_cols[3].metric("Total Served", str(summary["total_served"]), help="Total customers served across the simulation")

        st.subheader("DES Results")
        _des_display = results_df.copy()
        if "rho_sim" in _des_display.columns:
            _des_display["rho_sim"] = _des_display["rho_sim"] * 100
        st.dataframe(_des_display, column_config={
            "rho_sim": st.column_config.ProgressColumn("ρ Sim (%)", format="%.1f%%", min_value=0, max_value=100),
        }, use_container_width=True)

        # ── Queue animation: animated utilization bars ────────────────────────
        st.markdown("""
        <style>
        @keyframes pulse-bar {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }
        .queue-bar-container { display:flex; flex-direction:column; gap:4px; margin: 1rem 0; }
        .queue-bar-row { display:flex; align-items:center; gap:8px; }
        .queue-bar-label { width:100px; font-size:0.75rem; font-weight:600; color:#64748B; flex-shrink:0; }
        .queue-bar-track { flex:1; height:20px; background:#E2E8F0; border-radius:10px; overflow:hidden; }
        .queue-bar-fill { height:100%; border-radius:10px; transition:width 1s ease; }
        .queue-bar-value { width:60px; font-size:0.75rem; font-weight:700; color:#1B2A4A; text-align:right; }
        </style>
        """, unsafe_allow_html=True)
        bar_rows = "".join(
            f'<div class="queue-bar-row">'
            f'<span class="queue-bar-label">{r.get("time", "")}</span>'
            f'<div class="queue-bar-track">'
            f'<div class="queue-bar-fill" style="width:{min(r.get("rho_sim", 0) * 100, 100):.0f}%;'
            f'background:{"#C0392B" if r.get("rho_sim", 0) >= 1 else "#E8A838" if r.get("rho_sim", 0) >= 0.85 else "#27AE60"};'
            f'animation:pulse-bar 2s ease infinite;"></div></div>'
            f'<span class="queue-bar-value">{r.get("rho_sim", 0) * 100:.0f}%</span></div>'
            for _, r in results_df.iterrows()
        )
        st.markdown(f'<div class="queue-bar-container">{bar_rows}</div>', unsafe_allow_html=True)

        # ── Heatmap: λ × c × Wq ──────────────────────────────────────────────
        try:
            import plotly.graph_objects as go
            heat_data = results_df.copy()
            if not heat_data.empty and "lambda" in heat_data.columns and "c" in heat_data.columns and "rho_sim" in heat_data.columns:
                heat_pivot = heat_data.pivot_table(index="c", columns="lambda", values="rho_sim", aggfunc="mean")
                fig_hm = go.Figure(data=go.Heatmap(
                    z=heat_pivot.values * 100,
                    x=heat_pivot.columns,
                    y=heat_pivot.index,
                    colorscale="RdYlGn_r",
                    zmin=0, zmax=100,
                    hovertemplate="λ=%{x}<br>c=%{y}<br>ρ=%{z:.1f}%<extra></extra>",
                ))
                fig_hm.update_layout(
                    title="Utilization Heatmap: λ × c",
                    xaxis_title="Arrival Rate λ",
                    yaxis_title="Servers c",
                    height=300,
                    margin=dict(l=40, r=40, t=40, b=40),
                )
                st.plotly_chart(fig_hm, use_container_width=True)
        except Exception:
            pass

        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.line_chart(results_df.set_index("time")[["rho_sim", "Lq_sim"]])
        with chart_cols[1]:
            st.bar_chart(results_df.set_index("time")[["max_queue"]])

        dataframe_download(results_df, "novamart_des_simulation.csv", "Download DES Simulation CSV")
    else:
        st.info("Run the DES simulation to generate results.")

# ── Monte Carlo Tab ──────────────────────────────────────────────────────────

with tab_mc:
    mc_cols = st.columns(3)
    mc_trials = mc_cols[0].number_input(
        "Number of trials",
        min_value=50,
        value=MC_DEFAULT_TRIALS,
        step=50,
    )
    mc_threshold = mc_cols[1].number_input(
        "Failure threshold (ρ)",
        min_value=0.50,
        max_value=1.0,
        value=0.75,
        step=0.05,
    )

    if st.button("Run Monte Carlo", type="primary", use_container_width=True, key="mc_run"):
        mc_results = mc_simulate_segments(
            to_segment_records(simulation_input),
            num_trials=int(mc_trials),
            failure_threshold=mc_threshold,
            seed=seed,
        )
        st.session_state["mc_results"] = pd.DataFrame(mc_results)

    mc_df = st.session_state.get("mc_results")
    if mc_df is not None and not mc_df.empty:
        mc_summary = mc_summarize_simulation(to_segment_records(mc_df))
        mc_metrics = st.columns(4)
        mc_metrics[0].metric("Avg ρ (mean)", pretty_metric(mc_summary["avg_rho"], percent=True), help="Mean utilization across all Monte Carlo trials")
        mc_metrics[1].metric("Avg ρ Std Dev", pretty_metric(mc_summary["avg_rho_std"], percent=True), help="Standard deviation of utilization across trials")
        mc_metrics[2].metric("Avg Failure Rate", pretty_metric(mc_summary["avg_failure_rate"], percent=True), help="Fraction of trials where utilization exceeded the threshold")
        mc_metrics[3].metric("Segments Failed", f"{mc_summary['segments_failed']}/{mc_summary['segments_total']}", help="Segments with at least one failure across trials")

        st.subheader("Monte Carlo Results")

        # Show sample-size adequacy status
        if "adequate_samples" in mc_df.columns and mc_df["adequate_samples"].notna().any():
            if mc_df["adequate_samples"].all():
                st.success("✅ Sample size is sufficient for all segments (CI within 10%).")
            else:
                n_bad = int(mc_df["adequate_samples"].value_counts().get(False, 0))
                st.warning(
                    f"⚠️ Some segments ({n_bad}) may need more trials for reliable estimates. "
                    "Try increasing N above 500."
                )

        # Build display table with CI-formatted Wq column
        display_df = mc_df[
            ["time", "rho_mean", "rho_std", "rho_p95", "Lq_mean", "Wq_mean", "failure_rate", "status"]
        ].copy()

        if "ci_Wq_hw" in mc_df.columns:
            display_df["Wq (95% CI)"] = display_df.apply(
                lambda r: (
                    f"{r['Wq_mean'] * 60:.2f} min ± {r['ci_Wq_hw'] * 60:.2f} min (95% CI)"
                    if pd.notna(r.get("Wq_mean")) and pd.notna(r.get("ci_Wq_hw"))
                    else "N/A"
                ),
                axis=1,
            )
        _mc_display = display_df.copy()
        if "rho_mean" in _mc_display.columns:
            _mc_display["rho_mean"] = _mc_display["rho_mean"] * 100
        st.dataframe(_mc_display, column_config={
            "rho_mean": st.column_config.ProgressColumn("ρ Mean (%)", format="%.1f%%", min_value=0, max_value=100),
        }, use_container_width=True)

        chart_cols = st.columns(2)
        with chart_cols[0]:
            chart_df = mc_df.set_index("time")[["rho_mean", "rho_p95"]]
            st.line_chart(chart_df)
        with chart_cols[1]:
            st.bar_chart(mc_df.set_index("time")[["failure_rate"]])

        dataframe_download(mc_df, "novamart_mc_simulation.csv", "Download Monte Carlo CSV")
    else:
        st.info("Run the Monte Carlo simulation to generate results.")
