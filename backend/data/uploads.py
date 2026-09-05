"""Upload parsing, validation, and sanitization (data layer).

Never writes uploads to disk: payloads are parsed strictly from bytes with
extension allowlists, magic-byte checks, size caps, and formula-injection
sanitization before any data enters the pipeline.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")
FORMULA_PREFIXES = ("=", "+", "@", "-", "\t", "\r")
DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

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


def parse_upload(filename: str, data: bytes, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> pd.DataFrame:
    """Parse CSV/Excel bytes into a DataFrame, enforcing size and magic checks."""
    name = filename.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise UploadError("Upload must be a CSV or Excel file.")

    if len(data) > max_bytes:
        raise UploadError(f"File too large: limit is {max_bytes} bytes.")

    if name.endswith(".csv"):
        if b"\x00" in data:
            raise UploadError("Uploaded file is not a valid CSV.")
        buffer = io.BytesIO(data)
        try:
            return pd.read_csv(buffer)
        except Exception as exc:
            raise UploadError(f"Could not parse CSV: {exc}") from exc

    if name.endswith(".xlsx") and not data.startswith(_XLSX_MAGIC):
        raise UploadError("Uploaded file is not a valid Excel workbook.")

    buffer = io.BytesIO(data)
    try:
        return pd.read_excel(buffer)
    except Exception as exc:
        raise UploadError(f"Could not parse Excel file: {exc}") from exc


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
    "safe_stem",
    "sanitize_workbook",
]
