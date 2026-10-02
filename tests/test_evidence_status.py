"""Step 1 tests for backend/api/evidence_status.py (pure classifier; not wired into the app).

Two kinds of fixtures, labelled on every test:

- SYNTHETIC: hand-built records and version policies (ids 101-999, values such as
  "plan-v3"). They exercise one rule at a time and say nothing about stored data.
- RECORDED: tests/fixtures/evidence_status_local_reference_2026-09-25.json, a minimized read-only
  export from the local development database: identity fields of scenarios 30 and 12, Current
  DES jobs 34 and 12, and the records they depend on (its _provenance block lists them).
  Identifiers are used as recorded; version knowledge comes from the repository's own constants.
"""

from __future__ import annotations

import ast
import copy
import itertools
import json
import random
import re
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.api import evidence_status as es
from backend.api.evidence_status import (
    ArtifactRef,
    CurrentContext,
    Dependency,
    EvidencePolicy,
    EvidenceStatus,
    ReasonCode,
    VersionFamily,
)

S = EvidenceStatus
R = ReasonCode
REPO_ROOT = Path(__file__).resolve().parents[1]

# ── SYNTHETIC helpers ───────────────────────────────────────────────────────

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
ANALYSIS, OWNER, DATASET, FP = 101, 7, 201, "fp-current"
KINDS = {"workflow_selection", "workflow_des", "workflow_des_current", "workflow_mc", "workflow_mc_current",
         "workflow_validation", "workflow_validation_current", "workflow_decision"}


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def syn_policy(**overrides: Any) -> EvidencePolicy:
    base = EvidencePolicy(
        scenario_schema=VersionFamily.of("scenario schema", current={"1", "2"}),
        separate_plan_engine=VersionFamily.of("synthetic plan engine", current={"plan-v3"},
                                              historical={"plan-v2"}, unsupported={"plan-v1"}),
        schema1_engine=VersionFamily.of("synthetic schema-1 engine", current={"s1-v1"}),
        job_kind=VersionFamily.of("workflow job kind", current=KINDS),
        job_engine=VersionFamily.of("workflow job engine", current={es.SELECTED_DES_ENGINE, es.SELECTED_MC_ENGINE}),
        selected_des_basis=VersionFamily.of("selected-plan DES basis", current={"basis-per-period", "basis-day"}),
        workflow_engine=VersionFamily.of("synthetic workflow engine", current={"wf-v1"}),
    )
    return replace(base, **overrides)


def ctx(**overrides: Any) -> CurrentContext:
    base = CurrentContext(analysis_id=ANALYSIS, owner_id=OWNER, current_dataset_id=DATASET,
                          setup_fingerprint=FP, setup_queue_type="separate")
    return replace(base, **overrides)


def dataset_dep(dataset_id: int = DATASET, *, exists: bool = True, analysis_id: int | None = ANALYSIS,
                owner_id: int = OWNER, created_at: datetime | None = at(0)) -> Dependency:
    return Dependency(ArtifactRef("dataset", dataset_id), exists, owner_id, analysis_id, created_at)


def plan(scenario_id: int = 301, *, engine: Any = "plan-v3", setup_hash: Any = FP, dataset_id: int | None = DATASET,
         schema: Any = 2, created_at: datetime | None = at(10), deps: list[Dependency] | None = None,
         policy: EvidencePolicy | None = None, snapshot_queue_type: str | None = None,
         settings: dict | None = None) -> es.EvidenceRecord:
    calc = {"schema_version": schema, "engine_version": engine, "setup_hash": setup_hash}
    if settings is None:
        settings = {"calculation": {key: value for key, value in calc.items() if value is not None}}
    if deps is None:
        deps = [dataset_dep(dataset_id)] if dataset_id is not None else []
    return es.scenario_record(scenario_id=scenario_id, owner_id=OWNER, analysis_id=ANALYSIS,
                              dataset_id=dataset_id, created_at=created_at, settings=settings,
                              policy=policy or syn_policy(), snapshot_queue_type=snapshot_queue_type,
                              dependencies=deps)


def dep_of(record: es.EvidenceRecord) -> Dependency:
    return Dependency(record.ref, True, OWNER, ANALYSIS, record.created_at, record)


def job(job_id: int, kind: str, *, params: dict | None = None, result: dict | None = None,
        created_at: datetime | None = at(20), deps: list[Dependency] | None = None,
        superseded_by: ArtifactRef | None = None, status: str = "completed",
        policy: EvidencePolicy | None = None) -> es.EvidenceRecord:
    recorded = {"analysis_id": ANALYSIS, "dataset_id": DATASET, "setup_hash": FP, "engine_version": "wf-v1",
                **(params or {})}
    recorded = {key: value for key, value in recorded.items() if value is not None}
    if deps is None:
        deps = [dataset_dep()]
    return es.job_record(job_id=job_id, kind=kind, status=status, owner_id=OWNER, created_at=created_at,
                         params=recorded, result=result or {}, policy=policy or syn_policy(),
                         dependencies=deps, superseded_by=superseded_by)


def selected_des(job_id: int = 401, *, scenario: es.EvidenceRecord | None = None, execution: Any = "basis-day",
                 result_extra: dict | None = None, **kwargs: Any) -> es.EvidenceRecord:
    scenario = scenario or plan()
    result = {"execution": execution, **(result_extra or {})} if execution is not None else dict(result_extra or {})
    return job(job_id, "workflow_des", params={"scenario_id": scenario.ref.id, "engine": es.SELECTED_DES_ENGINE},
               result=result, deps=[dataset_dep(), dep_of(scenario)], **kwargs)


def selected_mc(job_id: int, des: es.EvidenceRecord, scenario: es.EvidenceRecord, **kwargs: Any) -> es.EvidenceRecord:
    return job(job_id, "workflow_mc", params={"scenario_id": scenario.ref.id, "engine": es.SELECTED_MC_ENGINE,
                                              "des_job_id": des.ref.id},
               result={"provenance": "SELECTED"}, deps=[dataset_dep(), dep_of(scenario), dep_of(des)],
               created_at=at(30), **kwargs)


def assess(record: es.EvidenceRecord, context: CurrentContext | None = None) -> es.EvidenceAssessment:
    return es.classify(record, context or ctx())


# ── Contract ────────────────────────────────────────────────────────────────


