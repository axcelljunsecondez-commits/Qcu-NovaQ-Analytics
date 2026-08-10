"""
theme.py — Centralized Design System for the Queueing Theory Dashboard.

All CSS, component styles, design tokens, and shared UI components
live here. Each page calls apply_theme() once at startup.
"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

# ─────────────────────────────────────────────────────────────────────
# DESIGN TOKENS
# ─────────────────────────────────────────────────────────────────────

LIGHT_TOKENS = {
    "--bg-page": "#F1F5F9",
    "--bg-card": "#FFFFFF",
    "--bg-sidebar": "#0F172A",
    "--bg-hero": "linear-gradient(135deg, #1B2A4A 0%, #243B5E 50%, #2C4A72 100%)",
    "--bg-input": "#FFFFFF",
    "--bg-code": "#1B2A4A",
    "--text-primary": "#0F172A",
    "--text-secondary": "#64748B",
    "--text-sidebar": "#E2E8F0",
    "--text-sidebar-heading": "#FFFFFF",
    "--text-on-hero": "#FFFFFF",
    "--accent": "#E8A838",
    "--accent-hover": "#D4912F",
    "--accent-light": "rgba(232, 168, 56, 0.1)",
    "--accent-glow": "rgba(232, 168, 56, 0.25)",
    "--border": "#E2E8F0",
    "--border-accent": "#E8A838",
    "--shadow-sm": "0 8px 24px rgba(0, 0, 0, 0.06)",
    "--shadow-md": "0 12px 32px rgba(232, 168, 56, 0.12)",
    "--shadow-lg": "0 24px 48px rgba(27, 42, 74, 0.25)",
    "--radius-sm": "8px",
    "--radius-md": "12px",
    "--radius-lg": "16px",
    "--radius-xl": "20px",
    "--font-sans": "'Inter', sans-serif",
    "--font-display": "'Poppins', sans-serif",
    "--success": "#27AE60",
    "--warning": "#E8A838",
    "--danger": "#C0392B",
    "--info": "#2E86AB",
    "--badge-mmc": "#5DADE2",
    "--badge-mgc": "#A569BD",
    "--badge-mmc-k": "#58D68D",
    "--badge-mgc-k": "#EC7063",
    "--badge-erlang-a": "#F39C12",
}

DARK_TOKENS = {
    "--bg-page": "#0B1120",
    "--bg-card": "#162032",
    "--bg-sidebar": "#070D18",
    "--bg-hero": "linear-gradient(135deg, #0B1120 0%, #162032 50%, #1B2A4A 100%)",
    "--bg-input": "#1B2A4A",
    "--bg-code": "#0F172A",
    "--text-primary": "#E2E8F0",
    "--text-secondary": "#94A3B8",
    "--text-sidebar": "#94A3B8",
    "--text-sidebar-heading": "#F1F5F9",
    "--text-on-hero": "#F1F5F9",
    "--accent": "#F0B84C",
    "--accent-hover": "#E8A838",
    "--accent-light": "rgba(240, 184, 76, 0.12)",
    "--accent-glow": "rgba(240, 184, 76, 0.3)",
    "--border": "#1E2D45",
    "--border-accent": "#F0B84C",
    "--shadow-sm": "0 8px 24px rgba(0, 0, 0, 0.25)",
    "--shadow-md": "0 12px 32px rgba(240, 184, 76, 0.08)",
    "--shadow-lg": "0 24px 48px rgba(0, 0, 0, 0.4)",
    "--radius-sm": "8px",
    "--radius-md": "12px",
    "--radius-lg": "16px",
    "--radius-xl": "20px",
    "--font-sans": "'Inter', sans-serif",
    "--font-display": "'Poppins', sans-serif",
    "--success": "#2ECC71",
    "--warning": "#F0B84C",
    "--danger": "#E74C3C",
    "--info": "#3498DB",
    "--badge-mmc": "#5DADE2",
    "--badge-mgc": "#A569BD",
    "--badge-mmc-k": "#58D68D",
    "--badge-mgc-k": "#EC7063",
    "--badge-erlang-a": "#F39C12",
}


def _build_css(tokens: dict[str, str]) -> str:
    """Build a CSS variable block from token dict."""
    lines = [f"    {k}: {v};" for k, v in tokens.items()]
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def _badge_css() -> str:
    """Badge component styles."""
    return """
