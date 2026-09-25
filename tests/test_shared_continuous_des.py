"""Phase 3 continuous shared-queue DES: exact, identity, statistical, and reproducibility checks.

Deterministic cases use prescribed arrivals and unit work with μ = 1 (so work = hours) and
binary-exact times, so every expected value below is computed by hand. Statistical checks
compare replication means with independent references within 4 standard errors.

Phase 3A closing: every run names DRAIN or HARD_CUTOFF. The Phase 3 exact cases end all
activity before closing, so they run under both policies and must agree.
"""

from __future__ import annotations

import logging
import math

import pytest

from backend.queueing_engine.services.shared_capacity import CapacityConfig, optimize_shared_capacity
from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
    timeline_from_aggregate_rows,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    CLOSING_POLICIES,
    DRAIN,
    HARD_CUTOFF,
    simulate_prescribed,
    simulate_shared_day,
    staffing_from_capacity_result,
)
from tests.test_shared_segments import NOVAMART_AVERAGE_ROWS, erlang_reference


def hourly(*servers: int, lam: float = 1.0, mu: float = 1.0) -> tuple[OperatingHorizon, list, list]:
    """One demand period over the horizon and one staffing segment per hour."""
    hours = len(servers)
    horizon = OperatingHorizon(0, 60 * hours)
    periods = [DemandPeriod("d", 0, 60 * hours, lam, mu)]
    segments = [StaffingSegment(f"h{i}", 60 * i, 60 * (i + 1), c) for i, c in enumerate(servers)]
    return horizon, periods, segments


def by_id(result: dict) -> dict[int, dict]:
    return {row["customer_id"]: row for row in result["customers"]}


def approx(value: float) -> object:
    return pytest.approx(value, rel=1e-9, abs=1e-12)


def assert_sample_path_identities(result: dict) -> None:
    """Time integrals equal sums over customers, inside the horizon and after closing."""
    end = result["closing"]["closing_hours"]
    rows = result["customers"]

    def waited_until(row: dict) -> float:  # unserved customers leave the line at closing
        return row["service_start_hours"] if row["service_start_hours"] is not None else end

    served = [row for row in rows if row["service_start_hours"] is not None]
    waiting_in = math.fsum(min(waited_until(row), end) - row["arrival_hours"] for row in rows)
    waiting_after = math.fsum(max(0.0, waited_until(row) - end) for row in rows)
    busy_in = math.fsum(max(0.0, min(row["service_end_hours"], end) - row["service_start_hours"]) for row in served)
    busy_after = math.fsum(
        row["service_end_hours"] - max(row["service_start_hours"], end) for row in served if row["service_end_hours"] > end
    )
    totals, closing, quantities = result["totals"], result["closing"], result["cost_quantities"]
    assert totals["queue_customer_hours"] == approx(waiting_in)
    assert closing["after_close_waiting_customer_hours"] == approx(waiting_after)
    assert quantities["total_waiting_customer_hours"] == approx(
        math.fsum(row["wait_hours"] for row in served)
        + math.fsum(row["elapsed_wait_at_close_hours"] for row in rows if row["status"] == "unserved_at_close")
    )
    assert totals["busy_server_hours"] == approx(busy_in)
    assert closing["after_close_busy_server_hours"] == approx(busy_after)
    # After closing a server stays only while it serves, so overtime = service time after closing.
    assert quantities["overtime_server_hours"] == approx(busy_after)
    assert quantities["regular_server_hours"] == totals["present_server_hours"]
    last_end = max((row["service_end_hours"] for row in served if row["service_end_hours"] > end), default=end)
    assert closing["overrun_hours"] == approx(last_end - end)


def assert_conservation_and_identity(result: dict) -> None:
    totals = result["totals"]
    assert totals["customer_conservation"] is True
    assert totals["arrivals"] == totals["departed"] + totals["unserved_at_close"]
    ids = [row["customer_id"] for row in result["customers"]]
    assert ids == list(range(1, len(ids) + 1))
    arrival_events = [event["customer_id"] for event in result["trace"] if event["type"] == "arrival"]
    assert sorted(arrival_events) == ids  # one arrival event per customer, never a replacement
    starts = [row for row in result["customers"] if row["service_start_hours"] is not None]
    assert all(row["wait_hours"] >= 0 for row in starts)
    assert all(row["status"] == "departed" and row["service_end_hours"] is not None for row in starts)
    # First come, first served: service starts follow arrival order.
    start_times = [row["service_start_hours"] for row in sorted(starts, key=lambda row: row["customer_id"])]
    assert start_times == sorted(start_times)
    # Every customer ends with an explicit outcome. Unserved customers were still waiting at
    # closing, so under FCFS they are the latest arrivals.
    unserved = [row for row in result["customers"] if row["status"] == "unserved_at_close"]
    assert [row["customer_id"] for row in unserved] == ids[len(ids) - len(unserved):]
    assert [row["customer_id"] for row in unserved] == result["closing"]["unserved_customer_ids"]
    assert all(row["unserved_reason"] in ("hard_cutoff", "no_eligible_server") for row in unserved)
    assert all(row["wait_hours"] is None and row["elapsed_wait_at_close_hours"] >= 0 for row in unserved)
    assert all(row["unserved_reason"] is None for row in starts)
    if not result["closing"]["unserved_possible"]:
        assert unserved == []


