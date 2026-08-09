# Phase 2.5 — Correctness Workstream Implementation Plan (2026-08-09)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six proven behavioral defects in the queueing engine (ternary search, waste-hours savings, cost engines, dispatch precedence, MC thresholds, summarize keys) with TDD regression tests, isolated per item.

**Architecture:** One task per defect. Each task: prove → failing regression test → minimal fix → relevant tests → full suite → E2E → commit. No refactors, no formula changes beyond the proven defect.

**Tech Stack:** Python 3.10-3.13, pytest/unittest, ruff, mypy, Streamlit AppTest.

## Global Constraints

- No Phase 3 work: no FastAPI routers, no PostgreSQL, no React, no auth changes.
- Do not change unrelated code; each change isolated and reviewable.
- If expected behavior cannot be established confidently for an item, STOP and report the ambiguity (do not guess).
- Per item after correction: run the new regression test, the full `python -m pytest tests/ -x --tb=short` suite, and Streamlit E2E `tests/test_dashboard_e2e.py`.
- After every item: `python -m ruff check .` and `python -m mypy .` clean; commit per item.
- Suite baseline: 146 tests + 15 E2E, all green.

---

## Research findings (established during planning)

| Item | Defect location | Proven behavior |
|---|---|---|
| 1 | `_ternary_search_c` both-inf branch | `optimize_segment({"lambda":30,"mu":1,"c":1}, max_servers=40)` → `c_optimal=None` ("Unable to find a stable staffing plan.") although c=31..40 are stable. Both-inf branch `lo=m1; hi=m2` collapses the window and discards the feasible tail. |
| 2 | Waste-hours branch in `optimize_segment` | λ=2, μ=5, c=2, waiting cost 2000 → recommends "Remove 1 server … save ₱-413.00" and sets `c_optimal=1` even though removing a server RAISES total cost. No savings>0 guard. |
| 3 | `compute_segment_costs` unstable branch | Unstable rows: `compute_segment_costs` sets abandonment=0; `compute_all_costs` and optimization engine charge λ×rate×cost (tests `test_costing.py:155-171` and `test_costing_matches_optimization_for_unstable_segment` agree with the latter). Documented intent (AGENTS.md 2026-08-09): unstable rows still get server+abandonment costs. |
| 4 | `_queue_metrics` precedence | Page 1 `process_segments` and API `_auto_select_model`: theta (Erlang-A) has TOP priority and gate `theta > 0`. `_queue_metrics`: theta checked LAST (after K/variance) and gate is `_is_number` (accepts theta=0/negative). Divergent dispatch for theta+variance / theta+K segments. |
| 5 | `validate_with_simulation` default | `MC_DEFAULT_FAILURE_THRESHOLD = 0.75` (simulation.py:593) is the engine default and Page 3 UI default (pages/3:236). `validate_with_simulation(mc_failure_threshold: float = 0.85)` (simulation.py:797) hardcodes 0.85 — Page 2 validation uses 0.85. |
| 6 | `summarize_optimization` empty branch | Normal branch returns 13 keys incl. `total_waiting_cost_current/optimal`, `total_abandonment_cost_current/optimal`; empty branch (optimization.py:407-419) omits those 4 keys. `mc_summarize_simulation` (simulation.py) branches are consistent — this item is `summarize_optimization`. |

---

### Task 1: Ternary-search feasible-region bug

**Files:**
- Modify: `backend/queueing_engine/services/optimization.py:114-165` (`_ternary_search_c`)
- Test: `tests/test_optimization.py`

- [ ] **Step 1: Write the failing regression tests**

In `tests/test_optimization.py`, after `test_ternary_search_all_inf`:

```python
def test_ternary_search_feasible_region_beyond_inf_band(self):
    def fn(c):
        return float("inf") if c < 31 else float(c)

    result = _ternary_search_c(fn, 1, 40)
    self.assertEqual(result, 31)

def test_optimize_segment_finds_stable_plan_above_inf_band(self):
    result = optimize_segment(
        {"time": "t", "lambda": 30, "mu": 1, "c": 1},
        max_servers=40,
    )
    self.assertIsNotNone(result["c_optimal"])
    self.assertEqual(result["c_optimal"], 31)
```

