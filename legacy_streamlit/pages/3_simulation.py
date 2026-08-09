"""Simulation page with DES (SimPy) and Monte Carlo tabs."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app_page_utils import dataframe_download, init_session_state, pretty_metric, to_segment_records
from i18n import t
from theme import apply_dark_overrides, apply_theme, breadcrumb, skeleton_card, skeleton_metric, toast

from backend.queueing_engine.log import get_logger
from backend.queueing_engine.simulation import (
    MC_DEFAULT_TRIALS,
    SIM_HOURS_PER_SEGMENT,
    mc_simulate_segments,
    mc_summarize_simulation,
    simulate_segments,
    summarize_simulation,
)

logger = get_logger(__name__)


def _safe_rho(value) -> float:
    """Coerce a rho value to a finite float, defaulting to 0 for error rows."""
    try:
        rho = float(value)
    except (TypeError, ValueError):
        return 0.0
    return rho if math.isfinite(rho) else 0.0


st.set_page_config(page_title="Simulation", layout="wide")
init_session_state()
apply_theme()
apply_dark_overrides()
breadcrumb(current_page=3)

st.title(t("page3.title"))
st.caption(t("page3.caption"))

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
try:
    seed = None if seed_text.strip() == "" else int(seed_text)
except ValueError:
    seed = None

tab_des, tab_mc = st.tabs([t("page3.des"), t("page3.mc")])

# ── DES Tab ──────────────────────────────────────────────────────────────────

with tab_des:
    if st.button("Run DES Simulation", type="primary", use_container_width=True, key="des_run"):
        with st.spinner("Running DES simulation…"):
            skeleton_metric()
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
            f'<div class="queue-bar-fill" style="width:{min(_safe_rho(r.get("rho_sim")) * 100, 100):.0f}%;'
            f'background:{"#C0392B" if _safe_rho(r.get("rho_sim")) >= 1 else "#E8A838" if _safe_rho(r.get("rho_sim")) >= 0.85 else "#27AE60"};'
            f'animation:pulse-bar 2s ease infinite;"></div></div>'
            f'<span class="queue-bar-value">{_safe_rho(r.get("rho_sim")) * 100:.0f}%</span></div>'
            for _, r in results_df.iterrows()
        )
        st.markdown(f'<div class="queue-bar-container">{bar_rows}</div>', unsafe_allow_html=True)

        # ── Heatmap: λ × c × Wq ──────────────────────────────────────────────
        try:
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
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=results_df["time"], y=results_df["rho_sim"],
                mode="lines+markers", name="ρ sim",
                line=dict(color="#E8A838", width=2),
            ))
            fig_line.add_trace(go.Scatter(
                x=results_df["time"], y=results_df["Lq_sim"],
                mode="lines+markers", name="Lq sim",
                line=dict(color="#2E86AB", width=2),
                yaxis="y2",
            ))
            fig_line.update_layout(
                title="Utilization & Queue Length over Time",
                xaxis_title="Time Segment",
                yaxis=dict(title="ρ sim", color="#E8A838"),
                yaxis2=dict(title="Lq sim", color="#2E86AB", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.12),
                height=350, margin=dict(l=40, r=40, t=50, b=40),
            )
            st.plotly_chart(fig_line, use_container_width=True)
        with chart_cols[1]:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=results_df["time"], y=results_df["max_queue"],
                marker_color="#C0392B", name="Max Queue",
            ))
            fig_bar.update_layout(
                title="Maximum Queue Length per Segment",
                xaxis_title="Time Segment",
                yaxis_title="Max Queue",
                height=350, margin=dict(l=40, r=40, t=50, b=40),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        if "Lq_sim" in results_df.columns:
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=results_df["Lq_sim"],
                nbinsx=20,
                marker_color="#5DADE2",
                name="Lq sim",
            ))
            fig_hist.update_layout(
                title="Distribution of Queue Lengths (Lq)",
                xaxis_title="Queue Length",
                yaxis_title="Frequency",
                height=300, margin=dict(l=40, r=40, t=40, b=40),
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        dataframe_download(results_df, "novamart_des_simulation.csv", "Download DES Simulation CSV")
    else:
        skeleton_metric()

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
        with st.spinner("Running Monte Carlo (500 trials)…"):
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
                toast("Sample size is sufficient for all segments (CI within 10%).", type="success")
            else:
                n_bad = int(mc_df["adequate_samples"].value_counts().get(False, 0))
                toast(
                    f"Some segments ({n_bad}) may need more trials for reliable estimates. "
                    "Try increasing N above 500.",
                    type="warning",
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
            fig_mc_line = go.Figure()
            fig_mc_line.add_trace(go.Scatter(
                x=mc_df["time"], y=mc_df["rho_mean"],
                mode="lines+markers", name="ρ mean",
                line=dict(color="#E8A838", width=2),
            ))
            fig_mc_line.add_trace(go.Scatter(
                x=mc_df["time"], y=mc_df["rho_p95"],
                mode="lines+markers", name="ρ p95",
                line=dict(color="#C0392B", width=2, dash="dash"),
            ))
            fig_mc_line.update_layout(
                title="Mean & P95 Utilization by Segment",
                xaxis_title="Time Segment",
                yaxis_title="Utilization (ρ)",
                legend=dict(orientation="h", y=1.12),
                height=350, margin=dict(l=40, r=40, t=50, b=40),
            )
            st.plotly_chart(fig_mc_line, use_container_width=True)
        with chart_cols[1]:
            fig_mc_bar = go.Figure()
            fig_mc_bar.add_trace(go.Bar(
                x=mc_df["time"], y=mc_df["failure_rate"],
                marker_color="#C0392B", name="Failure Rate",
            ))
            fig_mc_bar.update_layout(
                title="Failure Rate by Segment",
                xaxis_title="Time Segment",
                yaxis_title="Failure Rate",
                height=350, margin=dict(l=40, r=40, t=50, b=40),
            )
            st.plotly_chart(fig_mc_bar, use_container_width=True)

        dataframe_download(mc_df, "novamart_mc_simulation.csv", "Download Monte Carlo CSV")
    else:
        st.info("Run the Monte Carlo simulation to generate results.")
