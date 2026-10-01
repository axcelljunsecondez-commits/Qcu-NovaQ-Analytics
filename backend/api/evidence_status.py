"""Evidence status: one pure classifier for stored workflow evidence.

Spec: docs/superpowers/specs/2026-09-25-analytical-versioning-historical-evidence.md, section 4.
Plan: Step 1. Nothing in the application calls this module yet; a test enforces that.

The classifier decides whether a stored scenario or workflow job may be used as *current*
evidence for one analysis. It reads only recorded identity and provenance (ids, setup hash,
version strings, execution basis, link ids, creation times) and never a metric: a cost, wait
or utilization value never changes a status, and a missing one is never read as zero or as a
sign of an older engine. Every failed check becomes a Reason; the primary status is the
highest-precedence status among them (``CURRENT`` when there is none).

Version knowledge is not built in. The caller supplies an ``EvidencePolicy`` that lists, per
version family, the values that are current, historical (known and recalculable) and
unsupported; anything else recorded is unrecognized. A required value that is not recorded is
missing provenance, never an old version.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class EvidenceStatus(str, Enum):
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    UNSUPPORTED = "UNSUPPORTED"
    STALE_DATASET = "STALE_DATASET"
    STALE_SETUP = "STALE_SETUP"
    HISTORICAL_REQUIRES_RECALCULATION = "HISTORICAL_REQUIRES_RECALCULATION"
    HISTORICAL_VIEWABLE = "HISTORICAL_VIEWABLE"
    CURRENT = "CURRENT"


# First entry wins. An engine problem (UNSUPPORTED, HISTORICAL_REQUIRES_RECALCULATION) and a
# dataset or setup change are separate statuses with separate reasons.
PRECEDENCE: tuple[EvidenceStatus, ...] = (
    EvidenceStatus.MISSING_DEPENDENCY,
    EvidenceStatus.MISSING_PROVENANCE,
    EvidenceStatus.UNSUPPORTED,
    EvidenceStatus.STALE_DATASET,
    EvidenceStatus.STALE_SETUP,
    EvidenceStatus.HISTORICAL_REQUIRES_RECALCULATION,
    EvidenceStatus.HISTORICAL_VIEWABLE,
    EvidenceStatus.CURRENT,
)


class ReasonCode(str, Enum):
    # MISSING_DEPENDENCY: a referenced record is absent or not this analysis's.
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DEPENDENCY_OUT_OF_SCOPE = "DEPENDENCY_OUT_OF_SCOPE"
    DEPENDENCY_CREATED_AFTER = "DEPENDENCY_CREATED_AFTER"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    # MISSING_PROVENANCE: an identity needed to decide currentness is not recorded or not established.
    ANALYSIS_UNRECORDED = "ANALYSIS_UNRECORDED"
    OWNER_UNRECORDED = "OWNER_UNRECORDED"
    DATASET_UNRECORDED = "DATASET_UNRECORDED"
    SETUP_UNRECORDED = "SETUP_UNRECORDED"
    VERSION_UNRECORDED = "VERSION_UNRECORDED"
    REFERENCE_UNRECORDED = "REFERENCE_UNRECORDED"
    CREATION_TIME_UNRECORDED = "CREATION_TIME_UNRECORDED"
    DEPENDENCY_UNASSESSED = "DEPENDENCY_UNASSESSED"
    GENERATION_UNRECORDED = "GENERATION_UNRECORDED"
    RESULT_INCOMPLETE = "RESULT_INCOMPLETE"
    # UNSUPPORTED: a recorded version is not interpretable, or the result records the
    # calculation itself as unsupported.
    VERSION_UNSUPPORTED = "VERSION_UNSUPPORTED"
    VERSION_UNRECOGNIZED = "VERSION_UNRECOGNIZED"
    CALCULATION_UNSUPPORTED = "CALCULATION_UNSUPPORTED"
    # STALE_DATASET
    DATASET_NOT_CURRENT = "DATASET_NOT_CURRENT"
    NO_CURRENT_DATASET = "NO_CURRENT_DATASET"
    # STALE_SETUP
    SETUP_CHANGED = "SETUP_CHANGED"
    SETUP_QUEUE_TYPE_MISMATCH = "SETUP_QUEUE_TYPE_MISMATCH"
    # HISTORICAL_REQUIRES_RECALCULATION
    VERSION_HISTORICAL = "VERSION_HISTORICAL"
    # HISTORICAL_VIEWABLE
    SUPERSEDED = "SUPERSEDED"
    # Chain rule: an upstream artifact that is not CURRENT, by its primary status.
    UPSTREAM_MISSING_DEPENDENCY = "UPSTREAM_MISSING_DEPENDENCY"
    UPSTREAM_MISSING_PROVENANCE = "UPSTREAM_MISSING_PROVENANCE"
    UPSTREAM_UNSUPPORTED = "UPSTREAM_UNSUPPORTED"
    UPSTREAM_STALE_DATASET = "UPSTREAM_STALE_DATASET"
    UPSTREAM_STALE_SETUP = "UPSTREAM_STALE_SETUP"
    UPSTREAM_HISTORICAL_REQUIRES_RECALCULATION = "UPSTREAM_HISTORICAL_REQUIRES_RECALCULATION"
    UPSTREAM_HISTORICAL_VIEWABLE = "UPSTREAM_HISTORICAL_VIEWABLE"


_S = EvidenceStatus
_R = ReasonCode
# Every reason code contributes exactly one status.
REASON_STATUS: Mapping[ReasonCode, EvidenceStatus] = {
    _R.OUT_OF_SCOPE: _S.MISSING_DEPENDENCY,
    _R.DEPENDENCY_MISSING: _S.MISSING_DEPENDENCY,
    _R.DEPENDENCY_OUT_OF_SCOPE: _S.MISSING_DEPENDENCY,
    _R.DEPENDENCY_CREATED_AFTER: _S.MISSING_DEPENDENCY,
    _R.GENERATION_MISMATCH: _S.MISSING_DEPENDENCY,
    _R.ANALYSIS_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.OWNER_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.DATASET_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.SETUP_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.VERSION_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.REFERENCE_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.CREATION_TIME_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.DEPENDENCY_UNASSESSED: _S.MISSING_PROVENANCE,
    _R.GENERATION_UNRECORDED: _S.MISSING_PROVENANCE,
    _R.RESULT_INCOMPLETE: _S.MISSING_PROVENANCE,
    _R.VERSION_UNSUPPORTED: _S.UNSUPPORTED,
    _R.VERSION_UNRECOGNIZED: _S.UNSUPPORTED,
    _R.CALCULATION_UNSUPPORTED: _S.UNSUPPORTED,
    _R.DATASET_NOT_CURRENT: _S.STALE_DATASET,
    _R.NO_CURRENT_DATASET: _S.STALE_DATASET,
    _R.SETUP_CHANGED: _S.STALE_SETUP,
    _R.SETUP_QUEUE_TYPE_MISMATCH: _S.STALE_SETUP,
    _R.VERSION_HISTORICAL: _S.HISTORICAL_REQUIRES_RECALCULATION,
    _R.SUPERSEDED: _S.HISTORICAL_VIEWABLE,
    _R.UPSTREAM_MISSING_DEPENDENCY: _S.MISSING_DEPENDENCY,
    _R.UPSTREAM_MISSING_PROVENANCE: _S.MISSING_PROVENANCE,
    _R.UPSTREAM_UNSUPPORTED: _S.UNSUPPORTED,
    _R.UPSTREAM_STALE_DATASET: _S.STALE_DATASET,
    _R.UPSTREAM_STALE_SETUP: _S.STALE_SETUP,
    _R.UPSTREAM_HISTORICAL_REQUIRES_RECALCULATION: _S.HISTORICAL_REQUIRES_RECALCULATION,
    _R.UPSTREAM_HISTORICAL_VIEWABLE: _S.HISTORICAL_VIEWABLE,
}

_UPSTREAM_CODE: Mapping[EvidenceStatus, ReasonCode] = {
    _S.MISSING_DEPENDENCY: _R.UPSTREAM_MISSING_DEPENDENCY,
    _S.MISSING_PROVENANCE: _R.UPSTREAM_MISSING_PROVENANCE,
    _S.UNSUPPORTED: _R.UPSTREAM_UNSUPPORTED,
    _S.STALE_DATASET: _R.UPSTREAM_STALE_DATASET,
    _S.STALE_SETUP: _R.UPSTREAM_STALE_SETUP,
    _S.HISTORICAL_REQUIRES_RECALCULATION: _R.UPSTREAM_HISTORICAL_REQUIRES_RECALCULATION,
    _S.HISTORICAL_VIEWABLE: _R.UPSTREAM_HISTORICAL_VIEWABLE,
}

# Kinds that are plain inputs, not classified evidence: their dependency is checked for
# existence, scope and creation order only.
PLAIN_KINDS = frozenset({"dataset"})


@dataclass(frozen=True)
class ArtifactRef:
    kind: str
    id: int | None

    def __str__(self) -> str:
        return f"{self.kind} {self.id if self.id is not None else '(unrecorded id)'}"


def _ref_key(ref: ArtifactRef) -> tuple[str, bool, int]:
    return (ref.kind, ref.id is None, ref.id if ref.id is not None else 0)


@dataclass(frozen=True)
class Reason:
    code: ReasonCode
    subject: str
    detail: str

    @property
    def status(self) -> EvidenceStatus:
        return REASON_STATUS[self.code]


def _sort_key(reason: Reason) -> tuple[int, str, str, str]:
    return (PRECEDENCE.index(reason.status), reason.code.value, reason.subject, reason.detail)


def primary_status(reasons: Iterable[Reason]) -> EvidenceStatus:
    """Highest-precedence status among the reasons; CURRENT only when there is none."""
    statuses = [reason.status for reason in reasons]
    if not statuses:
        return EvidenceStatus.CURRENT
    return min(statuses, key=PRECEDENCE.index)


@dataclass(frozen=True)
class VersionFamily:
    """Known values of one recorded version marker.

    ``current``: may be current evidence. ``historical``: a known earlier version whose
    results must be recalculated. ``unsupported``: known, not interpretable. Anything else
    recorded is unrecognized.
    """

    name: str
    current: frozenset[str]
    historical: frozenset[str] = frozenset()
    unsupported: frozenset[str] = frozenset()

    @classmethod
    def of(cls, name: str, *, current: Iterable[str], historical: Iterable[str] = (),
           unsupported: Iterable[str] = ()) -> VersionFamily:
        family = cls(name, frozenset(current), frozenset(historical), frozenset(unsupported))
        if not family.current:
            raise ValueError(f"Version family {name!r} needs at least one current value.")
        overlap = ((family.current & family.historical) | (family.current & family.unsupported)
                   | (family.historical & family.unsupported))
        if overlap:
            raise ValueError(f"Version family {name!r} lists {sorted(overlap)} in more than one class.")
        return family

    def classify(self, value: str) -> Literal["current", "historical", "unsupported", "unrecognized"]:
        if value in self.current:
            return "current"
        if value in self.historical:
            return "historical"
        if value in self.unsupported:
            return "unsupported"
        return "unrecognized"


@dataclass(frozen=True)
class VersionRequirement:
    """A version marker the artifact must carry, and the value it recorded (None: not recorded)."""

    family: VersionFamily
    recorded: str | None


@dataclass(frozen=True)
class GenerationRequirement:
    """The generation token the artifact recorded for one referenced record (None: not recorded).

    It must equal the live token the caller supplies on the matching ``Dependency``
    (spec 2026-09-26 §9). Only the kinds a policy enables in ``generation_kinds`` get one.
    """

    ref: ArtifactRef
    recorded: str | None


@dataclass(frozen=True)
class SetupBinding:
    """How the artifact records the Setup it describes.

    ``hash``: the recorded setup fingerprint (jobs, schema-2 plans). ``queue_type``: the queue
    type of a schema-1 snapshot, compared with the current Setup's queue type.
    """

    kind: Literal["hash", "queue_type"]
    recorded: str | None


@dataclass(frozen=True)
class CurrentContext:
    """What is current for one analysis, established by the caller from stored records."""

    analysis_id: int
    owner_id: int
    current_dataset_id: int | None      # None: the analysis has no valid dataset
    setup_fingerprint: str
    setup_queue_type: str | None        # None: the current Setup's queue type is not verifiable


@dataclass(frozen=True)
class Dependency:
    """A record the artifact references, as found by the caller.

    ``exists`` False means the referenced id resolves to nothing. For evidence kinds
    (anything not in PLAIN_KINDS) ``record`` must be supplied so the chain rule can apply.
    ``generation`` is the referenced row's live generation token as the caller read it; None means
    it was not supplied.
    """

    ref: ArtifactRef
    exists: bool
    owner_id: int | None = None
    analysis_id: int | None = None
    created_at: datetime | None = None
    record: EvidenceRecord | None = None
    generation: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    """Recorded identity of one stored artifact. No metric belongs here."""

    ref: ArtifactRef
    owner_id: int | None
    analysis_id: int | None
    created_at: datetime | None
    dataset_id: int | None
    setup: SetupBinding
    versions: tuple[VersionRequirement, ...] = ()
    required_refs: tuple[ArtifactRef, ...] = ()
    unrecorded_refs: tuple[str, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    result_complete: bool = True
    calculation_unsupported: bool = False
    superseded_by: ArtifactRef | None = None
    generations: tuple[GenerationRequirement, ...] = ()


@dataclass(frozen=True)
class EvidenceAssessment:
    ref: ArtifactRef
    status: EvidenceStatus
    reasons: tuple[Reason, ...]
    dependencies: tuple[EvidenceAssessment, ...]

    @property
    def is_current(self) -> bool:
        return self.status is EvidenceStatus.CURRENT

    @property
    def codes(self) -> tuple[ReasonCode, ...]:
        return tuple(reason.code for reason in self.reasons)


def classify(record: EvidenceRecord, context: CurrentContext) -> EvidenceAssessment:
    """Classify one artifact (and, recursively, its evidence dependencies) for ``context``.

    Deterministic: reasons are de-duplicated and sorted by (precedence, code, subject, detail),
    and dependency assessments by reference, so input order never changes the result.
    """
    return _classify(record, context, ())


def _classify(record: EvidenceRecord, context: CurrentContext,
              stack: tuple[ArtifactRef, ...]) -> EvidenceAssessment:
    if record.ref in stack:
        raise ValueError(f"Dependency cycle through {record.ref}.")
    stack = (*stack, record.ref)
    reasons: set[Reason] = set()

    def add(code: ReasonCode, subject: str, detail: str) -> None:
        reasons.add(Reason(code, subject, detail))

    this = str(record.ref)

    # Scope: the artifact must be this analysis's, for this owner.
    if record.analysis_id is None:
        add(_R.ANALYSIS_UNRECORDED, this, "The owning analysis is not recorded.")
    elif record.analysis_id != context.analysis_id:
        add(_R.OUT_OF_SCOPE, this, f"Recorded for analysis {record.analysis_id}, not {context.analysis_id}.")
    if record.owner_id is None:
        add(_R.OWNER_UNRECORDED, this, "The owner is not recorded.")
    elif record.owner_id != context.owner_id:
        add(_R.OUT_OF_SCOPE, this, "The artifact is not owned by the analysis owner.")
    if record.created_at is None:
        add(_R.CREATION_TIME_UNRECORDED, this, "The creation time is not recorded.")
    if not record.result_complete:
        add(_R.RESULT_INCOMPLETE, this, "No completed result is recorded.")

    # Dependencies: existence, scope, creation order, and the chain rule.
    by_ref = {dependency.ref: dependency for dependency in record.dependencies}
    if len(by_ref) != len(record.dependencies):
        raise ValueError(f"{this} lists a dependency twice.")
    # Generation identity (spec 2026-09-26 §9). A record carries requirements only for the kinds its
    # policy enables, so with none enabled nothing below changes.
    generation_of = {requirement.ref: requirement.recorded for requirement in record.generations}
    if len(generation_of) != len(record.generations):
        raise ValueError(f"{this} records a generation twice.")
    for name in sorted(set(record.unrecorded_refs)):
        add(_R.REFERENCE_UNRECORDED, this, f"The required {name} reference is not recorded.")
    required = set(record.required_refs) | set(generation_of)
    if record.dataset_id is not None:
        # A recorded dataset id counts only once its existence and scope are established.
        required.add(ArtifactRef("dataset", record.dataset_id))
    for ref in sorted(required, key=_ref_key):
        if ref not in by_ref:
            add(_R.DEPENDENCY_UNASSESSED, str(ref), "The referenced record was not resolved.")
    upstream: list[EvidenceAssessment] = []
    for dependency in sorted(record.dependencies, key=lambda item: _ref_key(item.ref)):
        subject = str(dependency.ref)
        if not dependency.exists:
            add(_R.DEPENDENCY_MISSING, subject, "The referenced record does not exist.")
            continue
        if dependency.owner_id != context.owner_id or dependency.analysis_id != context.analysis_id:
            add(_R.DEPENDENCY_OUT_OF_SCOPE, subject,
                "The referenced record is not the analysis owner's or belongs to another analysis.")
            continue
        if dependency.created_at is None or record.created_at is None:
            add(_R.CREATION_TIME_UNRECORDED, subject, "Creation order cannot be verified.")
        elif dependency.created_at > record.created_at:
            add(_R.DEPENDENCY_CREATED_AFTER, subject,
                f"The referenced record was created after {this}; the reference cannot be its own.")
        if dependency.ref in generation_of:
            recorded = _recorded_token(generation_of[dependency.ref])
            live = _recorded_token(dependency.generation)
            if recorded is None:
                add(_R.GENERATION_UNRECORDED, subject, "No generation token is recorded for the referenced record.")
            if live is None:
                add(_R.DEPENDENCY_UNASSESSED, subject, "The referenced record's generation token was not supplied.")
            elif recorded is not None and recorded != live:
                add(_R.GENERATION_MISMATCH, subject,
                    "The recorded generation token is not the referenced record's; the reference cannot be its own.")
        if dependency.ref.kind in PLAIN_KINDS:
            continue
        if dependency.record is None:
            add(_R.DEPENDENCY_UNASSESSED, subject, "The referenced evidence was not supplied for assessment.")
            continue
        if dependency.record.ref != dependency.ref:
            raise ValueError(f"Dependency {subject} carries the record of {dependency.record.ref}.")
        assessed = _classify(dependency.record, context, stack)
        upstream.append(assessed)
        if not assessed.is_current:
            add(_UPSTREAM_CODE[assessed.status], subject,
                f"Upstream evidence is {assessed.status.value}.")

    # Dataset: recorded, established as a dependency (above), and the analysis's current dataset.
    if record.dataset_id is None:
        add(_R.DATASET_UNRECORDED, this, "The dataset is not recorded.")
    else:
        if context.current_dataset_id is None:
            add(_R.NO_CURRENT_DATASET, this, "The analysis has no valid dataset.")
        elif record.dataset_id != context.current_dataset_id:
            add(_R.DATASET_NOT_CURRENT, this,
                f"Recorded dataset {record.dataset_id}; the current dataset is {context.current_dataset_id}.")

    # Setup.
    if record.setup.recorded is None:
        add(_R.SETUP_UNRECORDED, this, f"The setup {record.setup.kind} is not recorded.")
    elif record.setup.kind == "hash":
        if record.setup.recorded != context.setup_fingerprint:
            add(_R.SETUP_CHANGED, this, "The recorded setup fingerprint differs from the current Setup.")
    elif record.setup.recorded != context.setup_queue_type:
        add(_R.SETUP_QUEUE_TYPE_MISMATCH, this,
            f"Recorded queue type {record.setup.recorded!r}; the current Setup's is {context.setup_queue_type!r}.")

    # Versions: recorded values against the supplied policy only.
    for requirement in record.versions:
        family = requirement.family
        value = requirement.recorded
        if value is None:
            add(_R.VERSION_UNRECORDED, family.name, f"{family.name} is not recorded.")
            continue
        kind = family.classify(value)
        if kind == "historical":
            add(_R.VERSION_HISTORICAL, family.name,
                f"Recorded {value!r} is a known earlier {family.name}; recalculate under a current one.")
        elif kind == "unsupported":
            add(_R.VERSION_UNSUPPORTED, family.name, f"Recorded {value!r} is not supported.")
        elif kind == "unrecognized":
            add(_R.VERSION_UNRECOGNIZED, family.name, f"Recorded {value!r} is not a known {family.name}.")

    if record.calculation_unsupported:
        add(_R.CALCULATION_UNSUPPORTED, this, "The stored result records the calculation as unsupported.")
    if record.superseded_by is not None:
        add(_R.SUPERSEDED, this, f"Superseded by {record.superseded_by}.")

    ordered = tuple(sorted(reasons, key=_sort_key))
    return EvidenceAssessment(
        ref=record.ref,
        status=primary_status(ordered),
        reasons=ordered,
        dependencies=tuple(sorted(upstream, key=lambda item: _ref_key(item.ref))),
    )


# ── Extraction from stored rows (pure) ──────────────────────────────────────


@dataclass(frozen=True)
class AccountingRequirement:
    """A recorded accounting marker a job kind must carry (none exists yet; plan Step 10)."""

    family: VersionFamily
    params_key: str
    job_kinds: frozenset[str]


#: Record kinds that carry a generation token (datasets and scenarios; spec 2026-09-26 §3). Jobs
#: never carry one, so they are not listed.
GENERATION_KINDS = frozenset({"dataset", "scenario"})


@dataclass(frozen=True)
class EvidencePolicy:
    """Version knowledge supplied by the caller; nothing here is read from the application.

    ``generation_kinds`` names the referenced kinds whose recorded generation token must match
    the live one. Empty (the default) turns generation enforcement off: records then carry no
    generation requirement and every result is what it was without them.
    """

    scenario_schema: VersionFamily
    separate_plan_engine: VersionFamily
    schema1_engine: VersionFamily
    job_kind: VersionFamily
    job_engine: VersionFamily
    selected_des_basis: VersionFamily
    workflow_engine: VersionFamily | None = None
    current_des_accounting: AccountingRequirement | None = None
    generation_kinds: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        unknown = set(self.generation_kinds) - GENERATION_KINDS
        if unknown:
            raise ValueError(f"No generation token is recorded for {sorted(unknown)}.")


SELECTED_DES_ENGINE = "selected-plan-routing-des"
SELECTED_MC_ENGINE = "selected-plan-measured-mc"


def recorded_text(value: Any) -> str | None:
    """A recorded marker as text. None, empty text: not recorded. A non-text value keeps its type
    in the text so it can never match a known version by coincidence (``2`` becomes ``"2"``, a
    bool or float is tagged)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return f"<bool:{value}>"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value if value.strip() else None
    return f"<{type(value).__name__}:{value!r}>"


