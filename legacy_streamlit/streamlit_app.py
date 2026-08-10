"""
Streamlit Multi-Page Dashboard — 4-Page Queueing Theory System
With strict data pipeline integrity and mandatory error-checking.

🎯 Architecture:
  Page 1 (pages/1_current_metrics.py) — Upload & validate
  Page 2 (pages/2_optimization.py) — Generate recommendations
  Page 3 (pages/3_comparison.py) — Compare with error-safe merge
  Page 4 (pages/4_simulation.py) — Monte Carlo using ONLY recommended data

🔐 Safety Rules:
  - Session state initialized on startup
  - Schema validation on all data entry points
  - Page 3 & 4 require upstream completion
  - All numeric columns validated before compute
  - No mutations of original data — always .copy()
"""

import sys
from pathlib import Path

import streamlit as st

_APP_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _APP_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app_page_utils import init_session_state
from i18n import language_selector, t
from theme import apply_dark_overrides, apply_theme, onboarding_tour, theme_toggle_button

from backend.queueing_engine.config import (
    DEFAULT_ABANDONMENT_COST,
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
)
from backend.queueing_engine.log import configure_logging

configure_logging()

# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED_COLUMNS — Data Contract (STRICT)
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "c"
]

OPTIONAL_COLUMNS = [
    "variance",  # For M/G/c and M/G/c/K model support
    "K",  # Total finite system capacity for M/M/c/K and M/G/c/K
]