def test_contract_every_status_and_reason_is_defined_once():
    # SYNTHETIC-free: checks the module's own tables.
    assert list(es.PRECEDENCE) == list(EvidenceStatus) and len(set(es.PRECEDENCE)) == len(EvidenceStatus)
    assert es.PRECEDENCE[-1] is S.CURRENT
    assert set(es.REASON_STATUS) == set(ReasonCode)
    assert S.CURRENT not in set(es.REASON_STATUS.values())
    assert set(es.REASON_STATUS.values()) == set(EvidenceStatus) - {S.CURRENT}
    for status in set(EvidenceStatus) - {S.CURRENT}:
        upstream = ReasonCode(f"UPSTREAM_{status.value}")
        assert es.REASON_STATUS[upstream] is status


def test_version_family_rejects_ambiguous_classes():
    # SYNTHETIC
    with pytest.raises(ValueError):
        VersionFamily.of("f", current={"a"}, historical={"a"})
    with pytest.raises(ValueError):
        VersionFamily.of("f", current={"a"}, historical={"b"}, unsupported={"b"})
    with pytest.raises(ValueError):
        VersionFamily.of("f", current=())


# ── 1. Fully compatible current evidence ────────────────────────────────────


def test_1_fully_compatible_chain_is_current():
    # SYNTHETIC
    scenario = plan()
    des = selected_des(scenario=scenario)
    mc = selected_mc(402, des, scenario)
    for record in (scenario, des, mc):
        result = assess(record)
        assert result.status is S.CURRENT and result.reasons == () and result.is_current
    chain = assess(mc)
    assert [item.ref for item in chain.dependencies] == [des.ref, scenario.ref]
    assert all(item.is_current for item in chain.dependencies)


# ── 2-4. Engine identity ────────────────────────────────────────────────────


def test_2_known_older_engine_version_requires_recalculation():
    # SYNTHETIC
    result = assess(plan(engine="plan-v2"))
    assert result.status is S.HISTORICAL_REQUIRES_RECALCULATION
    assert result.codes == (R.VERSION_HISTORICAL,)
    assert "plan-v2" in result.reasons[0].detail


@pytest.mark.parametrize("recorded, code", [
    ("plan-v9", R.VERSION_UNRECOGNIZED),
    ("plan-v1", R.VERSION_UNSUPPORTED),
    (3, R.VERSION_UNRECOGNIZED),
    (True, R.VERSION_UNRECOGNIZED),
    (2.0, R.VERSION_UNRECOGNIZED),
    ({"v": 3}, R.VERSION_UNRECOGNIZED),
])
def test_3_unknown_or_unsupported_engine_version_is_unsupported(recorded, code):
    # SYNTHETIC
    result = assess(plan(engine=recorded))
    assert result.status is S.UNSUPPORTED
    assert result.codes == (code,)


def test_3_non_integer_schema_version_is_never_silently_accepted():
    # SYNTHETIC: 2.0 would compare equal to 2 in Python; the classifier does not accept it.
    result = assess(plan(schema=2.0))
    assert result.status is S.UNSUPPORTED and R.VERSION_UNRECOGNIZED in result.codes


@pytest.mark.parametrize("recorded", [None, "", "   "])
def test_4_missing_engine_identity_is_missing_provenance_not_an_old_version(recorded):
    # SYNTHETIC
    result = assess(plan(engine=recorded))
    assert result.status is S.MISSING_PROVENANCE
    assert result.codes == (R.VERSION_UNRECORDED,)
    assert R.VERSION_HISTORICAL not in result.codes
    detail = result.reasons[0].detail
    assert not any(value in detail for value in ("plan-v1", "plan-v2", "plan-v3"))


def test_4_scenario_without_calculation_snapshot_has_no_identity():
    # SYNTHETIC
    result = assess(plan(settings={}))
    assert result.status is S.MISSING_PROVENANCE
    assert set(result.codes) == {R.VERSION_UNRECORDED, R.SETUP_UNRECORDED}


# ── 5-6. Dataset and setup ──────────────────────────────────────────────────


def test_5_stale_dataset_is_distinct_from_engine_compatibility():
    # SYNTHETIC: dataset 200 exists and is in scope, but 201 is current.
    result = assess(plan(dataset_id=200))
    assert result.status is S.STALE_DATASET and result.codes == (R.DATASET_NOT_CURRENT,)
    historical = assess(plan(dataset_id=200, engine="plan-v2"))
    assert historical.status is S.STALE_DATASET
    assert set(historical.codes) == {R.DATASET_NOT_CURRENT, R.VERSION_HISTORICAL}


def test_5_no_valid_dataset_is_never_current():
    # SYNTHETIC
    result = assess(plan(), ctx(current_dataset_id=None))
    assert result.status is S.STALE_DATASET and result.codes == (R.NO_CURRENT_DATASET,)


def test_6_stale_setup_hash():
    # SYNTHETIC
    result = assess(plan(setup_hash="fp-old"))
    assert result.status is S.STALE_SETUP and result.codes == (R.SETUP_CHANGED,)
    assert assess(plan(setup_hash=None)).codes == (R.SETUP_UNRECORDED,)


def test_6_schema1_setup_is_its_queue_type_and_unverifiable_is_not_favourable():
    # SYNTHETIC
    shared = plan(schema=1, engine="s1-v1", setup_hash=None, snapshot_queue_type="shared")
    assert assess(shared, ctx(setup_queue_type="shared")).status is S.CURRENT
    mismatch = assess(shared, ctx(setup_queue_type="separate"))
    assert mismatch.status is S.STALE_SETUP and mismatch.codes == (R.SETUP_QUEUE_TYPE_MISMATCH,)
    unknown = assess(shared, ctx(setup_queue_type=None))
    assert unknown.codes == (R.SETUP_QUEUE_TYPE_MISMATCH,)


# ── 7-9. Missing dependencies ───────────────────────────────────────────────


def test_7_missing_scenario():
    # SYNTHETIC
    missing = job(501, "workflow_selection", params={"scenario_id": 399},
                  deps=[dataset_dep(), Dependency(ArtifactRef("scenario", 399), exists=False)])
    result = assess(missing)
    assert result.status is S.MISSING_DEPENDENCY and result.codes == (R.DEPENDENCY_MISSING,)
    assert result.reasons[0].subject == "scenario 399"


