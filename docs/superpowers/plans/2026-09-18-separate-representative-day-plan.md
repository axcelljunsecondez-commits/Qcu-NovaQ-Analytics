# Separate Queue Representative Day — Plan

Spec: `docs/superpowers/specs/2026-09-18-separate-representative-day.md`.
Every task is RED → GREEN; no protected formula changes.

1. **Setup field** — `backend/api/analysis_schemas.py`: add
   `event_period_basis` (`per_date` default, `representative_day` only for
   separate queues). Test: `tests/test_representative_day.py`.
2. **Ingestion** — `backend/data/analysis_ingestion.py`: allow separate
   customer-event uploads with varying staffing; representative-day grouping
   by (segment, queue) across dates with `lambda = n / (hours × D)`, pooled
   samples, `observation_days`, provenance. Per-date path byte-identical.
3. **Full coverage by schedule** — `separate_optimization.py`:
   `optimize_separate_schedule(..., full_coverage=True)` sets each period's
   lower bound to its scheduled lanes and rejects rows ≠ schedule; endpoint
   and save verifier pass it. Fixed-staffing results unchanged.
4. **Continuous day DES** — `separate_optimization.py`: `run_routing_day_des`
   reusing `route_arrival`, `DedicatedQueueLifecycle` (scheduled open/close +
   breaks), empirical resampling, and the trace schema. `workflow.py`:
   selected-plan DES uses it for representative-day analyses; Monte Carlo
   uses per-period duration when present.
5. **Frontend** — setup option (types, Analysis Setup, EN/TL locales), test.
6. **Verify** — focused + full backend/frontend gates; real NovaMart upload
   through Setup → Current → Optimize → Save → Compare → Simulate → MC →
   Validation → Decision → Reports.