def run_both(*args, **kwargs) -> dict:
    """Run a case whose activity ends before closing under both policies; they must agree."""
    drain = simulate_prescribed(*args, closing_policy=DRAIN, **kwargs)
    cutoff = simulate_prescribed(*args, closing_policy=HARD_CUTOFF, **kwargs)
    for key in ("customers", "segments", "totals", "capacity_transitions", "drains", "trace"):
        assert drain[key] == cutoff[key], key
    assert drain["closing"]["overrun_hours"] == cutoff["closing"]["overrun_hours"] == 0.0
    return drain


def in_horizon(transitions: list[dict]) -> list[dict]:
    return [item for item in transitions if item["segment_id"] is not None]


TIME_ATTRIBUTED_KEYS = (
    "segment_id", "arrivals", "time_average_queue", "max_queue", "busy_server_hours", "present_server_hours",
    "scheduled_server_hours", "server_hours_above_schedule", "utilization_of_present",
)


def time_attributed(result: dict) -> list[dict]:
    """Per-segment values that measure [start, closing) only, so no closing policy can change them."""
    return [{key: row[key] for key in TIME_ATTRIBUTED_KEYS} for row in result["segments"]]


# ── Exact deterministic cases ───────────────────────────────────────────────


def test_constant_capacity_fcfs_waits_are_exact():
    result = run_both(*hourly(1), [(0.125, 0.25), (0.1875, 0.0625), (0.25, 0.0625)])
    customers = by_id(result)
    assert [customers[i]["wait_hours"] for i in (1, 2, 3)] == [0.0, 0.1875, 0.1875]
    assert [customers[i]["service_end_hours"] for i in (1, 2, 3)] == [0.375, 0.4375, 0.5]
    assert result["totals"]["queue_customer_hours"] == 0.375
    assert result["segments"][0]["time_average_queue"] == 0.375
    assert result["totals"]["mean_wait_hours"] == pytest.approx(0.125)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_increase_serves_the_backlog_at_the_boundary():
    # c = 1 then 2 at 1.0 h. Customer 2 waits from 0.25 to the increase, then uses server 2.
    result = run_both(*hourly(1, 2), [(0.125, 1.5), (0.25, 0.125)])
    second = by_id(result)[2]
    assert second["service_start_hours"] == 1.0
    assert second["server_id"] == 2
    assert second["wait_hours"] == 0.75
    assert second["arrival_segment_id"] == "h0"
    opened = [t for t in result["capacity_transitions"] if t["kind"] == "open"]
    assert [(t["t"], t["server_id"]) for t in opened] == [(0.0, 1), (1.0, 2)]
    assert result["segments"][0]["time_average_queue"] == 0.75
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_decrease_drains_a_busy_server_without_interrupting_service():
    # c = 2 then 1 at 1.0 h; both servers busy, so server 2 (highest number) drains.
    result = run_both(*hourly(2, 1), [(0.125, 1.25), (0.25, 1.0), (1.0625, 0.125)])
    customers = by_id(result)
    assert customers[2]["service_end_hours"] == 1.25  # finished, not cut at 1.0
    assert customers[2]["status"] == "departed"
    # Customer 3 must not go to draining server 2 when it frees at 1.25; it waits for server 1.
    assert customers[3]["server_id"] == 1
    assert customers[3]["service_start_hours"] == 1.375
    assert customers[3]["wait_hours"] == 0.3125
    assert result["drains"] == [
        {"server_id": 2, "customer_id": 2, "designated_at": 1.0, "released_at": 1.25, "segment_id": "h1"}
    ]
    later = result["segments"][1]
    assert later["scheduled_server_hours"] == 1.0
    assert later["present_server_hours"] == 1.25
    assert later["server_hours_above_schedule"] == 0.25
    assert later["busy_server_hours"] == 0.75
    assert later["utilization_of_present"] == 0.6
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_capacity_decrease_closes_idle_servers_first():
    result = run_both(*hourly(2, 1), [(0.125, 1.5), (0.25, 0.125), (1.125, 0.125)])
    assert result["drains"] == []
    closes = [(t["t"], t["server_id"]) for t in in_horizon(result["capacity_transitions"]) if t["kind"] == "close"]
    assert closes == [(1.0, 2)]
    assert by_id(result)[3]["service_start_hours"] == 1.625  # server 1 keeps working and takes it
    assert result["segments"][1]["server_hours_above_schedule"] == 0.0
    assert_conservation_and_identity(result)


def test_zero_capacity_segment_keeps_backlog_and_finishes_started_service():
    # c = 1, 0, 1 by 30 minutes. Customer 1 is in service across the closing boundary.
    horizon = OperatingHorizon(0, 90)
    periods = [DemandPeriod("d", 0, 90, 1.0, 1.0)]
    segments = [StaffingSegment("a", 0, 30, 1), StaffingSegment("b", 30, 60, 0), StaffingSegment("c", 60, 90, 1)]
    result = run_both(horizon, periods, segments, [(0.375, 0.25), (0.5625, 0.125)])
    customers = by_id(result)
    assert customers[1]["service_end_hours"] == 0.625
    assert result["drains"][0]["designated_at"] == 0.5 and result["drains"][0]["released_at"] == 0.625
    assert customers[2]["service_start_hours"] == 1.0  # waits through the closed segment
    assert customers[2]["wait_hours"] == 0.4375
    closed = result["segments"][1]
    assert closed["scheduled_server_hours"] == 0.0
    assert closed["busy_server_hours"] == 0.125  # the drain, reported as time above schedule
    assert closed["server_hours_above_schedule"] == 0.125
    assert closed["time_average_queue"] == pytest.approx((1.0 - 0.5625) / 0.5)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_zero_demand_period_still_serves_backlog():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("busy", 0, 60, 1.0, 1.0), DemandPeriod("quiet", 60, 120, 0.0, 1.0)]
    segments = [StaffingSegment("busy", 0, 60, 1), StaffingSegment("quiet", 60, 120, 1)]
    result = run_both(horizon, periods, segments, [(0.5, 0.625), (0.625, 0.25)])
    quiet = result["segments"][1]
    assert quiet["arrivals"] == 0
    assert quiet["time_average_queue"] == 0.125  # customer 2 waits 1.0 to 1.125 inside it
    assert by_id(result)[2]["service_start_hours"] == 1.125
    assert_sample_path_identities(result)
    with pytest.raises(SharedSegmentError, match="arrival rate is 0"):
        simulate_prescribed(horizon, periods, segments, [(1.5, 0.25)], closing_policy=DRAIN)