def test_7_unrecorded_or_unresolved_scenario_reference_is_not_current():
    # SYNTHETIC
    unrecorded = assess(job(502, "workflow_selection", params={}))
    assert unrecorded.status is S.MISSING_PROVENANCE and unrecorded.codes == (R.REFERENCE_UNRECORDED,)
    unresolved = assess(job(503, "workflow_selection", params={"scenario_id": 301}))
    assert unresolved.status is S.MISSING_PROVENANCE and unresolved.codes == (R.DEPENDENCY_UNASSESSED,)
    no_record = assess(job(504, "workflow_selection", params={"scenario_id": 301},
                           deps=[dataset_dep(), Dependency(ArtifactRef("scenario", 301), True, OWNER, ANALYSIS, at(1))]))
    assert no_record.codes == (R.DEPENDENCY_UNASSESSED,)


def test_8_missing_dataset_keeps_every_reason():
    # SYNTHETIC: a Current DES job whose dataset 250 no longer exists.
    record = job(601, "workflow_des_current", params={"dataset_id": 250}, deps=[dataset_dep(250, exists=False)])
    result = assess(record)
    assert result.status is S.MISSING_DEPENDENCY
    assert set(result.codes) == {R.DEPENDENCY_MISSING, R.DATASET_NOT_CURRENT}


def test_8_dataset_id_counts_only_after_scope_and_existence_are_established():
    # SYNTHETIC
    unresolved = assess(plan(deps=[]))
    assert unresolved.status is S.MISSING_PROVENANCE and unresolved.codes == (R.DEPENDENCY_UNASSESSED,)
    foreign = assess(plan(deps=[dataset_dep(analysis_id=999)]))
    assert foreign.status is S.MISSING_DEPENDENCY and foreign.codes == (R.DEPENDENCY_OUT_OF_SCOPE,)
    unattached = assess(plan(deps=[dataset_dep(analysis_id=None)]))
    assert unattached.codes == (R.DEPENDENCY_OUT_OF_SCOPE,)
    other_owner = assess(plan(deps=[dataset_dep(owner_id=8)]))
    assert other_owner.codes == (R.DEPENDENCY_OUT_OF_SCOPE,)
    assert assess(plan(dataset_id=None)).codes == (R.DATASET_UNRECORDED,)


def test_9_missing_linked_job():
    # SYNTHETIC
    scenario = plan()
    mc = job(701, "workflow_mc", params={"scenario_id": 301, "engine": es.SELECTED_MC_ENGINE, "des_job_id": 999},
             deps=[dataset_dep(), dep_of(scenario), Dependency(ArtifactRef("job:workflow_des", 999), exists=False)])
    result = assess(mc)
    assert result.status is S.MISSING_DEPENDENCY and result.codes == (R.DEPENDENCY_MISSING,)
    unlinked = assess(job(702, "workflow_mc", params={"scenario_id": 301, "engine": es.SELECTED_MC_ENGINE},
                          deps=[dataset_dep(), dep_of(scenario)]))
    assert unlinked.status is S.MISSING_PROVENANCE and unlinked.codes == (R.REFERENCE_UNRECORDED,)
    validation = assess(job(703, "workflow_validation_current", params={"mc_job_id": 998},
                            deps=[dataset_dep(), Dependency(ArtifactRef("job:workflow_mc_current", 998), exists=False)]))
    assert validation.status is S.MISSING_DEPENDENCY


def test_9_reference_created_after_the_job_is_refused():
    # SYNTHETIC: guards a reused id pointing at a newer record.
    record = job(704, "workflow_des_current", created_at=at(5), deps=[dataset_dep(created_at=at(6))])
    result = assess(record)
    assert result.status is S.MISSING_DEPENDENCY and result.codes == (R.DEPENDENCY_CREATED_AFTER,)
    unordered = assess(job(705, "workflow_des_current", created_at=None))
    assert unordered.status is S.MISSING_PROVENANCE
    assert set(unordered.codes) == {R.CREATION_TIME_UNRECORDED}


# ── 10. Multiple reasons ────────────────────────────────────────────────────


def test_10_multiple_reasons_are_all_preserved_under_one_primary_status():
    # SYNTHETIC
    old_plan = plan(engine="plan-v2", setup_hash="fp-old", dataset_id=200)
    record = job(801, "workflow_des", params={"scenario_id": 301, "dataset_id": 200, "setup_hash": "fp-old",
                                              "engine_version": "wf-v0"},
                 deps=[dataset_dep(200), dep_of(old_plan)], superseded_by=ArtifactRef("job:workflow_des", 802))
    result = assess(record)
    assert set(result.codes) == {
        R.VERSION_UNRECOGNIZED,           # UNSUPPORTED
        R.DATASET_NOT_CURRENT,            # STALE_DATASET
        R.SETUP_CHANGED,                  # STALE_SETUP
        R.UPSTREAM_STALE_DATASET,         # the plan's own primary status
        R.SUPERSEDED,                     # HISTORICAL_VIEWABLE
    }
    assert result.status is S.UNSUPPORTED
    upstream = result.dependencies[0]
    assert upstream.status is S.STALE_DATASET
    assert set(upstream.codes) == {R.DATASET_NOT_CURRENT, R.SETUP_CHANGED, R.VERSION_HISTORICAL}


# ── 11. Chain rule ──────────────────────────────────────────────────────────


def _chain(scenario: es.EvidenceRecord) -> list[es.EvidenceRecord]:
    des = selected_des(scenario=scenario)
    mc = selected_mc(402, des, scenario)
    validation = job(403, "workflow_validation", params={"scenario_id": scenario.ref.id, "des_job_id": 401,
                                                         "mc_job_id": 402},
                     result={"provenance": "SELECTED"}, created_at=at(40),
                     deps=[dataset_dep(), dep_of(scenario), dep_of(des), dep_of(mc)])
    selection = job(400, "workflow_selection", params={"scenario_id": scenario.ref.id}, created_at=at(15),
                    deps=[dataset_dep(), dep_of(scenario)])
    decision = job(404, "workflow_decision",
                   params={"scenario_id": scenario.ref.id, "validation_job_id": 403, "des_job_id": 401, "mc_job_id": 402},
                   result={"provenance": "SELECTED", "evidence_ids": {"selection": 400, "des": 401, "mc": 402,
                                                                      "validation": 403}},
                   created_at=at(50),
                   deps=[dataset_dep(), dep_of(scenario), dep_of(des), dep_of(mc), dep_of(validation), dep_of(selection)])
    return [scenario, selection, des, mc, validation, decision]


