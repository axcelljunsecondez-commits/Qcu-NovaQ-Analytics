"""Day cost of one continuous shared-queue DES run (Phase 3A of the shared-queue enhancement).

The DES reports hours and counts only (``cost_quantities``); this module applies rates the
caller supplies. It holds no monetary default and never substitutes 0 for a missing rate:

    total_cost = regular_server_hours × regular_server_rate
               + overtime_server_hours × overtime_rate
               + total_waiting_customer_hours × waiting_rate
               + unserved_customer_count × unserved_customer_rate

The unserved-customer term applies only when the configured closing can leave customers
unserved (``cost_quantities.unserved_possible``).

Spec: docs/superpowers/specs/2026-09-25-shared-queue-closing-policy.md.
Nothing legacy imports this module; the legacy ``REGULAR_RATE`` / ``OT_RATE`` are not used.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any

from backend.queueing_engine.services.shared_segments import SharedSegmentError

COSTED, RATE_MISSING, NOT_APPLICABLE = "COSTED", "RATE_MISSING", "NOT_APPLICABLE"

SERVER_HOURS_NOTE = (
    "Server-hours are modeled service-capacity hours from the DES, not necessarily paid "
    "employee-hours; the server and overtime costs are costs of modeled capacity."
)


@dataclass(frozen=True)
class DayCostRates:
    """Rates in the caller's currency. Every field is required; ``None`` means not supplied."""

    regular_server_rate: float | None  # per modeled server-hour inside the horizon
    overtime_rate: float | None  # per modeled server-hour after closing
    waiting_rate: float | None  # per customer-hour spent waiting
    unserved_customer_rate: float | None  # per customer recorded as unserved_at_close


_COMPONENTS = (
    # (component, quantity key, rate field, unit of the quantity)
    ("regular_server", "regular_server_hours", "regular_server_rate", "server-hours"),
    ("overtime_server", "overtime_server_hours", "overtime_rate", "server-hours"),
    ("waiting", "total_waiting_customer_hours", "waiting_rate", "customer-hours"),
    ("unserved_customer", "unserved_customer_count", "unserved_customer_rate", "customers"),
)


def validate_rates(rates: DayCostRates) -> None:
    """Raise ``SharedSegmentError`` for a supplied rate that is not a finite number, 0 or more."""
    problems = []
    for _, _, field, _ in _COMPONENTS:
        value = getattr(rates, field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or value < 0:
            problems.append(f"{field} must be a finite number, 0 or more, or None when not supplied.")
    if problems:
        raise SharedSegmentError(problems)


def cost_shared_day(result: dict[str, Any], rates: DayCostRates) -> dict[str, Any]:
    """Cost one ``simulate_prescribed`` / ``simulate_shared_day`` result with caller rates."""
    validate_rates(rates)
    quantities = result["cost_quantities"]
    components = []
    missing = []
    for name, quantity_key, field, unit in _COMPONENTS:
        quantity = quantities[quantity_key]
        rate = getattr(rates, field)
        applies = quantities["unserved_possible"] if name == "unserved_customer" else True
        if not applies:
            status, cost = NOT_APPLICABLE, None
            note = (
                "The configured closing policy cannot leave customers unserved, so this term is not "
                "applied" + ("; the supplied rate is recorded but not used." if rate is not None else ".")
            )
        elif rate is None:
            status, cost, note = RATE_MISSING, None, f"{field} was not supplied; no value is substituted."
            missing.append(field)
        else:
            status, cost, note = COSTED, quantity * float(rate), None
        components.append({
            "component": name, "quantity": quantity, "unit": unit, "rate_field": field,
            "rate": rate, "applies": applies, "cost": cost, "status": status, "note": note,
        })
    complete = not missing
    return {
        "closing_policy": quantities["closing_policy"],
        "components": components,
        "total_cost": math.fsum(row["cost"] for row in components if row["status"] == COSTED) if complete else None,
        "total_withheld_reason": None if complete else f"Rates not supplied: {', '.join(missing)}.",
        "formula": (
            "regular_server_hours × regular_server_rate + overtime_server_hours × overtime_rate + "
            "total_waiting_customer_hours × waiting_rate + unserved_customer_count × unserved_customer_rate "
            "(the last term only when unserved customers are possible)"
        ),
        "currency": "The caller's currency; this module assumes none.",
        "server_hours_note": SERVER_HOURS_NOTE,
        "rates": asdict(rates),
    }