.badge-mm1, .badge-mmc, .badge-mgc, .badge-mmc-k, .badge-mgc-k, .badge-erlang-a {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: var(--font-sans);
    border: 1px solid;
}
.badge-mm1 { background: var(--bg-code); color: var(--accent); border-color: var(--accent); }
.badge-mmc { background: var(--bg-code); color: var(--badge-mmc); border-color: var(--badge-mmc); }
.badge-mgc { background: var(--bg-code); color: var(--badge-mgc); border-color: var(--badge-mgc); }
.badge-mmc-k { background: var(--bg-code); color: var(--badge-mmc-k); border-color: var(--badge-mmc-k); }
.badge-mgc-k { background: var(--bg-code); color: var(--badge-mgc-k); border-color: var(--badge-mgc-k); }
.badge-erlang-a { background: var(--bg-code); color: var(--badge-erlang-a); border-color: var(--badge-erlang-a); }
.model-legend { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
"""


# ─────────────────────────────────────────────────────────────────────
# THEME CSS — full design system
# ─────────────────────────────────────────────────────────────────────

def _full_css(dark: bool = False) -> str:
    tokens = DARK_TOKENS if dark else LIGHT_TOKENS
    return f"""
<style>
/* ══════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ══════════════════════════════════════════════════════════════ */
{_build_css(tokens)}

/* ══════════════════════════════════════════════════════════════
   GLOBAL
   ══════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@600;700;800&display=swap');

.main {{ background-color: var(--bg-page); }}
.block-container {{ background-color: var(--bg-page); padding-top: 2rem; }}
* {{ scroll-behavior: smooth; }}
p {{ font-family: var(--font-sans); }}
h1, h2, h3, h4, h5, h6 {{ font-family: var(--font-display); color: var(--text-primary); }}
hr {{ border: none; border-top: 1px solid var(--border); margin: 3.5rem 0; }}

/* ══════════════════════════════════════════════════════════════
   HERO SECTION
   ══════════════════════════════════════════════════════════════ */
.hero-section {{
    background: var(--bg-hero);
    color: var(--text-on-hero);
    padding: 5rem 3rem;
    border-radius: var(--radius-xl);
    text-align: center;
    margin-bottom: 3.5rem;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}}
.hero-section::before {{
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 400px;
    height: 400px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 50%;
    filter: blur(60px);
}}
.hero-section .subtitle {{
    font-size: 0.875rem;
    letter-spacing: 3px;
    color: var(--text-on-hero);
    margin-bottom: 1rem;
    text-transform: uppercase;
    font-weight: 800;
    font-family: var(--font-sans);
}}
.hero-section h1 {{
    margin: 0;
    font-size: 3.5rem;
    font-weight: 900;
    line-height: 1.15;
    margin-bottom: 0.75rem;
    color: var(--text-on-hero);
    font-family: var(--font-display);
    text-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}}
.hero-section .tagline {{
    font-size: 1.875rem;
    font-weight: 500;
    color: var(--text-on-hero);
    margin-bottom: 1.5rem;
    font-family: var(--font-display);
}}
.hero-section .description {{
    font-size: 1.125rem;
    color: var(--text-on-hero);
    max-width: 700px;
    margin: 0 auto 2.5rem;
    line-height: 1.8;
    font-family: var(--font-sans);
    font-weight: 500;
}}

/* ══════════════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════════════ */
div[data-testid="stButtonContainer"] button {{
    font-family: var(--font-sans);
    font-weight: 600;
    padding: 0.875rem 1.75rem !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    border: none !important;
}}
.btn-secondary {{
    padding: 1rem 2.25rem;
    border-radius: 10px;
    font-weight: 700;
    font-size: 1rem;
    text-decoration: none;
    cursor: pointer;
    border: 2px solid var(--accent);
    background: transparent;
    color: var(--accent);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    font-family: var(--font-sans);
}}
.btn-secondary:hover {{
    background: var(--accent-light);
    border-color: var(--accent-hover);
    color: var(--accent-hover);
    box-shadow: 0 8px 20px var(--accent-glow);
}}

/* ══════════════════════════════════════════════════════════════
   CARD COMPONENTS
   ══════════════════════════════════════════════════════════════ */
.info-section {{
    background: var(--bg-card);
    padding: 2.25rem;
    border-radius: var(--radius-lg);
    margin-bottom: 3.5rem;
    border: 1px solid var(--border);
    display: flex;
    gap: 1.75rem;
    align-items: flex-start;
    box-shadow: var(--shadow-sm);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}
.info-section:hover {{
    border-color: var(--border-accent);
    box-shadow: var(--shadow-md);
}}
.info-icon {{ font-size: 2.8rem; flex-shrink: 0; line-height: 1; }}
.info-content h3 {{
    margin-top: 0;
    color: var(--text-primary);
    font-size: 1.3rem;
    font-weight: 700;
    font-family: var(--font-display);
}}
.info-content p {{
    margin: 0.75rem 0 0 0;
    color: var(--text-secondary);
    line-height: 1.8;
    font-size: 1rem;
    font-family: var(--font-sans);
}}

/* ══════════════════════════════════════════════════════════════
   WORKFLOW & SCHEMA GRID
   ══════════════════════════════════════════════════════════════ */
.section-title {{
    font-size: 0.8rem;
    letter-spacing: 2.5px;
    color: var(--text-secondary);
    margin-bottom: 2.25rem;
    font-weight: 800;
    text-transform: uppercase;
    font-family: var(--font-sans);
}}

.workflow-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 2rem;
    margin-bottom: 3.5rem;
}}
.workflow-card {{
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2.25rem;
    background: var(--bg-card);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-sm);
}}
.workflow-card:hover {{
    border-color: var(--border-accent);
    box-shadow: var(--shadow-md);
    transform: translateY(-6px);
}}
.workflow-card .step-number {{
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
    font-family: var(--font-display);
}}
.workflow-card h3 {{
    margin-top: 0;
    font-size: 1.25rem;
    color: var(--text-primary);
    font-weight: 700;
    font-family: var(--font-display);
}}
.workflow-card p {{
    color: var(--text-secondary);
    margin: 0.75rem 0 1.5rem 0;
    line-height: 1.8;
    font-size: 0.95rem;
    font-family: var(--font-sans);
}}
.workflow-card .action-btn {{
    color: var(--accent);
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 0.95rem;
    font-family: var(--font-sans);
}}
.workflow-card .action-btn:hover {{ color: var(--accent-hover); }}