def test_11_historical_dependency_prevents_any_current_downstream():
    # SYNTHETIC
    chain = _chain(plan(engine="plan-v2"))
    results = [assess(record) for record in chain]
    assert [result.status for result in results] == [S.HISTORICAL_REQUIRES_RECALCULATION] * 6
    assert R.UPSTREAM_HISTORICAL_REQUIRES_RECALCULATION in results[-1].codes
    current = [assess(record) for record in _chain(plan())]
    assert all(result.is_current for result in current)


def test_11_selected_decision_is_bound_to_the_selection_it_recorded():
    # SYNTHETIC: create_selected_decision records its selection in result.evidence_ids.
    refs = es.job_references("workflow_decision",
                             {"scenario_id": 301, "validation_job_id": 403, "des_job_id": 401, "mc_job_id": 402},
                             {"provenance": "SELECTED", "evidence_ids": {"selection": 400}})
    assert ArtifactRef("job:workflow_selection", 400) in refs.refs and refs.unrecorded == ()
    scenario, selection, des, mc, validation, decision = _chain(plan())
    unrecorded = job(405, "workflow_decision",
                     params={"scenario_id": 301, "validation_job_id": 403, "des_job_id": 401, "mc_job_id": 402},
                     result={"provenance": "SELECTED", "evidence_ids": {}}, created_at=at(50),
                     deps=[dataset_dep(), dep_of(scenario), dep_of(des), dep_of(mc), dep_of(validation)])
    result = assess(unrecorded)
    assert result.status is S.MISSING_PROVENANCE and result.codes == (R.REFERENCE_UNRECORDED,)
    # A newer selection makes the decision's own selection superseded, and with it the decision.
    replaced = replace(selection, superseded_by=ArtifactRef("job:workflow_selection", 406))
    stale = replace(decision, dependencies=tuple(dep_of(replaced) if item.ref == selection.ref else item
                                                 for item in decision.dependencies))
    outcome = assess(stale)
    assert outcome.status is S.HISTORICAL_VIEWABLE
    assert [(r.code, r.subject) for r in outcome.reasons] == [
        (R.UPSTREAM_HISTORICAL_VIEWABLE, "job:workflow_selection 400")]
    unresolved = replace(decision, dependencies=tuple(item for item in decision.dependencies
                                                      if item.ref != selection.ref))
    assert assess(unresolved).codes == (R.DEPENDENCY_UNASSESSED,)


@pytest.mark.parametrize("scenario", [
    plan(engine="plan-v1"), plan(engine=None), plan(dataset_id=200), plan(setup_hash="fp-old"),
    plan(deps=[dataset_dep(exists=False)]),
])
def test_11_downstream_is_never_more_current_than_its_dependencies(scenario):
    # SYNTHETIC
    def walk(result: es.EvidenceAssessment) -> None:
        for upstream in result.dependencies:
            assert es.PRECEDENCE.index(result.status) <= es.PRECEDENCE.index(upstream.status)
            walk(upstream)

    for record in _chain(scenario):
        result = assess(record)
        assert not result.is_current
        walk(result)


# ── 12. Superseded ──────────────────────────────────────────────────────────


def test_12_superseded_evidence_remains_viewable_and_names_its_successor():
    # SYNTHETIC
    older = selected_des(401, superseded_by=ArtifactRef("job:workflow_des", 405))
    result = assess(older)
    assert result.status is S.HISTORICAL_VIEWABLE and result.codes == (R.SUPERSEDED,)
    assert "job:workflow_des 405" in result.reasons[0].detail
    mc = selected_mc(402, older, plan())
    assert assess(mc).codes == (R.UPSTREAM_HISTORICAL_VIEWABLE,)


# ── 13. Undefined analytical values ─────────────────────────────────────────


def test_13_metric_values_neither_change_status_nor_become_zero():
    # SYNTHETIC: identical identity, different stored metrics.
    undefined = {"periods": [{"total_cost": None, "waiting_cost": None, "results": [{"Wq_sim": None, "rho_sim": None}]}]}
    zero = {"periods": [{"total_cost": 0.0, "waiting_cost": 0.0, "results": [{"Wq_sim": 0.0, "rho_sim": 0.0}]}]}
    measured = {"periods": [{"total_cost": 435.0, "waiting_cost": 12.5, "results": [{"Wq_sim": 0.1, "rho_sim": 0.6}]}]}
    stored = copy.deepcopy(undefined)
    results = [assess(selected_des(result_extra=extra)) for extra in (undefined, zero, measured)]
    assert results[0] == results[1] == results[2] and results[0].is_current
    assert undefined == stored  # the classifier never writes into stored results


def test_13_records_cannot_carry_metrics():
    # SYNTHETIC-free: the record type has identity fields only. ``generations`` holds recorded
    # generation tokens (spec 2026-09-26 §9): record identity, not a metric.
    names = {field.name for field in fields(es.EvidenceRecord)}
    assert names == {"ref", "owner_id", "analysis_id", "created_at", "dataset_id", "setup", "versions",
                     "required_refs", "unrecorded_refs", "dependencies", "result_complete",
                     "calculation_unsupported", "superseded_by", "generations"}


# ── 14. Simulation basis ────────────────────────────────────────────────────


def test_14_unrecorded_simulation_basis_is_never_inferred_from_null_costs():
    # SYNTHETIC: the continuous-day selected DES stores null costs; nulls are not a basis.
    nulls = {"periods": [{"total_cost": None, "server_cost": None, "waiting_cost": None}]}
    result = assess(selected_des(execution=None, result_extra=nulls))
    assert result.status is S.MISSING_PROVENANCE and result.codes == (R.VERSION_UNRECORDED,)
    assert result.reasons[0].subject == "selected-plan DES basis"
    priced = assess(selected_des(execution=None, result_extra={"periods": [{"total_cost": 435.0}]}))
    assert priced.codes == (R.VERSION_UNRECORDED,)


def test_14_unrecognized_simulation_basis_is_unsupported():
    # SYNTHETIC
    result = assess(selected_des(execution="some other basis"))
    assert result.status is S.UNSUPPORTED and result.codes == (R.VERSION_UNRECOGNIZED,)


