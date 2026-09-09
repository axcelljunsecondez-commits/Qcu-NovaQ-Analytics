import json
import math
from pathlib import Path

import pandas as pd
import pytest

from backend.api.optimization import OptimizeBatchRequest, OptimizeRequest, optimize_batch
from backend.api.simulation import McRequest
from backend.queueing_engine.services.model_selection import select_model
from backend.queueing_engine.services.optimization import optimize_segment
from backend.queueing_engine.simulation.simulation import (
    mc_simulate_segment,
    simulate_segment,
    validate_with_simulation,
)


def test_minimum_and_wait_constraints():
    result = optimize_segment({'lambda': 8, 'mu': 5, 'c': 2}, min_servers=4, max_servers=5, max_wait_minutes=0)
    assert result['c_optimal'] is None
    assert result['feasibility_status'] == 'NO_FEASIBLE_CONFIGURATION'
    assert 'max_wait_minutes' in result['violated_constraints']
    feasible = optimize_segment({'lambda': 8, 'mu': 5, 'c': 2}, min_servers=4, max_servers=5)
    assert 4 <= feasible['c_optimal'] <= 5
    assert feasible['constraints_passed']


def test_invalid_server_range():
    with pytest.raises(ValueError):
        OptimizeBatchRequest(segments=[], min_servers=5, max_servers=4)


def test_des_busy_time_and_requested_duration():
    result = simulate_segment({'lambda': 100, 'mu': 1, 'c': 1}, sim_hours=2, seed=42, initial_queue_depth=100).to_dict()
    assert result['rho_sim'] == 1.0
    assert result['effective_sim_hours'] == 2
    assert result['measurement_hours'] == 2 - result['warmup_end']


def test_mc_explicit_metadata_and_default():
    assert McRequest(segments=[]).failure_rate_cap == .05
    result = mc_simulate_segment({'lambda': 0, 'mu': 5, 'c': 1}, num_trials=20, seed=42)
    assert result['num_trials'] == 20
    assert result['failure_count'] == 0
    assert result['failure_criterion'] == 'utilization_exceeds_threshold'
    assert result['confidence_level'] == .95
    assert result['failure_rate_cap'] == .05


@pytest.mark.parametrize('target', [.4, .7, .9])
def test_targets_are_hard_constraints(target):
    row = optimize_segment({'lambda': 18, 'mu': 5, 'c': 4}, target_utilization=target, max_servers=12)
    assert row['rho_optimal'] <= target + 1e-12
    assert row['effective_constraints']['target_utilization'] == target


def test_finite_capacity_and_joint_constraints():
    row = optimize_segment({'lambda': 50, 'mu': 5, 'c': 2, 'K': 3}, min_servers=4, max_servers=6)
    assert row['c_optimal'] is None
    assert row['violated_constraints'] == ['server_capacity_bounds']
    row = optimize_segment({'lambda': 8, 'mu': 5, 'c': 2}, max_wait_minutes=1, max_servers=8)
    assert row['Wq_optimal'] * 60 <= 1


def test_api_defaults_match_frontend_generated_configuration():
    options = json.loads(Path('frontend/src/api/planning-defaults.json').read_text())
    request = OptimizeRequest(segment={'lambda': 1, 'mu': 2, 'c': 1})
    assert all(getattr(request, key) == value for key, value in options.items())


def test_validation_preserves_optimizer_metadata_without_merge_collisions():
    row = optimize_batch(OptimizeBatchRequest(segments=[{'time': 't', 'lambda': 5, 'mu': 10, 'c': 2}], min_servers=2), _user=None)['results'][0]
    frame = validate_with_simulation(pd.DataFrame([{**row, 'lambda': row['lambda_']}]), des_sim_hours=.2, mc_trials=10, seed=42)
    assert frame.iloc[0]['selected_model'] == 'M/M/c'
    assert frame.iloc[0]['mc_num_trials'] == 10
    assert frame.iloc[0]['effective_constraints']['min_servers'] == 2
    assert frame.iloc[0]['effective_sim_hours'] == .2


def test_zero_load_and_threshold_boundary(monkeypatch):
    result = simulate_segment({'lambda': 0, 'mu': 5, 'c': 2}, sim_hours=3).to_dict()
    assert result['rho_sim'] == 0
    assert result['effective_sim_hours'] == 3
    from backend.queueing_engine.simulation import simulation
    monkeypatch.setattr(simulation, 'MC_ARRIVAL_NOISE', 0)
    monkeypatch.setattr(simulation, 'MC_SERVICE_NOISE', 0)
    row = mc_simulate_segment({'lambda': 5, 'mu': 10, 'c': 1}, num_trials=20, failure_threshold=.5)
    assert row['failure_count'] == 0  # Strictly exceeds, not equals.
    assert row['failure_rate_ci_upper'] == pytest.approx(3.8416 / (20 + 3.8416), abs=1e-4)
    assert row == mc_simulate_segment({'lambda': 5, 'mu': 10, 'c': 1}, num_trials=20, failure_threshold=.5)


