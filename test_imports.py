#!/usr/bin/env python3
"""Check that runtime and app imports work correctly."""

from __future__ import annotations

import sys
import traceback
from typing import Any

CHECKS = [
    ("streamlit", "import streamlit"),
    ("pandas", "import pandas"),
    ("plotly", "import plotly"),
    ("numpy", "import numpy"),
    ("PIL", "from PIL import Image"),
    ("openpyxl", "import openpyxl"),
    ("simpy", "import simpy"),
    (
        "app_page_utils",
        "from legacy_streamlit.app_page_utils import init_session_state",
    ),
    (
        "data_processing",
        "from legacy_streamlit.data_processing import compute_kpis",
    ),
    ("queue_models", "from backend.queueing_engine.models import mgc, mgck, mm1, mmc, mmck"),
    ("optimization", "from backend.queueing_engine.services.optimization import DEFAULT_MAX_SERVERS"),
]


def main() -> int:
    errors = []
    namespace: dict[str, Any] = {}

    for label, statement in CHECKS:
        try:
            exec(statement, namespace)
            print(f"OK {label}")
        except Exception as exc:
            errors.append(f"FAIL {label}: {exc}")
            traceback.print_exc()

    if errors:
        print(f"\n{len(errors)} import error(s) found:")
        for error in errors:
            print(f"  {error}")
        return 1

    print("\nAll imports successful. App is ready to run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
