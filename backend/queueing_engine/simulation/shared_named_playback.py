"""Event playback of one named-employee shared-queue DES replication (Phase 5B-4.5 of the shared-queue enhancement).

A playback is one identifiable replication, regenerated from its recorded inputs, root entropy, and
replication index through the Phase 5B-4.4 seed path, with a full trace. Its events are the named
engine's own two records, the customer trace and the employee transitions, interleaved exactly as
the engine recorded them (each customer event records how many transitions precede it). Nothing is
synthesized: a concept no engine event represents is listed as unsupported, never invented.

An independent replay rebuilds the line, every customer, every employee, and every register from
those events alone, checks the named-DES rules, and reconciles the result with the regenerated
engine result and the stored replication row. A failed check returns the check, the event, and
the evidence; the trace is never repaired. The replay draws no random numbers and simulates
nothing.

Spec: docs/superpowers/specs/2026-09-28-shared-queue-named-playback.md.
Nothing legacy imports this module. No API, database, or frontend uses it.
"""

from __future__ import annotations

import bisect
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import asdict
from numbers import Integral, Real
from typing import Any, NoReturn

from backend.queueing_engine.services.shared_segments import (
    DemandPeriod,
    OperatingHorizon,
    SharedSegmentError,
    StaffingSegment,
)
from backend.queueing_engine.services.shared_workforce import (
    AvailabilityWindow,
    BreakRequirement,
    BreakRule,
    Employee,
    EmployeePay,
    ScheduledBreak,
    ScheduledShift,
    ShiftRules,
    WorkforceRules,
)
from backend.queueing_engine.simulation.shared_continuous_des import (
    CLOSING_POLICIES,
    DRAIN,
    ENGINE_VERSION,
    HARD_CUTOFF,
)
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    BASE_STATES,
    BREAK_DUE,
    BREAK_END,
    CLOSING_INPUT,
    COMPLETED,
    COMPLETION,
    OFF,
    ON_BREAK,
    REGISTER_HANDOVER,
    REGISTER_STATES,
    SERVICE_START,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    SERVING_STATES,
    SHIFT_END,
    SHIFT_START,
    STAGES,
    STATE_MACHINE_VERSION,
    TRUNCATED_BY_CLOSING,
    UNFULFILLED,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_des import (
    ACCEPTING_STATES,
    DEPARTED,
    HARD_CUTOFF_REASON,
    NAMED_ENGINE_VERSION,
    NO_ELIGIBLE_EMPLOYEE,
    UNSERVED_AT_CLOSE,
    EmployeeDesPolicy,
)
from backend.queueing_engine.simulation.shared_named_replications import (
    METHOD_VERSION,
    named_inputs_digest,
    named_inputs_snapshot,
    named_replication_row,
    replication_seed_sequence,
    simulate_named_replication,
)
from backend.queueing_engine.simulation.shared_replications import SEED_SCHEME

# v2 (5B-4.5 hardening): the closing policy must be an approved value, and a malformed trace field fails a check
# instead of raising. Output for a valid trace is unchanged apart from the new check in validation.checks.
PLAYBACK_VERSION = "novaq-shared-named-playback-v2"

# ── Event vocabulary (from the named engine; anything else is rejected) ─────

CUSTOMER_EVENT_TYPES = {
    "arrival": "The customer arrives and joins the one shared line; the arrival is also the queue entry.",
    "service_start": "The customer at the head of the line starts service with the named employee at that register.",
    "service_end": "The service completes and the customer departs; no post-service time is modeled.",
    "closing": "The closing boundary at the horizon end, where the closing policy applies. No customer or employee.",
    "unserved_at_close": "A customer still waiting at closing leaves unserved (reason: the engine's customer row).",
}

# (stage, event, from_state, to_state) -> meaning. These are the transitions the Phase 5B-4.2 state machine
# emits under the named engine's inputs (shared_employee_states._set callers, driven by
# shared_named_des.simulate_named_prescribed).
EMPLOYEE_TRANSITIONS = {
    (COMPLETION, "employee_service_completion", SERVING, AVAILABLE): "The service completes; the register is kept.",
    (COMPLETION, "employee_service_completion", SERVING_BREAK_DUE, AVAILABLE): (
        "At closing only (approved Phase 5B-4.4 rule 1): the service completes, and the due break is cancelled."),
    (COMPLETION, "employee_break_start", SERVING_BREAK_DUE, ON_BREAK): (
        "The service completes and the due break starts; the register is freed."),
    (COMPLETION, "employee_service_completion", SERVING_SHIFT_ENDED, OFF): (
        "The last service completes and the employee is released; the register is freed."),
    (CLOSING_INPUT, "employee_release_input", AVAILABLE, OFF): "Released at or after closing (P5 or P6).",
    (CLOSING_INPUT, "employee_release_input", WAITING_FOR_REGISTER, OFF): "Released at closing while waiting (P5, P6).",
    (CLOSING_INPUT, "employee_release_input", SERVING, SERVING_SHIFT_ENDED): (
        "Released at closing while serving (P6): released at the completion."),
    (CLOSING_INPUT, "employee_release_input", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED): (
        "Released at closing while serving with a break due (P5, P6, P7): released at the completion."),
    (CLOSING_INPUT, "employee_break_truncated_at_closing", ON_BREAK, OFF): (
        "P7: the break in progress ends at closing (truncated_by_closing) and the employee is released."),
    (SHIFT_END, "employee_shift_end", AVAILABLE, OFF): "The scheduled shift end releases an idle employee.",
    (SHIFT_END, "employee_shift_end", WAITING_FOR_REGISTER, OFF): "The scheduled shift end releases a waiting employee.",
    (SHIFT_END, "employee_shift_end", SERVING, SERVING_SHIFT_ENDED): "The shift ends during a service (P3).",
    (SHIFT_END, "employee_shift_end", SERVING_BREAK_DUE, SERVING_SHIFT_ENDED): (
        "The shift ends during a service with a break due (P3)."),
    (BREAK_END, "employee_break_end", ON_BREAK, WAITING_FOR_REGISTER): "The break ends (completed); waiting for a register.",
    (BREAK_END, "employee_break_end", ON_BREAK, OFF): "The break ends (completed) after the shift end; released.",
    (BREAK_DUE, "employee_break_start", AVAILABLE, ON_BREAK): "A break falls due while idle and starts; register freed.",
    (BREAK_DUE, "employee_break_start", WAITING_FOR_REGISTER, ON_BREAK): "A break falls due while waiting and starts.",
    (BREAK_DUE, "employee_break_due_while_serving", SERVING, SERVING_BREAK_DUE): (
        "A break falls due during a service; it starts at the completion (P1, P2)."),
    (SHIFT_START, "employee_shift_start", OFF, WAITING_FOR_REGISTER): "A shift starts; the employee waits for a register.",
    (SHIFT_START, "employee_break_start_at_shift_start", OFF, ON_BREAK): "A shift starts with a break due at once.",
    (REGISTER_HANDOVER, "employee_register_assigned", WAITING_FOR_REGISTER, AVAILABLE): "A free register is assigned (P4).",
    (SERVICE_START, "employee_service_start", AVAILABLE, SERVING): "The employee takes the head of the line (X1, FCFS).",
}
# State-machine transitions the named engine's closing inputs never produce (INFERRED from
# shared_named_des._closing_inputs); the playback rejects them.
NOT_PRODUCED_BY_THE_NAMED_ENGINE = {
    (CLOSING_INPUT, "employee_breaks_cancelled_at_closing", SERVING_BREAK_DUE, SERVING): (
        "The crew is AVAILABLE or SERVING before closing, and a non-crew SERVING_BREAK_DUE employee gets Release "
        "before CancelPendingBreaks, so no cancel input finds an employee in SERVING_BREAK_DUE."),
    (CLOSING_INPUT, "employee_break_truncated_at_closing", ON_BREAK, WAITING_FOR_REGISTER): (
        "Every employee on a break before closing gets Release before EndBreakAtClosing, so the truncated break "
        "always ends in a release."),
}

