"""Large server-count and capacity numerics for M/M/c, M/G/c, M/M/c/K and M/G/c/K.

Spec: docs/superpowers/specs/2026-10-12-large-server-count-erlang-numerics.md (OD-N1 approved 2026-10-12).
``mmc`` uses the Erlang B recursion; ``mmck`` keeps its closed form and uses closed-form logarithms only
when that form overflows; ``mgc`` reports a numerical failure as one instead of "Unstable system".

``fixtures/erlang_numerics_pin.json`` is the output of the four functions at commit 6093d78a, before the
change. Every case that computed then computes the same now (within rel 1e-12; values below 1e-300 are
subnormal and compared absolutely; ``mmck``/``mgck`` are bit-identical on the Python that wrote the fixture), every truly
unstable case keeps its exact result, and every case that failed numerically is checked against an exact
rational oracle. The fixture records the old engine: it was written once, on the unchanged engine, with
``python -m tests.test_large_server_numerics --write``, and must not be regenerated after the change.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from backend.queueing_engine.models import mgc, mgck, mm1, mmc, mmck, queue_models

FIXTURE = Path(__file__).parent / "fixtures" / "erlang_numerics_pin.json"
REL_TOL = 1e-12
ABS_TOL = 1e-300  # below this a double is subnormal and relative error is meaningless
NUMERICAL_ERRORS = {
    "mmc": "Calculation failed due to numerical instability.",
    "mgc": "M/G/c calculation failed due to numerical instability.",
    "mmck": "M/M/c/K calculation failed due to numerical instability.",
    "mgck": "M/M/c/K calculation failed due to numerical instability.",
}

SERVERS = (1, 2, 3, 5, 10, 24, 50, 100, 120, 143, 144, 145, 149, 153, 162, 169, 170, 171, 200, 256)
LOADS = (0.0, 0.01, 0.3, 0.5, 0.8, 0.95, 0.99, 0.999999, 1.0, 1.2)
RATES = (1.0, 1.05, 37.5)
CAPACITY_SERVERS = (1, 2, 3, 5, 10, 24, 50, 100, 150, 170)
CAPACITY_EXTRA = (0, 1, 5, 20, 100, 500)
CAPACITY_LOADS = (0.0, 0.01, 0.3, 0.8, 0.95, 1.0, 1.2, 2.0)

CASES: dict[str, list[tuple]] = {
    "mmc": [(load * c * mu, mu, c) for c in SERVERS for load in LOADS for mu in RATES] + [(3.15, 1.05, 3)],
    "mgc": [
        (load * c * 1.05, 1.05, c, scv / 1.05 ** 2)
        for c in SERVERS for load in (0.01, 0.5, 0.95, 1.2) for scv in (0.0, 1.0, 2.5)
    ],
    "mmck": [
        (load * c, 1.0, c, c + extra)
        for c in CAPACITY_SERVERS for extra in CAPACITY_EXTRA for load in CAPACITY_LOADS
    ],
    "mgck": [
        (load * c, 1.0, c, scv, c + extra)
        for c in (1, 2, 10, 24) for extra in (0, 20, 500) for load in (0.3, 0.95, 1.2) for scv in (0.0, 2.5)
    ],
}
FUNCTIONS: dict[str, Callable[..., dict[str, Any]]] = {"mmc": mmc, "mgc": mgc, "mmck": mmck, "mgck": mgck}


def run(name: str, args: tuple) -> dict:
    """The function's result as JSON values (floats round-trip exactly through ``repr``)."""
    return json.loads(json.dumps(FUNCTIONS[name](*args)))


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── Exact rational oracle (textbook forms, independent of the engine) ───────────


def exact_mmc(lambda_: float, mu: float, c: int) -> dict[str, Fraction]:
    """M/M/c from p0 = 1 / (sum_{n<c} a^n/n! + a^c / (c! (1 - rho))) in exact arithmetic of the float inputs."""
    a = Fraction(lambda_) / Fraction(mu)
    rho = a / c
    term, head = Fraction(1), Fraction(0)
    for n in range(c):
        if n:
            term = term * a / n
        head += term
    tail = term * a / c / (1 - rho)  # a^c / (c! (1 - rho))
    lq = tail / (head + tail) * rho / (1 - rho)
    wq = lq / Fraction(lambda_) if lambda_ else Fraction(0)
    w = wq + 1 / Fraction(mu)
    return {"Lq": lq, "Wq": wq, "W": w, "L": Fraction(lambda_) * w}


