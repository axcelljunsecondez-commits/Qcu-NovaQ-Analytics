"""U10 F1/F2: one shared line from customer records is checked with its recorded service times.

Spec: docs/superpowers/specs/2026-10-13-u10-f1-f2-recorded-service-checks.md.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.db.models import AnalysisProject, Dataset, Scenario
from backend.queueing_engine.models import mgc
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segment,
    simulate_segment,
    simulate_segments_with_trace,
    simulation_coverage,
    validate_with_simulation,
)
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

DURATIONS = [0.02, 0.03, 0.05, 0.04, 0.11, 0.025, 0.06, 0.035]  # hours, recorded per customer


def _moments(samples):
    mean = math.fsum(samples) / len(samples)
    return mean, math.fsum((value - mean) ** 2 for value in samples) / len(samples)


def _recorded(lam=40.0, c=3, samples=DURATIONS, **extra):
    mean, variance = _moments(samples)
    return {"time": "p", "lambda": lam, "mu": 1 / mean, "c": c, "variance": variance,
            "service_time_source": "empirical", "service_samples_hours": list(samples), **extra}


def test_m_g_c_is_simulated_only_with_matching_recorded_durations():
    assert simulation_coverage(_recorded()) == ("M/G/c", None)
    without = {key: value for key, value in _recorded().items() if key != "service_samples_hours"}
    name, problem = simulation_coverage(without)
    assert name == "M/G/c" and "recorded service times" in problem and "no service-time distribution is assumed" in problem
    assert "do not match" in simulation_coverage({**_recorded(), "mu": 1 / 0.05})[1]
    assert "do not match" in simulation_coverage({**_recorded(), "variance": 0.01})[1]
    for bad in ([0.02, -0.01], [0.02, float("nan")], [0.02, True], []):
        assert simulation_coverage({**_recorded(), "service_samples_hours": bad})[1] is not None
    for bad in ([0.02, -0.01], [0.02, True]):  # refused even when the plan's moments match them
        assert simulation_coverage(_recorded(samples=bad))[1] is not None
    assert simulation_coverage({**_recorded(), "service_time_source": "estimated"})[1] is not None


def test_constant_durations_are_accepted_with_zero_variance():
    # Ingestion stores the population variance; for equal durations it is 0 while the float mean is
    # only within rounding of each value.
    assert simulation_coverage({**_recorded(samples=[0.05] * 6), "variance": 0.0}) == ("M/G/c", None)


def test_every_simulated_service_time_is_a_recorded_duration():
    result = simulate_segments_with_trace([_recorded(lam=30.0)], sim_hours=3.0, seed=5, max_events=4000)
    starts = {(event["customer_id"]): event["t"] for event in result["trace"] if event["type"] == "service_start"}
    services = [event["t"] - starts[event["customer_id"]] for event in result["trace"]
                if event["type"] == "service_end" and event["customer_id"] in starts]
    assert len(services) > 50
    assert all(any(abs(service - value) < 1e-5 for value in DURATIONS) for service in services)
    assert result["results"][0]["selected_model"] == "M/G/c" and result["results"][0]["simulation_supported"] is True


def test_m_d_1_wait_matches_the_exact_formula():
    # Every recorded duration 3 minutes, utilization 0.8: exact Wq = rho * d / (2 (1 - rho)) = 6 minutes.
    segment = _recorded(lam=0.8 / 0.05, c=1, samples=[0.05] * 10)
    waits = [simulate_segment(segment, sim_hours=3000.0, seed=seed).Wq_sim for seed in range(1, 6)]
    assert math.fsum(waits) / len(waits) * 60 == pytest.approx(6.0, rel=0.03)


def test_exponential_runs_ignore_durations_unless_the_model_is_m_g_c():
    plain = {"time": "p", "lambda": 30.0, "mu": 12.0, "c": 3}
    with_durations = {**plain, "service_time_source": "empirical", "service_samples_hours": DURATIONS}
    assert simulate_segment(plain, sim_hours=50.0, seed=9).to_dict() == simulate_segment(
        with_durations, sim_hours=50.0, seed=9).to_dict()


def test_monte_carlo_pass_fail_equals_m_m_c_and_the_wait_scales_with_the_service_rate():
    segment = _recorded(lam=60.0, c=3)
    exponential = {key: segment[key] for key in ("time", "lambda", "mu", "c")}
    general = mc_simulate_segment(segment, num_trials=800, seed=21)
    markov = mc_simulate_segment(exponential, num_trials=800, seed=21)
    assert general["selected_model"] == "M/G/c" and general["simulation_supported"] is True
    for key in ("failure_count", "failure_rate", "rho_mean", "rho_p95", "status", "failure_rate_ci_upper"):
        assert general[key] == markov[key]
    # A rescaled service rate keeps the squared coefficient of variation, so every trial's
    # Allen-Cunneen factor is the same and the mean waits differ by exactly that factor.
    factor = (1 + segment["variance"] * segment["mu"] ** 2) / 2
    assert general["Wq_mean"] == pytest.approx(markov["Wq_mean"] * factor, rel=1e-4)
    assert mgc(60.0, segment["mu"], 3, segment["variance"])["rho"] == pytest.approx(60.0 / (3 * segment["mu"]))


def test_validation_simulates_the_plan_model_and_does_not_store_the_durations():
    mean, variance = _moments(DURATIONS)
    frame = pd.DataFrame([{"time": "p", "lambda": 40.0, "mu": 1 / mean, "c_optimal": 3, "variance": variance,
                           "service_time_source": "empirical", "service_samples_hours": DURATIONS}])
    rows = validate_with_simulation(frame, des_sim_hours=20.0, mc_trials=200, seed=3).to_dict("records")
    assert rows[0]["selected_model"] == "M/G/c" and rows[0]["simulation_supported"] is True
    assert "service_samples_hours" not in rows[0] and "service_time_source" not in rows[0]


def test_durations_come_only_from_one_dataset_row_with_the_period_label():
    from types import SimpleNamespace

    from backend.api.workflow import _attach_recorded_service

    row = {"time": "08:00", "service_time_source": "empirical", "service_samples_hours": DURATIONS}
    one = {"time": "08:00"}
    _attach_recorded_service(one, SimpleNamespace(normalized_json=[row, {**row, "time": "09:00"}]))
    assert one["service_samples_hours"] == DURATIONS
    for rows in ([row, dict(row)], [{**row, "time": "09:00"}]):  # ambiguous or missing label
        segment = {"time": "08:00"}
        _attach_recorded_service(segment, SimpleNamespace(normalized_json=rows))
        assert "service_samples_hours" not in segment


def _customer_record_plan(db_engine, email: str, with_durations: bool) -> tuple[int, int]:
    """A shared line from customer records: its period carries a variance and, here, its durations."""
    mean, variance = _moments(DURATIONS)
    user = create_user(db_engine, email, "pw")
    row = {"time": "08:00-09:00", "lambda": 40.0, "mu": 1 / mean, "c": 3, "variance": variance}
    stored = {**row, **({"service_time_source": "empirical", "service_samples_hours": DURATIONS} if with_durations else {})}
    with make_sessionmaker(db_engine)() as db:
        analysis = AnalysisProject(
            user_id=user.id, name="Records line",
            queue_setup_json={"queue_structure": "shared_queue", "fixed_server_count": 3, "staffing_varies_by_period": False,
                              "capacity_mode": "unlimited", "total_system_capacity": None,
                              "abandonment_mode": "not_modeled", "patience_rate_per_hour": None},
            setup_status="ready")
        db.add(analysis)
        db.flush()
        dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Records", source_filename="records.csv",
                          source_format="csv", row_count=1, normalized_json=[stored],
                          validation_report_json={"ok": True, "message": "Input data is valid."})
        db.add(dataset)
        db.flush()
        scenario = Scenario(
            user_id=user.id, analysis_id=analysis.id, dataset_id=dataset.id, name="Records plan",
            settings_json={"calculation": {"schema_version": 1, "engine_version": "novaq-2026-09-system-v2",
                                           "input_segments": [row], "options": {}, "what_if_multiplier": 1,
                                           "calculated_at": "2026-10-13T00:00:00+00:00"}},
            results_json={"results": [{
                "time": "08:00-09:00", "lambda": 40.0, "mu": 1 / mean, "c_current": 4, "c_optimal": 3,
                "rho_current": 0.4, "rho_optimal": 0.55, "Wq_current": 0.001, "Wq_optimal": 0.01,
                "Lq_current": 0.01, "Lq_optimal": 0.1, "cost_current": 500, "cost_optimal": 400,
                "current_stable": True, "optimized_stable": True, "service_cv": math.sqrt(variance) / mean}]})
        db.add(scenario)
        db.commit()
        return analysis.id, scenario.id


def _run_chain(client, analysis_id: int, scenario_id: int) -> dict:
    headers = csrf_header(client)
    assert client.post(f"/analyses/{analysis_id}/workflow/selection", headers=headers,
                       json={"scenario_id": scenario_id}).status_code == 200
    des = client.post(f"/analyses/{analysis_id}/workflow/simulation/des", headers=headers,
                      json={"sim_hours": 24, "max_events": 200, "seed": 7})
    mc = client.post(f"/analyses/{analysis_id}/workflow/simulation/mc", headers=headers,
                     json={"num_trials": 500, "seed": 7})
    validation = client.post(f"/analyses/{analysis_id}/workflow/simulation/validation", headers=headers,
                             json={"des_sim_hours": 24, "mc_trials": 2000, "seed": 7})
    decision = client.post(f"/analyses/{analysis_id}/workflow/decision", headers=headers)
    return {"des": des.json()["evidence"]["result"]["results"][0],
            "mc": mc.json()["evidence"]["result"]["results"][0],
            "validation": validation.json()["evidence"]["result"]["results"][0],
            "decision": decision.json()["decision"]}


def test_a_customer_record_plan_reaches_a_decision_through_its_recorded_service_times(db_engine, client):
    analysis_id, scenario_id = _customer_record_plan(db_engine, "records@example.com", with_durations=True)
    login(client, "records@example.com", "pw")
    chain = _run_chain(client, analysis_id, scenario_id)
    for row in (chain["des"], chain["mc"], chain["validation"]):
        assert row["selected_model"] == "M/G/c" and row["simulation_supported"] is True
    assert "service_samples_hours" not in chain["validation"]
    assert chain["decision"]["status"] != "insufficient_evidence", chain["decision"]


def test_without_recorded_durations_the_check_refuses_instead_of_using_m_m_c(db_engine, client):
    analysis_id, scenario_id = _customer_record_plan(db_engine, "variance-only@example.com", with_durations=False)
    login(client, "variance-only@example.com", "pw")
    chain = _run_chain(client, analysis_id, scenario_id)
    assert chain["validation"]["selected_model"] == "M/G/c"  # before U10 F2 this was checked as M/M/c
    assert chain["validation"]["simulation_supported"] is False
    assert "no service-time distribution is assumed" in chain["validation"]["validation_reason"]
    assert chain["decision"]["status"] == "insufficient_evidence"