def test_14_legacy_scenario_des_has_no_basis_requirement():
    # SYNTHETIC: only a recorded selected-plan engine marker makes the basis required.
    scenario = plan(schema=1, engine="s1-v1", setup_hash=None, snapshot_queue_type="separate")
    legacy = job(410, "workflow_des", params={"scenario_id": 301}, deps=[dataset_dep(), dep_of(scenario)])
    assert assess(legacy).is_current


# ── 15. Precedence and determinism ──────────────────────────────────────────


def _reason(code: ReasonCode) -> es.Reason:
    return es.Reason(code, "subject", "detail")


def test_15_primary_status_follows_precedence_for_every_pair_and_order():
    # SYNTHETIC
    assert es.primary_status([]) is S.CURRENT
    for left, right in itertools.product(ReasonCode, repeat=2):
        expected = min((es.REASON_STATUS[left], es.REASON_STATUS[right]), key=es.PRECEDENCE.index)
        assert es.primary_status([_reason(left), _reason(right)]) is expected
        assert es.primary_status([_reason(right), _reason(left)]) is expected


def test_15_classification_is_deterministic_and_order_independent():
    # SYNTHETIC
    scenario = plan(engine="plan-v2", dataset_id=200)
    base = job(901, "workflow_decision",
               params={"scenario_id": 301, "validation_job_id": 403, "des_job_id": 401, "mc_job_id": 402,
                       "dataset_id": 200, "setup_hash": "fp-old"},
               result={"provenance": "SELECTED", "evidence_ids": {"selection": 400}},
               deps=[dataset_dep(200), dep_of(scenario),
                     Dependency(ArtifactRef("job:workflow_des", 401), exists=False),
                     Dependency(ArtifactRef("job:workflow_mc", 402), True, OWNER, 999, at(1)),
                     Dependency(ArtifactRef("job:workflow_validation", 403), True, OWNER, ANALYSIS, None)])
    expected = assess(base)
    shuffler = random.Random(20260925)
    for _ in range(25):
        deps = list(base.dependencies)
        shuffler.shuffle(deps)
        assert assess(replace(base, dependencies=tuple(deps))) == expected
    assert assess(base) == expected
    assert list(expected.reasons) == sorted(expected.reasons, key=es._sort_key)


# ── Further guards ──────────────────────────────────────────────────────────


def test_scope_owner_and_completion():
    # SYNTHETIC
    other_analysis = assess(plan(), ctx(analysis_id=102))
    assert other_analysis.status is S.MISSING_DEPENDENCY
    assert {R.OUT_OF_SCOPE, R.DEPENDENCY_OUT_OF_SCOPE} == set(other_analysis.codes)
    assert R.OUT_OF_SCOPE in assess(plan(), ctx(owner_id=8)).codes
    unowned = replace(plan(), owner_id=None)
    assert assess(unowned).codes == (R.OWNER_UNRECORDED,)
    failed = assess(job(950, "workflow_des_current", status="failed"))
    assert failed.status is S.MISSING_PROVENANCE and failed.codes == (R.RESULT_INCOMPLETE,)


def test_calculation_recorded_as_unsupported():
    # SYNTHETIC
    rows = [{"queue_structure": "separate", "simulation_supported": False}] * 3
    result = assess(job(951, "workflow_des_current", result={"results": rows}))
    assert result.status is S.UNSUPPORTED and result.codes == (R.CALCULATION_UNSUPPORTED,)
    mixed = rows[:2] + [{"queue_structure": "separate", "simulation_supported": True}]
    assert assess(job(952, "workflow_des_current", result={"results": mixed})).is_current


def test_accounting_marker_is_required_only_when_supplied_and_never_named_when_absent():
    # SYNTHETIC: the Current DES accounting marker does not exist yet (plan Step 10), so the
    # requirement is supplied explicitly here; nothing is stamped on any record.
    family = VersionFamily.of("synthetic Current DES accounting", current={"acct-fixed-horizon-1"})
    requirement = es.AccountingRequirement(family, "synthetic_accounting_key",
                                           frozenset({"workflow_des_current", "workflow_des"}))
    separate = {"results": [{"queue_structure": "separate", "simulation_supported": True}]}
    assert assess(job(960, "workflow_des_current", result=separate)).is_current  # no requirement supplied
    policy = syn_policy(current_des_accounting=requirement)
    unmarked = assess(job(961, "workflow_des_current", result=separate, policy=policy))
    assert unmarked.status is S.MISSING_PROVENANCE and unmarked.codes == (R.VERSION_UNRECORDED,)
    assert "acct-fixed-horizon-1" not in unmarked.reasons[0].detail
    marked = job(962, "workflow_des_current", result=separate, policy=policy,
                 params={"synthetic_accounting_key": "acct-fixed-horizon-1"})
    assert assess(marked).is_current
    pooled = {"results": [{"queue_structure": "shared", "simulation_supported": True}]}
    assert assess(job(963, "workflow_des_current", result=pooled, policy=policy)).is_current


def test_malformed_inputs_are_rejected():
    # SYNTHETIC
    first = plan(301)
    looped = replace(first, dependencies=(dataset_dep(), Dependency(first.ref, True, OWNER, ANALYSIS, at(1), first)))
    with pytest.raises(ValueError, match="cycle"):
        assess(looped)
    with pytest.raises(ValueError, match="twice"):
        assess(replace(first, dependencies=(dataset_dep(), dataset_dep())))
    other = plan(302)
    with pytest.raises(ValueError, match="carries the record"):
        assess(job(970, "workflow_selection", params={"scenario_id": 301},
                   deps=[dataset_dep(), Dependency(ArtifactRef("scenario", 301), True, OWNER, ANALYSIS, at(1), other)]))


CLASSIFIER = "backend.api.evidence_status"
# The calls that load a module or look one up, with their parameter names in order.
IMPORT_CALLS: dict[str, tuple[str, ...]] = {
    "builtins.__import__": ("name", "globals", "locals", "fromlist", "level"),
    "importlib.__import__": ("name", "globals", "locals", "fromlist", "level"),
    "importlib.import_module": ("name", "package"),
    "builtins.getattr": ("object", "name"),
}


