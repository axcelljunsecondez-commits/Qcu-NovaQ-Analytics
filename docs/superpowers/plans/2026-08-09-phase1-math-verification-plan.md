# Phase 1 — Mathematical Verification Plan (2026-08-09)

Spec: `docs/superpowers/specs/2026-08-09-novamart-production-architecture-design.md` (Phase 1 row, §12, risk 1)

## Project overview

Add analytical benchmark tests for the existing queueing engine (`queue_models.py`) proving M/M/1 and M/M/c results against independently known reference values, with the full edge-case matrix. **No queueing formula may change** unless a benchmark proves an actual error — this plan expects zero production-code changes.

## Architecture / tasks (diff-style)

| File | Action |
|---|---|
| `tests/analytical_benchmarks.py` | ADD — new benchmark suite (pytest style, `pytest.approx`) |
| `pyproject.toml` | MODIFY — `[tool.pytest.ini_options]` gains `python_files = ["test_*.py", "analytical_benchmarks.py"]` so pytest collects the spec-named file (default discovery only picks `test_*.py`) |
| `queue_models.py` | UNTOUCHED unless a benchmark proves an error (expected: no change) |

## What to do

1. Benchmark M/M/1 textbook case (user-specified): λ=2, μ=3 → ρ=2/3, L=2, W=1, Lq=4/3, Wq=2/3; plus the internal-consistency relations L = Lq + ρ, W = Wq + 1/μ, L = λ·W.
2. Benchmark M/M/c with independently known reference constants derived from the closed-form Erlang-C equations (computed by hand/calculator, NOT by calling `mmc`):
   - λ=8, μ=4, c=3 → exact rationals: ρ=2/3, P0=1/9, Lq=8/9, Wq=1/9, W=13/36, L=26/9
   - λ=10, μ=4, c=3 → P0=0.0449438202247191, Lq=3.5112359550561796, Wq=0.351123595505618, W=0.601123595505618, L=6.01123595505618
3. Edge cases:
   - λ=0: M/M/1 (μ=5) and M/M/c (μ=5, c=2) → ρ=0, L=0, Lq=0, Wq=0, stable=True; W=1/μ (documented implementation convention)
   - c=1 identity: `mmc(λ, μ, 1)` equals `mm1(λ, μ)` on every returned metric
   - utilization → 1: M/M/1 λ=9.9, μ=10 (exact: L=99, Lq=98.01, W=10, Wq=9.9); M/M/c λ=9.99, μ=5, c=2 (ρ=0.999, Lq≈997.50175, Wq≈99.85003, W≈100.05003, L≈999.49975, rel tolerance)
   - unstable: λ ≥ μ (M/M/1) and λ ≥ c·μ (M/M/c) → stable=False, error contains "Unstable", metric values None, rho still reported
   - boundary λ = μ exactly → unstable
   - invalid parameters: negative λ, zero/negative μ, c=0, c<0, non-integer c (float, string), non-finite (inf/nan), None → error flag, stable=False, no metrics
4. Use `pytest.approx` with tolerances (rel=1e-9 default where exact, abs for clean fractions), never exact float equality.
5. Keep reference values as literals with derivation comments.

## What NOT to do

- Do NOT change any formula in `queue_models.py` (freeze zone: Erlang-A log-domain, warm-up, POS stats are also frozen but out of scope here).
- Do NOT add P0 to result dicts (API change — flag in report, needs separate sign-off).
- Do NOT touch `mmc` overflow behavior (Phase 5 hardening item).
- Do NOT refactor `queue_models.py`, the tests/ dir layout, or existing tests.
- Do NOT begin Phase 2 (no extraction, no FastAPI, no DB, no React, no Streamlit changes).

## Testing strategy

- New benchmarks assert behavior against independent closed-form reference values — they lock mathematical correctness and catch future regressions (e.g., during Phase 2 extraction).
- TDD protocol: tests written first; run and watch them fail-or-pass; if any fail, diagnose per spec rules (bad expectation / tolerance / input interpretation / real error) BEFORE touching code; if a real error is proven, document it, list affected existing tests, then propose the smallest fix.
- Expected outcome: all new benchmarks pass immediately (implementation verified correct), proving the baseline math — the tests then serve as regression locks.

## Test plan

1. `python -m pytest tests/analytical_benchmarks.py -x --tb=short` → all new benchmarks pass (or diagnose failures).
2. `python -m pytest tests/ -x --tb=short` → 122 existing + new = all green.
3. `python -m ruff check .` and `python -m mypy .` → clean (new file must be type-clean).

## Implementation steps

- [ ] Write `tests/analytical_benchmarks.py` (M/M/1 + M/M/c + edge cases, pytest.approx)
- [ ] Add `python_files` to `pyproject.toml` pytest config
- [ ] Run new benchmarks; diagnose any failure per the protocol
- [ ] Apply smallest corrective change ONLY if a real error is proven (documented)
- [ ] Run full suite + ruff + mypy
- [ ] Report: baseline result, benchmarks added, results, formula-change status, counts, files changed, remaining issues, exit criteria

## Risk register

| Risk | Mitigation |
|---|---|
| A benchmark fails | Diagnose per protocol; do not touch formulas without proof |
| `mmc` λ=0 W convention questioned | Document convention (W=1/μ), lock behavior, flag for product owner |
| P0 not exposed by implementation | Out of Phase 1 scope; flag in report as Phase 3 API decision |
| Local Python 3.13 vs CI 3.10-3.12 | Parity watch; benchmarks are pure float math, low risk |
| Flaky AppTest under coverage | Pre-existing watch item; unrelated to this phase |
