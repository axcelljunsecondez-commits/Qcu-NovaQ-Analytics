"""E2E smoke tests for the Streamlit dashboard pages."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

BASE_DIR = Path(__file__).resolve().parent.parent

PAGE_CHECKS: dict[str, tuple[str, ...] | int] = {
    "streamlit_app.py": 5,  # number of navigation buttons expected
    "pages/1_current_metrics.py": ("Current Metrics",),
    "pages/2_optimization.py": ("Optimization",),
    "pages/3_simulation.py": ("Simulation",),
    "pages/4_comparison.py": ("Comparison",),
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
        for el in at.title:
            visible_texts.append(el.value)
        for el in at.header:
            visible_texts.append(el.value)
        for el in at.subheader:
            visible_texts.append(el.value)

        combined = " ".join(visible_texts).lower()
        for expected in check:
            assert expected.lower() in combined, (
                f"Expected {expected!r} in page text, got: {combined[:200]}"
            )


def test_page1_sample_data_loads_metrics() -> None:
    """Clicking 'Load Sample Data' on the Current Metrics page renders KPI metrics."""
    at = AppTest(str(BASE_DIR / "pages/1_current_metrics.py"), default_timeout=15)
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
    ("pages/2_optimization.py", "Optimization"),
    ("pages/3_simulation.py", "Simulation"),
    ("pages/4_comparison.py", "Comparison"),
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
