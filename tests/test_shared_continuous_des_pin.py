"""Whole-output pin for the anonymous continuous shared-queue DES (Phase 5B-4.0).

The hand-computed cases in ``test_shared_continuous_des.py`` pin individual behaviors. This file
pins the complete result dictionary of ``simulate_prescribed`` on fixed, prescribed arrivals:
customers, segments, totals, capacity transitions, drains, closing, cost quantities, the trace,
and the provenance text. Any change to the anonymous engine's output fails here, so the
named-employee work (Phase 5B-4) cannot change it unnoticed.

No random numbers are involved: ``simulate_prescribed`` draws nothing, and every input time and
unit work amount is binary-exact. The expected dictionaries in
``fixtures/shared_continuous_des_output_pin.json`` are the engine's output at commit d5723aba
(engine version novaq-shared-continuous-des-v2). The customer schedule and capacity transitions of
the main case were also derived by hand, and ``test_transitions_case_matches_hand_derivation``
checks them without the fixture.

Regenerate the fixture only for an authorized, documented change to the anonymous engine:
``python -m tests.test_shared_continuous_des_pin --write``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from backend.queueing_engine.services.shared_segments import DemandPeriod, OperatingHorizon, StaffingSegment
from backend.queueing_engine.simulation.shared_continuous_des import (
    DRAIN,
    ENGINE_VERSION,
    HARD_CUTOFF,
    simulate_prescribed,
)

FIXTURE = Path(__file__).parent / "fixtures" / "shared_continuous_des_output_pin.json"

# Main case, 4 hours. μ = 2 for 0-2 h, μ = 4 for 2-4 h (no arrivals 2-3 h). Staffing 2, 3, 1, 3,
# 0, 2 servers: a new server, idle close before drain, reactivation before reopening, a drain
# into a closed segment, ties at boundaries, completions exactly at closing, and a backlog at
# closing that DRAIN serves at the final μ and HARD_CUTOFF records as unserved.
TRANSITIONS = (
    OperatingHorizon(0, 240),
    [
        DemandPeriod("p1", 0, 120, 2.0, 2.0),
        DemandPeriod("p2", 120, 180, 0.0, 4.0),
        DemandPeriod("p3", 180, 240, 2.0, 4.0),
    ],
    [
        StaffingSegment("s1", 0, 60, 2),
        StaffingSegment("s2", 60, 90, 3),
        StaffingSegment("s3", 90, 120, 1),
        StaffingSegment("s4", 120, 150, 3),
        StaffingSegment("s5", 150, 180, 0),
        StaffingSegment("s6", 180, 240, 2),
    ],
    [
        (0.125, 0.5), (0.25, 1.5), (0.25, 0.25), (0.5, 0.75), (0.75, 1.0), (1.0, 0.5),
        (1.125, 0.5), (1.25, 2.0), (1.4375, 1.0), (1.5, 0.25), (1.75, 2.5), (3.0, 1.0),
        (3.5, 1.0), (3.5, 2.0), (3.625, 1.0), (3.8125, 1.0), (3.875, 0.5), (3.9375, 0.5),
    ],
)

# Nobody accepts customers at closing: server 1 drains across closing and two customers wait.
NO_ONE_ON_DUTY = (
    OperatingHorizon(0, 120),
    [DemandPeriod("d", 0, 120, 1.0, 1.0)],
    [StaffingSegment("open", 0, 60, 2), StaffingSegment("closed", 60, 120, 0)],
    [(0.25, 2.0), (0.5, 0.25), (1.0, 0.5), (1.25, 0.5)],
)

# No customers: empty means, zero busy time, and no utilization for a segment with no servers.
NO_ARRIVALS: tuple[Any, ...] = (
    OperatingHorizon(0, 60),
    [DemandPeriod("d", 0, 60, 1.0, 1.0)],
    [StaffingSegment("open", 0, 30, 1), StaffingSegment("closed", 30, 60, 0)],
    [],
)

CASES: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "transitions_drain": (TRANSITIONS, {"closing_policy": DRAIN}),
    "transitions_hard_cutoff": (TRANSITIONS, {"closing_policy": HARD_CUTOFF}),
    "transitions_drain_trace_cap_7": (TRANSITIONS, {"closing_policy": DRAIN, "max_trace_events": 7}),
    "no_one_on_duty_drain": (NO_ONE_ON_DUTY, {"closing_policy": DRAIN}),
    "no_one_on_duty_hard_cutoff": (NO_ONE_ON_DUTY, {"closing_policy": HARD_CUTOFF}),
    "no_arrivals_drain": (NO_ARRIVALS, {"closing_policy": DRAIN}),
    "no_arrivals_hard_cutoff": (NO_ARRIVALS, {"closing_policy": HARD_CUTOFF}),
}


def run_case(name: str) -> dict:
    """The case's full result as JSON values (floats round-trip exactly through ``repr``)."""
    (horizon, periods, segments, arrivals), options = CASES[name]
    return json.loads(json.dumps(simulate_prescribed(horizon, periods, segments, arrivals, **options)))


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_covers_exactly_the_cases():
    fixture = load_fixture()
    assert fixture["engine_version"] == ENGINE_VERSION
    assert sorted(fixture["cases"]) == sorted(CASES)


