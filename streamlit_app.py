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

import streamlit as st
import pandas as pd
import base64
from pathlib import Path
import os
from PIL import Image

from config import (
    DEFAULT_SERVER_COST_HR,
    DEFAULT_WAIT_COST_HR,
    DEFAULT_ABANDONMENT_COST,
)

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

# ─────────────────────────────────────────────────────────────────────────────
# LOGO UTILITY FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def get_base64_image(image_path):
    """Convert image file to base64 string."""
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization (MANDATORY)
# ─────────────────────────────────────────────────────────────────────────────

def init_session_state():
    """Initialize all required session state keys."""
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "current_data" not in st.session_state:
        st.session_state["current_data"] = None
    if "recommended_data" not in st.session_state:
        st.session_state["recommended_data"] = None
    if "comparison_data" not in st.session_state:
        st.session_state["comparison_data"] = None
    if "simulation_results" not in st.session_state:
        st.session_state["simulation_results"] = None
    if "waste_reduction_data" not in st.session_state:
        st.session_state["waste_reduction_data"] = None
    
    # Costing parameters (NOVAMART defaults)
    if "cost_per_server_hr" not in st.session_state:
        st.session_state["cost_per_server_hr"] = DEFAULT_SERVER_COST_HR
    if "cost_per_wait_hr" not in st.session_state:
        st.session_state["cost_per_wait_hr"] = DEFAULT_WAIT_COST_HR
    if "cost_per_abandonment" not in st.session_state:
        st.session_state["cost_per_abandonment"] = DEFAULT_ABANDONMENT_COST