def test_model_family_independent_benchmarks():
    from backend.queueing_engine.models.queue_models import erlang_a, mgc, mgck, mmc, mmck
    # CV=1 reduces the general-service approximation to its exponential baseline.
    assert mgc(3, 2, 2, .25)['Wq'] == pytest.approx(mmc(3, 2, 2)['Wq'])
    assert mgck(3, 2, 2, .25, 4)['Lq'] == pytest.approx(mmck(3, 2, 2, 4)['Lq'])
    weights = [1.0]
    for n in range(1, 5):
        weights.append(weights[-1] * 3 / (min(n, 2) * 2))
    probs = [x / sum(weights) for x in weights]
    assert mmck(3, 2, 2, 4)['Lq'] == pytest.approx(sum(max(n-2, 0) * p for n, p in enumerate(probs)))
    # theta=mu gives death rate n*mu, hence Poisson stationary occupancy.
    expected_lq = sum(max(n-2, 0) * math.exp(-1.5) * 1.5**n / math.factorial(n) for n in range(40))
    assert erlang_a(3, 2, 2, 2)['Lq'] == pytest.approx(expected_lq, abs=1e-8)
    assert select_model(3, 2, 2, variance=.25)['service_cv'] == 1
    assert 'variance supplied' in select_model(3, 2, 2, variance=.25)['selection_reason']


def test_cost_and_feasibility_metadata():
    row = optimize_segment({'lambda': 3, 'mu': 5, 'c': 2, 'server_cost': 123}, min_servers=2, customer_waiting_cost=17, abandonment_rate=0)
    assert row['effective_costs']['server_cost_per_hr'] == 123
    assert row['effective_costs']['customer_waiting_cost'] == 17
    assert row['metric_provenance'] == 'analytical'
    assert row['cost_optimal'] == pytest.approx(row['c_optimal']*123 + 3*row['Wq_optimal']*17)
    changed = optimize_segment({'lambda': 8, 'mu': 5, 'c': 1}, min_servers=2)
    assert changed['selected_model'] == 'M/M/c'


def test_new_snapshot_constraints_are_verified_and_exported(db_engine, client):
    from io import BytesIO

    import openpyxl

    from tests.helpers import create_user, csrf_header, login
    from tests.test_scenario_integrity import snapshot_payload
    create_user(db_engine, 'system@example.com', 'pw')
    login(client, 'system@example.com', 'pw')
    payload = snapshot_payload(client)
    calculation = payload['settings']['calculation']
    calculation['engine_version'] = 'novaq-2026-09-system-v2'
    options = {**calculation['options'], 'min_servers': 2, 'max_wait_minutes': 3}
    calculation['options'] = options
    payload['settings'].update(options)
    payload['results'] = client.post('/optimize/batch', json={'segments': calculation['input_segments'], **options}).json()
    response = client.post('/scenarios', headers=csrf_header(client), json=payload)
    assert response.status_code == 201
    ident = response.json()['scenario']['id']
    exported = client.get(f'/reports/scenarios/{ident}/excel')
    assert exported.status_code == 200
    wb = openpyxl.load_workbook(BytesIO(exported.content), data_only=True)
    cells = [str(c.value) for row in wb['Segments'] for c in row]
    assert any('"min_servers": 2' in value for value in cells)
    calculation['options']['min_servers'] = 3
    payload['settings']['min_servers'] = 3
    assert client.post('/scenarios', headers=csrf_header(client), json=payload).status_code == 422


def test_legacy_snapshot_without_additive_metadata_stays_readable(db_engine, client):
    from tests.helpers import create_user, csrf_header, login
    from tests.test_scenario_integrity import snapshot_payload
    create_user(db_engine, 'legacy@example.com', 'pw')
    login(client, 'legacy@example.com', 'pw')
    payload = snapshot_payload(client)
    added = {'feasibility_status', 'constraints_passed', 'violated_constraints', 'selected_model', 'model_selection_reason', 'model_assumptions', 'service_cv', 'metric_provenance', 'effective_constraints', 'effective_costs', 'explanation'}
    for row in payload['results']['results']:
        for key in added:
            row.pop(key, None)
    response = client.post('/scenarios', headers=csrf_header(client), json=payload)
    assert response.status_code == 201
    saved = response.json()['scenario']
    assert saved['settings']['calculation']['engine_version'] == 'novaq-2026-09-integrity-v1'
    assert saved['results'] == payload['results']