- [ ] **Step 2: Run and confirm both FAIL** (current code returns None)

Run: `python -m pytest tests/test_optimization.py -x --tb=short`

- [ ] **Step 3: Fix `_ternary_search_c`** — two-phase: binary search the leftmost feasible c, then ternary over the feasible window (stability is monotone in c, so feasible c form a suffix [c_min, hi]):

```python
def _ternary_search_c(eval_fn, lo, hi):
    """
    Ternary search for the integer c ∈ [*lo*, *hi*] that minimises *eval_fn*(c).

    *eval_fn*(c) must return a finite ``float`` for stable server counts and
    ``float('inf')`` for unstable ones.  The function is assumed unimodal
    (convex) in *c*.

    Parameters
    ----------
    eval_fn : Callable[[int], float]
        Total cost as a function of server count.
    lo, hi : int
        Inclusive search bounds (``lo <= hi``).

    Returns
    -------
    int or None
        The integer *c* with minimum *eval_fn*(c), or ``None`` if all
        candidates are unstable (eval returns inf).
    """
    if lo > hi:
        return None

    # No feasible (stable) candidate in range
    if eval_fn(hi) == float("inf"):
        return None

    # Binary search the leftmost feasible c. Stability is monotone in c, so
    # the feasible set is the suffix [first_feasible, hi].
    first_feasible = hi
    left, right = lo, hi
    while left < right:
        mid = (left + right) // 2
        if eval_fn(mid) == float("inf"):
            left = mid + 1
        else:
            right = mid
    lo = left

    # Shrink by thirds until the window is tiny
    while hi - lo > 2:
        m1 = lo + (hi - lo) // 3
        m2 = hi - (hi - lo) // 3

        f1 = eval_fn(m1)
        f2 = eval_fn(m2)

        if f1 < f2:
            hi = m2
        else:
            lo = m1

    # Brute-force the remaining window
    best_c = None
    best_val = float("inf")

    for c in range(lo, hi + 1):
        val = eval_fn(c)
        if val < best_val:
            best_val = val
            best_c = c

    return best_c if best_val != float("inf") else None
```

- [ ] **Step 4: Run new tests + optimization suite** — `python -m pytest tests/test_optimization.py -x --tb=short`
- [ ] **Step 5: Full battery + E2E + ruff + mypy** — `python -m pytest tests/ -x --tb=short`, `python -m pytest tests/test_dashboard_e2e.py -x --tb=short`, `python -m ruff check .`, `python -m mypy .`
- [ ] **Step 6: Commit** — `git add -A; git commit -m "fix: ternary search finds feasible region beyond unstable band (Phase 2.5 item 1)"`

---

### Task 2: Waste-hours negative-savings bug

**Files:**
- Modify: `backend/queueing_engine/services/optimization.py:343-375` (waste branch in `optimize_segment`)
- Test: `tests/test_optimization.py`

- [ ] **Step 1: Write the failing regression tests**

```python
def test_waste_reduction_skipped_when_savings_negative(self):
    result = optimize_segment(
        {"time": "t", "lambda": 2, "mu": 5, "c": 2},
        max_servers=5,
        default_server_cost=87.0,
        customer_waiting_cost=2000.0,
    )
    self.assertEqual(result["c_optimal"], 2)
    self.assertNotIn("Remove 1 server", result["recommendation"])

def test_waste_reduction_applies_when_savings_positive(self):
    result = optimize_segment(
        {"time": "t", "lambda": 2, "mu": 5, "c": 2},
        max_servers=5,
        default_server_cost=87.0,
        customer_waiting_cost=100.0,
    )
    self.assertEqual(result["c_optimal"], 1)
    self.assertIn("Remove 1 server", result["recommendation"])
    self.assertIn("save", result["recommendation"])
```

