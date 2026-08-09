# Phase 2 — Domain/Service Layer Extraction Plan (2026-08-09)

Spec: `docs/superpowers/specs/2026-08-09-novamart-production-architecture-design.md` (§4, §5, §8, Phase 2 row)

## Project overview

Behavior-preserving extraction of the framework-free domain layer out of the current single-directory Streamlit app into `backend/` packages, per the approved architecture. The legacy Streamlit app moves to `legacy_streamlit/` and keeps working. Two contained security fixes land (Page 3 queue-bar XSS, `theme.toast()` escaping). No formula/behavior changes, no Phase 2.5 correctness fixes.

## Target layout

```
backend/
├── __init__.py
├── queueing_engine/
│   ├── __init__.py, config.py, log.py
│   ├── models/__init__.py, queue_models.py
│   ├── simulation/__init__.py, simulation.py        (+ validate_with_simulation merged in)
│   ├── statistics/__init__.py, pos_connector.py
│   └── services/__init__.py, optimization.py, costing.py, data_processing.py
├── data/__init__.py, ingestion.py                    (pure app_page_utils funcs)
└── reports/__init__.py, report_export.py
legacy_streamlit/
├── streamlit_app.py, theme.py, app_page_utils.py     (st-coupled: init_session_state, dataframe_download + re-exports)
├── data_processing.py                                (st.cache_data cached bridge)
├── i18n/__init__.py                                  (loader repointed to frontend)
└── pages/1..4
frontend/public/locales/{en,tl}/translation.json      (i18n JSON resources relocated)
tests/conftest.py                                     (sys.path bootstrap: repo root + legacy_streamlit)
api.py, test_imports.py                               (stay at root; imports repointed)
```

Package `__init__.py` files re-export the public API of each module so consumers import
`from backend.queueing_engine.models import mm1` etc.; privates (`_queue_metrics`,
`_classify_utilization_status`) are imported from module paths.

## What to do

1. **Unit A — foundation:** move `config.py`, `log.py` → `backend/queueing_engine/`; repoint every importer (`queue_models`, `simulation`, `pos_connector`, `optimization`, `costing`, `data_processing`, `report_export`, `app_page_utils`, `api`, `streamlit_app`, `pages/1-4`, `tests/test_costing`); add `tests/conftest.py` (repo-root bootstrap).
2. **Unit B — models:** move `queue_models.py` → `models/`; repoint `simulation`, `optimization`, `data_processing`, `api`, `tests/test_queue_models`, `tests/analytical_benchmarks`.
3. **Unit C — statistics:** move `pos_connector.py` → `statistics/`; repoint lazy import in `pages/1_current_metrics.py`.
4. **Unit D — simulation:** move `simulation.py` → `simulation/`; relocate `validate_with_simulation` from `data_processing.py` into it (top-level import, decorator dropped); repoint `services/data_processing` (lazy import removed), `pages/3`, `tests/test_dashboard_flow` (lazy), `tests/test_simulation`.
5. **Unit E — services:** move `optimization.py`, `costing.py`, `data_processing.py` → `services/`; in `data_processing.py` drop `import streamlit` and the three `@st.cache_data` decorators; replace root `data_processing.py` with a temporary cached bridge (st.cache_data wrappers re-exporting from the package — keeps root pages + tests working until Unit G); repoint `api.py`, `pages/1,2,4`, `tests/test_optimization`, `tests/test_costing`, `tests/test_dashboard_flow`.
6. **Unit F — data:** create `backend/data/ingestion.py` (pure `validate_and_normalize`, `to_segment_records`, `read_uploaded_table`, `sample_segments`, `pretty_metric`, `REQUIRED_COLUMNS`, `OPTIONAL_COLUMNS`, config imports repointed); root `app_page_utils.py` becomes a bridge (st-coupled funcs stay, pure funcs re-exported from `backend.data.ingestion`); repoint `tests/test_dashboard_flow`, `tests/test_dashboard_e2e`.
7. **Unit G — legacy move:** `git mv` `streamlit_app.py`, `theme.py`, `pages/`, `i18n/__init__.py` → `legacy_streamlit/`; move `en.json`/`tl.json` → `frontend/public/locales/{en,tl}/translation.json`; repoint i18n loader (`_locale_dir` → repo root / `frontend/public/locales`, path `<lang>/translation.json`); move the two bridges (`app_page_utils.py`, `data_processing.py`) into `legacy_streamlit/`; repoint page imports of `config`/`log` → `backend.queueing_engine.*` (already done in earlier units for the rest); add repo-root bootstrap to `streamlit_app.py` (real `streamlit run` needs it); extend `tests/conftest.py` with `legacy_streamlit` on sys.path (AppTest runs pages directly); update `tests/test_dashboard_e2e.py` paths to `legacy_streamlit/...`; update `test_imports.py` CHECKS; update run-command docs.
8. **Unit H — security fixes:**
   - Page 3 queue bars (`legacy_streamlit/pages/3_simulation.py` ~line 130): `html.escape(str(r.get("time", "")))` for the label interpolation.
   - `theme.toast()` (`legacy_streamlit/theme.py` ~line 739): `html.escape(message)` before HTML interpolation.