def _recorded_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _recorded_token(value: Any) -> str | None:
    """A generation token as text. None or blank text: not recorded. Unlike ``recorded_text``, a
    value that is not text is never turned into plain digits: it stays tagged with its type, so it
    can never equal a live token (``123`` does not match ``"123"``)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return f"<{type(value).__name__}:{value!r}>"


def _generation_requirements(policy: EvidencePolicy,
                             recorded: Iterable[tuple[ArtifactRef, Any]]) -> tuple[GenerationRequirement, ...]:
    """One requirement per referenced record of an enabled kind, with the token recorded for it."""
    return tuple(GenerationRequirement(ref, _recorded_token(token))
                 for ref, token in recorded if ref.kind in policy.generation_kinds)


def scenario_record(*, scenario_id: int, owner_id: int | None, analysis_id: int | None,
                    dataset_id: int | None, created_at: datetime | None, settings: Mapping[str, Any] | None,
                    policy: EvidencePolicy, snapshot_queue_type: str | None,
                    dependencies: Sequence[Dependency] = (), dataset_generation: Any = None) -> EvidenceRecord:
    """Recorded identity of a saved scenario.

    Reads ``settings["calculation"]`` keys ``schema_version``, ``engine_version`` and
    ``setup_hash`` only. ``snapshot_queue_type`` is the schema-1 snapshot's queue type as the
    existing ``_legacy_snapshot_queue_type`` computes it; it is ignored for schema 2.
    ``dataset_generation`` is the scenario's recorded dataset binding; it is read only when the
    policy enables dataset generations.
    """
    calculation = (settings or {}).get("calculation")
    snapshot: Mapping[str, Any] = calculation if isinstance(calculation, Mapping) else {}
    schema = recorded_text(snapshot.get("schema_version"))
    engine = recorded_text(snapshot.get("engine_version"))
    versions = [VersionRequirement(policy.scenario_schema, schema)]
    # Schema meanings as saved (scenarios.py _verify_calculation): 2 is a Separate-Queue plan with
    # a server-stamped setup_hash; 1 is a shared optimization whose Setup identity is its queue type.
    setup = SetupBinding("hash", recorded_text(snapshot.get("setup_hash")))
    if schema == "2":
        versions.append(VersionRequirement(policy.separate_plan_engine, engine))
    elif schema == "1":
        versions.append(VersionRequirement(policy.schema1_engine, engine))
        setup = SetupBinding("queue_type", snapshot_queue_type)
    bindings = [(ArtifactRef("dataset", dataset_id), dataset_generation)] if dataset_id is not None else []
    return EvidenceRecord(
        ref=ArtifactRef("scenario", scenario_id), owner_id=owner_id, analysis_id=analysis_id,
        created_at=created_at, dataset_id=dataset_id, setup=setup, versions=tuple(versions),
        dependencies=tuple(dependencies), generations=_generation_requirements(policy, bindings),
    )


@dataclass(frozen=True)
class JobReferences:
    """The records a stored job references, read from its recorded link fields."""

    refs: tuple[ArtifactRef, ...]
    unrecorded: tuple[str, ...]


def job_references(kind: str, params: Mapping[str, Any] | None,
                   result: Mapping[str, Any] | None) -> JobReferences:
    """Which records a job references, from recorded params/result keys only.

    Scenario-scoped kinds need ``scenario_id``. Selected-plan jobs are recognized by recorded
    markers only: ``params.engine`` for MC, ``result.provenance == "SELECTED"`` for validation
    and decision. A selected decision also references ``result.evidence_ids["selection"]``; a
    legacy decision references the non-null ids of ``result.evidence_ids``.
    """
    params = params or {}
    result = result or {}
    refs: list[ArtifactRef] = []
    unrecorded: list[str] = []

    def need(name: str, source: Mapping[str, Any], key: str, ref_kind: str) -> None:
        value = _recorded_int(source.get(key))
        if value is None:
            unrecorded.append(name)
        else:
            refs.append(ArtifactRef(ref_kind, value))

    scoped = {"workflow_selection", "workflow_des", "workflow_mc", "workflow_validation", "workflow_decision"}
    if kind in scoped:
        need("scenario", params, "scenario_id", "scenario")
    selected = result.get("provenance") == "SELECTED"
    if kind == "workflow_mc" and params.get("engine") == SELECTED_MC_ENGINE:
        need("selected-plan DES job", params, "des_job_id", "job:workflow_des")
    elif kind == "workflow_validation" and selected:
        need("selected-plan DES job", params, "des_job_id", "job:workflow_des")
        need("selected-plan MC job", params, "mc_job_id", "job:workflow_mc")
    elif kind == "workflow_decision" and selected:
        need("selected-plan validation job", params, "validation_job_id", "job:workflow_validation")
        need("selected-plan DES job", params, "des_job_id", "job:workflow_des")
        need("selected-plan MC job", params, "mc_job_id", "job:workflow_mc")
        # create_selected_decision records the selection it was decided under in evidence_ids.
        ids = result.get("evidence_ids")
        need("selection job", ids if isinstance(ids, Mapping) else {}, "selection", "job:workflow_selection")
    elif kind == "workflow_decision":
        ids = result.get("evidence_ids")
        if not isinstance(ids, Mapping):
            unrecorded.append("evidence_ids")
        else:
            for key, ref_kind in (("selection", "job:workflow_selection"), ("des", "job:workflow_des"),
                                  ("mc", "job:workflow_mc"), ("validation", "job:workflow_validation")):
                value = _recorded_int(ids.get(key))
                if value is not None:
                    refs.append(ArtifactRef(ref_kind, value))
    elif kind == "workflow_validation_current":
        need("Current MC job", params, "mc_job_id", "job:workflow_mc_current")
    return JobReferences(tuple(refs), tuple(unrecorded))


def _all_rows_unsupported(result: Mapping[str, Any]) -> bool:
    rows = result.get("results")
    return (isinstance(rows, list) and bool(rows)
            and all(isinstance(row, Mapping) and row.get("simulation_supported") is False for row in rows))


def _has_separate_rows(result: Mapping[str, Any]) -> bool:
    rows = result.get("results")
    return isinstance(rows, list) and any(
        isinstance(row, Mapping) and row.get("queue_structure") == "separate" for row in rows)


def job_record(*, job_id: int, kind: str, status: str, owner_id: int | None, created_at: datetime | None,
               params: Mapping[str, Any] | None, result: Mapping[str, Any] | None, policy: EvidencePolicy,
               dependencies: Sequence[Dependency] = (),
               superseded_by: ArtifactRef | None = None) -> EvidenceRecord:
    """Recorded identity of a stored workflow job.

    Reads params ``analysis_id``, ``dataset_id``, ``setup_hash``, ``engine_version``, ``engine``
    and the link ids; result ``execution`` (selected-plan DES basis), ``provenance``,
    ``evidence_ids``, and per result row ``queue_structure`` and ``simulation_supported``. The
    simulation basis is never inferred from costs or waits: a selected-plan DES without a
    recorded ``execution`` has missing provenance.

    For the kinds the policy enables, params ``dataset_generation`` and ``scenario_generation``
    become generation requirements on the recorded dataset and on the scenario the job references.
    A job that references no scenario (every Current kind) gets no scenario requirement, whatever
    its ``scenario_generation`` says.
    """
    params = params or {}
    result = result or {}
    versions = [VersionRequirement(policy.job_kind, recorded_text(kind))]
    if policy.workflow_engine is not None:
        versions.append(VersionRequirement(policy.workflow_engine, recorded_text(params.get("engine_version"))))
    engine = recorded_text(params.get("engine"))
    if engine is not None:
        versions.append(VersionRequirement(policy.job_engine, engine))
    if kind == "workflow_des" and engine == SELECTED_DES_ENGINE:
        versions.append(VersionRequirement(policy.selected_des_basis, recorded_text(result.get("execution"))))
    accounting = policy.current_des_accounting
    if accounting is not None and kind in accounting.job_kinds and _has_separate_rows(result):
        versions.append(VersionRequirement(accounting.family, recorded_text(params.get(accounting.params_key))))
    references = job_references(kind, params, result)
    dataset_id = _recorded_int(params.get("dataset_id"))
    bindings = [(ref, params.get("scenario_generation")) for ref in references.refs if ref.kind == "scenario"]
    if dataset_id is not None:
        bindings.append((ArtifactRef("dataset", dataset_id), params.get("dataset_generation")))
    return EvidenceRecord(
        ref=ArtifactRef(f"job:{kind}", job_id), owner_id=owner_id,
        analysis_id=_recorded_int(params.get("analysis_id")), created_at=created_at,
        dataset_id=dataset_id, setup=SetupBinding("hash", recorded_text(params.get("setup_hash"))),
        versions=tuple(versions), required_refs=references.refs, unrecorded_refs=references.unrecorded,
        dependencies=tuple(dependencies), result_complete=status == "completed",
        calculation_unsupported=_all_rows_unsupported(result), superseded_by=superseded_by,
        generations=_generation_requirements(policy, bindings),
    )