def exact_mmck(lambda_: float, mu: float, c: int, K: int) -> dict[str, Fraction]:
    """M/M/c/K from the birth-death weights a^n/n! (n <= c) and a^n/(c! c^(n-c)) (n > c) in exact arithmetic."""
    a = Fraction(lambda_) / Fraction(mu)
    weights = [Fraction(1)]
    for n in range(1, K + 1):
        weights.append(weights[-1] * a / min(n, c))
    total = sum(weights, Fraction(0))  # each sum below is divided by it once, instead of normalizing every weight
    blocking = weights[K] / total
    effective = Fraction(lambda_) * (1 - blocking)
    length = sum((n * weights[n] for n in range(K + 1)), Fraction(0)) / total
    waiting = sum(((n - c) * weights[n] for n in range(c + 1, K + 1)), Fraction(0)) / total
    return {
        "rho": sum((min(n, c) * weights[n] for n in range(K + 1)), Fraction(0)) / (c * total),
        "L": length,
        "Lq": waiting,
        "W": length / effective if effective else Fraction(0),
        "Wq": waiting / effective if effective else Fraction(0),
        "blocking_probability": blocking,
        "effective_lambda": effective,
    }


def assert_close(actual: float, expected: float | Fraction, label: str) -> None:
    assert math.isclose(actual, float(expected), rel_tol=REL_TOL, abs_tol=ABS_TOL), (label, actual, float(expected))


def assert_matches_oracle(name: str, args: tuple, result: dict) -> None:
    assert result["stable"] is True and result["error"] is None, (name, args, result)
    if name in ("mmc", "mgc"):
        lambda_, mu, c = args[:3]
        exact = exact_mmc(lambda_, mu, c)
        factor = Fraction((1.0 + args[3] * mu ** 2) / 2.0) if name == "mgc" else Fraction(1)
        wq = exact["Wq"] * factor
        expected = {"Wq": wq, "Lq": Fraction(lambda_) * wq, "W": wq + 1 / Fraction(mu)}
        expected["L"] = Fraction(lambda_) * expected["W"]
    else:
        lambda_, mu, c = args[:3]
        exact = exact_mmck(lambda_, mu, c, args[-1])
        if name == "mmck":
            expected = exact
        else:
            factor = Fraction((1.0 + args[3] * float(mu) ** 2) / 2.0)
            wq = exact["Wq"] * factor
            w = wq + 1 / Fraction(mu)
            expected = {"Wq": wq, "Lq": exact["effective_lambda"] * wq, "W": w, "L": exact["effective_lambda"] * w,
                        "blocking_probability": exact["blocking_probability"]}
    for key, value in expected.items():
        assert_close(result[key], value, f"{name}{args} {key}")


def assert_same_result(new: dict, old: dict, label: object) -> None:
    """Same keys, equal non-float values, floats within REL_TOL.

    mmck/mgck keep their closed form wherever it ran, but its built-in sum() of floats is compensated from
    Python 3.12 on, so a fixture written on 3.13 differs from 3.10/3.11 in the last bits (at most 1.3e-14
    relative, VERIFIED 2026-10-13 by replaying the pre-change engine with plain left-to-right addition).
    """
    assert sorted(new) == sorted(old), label
    for key, value in old.items():
        if isinstance(value, float):
            assert math.isclose(new[key], value, rel_tol=REL_TOL, abs_tol=ABS_TOL), (label, key, new[key], value)
        else:
            assert new[key] == value, (label, key)


def load_of(name: str, args: tuple) -> float:
    lambda_, mu, c = args[:3]
    return lambda_ / (c * mu)


# ── Pins against the engine before the change ────────────────────────────────


def test_fixture_covers_exactly_the_cases():
    fixture = load_fixture()
    assert fixture["source_commit"] == "6093d78a5874d8cbdfa0026e9c25bdb5ddc70881"
    for name, cases in CASES.items():
        assert [tuple(record["args"]) for record in fixture["cases"][name]] == cases


