"""Write the Named Shared Queue frontend test fixture from the real backend.

Runs the named API routes R1-R6 through the FastAPI app on a throwaway SQLite database, with the
synthetic inputs below, and writes their responses unchanged to
frontend/src/test/fixtures/sharedNamed.json (spec 2026-09-30-shared-queue-named-api-ui-first-slice.md,
section 16, item 7). The inputs are SYNTHETIC; nothing here is observed data.

Usage: python scripts/generate_shared_named_fixture.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from backend.api.email_delivery import FakeEmailSender  # noqa: E402
from backend.api.main import create_app  # noqa: E402
from backend.api.settings import Settings  # noqa: E402
from backend.db.base import Base  # noqa: E402
from backend.db.models import AnalysisProject, Dataset  # noqa: E402
from tests.helpers import create_user, csrf_header, login, make_sessionmaker  # noqa: E402

OUTPUT = REPO_ROOT / "frontend" / "src" / "test" / "fixtures" / "sharedNamed.json"
SETUP = {
    "queue_structure": "shared_queue", "fixed_server_count": 2, "staffing_varies_by_period": True,
    "capacity_mode": "unlimited", "total_system_capacity": None, "abandonment_mode": "not_modeled",
    "patience_rate_per_hour": None,
}
ROWS = [  # SYNTHETIC aggregate demand: clock-range labels, no variance, K, or theta
    {"time": "08:00-09:00", "lambda": 6.0, "mu": 4.0, "c": 1},
    {"time": "09:00-10:00", "lambda": 8.0, "mu": 4.0, "c": 2},
]
WORKFORCE = {  # SYNTHETIC pseudonymous workforce
    "horizon": {"start_minute": 480, "end_minute": 600},
    "required_staffing": [
        {"segment_id": "early", "start_minute": 480, "end_minute": 540, "servers": 1},
        {"segment_id": "late", "start_minute": 540, "end_minute": 600, "servers": 2},
    ],
    "employees": [
        {"employee_id": "E1", "availability": [{"start_minute": 480, "end_minute": 600}],
         "pay": {"regular_rate_per_hour": 100.0, "overtime_rate_per_hour": 150.0, "daily_regular_paid_minutes": 480}},
        {"employee_id": "E2", "availability": [{"start_minute": 480, "end_minute": 600}],
         "pay": {"regular_rate_per_hour": None, "overtime_rate_per_hour": None, "daily_regular_paid_minutes": None}},
    ],
    "rules": {
        "shift_rules": {"earliest_start_minute": 480, "latest_end_minute": 600, "min_shift_minutes": 60,
                        "max_shift_minutes": 120, "boundary_granularity_minutes": 15, "max_shifts_per_employee": 1,
                        "min_minutes_between_shifts": None},
        "break_rules": [
            {"min_shift_minutes": 60, "max_shift_minutes": 90, "min_gap_minutes": 0, "breaks": []},
            {"min_shift_minutes": 91, "max_shift_minutes": 120, "min_gap_minutes": 0, "breaks": [
                {"name": "rest", "duration_minutes": 15, "paid": True, "earliest_start_offset_minutes": 30,
                 "latest_start_offset_minutes": 60}]},
        ],
        "register_count": 2,
    },
    "roster": [
        {"employee_id": "E1", "start_minute": 480, "end_minute": 600, "breaks": [{"name": "rest", "start_minute": 525}]},
        {"employee_id": "E2", "start_minute": 540, "end_minute": 600, "breaks": []},
    ],
    "closing_policy": "HARD_CUTOFF",
}
REPLICATIONS, SEED, SELECTED = 3, 20261001, 1


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite:///{(Path(directory) / 'fixture.db').as_posix()}",
                               connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        client = TestClient(create_app(engine=engine, settings=Settings(), email_sender=FakeEmailSender()))
        user = create_user(engine, "fixture@example.com", "fixture-only")
        with make_sessionmaker(engine)() as db:
            analysis = AnalysisProject(user_id=user.id, name="Fixture", queue_setup_json=SETUP, setup_status="ready")
            db.add(analysis)
            db.flush()
            dataset = Dataset(user_id=user.id, analysis_id=analysis.id, name="Synthetic rates",
                              source_filename="synthetic.csv", source_format="csv", row_count=len(ROWS),
                              normalized_json=ROWS, validation_report_json={"ok": True})
            db.add(dataset)
            db.commit()
            analysis_id, dataset_id = analysis.id, dataset.id
        assert login(client, "fixture@example.com", "fixture-only") == 200
        base = f"/analyses/{analysis_id}/shared-named"

        def ok(response):
            assert response.status_code == 200, response.text
            return response.json()

        contract = ok(client.get(f"{base}/contract"))
        policy = {name: item["approved"] for name, item in contract["employee_policy"].items()}
        workforce = {"dataset_id": dataset_id, **WORKFORCE, "employee_policy": policy}
        request = {**workforce, "replications": REPLICATIONS, "seed": SEED}
        validated = ok(client.post(f"{base}/validate", json=workforce, headers=csrf_header(client)))
        run = ok(client.post(f"{base}/runs", json=request, headers=csrf_header(client)))
        run_id = run["evidence"]["id"]
        fixture = {
            "generated_by": "scripts/generate_shared_named_fixture.py (synthetic inputs; SQLite; not observed data)",
            "analysis_id": analysis_id,
            "dataset_id": dataset_id,
            "request": request,
            "contract": contract,
            "validate": validated,
            "run": run,
            "runs": ok(client.get(f"{base}/runs")),
            "run_detail": ok(client.get(f"{base}/runs/{run_id}")),
            "replication": ok(client.get(f"{base}/runs/{run_id}/replications/{SELECTED}")),
        }
        client.close()
        engine.dispose()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fixture, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT).as_posix()} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
