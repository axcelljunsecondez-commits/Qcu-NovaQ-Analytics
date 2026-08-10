"""Current queue metrics page."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from app_page_utils import (
    dataframe_download,
    init_session_state,
    pretty_metric,
    read_uploaded_table,
    sample_segments,
    to_segment_records,
    validate_and_normalize,
)
from data_processing import compute_kpis, get_unstable_messages, process_segments
from i18n import t
from theme import (
    apply_dark_overrides,
    apply_theme,
    breadcrumb,
    skeleton_metric,
    toast,
)

from backend.queueing_engine.services.costing import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    compute_all_costs,
    compute_cost_summary,
)

st.set_page_config(page_title="Current Metrics", layout="wide")
init_session_state()
apply_theme()
apply_dark_overrides()

# ── Alert thresholds (sidebar, form-wrapped to avoid re-render cascade) ───
if "alert_thresholds" not in st.session_state:
    st.session_state["alert_thresholds"] = {"max_wq": 5.0, "max_rho": 0.85}

st.sidebar.subheader("🔔 Alert Thresholds")
with st.sidebar.form("alert_thresholds_form"):
    st.caption("Adjust thresholds then press Apply:")
    max_wq = st.number_input(
        "Max wait time (min)", value=st.session_state["alert_thresholds"]["max_wq"], min_value=0.1, step=0.5
    )
    max_rho = st.number_input(
        "Max utilization (ρ)", value=st.session_state["alert_thresholds"]["max_rho"], min_value=0.1, max_value=1.0, step=0.05
    )
    if st.form_submit_button("Apply", use_container_width=True):
        st.session_state["alert_thresholds"] = {"max_wq": max_wq, "max_rho": max_rho}

breadcrumb(current_page=1)
st.title(t("page1.title"))
st.caption(t("page1.caption"))

data_source_options = {"csv": t("page1.upload_csv"), "pos": t("page1.import_pos")}
data_source = st.radio(
    t("page1.data_source"),
    list(data_source_options.keys()),
    format_func=lambda key: data_source_options[key],
    horizontal=True,
)

source_df = None

# ── POS Import Path ───────────────────────────────────────────────────────

if data_source == "pos":
    from backend.queueing_engine.statistics import (  # noqa: E402 — lazy import (saves ~1–2s on page load)
        compute_lambda_mu,
        fit_service_distribution,
        load_transactions,
        test_poisson_arrivals,
        to_novamart_csv,
    )

    # Clear stale manual-upload state
    if "pos_csv" not in st.session_state:
        st.session_state["pos_csv"] = None

    pos_file = st.file_uploader(
        "Upload raw POS transaction CSV",
        type=["csv"],
        key="pos_upload",
    )

    if pos_file is not None:
        try:
            raw_df = load_transactions(pos_file)
            param_df = compute_lambda_mu(raw_df)
            csv_str = to_novamart_csv(param_df)

            st.success(f"Computed {len(param_df)} time segments from POS data.")
            st.subheader("Computed Queueing Parameters")
            st.dataframe(param_df, use_container_width=True)

            # Distribution tests
            poisson_result = test_poisson_arrivals(raw_df)
            service_result = fit_service_distribution(raw_df)

            if poisson_result["is_poisson"]:
                st.success("✅ Arrivals follow Poisson distribution")
            elif poisson_result.get("warning"):
                st.warning(poisson_result["warning"])

            st.info(
                f"Estimated service rate: μ = {service_result['mu_mle']:.1f}/hr "
                f"| CV = {service_result['cv']:.2f}"
            )

            if not service_result["is_exponential"]:
                st.warning(
                    "Service times deviate from exponential — "
                    "consider using variance column + M/G/c model."
                )

            if st.button("Use this data", type="primary", use_container_width=True):
                st.session_state["pos_csv"] = csv_str
                st.rerun()
        except Exception as exc:
            st.error(f"Error processing POS file: {exc}")

    if st.session_state.get("pos_csv"):
        source_df = pd.read_csv(io.StringIO(st.session_state["pos_csv"]))
    else:
        st.info("Upload a POS transaction CSV to generate queueing parameters.")
        st.stop()

# ── Manual Upload Path (existing behaviour) ───────────────────────────────

else:
    # Clear any previously stored POS data when switching modes
    st.session_state["pos_csv"] = None

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"], key="manual_upload")
    use_sample = st.button("Load Sample Data", use_container_width=True)

    if uploaded_file is not None:
        try:
            source_df = read_uploaded_table(uploaded_file)
        except ValueError as exc:
            st.error(str(exc))
    elif use_sample:
        source_df = sample_segments()

    if source_df is None:
        st.info("Upload a file or load sample data to begin.")
        st.stop()

# ── Data Preview with inline editing ──────────────────────────────
with st.expander("📝 Preview & Edit Data Before Validation", expanded=False):
    st.caption("Edit values directly in the table. Click outside a cell to commit changes.")
    edited_df = st.data_editor(
        source_df,
        use_container_width=True,
        num_rows="dynamic",
        key="data_preview_editor",
    )
    use_edited = st.checkbox("Use edited data for validation", value=False)
    source_for_validation = edited_df if use_edited else source_df
    if st.button("Re-validate", use_container_width=True):
        st.rerun()

valid, message, normalized_df = validate_and_normalize(source_for_validation)
if not valid:
    st.error(message)
    st.dataframe(normalized_df, use_container_width=True)
    st.stop()

toast(message, "success")
st.subheader("Input Data")

# ── Filter bar for data table ──────────────────────────────────
filter_col, search_col = st.columns([2, 1])
filter_text = filter_col.text_input("🔍 Filter rows", placeholder="Type to filter...", label_visibility="collapsed")
col_filter = search_col.selectbox("Column", ["time", "lambda", "mu", "c"], label_visibility="collapsed")

_display_df = normalized_df.copy()
if filter_text:
    _display_df = _display_df[_display_df[col_filter].astype(str).str.contains(filter_text, case=False, na=False)]
st.dataframe(_display_df, use_container_width=True)

segments = to_segment_records(normalized_df)
results_df = process_segments(segments)
kpis = compute_kpis(results_df)

# ── Threshold alerts (vectorized) ───────────────────────────────────────
thresholds = st.session_state.get("alert_thresholds", {"max_wq": 5.0, "max_rho": 0.85})
max_wq_min = thresholds["max_wq"]
max_rho_val = thresholds["max_rho"]

df_violations = results_df.copy()
wq_exceed = df_violations["Wq"].notna() & (df_violations["Wq"] * 60 > max_wq_min)
rho_exceed = df_violations["rho"].notna() & (df_violations["rho"] > max_rho_val)
unstable = ~df_violations["stable"]

has_any = wq_exceed | rho_exceed | unstable

if has_any.any():
    for idx in df_violations[has_any].index:
        row = df_violations.loc[idx]
        seg_time = str(row.get("time", "Unknown"))
        issues = []
        if wq_exceed.loc[idx]:
            issues.append(f"Wq = {row['Wq'] * 60:.2f} min exceeds threshold {max_wq_min:.2f} min")
        if rho_exceed.loc[idx]:
            issues.append(f"ρ = {row['rho']:.2%} exceeds threshold {max_rho_val:.0%}")
        if unstable.loc[idx]:
            issues.append("System is unstable (ρ ≥ 1)")
        st.error(f"🚨 Segment {seg_time}: {' | '.join(issues)}")
else:
    st.success("✅ All segments are within thresholds.")

# ── Health score gauge ────────────────────────────────────────────────
unstable = kpis.get("unstable_count", 0)
avg_util = kpis.get("avg_utilization", 0) or 0
avg_wq = kpis.get("avg_waiting_time", 0) or 0
util_score = max(0, 100 - abs(avg_util - 0.7) * 200)
wq_score = max(0, 100 - avg_wq * 60)
stable_score = 100 if unstable == 0 else max(0, 100 - unstable * 20)
health = int(round(util_score * 0.3 + wq_score * 0.4 + stable_score * 0.3))
health_color = "#27AE60" if health >= 70 else "#E8A838" if health >= 40 else "#C0392B"
st.markdown(
    f'<div style="display:flex;align-items:center;gap:1rem;background:#1B2A4A;padding:1rem 2rem;border-radius:16px;margin-bottom:1.5rem;">'
    f'<div style="font-size:2.5rem;font-weight:900;color:{health_color};">{health}</div>'
    f'<div style="flex:1;"><div style="height:8px;background:#2C4A72;border-radius:4px;overflow:hidden;">'
    f'<div style="height:100%;width:{health}%;background:{health_color};border-radius:4px;transition:width 0.6s;"></div></div></div>'
    f'<div style="color:#E8A838;font-weight:700;font-size:0.9rem;">SYSTEM HEALTH</div>'
    f'</div>',
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
metric_cols[0].metric("Average Utilization", pretty_metric(kpis["avg_utilization"], percent=True), help="Fraction of time servers are busy. Above 85% → queues grow fast.")
metric_cols[1].metric("Max Utilization", pretty_metric(kpis["max_utilization"], percent=True), help="Fraction of time servers are busy. Above 85% → queues grow fast.")
metric_cols[2].metric("Average Wq (min)", pretty_metric(kpis["avg_waiting_time"] * 60), help="Average time in minutes a customer waits before being served. Excludes service time.")
metric_cols[3].metric("Unstable Rows", str(kpis["unstable_count"]), help="Segments where ρ ≥ 1 — system cannot keep up with arrivals")

def _model_badge_html(name):
    cls_map = {
        "M/M/1": "badge-mm1",
        "M/M/c": "badge-mmc",
        "M/G/c": "badge-mgc",
        "M/M/c/K": "badge-mmc-k",
        "M/G/c/K": "badge-mgc-k",
        "M/M/c+M (Erlang-A)": "badge-erlang-a",
    }
    cls = cls_map.get(name, "")
    return f'<span class="{cls}">{name}</span>' if cls else name

st.subheader("Computed Metrics")
_display = results_df.copy()
if "model" in _display.columns:
    unique_models = _display["model"].unique()
    legend = "".join(_model_badge_html(m) for m in sorted(unique_models))
    st.markdown(f'<div class="model-legend">{legend}</div>', unsafe_allow_html=True)
if "rho" in _display.columns:
    _display["rho"] = _display["rho"] * 100
st.dataframe(_display, column_config={
    "rho": st.column_config.ProgressColumn("ρ (%)", format="%.1f%%", min_value=0, max_value=100),
}, use_container_width=True)

for warning in get_unstable_messages(results_df):
    st.warning(warning)

st.subheader("Cost Analysis")

cost_per_server_hr = st.session_state.get("sb_server_cost", DEFAULT_SERVER_COST_HR)
cost_per_wait_hr = st.session_state.get("sb_wait_cost", DEFAULT_WAIT_COST_HR)
cost_per_abandonment = st.session_state.get("sb_abandon_cost", DEFAULT_ABANDONMENT_COST)
abandonment_rate = st.session_state.get("sb_abandon_rate", 0.10)
st.caption(f"Cost parameters from sidebar — Server: ₱{cost_per_server_hr:.0f}/hr · Wait: ₱{cost_per_wait_hr:.0f}/hr · Abandon: ₱{cost_per_abandonment:.0f}")

cost_summary = compute_cost_summary(
    results_df,
    cost_per_server_hr=cost_per_server_hr,
    cost_per_wait_hr=cost_per_wait_hr,
    cost_per_abandonment=cost_per_abandonment,
    abandonment_rate=abandonment_rate,
)
cost_df = compute_all_costs(
    results_df,
    cost_per_server_hr=cost_per_server_hr,
    cost_per_wait_hr=cost_per_wait_hr,
    cost_per_abandonment=cost_per_abandonment,
    abandonment_rate=abandonment_rate,
)

cost_metrics = st.columns(4)
cost_metrics[0].metric("Server Cost", pretty_metric(cost_summary["total_server_cost"], money=True), help="Total cost of staffing servers across all segments")
cost_metrics[1].metric("Waiting Cost", pretty_metric(cost_summary["total_wait_cost"], money=True), help="Cost incurred from customer waiting time")
cost_metrics[2].metric("Abandonment Cost", pretty_metric(cost_summary["total_abandonment_cost"], money=True), help="Cost of customers who left without service (Erlang-A only)")
cost_metrics[3].metric("Total Cost", pretty_metric(cost_summary["total_cost"], money=True), help="Sum of server, waiting, and abandonment costs")

cost_display_cols = ["time", "c", "lambda", "Wq", "server_cost", "wait_cost", "abandonment_cost", "total_cost"]
st.dataframe(cost_df[[c for c in cost_display_cols if c in cost_df.columns]], use_container_width=True)

# Show Erlang-A abandonment info when applicable
erlang_rows = results_df[results_df["model"] == "M/M/c+M (Erlang-A)"]
if not erlang_rows.empty:
    avg_abandon = erlang_rows["abandonment_rate"].mean()
    avg_lambda_eff = erlang_rows["lambda_eff"].mean()
    avg_lambda = erlang_rows["lambda"].mean()

    st.info(
        f"**Erlang-A (Abandonment) Summary**  —  "
        f"Avg abandonment rate: {avg_abandon:.2%}  |  "
        f"Avg effective λ: {avg_lambda_eff:.1f} / {avg_lambda:.1f} "
        f"({erlang_rows['theta'].iloc[0]} reneging rate θ)"
    )

if st.button("Save as Current Data", type="primary", use_container_width=True):
    st.session_state["df"] = normalized_df.copy()
    st.session_state["current_data"] = results_df.copy()
    toast("Current metrics saved! Proceed to Optimization page.", "success")

dataframe_download(results_df, "novamart_current_metrics.csv", "Download Current Metrics CSV")
