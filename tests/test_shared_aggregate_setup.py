"""File-only shared Setup derivation; uses the existing published owner-CSV fixture."""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import pytest

from backend.api.analysis_schemas import QueueSetup
from backend.data.analysis_ingestion import AnalysisIngestionError, normalize_analysis_input
from backend.data.shared_aggregate_setup import derive_shared_aggregate
from tests.test_shared_segments import NOVAMART_AVERAGE_ROWS


def saved(**fields):
    return QueueSetup(queue_structure="shared_queue", **fields).model_dump(mode="json")


def owner_frame():
    return pd.read_csv(Path(__file__).parent / "fixtures" / "shared_aggregate_owner.csv")


def test_owner_csv_derives_hourly_setup_without_changing_input_or_assumptions():
    frame = owner_frame()
    original = frame.copy(deep=True)
    setup = saved(fixed_server_count=3)
    original_setup = copy.deepcopy(setup)
    result = derive_shared_aggregate(frame, setup, "owner.csv")
    assert result["mode"] == "shared_aggregate"
    assert result["facts"] == {
        "filename": "owner.csv", "row_count": 13, "start_time": "05:00", "end_time": "18:00",
        "counter_min": 2, "counter_max": 5, "rows": NOVAMART_AVERAGE_ROWS,
        "lambda_min": 5.0, "lambda_max": 12.7857, "mu_min": 4.3068, "mu_max": 5.3242,
    }
    candidate = result["derived_setup"]
    assert candidate["fixed_server_count"] is None
    assert candidate["staffing_varies_by_period"] is True
    assert len(candidate["segments"]) == 13
    assert candidate["segments"][0] == {
        "id": "05:00-06:00", "start_time": "05:00:00", "end_time": "06:00:00", "active_queue_ids": None,
    }
    assert candidate["segments"][-1]["end_time"] == "18:00:00"
    assert result["unresolved"] == ["capacity_mode", "abandonment_mode"]
    assert result["conflicts"] == []
    assert {entry["field"] for entry in result["diff"]} == {
        "fixed_server_count", "staffing_varies_by_period", "segments",
    }
    assert result["needs_confirmation"] is True
    pd.testing.assert_frame_equal(frame, original)
    assert setup == original_setup


def test_constant_staffing_and_preserved_operational_choices():
    setup = saved(capacity_mode="finite", total_system_capacity=20,
                  abandonment_mode="modeled", patience_rate_per_hour=0.5,
                  event_period_basis="representative_day",
                  counter_breaks=[{"scheduled_start_time": "10:00", "duration_minutes": 15}])
    frame = owner_frame()
    frame["c"] = 4
    result = derive_shared_aggregate(frame, setup)
    assert result["mode"] == "shared_aggregate"
    assert result["derived_setup"]["fixed_server_count"] == 4
    assert result["derived_setup"]["staffing_varies_by_period"] is False
    for key in ("capacity_mode", "total_system_capacity", "abandonment_mode", "patience_rate_per_hour",
                "counter_breaks", "event_period_basis"):
        assert result["derived_setup"][key] == setup[key]
    assert result["unresolved"] == []
    assert result["conflicts"] == []
    assert all("K" not in row or row["K"] is None for row in result["records"])


@pytest.mark.parametrize("change", ["gap", "overlap", "overnight", "bad_label", "half_hour"])
def test_readable_outside_slice_declines_without_partial_setup(change):
    frame = owner_frame()
    if change == "gap":
        frame = frame.drop(index=1)
    elif change == "overlap":
        frame.loc[1, "time"] = "05:30-06:30"
    elif change == "overnight":
        frame.loc[0, "time"] = "23:00-00:00"
    elif change == "bad_label":
        frame.loc[0, "time"] = "5am"
    else:
        frame.loc[0, "time"] = "05:00-05:30"
    result = derive_shared_aggregate(frame, saved())
    assert result["mode"] == "declined"
    assert result["derived_setup"] is None
    assert result["reasons"]


