"""Store timestamps as timezone-aware (UTC)

Revision ID: 9f4c2e8a71b3
Revises: d5bd1e70d3d6
Create Date: 2026-10-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f4c2e8a71b3"
down_revision: Union[str, None] = "d5bd1e70d3d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs that hold timestamps
TIMESTAMP_COLUMNS = (
    ("users", "created_at"),
    ("ml_models", "created_at"),
    ("ml_models", "updated_at"),
    ("alerts", "created_at"),
    ("alerts", "resolved_at"),
    ("predictions", "created_at"),
)


def upgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            # Existing values were written as naive UTC
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