def test_completion_at_a_decrease_boundary_is_processed_first():
    # Server 1 finishes exactly at 1.0; the decrease then closes the now-idle server, no drain.
    result = run_both(*hourly(2, 1), [(0.25, 0.75), (0.5, 1.0)])
    assert result["drains"] == []
    assert [(t["t"], t["kind"], t["server_id"]) for t in result["capacity_transitions"] if t["t"] == 1.0] == [
        (1.0, "close", 1)
    ]
    assert by_id(result)[2]["service_end_hours"] == 1.5


def test_arrival_at_an_increase_boundary_sees_the_new_capacity():
    result = run_both(*hourly(1, 2), [(0.25, 1.0), (1.0, 0.25)])
    second = by_id(result)[2]
    assert (second["service_start_hours"], second["server_id"], second["wait_hours"]) == (1.0, 2, 0.0)
    at_boundary = [(event["type"], event["segment_id"]) for event in result["trace"] if event["t"] == 1.0]
    assert at_boundary.index(("capacity_change", "h1")) < at_boundary.index(("arrival", "h1"))


def test_arrival_at_a_decrease_boundary_sees_the_reduced_capacity():
    # c = 2 then 1 at 1.0 h. Server 2 is idle at 1.0, so the decrease closes it before the
    # arrival at 1.0 is handled; the arrival waits for server 1 instead of taking server 2.
    result = run_both(*hourly(2, 1), [(0.25, 1.0), (1.0, 0.25)])
    second = by_id(result)[2]
    assert (second["service_start_hours"], second["server_id"], second["wait_hours"]) == (1.25, 1, 0.25)
    assert result["drains"] == []


def test_started_service_keeps_its_duration_when_mu_changes():
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("slow", 0, 60, 1.0, 1.0), DemandPeriod("fast", 60, 120, 1.0, 2.0)]
    segments = [StaffingSegment("slow", 0, 60, 2), StaffingSegment("fast", 60, 120, 2)]
    result = run_both(horizon, periods, segments, [(0.75, 0.5), (1.25, 0.5)])
    customers = by_id(result)
    assert customers[1]["service_end_hours"] == 1.25  # 0.5 work / μ 1, started before the change
    assert customers[2]["service_end_hours"] == 1.5  # 0.5 work / μ 2, started after it


def test_reactivating_a_draining_server_before_opening_a_new_one():
    # c = 2, 1, 2: server 2 drains at 1.0 and is reactivated at 2.0 while still busy.
    result = run_both(*hourly(2, 1, 2), [(0.125, 2.5), (0.25, 2.5)])
    kinds = [(t["t"], t["kind"], t["server_id"]) for t in result["capacity_transitions"]]
    assert (1.0, "drain_start", 2) in kinds and (2.0, "reactivate", 2) in kinds
    assert result["totals"]["servers_used"] == 2
    assert result["drains"][0]["reactivated_at"] == 2.0 and result["drains"][0]["released_at"] is None


# ── Closing (Phase 3A) ──────────────────────────────────────────────────────


def closing_view(result: dict) -> dict:
    closing = result["closing"]
    return {key: closing[key] for key in (
        "unserved_customer_ids", "service_starts_after_close", "completions_after_close",
        "after_close_server_hours", "after_close_waiting_customer_hours", "overrun_hours",
    )}


def test_closing_policy_is_required_and_validated():
    with pytest.raises(TypeError, match="closing_policy"):
        simulate_prescribed(*hourly(1), [])  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="closing_policy"):
        simulate_shared_day(*hourly(1), seed=1)  # type: ignore[call-arg]
    for bad in ("drain", "OBSERVE", None, 1):
        with pytest.raises(SharedSegmentError, match="closing_policy must be DRAIN or HARD_CUTOFF"):
            simulate_prescribed(*hourly(1), [], closing_policy=bad)  # type: ignore[arg-type]
    assert CLOSING_POLICIES == (DRAIN, HARD_CUTOFF)


def test_empty_system_at_closing():
    result = run_both(*hourly(1), [(0.25, 0.25)])
    closing = result["closing"]
    assert closing["at_close"] == {
        "waiting_customer_ids": [], "in_service_customer_ids": [], "accepting_server_ids": [1],
        "draining_server_ids": [],
    }
    assert closing_view(result) == {
        "unserved_customer_ids": [], "service_starts_after_close": 0, "completions_after_close": 0,
        "after_close_server_hours": 0.0, "after_close_waiting_customer_hours": 0.0, "overrun_hours": 0.0,
    }
    # The idle server closes at the closing time, outside any staffing segment.
    assert result["capacity_transitions"][-1] == {
        "t": 1.0, "kind": "close", "server_id": 1, "segment_id": None, "customer_id": None,
    }
    assert result["trace"][-2]["type"] == "closing" and result["trace"][-2]["segment_id"] is None
    assert result["cost_quantities"]["regular_server_hours"] == 1.0
    assert result["cost_quantities"]["overtime_server_hours"] == 0.0