def main():
    """Initialize app and configure metadata."""
    st.set_page_config(
        page_title="Queueing Theory Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_theme()
    apply_dark_overrides()
    init_session_state()

    # ═════════════════════════════════════════════════════════════════════════
    # ONBOARDING TOUR
    # ═════════════════════════════════════════════════════════════════════════
    if not st.session_state.get("onboarding_done"):
        with st.expander("👋 Welcome! Take a quick tour", expanded=True):
            onboarding_tour()

    # ═════════════════════════════════════════════════════════════════════════
    # HERO SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown(f"""
    <div class="hero-section">
        <div class="subtitle">{t('app.title').upper()}</div>
        <h1>{t('app.subtitle')}</h1>
        <div class="tagline">{t('app.tagline')}</div>
        <div class="description">
            {t('app.description')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Hero section button
    if st.button("📥 Upload your CSV", key="hero_upload", use_container_width=True):
        st.switch_page("pages/1_current_metrics.py")

    with st.expander("📐 Technical Details — Supported Models"):
        st.markdown("""
        **Queueing Models:**
        - **M/M/1** — Single server, Poisson arrivals, exponential service
        - **M/M/c** — Multi-server, Poisson arrivals, exponential service
        - **M/G/c** — Multi-server, general service time distribution
        - **M/M/c/K** — Multi-server, finite system capacity
        - **M/G/c/K** — Multi-server, general service, finite capacity
        - **M/M/c+M (Erlang-A)** — Multi-server with customer abandonment
        - **Two-class priority** — Express lane + regular lane

        **Simulation:** Discrete-event (SimPy) · Monte Carlo (configurable trials, default 2K)
        **Input:** 4 required columns (time, λ, μ, c) + 2 optional (variance, K)
        """)

    # ═════════════════════════════════════════════════════════════════════════
    # INFO SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="info-section">
        <div class="info-icon">⏰</div>
        <div class="info-content">
            <h3>Balancing Queues, Reducing Costs.</h3>
            <p>This system applies queueing theory to real operational data, helping managers make informed staffing decisions that reduce delays and control costs.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════
    # WORKFLOW SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">THE 4-PAGE WORKFLOW</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">1</div>
            <h3>Current metrics</h3>
            <p>Upload your CSV and see your queue's true state: utilization, average wait, queue length, and where things are quietly breaking down.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Explore →", key="workflow_1", use_container_width=True):
            st.switch_page("pages/1_current_metrics.py")

    with col2:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">2</div>
            <h3>Optimization</h3>
            <p>The model calculates the minimum number of servers needed to hit your target wait time. No manual trial-and-error required.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Optimize →", key="workflow_2", use_container_width=True):
            st.switch_page("pages/2_optimization.py")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">3</div>
            <h3>Simulation</h3>
            <p>Run Monte Carlo scenarios across thousands of variations. See how your queue behaves when arrival rates spike before it happens in production.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Simulate here →", key="workflow_3", use_container_width=True):
            st.switch_page("pages/3_simulation.py")

    with col2:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">4</div>
            <h3>Compare</h3>
            <p>Side-by-side view of current vs recommended. See exactly what changes, what improves, and what it means for your team's workload.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Review →", key="workflow_4", use_container_width=True):
            st.switch_page("pages/4_comparison.py")

    st.markdown("---")

    # ═════════════════════════════════════════════════════════════════════════
    # SCHEMA SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">WHAT TO PREPARE — YOUR CSV SCHEMA</p>', unsafe_allow_html=True)
    st.markdown('<p style="color: #999; margin-bottom: 1.5rem;"><strong>4 required columns</strong> + 2 optional | <span style="color: #28a745;">Supports M/M/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K</span></p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="schema-grid">
        <div class="schema-item">
            <div class="field-name">time</div>
            <div class="field-type">Text — interval label</div>
            <div class="field-example">e.g., 08:00–09:00</div>
        </div>
        <div class="schema-item">
            <div class="field-name">lambda</div>
            <div class="field-type">Float — arrival rate</div>
            <div class="field-example">e.g., 12.5 /min</div>
        </div>
        <div class="schema-item">
            <div class="field-name">mu</div>
            <div class="field-type">Float — service rate</div>
            <div class="field-example">e.g., 5.0 /min</div>
        </div>
        <div class="schema-item">
            <div class="field-name">c</div>
            <div class="field-type">Integer — servers</div>
            <div class="field-example">e.g., 3</div>
        </div>
        <div class="schema-item">
            <div class="field-name">variance</div>
            <div class="field-type">Float — optional (M/G/c)</div>
            <div class="field-example">e.g., 0.04</div>
        </div>
        <div class="schema-item">
            <div class="field-name">K</div>
            <div class="field-type">Integer — optional capacity</div>
            <div class="field-example">e.g., 12</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Required:** time, lambda, mu, c | **Optional:** variance (general service), K (finite total capacity)")

    # ═════════════════════════════════════════════════════════════════════════
    # FORMULA REFERENCE
    # ═════════════════════════════════════════════════════════════════════════
    with st.expander("📐 Queueing Theory Formulas", expanded=False):
        st.markdown("**Kendall Notation:** `A/B/c/K` where A = arrival dist., B = service dist., c = servers, K = system capacity")
        st.latex(r"\text{M/M/1:} \quad L = \frac{\lambda}{\mu - \lambda} \quad W_q = \frac{\lambda}{\mu(\mu - \lambda)}")
        st.latex(r"\text{M/M/c:} \quad P_0 = \left[ \sum_{n=0}^{c-1} \frac{(c\rho)^n}{n!} + \frac{(c\rho)^c}{c!(1-\rho)} \right]^{-1} \quad W_q = \frac{P_0 (c\rho)^c}{c! c\mu (1-\rho)^2}")
        st.latex(r"\text{Little's Law:} \quad L = \lambda W \quad L_q = \lambda W_q \quad W = W_q + \frac{1}{\mu}")
        st.latex(r"\text{Pollaczek-Khinchine (M/G/1):} \quad W_q = \frac{\lambda (\sigma^2 + 1/\mu^2)}{2(1-\rho)}")
        st.latex(r"\text{Erlang-C:} \quad C(c, a) = \frac{a^c / c!}{(1-\rho) \sum_{n=0}^{c-1} a^n / n! + a^c / c!}")
        st.caption("Where: ρ = λ/(cμ)  |  a = λ/μ  |  λ = arrival rate  |  μ = service rate")

    # ═════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═════════════════════════════════════════════════════════════════════════
    st.sidebar.markdown("### 📊 Queueing Theory Optimizer")
    st.sidebar.markdown("""
    **Multi-Page System**
    - 📥 **Page 1:** Upload & compute current metrics
    - ⚙️ **Page 2:** Generate optimized recommendations
    - 🕹️ **Page 3:** Simulation
    - 📊 **Page 4:** Comparison
    
    **Supported Models**
    - M/M/1 (single server)
    - M/M/c (multi-server)
    - M/G/c (general service time)
    - M/M/c/K and M/G/c/K (finite total system capacity)
    
    **Schema** (4 required + 2 optional)
    """)

    st.sidebar.markdown(f"""
    ```
    {', '.join(REQUIRED_COLUMNS)}
    variance, K (optional)
    ```
    """)

    # Theme toggle
    theme_toggle_button()

    # Language selector
    language_selector()

    # Cost parameters
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💰 Cost Parameters")
    st.sidebar.number_input("Server Cost (₱/hr)", min_value=0.0, value=DEFAULT_SERVER_COST_HR, step=1.0, key="sb_server_cost")
    st.sidebar.number_input("Waiting Cost (₱/hr)", min_value=0.0, value=DEFAULT_WAIT_COST_HR, step=1.0, key="sb_wait_cost")
    st.sidebar.number_input("Abandonment Cost (₱)", min_value=0.0, value=DEFAULT_ABANDONMENT_COST, step=1.0, key="sb_abandon_cost")
    st.sidebar.number_input("Abandonment Rate", min_value=0.0, max_value=1.0, value=0.10, step=0.05, key="sb_abandon_rate")

    # Progress timeline
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Progress")
    steps = [
        ("1️⃣ Upload Data", st.session_state.get("current_data") is not None),
        ("2️⃣ Optimize", st.session_state.get("recommended_data") is not None),
        ("3️⃣ Simulate", st.session_state.get("simulation_results") is not None),
        ("4️⃣ Compare", st.session_state.get("comparison_data") is not None),
    ]
    for i, (label, done) in enumerate(steps):
        icon = "✅" if done else "➖"
        weight = "bold" if done else "normal"
        st.sidebar.markdown(
            f"<span style='font-weight: {weight};'>{icon} {label}</span>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