.schema-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.75rem;
    margin-bottom: 3.5rem;
}}
.schema-item {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2rem;
    box-shadow: var(--shadow-sm);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}
.schema-item:hover {{
    border-color: var(--border-accent);
    box-shadow: var(--shadow-md);
    transform: translateY(-4px);
}}
.schema-item .field-name {{
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 0.625rem;
    font-size: 1.1rem;
    font-family: var(--font-display);
}}
.schema-item .field-type {{
    font-size: 0.8rem;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
    font-weight: 600;
    font-family: var(--font-sans);
}}
.schema-item .field-example {{
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-style: italic;
    font-family: var(--font-sans);
}}

/* ══════════════════════════════════════════════════════════════
   METRICS
   ══════════════════════════════════════════════════════════════ */
[data-testid="stMetric"] {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    padding: 1.75rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}
[data-testid="stMetric"]:hover {{
    border-color: var(--border-accent);
    box-shadow: var(--shadow-md);
}}

/* ══════════════════════════════════════════════════════════════
   INPUTS
   ══════════════════════════════════════════════════════════════ */
input {{
    border-radius: var(--radius-md) !important;
    border: 1.5px solid var(--border) !important;
    padding: 0.75rem 1rem !important;
    font-family: var(--font-sans) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    background: var(--bg-input) !important;
    color: var(--text-primary) !important;
}}
input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-light) !important;
}}
div[data-testid="stNumberInput"] input {{ background: var(--bg-input) !important; color: var(--text-primary) !important; }}