def test_drain_serves_waiting_customers_after_closing():
    # c = 1 for one hour. Customer 1 is in service across closing; 2 and 3 are waiting at closing.
    arrivals = [(0.5, 0.75), (0.75, 0.125), (0.875, 0.25)]
    result = simulate_prescribed(*hourly(1), arrivals, closing_policy=DRAIN)
    customers = by_id(result)
    assert result["closing"]["at_close"] == {
        "waiting_customer_ids": [2, 3], "in_service_customer_ids": [1], "accepting_server_ids": [1],
        "draining_server_ids": [],
    }
    assert [(customers[i]["service_start_hours"], customers[i]["service_end_hours"]) for i in (1, 2, 3)] == [
        (0.5, 1.25), (1.25, 1.375), (1.375, 1.625)
    ]
    assert [customers[i]["wait_hours"] for i in (1, 2, 3)] == [0.0, 0.5, 0.5]  # waits continue across closing
    assert all(customers[i]["status"] == "departed" for i in (1, 2, 3))
    assert closing_view(result) == {
        "unserved_customer_ids": [], "service_starts_after_close": 2, "completions_after_close": 3,
        "after_close_server_hours": 0.625, "after_close_waiting_customer_hours": 0.625, "overrun_hours": 0.625,
    }
    assert result["totals"]["queue_customer_hours"] == 0.375  # 0.25 + 0.125 before closing
    assert result["totals"]["mean_wait_hours"] == pytest.approx(1 / 3)
    assert result["segments"][0]["mean_wait_hours"] == pytest.approx(1 / 3)  # arrival-attributed
    assert result["cost_quantities"] == result["cost_quantities"] | {
        "regular_server_hours": 1.0, "overtime_server_hours": 0.625, "total_waiting_customer_hours": 1.0,
        "unserved_customer_count": 0, "unserved_possible": False,
    }
    assert [t["kind"] for t in result["capacity_transitions"] if t["segment_id"] is None] == ["close"]
    assert result["capacity_transitions"][-1]["t"] == 1.625
    assert all(event["segment_id"] is None for event in result["trace"] if event["t"] >= 1.0)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_hard_cutoff_records_waiting_customers_and_finishes_service():
    arrivals = [(0.5, 0.75), (0.75, 0.125), (0.875, 0.25)]
    result = simulate_prescribed(*hourly(1), arrivals, closing_policy=HARD_CUTOFF)
    customers = by_id(result)
    assert customers[1]["service_end_hours"] == 1.25 and customers[1]["status"] == "departed"
    for customer_id, elapsed in ((2, 0.25), (3, 0.125)):
        row = customers[customer_id]
        assert row["status"] == "unserved_at_close" and row["unserved_reason"] == "hard_cutoff"
        assert row["wait_hours"] is None and row["elapsed_wait_at_close_hours"] == elapsed
        assert row["service_start_hours"] is None and row["server_id"] is None
    assert closing_view(result) == {
        "unserved_customer_ids": [2, 3], "service_starts_after_close": 0, "completions_after_close": 1,
        "after_close_server_hours": 0.25, "after_close_waiting_customer_hours": 0.0, "overrun_hours": 0.25,
    }
    assert result["totals"]["unserved_at_close"] == 2 and result["segments"][0]["unserved_at_close"] == 2
    assert result["totals"]["mean_wait_hours"] == 0.0  # only customer 1 started service
    assert result["cost_quantities"] == result["cost_quantities"] | {
        "regular_server_hours": 1.0, "overtime_server_hours": 0.25, "total_waiting_customer_hours": 0.375,
        "unserved_customer_count": 2, "unserved_possible": True,
    }
    unserved_events = [(e["t"], e["customer_id"]) for e in result["trace"] if e["type"] == "unserved_at_close"]
    assert unserved_events == [(1.0, 2), (1.0, 3)]
    assert not any(e["type"] == "service_start" and e["t"] >= 1.0 for e in result["trace"])
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_completion_exactly_at_closing_departs_before_the_closing_rule():
    # Customer 1 finishes exactly at closing (1.0); customer 2 is waiting then.
    arrivals = [(0.5, 0.5), (0.75, 0.25)]
    drain = simulate_prescribed(*hourly(1), arrivals, closing_policy=DRAIN)
    cutoff = simulate_prescribed(*hourly(1), arrivals, closing_policy=HARD_CUTOFF)
    for result in (drain, cutoff):
        assert result["closing"]["at_close"]["in_service_customer_ids"] == []
        assert result["closing"]["at_close"]["waiting_customer_ids"] == [2]
        assert by_id(result)[1]["service_end_hours"] == 1.0 and by_id(result)[1]["status"] == "departed"
        assert_sample_path_identities(result)
        assert_conservation_and_identity(result)
    # DRAIN: the freed server takes customer 2 at closing. HARD_CUTOFF: nobody starts at closing.
    assert (by_id(drain)[2]["service_start_hours"], by_id(drain)[2]["wait_hours"]) == (1.0, 0.25)
    assert closing_view(drain)["completions_after_close"] == 1  # customer 1 ended at, not after, closing
    assert closing_view(drain)["overrun_hours"] == 0.25
    assert by_id(cutoff)[2]["unserved_reason"] == "hard_cutoff"
    assert closing_view(cutoff)["overrun_hours"] == 0.0
    assert cutoff["cost_quantities"]["overtime_server_hours"] == 0.0


