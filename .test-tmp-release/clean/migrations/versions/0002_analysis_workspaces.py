"""add analysis workspaces and backfill legacy ownership

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.JSON:
    return sa.JSON().with_variant(JSONB(), "postgresql")


UNKNOWN_SETUP = {
    "queue_structure": "unknown",
    "fixed_server_count": None,
    "staffing_varies_by_period": False,
    "capacity_mode": "unknown",
    "total_system_capacity": None,
    "abandonment_mode": "unknown",
    "patience_rate_per_hour": None,
}


def upgrade() -> None:
    op.create_table(
        "analysis_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("service_type", sa.String(100), nullable=True),
        sa.Column("location_label", sa.String(255), nullable=True),
        sa.Column("queue_setup_json", _json(), nullable=False),
        sa.Column("setup_status", sa.String(32), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analysis_projects_user_id", "analysis_projects", ["user_id"])
    with op.batch_alter_table("datasets") as batch:
        batch.add_column(sa.Column("analysis_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_datasets_analysis_id", "analysis_projects", ["analysis_id"], ["id"])
        batch.create_index("ix_datasets_analysis_id", ["analysis_id"])
    with op.batch_alter_table("scenarios") as batch:
        batch.add_column(sa.Column("analysis_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_scenarios_analysis_id", "analysis_projects", ["analysis_id"], ["id"])
        batch.create_index("ix_scenarios_analysis_id", ["analysis_id"])

    bind = op.get_bind()
    metadata = sa.MetaData()
    analyses = sa.Table("analysis_projects", metadata, autoload_with=bind)
    datasets = sa.Table("datasets", metadata, autoload_with=bind)
    scenarios = sa.Table("scenarios", metadata, autoload_with=bind)

    dataset_rows = bind.execute(
        sa.select(datasets.c.id, datasets.c.user_id, datasets.c.name).order_by(datasets.c.id)
    ).mappings()
    dataset_analyses: dict[int, tuple[int, int]] = {}
    for row in dataset_rows:
        result = bind.execute(
            analyses.insert().values(
                user_id=row["user_id"],
                name=(row["name"] or f"Dataset {row['id']}")[:255],
                queue_setup_json=UNKNOWN_SETUP,
                setup_status="legacy_unknown",
            )
        )
        primary_key = result.inserted_primary_key
        assert primary_key is not None and primary_key[0] is not None
        dataset_analysis_id = int(primary_key[0])
        dataset_analyses[int(row["id"])] = (dataset_analysis_id, int(row["user_id"]))
        bind.execute(
            datasets.update().where(datasets.c.id == row["id"]).values(analysis_id=dataset_analysis_id)
        )

    scenario_rows = bind.execute(
        sa.select(scenarios.c.id, scenarios.c.user_id, scenarios.c.dataset_id).order_by(scenarios.c.id)
    ).mappings()
    legacy_by_user: dict[int, int] = {}
    for row in scenario_rows:
        dataset_id = row["dataset_id"]
        user_id = int(row["user_id"])
        scenario_analysis_id: int | None = None
        if dataset_id is not None:
            assigned = dataset_analyses.get(int(dataset_id))
            if assigned is not None and assigned[1] == user_id:
                scenario_analysis_id = assigned[0]
            else:
                warnings.warn(
                    f"Scenario {row['id']} could not be assigned safely: dataset ownership is inconsistent.",
                    stacklevel=1,
                )
        else:
            scenario_analysis_id = legacy_by_user.get(user_id)
            if scenario_analysis_id is None:
                result = bind.execute(
                    analyses.insert().values(
                        user_id=user_id,
                        name="Legacy scenarios",
                        queue_setup_json=UNKNOWN_SETUP,
                        setup_status="legacy_unknown",
                    )
                )
                legacy_key = result.inserted_primary_key
                assert legacy_key is not None and legacy_key[0] is not None
                scenario_analysis_id = int(legacy_key[0])
                legacy_by_user[user_id] = scenario_analysis_id
        if scenario_analysis_id is not None:
            bind.execute(
                scenarios.update().where(scenarios.c.id == row["id"]).values(analysis_id=scenario_analysis_id)
            )


def downgrade() -> None:
    with op.batch_alter_table("scenarios") as batch:
        batch.drop_index("ix_scenarios_analysis_id")
        batch.drop_constraint("fk_scenarios_analysis_id", type_="foreignkey")
        batch.drop_column("analysis_id")
    with op.batch_alter_table("datasets") as batch:
        batch.drop_index("ix_datasets_analysis_id")
        batch.drop_constraint("fk_datasets_analysis_id", type_="foreignkey")
        batch.drop_column("analysis_id")
    op.drop_index("ix_analysis_projects_user_id", table_name="analysis_projects")
    op.drop_table("analysis_projects")