@pytest.mark.parametrize("column,value", [("K", 20), ("theta", 0.5), ("variance", 0.04), ("notes", "source")])
def test_extra_evidence_is_not_discarded_to_fit_the_slice(column, value):
    frame = owner_frame()
    frame[column] = value
    result = derive_shared_aggregate(frame, saved())
    assert result["mode"] == "declined"
    assert column in frame.columns
    assert result["derived_setup"] is None


@pytest.mark.parametrize("column,value", [("c", 2.5), ("mu", 0), ("lambda", -1)])
def test_existing_ingestion_validation_still_refuses_invalid_values(column, value):
    frame = owner_frame().astype({column: float})
    frame.loc[0, column] = value
    with pytest.raises(AnalysisIngestionError):
        derive_shared_aggregate(frame, saved())


@pytest.mark.parametrize("breaks,code", [
    ([{"scheduled_start_time": "04:00", "duration_minutes": 15}], "breaks_outside_hours"),
    ([{"scheduled_start_time": "11:00", "duration_minutes": 15}] * 3, "breaks_not_staffed"),
])
def test_saved_break_conflicts_are_reported_and_preserved(breaks, code):
    setup = saved(counter_breaks=breaks)
    result = derive_shared_aggregate(owner_frame(), setup)
    assert result["mode"] == "shared_aggregate"
    assert code in [entry["code"] for entry in result["conflicts"]]
    assert result["derived_setup"]["counter_breaks"] == setup["counter_breaks"]


def test_wrong_structure_does_not_become_shared_from_four_columns():
    result = derive_shared_aggregate(owner_frame(), QueueSetup().model_dump(mode="json"))
    assert result["mode"] == "declined"
    assert result["derived_setup"] is None


def test_first_primary_apply_is_enough_when_only_missing_file_facts_are_filled():
    result = derive_shared_aggregate(owner_frame(), saved())
    assert result["diff"]
    assert result["needs_confirmation"] is False


EVENTS = {"arrival_time": "2026-10-01 05:00:00", "service_start": "2026-10-01 05:01:00", "service_end": "2026-10-01 05:04:00"}


def unreadable_frame(case):
    frame = owner_frame()
    if case == "missing_c":
        return frame.drop(columns=["c"])
    if case == "missing_lambda_and_mu":
        return frame.drop(columns=["lambda", "mu"])
    if case == "partial_customer_records":
        return frame.drop(columns=["c"]).assign(arrival_time=EVENTS["arrival_time"])
    return frame.assign(**EVENTS)  # both schemas


@pytest.mark.parametrize("case,message", [
    ("missing_c", "Schema could not be identified. Missing aggregate columns: c."),
    ("missing_lambda_and_mu", "Schema could not be identified. Missing aggregate columns: lambda, mu."),
    ("partial_customer_records", "Missing customer-event columns: service_end ("),
    ("both_schemas", "The file contains both aggregate and customer-event schemas; upload only one schema."),
])
def test_missing_required_columns_raise_the_usual_upload_message(case, message):
    """D3: a file the usual upload cannot read is unreadable here too, with the same words."""
    frame = unreadable_frame(case)
    with pytest.raises(AnalysisIngestionError) as usual:
        normalize_analysis_input(frame, QueueSetup.model_validate(saved()))
    with pytest.raises(AnalysisIngestionError) as read:
        derive_shared_aggregate(frame, saved())
    assert str(read.value) == str(usual.value)
    assert str(read.value).startswith(message)


@pytest.mark.parametrize("case", ["business_names", "full_customer_records"])
def test_readable_files_outside_this_path_still_decline(case):
    if case == "business_names":
        frame = owner_frame().rename(columns={"c": "cashiers", "lambda": "arrival rate"})
    else:
        frame = pd.DataFrame([EVENTS, EVENTS])
    result = derive_shared_aggregate(frame, saved())
    assert result["mode"] == "declined"
    assert result["derived_setup"] is None
    assert [reason["code"] for reason in result["reasons"]] == ["outside_slice"]