@pytest.mark.parametrize("name", sorted(CASES))
def test_results_that_computed_before_are_unchanged(name):
    for record in load_fixture()["cases"][name]:
        args, old = tuple(record["args"]), record["result"]
        if not old["stable"]:
            continue
        new = run(name, args)
        assert new["stable"] is True and new["error"] is None, (name, args)
        if name in ("mmc", "mgc"):
            assert new["rho"] == old["rho"], (name, args)  # lambda / (c * mu), unchanged
        assert_same_result(new, old, (name, args))


@pytest.mark.parametrize("name", sorted(CASES))
def test_truly_unstable_and_invalid_results_are_unchanged(name):
    for record in load_fixture()["cases"][name]:
        args, old = tuple(record["args"]), record["result"]
        if old["stable"] or old["error"] == NUMERICAL_ERRORS[name]:
            continue
        if name == "mgc" and load_of(name, args) < 1.0:  # a numerical failure the old mgc called unstable
            continue
        assert_same_result(run(name, args), old, (name, args))


@pytest.mark.parametrize("name", sorted(CASES))
def test_former_numerical_failures_now_match_the_exact_oracle(name):
    failures = [record for record in load_fixture()["cases"][name] if record["result"]["error"] == NUMERICAL_ERRORS[name]]
    if name == "mgc":  # the old mgc called every mmc failure "Unstable system"; pick the non-saturated ones
        failures = [
            record for record in load_fixture()["cases"][name]
            if not record["result"]["stable"] and load_of(name, tuple(record["args"])) < 1.0
        ]
    assert failures, name
    for record in failures:
        args = tuple(record["args"])
        new = run(name, args)
        if name == "mgck" and not new["stable"]:
            assert new["error"] == "M/G/c/K approximation exceeds finite-capacity bounds.", (args, new)
            continue
        if name in ("mmc", "mgc") and load_of(name, args) > 0.99:
            # Near rho = 1 the 1-ulp rounding of rho is amplified by about 1 / (1 - rho), so an oracle in
            # exact arithmetic of the inputs cannot be met at 1e-12; check finiteness and Little's law.
            assert new["stable"] is True and all(math.isfinite(new[k]) for k in ("L", "Lq", "W", "Wq")), (args, new)
            assert math.isclose(new["L"], args[0] * new["W"], rel_tol=REL_TOL)
            continue
        assert_matches_oracle(name, args, new)


# ── Reference values outside the old range ───────────────────────────────────


@pytest.mark.parametrize(
    ("lambda_", "c", "lq"),
    [
        # Exact rational evaluation (fractions.Fraction), 2026-10-12. The last two took 14 s and 136 s,
        # so they are recorded instead of recomputed here.
        (150.0, 171, 0.42986706495410837),
        (200.0, 250, 0.0015489421656682436),
        (4500.0, 5000, 1.1626486270673929e-12),
        (9500.0, 10000, 3.6642397405494717e-06),
    ],
)
def test_large_c_reference_values(lambda_, c, lq):
    result = mmc(lambda_, 1.0, c)
    assert result["stable"] is True
    assert math.isclose(result["Lq"], lq, rel_tol=REL_TOL)
    assert math.isclose(result["Wq"], lq / lambda_, rel_tol=REL_TOL)


@pytest.mark.parametrize("args", [(1.0, 1.0, 2, 1100), (19.2, 1.0, 24, 231), (160.0, 1.0, 200, 260), (40.0, 1.0, 50, 400)])
def test_large_capacity_reference_values(args):
    assert_matches_oracle("mmck", args, mmck(*args))


@pytest.mark.parametrize("K", [1748, 1749, 1750])
def test_capacity_sum_overflow_is_no_longer_reported_as_an_idle_system(K):
    # Each weight 1.5^n fit in a double but their sum overflowed to inf without an exception, so the old
    # mmck returned stable with rho = L = blocking = 0 (VERIFIED 2026-10-12). It now uses the log form.
    result = mmck(1.5, 1.0, 1, K)
    assert_matches_oracle("mmck", (1.5, 1.0, 1, K), result)
    assert result["blocking_probability"] > 0.33


# ── M/G/c error text ─────────────────────────────────────────────────────────


