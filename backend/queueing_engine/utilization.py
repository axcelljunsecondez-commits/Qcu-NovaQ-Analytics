"""Utilization status bands shared by analytical, simulation, and report output.

Bands (ρ = λ / (cμ)):
- Lean:     ρ < 60%
- Normal:   60% ≤ ρ ≤ 80%
- Peak:     80% < ρ < 90%
- Critical: 90% ≤ ρ ≤ 100%
- Unstable: ρ > 100%
"""

from __future__ import annotations

LEAN_THRESHOLD = 0.60        # ρ < this → Lean
NORMAL_THRESHOLD = 0.80      # 0.60 ≤ ρ ≤ this → Normal
CRITICAL_THRESHOLD = 0.90    # ρ ≥ this → Critical
UNSTABLE_THRESHOLD = 1.0     # ρ > this → Unstable

# λ / (cμ) carries binary float noise: inputs whose exact ρ is 0.9 (λ=0.99,
# μ=1.1, c=1) compute as 0.8999999999999999. A value within this distance of a
# boundary counts as on it. It sits far above float noise (~1e-16) and far
# below the smallest displayed step (0.0001 percentage points = 1e-6).
THRESHOLD_TOLERANCE = 1e-9


def utilization_band(rho: float) -> str:
    """Status band for a numeric ρ. NaN falls through every comparison to Lean."""
    if rho > UNSTABLE_THRESHOLD + THRESHOLD_TOLERANCE:
        return "Unstable"
    if rho >= CRITICAL_THRESHOLD - THRESHOLD_TOLERANCE:
        return "Critical"
    if rho > NORMAL_THRESHOLD + THRESHOLD_TOLERANCE:
        return "Peak"
    if rho >= LEAN_THRESHOLD - THRESHOLD_TOLERANCE:
        return "Normal"
    return "Lean"
