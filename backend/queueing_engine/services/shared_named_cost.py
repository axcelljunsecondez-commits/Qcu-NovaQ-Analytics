"""Named workforce cost of one named-employee shared-queue DES run (Phase 5B-5 of the shared-queue enhancement).

The cost of one run (C12) is the named employees' wages for simulated paid time, the realized waiting, and, where the
unserved term applies, the customers left unserved at closing:

    total_cost = sum over employees of (regular_paid_hours × regular_rate_per_hour
                                        + overtime_paid_hours × overtime_rate_per_hour)
               + queue.customer_hours_total × waiting_rate
               + counts.unserved_at_close × unserved_customer_rate      (only when the unserved term applies)

Named wages replace the Phase 3A capacity labor terms; both are never charged (C2). The module first runs the 5B-4.6
attribution, whose failures propagate unchanged, and reads every operational quantity from it. It then walks the same
validated employee intervals in time order only for what attribution totals cannot give: which paid time is regular and
which is overtime when the daily threshold is crossed partway through an interval (C16).

It is a pure read: it runs no simulation, draws no random numbers, and changes no input. Rates come from the caller,
with no defaults; a missing rate is never read as 0. Hours are hours from the horizon start. A failed check raises
``NamedCostError`` with the check, a message, and the evidence; nothing is repaired. Times compare exactly; the house
tolerance (``shared_named_playback.TOLERANCE``) is used only for reconciliation checks and the D7 rule. No output states
what any law requires, and nothing here is a PASS/FAIL verdict (C11).

Spec: docs/superpowers/specs/2026-09-30-shared-queue-named-workforce-cost.md.
Nothing legacy imports this module. No API, database, or frontend uses it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from numbers import Integral, Real
from typing import Any

from backend.queueing_engine.services.shared_day_cost import COSTED, NOT_APPLICABLE, RATE_MISSING
from backend.queueing_engine.services.shared_workforce import Employee, EmployeePay
from backend.queueing_engine.simulation.shared_continuous_des import HARD_CUTOFF
from backend.queueing_engine.simulation.shared_employee_states import (
    AVAILABLE,
    ON_BREAK,
    SERVING,
    SERVING_BREAK_DUE,
    SERVING_SHIFT_ENDED,
    WAITING_FOR_REGISTER,
)
from backend.queueing_engine.simulation.shared_named_attribution import (
    NamedAttributionError,
    build_named_attribution,
    derived_duration,
)
from backend.queueing_engine.simulation.shared_named_des import (
    DEPARTED,
    HARD_CUTOFF_REASON,
    NO_ELIGIBLE_EMPLOYEE,
    UNSERVED_AT_CLOSE,
)
from backend.queueing_engine.simulation.shared_named_playback import TOLERANCE

NAMED_COST_VERSION = "novaq-shared-named-cost-v1"

ZERO_QUANTITY, HOURS_UNDETERMINED = "ZERO_QUANTITY", "HOURS_UNDETERMINED"
DETERMINED = "DETERMINED"
# C3: paid whatever the break flag. OFF is unpaid (C4); ON_BREAK is paid only when its break's paid flag is True.
PAID_STATES = (WAITING_FOR_REGISTER, AVAILABLE, SERVING, SERVING_BREAK_DUE, SERVING_SHIFT_ENDED)
UNSERVED_REASONS = (HARD_CUTOFF_REASON, NO_ELIGIBLE_EMPLOYEE)
_LABOR = (
    # (component, quantity field, rate field)
    ("regular_labor", "regular_paid_hours", "regular_rate_per_hour"),
    ("overtime_labor", "overtime_paid_hours", "overtime_rate_per_hour"),
)
_QUEUE_FIELDS = ("customer_hours_in_horizon", "customer_hours_after_closing", "customer_hours_total")
_CUSTOMER_FIELDS = ("customer_id", "status", "unserved_reason")

CHECKS = {
    "rate_structure": (
        "rates is a NamedCostRates; each rate is a finite real number, 0 or more (not bool), or None when not "
        "supplied."),
    "pay_structure": (
        "Each input employee's pay is an EmployeePay that passes the 5B-1 value rules: each rate a finite real, 0 or "
        "more, or None; daily_regular_paid_minutes a whole number, 0 or more, or None, whose hours are a finite float."),
    "result_structure": (
        "Beyond what attribution checks, the result has counts (with unserved_at_close and unserved_by_reason), "
        "customers (customer_id, status departed or unserved_at_close, unserved_reason), queue (the three "
        "customer-hour integrals as real numbers), at_close as a mapping, and a bool paid flag on every break."),
    "break_mapping": (
        "Each ON_BREAK interval lies inside exactly one started break of the same employee and shift (exact "
        "comparisons), and the intervals mapped to each started break tile [actual_start, actual_end) exactly."),
    "paid_partition": (
        "Per activated shift and per employee: paid_hours + unpaid_break_hours equals attribution on_duty_hours, and "
        "paid_break_hours + unpaid_break_hours equals attribution ON_BREAK hours, within tolerance."),
    "overtime_partition": (
        "Per activated shift and per employee: the G, T, and F sums are 0 or more; when determined, regular + "
        "overtime equals paid_hours within tolerance and regular stays at or below the threshold; F plus unpaid "
        "ON_BREAK time in flagged intervals equals attribution after_closing_or_past_scheduled_end_hours within "
        "tolerance."),
    "unserved_consistency": (
        "at_close carries waiting_customer_ids and drain_crew as lists; unserved_by_reason has exactly hard_cutoff and "
        "no_eligible_employee, whole and 0 or more, summing to unserved_at_close; the unserved customer rows match the "
        "count and the reasons, and no departed row has a reason. HARD_CUTOFF: no no_eligible_employee, and the "
        "unserved ids are the waiting ids. DRAIN: no hard_cutoff; with an empty crew the unserved ids are the waiting "
        "ids, all no_eligible_employee; with a crew nobody is unserved. All comparisons are exact."),
    "waiting_consistency": (
        "The three queue customer-hour integrals are finite and 0 or more, and customer_hours_total equals "
        "customer_hours_in_horizon + customer_hours_after_closing within tolerance."),
    "finite_nonnegative": (
        "The D7 rule (C15) passes for R_k and for the T piece of a crossing, and every output hour and cost is a finite "
        "number, 0 or more, or None where the spec allows None."),
    "cost_arithmetic": (
        "Each component's status and cost follow the section 9 rules, and the totals are fsums of the COSTED and "
        "ZERO_QUANTITY costs, with None propagating."),
}

DEFINITIONS = {
    "time_unit": "Hours from the horizon start, as in the named engine. Costs are in the caller's currency.",
    "paid_time": (
        "C3: WAITING_FOR_REGISTER, AVAILABLE, SERVING, SERVING_BREAK_DUE, and SERVING_SHIFT_ENDED are paid; OFF is "
        "unpaid; ON_BREAK is paid if and only if the engine break record it maps to has paid True. C4: time before "
        "actual activation and rest between split shifts are OFF, so unpaid. Only simulated time is costed."),
    "breaks": (
        "C7: no penalty or bonus for a delayed, shortened, truncated, or unfulfilled break. A paid break is paid for "
        "its actual time, an unpaid break is unpaid for its actual time, and time worked instead is paid normally."),
    "overtime": (
        "C5: a paid instant is overtime when it is past its shift's scheduled end, or after closing, or the employee's "
        "cumulative actual paid time has reached the daily threshold. At most one premium applies to an instant. C6: "
        "regular = paid - overtime, summed directly from the regular pieces."),
    "pieces": (
        "Each paid interval is split into disjoint pieces: F (past its shift's scheduled end or after closing), T "
        "(neither, and after the daily threshold is reached), and G (regular). regular = sum G; overtime = fsum(sum F, "
        "sum T)."),
    "threshold_walk": (
        "Per employee, the paid intervals in time order across split shifts. C_k is the fsum of every earlier paid "
        "length, flagged or not. The threshold is exhausted at the first interval with C_k >= theta_h, or inside "
        "interval k when R_k = theta_h - C_k (D7) is at most its length. Every comparison is exact."),
    "threshold_required": (
        "C14: the daily threshold is required if and only if some paid interval is neither past its shift's scheduled "
        "end nor after closing. A required threshold that is missing leaves regular and overtime undetermined "
        "(HOURS_UNDETERMINED); it is never inferred."),
    "threshold_reached_at_hours": (
        "The derived instant at which cumulative paid time reaches the threshold: the start of the first paid interval "
        "when theta is 0, the end of an interval when the threshold is reached exactly there, or start + R_k inside an "
        "interval. It is not an event and takes part in no ordering or classification."),
    "derived_durations": (
        "C15: R_k and the T piece of a crossing go through the 5B-4.6 D7 rule (derived_duration) with the house "
        "tolerance; no other tolerance exists, and raw times stay exact."),
    "waiting": "C9: the realized queue.customer_hours_total of the named result, never an analytical estimate.",
    "unserved": (
        "X6 named (C10b): under HARD_CUTOFF the unserved term applies, as in Phase 3A. Under DRAIN it applies if and "
        "only if the realized counts.unserved_at_close is above 0. Eligibility is never recomputed; the engine's "
        "closing record is only reconciled."),
    "rate_required": (
        "C13: for a determined quantity Q, Q == 0 (exact) needs no rate and costs 0.0 (ZERO_QUANTITY); Q > 0 needs "
        "its rate (RATE_MISSING when absent, else COSTED at Q × rate). An undetermined quantity is never zero."),
    "statuses": (
        "COSTED: Q × rate. ZERO_QUANTITY: an established zero quantity, cost 0.0. RATE_MISSING: a required rate was "
        "not supplied, cost None. HOURS_UNDETERMINED: a required daily threshold was not supplied, so the labor "
        "quantity and cost are None. NOT_APPLICABLE: the unserved term is not part of this run's model, cost None. "
        "0.0 and None are never conflated."),
    "labor": (
        "C2: named employee wages replace the Phase 3A capacity labor terms; Phase 3A server-hours, the result's "
        "staffing integrals, and Phase 2 server cost are not charged, and 5B-1 scheduled pay is not mixed in."),
}

RECONCILIATION = [
    {"identity": "ON_BREAK interval inside exactly one started break; mapped intervals tile the break",
     "method": "exact"},
    {"identity": "paid_hours + unpaid_break_hours = attribution on_duty_hours (shift and employee)",
     "method": "tolerance"},
    {"identity": "paid_break_hours + unpaid_break_hours = attribution ON_BREAK hours (shift and employee)",
     "method": "tolerance"},
    {"identity": "regular_paid_hours + overtime_paid_hours = paid_hours (when determined)", "method": "tolerance"},
    {"identity": "regular_paid_hours <= daily threshold hours", "method": "exact or tolerance"},
    {"identity": "F + unpaid flagged ON_BREAK = attribution after_closing_or_past_scheduled_end_hours",
     "method": "tolerance"},
    {"identity": "customer_hours_total = customer_hours_in_horizon + customer_hours_after_closing",
     "method": "tolerance"},
    {"identity": "unserved counts, reasons, customer rows, waiting_customer_ids, and drain_crew agree",
     "method": "exact"},
    {"identity": "labor total = fsum of employee labor costs; total_cost = fsum of COSTED and ZERO_QUANTITY costs",
     "method": "exact"},
]

UNDETERMINED = [
    "D15 is UNKNOWN (an undefined repository reference labeled 'acceptance rule'); no verdict, threshold, or "
    "acceptance field is produced (C11).",
    "The contents of Phase 5A D6 and D8 are UNKNOWN; C5 is a new rule, not a restatement of them.",
    "A paid time above 0 that is entirely past its shift's scheduled end or after closing (the C14 'not required' "
    "branch with paid time) is INFERRED unreachable from the named engine: every activated shift starts before its "
    "scheduled end and before closing. The rule decides the branch either way.",
    "The D7 zero and failure branches inside the pay walk are INFERRED unreachable: both differences are taken only "
    "where an exact comparison already shows a positive true value. The rule decides them either way.",
    "Float event times can leave a very small G or T piece at a crossing; it is reported as computed, never snapped.",
    "Cross-replication cost aggregation is out of scope (C12).",
]


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NamedCostRates:
    """Caller rates in the caller's currency. Both fields are required; ``None`` means not supplied (never zero)."""

    waiting_rate: float | None  # per customer-hour waiting (queue.customer_hours_total)
    unserved_customer_rate: float | None  # per customer recorded as unserved_at_close, when the term applies


