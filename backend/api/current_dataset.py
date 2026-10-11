"""The one rule for an Analysis's current dataset (read-only).

Before this module the rule was written twice, identically: ``workflow._current_valid_dataset_id``
and the inline selection in ``analyses.current_analysis``. Both now call ``resolve_current_dataset``.

Rule (B10, spec docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md): among the datasets
recorded for the Analysis, owned by the user and uploaded FOR PLANNING, the one with the highest id
whose validation report has a truthy ``ok``. A review-only file is never current. Every dataset that
existed before migration 0006 is a planning file, so B10 changed no existing analysis's result.

- Ordering is by id, not by ``created_at``.
- A dataset with ``analysis_id`` NULL (legacy, never associated) belongs to no Analysis.
- A deleted dataset has no row, so it cannot be selected.
- Archival of the Analysis does not change the result.
- The caller authorizes the Analysis first (``own_analysis``). This module only filters by the
  owner and Analysis ids it is given, and it never writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Dataset

PLANNING, REVIEW = "planning", "review"
PURPOSES = (PLANNING, REVIEW)


class CurrentDatasetStatus(str, Enum):
    CURRENT = "current"
    NO_DATASET = "no_dataset"  # the Analysis has no dataset of this owner
    NO_VALID_DATASET = "no_valid_dataset"  # it has planning datasets, but no validation report is ok
    NO_PLANNING_DATASET = "no_planning_dataset"  # it has datasets, all of them review-only


@dataclass(frozen=True)
class CurrentDatasetResolution:
    status: CurrentDatasetStatus
    dataset: Dataset | None  # set exactly when status is CURRENT

    @property
    def dataset_id(self) -> int | None:
        return self.dataset.id if self.dataset is not None else None


def is_successfully_processed(dataset: Dataset) -> bool:
    """The existing validity test: a truthy ``ok`` in the stored validation report."""
    return bool((dataset.validation_report_json or {}).get("ok"))


def is_for_planning(dataset: Dataset) -> bool:
    """B10: only a planning file may be planned with; review-only files are for reading."""
    return dataset.purpose == PLANNING


def resolve_current_dataset(db: Session, *, owner_id: int, analysis_id: int) -> CurrentDatasetResolution:
    candidates = db.execute(
        select(Dataset)
        .where(Dataset.user_id == owner_id, Dataset.analysis_id == analysis_id)
        .order_by(Dataset.id.desc())
    ).scalars()
    found_any = found_planning = False
    for dataset in candidates:
        found_any = True
        if not is_for_planning(dataset):
            continue
        found_planning = True
        if is_successfully_processed(dataset):
            return CurrentDatasetResolution(CurrentDatasetStatus.CURRENT, dataset)
    if found_planning:
        status = CurrentDatasetStatus.NO_VALID_DATASET
    elif found_any:
        status = CurrentDatasetStatus.NO_PLANNING_DATASET
    else:
        status = CurrentDatasetStatus.NO_DATASET
    return CurrentDatasetResolution(status, None)
