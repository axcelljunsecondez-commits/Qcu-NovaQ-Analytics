"""
simulation.py — Discrete-event (SimPy) and Monte Carlo simulation engines.

Provides two complementary simulation approaches for M/M/1 and M/M/c
queueing systems:

  DES (SimPy)        — Event-by-event simulation tracking every arrival,
                       service, and queue state change. Produces empirical
                       rho_sim, Lq_sim, Wq_sim, max_queue, served, dropped.

  Monte Carlo        — Repeated analytical computations with perturbed
                       arrival/service rates. Produces mean, std, percentiles,
                       and failure rates per segment.

DES metric glossary
───────────────────
  rho_sim      : empirical server utilization (fraction of busy time)
  Lq_sim       : time-average queue length  (Little's Law: Lq = λ * Wq)
  Wq_sim       : mean waiting time in queue  (hours)
  max_queue    : maximum observed queue depth during the interval
  status       : NORMAL / BUSY / OVERLOADED based on configurable thresholds
  served       : total customers served in the interval
  dropped      : customers who arrived during an overloaded stretch

Monte Carlo metric glossary
───────────────────────────
  rho_mean     : mean utilization across trials
  rho_std      : std deviation of utilization
  rho_p95      : 95th percentile utilization
  Lq_mean      : mean queue length across trials
  Wq_mean      : mean wait time across trials
  failure_rate : proportion of trials where rho > failure_threshold
  failure_rate_ci_lower / _upper / _half_width
               : 95 % Wilson confidence interval on failure_rate
  failure_rate_precision : high / moderate / low band of the CI half-width
  failure_rate_adequate : whether the CI half-width is within the adequacy band
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import simpy

from backend.data.ingestion import validate_and_normalize
from backend.queueing_engine.log import get_logger
from backend.queueing_engine.models import mm1, mmc
from backend.queueing_engine.services.model_selection import select_model
from backend.queueing_engine.statistics.proportions import (
    ADEQUATE_MAX_HW,
    failure_rate_precision,
    wilson_ci,
)

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Simulation constants
# ──────────────────────────────────────────────────────────────────────────────

LEAN_THRESHOLD = 0.60        # ρ < this → Lean
NORMAL_THRESHOLD = 0.80      # 0.60 ≤ ρ < this → Normal
CRITICAL_THRESHOLD = 0.90    # ρ ≥ this → Critical
UNSTABLE_THRESHOLD = 1.0     # ρ > this → Unstable
DEFAULT_QUEUE_OVERLOAD = 20  # queue depth that triggers Critical regardless of ρ
SIM_HOURS_PER_SEGMENT = 24.0  # simulated hours per segment
RANDOM_SEED = 42             # reproducible runs; override per call for stochastic analysis


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SegmentResult:
    """Holds simulation output for one time segment."""
    time: str
    lambda_: float
    mu: float
    c: int

    # Empirical metrics
    rho_sim: float | None = None
    Lq_sim: float | None = None
    Wq_sim: float | None = None
    max_queue: int = 0
    served: int = 0
    dropped: int = 0
    status: str = "Lean"
    error: str | None = None
    warmup_fraction: float = 0.0
    warmup_end: float = 0.0
    initial_queue_depth: int = 0
    final_Lq: int = 0
    requested_sim_hours: float = 0.0
    effective_sim_hours: float = 0.0
    measurement_hours: float = 0.0

    selected_model: str | None = None
    simulation_supported: bool = False

    # Internal accumulators (not exposed to callers)
    _busy_area: float = field(default=0.0, repr=False)
    _queue_area: float = field(default=0.0, repr=False)
    _wait_sum: float = field(default=0.0, repr=False)

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "lambda": self.lambda_,
            "mu": self.mu,
            "c": self.c,
            "metric_provenance": "simulated",
            "requested_sim_hours": self.requested_sim_hours,
            "effective_sim_hours": self.effective_sim_hours,
            "measurement_hours": self.measurement_hours,
            "served_basis": "service_starts_after_warmup",
            "wait_time_unit": "hours",
            "wait_estimator": "mean_of_service_starts" if self.served else "queue_area_over_arrival_rate",
            "rho_sim": self.rho_sim,
            "Lq_sim": self.Lq_sim,
            "Wq_sim": self.Wq_sim,
            "max_queue": self.max_queue,
            "served": self.served,
            "dropped": self.dropped,
            "status": self.status,
            "error": self.error,
            "selected_model": self.selected_model,
            "simulation_supported": self.simulation_supported,
            "warmup_fraction": self.warmup_fraction,
            "warmup_end": self.warmup_end,
            "initial_queue_depth": self.initial_queue_depth,
            "final_Lq": self.final_Lq,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def simulation_coverage(segment: Mapping) -> tuple[str | None, str | None]:
    """Identify the model using the shared dispatcher; only M/M families are simulated."""
    row = {"time": "segment", "c": 1, **segment}
    ok, message, frame = validate_and_normalize(pd.DataFrame([row]))
    if not ok:
        return None, message
    row = frame.astype(object).where(pd.notna(frame), None).to_dict("records")[0]
    selected = select_model(row.get("lambda"), row.get("mu"), row.get("c"),
                            row.get("variance"), row.get("K"), row.get("theta"))
    name = selected["name"]
    if name not in ("M/M/1", "M/M/c"):
        return name, f"Unsupported simulation model: {name}. DES/Monte Carlo cover M/M/1 and M/M/c only."
    return name, None


def _validate_segment(segment: Mapping[str, Any]) -> tuple[str | None, float | None, float | None, int]:
    """Extract and validate segment fields. Returns (error, lambda_, mu, c)."""
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    c = segment.get("c", 1)

    if lambda_ is None or mu is None:
        return "Missing lambda or mu.", None, None, 1

    try:
        lambda_ = float(lambda_)
        mu = float(mu)
        if isinstance(c, bool) or not math.isfinite(float(c)) or not float(c).is_integer():
            return "c must be a finite integer.", None, None, 1
        c = int(c)
    except (TypeError, ValueError, OverflowError):
        return "lambda, mu, and c must be numeric.", None, None, 1

    if not math.isfinite(lambda_):
        return "lambda must be a finite number.", None, None, c
    if not math.isfinite(mu):
        return "mu must be a finite number.", None, None, c
    if lambda_ < 0:
        return "lambda must be >= 0.", None, None, c
    if mu <= 0:
        return "mu must be > 0.", None, None, c
    if c <= 0:
        return "c must be >= 1.", None, None, c

    return None, lambda_, mu, c


def _classify_status(rho: float, max_queue: int, queue_overload_threshold: int) -> str:
    """Map empirical utilization + queue depth to a status label.
    
    Categories:
    - Lean: ρ < 60%
    - Normal: 60% ≤ ρ < 80%
    - Peak: 80% < ρ < 90%
    - Critical: ρ ≥ 90% or queue depth ≥ threshold
    - Unstable: ρ > 1 (system unstable)
    """
    if rho > UNSTABLE_THRESHOLD:
        return "Unstable"
    if rho >= CRITICAL_THRESHOLD or max_queue >= queue_overload_threshold:
        return "Critical"
    if rho > NORMAL_THRESHOLD:
        return "Peak"
    if rho >= LEAN_THRESHOLD:
        return "Normal"
    return "Lean"


def _exponential(rate: float, rng: random.Random) -> float:
    """Draw an exponential inter-event time; guard against zero rate."""
    if rate <= 0:
        return float("inf")
    return rng.expovariate(rate)


# ──────────────────────────────────────────────────────────────────────────────
# SimPy process definitions
# ──────────────────────────────────────────────────────────────────────────────

class _QueueMonitor:
    """Tracks time-averaged queue length and server busyness via area-under-curve."""

    def __init__(self, env: simpy.Environment, servers: simpy.Resource, warmup_end: float = 0.0):
        self.env = env
        self.servers = servers
        self._warmup_end = warmup_end
        self._last_t = 0.0
        self._queue_area = 0.0   # ∫ Lq(t) dt  (post-warmup only)
        self._busy_area = 0.0    # ∫ busy_servers(t) dt  (post-warmup only)

    def _snapshot(self, at: float | None = None) -> None:
        """Accumulate area since the last snapshot, optionally forcing a time.

        Only the portion of each interval that falls **after** *warmup_end* is
        counted — warm-up periods are discarded from the area integrals.
        """
        now = at if at is not None else self.env.now
        dt = now - self._last_t
        if dt <= 0:
            return

        q = len(self.servers.queue)           # number waiting
        b = self.servers.count                # number in service

        # Split the interval at warmup_end if it falls in the middle
        if self._warmup_end > self._last_t and self._warmup_end < now:
            post_dt = now - self._warmup_end
            self._queue_area += q * post_dt
            self._busy_area  += b * post_dt
        elif self._last_t >= self._warmup_end:
            # Entirely within the post-warmup region
            self._queue_area += q * dt
            self._busy_area  += b * dt
        # else: entirely within warmup — discard

        self._last_t = now

    def record(self) -> None:
        """Call this at every state-change point."""
        self._snapshot()

    def finalize(self, end_time: float) -> tuple[float, float]:
        """Flush remaining area exactly up to end_time and return (Lq, busy_fraction).

        Uses the *post-warmup* period as the averaging denominator.
        """
        self._snapshot(at=end_time)
        effective_start = max(0.0, self._warmup_end)
        duration = end_time - effective_start
        if duration <= 0:
            return 0.0, 0.0
        lq = self._queue_area / duration
        busy_fraction = self._busy_area / (duration * max(self.servers.capacity, 1))
        return lq, busy_fraction


def _customer_process(
    env: simpy.Environment,
    servers: simpy.Resource,
    mu: float,
    result: SegmentResult,
    monitor: _QueueMonitor,
    rng: random.Random,
    warmup_end: float = 0.0,
):
    """SimPy generator: one customer enters queue, waits for a server, gets served."""
    arrival = env.now
    monitor.record()

    with servers.request() as req:
        # Update queue depth tracking before and after acquiring server
        q_depth = len(servers.queue)
        if q_depth > result.max_queue:
            result.max_queue = q_depth

        yield req
        monitor.record()

        service_start = env.now
        wait = service_start - arrival

        # Only record post-warmup customers (service start >= warmup_end)
        if service_start >= warmup_end:
            result._wait_sum += wait
            result.served += 1

        service_time = _exponential(mu, rng)
        yield env.timeout(service_time)
        monitor.record()

        # result.served used to be incremented unconditionally here; moved above


def _arrival_process(
    env: simpy.Environment,
    servers: simpy.Resource,
    lambda_: float,
    mu: float,
    sim_duration: float,
    result: SegmentResult,
    monitor: _QueueMonitor,
    rng: random.Random,
    warmup_end: float = 0.0,
):
    """SimPy generator: generates arrivals for the duration of one segment."""
    while True:
        iat = _exponential(lambda_, rng)
        # Peek ahead: if next arrival falls outside the window, stop
        if env.now + iat >= sim_duration:
            break
        yield env.timeout(iat)

        env.process(
            _customer_process(env, servers, mu, result, monitor, rng, warmup_end)
        )


# ──────────────────────────────────────────────────────────────────────────────
# Public API — single-segment simulation
# ──────────────────────────────────────────────────────────────────────────────

def simulate_segment(
    segment: Mapping[str, Any],
    sim_hours: float = SIM_HOURS_PER_SEGMENT,
    queue_overload_threshold: int = DEFAULT_QUEUE_OVERLOAD,
    seed: int | None = RANDOM_SEED,
    warmup_fraction: float = 0.2,
    initial_queue_depth: int = 0,
) -> SegmentResult:
    """
    Run a discrete-event simulation for one time segment.

    Parameters
    ----------
    segment : Mapping
        Must contain 'lambda', 'mu', and optionally 'c' (default 1) and 'time'.
    sim_hours : float
        Duration of the simulated interval in hours (default 1.0 per segment).
    queue_overload_threshold : int
        Queue depth that triggers OVERLOADED status regardless of utilization.
    seed : int or None
        Random seed for reproducibility.  Pass None for true stochasticity.
    warmup_fraction : float
        Fraction of *sim_hours* to discard as warm-up (default 0.2, range 0.0–0.5).
        Set to 0.0 to disable warm-up deletion (identical to legacy behaviour).
    initial_queue_depth : int
        Number of customers already in queue when simulation starts (default 0).
        These customers have *arrival_time* = 0 and are subject to warm-up filtering.

    Returns
    -------
    SegmentResult
        Empirical metrics for the interval.  When *warmup_fraction* > 0,
        time-averaged metrics (Lq, rho) and waiting-time statistics only
        reflect the post-warmup portion of the simulation.
    """
    time_label = str(segment.get("time", "Unknown"))
    result = SegmentResult(time=time_label, lambda_=0.0, mu=0.0, c=1)

    error, lambda_, mu, c = _validate_segment(segment)
    result.selected_model, coverage_error = simulation_coverage(segment)
    result.simulation_supported = coverage_error is None
    error = error or coverage_error
    result.lambda_ = lambda_ or 0.0
    result.mu = mu or 0.0
    result.c = c

    logger.info(
        "simulate_segment(time=%s, lambda_=%.4g, mu=%.4g, c=%d, sim_hours=%.4g, warmup=%.2f)",
        time_label, lambda_ or 0, mu or 0, c, sim_hours, warmup_fraction,
    )

    # Clamp and record warm-up parameters
    warmup_fraction = max(0.0, min(0.5, warmup_fraction))
    result.warmup_fraction = warmup_fraction
    result.requested_sim_hours = sim_hours
    result.effective_sim_hours = sim_hours
    result.measurement_hours = sim_hours

    if error:
        result.error = error
        result.status = "ERROR"
        return result

    assert lambda_ is not None and mu is not None

    # Zero-arrival edge case: no queue, servers idle
    if lambda_ == 0 and initial_queue_depth == 0:
        result.rho_sim = 0.0
        result.Lq_sim = 0.0
        result.Wq_sim = 0.0
        result.status = "NORMAL"
        return result

    rng = random.Random(seed)
    sim_duration = sim_hours  # environment time unit = hours
    # Adaptive warm-up: ensure at least 30 expected arrivals before measurement begins
    if lambda_ and lambda_ > 0:
        arrivals_based_warmup = 30.0 / lambda_
        warmup_end = min(
            max(sim_duration * warmup_fraction, arrivals_based_warmup),
            sim_duration * 0.5,
        )
    else:
        warmup_end = sim_duration * warmup_fraction
    result.warmup_end = warmup_end
    result.measurement_hours = sim_duration - warmup_end

    env = simpy.Environment()
    servers = simpy.Resource(env, capacity=c)
    monitor = _QueueMonitor(env, servers, warmup_end=warmup_end)

    # Inject initial queue depth (customers already waiting at t=0)
    initial_queue_depth = max(0, int(initial_queue_depth))
    result.initial_queue_depth = initial_queue_depth
    if initial_queue_depth > 0:
        for _ in range(initial_queue_depth):
            env.process(
                _customer_process(env, servers, mu, result, monitor, rng, warmup_end)
            )

    env.process(
        _arrival_process(env, servers, lambda_, mu, sim_duration, result, monitor, rng, warmup_end)
    )
    env.run(until=sim_duration)

    # Record final queue depth (for carryover to next segment)
    result.final_Lq = len(servers.queue)

    # Finalize time-averaged metrics at the true segment boundary
    lq_avg, rho_emp = monitor.finalize(sim_duration)
    result.rho_sim = round(rho_emp, 6)
    result.Lq_sim = round(lq_avg, 6)

    # Sample mean for service starts after warmup; disclose the Little's Law
    # fallback when no sampled customer starts service.
    if result.served > 0:
        result.Wq_sim = round(result._wait_sum / result.served, 6)
    elif lambda_ > 0:
        result.Wq_sim = round(lq_avg / lambda_, 6)
    else:
        result.Wq_sim = 0.0

    result.status = _classify_status(rho_emp, result.max_queue, queue_overload_threshold)

    logger.info(
        "simulate_segment done: status=%s rho_sim=%.4g Lq_sim=%.4g Wq_sim=%.4g served=%d",
        result.status, result.rho_sim, result.Lq_sim, result.Wq_sim, result.served,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public API — multi-segment simulation
# ──────────────────────────────────────────────────────────────────────────────

def simulate_segments(
    time_segments: Iterable[Mapping[str, Any]] | None,
    sim_hours: float = SIM_HOURS_PER_SEGMENT,
    queue_overload_threshold: int = DEFAULT_QUEUE_OVERLOAD,
    seed: int | None = RANDOM_SEED,
    carryover: bool = True,
) -> list[dict[str, Any]]:
    """
    Simulate a sequence of time segments and return a list of result dicts.

    By default (*carryover* = True) the final queue depth of segment *i* is
    passed as the initial queue depth of segment *i* + 1, giving a more
    realistic picture across consecutive time windows.  Set *carryover* =
    False to simulate each segment independently (empty queue at start of
    every segment — legacy behaviour).

    The seed is incremented per segment so results are reproducible
    but statistically independent.

    Parameters
    ----------
    time_segments : Iterable[Mapping]
        Sequence of segment dicts (keys: time, lambda, mu, c).
    sim_hours : float
        Simulated hours per segment.
    queue_overload_threshold : int
        Queue depth that forces OVERLOADED status.
    seed : int or None
        Base random seed.  Segments use seed, seed+1, seed+2, … when not None.
    carryover : bool
        If True (default), carry final queue depth from segment *i* to segment
        *i* + 1.  If False, each segment starts with an empty queue.

    Returns
    -------
    list[dict]
        One dict per segment, matching SegmentResult.to_dict() schema.
    """
    if time_segments is None:
        return []

    results = []
    carry = 0  # initial queue depth for the first segment
    for i, seg in enumerate(time_segments):
        seg_seed = (seed + i) if seed is not None else None
        res = simulate_segment(
            segment=seg,
            sim_hours=sim_hours,
            queue_overload_threshold=queue_overload_threshold,
            seed=seg_seed,
            initial_queue_depth=carry,
        )
        results.append(res.to_dict())

        if carryover:
            carry = int(round(results[-1].get("final_Lq", 0)))
        else:
            carry = 0

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Public API — summary KPIs across all segments
# ──────────────────────────────────────────────────────────────────────────────

def summarize_simulation(sim_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute dashboard-level KPIs from a list of simulate_segments() outputs.

    Returns
    -------
    dict
        avg_rho, max_rho, max_rho_time, avg_Lq, avg_Wq,
        total_served, total_dropped,
        overloaded_count, busy_count, normal_count,
        avg_max_queue
    """
    if not sim_rows:
        return {
            "avg_rho": None,
            "max_rho": None,
            "max_rho_time": None,
            "avg_Lq": None,
            "avg_Wq": None,
            "total_served": 0,
            "total_dropped": 0,
            "overloaded_count": 0,
            "busy_count": 0,
            "normal_count": 0,
            "avg_max_queue": None,
        }

    valid = [r for r in sim_rows if r.get("rho_sim") is not None]

    if not valid:
        return {
            "avg_rho": None,
            "max_rho": None,
            "max_rho_time": None,
            "avg_Lq": None,
            "avg_Wq": None,
            "total_served": sum(r.get("served", 0) for r in sim_rows),
            "total_dropped": sum(r.get("dropped", 0) for r in sim_rows),
            "critical_count": sum(1 for r in sim_rows if r.get("status") == "Critical"),
            "peak_count": sum(1 for r in sim_rows if r.get("status") == "Peak"),
            "normal_count": sum(1 for r in sim_rows if r.get("status") == "Normal"),
            "lean_count": sum(1 for r in sim_rows if r.get("status") == "Lean"),
            "avg_max_queue": None,
        }

    # Mirror compute_kpis() on Page 1 & 2: exclude unstable segments (λ >= c·μ)
    # from avg_rho and avg_Wq so the simulation KPIs match the analytical tab,
    # which only averages stable segments.
    stable_for_avg = [
        r for r in valid
        if (r.get("lambda") or 0) < (r.get("c", 1) * r.get("mu", 1))
    ] or valid  # fallback to all rows if somehow all are unstable

    rho_vals = [r["rho_sim"] for r in valid]
    lq_vals  = [r["Lq_sim"]  for r in stable_for_avg if r.get("Lq_sim") is not None]
    wq_vals  = [r["Wq_sim"]  for r in stable_for_avg if r.get("Wq_sim") is not None]
    mq_vals  = [r["max_queue"] for r in valid]

    max_rho_row = max(valid, key=lambda r: r["rho_sim"])

    avg_rho = sum(r["rho_sim"] for r in stable_for_avg) / len(stable_for_avg)

    return {
        "avg_rho": avg_rho,
        "max_rho": max(rho_vals),
        "max_rho_time": max_rho_row["time"],
        "avg_Lq": sum(lq_vals) / len(lq_vals) if lq_vals else None,
        "avg_Wq": sum(wq_vals) / len(wq_vals) if wq_vals else None,
        "total_served": sum(r.get("served", 0) for r in sim_rows),
        "total_dropped": sum(r.get("dropped", 0) for r in sim_rows),
        "critical_count": sum(1 for r in sim_rows if r.get("status") == "Critical"),
        "peak_count": sum(1 for r in sim_rows if r.get("status") == "Peak"),
        "normal_count": sum(1 for r in sim_rows if r.get("status") == "Normal"),
        "lean_count": sum(1 for r in sim_rows if r.get("status") == "Lean"),
        "avg_max_queue": sum(mq_vals) / len(mq_vals) if mq_vals else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public API — Monte Carlo simulation
# ──────────────────────────────────────────────────────────────────────────────

from backend.queueing_engine.config import (
    MC_ARRIVAL_NOISE,
    MC_CONFIDENCE_LEVEL,
    MC_DEFAULT_FAILURE_THRESHOLD,
    MC_DEFAULT_TRIALS,
    MC_FAILURE_RATE_CAP,
    MC_MAX_TRIALS,
    MC_SERVICE_NOISE,
)


def mc_simulate_segment(
    segment: Mapping[str, Any],
    num_trials: int = MC_DEFAULT_TRIALS,
    failure_threshold: float = MC_DEFAULT_FAILURE_THRESHOLD,
    seed: int | None = 42,
    failure_rate_cap: float = MC_FAILURE_RATE_CAP,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation for one time segment.

    Perturbs arrival rate by ±20% and service rate by ±10% across *num_trials*
    independent analytical evaluations.  Returns distributional statistics.

    Parameters
    ----------
    segment : Mapping
        Must contain 'lambda', 'mu', and optionally 'c' (default 1) and 'time'.
    num_trials : int
        Number of Monte Carlo replications.
    failure_threshold : float
        Utilization above this counts as a "failure".
    seed : int or None
        Random seed for reproducibility.

    Returns
    -------
    dict
        time, lambda, mu, c, rho_mean, rho_std, rho_p95, Lq_mean, Wq_mean,
        failure_rate, failure_rate_ci_lower, failure_rate_ci_upper,
        failure_rate_ci_half_width, failure_rate_precision,
        failure_rate_adequate, status
    """
    metadata = {"metric_provenance": "monte_carlo", "method": "analytical_parameter_perturbation",
                "wait_time_unit": "hours", "num_trials": num_trials, "failure_criterion": "utilization_exceeds_threshold",
                "failure_threshold": failure_threshold, "failure_rate_cap": failure_rate_cap,
                "confidence_level": MC_CONFIDENCE_LEVEL,
                "arrival_noise_fraction": MC_ARRIVAL_NOISE, "service_noise_fraction": MC_SERVICE_NOISE,
                "noise_distribution": "independent_uniform", "assumption_basis": "configured sensitivity assumptions"}
    time_label = str(segment.get("time", "Unknown"))
    error, lambda_, mu, c = _validate_segment(segment)

    selected_model, coverage_error = simulation_coverage(segment)
    error = error or coverage_error
    if error:
        logger.warning("mc_simulate_segment(time=%s) validation error: %s", time_label, error)
        return {
            **metadata, "failure_count": None, "trials_completed": 0,
            "time": time_label, "lambda": lambda_, "mu": mu, "c": c,
            "rho_mean": None, "rho_std": None, "rho_p95": None,
            "Lq_mean": None, "Wq_mean": None,
            "failure_rate": None, "status": "ERROR",
            "selected_model": selected_model, "simulation_supported": False,
            "error": error,
            "ci_Wq_hw": None, "ci_Lq_hw": None, "adequate_samples": False,
            "failure_rate_ci_lower": None, "failure_rate_ci_upper": None,
            "failure_rate_ci_half_width": None,
            "failure_rate_precision": None, "failure_rate_adequate": False,
        }

    assert lambda_ is not None and mu is not None

    logger.info("mc_simulate_segment(time=%s, lambda_=%.4g, mu=%.4g, c=%d, trials=%d)", time_label, lambda_, mu, c, num_trials)
    rng = np.random.default_rng(seed)

    def _pick_model(lam: float, m: float, c_: int) -> dict[str, Any]:
        return mmc(lam, m, c_) if c_ > 1 else mm1(lam, m)

    rho_samples = np.empty(num_trials)
    lq_samples = np.empty(num_trials)
    wq_samples = np.empty(num_trials)
    failures = 0

    for i in range(num_trials):
        arrival_factor = 1.0 + rng.uniform(-MC_ARRIVAL_NOISE, MC_ARRIVAL_NOISE)
        service_factor = 1.0 + rng.uniform(-MC_SERVICE_NOISE, MC_SERVICE_NOISE)
        lam = lambda_ * arrival_factor
        m = mu * service_factor
        result = _pick_model(lam, m, c)

        if result.get("stable"):
            rho = result["rho"]
            lq_samples[i] = result["Lq"]
            wq_samples[i] = result["Wq"]
        else:
            rho = lam / (c * m) if (c * m) > 0 else float("inf")
            lq_samples[i] = float("inf")
            wq_samples[i] = float("inf")

        rho_samples[i] = rho
        if rho > failure_threshold:
            failures += 1

    finite = np.isfinite(rho_samples)
    finite_lq = np.isfinite(lq_samples)
    finite_wq = np.isfinite(wq_samples)
    n_finite_wq = int(np.sum(finite_wq))
    n_finite_lq = int(np.sum(finite_lq))
    failure_rate = failures / num_trials

    # 95 % CI half-widths (using normal approximation)
    if n_finite_wq > 1:
        std_wq = float(np.std(wq_samples[finite_wq], ddof=1))
        mean_wq = float(np.mean(wq_samples[finite_wq]))
        ci_Wq_hw = round(1.96 * std_wq / math.sqrt(n_finite_wq), 6)
        adequate_samples = bool(mean_wq > 0 and (ci_Wq_hw / mean_wq) < 0.10)
    else:
        ci_Wq_hw = None
        adequate_samples = False

    if n_finite_lq > 1:
        std_lq = float(np.std(lq_samples[finite_lq], ddof=1))
        ci_Lq_hw = round(1.96 * std_lq / math.sqrt(n_finite_lq), 6)
    else:
        ci_Lq_hw = None

    # 95 % Wilson confidence interval on the failure-rate proportion.
    fr_ci_lower, fr_ci_upper, fr_ci_hw = wilson_ci(failures, num_trials)
    if fr_ci_lower is None or fr_ci_upper is None or fr_ci_hw is None:
        fr_ci_lower = fr_ci_upper = fr_ci_hw = None
        failure_rate_precision_level: str | None = None
        failure_rate_adequate = False
    else:
        failure_rate_precision_level = failure_rate_precision(fr_ci_hw)
        failure_rate_adequate = bool(fr_ci_hw <= ADEQUATE_MAX_HW)

    return {
        **metadata,
        "time": time_label,
        "lambda": lambda_,
        "mu": mu,
        "c": c,
        "rho_mean": round(float(np.mean(rho_samples[finite])), 6) if finite.any() else None,
        "rho_std": round(float(np.std(rho_samples[finite])), 6) if finite.any() else None,
        "rho_p95": round(float(np.percentile(rho_samples[finite], 95)), 6) if finite.any() else None,
        "Lq_mean": round(float(np.mean(lq_samples[finite_lq])), 6) if finite_lq.any() else None,
        "Wq_mean": round(float(np.mean(wq_samples[finite_wq])), 6) if finite_wq.any() else None,
        "failure_rate": round(failure_rate, 4),
        "failure_count": int(failures),
        "trials_completed": num_trials,
        "status": "PASS" if failure_rate <= failure_rate_cap else "FAIL",
        "error": None,
        "selected_model": selected_model, "simulation_supported": True,
        "ci_Wq_hw": ci_Wq_hw,
        "ci_Lq_hw": ci_Lq_hw,
        "adequate_samples": adequate_samples,
        "failure_rate_ci_lower": round(fr_ci_lower, 4) if fr_ci_lower is not None else None,
        "failure_rate_ci_upper": round(fr_ci_upper, 4) if fr_ci_upper is not None else None,
        "failure_rate_ci_half_width": round(fr_ci_hw, 4) if fr_ci_hw is not None else None,
        "failure_rate_precision": failure_rate_precision_level,
        "failure_rate_adequate": failure_rate_adequate,
    }


def mc_simulate_segments(
    time_segments: Iterable[Mapping[str, Any]] | None,
    num_trials: int = MC_DEFAULT_TRIALS,
    failure_threshold: float = MC_DEFAULT_FAILURE_THRESHOLD,
    seed: int | None = 42,
    failure_rate_cap: float = MC_FAILURE_RATE_CAP,
) -> list[dict[str, Any]]:
    """
    Run Monte Carlo simulation across a sequence of time segments.

    The seed is incremented per segment for reproducible but independent trials.
    """
    if time_segments is None:
        return []

    results = []
    for i, seg in enumerate(time_segments):
        seg_seed = (seed + i) if seed is not None else None
        results.append(
            mc_simulate_segment(seg, num_trials, failure_threshold, seg_seed, failure_rate_cap)
        )
    return results


def mc_summarize_simulation(mc_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute dashboard-level KPIs from mc_simulate_segments() output.

    Returns
    -------
    dict
        avg_rho, avg_rho_std, max_rho_mean, max_rho_time,
        avg_failure_rate, total_failures, segments_failed, segments_total,
        avg_Lq, avg_Wq
    """
    if not mc_rows:
        return {
            "avg_rho": None, "avg_rho_std": None,
            "max_rho_mean": None, "max_rho_time": None,
            "avg_failure_rate": None, "total_failures": 0,
            "segments_failed": 0, "segments_total": 0,
            "avg_Lq": None, "avg_Wq": None,
            "n_adequate": 0, "n_inadequate": 0,
        }

    valid = [r for r in mc_rows if r.get("rho_mean") is not None]
    if not valid:
        return {
            "avg_rho": None, "avg_rho_std": None,
            "max_rho_mean": None, "max_rho_time": None,
            "avg_failure_rate": None,
            "total_failures": sum((r.get("failure_count") or 0) for r in mc_rows),
            "segments_failed": sum(1 for r in mc_rows if r.get("status") == "FAIL"),
            "segments_total": len(mc_rows),
            "avg_Lq": None, "avg_Wq": None,
            "n_adequate": 0, "n_inadequate": len(mc_rows),
        }

    rho_vals = np.array([r["rho_mean"] for r in valid])
    max_row = max(valid, key=lambda r: r["rho_mean"])

    n_adequate = sum(1 for r in mc_rows if r.get("adequate_samples"))
    n_inadequate = len(mc_rows) - n_adequate

    return {
        "avg_rho": round(float(np.mean(rho_vals)), 6),
        "avg_rho_std": round(float(np.mean([r["rho_std"] for r in valid if r.get("rho_std") is not None])), 6),
        "max_rho_mean": round(float(np.max(rho_vals)), 6),
        "max_rho_time": max_row["time"],
        "avg_failure_rate": round(float(np.mean([r["failure_rate"] for r in valid if r.get("failure_rate") is not None])), 4),
        "total_failures": sum((r.get("failure_count") or 0) for r in mc_rows),
        "segments_failed": sum(1 for r in mc_rows if r.get("status") == "FAIL"),
        "segments_total": len(mc_rows),
        "avg_Lq": round(float(np.nanmean([r["Lq_mean"] for r in valid if r.get("Lq_mean") is not None])), 6),
        "avg_Wq": round(float(np.nanmean([r["Wq_mean"] for r in valid if r.get("Wq_mean") is not None])), 6),
        "n_adequate": n_adequate,
        "n_inadequate": n_inadequate,
    }


def validate_with_simulation(
    comparison_df: pd.DataFrame,
    des_sim_hours: float = SIM_HOURS_PER_SEGMENT,
    mc_trials: int = MC_DEFAULT_TRIALS,
    mc_failure_threshold: float = MC_DEFAULT_FAILURE_THRESHOLD,
    seed: int | None = 42,
    failure_rate_cap: float = MC_FAILURE_RATE_CAP,
) -> pd.DataFrame:
    """Run DES + Monte Carlo on the optimized plan and merge validation columns.

    For each segment in *comparison_df* with a valid ``c_optimal``, a DES
    simulation and a Monte Carlo run (default 2 000 trials) are executed.  The
    following columns are appended (NaN for segments where the optimizer found
    no stable plan):

    - sim_status, sim_max_queue, sim_Wq, sim_rho        (DES)
    - mc_failure_rate, mc_adequate, mc_rho_mean,        (MC)
      mc_rho_p95, mc_Wq_ci, mc_failure_rate_ci_lower,
      mc_failure_rate_ci_upper, mc_failure_rate_ci_half_width,
      mc_failure_rate_precision, mc_failure_rate_adequate
    """
    if comparison_df is None or comparison_df.empty:
        return comparison_df

    comparison_df = comparison_df.drop(columns=["selected_model", "simulation_supported"], errors="ignore").copy().reset_index(drop=True)
    comparison_df["_validation_row"] = range(len(comparison_df))
    sim_records = []
    for index, row in comparison_df.iterrows():
        c_opt = row.get("c_optimal")
        if c_opt is None or pd.isna(c_opt):
            continue
        sim_records.append({
            "time": str(index),
            "lambda": row.get("lambda", row.get("lambda_")),
            "mu": row.get("mu"),
            "c": c_opt,
            **{key: row[key] for key in ("variance", "K", "theta") if key in row and pd.notna(row[key])},
        })

    if not sim_records:
        result = comparison_df.copy()
        for col in ["sim_status", "sim_max_queue", "sim_Wq", "sim_rho",
                     "mc_failure_rate", "mc_adequate", "mc_rho_mean",
                     "mc_rho_p95", "mc_Wq_ci", "mc_failure_rate_ci_lower",
                     "mc_failure_rate_ci_upper", "mc_failure_rate_ci_half_width",
                     "mc_failure_rate_precision", "mc_failure_rate_adequate"]:
            result[col] = None
        result["simulation_supported"] = False
        result["validation_reason"] = "No feasible optimized staffing to validate."
        return result.drop(columns=["_validation_row"])

    des_results = simulate_segments(sim_records, sim_hours=des_sim_hours, seed=seed)
    des_df = pd.DataFrame(des_results)[
        ["time", "rho_sim", "Wq_sim", "max_queue", "status", "selected_model", "simulation_supported", "error", "requested_sim_hours", "effective_sim_hours", "measurement_hours", "warmup_end"]
    ].rename(
        columns={
            "rho_sim": "sim_rho",
            "Wq_sim": "sim_Wq",
            "max_queue": "sim_max_queue",
            "status": "sim_status",
            "error": "validation_reason",
        }
    )

    mc_results = mc_simulate_segments(
        sim_records, num_trials=mc_trials,
        failure_threshold=mc_failure_threshold, seed=seed,
        failure_rate_cap=failure_rate_cap,
    )
    mc_metadata = pd.DataFrame(mc_results)[["num_trials", "failure_count", "failure_criterion", "failure_threshold", "failure_rate_cap", "confidence_level", "method", "arrival_noise_fraction", "service_noise_fraction"]].add_prefix("mc_")
    mc_raw = pd.DataFrame(mc_results)[
        ["time", "failure_rate", "adequate_samples",
         "rho_mean", "rho_p95", "Wq_mean", "ci_Wq_hw",
         "failure_rate_ci_lower", "failure_rate_ci_upper",
         "failure_rate_ci_half_width", "failure_rate_precision",
         "failure_rate_adequate"]
    ].rename(
        columns={
            "failure_rate": "mc_failure_rate",
            "adequate_samples": "mc_adequate",
            "rho_mean": "mc_rho_mean",
            "rho_p95": "mc_rho_p95",
            "failure_rate_ci_lower": "mc_failure_rate_ci_lower",
            "failure_rate_ci_upper": "mc_failure_rate_ci_upper",
            "failure_rate_ci_half_width": "mc_failure_rate_ci_half_width",
            "failure_rate_precision": "mc_failure_rate_precision",
            "failure_rate_adequate": "mc_failure_rate_adequate",
        }
    )
    mc_raw = pd.concat([mc_raw, mc_metadata], axis=1)
    mc_raw["mc_Wq_ci"] = mc_raw.apply(
        lambda r: (
            f"{r['Wq_mean'] * 60:.2f} ± {r['ci_Wq_hw'] * 60:.2f} min (95% CI)"
            if pd.notna(r.get("Wq_mean")) and pd.notna(r.get("ci_Wq_hw"))
            else "N/A"
        ),
        axis=1,
    )
    mc_raw.drop(columns=["Wq_mean", "ci_Wq_hw"], inplace=True)

    for frame in (des_df, mc_raw):
        frame["_validation_row"] = frame.pop("time").astype(int)
    result = comparison_df.merge(des_df, on="_validation_row", how="left").merge(mc_raw, on="_validation_row", how="left")
    result["simulation_supported"] = result["simulation_supported"].fillna(False).astype(bool)
    result.loc[result["c_optimal"].isna(), "validation_reason"] = "No feasible optimized staffing to validate."
    return result.drop(columns=["_validation_row"])