@pytest.mark.parametrize("name", sorted(CASES))
def test_whole_output_matches_the_pin(name):
    expected = load_fixture()["cases"][name]
    actual = run_case(name)
    assert sorted(actual) == sorted(expected)
    for key in expected:  # one key at a time, so a failure names the part that changed
        assert actual[key] == expected[key], key


def test_transitions_case_matches_hand_derivation():
    drain, cutoff = run_case("transitions_drain"), run_case("transitions_hard_cutoff")
    # (server, service start, service end) per customer, derived by hand from the event order.
    schedule = [
        (1, 0.125, 0.375), (2, 0.25, 1.0), (1, 0.375, 0.5), (1, 0.5, 0.875), (1, 0.875, 1.375),
        (2, 1.0, 1.25), (3, 1.125, 1.375), (2, 1.25, 2.25), (1, 1.4375, 1.9375), (1, 1.9375, 2.0625),
        (3, 2.0, 2.625), (1, 3.0, 3.25), (1, 3.5, 3.75), (2, 3.5, 4.0), (1, 3.75, 4.0),
    ]
    after_close = [(1, 4.0, 4.25), (2, 4.0, 4.125), (2, 4.125, 4.25)]
    served = [(row["server_id"], row["service_start_hours"], row["service_end_hours"]) for row in drain["customers"]]
    assert served == schedule + after_close
    assert [
        (row["server_id"], row["service_start_hours"], row["service_end_hours"]) for row in cutoff["customers"][:15]
    ] == schedule
    assert [(row["customer_id"], row["unserved_reason"]) for row in cutoff["customers"][15:]] == [
        (16, "hard_cutoff"), (17, "hard_cutoff"), (18, "hard_cutoff")
    ]
    in_horizon = [
        (0.0, "open", 1), (0.0, "open", 2), (1.0, "open", 3), (1.5, "close", 3), (1.5, "drain_start", 2),
        (2.0, "reactivate", 2), (2.0, "open", 3), (2.5, "close", 2), (2.5, "close", 1), (2.5, "drain_start", 3),
        (2.625, "drain_complete", 3), (3.0, "open", 1), (3.0, "open", 2),
    ]
    assert [(t["t"], t["kind"], t["server_id"]) for t in drain["capacity_transitions"]] == in_horizon + [
        (4.25, "close", 1), (4.25, "close", 2)
    ]
    assert [(t["t"], t["kind"], t["server_id"]) for t in cutoff["capacity_transitions"]] == in_horizon + [
        (4.0, "close", 1), (4.0, "close", 2)
    ]
    for result in (drain, cutoff):
        assert result["closing"]["at_close"] == {
            "waiting_customer_ids": [16, 17, 18], "in_service_customer_ids": [],
            "accepting_server_ids": [1, 2], "draining_server_ids": [],
        }
    assert (drain["closing"]["overrun_hours"], cutoff["closing"]["overrun_hours"]) == (0.25, 0.0)


def write_fixture() -> None:
    cases = {name: run_case(name) for name in sorted(CASES)}
    payload = {"engine_version": ENGINE_VERSION, "cases": cases}
    FIXTURE.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write_fixture()
    else:
        sys.exit("Usage: python -m tests.test_shared_continuous_des_pin --write")