UNSUPPORTED = {
    "customer_abandonment": "Not modeled by the named engine; no event exists.",
    "queue_entry_separate_from_arrival": "The arrival is the queue entry; no separate event exists.",
    "break_unfulfilled": (
        "A break that never starts (released, shift_not_activated, cancelled_at_closing) has no event; it is "
        "reported from the engine's break record under not_represented_by_events."),
    "shift_not_activated": (
        "A shift that never activates has no event; it is reported from the engine's shift record under "
        "not_represented_by_events."),
    "closing_inputs_without_a_state_change": (
        "A CancelPendingBreaks or Release input that changes no state (for example, Release to an employee on a "
        "break before EndBreakAtClosing) has no transition; the engine's at_close.closing_inputs lists every input."),
    "scheduled_and_required_staffing": (
        "The roster's scheduled_active and the required staffing come from inputs, not events; the playback does "
        "not recompute them or any gap."),
    "monetary_cost": "No pay or cost exists before Phase 5B-5.",
}

CHECKS = {
    "closing_policy": (
        "The closing policy is exactly one of the approved strings, DRAIN or HARD_CUTOFF (the engine's test); it is "
        "never normalized or inferred from the events."),
    "trace_complete": "The trace is not truncated.",
    "trace_structure": "Every record has the engine's fields, and the interleaving counts place every customer event.",
    "event_vocabulary": "Every customer event type and employee transition is in the named-engine vocabulary.",
    "time_order": "Timestamps never move backward.",
    "same_time_order": (
        "At one instant: service_end, closing, unserved_at_close, then the state machine's transitions in stage "
        "order, then arrivals, then each employee_service_start transition followed by its customer's "
        "service_start; employee_id order inside a stage; at closing, non-crew closing inputs before DRAIN releases; "
        "every completion transition pairs with its customer's service_end at that instant."),
    "customer_identity": "Arrivals are customers 1, 2, ... in order, and every later event names a known customer.",
    "customer_single_service": "A customer has at most one service, and its end matches its start.",
    "register_single_holder": "A register is held by at most one employee, and serving keeps the employee's register.",
    "register_capacity": (
        "Registers are numbered 1..K; with one holder per register, occupancy therefore never exceeds K."),
    "employee_transition_legal": (
        "Every transition starts from the replayed state and register and is a legal tuple. This also keeps an "
        "employee to one customer at a time: a service starts only from AVAILABLE, and a serving employee leaves the "
        "serving states only through a completion transition paired with its customer's service_end."),
    "no_register_off_break_waiting": "OFF, ON_BREAK, and WAITING_FOR_REGISTER hold no register; the others hold one.",
    "register_handover_order": "P4: earliest wait start, then employee_id, takes the lowest free register.",
    "fcfs": "Every service start and every unserved customer takes the head of the one line.",
    "x1_employee_choice": "X1: the AVAILABLE employee available longest, then the lowest employee_id, starts service.",
    "work_conservation": "After each instant, a waiting customer means no employee is AVAILABLE.",
    "service_duration": "Each service lasts unit_work / mu(start) exactly, the engine's non-preemptive service.",
    "closing_rules": (
        "One closing at the horizon end; no arrival, shift end, break, shift start, or handover at or after closing; "
        "closing inputs only at or after closing; P6 and P7 at closing; after closing only OFF, SERVING_SHIFT_ENDED, "
        "or (DRAIN) a serving crew member."),
    "hard_cutoff_no_start_after_closing": "Under HARD_CUTOFF no service starts at or after closing.",
    "drain_frozen_crew": (
        "Under DRAIN the crew is the employees AVAILABLE or SERVING immediately before closing; only they serve after "
        "closing, and at each instant the idle crew members X1 ranks after the waiting customers are released."),
    "unserved_reason": (
        "Unserved customers occur only at closing: hard_cutoff under HARD_CUTOFF, no_eligible_employee under DRAIN "
        "with an empty crew; then the line is empty."),
    "queue_reconciliation": "The rebuilt line length equals the engine's queue_len_after at every customer event.",
    "end_state": "The run ends with every customer resolved and the line empty.",
    "customer_reconciliation": "Rebuilt customers, counts, waits, closing state, and line integrals equal the result.",
    "employee_reconciliation": (
        "Rebuilt employee intervals, shifts, breaks, staffing series, and finish equal the employee timeline."),
}

TOLERANCE = {"rel": 1e-9, "abs": 1e-12}  # Phase 4 playback convention (shared_playback._TOLERANCE), float sums only
_CUSTOMER_SLOT = {"service_end": 0, "closing": 1, "unserved_at_close": 2, "arrival": 4, "service_start": 5}
_TRANSITION_SLOT, _PAIR_SLOT = 3, 5
_STAGE_RANK = {stage: rank for rank, stage in enumerate(STAGES)}
_ID_ORDERED_STAGES = frozenset({COMPLETION, SHIFT_END, BREAK_END, BREAK_DUE, SHIFT_START})
_KNOWN_EVENTS = frozenset(key[1] for key in EMPLOYEE_TRANSITIONS)
_TRACE_FIELDS = ("t", "type", "customer_id", "employee_id", "register_id", "queue_len_after",
                 "employee_transitions_before")
_TRANSITION_FIELDS = ("t", "stage", "employee_id", "from_state", "to_state", "register_before", "register_after",
                      "event")
_STATE_SERIES = {
    "accepting_capacity": ACCEPTING_STATES,
    "busy_employees": SERVING_STATES,
    "register_occupancy": REGISTER_STATES,
    "waiting_for_register": frozenset({WAITING_FOR_REGISTER}),
}
_WINDOW_SERIES = {"accepting_capacity_hours": "accepting_capacity", "busy_employee_hours": "busy_employees",
                  "register_occupancy_hours": "register_occupancy",
                  "waiting_for_register_hours": "waiting_for_register"}


class NamedPlaybackError(Exception):
    """A check failed, so no playback is produced. ``failure`` holds the check, message, and evidence."""

    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(f"{failure['check']}: {failure['message']}")
        self.failure = failure


class _Violation(Exception):
    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(failure["message"])
        self.failure = failure


def _fail(check: str, message: str, evidence: dict[str, Any] | None = None, **where: Any) -> _Violation:
    return _Violation({"check": check, "message": message, **where, "evidence": evidence or {}})