def test_draining_server_at_closing_only_finishes_its_own_customer():
    # c = 2 then 1 at 1.0 h. Server 2 drains from 1.0 and is still busy at closing (2.0).
    arrivals = [(0.125, 2.5), (0.25, 1.875), (1.5, 0.25)]
    drain = simulate_prescribed(*hourly(2, 1), arrivals, closing_policy=DRAIN)
    customers = by_id(drain)
    assert drain["closing"]["at_close"] == {
        "waiting_customer_ids": [3], "in_service_customer_ids": [1, 2], "accepting_server_ids": [1],
        "draining_server_ids": [2],
    }
    # Server 2 frees at 2.125 but closes; customer 3 waits for accepting server 1 at 2.625.
    assert (customers[3]["server_id"], customers[3]["service_start_hours"], customers[3]["wait_hours"]) == (
        1, 2.625, 1.125
    )
    assert drain["drains"] == [
        {"server_id": 2, "customer_id": 2, "designated_at": 1.0, "released_at": 2.125, "segment_id": "h1"}
    ]
    assert [(t["t"], t["kind"], t["server_id"]) for t in drain["capacity_transitions"] if t["segment_id"] is None] == [
        (2.125, "drain_complete", 2), (2.875, "close", 1)
    ]
    assert closing_view(drain)["after_close_server_hours"] == 1.0  # 0.875 + 0.125
    assert closing_view(drain)["overrun_hours"] == 0.875
    assert drain["cost_quantities"]["regular_server_hours"] == 4.0  # 2 + (1 scheduled + 1 draining)
    assert drain["totals"]["server_hours_above_schedule"] == 1.0

    cutoff = simulate_prescribed(*hourly(2, 1), arrivals, closing_policy=HARD_CUTOFF)
    assert by_id(cutoff)[3]["unserved_reason"] == "hard_cutoff"
    assert closing_view(cutoff)["after_close_server_hours"] == 0.75  # 0.625 + 0.125
    assert closing_view(cutoff)["overrun_hours"] == 0.625
    for result in (drain, cutoff):
        assert_sample_path_identities(result)
        assert_conservation_and_identity(result)


@pytest.mark.parametrize(("policy", "reason"), [(DRAIN, "no_eligible_server"), (HARD_CUTOFF, "hard_cutoff")])
def test_zero_capacity_final_segment_cannot_drain_forever(policy, reason):
    # c = 1 then 0 at 1.0 h. Customer 1 is in service across both boundaries (drains from 1.0);
    # customer 2 arrives while nobody accepts customers and is still waiting at closing.
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("d", 0, 120, 1.0, 1.0)]
    segments = [StaffingSegment("open", 0, 60, 1), StaffingSegment("closed", 60, 120, 0)]
    result = simulate_prescribed(horizon, periods, segments, [(0.5, 1.75), (1.5, 0.25)], closing_policy=policy)
    customers = by_id(result)
    assert result["closing"]["at_close"] == {
        "waiting_customer_ids": [2], "in_service_customer_ids": [1], "accepting_server_ids": [],
        "draining_server_ids": [1],
    }
    assert customers[1]["service_end_hours"] == 2.25 and customers[1]["status"] == "departed"
    assert (customers[2]["status"], customers[2]["unserved_reason"]) == ("unserved_at_close", reason)
    assert customers[2]["elapsed_wait_at_close_hours"] == 0.5
    assert result["closing"]["unserved_possible"] is True
    assert closing_view(result) == {
        "unserved_customer_ids": [2], "service_starts_after_close": 0, "completions_after_close": 1,
        "after_close_server_hours": 0.25, "after_close_waiting_customer_hours": 0.0, "overrun_hours": 0.25,
    }
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_backlog_from_a_zero_capacity_period_is_closed_out_by_policy():
    # c = 1, 0, 1 by hour. Three customers arrive while closed; capacity returns at 2.0.
    horizon = OperatingHorizon(0, 180)
    periods = [DemandPeriod("d", 0, 180, 1.0, 1.0)]
    segments = [StaffingSegment("a", 0, 60, 1), StaffingSegment("b", 60, 120, 0), StaffingSegment("c", 120, 180, 1)]
    arrivals = [(1.25, 0.75), (1.5, 0.75), (1.75, 0.75)]
    drain = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=DRAIN)
    cutoff = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=HARD_CUTOFF)
    assert [by_id(drain)[i]["wait_hours"] for i in (1, 2, 3)] == [0.75, 1.25, 1.75]
    assert by_id(drain)[3]["service_end_hours"] == 4.25
    assert closing_view(drain)["overrun_hours"] == 1.25
    assert drain["closing"]["unserved_possible"] is False  # the final segment has a server
    assert [by_id(cutoff)[i]["wait_hours"] for i in (1, 2)] == [0.75, 1.25]
    assert by_id(cutoff)[3]["elapsed_wait_at_close_hours"] == 1.25
    assert closing_view(cutoff)["overrun_hours"] == 0.5
    # Before closing both runs are identical; only arrival-attributed outcomes differ.
    assert time_attributed(drain) == time_attributed(cutoff)
    assert [row["service_starts"] for row in drain["segments"]] == [0, 3, 0]
    assert [row["service_starts"] for row in cutoff["segments"]] == [0, 2, 0]
    for result in (drain, cutoff):
        assert_sample_path_identities(result)
        assert_conservation_and_identity(result)