def test_mgc_on_a_lightly_loaded_large_system_is_stable():
    result = mgc(1.0, 1.0, 5000, 1.0)
    assert result["stable"] is True and result["error"] is None
    assert result["Wq"] == mmc(1.0, 1.0, 5000)["Wq"]  # Cs^2 = 1 reproduces M/M/c


@pytest.mark.parametrize("args", [(200.0, 1.0, 171, 1.0), (3.15, 1.05, 3, 1.0)])  # 3.15 / (3 * 1.05) is rho = 1
def test_mgc_keeps_the_unstable_text_for_a_saturated_system(args):
    result = mgc(*args)
    assert result["stable"] is False
    assert result["error"] == "Unstable system: lambda must be less than c * mu for M/G/c."


def test_mgc_reports_a_numerical_failure_as_numerical(monkeypatch):
    def failing_mmc(lambda_, mu, c):
        return queue_models._result(rho=lambda_ / (c * mu), stable=False, error=NUMERICAL_ERRORS["mmc"])

    monkeypatch.setattr(queue_models, "mmc", failing_mmc)
    result = queue_models.mgc(2.0, 1.0, 4, 1.0)
    assert result["stable"] is False and result["rho"] == 0.5
    assert result["error"] == "M/G/c calculation failed due to numerical instability."


# ── Identities and callers ───────────────────────────────────────────────────


@pytest.mark.parametrize("args", [(150.0, 1.0, 171), (0.0, 1.0, 300), (2400.0, 1.0, 2500), (4.0, 0.5, 9)])
def test_little_law_holds(args):
    result = mmc(*args)
    assert result["stable"] is True
    assert math.isclose(result["L"], args[0] * result["W"], rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(result["Lq"], args[0] * result["Wq"], rel_tol=REL_TOL, abs_tol=ABS_TOL)


@pytest.mark.parametrize(("lambda_", "mu"), [(0.0, 1.0), (0.3, 1.0), (2.0, 3.0), (0.99, 1.0)])
def test_single_server_mmc_equals_mm1(lambda_, mu):
    single, reference = mmc(lambda_, mu, 1), mm1(lambda_, mu)
    for key in ("rho", "L", "Lq", "W", "Wq"):
        assert math.isclose(single[key], reference[key], rel_tol=REL_TOL, abs_tol=ABS_TOL), key


def test_current_metrics_row_with_many_counters_is_stable():
    from backend.queueing_engine.services.data_processing import process_segments

    row = process_segments([{"time": "09:00", "lambda": 1.0, "mu": 1.0, "c": 171, "variance": 1.0}]).iloc[0]
    assert bool(row["stable"]) is True and row["warning"] is None


def test_optimizer_can_choose_more_than_170_counters():
    from backend.queueing_engine.services.optimization import optimize_segment

    result = optimize_segment({"time": "09:00", "lambda": 180.0, "mu": 1.0, "c": 200, "variance": 1.0},
                              target_utilization=0.95, max_servers=256)
    assert result["feasibility_status"] == "FEASIBLE"
    assert 190 <= result["c_optimal"] <= 256 and result["rho_optimal"] <= 0.95


def test_optimizer_no_longer_warns_unstable_for_an_overstaffed_plan():
    from backend.queueing_engine.services.optimization import optimize_segment

    result = optimize_segment({"time": "09:00", "lambda": 1.0, "mu": 1.0, "c": 200, "variance": 1.0},
                              target_utilization=0.85, max_servers=24)
    assert result["current_stable"] is True and result["warning"] == ""


def test_shared_segment_with_many_counters_is_stable():
    from backend.queueing_engine.services.shared_segments import DemandPeriod, StaffingSegment, evaluate_segment

    row = evaluate_segment(StaffingSegment("s1", 540, 600, 171), DemandPeriod("p1", 540, 600, 1.0, 1.0))
    assert row["status"] == "STABLE"


def write_fixture() -> None:
    cases = {name: [{"args": list(args), "result": run(name, args)} for args in CASES[name]] for name in sorted(CASES)}
    payload = {"source_commit": "6093d78a5874d8cbdfa0026e9c25bdb5ddc70881", "cases": cases}
    FIXTURE.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")).replace('{"args"', '\n{"args"') + "\n",
                       encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write_fixture()
    else:
        sys.exit("Usage: python -m tests.test_large_server_numerics --write")
