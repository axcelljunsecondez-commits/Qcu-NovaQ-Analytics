"""Central Setup break validation matches the three-sheet upload rules.

The upload path (``setup_derivation.derive_setup``) rejects a break outside
its cashier's shift (or the operating day) and two overlapping breaks for one
cashier. The same configuration entered through the Setup API must get the
same outcome. Different cashiers may overlap (the upload accepts that too).
Stored setups are read back without these checks so an older saved Analysis
still loads.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.analysis_schemas import STORED_SETUP, QueueSetup
from backend.data.setup_derivation import derive_setup
from tests.test_setup_derivation import sheets


def _segments():
    return [
        {"id": "06:00-07:00", "start_time": "06:00", "end_time": "07:00", "active_queue_ids": ["a"]},
        {"id": "07:00-11:00", "start_time": "07:00", "end_time": "11:00", "active_queue_ids": ["a", "b"]},
        {"id": "11:00-17:00", "start_time": "11:00", "end_time": "17:00", "active_queue_ids": ["b"]},
    ]


def _setup(breaks, **over):
    base = {
        "queue_structure": "separate_queues",
        "staffing_varies_by_period": True,
        "capacity_mode": "unlimited",
        "abandonment_mode": "not_modeled",
        "queue_ids": ["a", "b"],
        "segments": _segments(),
        "event_period_basis": "representative_day",
        "breaks": breaks,
    }
    base.update(over)
    return base


def _brk(queue_id, start, minutes):
    return {"queue_id": queue_id, "scheduled_start_time": start, "duration_minutes": minutes}


def _message(exc: pytest.ExceptionInfo) -> str:
    return str(exc.value.errors()[0]["msg"])


def test_case_a_break_after_the_shift_ends_is_rejected():
    # Cashier a works 06:00-11:00 here; the prompt's case uses a shift ending at 06:00.
    with pytest.raises(ValidationError) as exc:
        QueueSetup.model_validate(_setup([_brk("a", "11:00", 30)]))
    assert "The a break at 11:00 for 30 minutes is outside its shift 06:00–11:00." in _message(exc)


def test_case_b_overlapping_breaks_for_one_cashier_are_rejected():
    with pytest.raises(ValidationError) as exc:
        QueueSetup.model_validate(_setup([_brk("b", "12:00", 30), _brk("b", "12:15", 30)]))
    assert "Breaks for b overlap: 12:00 (30 minutes) and 12:15 (30 minutes)." in _message(exc)


def test_case_c_break_running_past_the_shift_end_is_rejected():
    with pytest.raises(ValidationError) as exc:
        QueueSetup.model_validate(_setup([_brk("b", "16:45", 30)]))
    assert "outside its shift 07:00–17:00" in _message(exc)


def test_case_c_fixed_staffing_uses_the_operating_day():
    fixed = _setup([_brk("a", "16:45", 30)], staffing_varies_by_period=False, fixed_server_count=2,
                   segments=[{**segment, "active_queue_ids": None} for segment in _segments()])
    with pytest.raises(ValidationError) as exc:
        QueueSetup.model_validate(fixed)
    assert "outside the operating day 06:00–17:00" in _message(exc)


def test_case_d_different_cashiers_may_overlap():
    setup = QueueSetup.model_validate(_setup([_brk("a", "08:00", 30), _brk("b", "08:00", 30)]))
    assert len(setup.breaks) == 2


def test_case_e_valid_schedule_is_accepted_including_shift_edges():
    setup = QueueSetup.model_validate(_setup([
        _brk("a", "06:00", 15), _brk("a", "08:00", 30), _brk("a", "08:30", 30),
        _brk("b", "12:00", 60), _brk("b", "16:30", 30)]))
    assert len(setup.breaks) == 5


def test_no_segments_keeps_only_the_overlap_rule():
    base = _setup([_brk("a", "23:30", 60)], segments=[], staffing_varies_by_period=False,
                  fixed_server_count=2)
    assert len(QueueSetup.model_validate(base).breaks) == 1
    with pytest.raises(ValidationError):
        QueueSetup.model_validate({**base, "breaks": [_brk("a", "10:00", 60), _brk("a", "10:30", 5)]})


def test_stored_setup_reads_back_without_the_break_checks():
    stored = _setup([_brk("a", "11:00", 30), _brk("b", "12:00", 30), _brk("b", "12:15", 30)])
    assert len(QueueSetup.model_validate(stored, context=STORED_SETUP).breaks) == 3


def test_upload_and_setup_agree_on_the_same_invalid_break():
    import pandas as pd

    frames = sheets()
    first = frames["breaks"].iloc[0]
    overlap = pd.DataFrame([{**first.to_dict(), "break_name": "Extra"}])
    frames["breaks"] = pd.concat([frames["breaks"], overlap], ignore_index=True)
    assert any("overlap" in error for error in derive_setup(frames, None).errors)
    valid = derive_setup(sheets(), None)
    assert valid.errors == []
    setup = dict(valid.setup)
    setup["breaks"] = [*setup["breaks"], {**setup["breaks"][0], "break_name": "Extra"}]
    with pytest.raises(ValidationError) as exc:
        QueueSetup.model_validate(setup)
    assert "overlap" in _message(exc)


def test_novamart_three_sheet_setup_stays_valid():
    derived = derive_setup(sheets(), None)
    assert derived.errors == []
    setup = QueueSetup.model_validate(derived.setup)
    assert len(setup.segments) == 13
    assert len(setup.breaks) == 15


def test_api_rejects_an_out_of_shift_break_and_keeps_the_saved_setup(db_engine, client):
    from tests.helpers import create_user, csrf_header, login

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    created = client.post("/analyses", headers=csrf_header(client),
                          json={"name": "Breaks", "queue_setup": _setup([_brk("a", "08:00", 30)])})
    assert created.status_code == 201, created.text
    analysis_id = created.json()["analysis"]["id"]
    response = client.patch(f"/analyses/{analysis_id}", headers=csrf_header(client),
                            json={"queue_setup": _setup([_brk("a", "11:00", 30)])})
    assert response.status_code == 422
    assert "outside its shift 06:00–11:00" in response.text
    reloaded = client.get(f"/analyses/{analysis_id}").json()["analysis"]["queue_setup"]
    assert [b["scheduled_start_time"] for b in reloaded["breaks"]] == ["08:00:00"]


def test_stored_invalid_setup_still_loads(db_engine, client):
    from sqlalchemy.orm import Session

    from backend.db.models import AnalysisProject
    from tests.helpers import create_user, csrf_header, login

    create_user(db_engine, "u@example.com", "pw")
    login(client, "u@example.com", "pw")
    created = client.post("/analyses", headers=csrf_header(client),
                          json={"name": "Legacy", "queue_setup": _setup([_brk("a", "08:00", 30)])})
    analysis_id = created.json()["analysis"]["id"]
    with Session(db_engine) as session:
        analysis = session.get(AnalysisProject, analysis_id)
        assert analysis is not None
        analysis.queue_setup_json = {**analysis.queue_setup_json,
                                     "breaks": [_brk("a", "11:00:00", 30)]}
        session.commit()
    response = client.get(f"/analyses/{analysis_id}")
    assert response.status_code == 200, response.text