- [ ] **Step 2: Run and confirm the first FAILS, second PASSES** (current code always adopts the removal and reports negative "savings")
- [ ] **Step 3: Fix** — in the waste branch (optimization.py:343-367), compute `savings` first and only adopt `waste_recommendation` when `savings > 0`; keep the rest of the branch (including final_optimal_* overrides) inside the guard.
- [ ] **Step 4-5: Run relevant + full battery + E2E + ruff + mypy**
- [ ] **Step 6: Commit** — `git commit -m "fix: waste-hours removal only when savings positive (Phase 2.5 item 2)"`

---

### Task 3: Divergent cost engines (unstable abandonment)

**Files:**
- Modify: `backend/queueing_engine/services/costing.py:89-94` (`compute_segment_costs`)
- Test: `tests/test_costing.py` (update 2 assertions at lines 131-153; add regression test)

- [ ] **Step 1: Add failing regression test (divergence proof)**

```python
def test_segment_costs_unstable_row_charges_abandonment_like_all_costs(self):
    costs = compute_segment_costs(
        servers=2,
        arrival_rate=10,
        wq=float("nan"),
        cost_per_server_hr=87,
        cost_per_wait_hr=100,
        cost_per_abandonment=60,
        abandonment_rate=0.1,
        hours_per_interval=1,
    )
    self.assertEqual(costs["wait_cost"], UNSTABLE_FIXED_COST)
    self.assertAlmostEqual(costs["abandonment_cost"], 60.0)
    self.assertAlmostEqual(costs["total_cost"], 174.0 + UNSTABLE_FIXED_COST + 60.0)
```

- [ ] **Step 2: Run and confirm FAILS** (`abandonment_cost` is 0.0 today) — also update the two existing assertions at `test_costing.py:141` and `:153` to `174.0 + UNSTABLE_FIXED_COST + 60.0` (they pin the divergent behavior; default abandonment_rate=0.1 × λ=10 × cost=60 = 60).
- [ ] **Step 3: Fix `compute_segment_costs`** — move `abandonment_cost` out of the else branch so unstable rows charge `arrival_rate * abandonment_rate * cost_per_abandonment` (matching `compute_all_costs` and the optimization engine).
- [ ] **Step 4-5: Relevant + full battery + E2E + ruff + mypy**
- [ ] **Step 6: Commit** — `git commit -m "fix: unify unstable-segment abandonment cost across cost engines (Phase 2.5 item 3)"`

---

### Task 4: Dispatch chains / theta precedence

**Files:**
- Modify: `backend/queueing_engine/services/optimization.py:69-81` (`_queue_metrics`)
- Test: `tests/test_optimization.py`

- [ ] **Step 1: Add failing regression tests**

```python
def test_queue_metrics_theta_precedes_variance(self):
    from backend.queueing_engine.services.optimization import _queue_metrics

    result = _queue_metrics(9, 10, 1, variance=0.1, theta=0.5)
    self.assertIn("theta", result)

def test_queue_metrics_theta_precedes_capacity(self):
    from backend.queueing_engine.services.optimization import _queue_metrics

    result = _queue_metrics(9, 10, 1, K=5, theta=0.5)
    self.assertIn("theta", result)

def test_queue_metrics_theta_zero_falls_through(self):
    from backend.queueing_engine.services.optimization import _queue_metrics

    result = _queue_metrics(2, 5, 1, variance=0.1, theta=0)
    self.assertNotIn("theta", result)
```

- [ ] **Step 2: Run and confirm FAIL** (today theta is checked last / `_is_number(0)` is True)
- [ ] **Step 3: Fix `_queue_metrics`** — theta first with gate `theta is not None and _is_number(theta) and float(theta) > 0` (matching `process_segments`/`_auto_select_model`); keep K+variance → mgck, K → mmck, variance → mgc, c==1 → mm1, else mmc.
- [ ] **Step 4-5: Relevant + full battery + E2E + ruff + mypy** (existing `test_optimize_segment_theta_uses_erlang_a` / `test_optimize_segment_theta_zero_falls_back_to_mm1` must stay green)
- [ ] **Step 6: Commit** — `git commit -m "fix: unify theta precedence across dispatch chains (Phase 2.5 item 4)"`

