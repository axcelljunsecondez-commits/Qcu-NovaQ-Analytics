"""G4: generation identity in the evidence classifier (gates G-T9 and G-T13).

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §9 and §14 (G4).
Decisions of 2026-09-29: the policy's ``generation_kinds`` decides whether ``job_record`` and
``scenario_record`` build generation requirements, and ``classify`` is unchanged (D1); a live token
the caller did not supply is ``DEPENDENCY_UNASSESSED`` (D2).

Nothing here is wired into the application: that is G5. The application's policy enables no
generation kind, which one test below pins.

Fixture labels follow tests/test_evidence_status.py: SYNTHETIC records are hand-built; RECORDED
cases use its minimized export of the local development database, which holds no generation token.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Any

import pytest

from backend.api import evidence_status as es
from backend.api.evidence_status import ArtifactRef, Dependency, EvidencePolicy, GenerationRequirement
from tests.test_evidence_status import (
    ANALYSIS,
    DATASET,
    FP,
    OWNER,
    SCENARIOS,
    R,
    S,
    assess,
    at,
    dataset_dep,
    dep_of,
    job,
    recorded_context,
    recorded_scenario,
    repository_policy,
    syn_policy,
)

DS = "a1" * 16      # the dataset row's live token (SYNTHETIC)
SC = "b2" * 16      # the scenario row's live token (SYNTHETIC)
OTHER = "c3" * 16   # a well-formed token of some other row
DIGITS = "1234567890" * 3 + "12"   # 32 hex digits that are also a decimal number
GENERATION_CODES = {R.GENERATION_MISMATCH, R.GENERATION_UNRECORDED}
DATASET_REF = ArtifactRef("dataset", DATASET)


def on(*kinds: str) -> EvidencePolicy:
    return syn_policy(generation_kinds=frozenset(kinds))


def live(dependency: Dependency, token: Any) -> Dependency:
    return replace(dependency, generation=token)


def bound_plan(binding: Any = DS, *, live_token: Any = DS, policy: EvidencePolicy | None = None,
               scenario_id: int = 301) -> es.EvidenceRecord:
    """A schema-2 plan whose recorded dataset binding is ``binding`` (SYNTHETIC)."""
    settings = {"calculation": {"schema_version": 2, "engine_version": "plan-v3", "setup_hash": FP}}
    return es.scenario_record(scenario_id=scenario_id, owner_id=OWNER, analysis_id=ANALYSIS, dataset_id=DATASET,
                              created_at=at(10), settings=settings, policy=policy or on("dataset", "scenario"),
                              snapshot_queue_type=None, dependencies=[live(dataset_dep(), live_token)],
                              dataset_generation=binding)


def stamped_des(*, dataset_token: Any = DS, scenario_token: Any = SC, live_dataset: Any = DS, live_scenario: Any = SC,
                scenario: es.EvidenceRecord | None = None, policy: EvidencePolicy | None = None,
                **kwargs: Any) -> es.EvidenceRecord:
    """A selected-plan DES job with recorded tokens and the live tokens of its rows (SYNTHETIC)."""
    policy = policy or on("dataset", "scenario")
    scenario = scenario or bound_plan(policy=policy)
    params = {"scenario_id": scenario.ref.id, "engine": es.SELECTED_DES_ENGINE,
              "dataset_generation": dataset_token, "scenario_generation": scenario_token}
    return job(401, "workflow_des", params=params, result={"execution": "basis-day"}, policy=policy,
               deps=[live(dataset_dep(), live_dataset), live(dep_of(scenario), live_scenario)], **kwargs)


def generation_reasons(assessment: es.EvidenceAssessment) -> list[tuple[R, str]]:
    return [(reason.code, reason.subject) for reason in assessment.reasons
            if reason.code in GENERATION_CODES or "generation token" in reason.detail]


# ── G-T9: the two reasons and their statuses ────────────────────────────────


def test_the_generation_reasons_have_their_specified_statuses():
    # SYNTHETIC-free: the module's own tables (spec §9).
    assert es.REASON_STATUS[R.GENERATION_MISMATCH] is S.MISSING_DEPENDENCY
    assert es.REASON_STATUS[R.GENERATION_UNRECORDED] is S.MISSING_PROVENANCE
    assert es.GENERATION_KINDS == {"dataset", "scenario"}


def test_matching_tokens_keep_evidence_current():
    # SYNTHETIC
    record = stamped_des()
    assert {requirement.ref.kind for requirement in record.generations} == {"dataset", "scenario"}
    result = assess(record)
    assert result.is_current, result.reasons


@pytest.mark.parametrize("which", ["dataset", "scenario"])
def test_a_different_token_is_a_mismatch_and_a_missing_dependency(which):
    # SYNTHETIC: the id resolves, but the recorded token is some other row's.
    record = stamped_des(**{f"{which}_token": OTHER})
    result = assess(record)
    assert result.status is S.MISSING_DEPENDENCY
    subject = str(DATASET_REF) if which == "dataset" else "scenario 301"
    assert generation_reasons(result) == [(R.GENERATION_MISMATCH, subject)]


@pytest.mark.parametrize("recorded", [None, "", "   ", "\t\n"])
@pytest.mark.parametrize("which", ["dataset", "scenario"])
def test_an_unrecorded_token_is_missing_provenance(which, recorded):
    # SYNTHETIC: None is left out of params (as the job() helper records it); blank text is kept.
    result = assess(stamped_des(**{f"{which}_token": recorded}))
    assert result.status is S.MISSING_PROVENANCE
    subject = str(DATASET_REF) if which == "dataset" else "scenario 301"
    assert generation_reasons(result) == [(R.GENERATION_UNRECORDED, subject)]


def test_an_explicit_null_token_is_unrecorded():
    # SYNTHETIC: params written directly, so the null is really stored.
    record = es.job_record(job_id=402, kind="workflow_des_current", status="completed", owner_id=OWNER,
                           created_at=at(20), params={"analysis_id": ANALYSIS, "dataset_id": DATASET,
                                                      "setup_hash": FP, "engine_version": "wf-v1",
                                                      "scenario_generation": None, "dataset_generation": None},
                           result={}, policy=on("dataset", "scenario"), dependencies=[live(dataset_dep(), DS)])
    assert record.generations == (GenerationRequirement(DATASET_REF, None),)
    assert generation_reasons(assess(record)) == [(R.GENERATION_UNRECORDED, str(DATASET_REF))]


@pytest.mark.parametrize("recorded, live_token", [
    (int(DIGITS), DIGITS),          # 32 decimal digits are a valid token; the integer is not it
    (1.0, "1.0"),
    (True, "True"),
    ([DIGITS], DIGITS),
    ({"token": DIGITS}, DIGITS),
    (DS.upper(), DS),               # tokens are compared exactly, never case-folded
    (" " + DS, DS),                 # nor trimmed
    (DS + "\n", DS),
])
def test_a_recorded_value_that_is_not_the_exact_token_never_matches(recorded, live_token):
    # SYNTHETIC
    result = assess(stamped_des(dataset_token=recorded, live_dataset=live_token))
    assert (R.GENERATION_MISMATCH, str(DATASET_REF)) in generation_reasons(result)
    assert not result.is_current


@pytest.mark.parametrize("live_token", [None, "", "   "])
def test_a_live_token_the_caller_did_not_supply_is_unassessed(live_token):
    # SYNTHETIC (D2): nothing to compare with, so the dependency is not assessed; never a match.
    result = assess(stamped_des(live_dataset=live_token))
    assert result.status is S.MISSING_PROVENANCE
    unassessed = [reason for reason in result.reasons if reason.subject == str(DATASET_REF)]
    assert [(reason.code, reason.detail) for reason in unassessed] == [
        (R.DEPENDENCY_UNASSESSED, "The referenced record's generation token was not supplied.")]


def test_tokens_are_read_from_recorded_params_only():
    # SYNTHETIC: a token placed in the result is not the job's recorded identity.
    policy = on("dataset")
    params = {"dataset_generation": OTHER}
    mismatched = job(403, "workflow_des_current", params=params, result={"dataset_generation": DS},
                     deps=[live(dataset_dep(), DS)], policy=policy)
    assert generation_reasons(assess(mismatched)) == [(R.GENERATION_MISMATCH, str(DATASET_REF))]
    unrecorded = job(404, "workflow_des_current", result={"dataset_generation": DS},
                     deps=[live(dataset_dep(), DS)], policy=policy)
    assert generation_reasons(assess(unrecorded)) == [(R.GENERATION_UNRECORDED, str(DATASET_REF))]


# ── Which references carry a requirement ───────────────────────────────────


@pytest.mark.parametrize("scenario_token", [None, SC])
def test_a_current_mode_job_gets_no_scenario_requirement(scenario_token):
    # SYNTHETIC: a Current run references no scenario, so a scenario token (null as G3 stamps it,
    # or anything else) creates no requirement.
    params = {"dataset_generation": DS, "scenario_generation": scenario_token}
    record = job(405, "workflow_des_current", params=params, deps=[live(dataset_dep(), DS)],
                 policy=on("dataset", "scenario"))
    assert record.generations == (GenerationRequirement(DATASET_REF, DS),)
    assert assess(record).is_current


def test_a_selection_records_its_scenario_requirement():
    # SYNTHETIC: a selection is scoped to its scenario, so its scenario token is checked.
    scenario = bound_plan()
    selection = job(406, "workflow_selection",
                    params={"scenario_id": 301, "scenario_generation": OTHER, "dataset_generation": DS},
                    deps=[live(dataset_dep(), DS), live(dep_of(scenario), SC)], policy=on("dataset", "scenario"))
    assert generation_reasons(assess(selection)) == [(R.GENERATION_MISMATCH, "scenario 301")]


def test_only_enabled_kinds_are_required():
    # SYNTHETIC: with only scenarios enabled, a mismatched dataset token is not consulted.
    record = stamped_des(dataset_token=OTHER, policy=on("scenario"))
    assert {requirement.ref.kind for requirement in record.generations} == {"scenario"}
    assert assess(record).is_current


@pytest.mark.parametrize("binding, code, upstream", [
    (DS, None, None),
    (OTHER, R.GENERATION_MISMATCH, R.UPSTREAM_MISSING_DEPENDENCY),
    (None, R.GENERATION_UNRECORDED, R.UPSTREAM_MISSING_PROVENANCE),
])
def test_the_scenario_dataset_binding_is_checked_and_carries_to_its_evidence(binding, code, upstream):
    # SYNTHETIC: the plan's recorded dataset_generation against the dataset's live token.
    scenario = bound_plan(binding)
    alone = assess(scenario)
    evidence = assess(stamped_des(scenario=scenario))
    if code is None:
        assert alone.is_current and evidence.is_current
        return
    assert generation_reasons(alone) == [(code, str(DATASET_REF))]
    assert alone.status is es.REASON_STATUS[code]
    assert (upstream, "scenario 301") in [(reason.code, reason.subject) for reason in evidence.reasons]
    assert not evidence.is_current


def test_the_scenario_binding_is_not_read_while_dataset_generations_are_off():
    # SYNTHETIC
    assert bound_plan(OTHER, policy=on("scenario")).generations == ()
    assert assess(bound_plan(OTHER, policy=on("scenario"))).is_current


# ── Existing reasons are kept, and never duplicated ────────────────────────


@pytest.mark.parametrize("dependency", [
    Dependency(DATASET_REF, exists=False, generation=DS),
    Dependency(DATASET_REF, True, OWNER, 999, at(0), generation=DS),
    Dependency(DATASET_REF, True, 999, ANALYSIS, at(0), generation=DS),
])
@pytest.mark.parametrize("recorded", [DS, OTHER, None])
def test_a_missing_or_out_of_scope_dependency_keeps_only_its_own_reason(dependency, recorded):
    # SYNTHETIC: no generation reason is added where the record itself cannot be established.
    record = job(407, "workflow_des_current", params={"dataset_generation": recorded}, deps=[dependency],
                 policy=on("dataset"))
    result = assess(record)
    assert generation_reasons(result) == []
    own = R.DEPENDENCY_MISSING if not dependency.exists else R.DEPENDENCY_OUT_OF_SCOPE
    assert [reason.code for reason in result.reasons if reason.subject == str(DATASET_REF)] == [own]


def test_a_required_dependency_that_was_never_supplied_is_unassessed_once():
    # SYNTHETIC: the existing "not resolved" reason, no generation reason on top.
    record = job(408, "workflow_des_current", params={"dataset_generation": DS}, deps=[], policy=on("dataset"))
    result = assess(record)
    assert generation_reasons(result) == []
    assert [(reason.code, reason.detail) for reason in result.reasons if reason.subject == str(DATASET_REF)] == [
        (R.DEPENDENCY_UNASSESSED, "The referenced record was not resolved.")]


def test_a_generation_requirement_without_its_dependency_is_unassessed():
    # SYNTHETIC (hand-built record): a requirement alone makes its reference required, so a record
    # that names a token but supplies no dependency for it is never current.
    record = replace(job(417, "workflow_des_current", deps=[live(dataset_dep(), DS)], policy=on("dataset")),
                     generations=(GenerationRequirement(DATASET_REF, DS),
                                  GenerationRequirement(ArtifactRef("scenario", 999), SC)))
    result = assess(record)
    assert [(reason.code, reason.detail) for reason in result.reasons if reason.subject == "scenario 999"] == [
        (R.DEPENDENCY_UNASSESSED, "The referenced record was not resolved.")]
    assert not result.is_current


def test_a_matching_token_does_not_hide_a_dependency_created_after_the_job():
    # SYNTHETIC: DEPENDENCY_CREATED_AFTER stays (spec §9).
    record = job(409, "workflow_des_current", params={"dataset_generation": DS},
                 deps=[live(dataset_dep(created_at=at(30)), DS)], policy=on("dataset"))
    result = assess(record)
    assert R.DEPENDENCY_CREATED_AFTER in result.codes
    assert generation_reasons(result) == []


def test_every_applicable_reason_is_kept_under_one_headline():
    # SYNTHETIC: a mismatch, a dependency newer than the job, a replaced dataset and a changed Setup.
    record = job(410, "workflow_des_current",
                 params={"dataset_id": 200, "dataset_generation": OTHER, "setup_hash": "fp-old"},
                 deps=[live(dataset_dep(200, created_at=at(30)), DS)], policy=on("dataset"))
    result = assess(record)
    assert {R.GENERATION_MISMATCH, R.DEPENDENCY_CREATED_AFTER, R.DATASET_NOT_CURRENT, R.SETUP_CHANGED} <= set(
        result.codes)
    assert result.status is S.MISSING_DEPENDENCY


def test_generation_results_do_not_depend_on_input_order():
    # SYNTHETIC
    scenario = bound_plan(OTHER)
    record = stamped_des(scenario=scenario, dataset_token=None, live_scenario=None)
    expected = assess(record)
    for dependencies in itertools.permutations(record.dependencies):
        for generations in itertools.permutations(record.generations):
            shuffled = replace(record, dependencies=tuple(dependencies), generations=tuple(generations))
            assert assess(shuffled) == expected


def test_malformed_generation_input_is_rejected():
    # SYNTHETIC: jobs never carry a token, so they cannot be enabled; a repeated requirement is refused.
    with pytest.raises(ValueError, match="No generation token is recorded"):
        on("job:workflow_des")
    record = stamped_des()
    with pytest.raises(ValueError, match="records a generation twice"):
        assess(replace(record, generations=record.generations + record.generations[:1]))


# ── G-T13: with no generation kind enabled, nothing changes ─────────────────


def _records(policy: EvidencePolicy, dataset_token: Any, scenario_token: Any, binding: Any,
             live_dataset: Any, live_scenario: Any) -> list[es.EvidenceRecord]:
    """Records covering Step 1–5 outcomes, built with the given token data (SYNTHETIC)."""
    tokens = {"dataset_generation": dataset_token, "scenario_generation": scenario_token}
    scenario = bound_plan(binding, live_token=live_dataset, policy=policy)
    other_plan = bound_plan(binding, live_token=live_dataset, policy=policy, scenario_id=302)
    return [
        scenario,
        stamped_des(dataset_token=dataset_token, scenario_token=scenario_token, live_dataset=live_dataset,
                    live_scenario=live_scenario, scenario=scenario, policy=policy),
        job(411, "workflow_des_current", params=tokens, deps=[live(dataset_dep(), live_dataset)], policy=policy),
        job(412, "workflow_des_current", params={**tokens, "dataset_id": 200},
            deps=[live(dataset_dep(200), live_dataset)], policy=policy),
        job(413, "workflow_des_current", params=tokens,
            deps=[Dependency(DATASET_REF, exists=False, generation=live_dataset)], policy=policy),
        job(414, "workflow_des_current", params=tokens,
            deps=[live(dataset_dep(created_at=at(30)), live_dataset)], policy=policy),
        job(415, "workflow_mc", params={**tokens, "scenario_id": 302, "engine": es.SELECTED_MC_ENGINE},
            deps=[live(dataset_dep(), live_dataset), live(dep_of(other_plan), live_scenario)], policy=policy),
        job(416, "workflow_des_current", params={**tokens, "setup_hash": "fp-old"},
            deps=[live(dataset_dep(), live_dataset)], policy=policy),
    ]


TOKEN_DATA = [
    (DS, SC, DS, DS, SC),                      # everything matches
    (OTHER, OTHER, OTHER, DS, SC),             # everything mismatches
    (None, None, None, DS, SC),                # nothing recorded
    ("", "   ", "", DS, SC),                   # blank text recorded
    (int(DIGITS), True, 1.5, DIGITS, SC),      # values that are not text
    (DS, SC, DS, None, None),                  # live tokens not supplied
]


@pytest.mark.parametrize("token_data", TOKEN_DATA)
def test_flag_off_results_are_identical_with_or_without_token_data(token_data):
    # SYNTHETIC (G-T13): the same records with no token data at all are the Step 1–5 baseline.
    off = syn_policy()
    assert off.generation_kinds == frozenset()
    baseline = [assess(record) for record in _records(off, None, None, None, None, None)]
    records = _records(off, *token_data)
    assert all(record.generations == () for record in records)
    assert [assess(record) for record in records] == baseline
    # The baseline itself exercises current, stale, missing and upstream outcomes.
    assert {result.status for result in baseline} >= {S.CURRENT, S.STALE_DATASET, S.MISSING_DEPENDENCY,
                                                      S.STALE_SETUP}


def test_the_application_policy_enables_no_generation_kind():
    # SYNTHETIC-free: the only policy the application builds (G5 is not wired).
    from backend.api.workflow import _current_evidence_policy

    assert _current_evidence_policy().generation_kinds == frozenset()


def test_recorded_legacy_scenario_is_never_current_under_generation_enforcement():
    # RECORDED: scenario 30 (analysis 21, dataset 35) was exported before any token existed.
    context = recorded_context(SCENARIOS[30]["analysis_id"])
    off = es.classify(recorded_scenario(30, repository_policy()), context)
    assert off.is_current
    enforced = replace(repository_policy(), generation_kinds=frozenset({"dataset", "scenario"}))
    result = es.classify(recorded_scenario(30, enforced), context)
    assert result.status is S.MISSING_PROVENANCE
    assert {R.GENERATION_UNRECORDED, R.DEPENDENCY_UNASSESSED} <= set(result.codes)