9. **Final verification:** full battery + grep that `backend/` imports no streamlit/fastapi/sqlalchemy + behavior parity.

## What NOT to do

- No formula changes; no Phase 2.5 fixes (ternary search, savings guard, cost engines, dispatch precedence, MC thresholds, summarize keys) — deferred with sign-off.
- No new FastAPI routers, no PostgreSQL, no React frontend build, no Streamlit retirement.
- Do not change test assertions — only import paths and AppTest script paths.
- Do not add P0/output keys to queue models.
- No `st.cache_data` inside `backend/`.

## Testing strategy

- After EVERY unit: (1) relevant unit tests, (2) full suite `python -m pytest tests/ -x --tb=short`, (3) Streamlit AppTest E2E (`tests/test_dashboard_e2e.py`), (4) `python -m ruff check .`, (5) `python -m mypy .`.
- Invariants: all original 122 tests green; E2E green; `backend/` free of streamlit/fastapi/DB imports; numerical behavior unchanged.
- If a test fails: STOP, diagnose (import/path, extraction mistake, changed behavior, environment, genuine defect). Fix the cause, never the assertion.

## Test plan

1. `python -m pytest tests/test_queue_models.py tests/analytical_benchmarks.py tests/test_simulation.py tests/test_optimization.py tests/test_costing.py tests/test_dashboard_flow.py -x --tb=short` (unit)
2. `python -m pytest tests/ -x --tb=short` (full: 122 + 24)
3. `python -m pytest tests/test_dashboard_e2e.py -x --tb=short` (E2E)
4. `python -m ruff check .`; 5. `python -m mypy .`
6. Framework-import audit: grep `streamlit|fastapi|sqlalchemy` under `backend/` → zero matches

## Implementation steps

- [ ] Unit A: config+log extraction, import repoints, conftest → battery
- [ ] Unit B: models extraction → battery
- [ ] Unit C: statistics extraction → battery
- [ ] Unit D: simulation extraction + validate_with_simulation relocation → battery
- [ ] Unit E: services extraction + cached bridge + decorator removal → battery
- [ ] Unit F: data ingestion + app_page_utils bridge → battery
- [ ] Unit G: legacy_streamlit move, i18n relocation, bootstrap, e2e paths → battery
- [ ] Unit H: XSS + toast escaping → battery
- [ ] Final audit + report; STOP before Phase 3

## Risk register

| Risk | Mitigation |
|---|---|
| Import resolution breaks during/after moves | Per-unit battery; conftest + app bootstrap; git mv preserves history |
| AppTest direct-page runs lack `legacy_streamlit` on sys.path | tests/conftest.py inserts it |
| `st.cache_data` removal changes legacy caching behavior | Cached bridge re-applies decorators at the legacy layer (same caching) |
| `validate_with_simulation` move changes import cycle risk | It lives in the same package as its dependencies (top-level import, no cycle) |
| Pre-commit hooks (ruff-format etc.) alter files | Run hooks via ruff/mypy first; fix hook complaints, then commit |
| i18n relocation breaks tl-locale E2E | Loader repointed to `frontend/public/locales/<lang>/translation.json` before E2E |
