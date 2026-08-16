"""Unit tests for backend.reports.report_export (legacy call-pattern compatibility)."""

from __future__ import annotations

import io

import pandas as pd

from backend.reports.report_export import (
    _exec_summary_bullets,
    generate_excel_report,
    generate_pdf_report,
)


def _comparison_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "time": "08:00-09:00",
                "c_current": 2,
                "rho_current": 0.65,
                "Wq_current": 0.15,
                "c_optimal": 3,
                "rho_optimal": 0.43,
                "Wq_optimal": 0.08,
            },
            {
                "time": "09:00-10:00",
                "c_current": 2,
                "rho_current": 0.71,
                "Wq_current": 0.22,
                "c_optimal": 3,
                "rho_optimal": 0.47,
                "Wq_optimal": 0.10,
            },
        ]
    )


def _kpis() -> dict:
    return {
        "avg_waiting_time": 0.15,
        "avg_waiting_optimized": 0.08,
        "avg_utilization": 0.65,
        "avg_utilization_optimized": 0.43,
        "total_savings": 12000,
    }


def test_pdf_report_accepts_legacy_segment_df_keyword() -> None:
    """The legacy comparison page calls with segment_df= — must not raise TypeError."""
    buf = generate_pdf_report(
        current_kpis=_kpis(),
        recommended_kpis=_kpis(),
        comparison_df=_comparison_df(),
        segment_df=_comparison_df(),
        recommendations=["Increase staffing to 3 servers."],
    )
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"%PDF")


def test_excel_report_accepts_legacy_segment_df_keyword() -> None:
    """The legacy comparison page calls with segment_df= — must not raise TypeError."""
    buf = generate_excel_report(
        comparison_df=_comparison_df(),
        segment_df=_comparison_df(),
        recommended_kpis=_kpis(),
    )
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"PK\x03\x04")


def test_pdf_report_api_positional_call_without_segment_df() -> None:
    """The active API route passes arguments positionally and never segment_df."""
    buf = generate_pdf_report(_kpis(), _kpis(), _comparison_df(), ["Add a server."])
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"%PDF")


def test_excel_report_api_positional_call_without_segment_df() -> None:
    """The active API route passes arguments positionally and never segment_df."""
    buf = generate_excel_report(_comparison_df(), _kpis())
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"PK\x03\x04")


def test_exec_summary_bullets_full_pair() -> None:
    bullets = _exec_summary_bullets(_kpis(), _kpis())
    assert bullets == [
        "• Average customer wait: 9.0 min → 4.8 min (optimized)",
        "• Estimated weekly savings: ₱12,000",
        "• Utilization improvement: 65% → 43%",
    ]


def test_exec_summary_bullets_current_only() -> None:
    bullets = _exec_summary_bullets(
        {"avg_waiting_time": 0.15, "avg_utilization": 0.65}, {}
    )
    assert bullets == [
        "• Average customer wait: 9.0 min (current)",
        "• Utilization improvement: 65% (current)",
    ]


def test_exec_summary_bullets_none() -> None:
    bullets = _exec_summary_bullets({}, {})
    assert bullets == [
        "• Average customer wait: N/A",
        "• Utilization improvement: N/A",
    ]