def _names_the_classifier(value: Any) -> bool:
    """Whether ``value`` is a module path or file path of the classifier: one word ending in
    ``.evidence_status`` or ``evidence_status.py``. Prose that mentions it has spaces."""
    return (isinstance(value, str) and not any(char.isspace() for char in value)
            and (value.endswith(".evidence_status") or re.split(r"[/\\]", value)[-1] == "evidence_status.py"))


def _wires_the_classifier(path: Path) -> bool:
    """Whether the module at ``path`` imports, loads or refers to the classifier module in any form its
    code states: an absolute, relative or aliased import (also one inside a function); ``__import__``
    (also with ``fromlist``), ``importlib.import_module`` or ``getattr`` naming it; a dotted reference
    through a name bound to its package, such as ``api.evidence_status`` after ``from backend import api``;
    or a module-path or file-path string for it. A field, key, attribute or word ``evidence_status`` on
    anything other than the ``backend.api`` package is not wiring."""
    package = list(path.relative_to(REPO_ROOT).parts[:-1])
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def absolute(module: str, level: int) -> str:
        """``module`` imported ``level`` packages up from ``path`` (as written when ``level`` is 0)."""
        return ".".join(package[:len(package) + 1 - level] + ([module] if module else [])) if level else module

    def literal(node: ast.AST | None) -> Any:
        """The value ``node`` states literally, joining strings added with ``+``; None otherwise."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literal(node.left), literal(node.right)
            return left + right if isinstance(left, str) and isinstance(right, str) else None
        try:
            return ast.literal_eval(node) if isinstance(node, ast.expr) else None
        except (ValueError, TypeError, SyntaxError):
            return None

    # Each name an import binds anywhere in the module, to the dotted path it stands for.
    bound = {"__import__": "builtins.__import__", "getattr": "builtins.getattr"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                bound[alias.asname or top] = alias.name if alias.asname else top
        elif isinstance(node, ast.ImportFrom):
            base = absolute(node.module or "", node.level)
            bound.update((alias.asname or alias.name, f"{base}.{alias.name}") for alias in node.names)

    def loaded(node: ast.AST) -> list[str]:
        """The dotted paths ``node`` loads or refers to, the one it evaluates to first."""
        if isinstance(node, ast.Name):
            return [bound[node.id]] if node.id in bound else []
        if isinstance(node, ast.Attribute):
            return [f"{owner}.{node.attr}" for owner in loaded(node.value)[:1]]
        function = loaded(node.func)[:1] if isinstance(node, ast.Call) else []
        if not isinstance(node, ast.Call) or not function or function[0] not in IMPORT_CALLS:
            return []
        given = dict(zip(IMPORT_CALLS[function[0]], node.args))
        given.update((keyword.arg, keyword.value) for keyword in node.keywords if keyword.arg)
        name = literal(given.get("name"))
        if not isinstance(name, str):
            return []
        if function[0] == "builtins.getattr":
            return [f"{owner}.{name}" for owner in loaded(given["object"])[:1]] if "object" in given else []
        if function[0] == "importlib.import_module":
            anchor, rest = str(literal(given.get("package")) or "").split("."), name.lstrip(".")
            level = len(name) - len(rest)
            return [".".join(anchor[:len(anchor) + 1 - level] + ([rest] if rest else [])) if level else name]
        level, fromlist = literal(given.get("level")), literal(given.get("fromlist"))
        level = level if isinstance(level, int) else 0
        fromlist = [item for item in fromlist if isinstance(item, str)] if isinstance(fromlist, (list, tuple)) else []
        module = absolute(name, level)
        evaluates_to = module if fromlist else absolute(name.partition(".")[0], level)
        return [evaluates_to, module, *(f"{module}.{item}" for item in fromlist)]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = absolute(node.module or "", node.level)
            names = [base, *(f"{base}.{alias.name}" for alias in node.names)]
        elif isinstance(node, (ast.Constant, ast.BinOp)):
            if _names_the_classifier(literal(node)):
                return True
            continue
        else:
            names = loaded(node)
        if any(name == CLASSIFIER or name.startswith(f"{CLASSIFIER}.") for name in names):
            return True
    return False


def test_only_the_reviewed_consumer_is_wired_into_the_application():
    """Step 1 kept the classifier isolated; Step 3 (D7) wired exactly one consumer.

    Previous expectation: no backend module referenced ``evidence_status`` at all.
    Corrected expectation: ``workflow.py`` imports the classifier, and nothing else yet. The remaining
    consumers named in spec section 5.2 (scenario selection, reports, decisions) are later steps, so
    this list still guards against unreviewed integration. The guard looks for imports of the
    classifier, not for the word: Step 4c scenario responses carry fields named ``evidence_status``
    and ``evidence_reasons`` that ``workflow.py`` computes, and a field name is not wiring.
    """
    classifier = REPO_ROOT / "backend" / "api" / "evidence_status.py"
    importers = [path.relative_to(REPO_ROOT).as_posix()
                 for path in (REPO_ROOT / "backend").rglob("*.py")
                 if path != classifier and _wires_the_classifier(path)]
    assert importers == ["backend/api/workflow.py"]


# ── RECORDED reference cases ────────────────────────────────────────────────

FIXTURE = Path(__file__).parent / "fixtures" / "evidence_status_local_reference_2026-09-25.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
ANALYSES = {item["id"]: item for item in DATA["analyses"]}
DATASETS = {item["id"]: item for item in DATA["datasets"]}
SCENARIOS = {item["id"]: item for item in DATA["scenarios"]}
JOBS = {item["id"]: item for item in DATA["jobs"]}
ABSENT_DATASETS = frozenset(DATA["verified_absent"]["datasets"])
PROPOSED_V3 = "<proposed separate plan engine v3: not implemented>"
PROPOSED_ACCOUNTING_KEY = "current_des_accounting"  # spec marker M3: PROPOSED, written by no code


def parse_time(text: str) -> datetime:
    # PostgreSQL trims trailing zeros in fractions; Python 3.10 needs 3 or 6 digits. Padding only.
    return datetime.fromisoformat(re.sub(r"\.(\d{1,6})", lambda m: "." + m.group(1).ljust(6, "0"), text))


def repository_policy() -> EvidencePolicy:
    """Version knowledge of this commit: no v3 plan engine, no Current DES accounting marker."""
    from backend.api.workflow import ENGINE_VERSION, WORKFLOW_KINDS
    from backend.queueing_engine.services.separate_optimization import (
        SELECTED_DES_CONTINUOUS_DAY_EXECUTION,
        SELECTED_DES_PER_PERIOD_EXECUTION,
        SEPARATE_DES_ENGINE_VERSION,
    )

    return EvidencePolicy(
        scenario_schema=VersionFamily.of("scenario schema", current={"1", "2"}),
        separate_plan_engine=VersionFamily.of("separate plan engine", current={SEPARATE_DES_ENGINE_VERSION},
                                              unsupported={"novaq-2026-09-separate-des-v1"}),
        # The schema-1 save gate accepts exactly these (backend/api/scenarios.py _verify_calculation).
        schema1_engine=VersionFamily.of("schema-1 engine",
                                        current={"novaq-2026-09-integrity-v1", "novaq-2026-09-system-v2"}),
        job_kind=VersionFamily.of("workflow job kind", current=WORKFLOW_KINDS),
        job_engine=VersionFamily.of("workflow job engine", current={es.SELECTED_DES_ENGINE, es.SELECTED_MC_ENGINE}),
        selected_des_basis=VersionFamily.of("selected-plan DES basis", current={
            SELECTED_DES_PER_PERIOD_EXECUTION, SELECTED_DES_CONTINUOUS_DAY_EXECUTION}),
        workflow_engine=VersionFamily.of("workflow engine", current={ENGINE_VERSION}),
    )


def proposed_v3_policy() -> EvidencePolicy:
    """PROPOSED spec M1, supplied explicitly: today's plan engine becomes historical."""
    from backend.queueing_engine.services.separate_optimization import SEPARATE_DES_ENGINE_VERSION

    return replace(repository_policy(), separate_plan_engine=VersionFamily.of(
        "separate plan engine", current={PROPOSED_V3}, historical={SEPARATE_DES_ENGINE_VERSION},
        unsupported={"novaq-2026-09-separate-des-v1"}))


