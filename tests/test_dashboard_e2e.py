"""E2E smoke tests for the Streamlit dashboard pages."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from backend.data.ingestion import sample_segments

BASE_DIR = Path(__file__).resolve().parent.parent

PAGE_CHECKS: dict[str, tuple[str, ...] | int] = {
    "legacy_streamlit/streamlit_app.py": 7,  # 4 workflow + 1 upload + 1 onboarding + 1 theme toggle
    "legacy_streamlit/pages/1_current_metrics.py": ("Current Metrics",),
    "legacy_streamlit/pages/2_optimization.py": ("Optimization",),
    "legacy_streamlit/pages/3_simulation.py": ("Simulation",),
    "legacy_streamlit/pages/4_comparison.py": ("Comparison",),
}


@pytest.mark.parametrize("script,check", list(PAGE_CHECKS.items()))
def test_page_loads_without_exception(script: str, check: tuple[str, ...] | int) -> None:
    """Each dashboard page must render without uncaught exceptions."""
    at = AppTest(str(BASE_DIR / script), default_timeout=15)
    at.run()

    assert not at.exception, f"{script} raised: {at.exception}"

    if isinstance(check, int):
        # Main landing page: check for expected number of buttons
        assert len(at.button) == check, (
            f"Expected {check} buttons on landing page, got {len(at.button)}"
        )
    else:
        # Sub-pages: check for expected heading text
        visible_texts = []
        for t in at.title:
            visible_texts.append(t.value)
        for h in at.header:
            visible_texts.append(h.value)
        for sh in at.subheader:
            visible_texts.append(sh.value)

        combined = " ".join(visible_texts).lower()
        for expected in check:
            assert expected.lower() in combined, (
                f"Expected {expected!r} in page text, got: {combined[:200]}"
            )


def test_page1_sample_data_loads_metrics() -> None:
    """Clicking 'Load Sample Data' on the Current Metrics page renders KPI metrics."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/1_current_metrics.py"), default_timeout=15)
    at.run()

    assert at.button, "Expected at least one button"
    assert any("Load Sample Data" in b.label for b in at.button), (
        f"Expected 'Load Sample Data' button, got: {[b.label for b in at.button]}"
    )

    at.button[0].click().run()

    assert not at.exception, f"Exception after clicking sample data: {at.exception}"
    assert at.metric, "Expected metrics after loading sample data"

    metric_labels = [m.label for m in at.metric]
    assert any("Utilization" in lbl for lbl in metric_labels), (
        f"Expected a utilization metric, got: {metric_labels}"
    )


@pytest.mark.parametrize("script,expected_heading", [
    ("legacy_streamlit/pages/2_optimization.py", "Optimization"),
    ("legacy_streamlit/pages/3_simulation.py", "Simulation"),
    ("legacy_streamlit/pages/4_comparison.py", "Comparison"),
])
def test_upstream_pages_show_blocked_message(script: str, expected_heading: str) -> None:
    """Pages 2-4 should show a user-facing error when upstream data is missing."""
    at = AppTest(str(BASE_DIR / script), default_timeout=10)
    at.run()

    assert not at.exception, f"{script} raised: {at.exception}"
    assert at.error, f"Expected at least one st.error() on {script} when data is missing"

    error_texts = " ".join(e.value for e in at.error)
    assert "data" in error_texts.lower() or "page" in error_texts.lower(), (
        f"Expected a 'data required' error on {script}, got: {error_texts[:200]}"
    )


def test_page1_pos_radio_uses_stable_values_in_english() -> None:
    """Selecting the POS radio option must reach the POS-import path."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/1_current_metrics.py"), default_timeout=15)
    at.run()

    assert not at.exception, f"Page 1 raised: {at.exception}"
    assert at.radio, "Expected a radio for data source selection"

    at.radio[0].set_value("pos").run()

    assert not at.exception, f"Page 1 raised after POS selection: {at.exception}"
    assert any("POS transaction" in u.label for u in at.file_uploader), (
        f"Expected the raw POS CSV uploader, got: {[u.label for u in at.file_uploader]}"
    )


def test_page1_pos_radio_works_in_filipino() -> None:
    """The POS radio must work in the tl locale (translated label, stable value)."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/1_current_metrics.py"), default_timeout=15)
    at.session_state["locale"] = "tl"
    at.run()

    assert not at.exception, f"Page 1 (tl) raised: {at.exception}"
    assert any("POS transaction" in opt for r in at.radio for opt in r.options), (
        f"Expected translated POS label in tl, got: {[r.options for r in at.radio]}"
    )

    at.radio[0].set_value("pos").run()

    assert not at.exception, f"Page 1 (tl) raised after POS selection: {at.exception}"
    assert any("POS transaction" in u.label for u in at.file_uploader), (
        f"Expected the raw POS CSV uploader in tl, got: {[u.label for u in at.file_uploader]}"
    )


def test_page2_no_false_validation_success_before_running() -> None:
    """Page 2 must not claim validation passed before the user runs it."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/2_optimization.py"), default_timeout=15)
    at.session_state["df"] = sample_segments()
    at.run()

    assert not at.exception, f"Page 2 raised: {at.exception}"
    markdown_texts = " ".join(m.value for m in at.markdown)
    assert "Plan passed" not in markdown_texts, (
        "False validation-success toast shown before validation was ever run"
    )
    assert at.info, "Expected a prompt to run DES + MC validation"


def test_page2_stale_validation_is_invalidated_when_settings_change() -> None:
    """Validation results computed for old settings must be dropped."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/2_optimization.py"), default_timeout=15)
    at.session_state["df"] = sample_segments()
    at.session_state["validated_comparison"] = pd.DataFrame(
        {"sim_status": ["NORMAL"], "mc_failure_rate": [0.0]}
    )
    at.session_state["validation_signature"] = "stale"
    at.run()

    assert not at.exception, f"Page 2 raised: {at.exception}"
    assert "validated_comparison" not in at.session_state, (
        "Stale validation results were not invalidated"
    )


def test_page3_invalid_seed_does_not_crash() -> None:
    """A non-numeric random seed must not crash the simulation page."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/3_simulation.py"), default_timeout=15)
    at.session_state["df"] = sample_segments()
    at.run()
    at.radio[0].set_value("Current input").run()

    assert not at.exception, f"Page 3 raised: {at.exception}"
    at.text_input[0].set_value("abc").run()

    assert not at.exception, f"Page 3 raised on invalid seed: {at.exception}"


def test_page3_error_rows_do_not_break_queue_bars() -> None:
    """Segments without a simulated rho must be skipped, not rendered as NaN bars."""
    at = AppTest(str(BASE_DIR / "legacy_streamlit/pages/3_simulation.py"), default_timeout=15)
    at.session_state["df"] = sample_segments()
    at.session_state["simulation_results"] = pd.DataFrame(
        [
            {
                "time": "08:00-09:00",
                "rho_sim": 0.5,
                "Lq_sim": 1.0,
                "max_queue": 3,
                "served": 10,
                "dropped": 0,
                "status": "NORMAL",
                "Wq_sim": 0.1,
            },
            {
                "time": "09:00-10:00",
                "rho_sim": None,
                "Lq_sim": None,
                "max_queue": 0,
                "served": 0,
                "dropped": 0,
                "status": "ERROR",
                "Wq_sim": None,
            },
        ]
    )
    at.run()
    at.radio[0].set_value("Current input").run()

    assert not at.exception, f"Page 3 raised on error rows: {at.exception}"
    markdown_texts = " ".join(m.value for m in at.markdown).lower()
    assert "nan%" not in markdown_texts, "Queue bars rendered NaN percentage"
