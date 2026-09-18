"""Upload parsing, validation, and sanitization (data layer).

Never writes uploads to disk: payloads are parsed strictly from bytes with
extension allowlists, magic-byte checks, size caps, and formula-injection
sanitization before any data enters the pipeline.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

ALLOWED_EXTENSIONS = (".csv", ".xlsx")
FORMULA_PREFIXES = ("=", "+", "@", "-", "\t", "\r")
DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_XLSX_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_XLSX_MAX_ZIP_MEMBERS = 1000
DEFAULT_XLSX_MAX_COMPRESSION_RATIO = 100.0
DEFAULT_XLSX_MAX_WORKSHEETS = 20
DEFAULT_UPLOAD_MAX_ROWS = 100000
DEFAULT_UPLOAD_MAX_COLUMNS = 100
DEFAULT_UPLOAD_MAX_CELL_CHARS = 32768
DEFAULT_UPLOAD_MAX_DATAFRAME_BYTES = 100 * 1024 * 1024

_XLSX_MAGIC = b"PK\x03\x04"
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")


class UploadError(ValueError):
    """Raised when an upload fails parsing, validation, or size checks."""


def safe_stem(filename: str) -> str:
    """Return the basename with any directory components and control chars removed."""
    decoded = unquote(str(filename))
    basename = Path(decoded.replace("\\", "/")).name
    cleaned = _CONTROL_CHARS.sub(" ", basename).strip()
    return cleaned or "upload"


def parse_upload(
    filename: str,
    data: bytes,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    *,
    xlsx_max_uncompressed_bytes: int = DEFAULT_XLSX_MAX_UNCOMPRESSED_BYTES,
    xlsx_max_zip_members: int = DEFAULT_XLSX_MAX_ZIP_MEMBERS,
    xlsx_max_compression_ratio: float = DEFAULT_XLSX_MAX_COMPRESSION_RATIO,
    xlsx_max_worksheets: int = DEFAULT_XLSX_MAX_WORKSHEETS,
    max_rows: int = DEFAULT_UPLOAD_MAX_ROWS,
    max_columns: int = DEFAULT_UPLOAD_MAX_COLUMNS,
    max_cell_chars: int = DEFAULT_UPLOAD_MAX_CELL_CHARS,
    max_dataframe_bytes: int = DEFAULT_UPLOAD_MAX_DATAFRAME_BYTES,
) -> pd.DataFrame:
    """Parse CSV/Excel bytes into a DataFrame, enforcing size and magic checks."""
    name = filename.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise UploadError("Upload must be a CSV or XLSX file.")

    if len(data) > max_bytes:
        raise UploadError(f"File too large: limit is {max_bytes} bytes.")

    if name.endswith(".csv"):
        if b"\x00" in data:
            raise UploadError("Uploaded file is not a valid CSV.")
        buffer = io.BytesIO(data)
        try:
            frame = pd.read_csv(buffer, keep_default_na=False)
        except Exception as exc:
            raise UploadError("Could not parse the CSV file.") from exc
        return _validate_frame(frame, max_rows, max_columns, max_cell_chars, max_dataframe_bytes)

    if not data.startswith(_XLSX_MAGIC):
        raise UploadError("Uploaded file is not a valid Excel workbook.")

    _validate_xlsx_archive(
        data,
        max_uncompressed_bytes=xlsx_max_uncompressed_bytes,
        max_members=xlsx_max_zip_members,
        max_compression_ratio=xlsx_max_compression_ratio,
        max_worksheets=xlsx_max_worksheets,
    )

    buffer = io.BytesIO(data)
    try:
        frame = pd.read_excel(buffer, keep_default_na=False, engine="openpyxl")
    except Exception as exc:
        raise UploadError("Could not parse the XLSX file.") from exc
    return _validate_frame(frame, max_rows, max_columns, max_cell_chars, max_dataframe_bytes)


SETUP_SHEETS = ("events", "staff", "breaks")


def parse_upload_workbook(
    filename: str,
    data: bytes,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    *,
    xlsx_max_uncompressed_bytes: int = DEFAULT_XLSX_MAX_UNCOMPRESSED_BYTES,
    xlsx_max_zip_members: int = DEFAULT_XLSX_MAX_ZIP_MEMBERS,
    xlsx_max_compression_ratio: float = DEFAULT_XLSX_MAX_COMPRESSION_RATIO,
    xlsx_max_worksheets: int = DEFAULT_XLSX_MAX_WORKSHEETS,
    max_rows: int = DEFAULT_UPLOAD_MAX_ROWS,
    max_columns: int = DEFAULT_UPLOAD_MAX_COLUMNS,
    max_cell_chars: int = DEFAULT_UPLOAD_MAX_CELL_CHARS,
    max_dataframe_bytes: int = DEFAULT_UPLOAD_MAX_DATAFRAME_BYTES,
) -> dict[str, pd.DataFrame | None] | None:
    """Read the ``events``/``staff``/``breaks`` sheets of a setup workbook.

    Returns None for CSV files and for workbooks without an ``events`` sheet
    (legacy mode: callers use ``parse_upload``). Sheet names match
    case-insensitively after trimming. The archive checks run once; the row,
    column, cell, and memory limits run on every sheet read. A ``staff`` or
    ``breaks`` sheet that is missing or has no data rows is returned as None.
    """
    name = filename.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise UploadError("Upload must be a CSV or XLSX file.")
    if len(data) > max_bytes:
        raise UploadError(f"File too large: limit is {max_bytes} bytes.")
    if name.endswith(".csv"):
        return None
    if not data.startswith(_XLSX_MAGIC):
        raise UploadError("Uploaded file is not a valid Excel workbook.")
    _validate_xlsx_archive(
        data,
        max_uncompressed_bytes=xlsx_max_uncompressed_bytes,
        max_members=xlsx_max_zip_members,
        max_compression_ratio=xlsx_max_compression_ratio,
        max_worksheets=xlsx_max_worksheets,
    )
    try:
        workbook = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        sheet_names = list(workbook.sheet_names)
    except Exception as exc:
        raise UploadError("Could not parse the XLSX file.") from exc
    found: dict[str, str] = {}
    for sheet_name in sheet_names:
        key = str(sheet_name).strip().lower()
        if key in SETUP_SHEETS:
            if key in found:
                raise UploadError(f"The workbook has more than one sheet named {key}.")
            found[key] = str(sheet_name)
    if "events" not in found:
        return None
    sheets: dict[str, pd.DataFrame | None] = {}
    for key in SETUP_SHEETS:
        if key not in found:
            sheets[key] = None
            continue
        try:
            frame = pd.read_excel(workbook, sheet_name=found[key], keep_default_na=False)
        except Exception as exc:
            raise UploadError("Could not parse the XLSX file.") from exc
        frame = _validate_frame(frame, max_rows, max_columns, max_cell_chars, max_dataframe_bytes)
        sheets[key] = None if key != "events" and frame.empty else frame
    return sheets


def _validate_xlsx_archive(
    data: bytes,
    *,
    max_uncompressed_bytes: int,
    max_members: int,
    max_compression_ratio: float,
    max_worksheets: int,
) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise UploadError("Uploaded file is not a valid XLSX workbook.")
            if len(members) > max_members:
                raise UploadError("XLSX workbook contains too many ZIP entries.")
            total_uncompressed = sum(member.file_size for member in members)
            if total_uncompressed > max_uncompressed_bytes:
                raise UploadError("XLSX workbook expands beyond the allowed size.")
            for member in members:
                if member.flag_bits & 0x1:
                    raise UploadError("Encrypted XLSX workbooks are not supported.")
                if member.file_size and member.compress_size == 0:
                    raise UploadError("XLSX workbook has an unsafe compression ratio.")
                if member.compress_size and member.file_size / member.compress_size > max_compression_ratio:
                    raise UploadError("XLSX workbook has an unsafe compression ratio.")
            worksheets = [name for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml")]
            if len(worksheets) > max_worksheets:
                raise UploadError("XLSX workbook contains too many worksheets.")
    except UploadError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise UploadError("Uploaded file is not a valid XLSX workbook.") from exc


def _validate_frame(
    frame: pd.DataFrame,
    max_rows: int,
    max_columns: int,
    max_cell_chars: int,
    max_dataframe_bytes: int,
) -> pd.DataFrame:
    rows, columns = frame.shape
    if rows > max_rows:
        raise UploadError("Uploaded dataset contains too many rows.")
    if columns > max_columns:
        raise UploadError("Uploaded dataset contains too many columns.")
    if int(frame.memory_usage(index=True, deep=True).sum()) > max_dataframe_bytes:
        raise UploadError("Uploaded dataset uses too much parsed memory.")
    for column in frame.columns:
        if len(str(column)) > max_cell_chars:
            raise UploadError("Uploaded dataset contains text that is too long.")
        series = frame[column]
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
            if series.map(lambda value: len(value) if isinstance(value, str) else 0).gt(max_cell_chars).any():
                raise UploadError("Uploaded dataset contains text that is too long.")
    return frame


def sanitize_workbook(df: pd.DataFrame) -> pd.DataFrame:
    """Prefix formula-injection payloads so spreadsheet apps treat them as text."""
    out = df.copy()
    for column in out.columns:
        if pd.api.types.is_string_dtype(out[column].dtype):
            out[column] = out[column].apply(_sanitize_cell)
    return out


def _sanitize_cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


__all__ = [
    "ALLOWED_EXTENSIONS",
    "DEFAULT_MAX_UPLOAD_BYTES",
    "UploadError",
    "parse_upload",
    "parse_upload_workbook",
    "safe_stem",
    "sanitize_workbook",
]
