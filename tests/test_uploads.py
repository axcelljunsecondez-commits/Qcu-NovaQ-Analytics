"""Upload parsing and sanitization coverage (data layer)."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from backend.data.uploads import UploadError, parse_upload, safe_stem, sanitize_workbook

CSV_BYTES = b"time,lambda,mu,c\n08:00-09:00,30,12,3\n09:00-10:00,45,12,4\n"


def make_xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(
        {"time": ["08:00-09:00"], "lambda": [30.0], "mu": [12.0], "c": [3]}
    ).to_excel(buffer, index=False)
    return buffer.getvalue()


def test_parse_csv_succeeds():
    df = parse_upload("segments.csv", CSV_BYTES)
    assert list(df.columns) == ["time", "lambda", "mu", "c"]
    assert len(df) == 2


def test_parse_xlsx_succeeds():
    df = parse_upload("segments.xlsx", make_xlsx_bytes())
    assert len(df) == 1
    assert float(df.iloc[0]["lambda"]) == 30.0


def test_parse_rejects_unsupported_extension():
    with pytest.raises(UploadError):
        parse_upload("segments.txt", b"hello")


def test_parse_rejects_binary_garbage_as_csv():
    with pytest.raises(UploadError):
        parse_upload("segments.csv", b"\x00\x01\x02\x03\x00binary")


def test_parse_rejects_garbage_as_xlsx():
    with pytest.raises(UploadError):
        parse_upload("segments.xlsx", b"this is not a zip file at all")


def test_parse_rejects_oversized_payload():
    with pytest.raises(UploadError):
        parse_upload("segments.csv", CSV_BYTES, max_bytes=10)


def test_sanitize_formula_injection():
    df = pd.DataFrame(
        {"time": ["=SUM(A1:A9)", "+cmd", "-alert", "@host", "\t=1"], "lambda": [30.0] * 5}
    )
    out = sanitize_workbook(df)
    for value in out["time"]:
        assert str(value).startswith("'")
        assert str(value)[1:] != ""


def test_sanitize_keeps_normal_values():
    df = pd.DataFrame({"time": ["08:00-09:00", "lunch"], "lambda": [30.0, 45.0]})
    out = sanitize_workbook(df)
    assert out["time"].tolist() == ["08:00-09:00", "lunch"]
    assert out["lambda"].tolist() == [30.0, 45.0]


def test_sanitize_keeps_numbers():
    df = pd.DataFrame({"lambda": [30.0, -5.0, 0.5]})
    out = sanitize_workbook(df)
    assert out["lambda"].tolist() == [30.0, -5.0, 0.5]


def test_safe_stem_strips_paths():
    assert safe_stem("..\\..\\evil.csv") == "evil.csv"
    assert safe_stem("../../evil2.csv") == "evil2.csv"
    assert safe_stem("normal.csv") == "normal.csv"
