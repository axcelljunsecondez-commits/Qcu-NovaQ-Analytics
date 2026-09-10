from __future__ import annotations

import copy

from tests.helpers import create_user, csrf_header, login


def snapshot_payload(client):
    segments = [{"time": "t", "lambda": 5, "mu": 10, "c": 2}]
    options = {"max_servers": 4, "target_utilization": .7}
    rows = client.post('/optimize/batch', json={"segments": segments, **options}).json()['results']
    return {"name": "snapshot", "settings": {**options, "calculation": {
        "schema_version": 1, "engine_version": "novaq-2026-09-integrity-v1",
        "input_segments": segments, "options": options, "what_if_multiplier": 1,
        "calculated_at": "2026-09-06T00:00:00Z",
    }}, "results": {"results": rows}}


def test_snapshot_outputs_are_verified_and_immutable(db_engine, client):
    create_user(db_engine, 'u@example.com', 'pw')
    login(client, 'u@example.com', 'pw')
    payload = snapshot_payload(client)
    forged = copy.deepcopy(payload)
    forged['results']['results'][0]['cost_optimal'] = 0
    assert client.post('/scenarios', headers=csrf_header(client), json=forged).status_code == 422
    response = client.post('/scenarios', headers=csrf_header(client), json=payload)
    assert response.status_code == 201
    saved = response.json()['scenario']
    assert saved['provenance'] == 'verified_snapshot'
    url = f"/scenarios/{saved['id']}"
    assert client.patch(url, headers=csrf_header(client), json={"results": {}}).status_code == 409
    assert client.patch(url, headers=csrf_header(client), json={"settings": {}}).status_code == 409
    assert client.patch(url, headers=csrf_header(client), json={"name": "renamed"}).status_code == 200
    assert client.get(url).json()['scenario']['results'] == payload['results']


def test_legacy_scenarios_do_not_claim_reproducibility(db_engine, client):
    create_user(db_engine, 'u@example.com', 'pw')
    login(client, 'u@example.com', 'pw')
    saved = client.post('/scenarios', headers=csrf_header(client), json={"name": "old"}).json()['scenario']
    assert saved['provenance'] == 'legacy_unverified'


def test_dataset_bound_what_if_snapshot_keeps_costs_and_rejects_wrong_factor(db_engine, client):
    create_user(db_engine, 'u@example.com', 'pw')
    login(client, 'u@example.com', 'pw')
    dataset = client.post('/datasets', headers=csrf_header(client), files={
        'file': ('costs.csv', b'time,lambda,mu,c,server_cost\nt,5,10,2,123\n', 'text/csv'),
    }).json()['dataset']
    payload = snapshot_payload(client)
    payload['dataset_id'] = dataset['id']
    calculation = payload['settings']['calculation']
    calculation['what_if_multiplier'] = 1.5
    calculation['input_segments'] = [{'time': 't', 'lambda': 7.5, 'mu': 10, 'c': 2, 'server_cost': 123}]
    payload['results'] = client.post('/optimize/batch', json={
        'segments': calculation['input_segments'], **calculation['options'],
    }).json()
    assert client.post('/scenarios', headers=csrf_header(client), json=payload).status_code == 201
    calculation['what_if_multiplier'] = 2
    assert client.post('/scenarios', headers=csrf_header(client), json=payload).status_code == 422
    calculation['calculated_at'] = 123
    assert client.post('/scenarios', headers=csrf_header(client), json=payload).status_code == 422


def test_verified_unstable_baseline_roundtrips_complete_operational_result(db_engine, client):
    create_user(db_engine, 'u@example.com', 'pw')
    login(client, 'u@example.com', 'pw')
    segments = [{"time": "overload", "lambda": 20.214, "mu": 10, "c": 2}]
    options = {"max_servers": 5, "target_utilization": 0.7}
    results = client.post('/optimize/batch', json={"segments": segments, **options}).json()
    payload = {
        "name": "unstable baseline",
        "settings": {**options, "calculation": {
            "schema_version": 1,
            "engine_version": "novaq-2026-09-system-v2",
            "input_segments": segments,
            "options": options,
            "what_if_multiplier": 1,
            "calculated_at": "2026-09-08T00:00:00Z",
        }},
        "results": results,
    }
    created = client.post('/scenarios', headers=csrf_header(client), json=payload)
    assert created.status_code == 201
    scenario_id = created.json()['scenario']['id']
    retrieved = client.get(f'/scenarios/{scenario_id}').json()['scenario']
    listed = client.get('/scenarios').json()['scenarios'][0]
    for scenario in (retrieved, listed):
        row = scenario['results']['results'][0]
        assert scenario['settings']['target_utilization'] == 0.7
        assert row['selected_model'] == 'M/M/c'
        assert row['c_current'] == 2
        assert row['rho_current'] == 1.0107
        assert row['current_stable'] is False
        assert row['Wq_current'] is None
        assert row['cost_current'] is None
        assert row['c_optimal'] == 3
        assert row['optimized_stable'] is True
        assert row['Wq_optimal'] is not None