---

### Task 5: Divergent Monte Carlo failure thresholds

**Files:**
- Modify: `backend/queueing_engine/simulation/simulation.py:797` (`validate_with_simulation` default)
- Test: `tests/test_simulation.py`

- [ ] **Step 1: Add failing regression test**

```python
def test_validate_with_simulation_defaults_to_engine_failure_threshold(self):
    df = pd.DataFrame([
        {"time": "08:00", "lambda": 8.2, "mu": 10.0, "c_optimal": 1},
    ])
    result = validate_with_simulation(df, mc_trials=3000, seed=42)
    self.assertGreater(result.loc[0, "mc_failure_rate"], 0.5)
```

(ρ=0.82 with ±20% arrival / ±10% service noise: >75% of trials exceed 0.75; only ~40% exceed 0.85. Verify actual rates when running; if the gap is marginal, adjust λ to 8.4 and/or assert `> 0.4` after confirming old=~0.35 new=~0.6.)

- [ ] **Step 2: Run and confirm FAILS** (default 0.85 → rate < 0.5)
- [ ] **Step 3: Fix** — `mc_failure_threshold: float = MC_DEFAULT_FAILURE_THRESHOLD` (the 0.75 constant already used by `mc_simulate_segment(s)` and Page 3's UI default).
- [ ] **Step 4-5: Relevant + full battery + E2E + ruff + mypy**
- [ ] **Step 6: Commit** — `git commit -m "fix: validate_with_simulation uses engine MC failure threshold (Phase 2.5 item 5)"`

---

### Task 6: summarize_optimization empty-branch key mismatch

**Files:**
- Modify: `backend/queueing_engine/services/optimization.py:407-419` (empty branch of `summarize_optimization`)
- Test: `tests/test_optimization.py`

- [ ] **Step 1: Add failing regression test**

```python
def test_summarize_optimization_empty_branch_has_full_key_set(self):
    summary = summarize_optimization([])
    for key in [
        "total_waiting_cost_current",
        "total_waiting_cost_optimal",
        "total_abandonment_cost_current",
        "total_abandonment_cost_optimal",
    ]:
        self.assertIn(key, summary)
        self.assertEqual(summary[key], 0.0)
```

- [ ] **Step 2: Run and confirm FAILS**
- [ ] **Step 3: Fix** — add the 4 missing keys (0.0) to the empty-branch dict.
- [ ] **Step 4-5: Relevant + full battery + E2E + ruff + mypy**
- [ ] **Step 6: Commit** — `git commit -m "fix: summarize_optimization empty branch returns full key set (Phase 2.5 item 6)"`

---

### Task 7: Final report

- [ ] Re-run full battery: `python -m pytest tests/ -x --tb=short`, E2E, `python -m ruff check .`, `python -m mypy .`, `python test_imports.py`
- [ ] Per-item report: defect / failing test / expected behavior / correction / tests added / final result / behavior-changed flag
- [ ] Phase 2.5 exit assessment; STOP (no Phase 3)

## Risk register

| Risk | Mitigation |
|---|---|
| Existing tests pin divergent behavior (items 3, 5) | Update only the assertions that encode the defect; document each; add new regression tests proving the authoritative behavior |
| MC test flakiness from randomness | Seeded rng (seed=42); tuned segment whose rho separates 0.75 vs 0.85 cleanly; assert direction not exact rate |
| Ternary fix changes c_optimal for existing segments | Full suite + E2E verify; guard sweep retained for boundary non-convexity |
| Waste guard changes Page 2 recommendations | Existing E2E (`test_page2_no_false_validation_success_before_running`) + full suite cover page 2 flows |