def _close_enough(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOLERANCE["rel"], abs_tol=TOLERANCE["abs"])


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _time(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _check_closing_policy(policy: object) -> None:
    # The engine's test (``closing_policy not in CLOSING_POLICIES``) behind a string test, so any other value fails this
    # check rather than raising (no hashing, and no equality with an arbitrary object). Exact and case-sensitive. The
    # events cannot decide it: a day with nobody to serve after closing records the same events under both policies.
    if not isinstance(policy, str) or policy not in CLOSING_POLICIES:
        raise _fail("closing_policy", "The closing policy must be exactly DRAIN or HARD_CUTOFF.",
                    {"closing_policy": policy, "approved": list(CLOSING_POLICIES)})


def _period(t: float, closing: float) -> str:
    if t < 0.0:
        return "before_opening"
    if t < closing:
        return "operating_horizon"
    return "closing" if t == closing else "after_closing"


# ── Independent replay ──────────────────────────────────────────────────────


class _Replay:
    """Rebuilds the line, customers, employees, and registers from the two engine records alone."""

    def __init__(self, result: dict[str, Any], horizon: OperatingHorizon, demand_periods: Sequence[DemandPeriod]) -> None:
        timeline = result["employee_timeline"]
        self.result = result
        self.closing = result["closing_time"]
        self.policy = result["closing_policy"]
        self.registers = timeline["register_count"]
        self.begin = result["begin"]
        self.ids = sorted(timeline["state_totals"])
        self.period_starts = [(period.start_minute - horizon.start_minute) / 60.0 for period in demand_periods]
        self.rates = [float(period.service_rate_per_hour) for period in demand_periods]
        self.engine_customers = result["customers"]
        self.queue: deque[int] = deque()
        self.customers: dict[int, dict[str, Any]] = {}
        self.state = dict.fromkeys(self.ids, OFF)
        self.register: dict[str, int | None] = dict.fromkeys(self.ids)
        self.available_since: dict[str, float] = {}
        self.wait_start: dict[str, float] = {}
        self.holders: dict[int, str] = {}
        self.since = dict.fromkeys(self.ids, self.begin)
        self.intervals: dict[str, list[list[Any]]] = {employee_id: [] for employee_id in self.ids}
        self.shifts: dict[str, list[dict[str, Any]]] = {employee_id: [] for employee_id in self.ids}
        self.breaks: dict[str, list[dict[str, Any]]] = {employee_id: [] for employee_id in self.ids}
        self.closed = False
        self.crew: list[str] | None = None
        self.on_break_at_closing: list[str] = []
        self.at_close: dict[str, Any] = {}
        self.instants: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.max_queue_in_horizon = 0
        self.last_t: float | None = None
        # Per-instant bookkeeping.
        self.instant: float | None = None
        self.slot = -1
        self.stage_rank = -1
        self.stage_ids: list[str] = []
        self.closing_crew_phase = False
        self.ended: list[int] = []
        self.completing: dict[str, int] = {}
        self.awaiting: str | None = None
        self.after_completions: dict[str, Any] | None = None
        self.crew_released: list[str] = []
        self.truncated: list[str] = []

    # ── helpers ────────────────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        return {name: sum(1 for state in self.state.values() if state in members)
                for name, members in _STATE_SERIES.items()}

    def mu(self, hour: float) -> float:
        return self.rates[bisect.bisect_right(self.period_starts, hour) - 1]

    def x1_order(self, candidates: Sequence[str]) -> list[str]:
        return sorted(candidates, key=lambda employee_id: (self.available_since[employee_id], employee_id))

    def snapshot_after_completions(self) -> None:
        if self.after_completions is None:
            idle = [employee_id for employee_id in (self.crew or []) if self.state[employee_id] == AVAILABLE]
            self.after_completions = {"idle_crew": idle, "queue": len(self.queue)}

    # ── instants ───────────────────────────────────────────────────────────

    def start_instant(self, t: float) -> None:
        self.instant, self.slot, self.stage_rank, self.stage_ids = t, -1, -1, []
        self.closing_crew_phase, self.ended = False, []
        self.completing, self.awaiting, self.after_completions = {}, None, None
        self.crew_released, self.truncated = [], []

    def finish_instant(self) -> None:
        t = self.instant
        if t is None:
            return
        where = {"t": t}
        if t >= self.closing and not self.closed:
            raise _fail("closing_rules", "No closing event at the horizon end precedes this instant.",
                        {"closing_time": self.closing}, **where)
        if self.awaiting is not None:
            raise _fail("same_time_order", "An employee_service_start transition has no customer service_start after it.",
                        {"employee_id": self.awaiting}, **where)
        if self.completing:
            raise _fail("same_time_order", "A service_end has no completion transition for its employee at that instant.",
                        {"employee_ids": sorted(self.completing)}, **where)
        self.snapshot_after_completions()
        if self.queue and any(state == AVAILABLE for state in self.state.values()):
            raise _fail("work_conservation", "Customers wait while an employee is AVAILABLE after the instant.",
                        {"queue": list(self.queue), "available": [e for e in self.ids if self.state[e] == AVAILABLE]},
                        **where)
        waiting = [employee_id for employee_id in self.ids if self.state[employee_id] == WAITING_FOR_REGISTER]
        if waiting and len(self.holders) < self.registers:
            raise _fail("register_handover_order", "An employee waits for a register while one is free.",
                        {"waiting": waiting, "held": dict(self.holders)}, **where)
        if t >= self.closing:
            self.finish_closing_instant(t)
        if t < self.closing:
            self.max_queue_in_horizon = max(self.max_queue_in_horizon, len(self.queue))
        self.instants.append({"t": t, "period": _period(t, self.closing), "queue_len": len(self.queue), **self.counts()})

    def finish_closing_instant(self, t: float) -> None:
        where = {"t": t}
        assert self.crew is not None and self.after_completions is not None
        if t == self.closing:
            missing = sorted(set(self.on_break_at_closing) - set(self.truncated))
            if missing:
                raise _fail("closing_rules", "P7: a break in progress at closing was not truncated at closing.",
                            {"employee_ids": missing}, **where)
            if (self.policy == HARD_CUTOFF or not self.crew) and self.queue:
                raise _fail("unserved_reason", "Customers still wait after closing although none can be served.",
                            {"queue": list(self.queue), "crew": self.crew}, **where)
        if self.policy == DRAIN:
            idle = self.x1_order(self.after_completions["idle_crew"])
            expected = sorted(idle[self.after_completions["queue"]:])
            if self.crew_released != expected:
                raise _fail("drain_frozen_crew", "DRAIN releases differ from the idle crew X1 ranks after the line "
                            "(released in employee_id order).",
                            {"released": self.crew_released, "expected": expected, "idle_crew_x1": idle,
                             "waiting": self.after_completions["queue"]}, **where)
        for employee_id in self.ids:
            state = self.state[employee_id]
            allowed = {OFF, SERVING_SHIFT_ENDED} | ({SERVING} if employee_id in self.crew else set())
            if state not in allowed:
                raise _fail("closing_rules", "After closing only OFF, SERVING_SHIFT_ENDED, or a serving crew member.",
                            {"employee_id": employee_id, "state": state, "crew": self.crew}, **where)

    # ── ordering ───────────────────────────────────────────────────────────

    def order(self, slot: int, source: str, record: dict[str, Any], where: dict[str, Any]) -> None:
        if self.awaiting is not None and not (source == "customer" and record["type"] == "service_start"):
            raise _fail("same_time_order", "An employee_service_start transition must be followed at once by its "
                        "customer's service_start.", {"employee_id": self.awaiting}, **where)
        if slot < self.slot:
            raise _fail("same_time_order", "The event comes after a later same-time stage of the named-DES order.",
                        {"slot": slot, "previous_slot": self.slot}, **where)
        if slot > _TRANSITION_SLOT or (slot == _TRANSITION_SLOT and record["stage"] != COMPLETION):
            self.snapshot_after_completions()
        if slot != self.slot:
            self.slot, self.stage_rank, self.stage_ids = slot, -1, []
        if source == "customer":
            return
        stage, employee_id = record["stage"], record["employee_id"]
        if slot == _PAIR_SLOT:
            return
        rank = _STAGE_RANK[stage]
        if rank < self.stage_rank:
            raise _fail("same_time_order", "State-machine stages must follow the X2 order.",
                        {"stage": stage}, **where)
        if rank != self.stage_rank:
            self.stage_rank, self.stage_ids = rank, []
            self.closing_crew_phase = False
        if stage in _ID_ORDERED_STAGES:
            if self.stage_ids and employee_id <= self.stage_ids[-1]:
                raise _fail("same_time_order", f"Transitions of stage {stage} come in employee_id order, once each.",
                            {"previous_employee_id": self.stage_ids[-1]}, **where)
            self.stage_ids.append(employee_id)
        elif stage == CLOSING_INPUT:
            crew_member = employee_id in (self.crew or [])
            if crew_member and not self.closing_crew_phase:
                self.closing_crew_phase, self.stage_ids = True, []
            if not crew_member and self.closing_crew_phase:
                raise _fail("same_time_order", "Closing inputs for non-crew employees come before DRAIN releases.",
                            {"employee_id": employee_id}, **where)
            if self.stage_ids and employee_id <= self.stage_ids[-1]:
                raise _fail("same_time_order", "Closing-input transitions come in employee_id order within their group.",
                            {"previous_employee_id": self.stage_ids[-1]}, **where)
            self.stage_ids.append(employee_id)

    # ── customer events ────────────────────────────────────────────────────

    def customer_event(self, record: dict[str, Any], where: dict[str, Any]) -> dict[str, Any]:
        kind, t = record["type"], record["t"]
        customer_id, employee_id, register_id = record["customer_id"], record["employee_id"], record["register_id"]
        extra: dict[str, Any] = {}
        if kind == "closing":
            if customer_id is not None or employee_id is not None or register_id is not None:
                raise _fail("trace_structure", "The closing event names no customer, employee, or register.", **where)
            if self.closed or t != self.closing:
                raise _fail("closing_rules", "Exactly one closing event, at the horizon end.",
                            {"closing_time": self.closing}, **where)
            self.closed = True
            # The state here is the state immediately before closing: no transition at closing precedes this event.
            before = {employee_id: self.state[employee_id] for employee_id in self.ids}
            self.crew = [e for e in self.ids if before[e] in ACCEPTING_STATES] if self.policy == DRAIN else []
            self.on_break_at_closing = [e for e in self.ids if before[e] == ON_BREAK]
            self.at_close = {
                "waiting_customer_ids": list(self.queue),
                "in_service_customer_ids": sorted(c for c, row in self.customers.items()
                                                  if row["service_start_hours"] is not None and row["status"] is None),
                "drain_crew": list(self.crew),
            }
            extra = {"closing_policy": self.policy, "drain_crew": list(self.crew)}
            return extra
        if not _whole(customer_id):
            raise _fail("customer_identity", "A customer event must name a customer.", **where)
        if kind == "arrival":
            if customer_id != len(self.customers) + 1:
                raise _fail("customer_identity", "Arrivals must be customers 1, 2, ... in order, each once.",
                            {"expected_customer_id": len(self.customers) + 1}, **where)
            if employee_id is not None or register_id is not None:
                raise _fail("trace_structure", "An arrival names no employee or register.", **where)
            if self.closed or t >= self.closing:
                raise _fail("closing_rules", "No arrival at or after closing.", **where)
            if t < 0.0:
                raise _fail("closing_rules", "No arrival before opening.", **where)
            self.customers[customer_id] = {
                "customer_id": customer_id, "arrival_hours": t, "service_start_hours": None, "service_end_hours": None,
                "employee_id": None, "register_id": None, "status": None,
            }
            self.queue.append(customer_id)
            return extra
        customer = self.customers.get(customer_id)
        if customer is None:
            raise _fail("customer_identity", "The event names a customer who has not arrived.", **where)
        if kind == "service_start":
            if self.awaiting is None or self.awaiting != employee_id:
                raise _fail("same_time_order", "A customer service_start must follow its employee's "
                            "employee_service_start transition at once.", {"awaiting": self.awaiting}, **where)
            self.awaiting = None
            if customer["service_start_hours"] is not None or customer["status"] is not None:
                raise _fail("customer_single_service", "The customer already has a service or an outcome.",
                            {"customer": dict(customer)}, **where)
            if not self.queue or self.queue[0] != customer_id:
                raise _fail("fcfs", "Service must start with the customer at the head of the line.",
                            {"queue_head": self.queue[0] if self.queue else None}, **where)
            if register_id != self.register[employee_id]:
                raise _fail("register_single_holder", "The service's register differs from the employee's register.",
                            {"employee_register": self.register[employee_id]}, **where)
            if self.closed and self.policy == HARD_CUTOFF:
                raise _fail("hard_cutoff_no_start_after_closing", "No service may start at or after a hard cutoff.",
                            **where)
            if self.closed and employee_id not in (self.crew or []):
                raise _fail("drain_frozen_crew", "Only the frozen crew serves after closing.",
                            {"crew": self.crew}, **where)
            self.queue.popleft()
            customer.update(service_start_hours=t, employee_id=employee_id, register_id=register_id)
            return extra
        if kind == "service_end":
            if self.ended and customer_id <= self.ended[-1]:
                raise _fail("same_time_order", "Completions at one instant come in customer_id order (the engine's "
                            "completion heap).", {"previous_customer_id": self.ended[-1]}, **where)
            self.ended.append(customer_id)
            if customer["service_start_hours"] is None or customer["status"] is not None:
                raise _fail("customer_single_service", "Only a customer in service can complete.",
                            {"customer": dict(customer)}, **where)
            if (employee_id, register_id) != (customer["employee_id"], customer["register_id"]):
                raise _fail("customer_single_service", "The service ends with a different employee or register.",
                            {"customer": dict(customer)}, **where)
            engine = self.engine_row(customer_id, where)
            expected = customer["service_start_hours"] + engine["unit_work"] / self.mu(customer["service_start_hours"])
            if t != expected:
                raise _fail("service_duration", "The service does not last unit_work / mu(start).",
                            {"expected_end": expected, "unit_work": engine["unit_work"]}, **where)
            customer.update(service_end_hours=t, status=DEPARTED)
            self.completing[employee_id] = customer_id
            return extra
        # unserved_at_close
        if employee_id is not None or register_id is not None:
            raise _fail("trace_structure", "An unserved customer names no employee or register.", **where)
        if not self.closed or t != self.closing:
            raise _fail("unserved_reason", "Customers are unserved only at closing.", **where)
        if not self.queue or self.queue[0] != customer_id:
            raise _fail("fcfs", "Unserved customers leave in line order.",
                        {"queue_head": self.queue[0] if self.queue else None}, **where)
        engine = self.engine_row(customer_id, where)
        expected_reason = HARD_CUTOFF_REASON if self.policy == HARD_CUTOFF else (
            NO_ELIGIBLE_EMPLOYEE if not self.crew else None)
        if expected_reason is None or engine["unserved_reason"] != expected_reason:
            raise _fail("unserved_reason", "The unserved reason is not the approved code for this policy and crew.",
                        {"reason": engine["unserved_reason"], "expected": expected_reason, "crew": self.crew}, **where)
        self.queue.popleft()
        customer["status"] = UNSERVED_AT_CLOSE
        return {"unserved_reason": engine["unserved_reason"]}

    def engine_row(self, customer_id: int, where: dict[str, Any]) -> dict[str, Any]:
        if not 1 <= customer_id <= len(self.engine_customers) or \
                self.engine_customers[customer_id - 1]["customer_id"] != customer_id:
            raise _fail("customer_identity", "The engine has no customer row for this customer.", **where)
        row: dict[str, Any] = self.engine_customers[customer_id - 1]
        return row

    # ── employee transitions ───────────────────────────────────────────────

    def transition(self, record: dict[str, Any], where: dict[str, Any]) -> None:
        t, stage, employee_id = record["t"], record["stage"], record["employee_id"]
        before, after = record["from_state"], record["to_state"]
        register_before, register_after = record["register_before"], record["register_after"]
        if (before, register_before) != (self.state[employee_id], self.register[employee_id]):
            raise _fail("employee_transition_legal", "The transition does not start from the replayed state and "
                        "register.", {"replayed_state": self.state[employee_id],
                                      "replayed_register": self.register[employee_id]}, **where)
        if (stage, record["event"], before, after) == (COMPLETION, "employee_service_completion", SERVING_BREAK_DUE,
                                                       AVAILABLE) and t != self.closing:
            raise _fail("employee_transition_legal", "A break-due completion ends AVAILABLE only at closing (rule 1).",
                        **where)
        if (after in REGISTER_STATES) != (register_after is not None):
            raise _fail("no_register_off_break_waiting", "OFF, ON_BREAK, and WAITING_FOR_REGISTER hold no register; "
                        "AVAILABLE and the serving states hold one.", **where)
        if t < self.closing and stage == CLOSING_INPUT:
            raise _fail("closing_rules", "Closing inputs apply only at or after closing.", **where)
        if t >= self.closing and stage not in (COMPLETION, CLOSING_INPUT, SERVICE_START):
            raise _fail("closing_rules", f"No {stage} transition at or after closing.", **where)
        if t >= self.closing and after == ON_BREAK:
            raise _fail("closing_rules", "No break starts at or after closing.", **where)
        # After the closing instant, a non-crew employee is OFF or SERVING_SHIFT_ENDED (finish_closing_instant), and no
        # legal closing-input transition starts there, so only crew members can be released after closing.
        # Registers.
        if before in REGISTER_STATES and after in REGISTER_STATES and register_after != register_before:
            raise _fail("register_single_holder", "An employee keeps its register between register states.", **where)
        if before not in REGISTER_STATES and after in REGISTER_STATES:
            self.handover(record, where)
        # Stage-specific checks.
        if stage == COMPLETION:
            if employee_id not in self.completing:
                raise _fail("same_time_order", "A completion transition needs its customer's service_end earlier at "
                            "this instant.", **where)
            del self.completing[employee_id]
        elif stage == SERVICE_START:
            available = [e for e in self.ids if self.state[e] == AVAILABLE]
            chosen = self.x1_order(available)[0]
            if employee_id != chosen:
                raise _fail("x1_employee_choice", "X1 gives the next customer to the AVAILABLE employee available "
                            "longest, then the lowest employee_id.",
                            {"expected": chosen, "available_since": {e: self.available_since[e] for e in available}},
                            **where)
            if not self.queue:
                raise _fail("fcfs", "A service starts while nobody waits.", **where)
            self.awaiting = employee_id
        elif stage == CLOSING_INPUT and employee_id in (self.crew or []):
            self.crew_released.append(employee_id)
        if record["event"] == "employee_break_truncated_at_closing":
            self.truncated.append(employee_id)
        self.apply(record)

    def handover(self, record: dict[str, Any], where: dict[str, Any]) -> None:
        register = record["register_after"]
        if not _whole(register) or not 1 <= register <= self.registers:
            raise _fail("register_capacity", f"Registers are numbered 1..{self.registers}.", **where)
        if register in self.holders:
            raise _fail("register_single_holder", "The register is already held.",
                        {"holder": self.holders[register]}, **where)
        waiting = sorted((self.wait_start[e], e) for e in self.ids if self.state[e] == WAITING_FOR_REGISTER)
        free = min(set(range(1, self.registers + 1)) - set(self.holders))
        if (record["employee_id"], register) != (waiting[0][1], free):
            raise _fail("register_handover_order", "P4: earliest wait start, then employee_id, takes the lowest free "
                        "register.", {"expected": (waiting[0][1], free)}, **where)

    def apply(self, record: dict[str, Any]) -> None:
        t, employee_id, before, after = record["t"], record["employee_id"], record["from_state"], record["to_state"]
        if t > self.since[employee_id]:
            self.intervals[employee_id].append([self.since[employee_id], t, before, self.register[employee_id]])
            self.since[employee_id] = t
        old, new = self.register[employee_id], record["register_after"]
        if old is not None and new is None:
            del self.holders[old]
        if old is None and new is not None:
            self.holders[new] = employee_id
        self.state[employee_id], self.register[employee_id] = after, new
        if after == AVAILABLE:
            self.available_since[employee_id] = t
        if after == WAITING_FOR_REGISTER:
            self.wait_start[employee_id] = t
        if before == OFF:
            self.shifts[employee_id].append({"employee_id": employee_id, "activation": t, "release": None})
        if after == OFF:
            self.shifts[employee_id][-1]["release"] = t
        if after == ON_BREAK:
            self.breaks[employee_id].append({"employee_id": employee_id, "actual_start": t, "actual_end": None,
                                             "outcome": None})
        if before == ON_BREAK:
            outcome = TRUNCATED_BY_CLOSING if record["event"] == "employee_break_truncated_at_closing" else COMPLETED
            self.breaks[employee_id][-1].update(actual_end=t, outcome=outcome)

    # ── the whole trace ────────────────────────────────────────────────────

    def run(self, merged: list[tuple[str, int, dict[str, Any]]]) -> None:
        for seq, (source, index, record) in enumerate(merged):
            t = record["t"]
            where = {"seq": seq, "source": source, "source_index": index, "t": t, "event": dict(record)}
            if self.last_t is not None and t < self.last_t:
                raise _fail("time_order", "The timestamp moves backward.", {"previous_t": self.last_t}, **where)
            if t < self.begin:
                raise _fail("time_order", "The event precedes the timeline's begin.", {"begin": self.begin}, **where)
            if self.instant is None or t > self.instant:
                self.finish_instant()
                self.start_instant(t)
            self.last_t = t
            customer = source == "customer"
            if customer and record["customer_id"] is not None and not _whole(record["customer_id"]):
                raise _fail("trace_structure", "customer_id must be a whole number or None.", **where)
            if not customer and (not isinstance(record["employee_id"], str) or record["employee_id"] not in self.state):
                raise _fail("trace_structure", "The transition names an employee not in the timeline.", **where)
            slot = _CUSTOMER_SLOT[record["type"]] if customer else (
                _PAIR_SLOT if record["stage"] == SERVICE_START else _TRANSITION_SLOT)
            self.order(slot, source, record, where)
            queue_before = len(self.queue)
            extra: dict[str, Any] = {}
            if customer:
                extra = self.customer_event(record, where)
                if record["queue_len_after"] != len(self.queue):
                    raise _fail("queue_reconciliation", "The rebuilt line length differs from queue_len_after.",
                                {"rebuilt": len(self.queue)}, **where)
            else:
                self.transition(record, where)
            self.events.append({
                "seq": seq, "source": "customer_trace" if customer else "employee_transition", "source_index": index,
                "t": t, "period": _period(t, self.closing),
                "type": record["type"] if customer else record["event"],
                "stage": None if customer else record["stage"],
                "customer_id": record["customer_id"] if customer else None,
                "employee_id": record["employee_id"],
                "register_id": record["register_id"] if customer else None,
                "employee_state_before": None if customer else record["from_state"],
                "employee_state_after": None if customer else record["to_state"],
                "register_before": None if customer else record["register_before"],
                "register_after": None if customer else record["register_after"],
                "queue_len_before": queue_before, "queue_len_after": len(self.queue),
                **{f"{name}_after": value for name, value in self.counts().items()},
                "unserved_reason": extra.get("unserved_reason"),
                "closing_policy": extra.get("closing_policy"),
                "drain_crew": extra.get("drain_crew"),
                "break": None,
            })
        self.finish_instant()
        where = {"t": self.last_t}
        if not self.closed:
            raise _fail("closing_rules", "The trace has no closing event.", **where)
        # The closing-instant checks leave every employee OFF, SERVING_SHIFT_ENDED, or a serving crew member, and a
        # serving employee always has an unresolved customer, so resolving every customer also means every employee
        # ends OFF (reconciled with the engine's intervals afterwards).
        unresolved = [c for c, row in self.customers.items() if row["status"] is None]
        if self.queue or unresolved:
            raise _fail("end_state", "The run ends with a customer waiting or in service.",
                        {"queue": list(self.queue), "unresolved": unresolved}, **where)


