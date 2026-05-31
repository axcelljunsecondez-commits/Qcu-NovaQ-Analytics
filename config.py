"""
config.py — Centralized constants for the QCU Queueing Dashboard.

All default values live in exactly one place. Source files import from here
rather than defining literals locally.
"""

# ── Server / Labor Cost ──────────────────────────────────────────────
DEFAULT_SERVER_COST_HR = 87.0
REGULAR_RATE = 87.0
OT_RATE = 109.0

# ── Waiting / Customer Cost ──────────────────────────────────────────
DEFAULT_WAIT_COST_HR = 100.0
DEFAULT_CUSTOMER_WAITING_COST = 100.0

# ── Abandonment ──────────────────────────────────────────────────────
DEFAULT_ABANDONMENT_COST = 60.0
DEFAULT_ABANDONMENT_RATE = 0.10

# ── Optimization ─────────────────────────────────────────────────────
DEFAULT_TARGET_UTILIZATION = 0.70
DEFAULT_SERVER_COST = 1.0
DEFAULT_MAX_SERVERS = 24

# ── Simulation / Validation ──────────────────────────────────────────
UNSTABLE_PENALTY_MULTIPLIER = 10.0
UNSTABLE_FIXED_COST = 5000.0
DEFAULT_HOURS_PER_INTERVAL = 1.0