class NamedCostError(Exception):
    """A check failed, so no cost is produced. ``failure`` holds the check, message, and evidence."""

    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(f"{failure['check']}: {failure['message']}")
        self.failure = failure


class _Violation(Exception):
    def __init__(self, failure: dict[str, Any]) -> None:
        super().__init__(failure["message"])
        self.failure = failure


def _fail(check: str, message: str, evidence: dict[str, Any] | None = None) -> _Violation:
    return _Violation({"check": check, "message": message, "evidence": evidence or {}})


def _close_enough(a: float, b: float) -> bool:
    try:
        return math.isclose(a, b, rel_tol=TOLERANCE["rel"], abs_tol=TOLERANCE["abs"])
    except OverflowError:  # an exact value beyond the float range is not close to anything
        return False


def _finite(value: object) -> bool:
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:  # a whole number or fraction beyond the float range
        return False


def _whole(value: object) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _rate_ok(value: object) -> bool:
    return value is None or (_finite(value) and value >= 0)  # type: ignore[operator]


def _fsum(values: Iterable[float], field: str, evidence: dict[str, Any]) -> float:
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError):
        total = math.inf
    if not math.isfinite(total):
        raise _fail("finite_nonnegative", f"{field} is not a finite number.", {**evidence, "field": field})
    return total


