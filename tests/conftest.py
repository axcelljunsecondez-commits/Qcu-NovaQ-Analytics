"""Test-session bootstrap.

Makes the repository root (for ``backend.*`` packages) and the legacy
Streamlit app directory importable regardless of how pytest is invoked.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

for _path in (str(_ROOT), str(_ROOT / "legacy_streamlit")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("LOG_LEVEL", "WARNING")
