"""The one rule for an Analysis's current dataset (read-only).

Before this module the rule was written twice, identically: ``workflow._current_valid_dataset_id``
and the inline selection in ``analyses.current_analysis``. Both now call ``resolve_current_dataset``.

Rule (unchanged): among the datasets recorded for the Analysis and owned by the user, the one with
the highest id whose validation report has a truthy ``ok``.

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


class CurrentDatasetStatus(str, Enum):
    CURRENT = "current"
    NO_DATASET = "no_dataset"  # the Analysis has no dataset of this owner
    NO_VALID_DATASET = "no_valid_dataset"  # it has datasets, but no validation report is ok


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


def resolve_current_dataset(db: Session, *, owner_id: int, analysis_id: int) -> CurrentDatasetResolution:
    candidates = db.execute(
        select(Dataset)
        .where(Dataset.user_id == owner_id, Dataset.analysis_id == analysis_id)
        .order_by(Dataset.id.desc())
    ).scalars()
    found_any = False
    for dataset in candidates:
        found_any = True
        if is_successfully_processed(dataset):
            return CurrentDatasetResolution(CurrentDatasetStatus.CURRENT, dataset)
    status = CurrentDatasetStatus.NO_VALID_DATASET if found_any else CurrentDatasetStatus.NO_DATASET
    return CurrentDatasetResolution(status, None)