def recorded_context(analysis_id: int) -> CurrentContext:
    from backend.api.scenarios import setup_fingerprint
    from backend.api.workflow import _SETUP_QUEUE_TYPE

    analysis = ANALYSES[analysis_id]
    owner = analysis["user_id"]
    setup = analysis["queue_setup_json"]
    # Same rule as workflow._current_valid_dataset_id: the owner's highest-id dataset of the
    # analysis whose validation report is ok. The fixture holds every dataset of its analyses.
    valid = [item["id"] for item in DATA["datasets"]
             if item["analysis_id"] == analysis_id and item["user_id"] == owner and item["validation_ok"]]
    return CurrentContext(analysis_id=analysis_id, owner_id=owner,
                          current_dataset_id=max(valid) if valid else None,
                          setup_fingerprint=setup_fingerprint(setup),
                          setup_queue_type=_SETUP_QUEUE_TYPE.get(setup.get("queue_structure")))


def recorded_dataset_dep(dataset_id: int) -> Dependency:
    ref = ArtifactRef("dataset", dataset_id)
    if dataset_id in ABSENT_DATASETS:  # checked absent in the export session, never assumed
        return Dependency(ref, exists=False)
    item = DATASETS[dataset_id]
    return Dependency(ref, True, item["user_id"], item["analysis_id"], parse_time(item["created_at"]))


def recorded_scenario(scenario_id: int, policy: EvidencePolicy) -> es.EvidenceRecord:
    from backend.api.workflow import _legacy_snapshot_queue_type

    item = SCENARIOS[scenario_id]
    calculation = item["settings"]["calculation"]
    dataset_id = item["dataset_id"]
    return es.scenario_record(
        scenario_id=scenario_id, owner_id=item["user_id"], analysis_id=item["analysis_id"], dataset_id=dataset_id,
        created_at=parse_time(item["created_at"]), settings=item["settings"], policy=policy,
        snapshot_queue_type=_legacy_snapshot_queue_type(calculation),
        dependencies=[recorded_dataset_dep(dataset_id)] if dataset_id is not None else [])


def recorded_superseded_by(item: dict) -> ArtifactRef | None:
    # Same rule as workflow._latest_job for Current kinds: the owner's newest completed job of the
    # kind for the analysis. The fixture holds every workflow_des_current job of analyses 7 and 13.
    analysis_id = item["params"]["analysis_id"]
    peers = [peer for peer in DATA["supersession_peers"]
             if peer["kind"] == item["kind"] and peer["user_id"] == item["user_id"]
             and peer["analysis_id"] == analysis_id]
    assert item["id"] in {peer["id"] for peer in peers}
    latest = max(peer["id"] for peer in peers if peer["status"] == "completed")
    return None if latest == item["id"] else ArtifactRef(f"job:{item['kind']}", latest)


def recorded_current_des_job(job_id: int, policy: EvidencePolicy) -> es.EvidenceRecord:
    item = JOBS[job_id]
    assert item["kind"] == "workflow_des_current"
    # A Current run references no scenario or job; its only dependency is its dataset.
    assert es.job_references(item["kind"], item["params"], item["result"]) == es.JobReferences((), ())
    return es.job_record(job_id=job_id, kind=item["kind"], status=item["status"], owner_id=item["user_id"],
                         created_at=parse_time(item["created_at"]), params=item["params"], result=item["result"],
                         policy=policy, dependencies=[recorded_dataset_dep(item["params"]["dataset_id"])],
                         superseded_by=recorded_superseded_by(item))