# ── Input checks ────────────────────────────────────────────────────────────


def _check_rates(rates: object) -> NamedCostRates:
    if not isinstance(rates, NamedCostRates):
        raise _fail("rate_structure", "rates must be a NamedCostRates (use None for a rate not supplied).",
                    {"rates_type": type(rates).__name__})
    for field in ("waiting_rate", "unserved_customer_rate"):
        value = getattr(rates, field)
        if not _rate_ok(value):
            raise _fail("rate_structure", f"{field} must be a finite number, 0 or more, or None when not supplied.",
                        {"field": field, "value": value})
    return rates


def _check_pay(employees: Sequence[Employee]) -> dict[str, tuple[EmployeePay, float | None]]:
    """pay_structure: each employee's pay and its threshold in hours (None when not supplied)."""
    checked: dict[str, tuple[EmployeePay, float | None]] = {}
    for employee in employees:
        pay = employee.pay
        evidence = {"employee_id": employee.employee_id}
        if not isinstance(pay, EmployeePay):
            raise _fail("pay_structure", "An employee's pay must be an EmployeePay.",
                        {**evidence, "pay_type": type(pay).__name__})
        for field in ("regular_rate_per_hour", "overtime_rate_per_hour"):
            if not _rate_ok(getattr(pay, field)):
                raise _fail("pay_structure", f"{field} must be a finite number, 0 or more, or None.",
                            {**evidence, "field": field, "value": getattr(pay, field)})
        minutes = pay.daily_regular_paid_minutes
        theta: float | None = None
        if minutes is not None:
            if not _whole(minutes) or minutes < 0:
                raise _fail("pay_structure", "daily_regular_paid_minutes must be a whole number, 0 or more, or None.",
                            {**evidence, "value": minutes})
            try:
                theta = int(minutes) / 60
            except OverflowError:
                theta = math.inf
            if not math.isfinite(theta):
                raise _fail("pay_structure", "daily_regular_paid_minutes is beyond the float range in hours.",
                            {**evidence, "value": minutes})
        checked[employee.employee_id] = (pay, theta)
    return checked


