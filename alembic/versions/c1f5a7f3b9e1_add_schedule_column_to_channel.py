"""add schedule column to channel

Revision ID: c1f5a7f3b9e1
Revises:
Create Date: 2024-07-26 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "c1f5a7f3b9e1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = inspect(op.get_bind())
    columns = [c["name"] for c in inspector.get_columns("channels")]
    if "schedule" not in columns:
        op.add_column("channels", sa.Column("schedule", sa.JSON(), nullable=True))


def downgrade():
    inspector = inspect(op.get_bind())
    columns = [c["name"] for c in inspector.get_columns("channels")]
    if "schedule" in columns:
        op.drop_column("channels", "schedule")