def main():
    """Initialize app and configure metadata."""
    st.set_page_config(
        page_title="Queueing Theory Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Apply modern SaaS design system
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@600;700;800&display=swap');
    
    /* Page Background */
    .main {
        background-color: #F1F5F9;
    }
    
    .block-container {
        background-color: #F1F5F9;
        padding-top: 2rem;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       HERO SECTION - Premium Gradient with Depth
    ───────────────────────────────────────────────────────────────────────────────*/
    .hero-section {
        background: linear-gradient(135deg, #1B2A4A 0%, #243B5E 50%, #2C4A72 100%);
        color: #FFFFFF;
        padding: 5rem 3rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 3.5rem;
        box-shadow: 0 24px 48px rgba(27, 42, 74, 0.25),
                    0 0 1px rgba(27, 42, 74, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .hero-section::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 50%;
        filter: blur(60px);
    }
    
    .hero-section .subtitle {
        font-size: 0.875rem;
        letter-spacing: 3px;
        color: #FFFFFF;
        margin-bottom: 1rem;
        text-transform: uppercase;
        font-weight: 800;
        font-family: 'Inter', sans-serif;
    }
    
    .hero-section h1 {
        margin: 0;
        font-size: 3.5rem;
        font-weight: 900;
        line-height: 1.15;
        margin-bottom: 0.75rem;
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
        text-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
    }
    
    .hero-section .tagline {
        font-size: 1.875rem;
        font-weight: 500;
        color: #FFFFFF;
        margin-bottom: 1.5rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .hero-section .description {
        font-size: 1.125rem;
        color: #FFFFFF;
        max-width: 700px;
        margin: 0 auto 2.5rem;
        line-height: 1.8;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       BUTTON STYLES - Premium Accent Color Cyan
    ───────────────────────────────────────────────────────────────────────────────*/
    .button-group {
        display: flex;
        gap: 1.25rem;
        justify-content: center;
        margin-bottom: 2.5rem;
        flex-wrap: wrap;
    }
    
    /* Streamlit button wrapper styling */
    div[data-testid="stButtonContainer"] button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 0.875rem 1.75rem !important;
        border-radius: 10px !important;
        font-size: 1rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: none !important;
    }
    
    /* Primary CTA Button */
    .btn-primary {
        padding: 1rem 2.25rem;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1rem;
        text-decoration: none;
        cursor: pointer;
        border: none;
        background: linear-gradient(135deg, #E8A838 0%, #D4912F 100%);
        color: #1B2A4A;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 20px rgba(232, 168, 56, 0.25);
        font-family: 'Inter', sans-serif;
    }
    
    .btn-primary:hover {
        background: linear-gradient(135deg, #D4912F 0%, #C07D20 100%);
        box-shadow: 0 12px 32px rgba(232, 168, 56, 0.35);
        transform: translateY(-2px);
    }
    
    .btn-primary:active {
        transform: translateY(0);
        box-shadow: 0 4px 12px rgba(232, 168, 56, 0.2);
    }
    
    /* Secondary Button - Outline */
    .btn-secondary {
        padding: 1rem 2.25rem;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1rem;
        text-decoration: none;
        cursor: pointer;
        border: 2px solid #E8A838;
        background: transparent;
        color: #E8A838;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        font-family: 'Inter', sans-serif;
    }
    
    .btn-secondary:hover {
        background: rgba(232, 168, 56, 0.1);
        border-color: #D4912F;
        color: #D4912F;
        box-shadow: 0 8px 20px rgba(232, 168, 56, 0.15);
    }
    
    .tags-group {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 1.5rem;
    }
    
    .tag {
        background: #2C4A72;
        color: #E8A838;
        padding: 0.65rem 1.4rem;
        border-radius: 24px;
        font-size: 0.9rem;
        border: 1px solid #2C4A72;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       CARD COMPONENTS - Premium Style
    ───────────────────────────────────────────────────────────────────────────────*/
    
    /* Info Section Card */
    .info-section {
        background: #FFFFFF;
        padding: 2.25rem;
        border-radius: 16px;
        margin-bottom: 3.5rem;
        border: 1px solid #E2E8F0;
        display: flex;
        gap: 1.75rem;
        align-items: flex-start;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .info-section:hover {
        border-color: #E8A838;
        box-shadow: 0 12px 32px rgba(232, 168, 56, 0.12);
    }
    
    .info-icon {
        font-size: 2.8rem;
        flex-shrink: 0;
        line-height: 1;
    }
    
    .info-content h3 {
        margin-top: 0;
        color: #0F172A;
        font-size: 1.3rem;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }
    
    .info-content p {
        margin: 0.75rem 0 0 0;
        color: #64748B;
        line-height: 1.8;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
    }
    
    /* Section Titles */
    .section-title {
        font-size: 0.8rem;
        letter-spacing: 2.5px;
        color: #64748B;
        margin-bottom: 2.25rem;
        font-weight: 800;
        text-transform: uppercase;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       WORKFLOW CARDS - Premium Design
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .workflow-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 2rem;
        margin-bottom: 3.5rem;
    }
    
    @media (max-width: 768px) {
        .workflow-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .workflow-card {
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2.25rem;
        background: #FFFFFF;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    }
    
    .workflow-card:hover {
        border-color: #E8A838;
        box-shadow: 0 16px 40px rgba(232, 168, 56, 0.15);
        transform: translateY(-6px);
    }
    
    .workflow-card .step-number {
        display: inline-block;
        background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
        color: #92400E;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        line-height: 56px;
        text-align: center;
        font-weight: 800;
        font-size: 1.5rem;
        margin-bottom: 1.25rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .workflow-card h3 {
        margin-top: 0;
        font-size: 1.25rem;
        color: #0F172A;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }
    
    .workflow-card p {
        color: #64748B;
        margin: 0.75rem 0 1.5rem 0;
        line-height: 1.8;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
    }
    
    .workflow-card .action-btn {
        color: #E8A838;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
    }
    
    .workflow-card .action-btn:hover {
        color: #D4912F;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       SCHEMA CARDS - Premium Grid
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .schema-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.75rem;
        margin-bottom: 3.5rem;
    }
    
    @media (max-width: 768px) {
        .schema-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    .schema-item {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .schema-item:hover {
        border-color: #E8A838;
        box-shadow: 0 12px 32px rgba(232, 168, 56, 0.12);
        transform: translateY(-4px);
    }
    
    .schema-item .field-name {
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.625rem;
        font-size: 1.1rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .schema-item .field-type {
        font-size: 0.8rem;
        color: #0F172A;
        margin-bottom: 0.5rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
    }
    
    .schema-item .field-example {
        font-size: 0.85rem;
        color: #1F2937;
        font-style: italic;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       METRICS & DATA - Premium Display
    ───────────────────────────────────────────────────────────────────────────────*/
    
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        padding: 1.75rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    [data-testid="stMetric"]:hover {
        border-color: #E8A838;
        box-shadow: 0 12px 32px rgba(232, 168, 56, 0.12);
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       INPUT & UPLOAD STYLING
    ───────────────────────────────────────────────────────────────────────────────*/
    
    input {
        border-radius: 12px !important;
        border: 1.5px solid #E2E8F0 !important;
        padding: 0.75rem 1rem !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    input:focus {
        border-color: #E8A838 !important;
        box-shadow: 0 0 0 3px rgba(232, 168, 56, 0.1) !important;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       MODEL BADGES - OR-Style
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .badge-mm1 {
        display: inline-block;
        background: #1B2A4A;
        color: #E8A838;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #E8A838;
    }
    .badge-mmc {
        display: inline-block;
        background: #1B2A4A;
        color: #5DADE2;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #5DADE2;
    }
    .badge-mgc {
        display: inline-block;
        background: #1B2A4A;
        color: #A569BD;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #A569BD;
    }
    .badge-mmc-k {
        display: inline-block;
        background: #1B2A4A;
        color: #58D68D;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #58D68D;
    }
    .badge-mgc-k {
        display: inline-block;
        background: #1B2A4A;
        color: #EC7063;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #EC7063;
    }
    .badge-erlang-a {
        display: inline-block;
        background: #1B2A4A;
        color: #F39C12;
        padding: 0.2rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        border: 1px solid #F39C12;
    }

    .model-legend {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       SIDEBAR - Dark Theme Premium
    ───────────────────────────────────────────────────────────────────────────────*/
    
    [data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    
    [data-testid="stSidebar"] * {
        color: #E2E8F0;
        font-family: 'Inter', sans-serif;
    }
    
    [data-testid="stSidebar"] h3 {
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
        font-weight: 800;
    }
    
    [data-testid="stSidebar"] > div:first-child > div > div:nth-child(2) > div > div:nth-child(1) > div > button {
        background: rgba(232, 168, 56, 0.1) !important;
        border: 1px solid #E8A838 !important;
        color: #22D3EE !important;
    }
    
    /* Show sidebar collapse button with icon only, hide tooltip text */
    [data-testid="stSidebar"] button[kind="header"] {
        font-size: 1rem !important;
        padding: 0.5rem !important;
        min-width: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    [data-testid="stSidebar"] button[kind="header"] span {
        display: none !important;
    }
    
    [data-testid="stSidebar"] button[kind="header"] svg {
        font-size: 1.25rem !important;
        display: block !important;
    }
    
    /* Sidebar code block — dark background + amber text */
    [data-testid="stSidebar"] pre {
        background-color: #1B2A4A !important;
        border: 1px solid #2C4A72 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1rem !important;
    }
    [data-testid="stSidebar"] pre code {
        background-color: transparent !important;
        color: #E8A838 !important;
        font-size: 0.75rem !important;
    }
    
    /* Sidebar number inputs — dark background + light text */
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
        background-color: #1B2A4A !important;
        color: #E2E8F0 !important;
        border: 1px solid #2C4A72 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] input:focus {
        border-color: #E8A838 !important;
        box-shadow: 0 0 0 2px rgba(232, 168, 56, 0.2) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] label {
        color: #94A3B8 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] button {
        background-color: #2C4A72 !important;
        color: #E2E8F0 !important;
        border: none !important;
    }
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] button:hover {
        background-color: #3B5A8A !important;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       LOGO STRIP - Horizontal Layout
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .logo-strip {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: center;
        margin-top: 24px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }
    
    .logo-item {
        height: 60px;
        width: auto;
        opacity: 0.8;
        transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.1));
    }
    
    .logo-item:hover {
        opacity: 1;
    }
    
    p {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Poppins', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       UTILITIES
    ───────────────────────────────────────────────────────────────────────────────*/
    
    /* Divider */
    hr {
        border: none;
        border-top: 1px solid #E2E8F0;
        margin: 3.5rem 0;
    }
    
    /* Smooth transitions */
    * {
        scroll-behavior: smooth;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    init_session_state()
    
    # ═════════════════════════════════════════════════════════════════════════
    # HERO SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="hero-section">
        <div class="subtitle">QUEUEING THEORY OPTIMIZER</div>
        <h1>Turn Queue Data into Exact Staffing Decisions</h1>
        <div class="tagline">Stop guessing. Start optimizing.</div>
        <div class="description">
            Upload 4 columns and get precise, data-backed recommendations in minutes.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Logo strip - show only if logos exist
    logo_b64 = get_base64_image("logo/logo1.png")
    if logo_b64:
        st.markdown(f"""
        <div style='display: flex; justify-content: center; margin: 16px 0;'>
            <img src='data:image/png;base64,{logo_b64}' style='max-width: 80px; height: auto; object-fit: contain;'>
        </div>
        """, unsafe_allow_html=True)
    
    # Hero section buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        pass
    with col2:
        if st.button("📥 Upload your CSV", key="hero_upload", use_container_width=True):
            st.switch_page("pages/1_current_metrics.py")
    with col3:
        pass
    
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

        **Simulation:** Discrete-event (SimPy) · Monte Carlo (10K trials)
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