/* ══════════════════════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {{ background: var(--bg-sidebar); }}
[data-testid="stSidebar"] * {{ color: var(--text-sidebar); font-family: var(--font-sans); }}
[data-testid="stSidebar"] h3 {{ color: var(--text-sidebar-heading); font-family: var(--font-display); font-weight: 800; }}
[data-testid="stSidebar"] pre {{ background-color: var(--bg-code) !important; border: 1px solid var(--border) !important; border-radius: var(--radius-sm) !important; padding: 0.75rem 1rem !important; }}
[data-testid="stSidebar"] pre code {{ background-color: transparent !important; color: var(--accent) !important; font-size: 0.75rem !important; }}
[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {{ background-color: var(--bg-code) !important; color: var(--text-sidebar) !important; border: 1px solid var(--border) !important; border-radius: var(--radius-sm) !important; }}
[data-testid="stSidebar"] div[data-testid="stNumberInput"] input:focus {{ border-color: var(--accent) !important; box-shadow: 0 0 0 2px var(--accent-light) !important; }}
[data-testid="stSidebar"] div[data-testid="stNumberInput"] label {{ color: var(--text-secondary) !important; }}
[data-testid="stSidebar"] div[data-testid="stNumberInput"] button {{ background-color: var(--border) !important; color: var(--text-sidebar) !important; border: none !important; }}
[data-testid="stSidebar"] div[data-testid="stNumberInput"] button:hover {{ background-color: var(--bg-code) !important; }}

/* ══════════════════════════════════════════════════════════════
   LOGO
   ══════════════════════════════════════════════════════════════ */
.logo-strip {{ display: flex; gap: 28px; justify-content: center; align-items: center; margin: 24px 0; flex-wrap: wrap; }}
.logo-item {{ height: 60px; width: auto; opacity: 0.8; transition: opacity 0.3s; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.1)); }}
.logo-item:hover {{ opacity: 1; }}

/* ══════════════════════════════════════════════════════════════
   BADGES
   ══════════════════════════════════════════════════════════════ */
{_badge_css()}

/* ══════════════════════════════════════════════════════════════
   BREADCRUMB
   ══════════════════════════════════════════════════════════════ */
.breadcrumb-container {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--bg-card);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    box-shadow: var(--shadow-sm);
}}
.breadcrumb-step {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
    font-weight: 600;
    font-family: var(--font-sans);
    color: var(--text-secondary);
    text-decoration: none;
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    transition: all 0.2s;
}}
.breadcrumb-step:hover {{ background: var(--accent-light); color: var(--accent); }}
.breadcrumb-step.active {{ color: var(--accent); background: var(--accent-light); }}
.breadcrumb-step.done {{ color: var(--success); }}
.breadcrumb-step .step-icon {{ font-size: 1rem; }}
.breadcrumb-sep {{ color: var(--border); font-size: 0.8rem; }}

/* ══════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
   ══════════════════════════════════════════════════════════════ */
@keyframes toast-in {{
    0% {{ transform: translateX(100%); opacity: 0; }}
    100% {{ transform: translateX(0); opacity: 1; }}
}}
@keyframes toast-out {{
    0% {{ transform: translateX(0); opacity: 1; }}
    100% {{ transform: translateX(100%); opacity: 0; }}
}}
.toast-container {{
    position: fixed;
    top: 1rem;
    right: 1rem;
    z-index: 999999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 400px;
}}
.toast {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.875rem 1.25rem;
    border-radius: var(--radius-md);
    background: var(--bg-card);
    border: 1px solid var(--border);
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    animation: toast-in 0.35s cubic-bezier(0.4,0,0.2,1);
    font-family: var(--font-sans);
    font-size: 0.9rem;
    color: var(--text-primary);
}}
.toast-success {{ border-left: 4px solid var(--success); }}
.toast-error {{ border-left: 4px solid var(--danger); }}
.toast-warning {{ border-left: 4px solid var(--warning); }}
.toast-info {{ border-left: 4px solid var(--info); }}
.toast-icon {{ font-size: 1.25rem; flex-shrink: 0; }}