def test_capacity_increase_just_before_closing():
    # c = 1 until 0:45, then 2 until closing at 1:00.
    horizon = OperatingHorizon(0, 60)
    periods = [DemandPeriod("d", 0, 60, 1.0, 1.0)]
    segments = [StaffingSegment("early", 0, 45, 1), StaffingSegment("late", 45, 60, 2)]
    arrivals = [(0.125, 1.0), (0.25, 0.5), (0.875, 0.25)]
    drain = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=DRAIN)
    assert by_id(drain)[2]["service_start_hours"] == 0.75  # served by the server opened at 0:45
    assert drain["closing"]["at_close"]["accepting_server_ids"] == [1, 2]
    assert (by_id(drain)[3]["server_id"], by_id(drain)[3]["service_start_hours"]) == (1, 1.125)
    assert [(t["t"], t["kind"], t["server_id"]) for t in drain["capacity_transitions"] if t["segment_id"] is None] == [
        (1.25, "close", 2), (1.375, "close", 1)
    ]
    assert closing_view(drain)["after_close_server_hours"] == 0.625
    cutoff = simulate_prescribed(horizon, periods, segments, arrivals, closing_policy=HARD_CUTOFF)
    assert closing_view(cutoff)["unserved_customer_ids"] == [3]
    assert closing_view(cutoff)["after_close_server_hours"] == 0.375
    for result in (drain, cutoff):
        assert_sample_path_identities(result)
        assert_conservation_and_identity(result)


def test_service_after_closing_uses_the_final_demand_period_rate():
    # Customer 2 arrives in the μ = 1 period but first reaches a server after closing, where
    # the final period's μ = 4 applies: 1.0 work lasts 0.25 h, not 1.0 h.
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("slow", 0, 60, 1.0, 1.0), DemandPeriod("fast", 60, 120, 1.0, 4.0)]
    segments = [StaffingSegment("slow", 0, 60, 1), StaffingSegment("fast", 60, 120, 1)]
    result = simulate_prescribed(horizon, periods, segments, [(0.25, 2.0), (0.5, 1.0)], closing_policy=DRAIN)
    second = by_id(result)[2]
    assert by_id(result)[1]["service_end_hours"] == 2.25  # started under μ = 1, across closing
    assert (second["service_start_hours"], second["service_end_hours"], second["wait_hours"]) == (2.25, 2.5, 1.75)
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def independent_closing(result: dict, mu_final: float) -> dict:
    """Recompute the after-closing schedule from the at-close state with an FCFS recursion.

    Accepting servers are free at closing (idle) or at their customer's end; each waiting
    customer in line order takes the earliest-free accepting server (lowest number on ties) and
    serves work / μ_final. Draining servers only finish their own customer. Shares no engine code.
    """
    end = result["closing"]["closing_hours"]
    at_close = result["closing"]["at_close"]
    rows = by_id(result)
    running = {rows[cid]["server_id"]: rows[cid]["service_end_hours"] for cid in at_close["in_service_customer_ids"]}
    free = {sid: running.get(sid, end) for sid in at_close["accepting_server_ids"]}
    draining_ends = [running[sid] for sid in at_close["draining_server_ids"]]
    schedule, unserved = {}, []
    if result["closing"]["policy"] == HARD_CUTOFF or not free:
        unserved = list(at_close["waiting_customer_ids"])
    else:
        for cid in at_close["waiting_customer_ids"]:
            sid = min(free, key=lambda server: (free[server], server))
            start = free[sid]
            schedule[cid] = (sid, start, start + rows[cid]["unit_work"] / mu_final)
            free[sid] = schedule[cid][2]
    releases = list(free.values()) + draining_ends
    return {
        "schedule": schedule,
        "unserved": unserved,
        "overtime": math.fsum(release - end for release in releases),
        "overrun": max(releases, default=end) - end,
    }


@pytest.mark.parametrize("policy", CLOSING_POLICIES)
@pytest.mark.parametrize("seed", range(15))
def test_closing_matches_an_independent_fcfs_recursion(seed, policy):
    # Overloaded near closing, with a decrease from 4 to 2 at 1:50, so runs close with a line,
    # two accepting servers, and often a draining server.
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("early", 0, 60, 30.0, 10.0), DemandPeriod("late", 60, 120, 36.0, 8.0)]
    segments = [StaffingSegment("a", 0, 60, 3), StaffingSegment("b", 60, 110, 4), StaffingSegment("c", 110, 120, 2)]
    result = simulate_shared_day(horizon, periods, segments, seed=seed, closing_policy=policy)
    reference = independent_closing(result, mu_final=8.0)
    rows = by_id(result)
    assert {cid: (rows[cid]["server_id"], rows[cid]["service_start_hours"], rows[cid]["service_end_hours"])
            for cid in reference["schedule"]} == reference["schedule"]
    assert result["closing"]["unserved_customer_ids"] == reference["unserved"]
    assert result["cost_quantities"]["overtime_server_hours"] == approx(reference["overtime"])
    assert result["closing"]["overrun_hours"] == approx(reference["overrun"])
    assert_sample_path_identities(result)
    assert_conservation_and_identity(result)


def test_arrivals_stop_at_closing():
    with pytest.raises(SharedSegmentError, match="lie in the horizon"):
        simulate_prescribed(*hourly(1), [(1.0, 0.25)], closing_policy=DRAIN)
    result = simulate_shared_day(*hourly(1, lam=50.0, mu=10.0), seed=4, closing_policy=DRAIN)
    assert all(row["arrival_hours"] < 1.0 for row in result["customers"])
    assert result["closing"]["overrun_hours"] > 0  # ρ = 5 builds a backlog that DRAIN serves
    assert not any(event["type"] == "arrival" and event["t"] >= 1.0 for event in result["trace"])