def test_recorded_fixture_holds_only_the_documented_records_and_fields():
    # RECORDED: the reference cases below and nothing else; no metric or personal value.
    assert (sorted(ANALYSES), sorted(DATASETS), sorted(SCENARIOS), sorted(JOBS)) == (
        [2, 7, 13, 21], [7, 8, 35], [12, 30], [12, 34])
    assert [peer["id"] for peer in DATA["supersession_peers"]] == [12, 13, 14, 15, 16, 17, 18, 34]
    assert ABSENT_DATASETS == {17, 23}
    allowed = {
        "analyses": {"id", "user_id", "queue_setup_json"},
        "datasets": {"id", "user_id", "analysis_id", "created_at", "validation_ok"},
        "scenarios": {"id", "user_id", "analysis_id", "dataset_id", "created_at", "settings"},
        "jobs": {"id", "user_id", "kind", "status", "created_at", "params", "result"},
        "supersession_peers": {"id", "user_id", "kind", "status", "analysis_id"},
    }
    for section, keys in allowed.items():
        assert all(set(item) == keys for item in DATA[section]), section
    for scenario in SCENARIOS.values():
        calculation = scenario["settings"]["calculation"]
        assert set(scenario["settings"]) == {"calculation"}
        assert set(calculation) <= {"schema_version", "engine_version", "setup_hash", "input_segments"}
        assert all(set(row) <= {"queue_structure", "model_id"} for row in calculation.get("input_segments", []))
    for item in JOBS.values():
        assert set(item["params"]) <= {"analysis_id", "dataset_id", "setup_hash", "engine_version", "engine",
                                       PROPOSED_ACCOUNTING_KEY}
        assert set(item["result"]) == {"results"}
        assert all(set(row) <= {"queue_structure", "simulation_supported"} for row in item["result"]["results"])
    text = FIXTURE.read_text(encoding="utf-8")
    for forbidden in ("total_cost", "waiting_cost", "Wq", "rho", "lambda", "costs", "periods", "evidence",
                      "email", "name", "password", "token"):
        assert f'"{forbidden}"' not in text


def test_recorded_scenario_30_is_identified_only_by_its_engine_string():
    # RECORDED. Scenario 30 was priced before D1 (Milestone 5 replay), but the only recorded
    # identity is its engine string, which today equals the current constant. The classifier
    # reads no cost summary, so under today's version knowledge it cannot and does not flag it.
    from backend.queueing_engine.services.separate_optimization import SEPARATE_DES_ENGINE_VERSION

    stored = copy.deepcopy(SCENARIOS[30])
    calculation = SCENARIOS[30]["settings"]["calculation"]
    assert calculation["engine_version"] == SEPARATE_DES_ENGINE_VERSION
    assert set(calculation) == {"schema_version", "engine_version", "setup_hash"}
    context = recorded_context(21)
    assert context.current_dataset_id == 35 and calculation["setup_hash"] == context.setup_fingerprint
    today = es.classify(recorded_scenario(30, repository_policy()), context)
    assert today.status is S.CURRENT and today.reasons == ()
    # Once a new engine version is established (PROPOSED M1), the same record is historical,
    # for its engine only: dataset 35 and the Setup are still current.
    proposed = es.classify(recorded_scenario(30, proposed_v3_policy()), context)
    assert proposed.status is S.HISTORICAL_REQUIRES_RECALCULATION
    assert proposed.codes == (R.VERSION_HISTORICAL,)
    assert proposed.reasons[0].subject == "separate plan engine"
    assert SCENARIOS[30] == stored


def test_recorded_scenario_12_is_stale_for_its_dataset_independently_of_its_engine():
    # RECORDED: scenario 12 references dataset 7; analysis 2's datasets are 7 and 8, both valid,
    # so its current dataset is 8. The schema-1 queue type (shared) matches the Setup's.
    context = recorded_context(2)
    assert context.current_dataset_id == 8 and SCENARIOS[12]["dataset_id"] == 7
    assert {DATASETS[7]["analysis_id"], DATASETS[8]["analysis_id"]} == {2}
    for policy in (repository_policy(), proposed_v3_policy()):
        stale = es.classify(recorded_scenario(12, policy), context)
        assert stale.status is S.STALE_DATASET and stale.codes == (R.DATASET_NOT_CURRENT,)
        assert stale.reasons[0].detail == "Recorded dataset 7; the current dataset is 8."


def test_recorded_current_des_jobs_lack_dependencies_and_accounting_is_not_claimed():
    # RECORDED: job 34 (analysis 13) and job 12 (analysis 7) are Current DES runs whose datasets
    # (23 and 17) no longer exist, and whose analyses have no dataset left. Neither records a
    # setup_hash. Job 12's rows record the calculation as unsupported; jobs 13-18 superseded it.
    job_34 = es.classify(recorded_current_des_job(34, repository_policy()), recorded_context(13))
    assert job_34.status is S.MISSING_DEPENDENCY
    assert set(job_34.codes) == {R.DEPENDENCY_MISSING, R.SETUP_UNRECORDED, R.NO_CURRENT_DATASET}
    job_12 = es.classify(recorded_current_des_job(12, repository_policy()), recorded_context(7))
    assert job_12.status is S.MISSING_DEPENDENCY
    assert set(job_12.codes) == {R.DEPENDENCY_MISSING, R.SETUP_UNRECORDED, R.CALCULATION_UNSUPPORTED,
                                 R.NO_CURRENT_DATASET, R.SUPERSEDED}
    # No version is claimed from an absent marker: without an accounting requirement, nothing
    # about accounting is reported at all ("pre-D2" is never inferred).
    for result in (job_34, job_12):
        assert not {R.VERSION_UNRECORDED, R.VERSION_HISTORICAL, R.VERSION_UNSUPPORTED} & set(result.codes)
    # With the PROPOSED accounting requirement supplied explicitly, the absent marker is missing
    # provenance: no exported job records it, and no version is named for it.
    assert all(PROPOSED_ACCOUNTING_KEY not in item["params"] for item in DATA["jobs"])
    family = VersionFamily.of("Current DES accounting", current={"<proposed marker value: not implemented>"})
    requirement = es.AccountingRequirement(family, PROPOSED_ACCOUNTING_KEY,
                                           frozenset({"workflow_des_current", "workflow_des"}))
    policy = replace(repository_policy(), current_des_accounting=requirement)
    marked = es.classify(recorded_current_des_job(34, policy), recorded_context(13))
    accounting = [reason for reason in marked.reasons if reason.subject == "Current DES accounting"]
    assert [reason.code for reason in accounting] == [R.VERSION_UNRECORDED]
    assert accounting[0].detail == "Current DES accounting is not recorded."
    assert accounting[0].status is S.MISSING_PROVENANCE
    assert marked.status is S.MISSING_DEPENDENCY


def test_recorded_selected_engine_markers_match_the_workflow_source():
    # The extractor recognizes selected-plan jobs by the markers the workflow writes.
    source = (REPO_ROOT / "backend" / "api" / "workflow.py").read_text(encoding="utf-8")
    assert f'"engine": "{es.SELECTED_DES_ENGINE}"' in source
    assert f'"engine": "{es.SELECTED_MC_ENGINE}"' in source
