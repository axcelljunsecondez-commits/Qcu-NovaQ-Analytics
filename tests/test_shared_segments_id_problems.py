"""K-UF-2: the duplicate-id check counts in one pass and says exactly what it said before.

Data: SYNTHETIC ids and rates (made for the test).
"""

from __future__ import annotations

import random
import time

import pandas as pd
import pytest

from backend.api.analysis_schemas import QueueSetup
from backend.data.shared_aggregate_setup import derive_shared_aggregate
from backend.queueing_engine.services.shared_segments import _id_problems


def reference_id_problems(kind: str, identifiers: list[object]) -> list[str]:
    """The previous implementation, kept verbatim as the reference (quadratic list.count)."""
    problems = []
    if any(not isinstance(item, str) or not item.strip() for item in identifiers):
        problems.append(f"Every {kind} needs a non-empty text id.")
    texts = [item for item in identifiers if isinstance(item, str)]
    duplicates = sorted({item for item in texts if texts.count(item) > 1})
    if duplicates:
        problems.append(f"Duplicate {kind} ids: {', '.join(duplicates)}.")
    return problems


@pytest.mark.parametrize("identifiers", [
    [],
    ["a"],
    ["a", "b", "c"],
    ["a", "a"],
    ["b", "a", "b", "c", "a", "a", "d", "c"],  # several duplicates, out of order, one three times
    ["05:00-06:00", "06:00-07:00", "05:00-06:00"],
    ["café", "cafe", "café", "日本", "日本", "Ω", "Ω"],  # unicode, including look-alikes that differ
    ["café", "café", "café"],  # combining accent vs precomposed: different ids
    [" a", "a", "a ", " a", "", "", "   ", "   "],  # whitespace ids are compared as written
    ["a", None, 3, "a", None, 3.0, ""],  # non-text ids are refused, never counted as duplicates
    ["B", "b", "B", "b", "a"],  # case-sensitive, sorted as before
])
def test_duplicate_ids_are_reported_exactly_as_before(identifiers):
    for kind in ("demand period", "staffing segment"):
        assert _id_problems(kind, identifiers) == reference_id_problems(kind, identifiers)


def test_duplicate_ids_match_the_reference_on_random_lists():
    rng = random.Random(20261109)
    alphabet = ["a", "b", "c", " a", "a ", "", " ", "é", "é", "日", "08:00-09:00", None, 7]
    for _ in range(2000):
        identifiers = [rng.choice(alphabet) for _ in range(rng.randint(0, 25))]
        assert _id_problems("demand period", identifiers) == reference_id_problems("demand period", identifiers)


def test_a_large_repeated_hour_file_is_read_in_bounded_time():
    """100,000 rows (the default UPLOAD_MAX_ROWS) of repeated 05:00-18:00 hours: the quadratic check took >10 min."""
    hours = [f"{hour:02d}:00-{hour + 1:02d}:00" for hour in range(5, 18)]
    frame = pd.DataFrame({"time": [hours[index % 13] for index in range(100_000)], "lambda": 6.0, "mu": 5.0, "c": 3})
    started = time.perf_counter()
    result = derive_shared_aggregate(frame, QueueSetup(queue_structure="shared_queue").model_dump(mode="json"))
    elapsed = time.perf_counter() - started
    assert result["mode"] == "declined"
    assert [reason["code"] for reason in result["reasons"]] == ["invalid_timeline"]
    assert f"Duplicate demand period ids: {', '.join(sorted(hours))}." in result["reasons"][0]["detail"]
    assert elapsed < 30, elapsed