# ── Seeded runs: conservation, identity, identities over many transitions ───


@pytest.mark.parametrize("final_servers", [3, 0])
@pytest.mark.parametrize("seed", range(20))
def test_multi_transition_runs_conserve_customers(seed, final_servers):
    horizon = OperatingHorizon(480, 780)
    periods = [
        DemandPeriod("08", 480, 540, 30.0, 12.0),
        DemandPeriod("09", 540, 600, 0.0, 12.0),
        DemandPeriod("10", 600, 660, 45.0, 15.0),
        DemandPeriod("11", 660, 780, 20.0, 10.0),
    ]
    segments = [
        StaffingSegment("a", 480, 510, 3), StaffingSegment("b", 510, 540, 0),
        StaffingSegment("c", 540, 600, 1), StaffingSegment("d", 600, 615, 4),
        StaffingSegment("e", 615, 660, 2), StaffingSegment("f", 660, 780, final_servers),
    ]
    runs = {
        policy: simulate_shared_day(horizon, periods, segments, seed=seed, closing_policy=policy)
        for policy in CLOSING_POLICIES
    }
    for policy, result in runs.items():
        assert_conservation_and_identity(result)
        assert_sample_path_identities(result)
        assert result["segments"][2]["arrivals"] == 0  # 09:00-10:00 has no demand
        for row in result["segments"]:
            assert row["server_hours_above_schedule"] >= -1e-12
        assert result["closing"]["unserved_possible"] is (policy == HARD_CUTOFF or final_servers == 0)

    # The closing policy changes nothing before closing.
    drain, cutoff = runs[DRAIN], runs[HARD_CUTOFF]
    end = drain["closing"]["closing_hours"]
    assert [(row["arrival_hours"], row["unit_work"]) for row in drain["customers"]] == [
        (row["arrival_hours"], row["unit_work"]) for row in cutoff["customers"]
    ]
    assert time_attributed(drain) == time_attributed(cutoff)
    assert in_horizon(drain["capacity_transitions"]) == in_horizon(cutoff["capacity_transitions"])
    assert drain["drains"] == cutoff["drains"]
    assert drain["closing"]["at_close"] == cutoff["closing"]["at_close"]
    assert [event for event in drain["trace"] if event["t"] < end] == [
        event for event in cutoff["trace"] if event["t"] < end
    ]

    def started_before_closing(result: dict) -> list[dict]:
        return [row for row in result["customers"]
                if row["service_start_hours"] is not None and row["service_start_hours"] < end]

    assert started_before_closing(drain) == started_before_closing(cutoff)
    assert cutoff["closing"]["service_starts_after_close"] == 0
    if final_servers == 0:  # nobody on duty at closing: DRAIN cannot serve the line
        assert drain["closing"]["service_starts_after_close"] == 0
        assert drain["closing"]["unserved_customer_ids"] == cutoff["closing"]["unserved_customer_ids"]
    else:
        assert drain["totals"]["unserved_at_close"] == 0


# ── Statistical checks against independent references ──────────────────────