/* ══════════════════════════════════════════════════════════════
   SKELETON LOADERS
   ══════════════════════════════════════════════════════════════ */
@keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}
.skeleton {{
    background: linear-gradient(90deg, var(--border) 25%, rgba(255,255,255,0.08) 50%, var(--border) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
    border-radius: var(--radius-sm);
}}
.skeleton-card {{
    height: 120px;
    margin-bottom: 1rem;
}}
.skeleton-metric {{
    height: 100px;
    border-radius: var(--radius-lg);
}}

/* ══════════════════════════════════════════════════════════════
   ANIMATED KPI
   ══════════════════════════════════════════════════════════════ */
@keyframes countUp {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
.kpi-animated {{
    animation: countUp 0.6s cubic-bezier(0.4,0,0.2,1) forwards;
}}

/* ══════════════════════════════════════════════════════════════
   ONBOARDING TOOLTIP
   ══════════════════════════════════════════════════════════════ */
.onboarding-tooltip {{
    position: absolute;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    padding: 1.25rem;
    max-width: 340px;
    z-index: 100000;
    font-family: var(--font-sans);
}}

/* ══════════════════════════════════════════════════════════════
   DATA TABLE FILTER
   ══════════════════════════════════════════════════════════════ */
.filter-bar {{
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.75rem 1rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    margin-bottom: 1rem;
}}
.filter-bar input {{
    min-width: 180px;
}}

/* ══════════════════════════════════════════════════════════════
   RESPONSIVE — Mobile First
   ══════════════════════════════════════════════════════════════ */
@media (max-width: 1200px) {{
    .schema-grid {{ grid-template-columns: repeat(3, 1fr); }}
}}
@media (max-width: 992px) {{
    .schema-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .workflow-grid {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 768px) {{
    .schema-grid {{ grid-template-columns: 1fr; }}
    .hero-section {{ padding: 3rem 1.5rem; }}
    .hero-section h1 {{ font-size: 2.2rem; }}
    .hero-section .tagline {{ font-size: 1.3rem; }}
    .hero-section .description {{ font-size: 1rem; }}
    .info-section {{ flex-direction: column; }}
    .breadcrumb-container {{ flex-direction: column; align-items: flex-start; }}
}}
@media (max-width: 480px) {{
    .hero-section {{ padding: 2rem 1rem; }}
    .hero-section h1 {{ font-size: 1.6rem; }}
    .hero-section .tagline {{ font-size: 1rem; }}
    .toast-container {{ max-width: 300px; right: 0.5rem; }}
}}
</style>"""


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def init_theme() -> None:
    """Initialize theme session state."""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False
    if "onboarding_done" not in st.session_state:
        st.session_state["onboarding_done"] = False


def is_dark() -> bool:
    """Return True if dark mode is active."""
    return st.session_state.get("dark_mode", False)


def toggle_theme() -> None:
    """Flip dark/light mode."""
    st.session_state["dark_mode"] = not st.session_state["dark_mode"]
    st.rerun()


def apply_theme() -> None:
    """Apply the full design system CSS. Call once per page at startup."""
    init_theme()
    dark = is_dark()
    st.markdown(_full_css(dark=dark), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# COMPONENT HELPERS
# ─────────────────────────────────────────────────────────────────────

def breadcrumb(current_page: int) -> None:
    """Render a breadcrumb pipeline showing workflow progress.

    Pages: 1=Current Metrics, 2=Optimization, 3=Simulation, 4=Comparison
    """
    steps = [
        (1, "1️⃣", "Data"),
        (2, "2️⃣", "Optimize"),
        (3, "3️⃣", "Simulate"),
        (4, "4️⃣", "Compare"),
    ]
    links = {
        1: "1_current_metrics",
        2: "2_optimization",
        3: "3_simulation",
        4: "4_comparison",
    }
    parts = []
    page_keys = {
        1: "current_data",
        2: "recommended_data",
        3: "simulation_results",
        4: "comparison_data",
    }
    for num, icon, label in steps:
        if num == current_page:
            parts.append(f'<span class="breadcrumb-step active"><span class="step-icon">{icon}</span>{label}</span>')
        else:
            key = page_keys.get(num)
            if key is not None and st.session_state.get(key) is not None:
                parts.append(
                    f'<a href="/{links[num]}" target="_self" class="breadcrumb-step done">'
                    f'<span class="step-icon">✅</span>{label}</a>'
                )
            else:
                parts.append(f'<span class="breadcrumb-step"><span class="step-icon">{icon}</span>{label}</span>')
        if num < 4:
            parts.append('<span class="breadcrumb-sep">›</span>')

    st.markdown(
        f'<div class="breadcrumb-container">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def toast(message: str, type: str = "success") -> None:
    """Render a toast notification via st.markdown.

    Types: success, error, warning, info
    """
    icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
    icon = icons.get(type, "ℹ️")
    st.markdown(
        f'<div class="toast-container">'
        f'<div class="toast toast-{type}"><span class="toast-icon">{icon}</span>{html.escape(message)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def skeleton_card(count: int = 1) -> None:
    """Render shimmer skeleton loading cards."""
    html = "".join('<div class="skeleton skeleton-card"></div>' for _ in range(count))
    st.markdown(html, unsafe_allow_html=True)


def skeleton_metric(count: int = 4) -> None:
    """Render shimmer skeleton metric tiles."""
    cols = st.columns(count)
    for col in cols:
        col.markdown('<div class="skeleton skeleton-metric"></div>', unsafe_allow_html=True)


def theme_toggle_button() -> None:
    """Render a dark/light theme toggle in the sidebar."""
    dark = is_dark()
    icon = "🌙" if not dark else "☀️"
    label = "Dark Mode" if not dark else "Light Mode"
    if st.sidebar.button(f"{icon} {label}", use_container_width=True):
        toggle_theme()


def onboarding_tour() -> None:
    """Render a guided onboarding tooltip for first-time users."""
    if st.session_state.get("onboarding_done"):
        return
    steps = [
        ("👋 Welcome!", "This dashboard helps you optimize staffing using queueing theory. "
         "Upload data, get recommendations, simulate, and compare scenarios."),
        ("📥 Step 1", "Upload your CSV or POS data on the Current Metrics page. "
         "The system validates your schema and computes KPIs."),
        ("⚙️ Step 2", "Visit Optimization to find the ideal staffing level for each time segment."),
        ("🕹️ Step 3", "Run DES or Monte Carlo simulations to validate your plan."),
        ("📊 Step 4", "Compare current vs. optimized scenarios side-by-side on the Comparison page."),
    ]
    idx = st.session_state.get("onboarding_step", 0)
    if idx >= len(steps):
        st.session_state["onboarding_done"] = True
        st.session_state["onboarding_step"] = 0
        st.rerun()
        return

    title, body = steps[idx]
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"**{title}**  \n{body}")
    if c2.button("Next →" if idx < len(steps) - 1 else "Done", key=f"onboard_{idx}"):
        st.session_state["onboarding_step"] = idx + 1
        st.rerun()


# ─────────────────────────────────────────────────────────────────────
# THEME-SPECIFIC OVERRIDES (for Streamlit's native dark mode)
# ─────────────────────────────────────────────────────────────────────

def _st_dark_mode_css() -> str:
    """HACK: Force Streamlit native elements to respect our theme."""
    if not is_dark():
        return ""
    return """
<style>
.stApp { background-color: #0B1120; }
.stApp header { background-color: #070D18 !important; }
.st-emotion-cache-1avcm0n { background: #0B1120; }
.st-emotion-cache-1r4qj8v { background: #162032; }
div[data-testid="stDataFrame"] { background: #162032; border-color: #1E2D45; }
div[data-testid="stExpander"] { background: #162032; border-color: #1E2D45; }
div[data-testid="stTable"] { color: #E2E8F0; }
.stTabs [data-baseweb="tab-list"] { background: #162032; }
.stTabs [data-baseweb="tab"] { color: #94A3B8; }
</style>"""


def apply_dark_overrides() -> None:
    """Apply additional dark-mode overrides for Streamlit internals."""
    st.markdown(_st_dark_mode_css(), unsafe_allow_html=True)
