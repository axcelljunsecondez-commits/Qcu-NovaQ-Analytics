"""Upload parsing and sanitization coverage (data layer)."""

from __future__ import annotations

import io
import zipfile

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


def test_parse_rejects_unavailable_legacy_xls_format():
    with pytest.raises(UploadError, match="CSV or XLSX"):
        parse_upload("segments.xls", b"legacy")


def test_parse_rejects_binary_garbage_as_csv():
    with pytest.raises(UploadError):
        parse_upload("segments.csv", b"\x00\x01\x02\x03\x00binary")


def test_parse_rejects_garbage_as_xlsx():
    with pytest.raises(UploadError):
        parse_upload("segments.xlsx", b"this is not a zip file at all")


def test_parse_rejects_oversized_payload():
    with pytest.raises(UploadError):
        parse_upload("segments.csv", CSV_BYTES, max_bytes=10)


def test_parse_rejects_row_column_cell_and_dataframe_bounds():
    with pytest.raises(UploadError, match="too many rows"):
        parse_upload("segments.csv", CSV_BYTES, max_rows=1)
    with pytest.raises(UploadError, match="too many columns"):
        parse_upload("segments.csv", CSV_BYTES, max_columns=3)
    with pytest.raises(UploadError, match="text that is too long"):
        parse_upload("segments.csv", b"time,lambda,mu,c\nvery-long,1,2,1\n", max_cell_chars=4)
    with pytest.raises(UploadError, match="parsed memory"):
        parse_upload("segments.csv", CSV_BYTES, max_dataframe_bytes=32)


def test_parse_rejects_xlsx_zip_bomb_ratio_and_member_count():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("xl/workbook.xml", "workbook")
        archive.writestr("xl/worksheets/sheet1.xml", "A" * 10000)
    with pytest.raises(UploadError, match="compression ratio"):
        parse_upload("bomb.xlsx", buffer.getvalue(), xlsx_max_compression_ratio=2)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("xl/workbook.xml", "workbook")
        for index in range(10):
            archive.writestr(f"extra-{index}", "x")
    with pytest.raises(UploadError, match="too many ZIP entries"):
        parse_upload("many.xlsx", buffer.getvalue(), xlsx_max_zip_members=10)


def test_parser_error_is_sanitized():
    with pytest.raises(UploadError) as caught:
        parse_upload("bad.csv", b'"unterminated')
    assert "tokenizing" not in str(caught.value).lower()


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