def replication_stats(values: list[float]) -> tuple[float, float]:
    mean = math.fsum(values) / len(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


@pytest.mark.parametrize("policy", CLOSING_POLICIES)
def test_constant_capacity_matches_erlang_c_within_statistical_error(policy):
    # λ = 40 per hour, μ = 20 per hour per server, c = 3: Lq = 8/9, P(wait) = 4/9, Wq = 1/45 h.
    reference = erlang_reference(40.0, 20.0, 3)
    horizon, periods, segments = OperatingHorizon(0, 1440), [DemandPeriod("d", 0, 1440, 40.0, 20.0)], [
        StaffingSegment("s", 0, 1440, 3)
    ]
    lq, wait_share, wq = [], [], []
    for seed in range(100):
        totals = simulate_shared_day(horizon, periods, segments, seed=seed, closing_policy=policy)["totals"]
        lq.append(totals["time_average_queue"])
        wait_share.append(totals["waited_count"] / totals["service_starts"])
        wq.append(totals["mean_wait_hours"])
    for values, expected in ((lq, reference["Lq"]), (wait_share, reference["P_wait"]), (wq, reference["Wq"])):
        mean, standard_error = replication_stats(values)
        assert abs(mean - expected) <= 4 * standard_error, (mean, expected, standard_error)


def test_arrival_counts_are_poisson_per_period():
    horizon = OperatingHorizon(0, 180)
    periods = [DemandPeriod("a", 0, 60, 30.0, 10.0), DemandPeriod("b", 60, 120, 0.0, 10.0),
               DemandPeriod("c", 120, 180, 12.0, 10.0)]
    segments = [StaffingSegment("a", 0, 60, 10), StaffingSegment("b", 60, 120, 10), StaffingSegment("c", 120, 180, 10)]
    counts: dict[str, list[float]] = {"a": [], "b": [], "c": []}
    for seed in range(300):
        for row in simulate_shared_day(horizon, periods, segments, seed=seed, closing_policy=DRAIN)["segments"]:
            counts[row["segment_id"]].append(float(row["arrivals"]))
    assert set(counts["b"]) == {0.0}
    for key, rate in (("a", 30.0), ("c", 12.0)):
        mean, standard_error = replication_stats(counts[key])
        assert abs(mean - rate) <= 4 * standard_error
        variance = math.fsum((value - mean) ** 2 for value in counts[key]) / (len(counts[key]) - 1)
        # Poisson counts have variance = mean; the dispersion index has SE ≈ sqrt(2/(n-1)).
        assert abs(variance / mean - 1.0) <= 4 * math.sqrt(2 / (len(counts[key]) - 1))


def test_service_times_are_exponential_with_the_starting_period_rate():
    # Ample servers, so service starts at arrival and the starting period is the arrival period.
    horizon = OperatingHorizon(0, 120)
    periods = [DemandPeriod("slow", 0, 60, 60.0, 10.0), DemandPeriod("fast", 60, 120, 60.0, 40.0)]
    segments = [StaffingSegment("slow", 0, 60, 60), StaffingSegment("fast", 60, 120, 60)]
    durations: dict[str, list[float]] = {"slow": [], "fast": []}
    for seed in range(40):
        for row in simulate_shared_day(horizon, periods, segments, seed=seed, closing_policy=DRAIN)["customers"]:
            # Every started service has its full drawn end time, even past the horizon, so
            # in-service customers are included and long services are not selected out.
            if row["service_start_hours"] is not None:
                assert row["wait_hours"] == 0.0
                key = "slow" if row["service_start_hours"] < 1.0 else "fast"
                durations[key].append(row["service_end_hours"] - row["service_start_hours"])
    for key, mu in (("slow", 10.0), ("fast", 40.0)):
        values = durations[key]
        mean = math.fsum(values) / len(values)
        assert abs(mean - 1 / mu) <= 4 * (1 / mu) / math.sqrt(len(values))
        share_above = sum(1 for value in values if value > 1 / mu) / len(values)
        assert abs(share_above - math.exp(-1)) <= 4 * math.sqrt(math.exp(-1) * (1 - math.exp(-1)) / len(values))


# ── Reproducibility ─────────────────────────────────────────────────────────


def test_seeded_runs_are_reproducible_and_seeds_differ():
    args = hourly(2, 1, 3, lam=25.0, mu=12.0)
    first = simulate_shared_day(*args, seed=11, closing_policy=DRAIN)
    again = simulate_shared_day(*args, seed=11, closing_policy=DRAIN)
    other = simulate_shared_day(*args, seed=12, closing_policy=DRAIN)
    assert first == again
    assert first["customers"] != other["customers"]


def test_unseeded_run_records_entropy_that_reproduces_it():
    args = hourly(2, 2, lam=20.0, mu=12.0)
    free = simulate_shared_day(*args, seed=None, closing_policy=HARD_CUTOFF)
    entropy = free["provenance"]["seed_entropy"]
    assert isinstance(entropy, int)
    replay = simulate_shared_day(*args, seed=entropy, closing_policy=HARD_CUTOFF)
    assert replay["customers"] == free["customers"]


# ── Integration with Phase 2, validation, isolation ─────────────────────────


def test_simulates_a_complete_phase_two_plan():
    periods, current = timeline_from_aggregate_rows(NOVAMART_AVERAGE_ROWS)
    horizon = OperatingHorizon(300, 1080)
    logging.disable(logging.CRITICAL)
    try:
        plan = optimize_shared_capacity(horizon, periods, current, CapacityConfig(94.375, 100.0, 0.70, 1, 24))
    finally:
        logging.disable(logging.NOTSET)
    staffing = staffing_from_capacity_result(plan)
    assert [segment.servers for segment in staffing] == [2, 3, 3, 3, 3, 4, 3, 4, 4, 3, 3, 2, 2]
    result = simulate_shared_day(horizon, periods, staffing, seed=3, closing_policy=DRAIN)
    assert_conservation_and_identity(result)
    assert result["totals"]["scheduled_server_hours"] == pytest.approx(39.0)


def test_incomplete_phase_two_plan_is_refused():
    horizon = OperatingHorizon(0, 60)
    periods = [DemandPeriod("p", 0, 60, 8.2143, 4.3068)]
    plan = optimize_shared_capacity(horizon, periods, [StaffingSegment("p", 0, 60, 2)], CapacityConfig(1.0, 1.0, 0.7, 1, 2))
    with pytest.raises(SharedSegmentError, match="no feasible server count in: p"):
        staffing_from_capacity_result(plan)


@pytest.mark.parametrize(
    ("arrivals", "message"),
    [
        ([(1.0, 0.5)], "lie in the horizon"),
        ([(-0.1, 0.5)], "lie in the horizon"),
        ([(0.5, 0.5), (0.25, 0.5)], "earlier than the arrival before it"),
        ([(0.5, 0.0)], "work must be a finite number above 0"),
        ([(0.5, math.nan)], "work must be a finite number above 0"),
        ([(0.5,)], "must be an \\(hour, work\\) pair"),
    ],
)
def test_invalid_prescribed_arrivals(arrivals, message):
    with pytest.raises(SharedSegmentError, match=message):
        simulate_prescribed(*hourly(1), arrivals, closing_policy=DRAIN)


@pytest.mark.parametrize("seed", [-1, 1.5, True])
def test_invalid_seed(seed):
    with pytest.raises(SharedSegmentError, match="seed must be a whole number"):
        simulate_shared_day(*hourly(1), seed=seed, closing_policy=DRAIN)


def test_trace_cap_limits_only_the_trace():
    capped = simulate_shared_day(*hourly(2, lam=30.0, mu=12.0), seed=5, closing_policy=DRAIN, max_trace_events=10)
    full = simulate_shared_day(*hourly(2, lam=30.0, mu=12.0), seed=5, closing_policy=DRAIN)
    assert len(capped["trace"]) == 10 and capped["trace_truncated"] is True
    assert full["trace_truncated"] is False
    assert capped["totals"] == full["totals"]
    assert capped["closing"] == full["closing"]
    assert capped["cost_quantities"] == full["cost_quantities"]
