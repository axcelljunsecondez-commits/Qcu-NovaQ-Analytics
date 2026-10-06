# API `event=` log lines: fix plan (2026-10-06)

## Defect (VERIFIED)

`docs/operations.md` (Health, logs, alerts) requires API logs that carry the
following, and the code does not deliver them:
- runtime timestamp and severity;
- event, request ID, method and query-free path;
- status, duration and safe user ID.

- Found in production after the G-A release (GO packet §6, SMTP row): Render's
  log view never shows the app's `event=` lines.
- Cause, from the code:
  - The API logs through `logging.getLogger("novaq.api")` (`backend/api/main.py`).
  - Nothing in `backend/` gives the `novaq` loggers a level or handler, and
    uvicorn's default logging configuration covers only its own loggers.
  - The `novaq` loggers therefore inherit the root WARNING level. Every INFO
    `event=` line (`event=http_request` and the security events) is dropped,
    while WARNING and higher fall back to Python's bare last-resort stderr line.
- Reproduced locally:
  - Setup: release tree `2ccb8652`, the Render Start Command `uvicorn
    backend.api.main:app`, SQLite, `/health` and `/auth/forgot-password`.
  - Result: uvicorn's own lines only, 0 `event=` lines.
- Compose production runs `--no-access-log` and relies on these same lines, so
  it is affected the same way (INFERRED; not run).

## Change (scope: `backend/api/main.py`, one new test module)

`create_app()` calls the new `configure_event_logging()`:
- It sets the `novaq` logger to INFO, unless an explicit level is already set.
- It adds one UTC-timestamped stream handler (`2026-10-06T15:44:31Z INFO
  novaq.api event=…`), and only when the root logger has no handler.
  - An explicit logging configuration, or pytest's capture, still receives the
    records exactly once, by propagation.
  - The handler's own type prevents a second copy when the app is created again.

Unchanged:
- log message contents, so no new fields and nothing secret;
- the engine loggers (`backend.queueing_engine.*`, outside `novaq`);
- uvicorn's access log;
- API contracts, models and mathematics.

## Verification

- `tests/test_api_event_logging.py`, 5 tests, covering:
  - a request's `event=http_request` line at INFO;
  - `event=password_reset_request` at INFO;
  - one handler, UTC format, and DEBUG hidden when the root logger has no handler;
  - no second handler when the root logger is configured;
  - an explicit `novaq` level kept.
- Mutation check: 4 of 4 mutants killed. The mutants removed the call, removed
  the INFO level, ignored root handlers, and dropped the single-handler guard.
- End to end with the Start Command (uvicorn 0.54, Python 3.13):
  - each request logs one UTC `event=http_request` line, plus
    `event=password_reset_request`;
  - no duplicates;
  - the event path is query-free.
- Gates, run 2026-10-06/07 on Windows, Python 3.13.13, with the release
  requirements:
  - `python -m pytest tests/ -x`: 1585 passed, 118 skipped, 1 xfailed. That is
    the release baseline of 1580/118/1 plus the 5 new tests.
  - `ruff check .`: clean.
  - `mypy .`: no issues in 167 files.
  - Not run: PostgreSQL-backed tests (no `NOVAQ_TEST_DATABASE_URL`) and the
    frontend gates (no frontend change).

## Out of scope (reported, not changed)

- Uvicorn's own access line includes query strings
  (`POST /auth/forgot-password?…`). It already did so, and the Start Command
  keeps uvicorn's access log on.
- Changing that, for example with `--no-access-log` as Compose does, is a
  separate Render setting decision.

## Release

Released on 2026-10-06, each step authorized by the owner:
- Commit `0ddefa6d` was pushed to `main`.
- GitHub CI #98 (run 37493271324) passed 11/11 jobs, including backend tests on
  Python 3.10–3.13, postgres-integration, stack-integration and docker-build.
- The owner Manual-Deployed `0ddefa6` on Render as `dep-db2i3lom7kps73eupp50`.
  Startup completed and the service went live at ~16:30 UTC.
- VERIFIED in Render's logs with tagged requests at 16:31 UTC, each line once:
  - `2026-10-06T16:31:47Z INFO novaq.api event=http_request request_id=g8-logcheck-1 method=GET path=/ready status=200 …`
  - the bridge request `g8-logcheck-2`;
  - `event=password_reset_request request_id=g8-logcheck-3 outcome=accepted`
    and its `event=http_request` line.
  - The reset request used `nobody@example.com`, so no email was sent.