def _check_result(result: dict[str, Any]) -> None:
    """result_structure: the fields read beyond attribution, with the engine's types."""
    counts, customers, queue = result.get("counts"), result.get("customers"), result.get("queue")
    if not isinstance(counts, dict) or "unserved_at_close" not in counts or not isinstance(
            counts.get("unserved_by_reason"), dict):
        raise _fail("result_structure", "counts must carry unserved_at_close and an unserved_by_reason mapping.",
                    {"counts": counts})
    if not isinstance(customers, (list, tuple)):
        raise _fail("result_structure", "customers must be a list of customer rows.", {})
    for index, row in enumerate(customers):
        if not isinstance(row, dict) or any(name not in row for name in _CUSTOMER_FIELDS) or not _whole(
                row["customer_id"]) or not isinstance(row["status"], str) or row["status"] not in (
                DEPARTED, UNSERVED_AT_CLOSE) or not (row["unserved_reason"] is None or isinstance(
                row["unserved_reason"], str)):
            raise _fail("result_structure", "A customer row lacks the engine's customer_id, status, or "
                        "unserved_reason, or holds a value of another type.",
                        {"index": index, "row": dict(row) if isinstance(row, dict) else row})
    if not isinstance(queue, dict) or any(name not in queue for name in _QUEUE_FIELDS) or not all(
            isinstance(queue[name], Real) and not isinstance(queue[name], bool) for name in _QUEUE_FIELDS):
        raise _fail("result_structure", "queue must carry the three customer-hour integrals as real numbers.",
                    {"queue": queue})
    if not isinstance(result.get("at_close"), dict):
        raise _fail("result_structure", "at_close must be a mapping.", {"at_close": result.get("at_close")})
    for index, row in enumerate(result["employee_timeline"]["breaks"]):
        if not isinstance(row.get("paid"), bool):
            raise _fail("result_structure", "Every engine break record must carry paid as True or False.",
                        {"index": index, "break": dict(row)})


# ── Paid time (section 4) ───────────────────────────────────────────────────


