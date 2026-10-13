"""
config.py — Centralized constants for the QCU Queueing Dashboard.

All default values live in exactly one place. Source files import from here
rather than defining literals locally.
"""

# ── Server / Labor Cost ──────────────────────────────────────────────
DEFAULT_SERVER_COST_HR = 94.375  # NCR non-agri minimum wage PHP 755/day (Wage Order NCR-28) / 8 h
REGULAR_RATE = 87.0
OT_RATE = 109.0

# ── Waiting / Customer Cost ──────────────────────────────────────────
DEFAULT_WAIT_COST_HR = 100.0

# ── Abandonment ──────────────────────────────────────────────────────
DEFAULT_ABANDONMENT_COST = 0.0
DEFAULT_ABANDONMENT_RATE = 0.0

# ── Optimization ─────────────────────────────────────────────────────
DEFAULT_TARGET_UTILIZATION = 0.70
DEFAULT_MAX_SERVERS = 24

# ── Simulation / Validation ──────────────────────────────────────────
UNSTABLE_PENALTY_MULTIPLIER = 10.0
DEFAULT_HOURS_PER_INTERVAL = 1.0

# Separate-queue break policy (operational configuration, not queueing theory).
# Minutes before a scheduled break start during which the lane drains.
PRE_BREAK_CUTOFF_MINUTES = 3.0


# Monte Carlo analytical perturbation defaults (assumptions, not observations).
MC_DEFAULT_TRIALS = 2000
MC_DEFAULT_FAILURE_THRESHOLD = 0.75
MC_FAILURE_RATE_CAP = 0.05
MC_ARRIVAL_NOISE = 0.20
MC_SERVICE_NOISE = 0.10
MC_MAX_TRIALS = 100000
# Trials x total counters (c summed over segments) per Monte Carlo run, owner-approved 2026-10-13 (OD-N4):
# the largest measured value whose every run kept a margin under 60 s on a Render-Free-like container
# (docs/superpowers/specs/2026-10-12-large-server-count-erlang-numerics.md section 9).
MC_MAX_COUNTER_TRIALS = 24_000_000
MC_CONFIDENCE_LEVEL = 0.95
