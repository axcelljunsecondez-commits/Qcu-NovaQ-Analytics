"""Read four-column shared aggregate file facts and propose an explicit Setup.

The approved shared-upload specification adds a consumer of the existing ingestion
and timeline validators; it changes neither their rules nor any model calculation.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
from pydantic import ValidationError

from backend.api.analysis_schemas import STORED_SETUP, QueueSetup, QueueStructure
from backend.data.analysis_ingestion import normalize_analysis_input
from backend.data.setup_derivation import DIFF_FIELDS
from backend.data.uploads import safe_stem
from backend.queueing_engine.services.shared_segments import (
    OperatingHorizon,
    SharedSegmentError,
    format_clock,
    timeline_from_aggregate_rows,
    validate_timeline,
)


def digest(value: Any) -> str:
    """Version-independent SHA256 identity for JSON-compatible saved/request values."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def setup_digest(setup: dict) -> str:
    return digest(QueueSetup.model_validate(setup, context=STORED_SETUP).model_dump(mode="json"))


def derive_shared_aggregate(frame: pd.DataFrame, saved_setup: dict, filename: str = "upload.csv") -> dict[str, Any]:
    """Read file facts without injecting operational assumptions or changing the input.

    The final apply separately normalizes against the actual preserved/answered Setup,
    so known finite capacity and patience are preserved in the stored dataset as before.
    """
    saved = QueueSetup.model_validate(saved_setup, context=STORED_SETUP).model_dump(mode="json")
    result: dict[str, Any] = {
        "mode": "declined", "facts": None, "derived_setup": None, "saved_setup": saved,
        "diff": [], "needs_confirmation": False, "unresolved": [], "conflicts": [], "reasons": [],
        "records": [], "provenance": {},
    }

    def decline(code: str, detail: str) -> dict[str, Any]:
        result["reasons"] = [{"code": code, "detail": detail}]
        return result

    if saved["queue_structure"] != "shared_queue":
        return decline("not_shared_line", "This file-reading path requires an existing shared-queue analysis.")
    columns = [str(column).strip() for column in frame.columns]
    if set(columns) != {"time", "lambda", "mu", "c"} or len(columns) != 4:
        return decline("outside_slice", "This path reads exactly time, lambda, mu and c; use the existing upload for other columns.")
    # These are file facts only. Applying saved K/theta here would invent fields in
    # the file and make the shared timeline refuse a valid four-column input.
    file_setup = QueueSetup(queue_structure=QueueStructure.shared_queue, staffing_varies_by_period=True)
    records, provenance = normalize_analysis_input(frame, file_setup)
    try:
        periods, staffing = timeline_from_aggregate_rows(records)
        horizon = OperatingHorizon(periods[0].start_minute, periods[-1].end_minute)
        validate_timeline(horizon, periods, staffing)
    except SharedSegmentError as exc:
        return decline("invalid_timeline", str(exc))
    if any(period.end_minute - period.start_minute != 60 for period in periods):
        return decline("non_hourly", "This path requires one-hour rows; use the existing upload for other durations.")
    if horizon.end_minute >= 1440:
        return decline("outside_slice", "The saved Setup requires same-day clock times before 24:00.")
    counts = [int(segment.servers) for segment in staffing]
    if len(set(counts)) == 1 and counts[0] < 1:
        return decline("outside_slice", "The saved fixed counter count must be at least one.")
    rows: list[dict[str, Any]] = [{"time": str(row["time"]), "lambda": float(row["lambda"]),
                                 "mu": float(row["mu"]), "c": int(row["c"])} for row in records]
    result["facts"] = {
        "filename": safe_stem(filename), "row_count": len(rows),
        "start_time": format_clock(horizon.start_minute), "end_time": format_clock(horizon.end_minute),
        "counter_min": min(counts), "counter_max": max(counts), "rows": rows,
        "lambda_min": min(row["lambda"] for row in rows), "lambda_max": max(row["lambda"] for row in rows),
        "mu_min": min(row["mu"] for row in rows), "mu_max": max(row["mu"] for row in rows),
    }
    candidate = {
        **saved, "fixed_server_count": counts[0] if len(set(counts)) == 1 else None,
        "staffing_varies_by_period": len(set(counts)) > 1,
        "segments": [{"id": segment.segment_id, "start_time": format_clock(segment.start_minute),
                      "end_time": format_clock(segment.end_minute), "active_queue_ids": None}
                     for segment in staffing],
    }
    try:
        candidate = QueueSetup.model_validate(candidate).model_dump(mode="json")
    except ValidationError as exc:
        result["conflicts"] = [{"code": "invalid_setup", "detail": str(exc)}]
    # Reuse the exact existing break policy. Runtime import avoids the existing
    # shared adapter -> analyses import cycle; no new validator is copied here.
    from backend.api.shared_continuous import _counter_breaks

    _, conflicts = _counter_breaks(candidate, horizon, staffing)
    result["conflicts"].extend({**entry, "detail": " ".join(entry.get("problems", []))} for entry in conflicts)
    result.update({
        "mode": "shared_aggregate", "derived_setup": candidate,
        "diff": [{"field": key, "saved": saved.get(key), "derived": candidate.get(key)}
                 for key in [*DIFF_FIELDS, "counter_breaks"] if saved.get(key) != candidate.get(key)],
        "unresolved": [key for key in ("capacity_mode", "abandonment_mode") if saved[key] == "unknown"],
        "records": records, "provenance": provenance,
    })
    # The primary Apply confirms newly read facts. A second confirmation is
    # needed only when replacing configured count/period facts, not filling gaps.
    configured = saved["fixed_server_count"] is not None or bool(saved["segments"])
    result["needs_confirmation"] = configured and bool(result["diff"])
    return result