def _paid_rows(timeline: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Each employee's on-duty intervals in record (= time) order, with their pay class; checks break_mapping."""
    started: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in timeline["breaks"]:
        if row["actual_start"] is not None:
            started.setdefault((row["employee_id"], int(row["shift_index"])), []).append(row)
    mapped: dict[int, list[dict[str, Any]]] = {id(item): [] for items in started.values() for item in items}
    rows: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(timeline["intervals"]):
        on_break = row["state"] == ON_BREAK
        if row["shift_index"] is None:  # OFF: unpaid and never counted (C4); attribution ties None to OFF
            continue
        key = (row["employee_id"], int(row["shift_index"]))
        if on_break:
            matches = [item for item in started.get(key, [])
                       if item["actual_start"] <= row["start"] and row["end"] <= item["actual_end"]]
            if len(matches) != 1:
                raise _fail("break_mapping", "An ON_BREAK interval does not lie inside exactly one started break of "
                            "its shift.", {"index": index, "interval": dict(row), "matches": len(matches)})
            mapped[id(matches[0])].append(row)
            paid = matches[0]["paid"]
        else:
            paid = row["state"] in PAID_STATES
        rows.setdefault(row["employee_id"], []).append({
            "start": row["start"], "end": row["end"], "length": row["end"] - row["start"],
            "shift_index": key[1], "on_break": on_break, "paid": paid,
            "flagged": row["after_closing"] or row["past_scheduled_end"],
        })
    for items in started.values():
        for item in items:
            tiles = mapped[id(item)]
            if not tiles or tiles[0]["start"] != item["actual_start"] or tiles[-1]["end"] != item["actual_end"] or any(
                    first["end"] != second["start"] for first, second in zip(tiles, tiles[1:])):
                raise _fail("break_mapping", "The ON_BREAK intervals of a started break do not tile "
                            "[actual_start, actual_end) exactly.",
                            {"break": dict(item), "intervals": [dict(tile) for tile in tiles]})
    return rows


# ── Pay walk (section 5) ────────────────────────────────────────────────────


def _d7(a: float, b: float, field: str, evidence: dict[str, Any]) -> float:
    try:
        return derived_duration(a, b, field=field)
    except NamedAttributionError as error:
        raise _fail("finite_nonnegative", f"{field}: the D7 rule failed.",
                    {**evidence, "d7_failure": error.failure}) from None


def _pay_walk(paid: Sequence[dict[str, Any]], theta: float | None, evidence: dict[str, Any]) -> dict[str, Any]:
    """The F, G, and T pieces of one employee's paid intervals (time order, all shifts), per section 5.2.

    Returns the pieces as (shift_index, kind, hours), whether the threshold is required, whether the split is
    determined, and the threshold-reached instant.
    """
    required = any(not row["flagged"] for row in paid)
    pieces: list[tuple[int, str, float]] = []
    if theta is None:
        # Undetermined (step 5): only the flagged pieces are formed. Not required (step 6): every piece is flagged.
        pieces = [(row["shift_index"], "F", row["length"]) for row in paid if row["flagged"]]
        return {"required": required, "determined": not required, "pieces": pieces, "reached": None}
    exhausted, reached = False, None
    earlier: list[float] = []
    for k, row in enumerate(paid):
        length = row["length"]
        exhausted_before = exhausted
        at_or_past = False
        remaining: float | None = None
        if not exhausted:
            cumulative = math.fsum(earlier)  # every earlier paid length, flagged or not (C5 condition 3)
            if cumulative >= theta:
                exhausted, at_or_past = True, True
                reached = row["start"] if k == 0 else paid[k - 1]["end"]
            else:
                remaining = _d7(theta, cumulative, "R_k", {**evidence, "k": k})
                if remaining == length:
                    exhausted, reached = True, row["end"]
                elif remaining < length:
                    exhausted, reached = True, row["start"] + remaining
        earlier.append(length)
        if row["flagged"]:
            pieces.append((row["shift_index"], "F", length))  # one premium only: no threshold split
        elif exhausted_before or at_or_past:
            pieces.append((row["shift_index"], "T", length))
        else:
            assert remaining is not None  # computed whenever the threshold was not already reached
            if remaining >= length:
                pieces.append((row["shift_index"], "G", length))
            else:
                pieces.append((row["shift_index"], "G", remaining))
                pieces.append((row["shift_index"], "T", _d7(length, remaining, "T crossing", {**evidence, "k": k})))
    return {"required": required, "determined": True, "pieces": pieces, "reached": reached}


def _hours(rows: Sequence[dict[str, Any]], pieces: Sequence[tuple[int, str, float]], determined: bool,
           evidence: dict[str, Any]) -> dict[str, Any]:
    """Paid, break, and piece sums over the given rows and pieces (one shift or one employee)."""
    def total(values: Iterable[float], field: str) -> float:
        return _fsum(values, field, evidence)

    flagged_sum = total([hours for _, kind, hours in pieces if kind == "F"], "past_end_or_after_closing_hours")
    regular = total([hours for _, kind, hours in pieces if kind == "G"], "regular_paid_hours")
    threshold_only = total([hours for _, kind, hours in pieces if kind == "T"], "daily_threshold_only_hours")
    return {
        "paid_hours": total([row["length"] for row in rows if row["paid"]], "paid_hours"),
        "paid_break_hours": total([row["length"] for row in rows if row["paid"] and row["on_break"]],
                                  "paid_break_hours"),
        "unpaid_break_hours": total([row["length"] for row in rows if not row["paid"] and row["on_break"]],
                                    "unpaid_break_hours"),
        "unpaid_flagged_break_hours": total([row["length"] for row in rows
                                             if not row["paid"] and row["on_break"] and row["flagged"]],
                                            "unpaid_flagged_break_hours"),
        "regular_paid_hours": regular if determined else None,
        "overtime_paid_hours": total([flagged_sum, threshold_only], "overtime_paid_hours") if determined else None,
        "overtime_breakdown": {"past_end_or_after_closing_hours": flagged_sum,
                               "daily_threshold_only_hours": threshold_only if determined else None},
        "_g": regular, "_t": threshold_only,
    }


def _check_partitions(hours: dict[str, Any], attribution: dict[str, Any], theta: float | None,
                      evidence: dict[str, Any]) -> None:
    """paid_partition and overtime_partition for one shift or employee against its attribution record."""
    unpaid_break = hours["unpaid_break_hours"]
    if not (_close_enough(hours["paid_hours"] + unpaid_break, attribution["on_duty_hours"])
            and _close_enough(hours["paid_break_hours"] + unpaid_break, attribution["hours_by_state"][ON_BREAK])):
        raise _fail("paid_partition", "Paid and unpaid time do not reconcile with the attribution's on-duty or ON_BREAK "
                    "hours.", {**evidence, "paid_hours": hours["paid_hours"],
                               "paid_break_hours": hours["paid_break_hours"], "unpaid_break_hours": unpaid_break,
                               "on_duty_hours": attribution["on_duty_hours"],
                               "on_break_hours": attribution["hours_by_state"][ON_BREAK]})
    flagged_sum = hours["overtime_breakdown"]["past_end_or_after_closing_hours"]
    union = attribution["closing_attribution"]["after_closing_or_past_scheduled_end_hours"]
    regular, overtime = hours["regular_paid_hours"], hours["overtime_paid_hours"]
    problems = []
    if not (flagged_sum >= 0 and hours["_g"] >= 0 and hours["_t"] >= 0):
        problems.append("a piece sum is below 0")
    if not _close_enough(flagged_sum + hours["unpaid_flagged_break_hours"], union):
        problems.append("F plus unpaid flagged ON_BREAK time differs from the attribution's flagged union")
    if regular is not None and not _close_enough(regular + overtime, hours["paid_hours"]):
        problems.append("regular + overtime differs from paid_hours")
    if regular is not None and theta is not None and not (regular <= theta or _close_enough(regular, theta)):
        problems.append("regular paid time exceeds the daily threshold")
    if problems:
        raise _fail("overtime_partition", "The regular and overtime pieces do not reconcile: " + "; ".join(problems)
                    + ".", {**evidence, "past_end_or_after_closing_hours": flagged_sum,
                            "regular_paid_hours": regular, "overtime_paid_hours": overtime,
                            "paid_hours": hours["paid_hours"], "attribution_union_hours": union,
                            "daily_threshold_hours": theta})


# ── Run-level evidence (sections 7 and C9) ──────────────────────────────────


def _check_unserved(result: dict[str, Any]) -> dict[str, Any]:
    """unserved_consistency (section 7): the engine's closing record agrees with itself; nothing is recomputed."""
    policy, at_close, counts = result["closing_policy"], result["at_close"], result["counts"]
    waiting, crew = at_close.get("waiting_customer_ids"), at_close.get("drain_crew")
    if not isinstance(waiting, (list, tuple)) or not isinstance(crew, (list, tuple)) or not all(
            _whole(item) for item in waiting) or not all(isinstance(item, str) for item in crew):
        raise _fail("unserved_consistency", "at_close must carry waiting_customer_ids (whole numbers) and drain_crew "
                    "(employee ids) as lists; a run that never processed closing has neither.", {"at_close": at_close})
    total, reasons = counts["unserved_at_close"], counts["unserved_by_reason"]
    if set(reasons) != set(UNSERVED_REASONS) or not all(_whole(value) and value >= 0 for value in reasons.values()) \
            or not _whole(total) or total < 0 or total != sum(reasons.values()):
        raise _fail("unserved_consistency", "counts.unserved_by_reason must have exactly hard_cutoff and "
                    "no_eligible_employee, whole and 0 or more, summing to unserved_at_close.",
                    {"unserved_at_close": total, "unserved_by_reason": reasons})
    unserved = [row for row in result["customers"] if row["status"] == UNSERVED_AT_CLOSE]
    found = {reason: sum(1 for row in unserved if row["unserved_reason"] == reason) for reason in UNSERVED_REASONS}
    # With found == reasons and len(unserved) == total == sum(reasons), every unserved row has a known reason.
    if len(unserved) != total or found != reasons or any(
            row["unserved_reason"] is not None for row in result["customers"] if row["status"] != UNSERVED_AT_CLOSE):
        raise _fail("unserved_consistency", "The unserved customer rows do not match unserved_at_close and its "
                    "reasons, or a departed row carries a reason.",
                    {"unserved_at_close": total, "unserved_by_reason": reasons, "rows_by_reason": found,
                     "unserved_rows": len(unserved)})
    ids = sorted(row["customer_id"] for row in unserved)
    if policy == HARD_CUTOFF:
        agrees = reasons[NO_ELIGIBLE_EMPLOYEE] == 0 and ids == sorted(waiting)
    elif crew:
        agrees = total == 0  # DRAIN with a crew: the crew serves the admitted line (P5), so nobody is unserved
    else:
        # DRAIN with an empty crew (X6): every waiting customer is unserved, all as no_eligible_employee (the sum rule
        # above then gives no_eligible_employee == unserved_at_close); with nobody waiting, nobody is unserved.
        agrees = reasons[HARD_CUTOFF_REASON] == 0 and ids == sorted(waiting)
    if not agrees:
        raise _fail("unserved_consistency", "The unserved customers do not agree with the closing policy, the waiting "
                    "line at closing, and the DRAIN crew.",
                    {"closing_policy": policy, "unserved_customer_ids": ids, "waiting_customer_ids": list(waiting),
                     "drain_crew": list(crew), "unserved_by_reason": reasons})
    return {"closing_policy": policy,
            "rule": "X6 HARD_CUTOFF (inherited)" if policy == HARD_CUTOFF else "C10b DRAIN (realized)",
            "unserved_at_close": total, "unserved_by_reason": dict(reasons), "drain_crew": list(crew),
            "waiting_customer_count": len(waiting)}


def _check_waiting(result: dict[str, Any]) -> float:
    queue = result["queue"]
    values = {name: queue[name] for name in _QUEUE_FIELDS}
    if not all(_finite(value) and value >= 0 for value in values.values()):
        raise _fail("waiting_consistency", "The queue customer-hour integrals must be finite and 0 or more.", values)
    expected = queue["customer_hours_in_horizon"] + queue["customer_hours_after_closing"]
    if not _close_enough(queue["customer_hours_total"], expected):
        raise _fail("waiting_consistency", "customer_hours_total differs from in-horizon plus after-closing hours "
                    "beyond the tolerance.", values)
    return queue["customer_hours_total"]


# ── Components (sections 3 and 9) ───────────────────────────────────────────


def _component(name: str, quantity: Any, unit: str, source: str, rate_field: str, rate: Any, *,
               applies: bool = True) -> dict[str, Any]:
    used = "; the supplied rate is recorded but not used." if rate is not None else "."
    if not applies:
        status, cost, required = NOT_APPLICABLE, None, False
        note = "Under DRAIN nobody was unserved in this run (C10b), so this term is not applied" + used
    elif quantity is None:
        status, cost, required = HOURS_UNDETERMINED, None, None
        note = ("daily_regular_paid_minutes is required (C14) and was not supplied, so the regular and overtime "
                "hours are undetermined; no value is substituted.")
    elif quantity == 0:
        status, cost, required = ZERO_QUANTITY, 0.0, False
        note = "The quantity is exactly 0, so no rate is required (C13)" + used
    elif rate is None:
        status, cost, required = RATE_MISSING, None, True
        note = f"{rate_field} was not supplied; no value is substituted."
    else:
        status, cost, required, note = COSTED, quantity * float(rate), True, None
    return {"component": name, "quantity": quantity, "unit": unit, "source": source, "rate_field": rate_field,
            "rate": rate, "applies": applies, "rate_required": required, "cost": cost, "status": status, "note": note}


def _missing(scope: str, employee_id: str | None, field: str, status: str, requirement: str) -> dict[str, Any]:
    return {"scope": scope, "employee_id": employee_id, "field": field, "status": status, "requirement": requirement}


def _labor(employee_id: str, pay: EmployeePay, hours: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    components = [
        _component(name, hours[quantity], "paid hours", f"pay walk: {quantity}", field, getattr(pay, field))
        for name, quantity, field in _LABOR
    ]
    missing = []
    if hours["regular_paid_hours"] is None:
        missing.append(_missing("employee", employee_id, "daily_regular_paid_minutes", HOURS_UNDETERMINED, "required"))
        missing += [_missing("employee", employee_id, field, HOURS_UNDETERMINED, "undetermined")
                    for _, _, field in _LABOR if getattr(pay, field) is None]
    missing += [_missing("employee", employee_id, row["rate_field"], RATE_MISSING, "required")
                for row in components if row["status"] == RATE_MISSING]
    return components, missing


# ── Output checks ───────────────────────────────────────────────────────────


def _check_output(out: dict[str, Any], components: list[dict[str, Any]]) -> None:
    """finite_nonnegative on every output hour and cost, and cost_arithmetic on every component and total."""
    values: list[tuple[str, Any]] = [("total_cost", out["total_cost"]), ("labor.total_cost", out["labor"]["total_cost"])]
    for employee in out["employees"]:
        records = [employee, *(row for row in employee["shifts"] if row["activated"])]
        for record in records:
            prefix = f"{employee['employee_id']}" + ("" if record is employee else f".shift[{record['shift_index']}]")
            for field in ("paid_hours", "paid_break_hours", "unpaid_break_hours", "regular_paid_hours",
                          "overtime_paid_hours"):
                values.append((f"{prefix}.{field}", record[field]))
            values += [(f"{prefix}.overtime_breakdown.{key}", value)
                       for key, value in record["overtime_breakdown"].items()]
        values += [(f"{employee['employee_id']}.labor_cost", employee["labor_cost"]),
                   (f"{employee['employee_id']}.daily_threshold_hours", employee["daily_threshold_hours"])]
    values += [(f"component {row['component']}.cost", row["cost"]) for row in components]
    for field, value in values:
        if value is not None and not (math.isfinite(value) and value >= 0):
            raise _fail("finite_nonnegative", f"{field} is not a finite number, 0 or more.",
                        {"field": field, "value": value})
    for row in components:
        quantity, rate, cost, status = row["quantity"], row["rate"], row["cost"], row["status"]
        expected = {
            NOT_APPLICABLE: not row["applies"] and cost is None,
            HOURS_UNDETERMINED: row["applies"] and quantity is None and cost is None,
            ZERO_QUANTITY: row["applies"] and quantity == 0 and cost == 0.0,
            RATE_MISSING: row["applies"] and quantity is not None and quantity > 0 and rate is None and cost is None,
            COSTED: (row["applies"] and quantity is not None and quantity > 0 and rate is not None
                     and cost == quantity * float(rate)),
        }.get(status, False)
        if not expected:
            raise _fail("cost_arithmetic", "A component's status and cost do not follow the section 9 rules.",
                        {"component": dict(row)})
    withheld = any(row["status"] in (RATE_MISSING, HOURS_UNDETERMINED) for row in components)
    costs = [row["cost"] for row in components if row["status"] in (COSTED, ZERO_QUANTITY)]
    labor = [employee["labor_cost"] for employee in out["employees"]]
    if (out["total_cost"] is None) != withheld or (not withheld and out["total_cost"] != math.fsum(costs)) or (
            out["labor"]["total_cost"] is None) != any(value is None for value in labor) or (
            out["labor"]["total_cost"] is not None and out["labor"]["total_cost"] != math.fsum(labor)):
        raise _fail("cost_arithmetic", "The totals are not the fsums of the COSTED and ZERO_QUANTITY costs.",
                    {"total_cost": out["total_cost"], "labor_total_cost": out["labor"]["total_cost"]})


# ── Entry point ─────────────────────────────────────────────────────────────


def _employee_record(employee_id: str, pay: EmployeePay, theta: float | None, rows: list[dict[str, Any]],
                     attribution_shifts: list[dict[str, Any]], attribution_employee: dict[str, Any],
                     ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    evidence = {"employee_id": employee_id}
    walk = _pay_walk([row for row in rows if row["paid"]], theta, evidence)
    determined = walk["determined"]
    totals = _hours(rows, walk["pieces"], determined, evidence)
    shifts = []
    for shift in attribution_shifts:
        index = shift["shift_index"]
        if not shift["activated"]:
            shifts.append({"shift_index": index, "activated": False, **dict.fromkeys((
                "paid_hours", "paid_break_hours", "unpaid_break_hours", "regular_paid_hours", "overtime_paid_hours",
                "overtime_breakdown"))})
            continue
        where = {**evidence, "shift_index": index}
        mine = _hours([row for row in rows if row["shift_index"] == index],
                      [piece for piece in walk["pieces"] if piece[0] == index], determined, where)
        _check_partitions(mine, shift, theta, where)
        shifts.append({"shift_index": index, "activated": True,
                       **{key: value for key, value in mine.items() if not key.startswith(("_", "unpaid_flagged"))}})
    _check_partitions(totals, attribution_employee, theta, evidence)
    components, missing = _labor(employee_id, pay, totals)
    costs = [row["cost"] for row in components]
    record = {
        "employee_id": employee_id,
        "pay": asdict(pay),
        "paid_hours": totals["paid_hours"],
        "paid_break_hours": totals["paid_break_hours"],
        "unpaid_break_hours": totals["unpaid_break_hours"],
        "threshold_required": walk["required"],
        "daily_threshold_hours": theta,
        "threshold_reached_at_hours": walk["reached"],
        "hours_status": DETERMINED if determined else HOURS_UNDETERMINED,
        "regular_paid_hours": totals["regular_paid_hours"],
        "overtime_paid_hours": totals["overtime_paid_hours"],
        "overtime_breakdown": totals["overtime_breakdown"],
        "shifts": shifts,
        "components": components,
        "labor_cost": None if any(cost is None for cost in costs) else _fsum(costs, "labor_cost", evidence),
        "labor_cost_withheld": [{"field": item["field"], "status": item["status"]}
                                for item in missing if item["requirement"] == "required"],
    }
    return record, components, missing


def _build(result: object, employees: object, rates: object) -> dict[str, Any]:
    attribution = build_named_attribution(result, employees)  # type: ignore[arg-type]  # its failures propagate
    checked_rates = _check_rates(rates)
    assert isinstance(result, dict) and isinstance(employees, (list, tuple))  # established by the attribution
    pay = _check_pay(employees)
    _check_result(result)
    rows = _paid_rows(result["employee_timeline"])
    records, components, missing = [], [], []
    for employee in attribution["employees"]:
        employee_id = employee["employee_id"]
        record, own, gaps = _employee_record(
            employee_id, pay[employee_id][0], pay[employee_id][1], rows.get(employee_id, []),
            [shift for shift in attribution["shifts"] if shift["employee_id"] == employee_id], employee)
        records.append(record)
        components += own
        missing += gaps
    basis = _check_unserved(result)
    waiting_hours = _check_waiting(result)
    applies = result["closing_policy"] == HARD_CUTOFF or basis["unserved_at_close"] > 0
    waiting = _component("waiting", waiting_hours, "customer-hours", "queue.customer_hours_total", "waiting_rate",
                         checked_rates.waiting_rate)
    unserved = {**_component("unserved_customer", basis["unserved_at_close"], "customers", "counts.unserved_at_close",
                             "unserved_customer_rate", checked_rates.unserved_customer_rate, applies=applies),
                "applicability_basis": basis}
    components += [waiting, unserved]
    missing += [_missing("run", None, row["rate_field"], RATE_MISSING, "required")
                for row in (waiting, unserved) if row["status"] == RATE_MISSING]
    labor_costs = [record["labor_cost"] for record in records]
    withheld = any(row["status"] in (RATE_MISSING, HOURS_UNDETERMINED) for row in components)
    total = None if withheld else _fsum([row["cost"] for row in components if row["status"] in (COSTED, ZERO_QUANTITY)],
                                        "total_cost", {})
    required = [item for item in missing if item["requirement"] == "required"]
    provenance = attribution["provenance"]
    replication = provenance["replication"]
    out = {
        "employees": records,
        "labor": {
            "total_cost": None if any(cost is None for cost in labor_costs) else _fsum(labor_costs, "labor.total_cost",
                                                                                         {}),
            "withheld": [{"employee_id": item["employee_id"], "field": item["field"], "status": item["status"]}
                         for item in required if item["scope"] == "employee"],
        },
        "waiting": waiting,
        "unserved": unserved,
        "total_cost": total,
        "missing": missing,
        "total_withheld_reason": None if total is not None else "Withheld: " + "; ".join(
            f"{item['employee_id'] or 'run'}.{item['field']} ({item['status']})" for item in required) + ".",
        "formula": (
            "sum over employees of (regular_paid_hours × regular_rate_per_hour + overtime_paid_hours × "
            "overtime_rate_per_hour) + queue.customer_hours_total × waiting_rate + counts.unserved_at_close × "
            "unserved_customer_rate (the last term only when it applies: always under HARD_CUTOFF, and under DRAIN "
            "only when a customer was unserved). A quantity of exactly 0 costs 0.0 with no rate required."),
        "currency": "The caller's currency; this module assumes none.",
        "reconciliation": [dict(item) for item in RECONCILIATION],
        "definitions": dict(DEFINITIONS),
        "checks": dict(CHECKS),
        "undetermined": list(UNDETERMINED),
        "provenance": {
            "cost_version": NAMED_COST_VERSION,
            "attribution_version": provenance["attribution_version"],
            "named_engine_version": provenance["named_engine_version"],
            "state_machine_version": provenance["state_machine_version"],
            "closing_policy": provenance["closing_policy"],
            "replication": None if replication is None else {**replication, "spawn_key": list(replication["spawn_key"])},
            "inputs_sha256": None,
            "inputs_sha256_reason": (
                "full run inputs unavailable: the module receives only the result, the input employees, and the "
                "rates; no partial digest is computed (5B-4.6 D4)"),
            "time_unit": "hours",
            "tolerance": dict(TOLERANCE, applies_to=(
                "reconciliation and D7 only; times, order, and the threshold instant compare exactly")),
            "capacity_terms_not_charged": "Phase 3A server-hour terms and staffing capacity (C2)",
            "scheduled_pay_not_mixed": "5B-1 scheduled pay is a planning quantity and is not part of this cost",
            "scope_note": "Modeled workforce cost; not an employment-law or payroll-compliance interpretation.",
        },
    }
    _check_output(out, components)
    return out


def cost_named_workforce(result: dict[str, Any], employees: Sequence[Employee], rates: NamedCostRates) -> dict[str, Any]:
    """The named workforce cost of one named-engine result; raises ``NamedCostError`` on any failed check.

    ``result`` is a ``simulate_named_prescribed`` or ``simulate_named_replication`` result, ``employees`` the run's
    input employees (the same list attribution takes; each carries its ``EmployeePay``), and ``rates`` the caller's
    waiting and unserved rates. None has a default. ``NamedAttributionError`` from ``build_named_attribution``
    propagates unchanged.
    """
    try:
        return _build(result, employees, rates)
    except _Violation as violation:
        raise NamedCostError(violation.failure) from None