def _merge(result: dict[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    """The engine's recording order: customer event k follows the first employee_transitions_before transitions."""
    if result["trace_truncated"]:
        raise _fail("trace_complete", "The trace is truncated; a playback needs every event.")
    trace, transitions = result["trace"], result["employee_timeline"]["transitions"]
    for source, records, names in (("customer", trace, _TRACE_FIELDS), ("employee", transitions, _TRANSITION_FIELDS)):
        for index, record in enumerate(records):
            missing = [name for name in names if name not in record]
            if missing or not _time(record["t"]):
                raise _fail("trace_structure", "A record lacks the engine's fields or a finite time.",
                            {"missing": missing}, source=source, source_index=index, event=dict(record))
            # Every vocabulary value is a string. Testing that first means a malformed (for example unhashable)
            # value fails the check instead of raising; nothing is converted.
            if source == "customer" and (not isinstance(record["type"], str) or record["type"] not in CUSTOMER_EVENT_TYPES):
                raise _fail("event_vocabulary", f"Unknown customer event type {record['type']!r}.",
                            source=source, source_index=index, event=dict(record))
            if source == "employee":
                key = (record["stage"], record["event"], record["from_state"], record["to_state"])
                known = isinstance(record["event"], str) and record["event"] in _KNOWN_EVENTS
                if not known or not all(isinstance(value, str) for value in key) or key not in EMPLOYEE_TRANSITIONS:
                    raise _fail("employee_transition_legal" if known else "event_vocabulary",
                                f"Transition {key} is not in the named-engine vocabulary.",
                                source=source, source_index=index, event=dict(record))
    merged: list[tuple[str, int, dict[str, Any]]] = []
    position = 0
    for index, event in enumerate(trace):
        count = event["employee_transitions_before"]
        if not _whole(count) or not position <= count <= len(transitions):
            raise _fail("trace_structure", "employee_transitions_before does not place the event in the transition "
                        "record.", {"placed_after": position}, source="customer", source_index=index, event=dict(event))
        merged += [("employee", j, transitions[j]) for j in range(position, count)]
        position = count
        merged.append(("customer", index, event))
    merged += [("employee", j, transitions[j]) for j in range(position, len(transitions))]
    return merged


# ── Reconciliation with the regenerated result ──────────────────────────────


def _merged_intervals(rows: Sequence[Sequence[Any]]) -> list[tuple[float, float, str, int | None]]:
    merged: list[tuple[float, float, str, int | None]] = []
    for start, end, state, register in rows:
        if merged and merged[-1][2:] == (state, register) and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end, state, register)
        else:
            merged.append((start, end, state, register))
    return merged


def _hours_in(intervals: dict[str, list[tuple[float, float, str, int | None]]], states: frozenset[str],
              start: float, end: float) -> float:
    return math.fsum(min(end, high) - max(start, low) for rows in intervals.values() for low, high, state, _ in rows
                     if state in states and low < end and high > start)


def _reconcile(replay: _Replay, result: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Compare the rebuilt quantities with the engine's result. Returns the rebuilt tables and the method list."""
    methods: list[dict[str, str]] = []

    def exact(check: str, quantity: str, rebuilt: Any, engine: Any) -> None:
        if rebuilt != engine:
            raise _fail(check, f"{quantity}: the rebuilt value differs from the engine's.",
                        {"rebuilt": rebuilt, "engine": engine})
        methods.append({"quantity": quantity, "method": "exact"})

    def near(check: str, quantity: str, rebuilt: float, engine: float) -> None:
        if not _close_enough(float(rebuilt), float(engine)):
            raise _fail(check, f"{quantity}: the rebuilt value differs from the engine's beyond the tolerance.",
                        {"rebuilt": rebuilt, "engine": engine, "tolerance": TOLERANCE})
        methods.append({"quantity": quantity, "method": "tolerance"})

    closing, finish = replay.closing, replay.last_t
    assert finish is not None  # a valid replay has at least the closing event
    # Every rebuilt customer was served or left unserved, and each of those events checked that the engine has that
    # customer's row (engine_row); an engine with extra rows fails the customer comparison below.
    customers = []
    for customer_id in sorted(replay.customers):
        row = replay.customers[customer_id]
        engine = result["customers"][customer_id - 1]
        start = row["service_start_hours"]
        customers.append({
            **row, "wait_hours": None if start is None else start - row["arrival_hours"],
            "elapsed_wait_at_close_hours": closing - row["arrival_hours"] if row["status"] == UNSERVED_AT_CLOSE else None,
            "unserved_reason": engine["unserved_reason"],
        })
    fields = ("customer_id", "arrival_hours", "service_start_hours", "service_end_hours", "employee_id", "register_id",
              "status", "wait_hours", "elapsed_wait_at_close_hours")
    exact("customer_reconciliation", "customers (every field but unit_work and arrival_segment_id)",
          [{key: row[key] for key in fields} for row in customers],
          [{key: row[key] for key in fields} for row in result["customers"]])
    served = [row for row in customers if row["status"] == DEPARTED]
    missed = [row for row in customers if row["status"] == UNSERVED_AT_CLOSE]
    reasons = [row["unserved_reason"] for row in missed]
    exact("customer_reconciliation", "counts", {
        "arrivals": len(customers), "departed": len(served), "unserved_at_close": len(missed),
        "unserved_by_reason": {reason: reasons.count(reason) for reason in (HARD_CUTOFF_REASON, NO_ELIGIBLE_EMPLOYEE)},
        "served_after_closing": sum(1 for row in served if row["service_start_hours"] >= closing),
    }, result["counts"])
    waits = [row["wait_hours"] for row in served]
    exact("customer_reconciliation", "mean_wait_hours", math.fsum(waits) / len(waits) if waits else None,
          result["mean_wait_hours"])
    exact("customer_reconciliation", "queue.max_length_in_horizon", replay.max_queue_in_horizon,
          result["queue"]["max_length_in_horizon"])
    area = {"in_horizon": 0.0, "after_closing": 0.0}
    for here, following in zip(replay.instants, replay.instants[1:]):
        area["after_closing" if here["t"] >= closing else "in_horizon"] += here["queue_len"] * (following["t"] - here["t"])
    near("customer_reconciliation", "queue.customer_hours_in_horizon", area["in_horizon"],
         result["queue"]["customer_hours_in_horizon"])
    near("customer_reconciliation", "queue.customer_hours_after_closing", area["after_closing"],
         result["queue"]["customer_hours_after_closing"])
    exact("customer_reconciliation", "at_close (waiting and in-service customers)",
          {key: replay.at_close[key] for key in ("waiting_customer_ids", "in_service_customer_ids")},
          {key: result["at_close"][key] for key in ("waiting_customer_ids", "in_service_customer_ids")})
    exact("drain_frozen_crew", "at_close.drain_crew", replay.at_close["drain_crew"], result["at_close"]["drain_crew"])

    timeline = result["employee_timeline"]
    exact("employee_reconciliation", "finish", finish, result["finish"])
    exact("employee_reconciliation", "begin", replay.begin, timeline["begin"])
    intervals: dict[str, list[tuple[float, float, str, int | None]]] = {}
    for employee_id in replay.ids:
        rows = replay.intervals[employee_id] + ([[replay.since[employee_id], finish, replay.state[employee_id],
                                                  replay.register[employee_id]]] if finish > replay.since[employee_id] else [])
        intervals[employee_id] = _merged_intervals(rows)
    engine_intervals = {employee_id: _merged_intervals([
        (row["start"], row["end"], row["state"], row["register_id"]) for row in timeline["intervals"]
        if row["employee_id"] == employee_id]) for employee_id in replay.ids}
    exact("employee_reconciliation", "employee state and register intervals", intervals, engine_intervals)
    for employee_id in replay.ids:
        for state, hours in timeline["state_totals"][employee_id].items():
            total = math.fsum(end - start for start, end, own, _ in intervals[employee_id] if own == state)
            if not _close_enough(total, hours):
                raise _fail("employee_reconciliation", "state_totals: a rebuilt total differs beyond the tolerance.",
                            {"employee_id": employee_id, "state": state, "rebuilt": total, "engine": hours})
    methods.append({"quantity": "state_totals", "method": "tolerance"})
    shifts = [dict(row) for employee_id in replay.ids for row in replay.shifts[employee_id]]
    exact("employee_reconciliation", "activated shifts (actual start, release)",
          [(row["employee_id"], row["activation"], row["release"]) for row in shifts],
          [(row["employee_id"], row["actual_start"], row["release"]) for employee_id in replay.ids
           for row in sorted((item for item in timeline["shifts"] if item["employee_id"] == employee_id
                              and item["activated"]), key=lambda item: item["actual_start"])])
    # A started break is keyed below by (employee_id, actual_start), so a malformed key fails here instead of raising.
    malformed = [dict(row) for row in timeline["breaks"] if row["actual_start"] is not None
                 and (not isinstance(row["employee_id"], str) or not _time(row["actual_start"]))]
    if malformed:
        raise _fail("employee_reconciliation", "A started engine break has a non-string employee_id or a non-numeric "
                    "actual_start.", {"breaks": malformed})
    breaks = [dict(row) for employee_id in replay.ids for row in replay.breaks[employee_id]]
    exact("employee_reconciliation", "started breaks (actual start, actual end, outcome)",
          [(row["employee_id"], row["actual_start"], row["actual_end"], row["outcome"]) for row in breaks],
          [(row["employee_id"], row["actual_start"], row["actual_end"], row["outcome"]) for employee_id in replay.ids
           for row in sorted((item for item in timeline["breaks"] if item["employee_id"] == employee_id
                              and item["actual_start"] is not None), key=lambda item: item["actual_start"])])
    engine_breaks = {(row["employee_id"], row["actual_start"]): row for row in timeline["breaks"]
                     if row["actual_start"] is not None}
    for row in breaks:
        engine = engine_breaks[(row["employee_id"], row["actual_start"])]
        row.update({key: engine[key] for key in ("name", "shift_index", "scheduled_start", "due", "delay")})

    times = [row["t"] for row in replay.instants]
    for step in result["staffing"]["timeline"]:
        position = bisect.bisect_right(times, step["start"]) - 1
        rebuilt_counts = dict.fromkeys(_STATE_SERIES, 0) if position < 0 else {
            name: replay.instants[position][name] for name in _STATE_SERIES}
        engine_counts = {name: step[name] for name in _STATE_SERIES}
        if rebuilt_counts != engine_counts:
            raise _fail("employee_reconciliation", "A staffing step's employee-state series differ from the replay.",
                        {"step": dict(step), "rebuilt": rebuilt_counts})
    methods.append({"quantity": "staffing.timeline (accepting, busy, occupancy, waiting for a register)",
                    "method": "exact"})
    for window in result["staffing"]["windows"]:
        for key, series in _WINDOW_SERIES.items():
            rebuilt_hours = _hours_in(intervals, _STATE_SERIES[series], window["start"], window["end"])
            if not _close_enough(rebuilt_hours, window[key]):
                raise _fail("employee_reconciliation", f"staffing window {window['window']}: {key} differs.",
                            {"rebuilt": rebuilt_hours, "engine": window[key]})
    methods.append({"quantity": "staffing.windows (the four employee-state series)", "method": "tolerance"})
    methods += [
        {"quantity": "staffing scheduled_active, required_staffing, and both gaps", "method": "not_applicable",
         "reason": "roster and required-staffing inputs, not trace events"},
        {"quantity": "unit_work and arrival_segment_id", "method": "not_applicable",
         "reason": "inputs, not trace events; unit_work is used only for the service-duration check"},
        {"quantity": "at_close.closing_inputs", "method": "not_applicable",
         "reason": "an input that changes no state has no transition"},
        {"quantity": "unfulfilled breaks and shifts not activated", "method": "not_applicable",
         "reason": "no event represents them; reported from the engine's record"},
    ]
    tables = {"customers": customers, "intervals": intervals, "shifts": shifts, "breaks": breaks,
              "queue_customer_hours": area}
    return tables, methods


def _row_reconciliation(replay: _Replay, rebuilt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    """The row fields the result reconciliation does not already fix.

    The row is ``named_replication_row(result)``, a function of the result. Its customer, waiting,
    closing, shift, and break fields read quantities ``_reconcile`` has already compared with the
    replay (counts, customer rows, the queue integrals and maximum, ``at_close``, the finish, the
    shifts, the breaks, and the state totals). The one input it does not compare is each interval's
    ``after_closing`` flag, which the row's after-closing employee-hours use; those are recomputed
    here from the rebuilt intervals.
    """
    methods: list[dict[str, str]] = []
    key = "employee_hours_after_closing_by_state"
    for state, stored in row["employees"][key].items():
        value = _hours_in(rebuilt["intervals"], frozenset({state}), replay.closing, math.inf)
        if not _close_enough(value, stored):
            raise _fail("employee_reconciliation", f"row employees.{key}[{state}] differs beyond the tolerance.",
                        {"rebuilt": value, "row": stored})
    methods.append({"quantity": f"row.employees.{key}", "method": "tolerance"})
    methods.append({"quantity": "every other trace-represented row field", "method": "via_result_reconciliation",
                    "reason": "a function of the result, whose inputs to the row are reconciled above"})
    methods.append({"quantity": "row.staffing scheduled and required hours and gaps, overruns, activation and break "
                    "delays, unfulfilled causes, shifts not activated", "method": "not_applicable",
                    "reason": "need roster or requirement inputs, or have no event; covered only by the exact "
                    "equality of the regenerated and stored rows"})
    return methods


def _replay(
    result: dict[str, Any],
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
) -> tuple[_Replay, dict[str, Any], list[dict[str, str]]]:
    """The replay, the rebuilt tables, and the reconciliation methods; raises ``_Violation`` on a failed check."""
    _check_closing_policy(result["closing_policy"])
    replay = _Replay(result, horizon, demand_periods)
    replay.run(_merge(result))
    rebuilt, methods = _reconcile(replay, result)
    by_start = {(row["employee_id"], row["actual_start"]): row for row in rebuilt["breaks"]}
    current: dict[str, float] = {}
    for event in replay.events:
        if event["employee_state_after"] == ON_BREAK:
            current[event["employee_id"]] = event["t"]
        if event["employee_state_after"] == ON_BREAK or event["employee_state_before"] == ON_BREAK:
            row = by_start[(event["employee_id"], current[event["employee_id"]])]
            event["break"] = {key: row[key] for key in ("name", "scheduled_start", "due", "delay", "outcome")}
    return replay, rebuilt, methods


def replay_named_trace(
    result: dict[str, Any],
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
) -> dict[str, Any]:
    """Replay and validate one named-DES result from its trace and transitions alone.

    Returns ``{"valid": True, ...}`` with the playback events, the end-of-instant states, and the rebuilt
    tables, or ``{"valid": False, "failure": {...}}`` with the failed check, the event, and the
    evidence. Nothing is repaired, and no random number is drawn. ``horizon`` and ``demand_periods``
    give the service rate for the service-duration check only.
    """
    try:
        replay, rebuilt, methods = _replay(result, horizon, demand_periods)
    except _Violation as violation:
        return {"valid": False, "failure": violation.failure}
    return {
        "valid": True,
        "events": replay.events,
        "instants": replay.instants,
        "customers": rebuilt["customers"],
        "employees": {employee_id: [{"start": start, "end": end, "state": state, "register_id": register}
                                    for start, end, state, register in rows]
                      for employee_id, rows in rebuilt["intervals"].items()},
        "shifts": rebuilt["shifts"],
        "breaks": rebuilt["breaks"],
        "closing": {"policy": result["closing_policy"], "closing_hours": replay.closing, **replay.at_close},
        "outside_horizon": _outside_horizon(rebuilt["intervals"], replay.closing),
        "reconciliation": methods,
    }


# ── Playback ────────────────────────────────────────────────────────────────


def _outside_horizon(intervals: dict[str, list[tuple[float, float, str, int | None]]], closing: float) -> dict[str, Any]:
    return {
        "definition": ("Employee-hours by base state before opening and from closing on, rebuilt from the events. No "
                       "requirement or gap is calculated outside the operating horizon."),
        "before_opening_hours_by_state": {state: _hours_in(intervals, frozenset({state}), -math.inf, 0.0)
                                          for state in BASE_STATES},
        "after_closing_hours_by_state": {state: _hours_in(intervals, frozenset({state}), closing, math.inf)
                                         for state in BASE_STATES},
    }


def build_named_playback(
    result: dict[str, Any],
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    *,
    replication_index: int,
    root_entropy: int,
) -> dict[str, Any]:
    """A checked playback of one full-trace named replication result; raises ``NamedPlaybackError`` on any failure."""
    row = named_replication_row(result, replication_index)
    try:
        replay, rebuilt, methods = _replay(result, horizon, demand_periods)
        methods = methods + _row_reconciliation(replay, rebuilt, row)
    except _Violation as violation:
        raise NamedPlaybackError(violation.failure) from None
    timeline = result["employee_timeline"]
    identity = result["replication"]
    return {
        "replication": {
            "replication_index": replication_index,
            "root_entropy": root_entropy,
            "spawn_key": list(identity["spawn_key"]),
            "pool_size": identity["pool_size"],
            "customer_inputs_sha256": identity["customer_inputs"]["sha256"],
            "closing_policy": result["closing_policy"],
        },
        "events": replay.events,
        "instants": replay.instants,
        "customers": rebuilt["customers"],
        "employees": {employee_id: [{"start": start, "end": end, "state": state, "register_id": register}
                                    for start, end, state, register in rows]
                      for employee_id, rows in rebuilt["intervals"].items()},
        "shifts": rebuilt["shifts"],
        "breaks": rebuilt["breaks"],
        "not_represented_by_events": {
            "definition": "Engine records with no event; reported from the engine's employee timeline, not rebuilt.",
            "unfulfilled_breaks": [dict(item) for item in timeline["breaks"] if item["outcome"] == UNFULFILLED],
            "shifts_not_activated": [dict(item) for item in timeline["shifts"] if not item["activated"]],
        },
        "closing": {"policy": result["closing_policy"], "closing_hours": replay.closing, **replay.at_close},
        "outside_horizon": _outside_horizon(rebuilt["intervals"], replay.closing),
        "summary": row,
        "validation": {"valid": True, "checks": dict(CHECKS)},
        "reconciliation": methods,
        "event_vocabulary": {
            "customer_trace": dict(CUSTOMER_EVENT_TYPES),
            "employee_transitions": [{"stage": stage, "event": event, "from_state": before, "to_state": after,
                                      "meaning": meaning}
                                     for (stage, event, before, after), meaning in EMPLOYEE_TRANSITIONS.items()],
            "rejected_state_machine_transitions": [
                {"stage": stage, "event": event, "from_state": before, "to_state": after, "reason": reason}
                for (stage, event, before, after), reason in NOT_PRODUCED_BY_THE_NAMED_ENGINE.items()],
        },
        "unsupported": dict(UNSUPPORTED),
        "provenance": {
            "playback_version": PLAYBACK_VERSION,
            "named_engine_version": result["provenance"]["engine_version"],
            "state_machine_version": result["provenance"]["state_machine_version"],
            "runtime": dict(identity["runtime"]),
            "source": (
                "One replication regenerated through shared_named_replications.simulate_named_replication with "
                "replication_seed_sequence(root_entropy, replication_index) and a full trace. Events are the engine's "
                "customer trace and employee transitions, interleaved by each customer event's "
                "employee_transitions_before; per-event counts come from an independent replay of those events. "
                "Nothing is synthesized, and no event from another replication is included."),
            "time_unit": "hours from the horizon start",
            "randomness": "The replay draws no random numbers; only the regeneration draws, through the 5B-4.4 path.",
            "tolerance": dict(TOLERANCE, applies_to="float sums (integrals and totals) only; times compare exactly"),
            "per_event_counts": ("After the event, in the engine's recording order; events at one timestamp are "
                                 "simultaneous, and instants holds the state at the end of each instant."),
        },
    }


def prepare_named_playback(
    horizon: OperatingHorizon,
    demand_periods: Sequence[DemandPeriod],
    employees: Sequence[Employee],
    rules: WorkforceRules,
    roster: Sequence[ScheduledShift],
    *,
    root_entropy: int,
    replication_index: int,
    closing_policy: str,
    employee_policy: EmployeeDesPolicy,
    required_staffing: Sequence[StaffingSegment],
) -> dict[str, Any]:
    """Regenerate replication ``replication_index`` of the run with ``root_entropy`` and prepare its playback."""
    result = simulate_named_replication(
        horizon, demand_periods, employees, rules, roster,
        seed_sequence=replication_seed_sequence(root_entropy, replication_index), closing_policy=closing_policy,
        employee_policy=employee_policy, required_staffing=required_staffing, max_trace_events=None,
    )
    playback = build_named_playback(result, horizon, demand_periods, replication_index=replication_index,
                                    root_entropy=root_entropy)
    inputs = named_inputs_snapshot(horizon, demand_periods, employees, rules, roster, required_staffing)
    playback["provenance"]["inputs_sha256"] = named_inputs_digest(inputs, closing_policy, asdict(employee_policy))
    return playback


# ── Regeneration from a run's recorded provenance ───────────────────────────


def rebuild_named_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the input dataclasses from ``provenance.inputs`` (``named_inputs_snapshot``)."""
    rules = inputs["rules"]
    return {
        "horizon": OperatingHorizon(**inputs["horizon"]),
        "demand_periods": [DemandPeriod(**item) for item in inputs["demand_periods"]],
        "required_staffing": [StaffingSegment(**item) for item in inputs["required_staffing"]],
        "employees": [Employee(employee_id=item["employee_id"],
                               availability=tuple(AvailabilityWindow(**window) for window in item["availability"]),
                               pay=EmployeePay(**item["pay"])) for item in inputs["employees"]],
        "rules": WorkforceRules(
            shift_rules=ShiftRules(**rules["shift_rules"]),
            break_rules=tuple(BreakRule(min_shift_minutes=rule["min_shift_minutes"],
                                        max_shift_minutes=rule["max_shift_minutes"],
                                        min_gap_minutes=rule["min_gap_minutes"],
                                        breaks=tuple(BreakRequirement(**item) for item in rule["breaks"]))
                              for rule in rules["break_rules"]),
            register_count=rules["register_count"]),
        "roster": [ScheduledShift(employee_id=item["employee_id"], start_minute=item["start_minute"],
                                  end_minute=item["end_minute"],
                                  breaks=tuple(ScheduledBreak(**placed) for placed in item["breaks"]))
                   for item in inputs["roster"]],
    }


def playback_from_named_replications(replication_result: dict[str, Any], replication_index: int) -> dict[str, Any]:
    """Playback of one replication of a ``run_named_replications`` result, checked against its recorded inputs and row.

    Raises ``NamedPlaybackError`` (check ``regeneration_identity``, ``closing_policy``, or ``stored_row``) when the
    run cannot be regenerated exactly by this code, and for any failed replay check.
    """
    provenance = replication_result["provenance"]

    def refuse(message: str, evidence: dict[str, Any] | None = None, check: str = "regeneration_identity") -> NoReturn:
        raise NamedPlaybackError({"check": check, "message": message, "evidence": evidence or {}})

    for key, current in (("method_version", METHOD_VERSION), ("named_engine_version", NAMED_ENGINE_VERSION),
                         ("state_machine_version", STATE_MACHINE_VERSION), ("arrival_engine_version", ENGINE_VERSION),
                         ("seed_scheme", SEED_SCHEME)):
        if provenance.get(key) != current:
            refuse(f"The run's {key} is not this code's; it cannot be regenerated exactly.",
                   {"recorded": provenance.get(key), "current": current})
    if not _whole(replication_index) or not 0 <= replication_index < provenance["replications"]:
        raise SharedSegmentError([f"replication_index must be from 0 to {provenance['replications'] - 1}."])
    stored = replication_result["replications"][replication_index]
    if (stored["replication_index"], stored["spawn_key"]) != (replication_index, [replication_index]):
        refuse("The stored row does not carry this replication's index and spawn key.",
               {"replication_index": stored["replication_index"], "spawn_key": stored["spawn_key"]})
    recorded = provenance.get("inputs_sha256")
    try:
        digest = named_inputs_digest(provenance["inputs"], provenance["closing_policy"], provenance["employee_policy"])
    except (KeyError, SharedSegmentError) as error:
        refuse("The recorded inputs cannot be digested.", {"error": str(error)})
    if recorded is None or digest != recorded:
        refuse("The recorded inputs do not match the recorded inputs_sha256.", {"recorded": recorded, "computed": digest})
    try:
        inputs = rebuild_named_inputs(provenance["inputs"])
        policy = EmployeeDesPolicy(**provenance["employee_policy"])
    except (KeyError, TypeError) as error:  # a field missing from, or unknown to, the input dataclasses
        refuse("The recorded inputs cannot be rebuilt into the input dataclasses.", {"error": str(error)})
    rebuilt_digest = named_inputs_digest(
        named_inputs_snapshot(inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"],
                              inputs["roster"], inputs["required_staffing"]),
        provenance["closing_policy"], asdict(policy))
    if rebuilt_digest != recorded:
        refuse("The rebuilt inputs do not reproduce the recorded inputs_sha256.",
               {"recorded": recorded, "rebuilt": rebuilt_digest})
    # The same closing-policy check as the replay, before regeneration (the digest records a value, not its approval).
    try:
        _check_closing_policy(provenance["closing_policy"])
    except _Violation as violation:
        raise NamedPlaybackError(violation.failure) from None
    playback = prepare_named_playback(
        inputs["horizon"], inputs["demand_periods"], inputs["employees"], inputs["rules"], inputs["roster"],
        root_entropy=provenance["root_entropy"], replication_index=replication_index,
        closing_policy=provenance["closing_policy"], employee_policy=policy, required_staffing=inputs["required_staffing"],
    )
    regenerated = playback["summary"]
    differing = sorted(key for key in set(regenerated) | set(stored) if regenerated.get(key) != stored.get(key))
    if differing:
        refuse(f"Regenerated replication {replication_index} differs from the stored row.", {"fields": differing},
               check="stored_row")
    runtime_matches = playback["provenance"]["runtime"] == provenance["runtime"]
    playback["reconciliation"].append({"quantity": "stored replication row", "method": "exact"})
    playback["provenance"].update({
        "recorded_inputs_sha256": recorded,
        "runtime_recorded": dict(provenance["runtime"]),
        "runtime_matches_recorded": runtime_matches,
        "regeneration_basis": (
            "Same method, engine, state-machine, and arrival versions and seed scheme; the recorded inputs match "
            "their digest and the rebuilt inputs reproduce it; the regenerated row equals the stored row exactly."
            + ("" if runtime_matches else " The runtime differs from the recorded one: the equality above was "
               "established by comparison for this replication only, not by a cross-version reproducibility claim.")),
    })
    return playback
