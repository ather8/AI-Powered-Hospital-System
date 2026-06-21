"""Add department column to appointments table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-21

Problem fixed: analytics.py queried Appointment.department for per-department
appointment breakdowns, but the column never existed on the model or the DB
table. This caused either an AttributeError at import time or a silent empty
result. The column is nullable so all existing rows remain valid and appear
under "Unknown" in the analytics grouping (handled via COALESCE in
services/analytics.py).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005"
# Fixed: this previously pointed to the literal string "0004", but
# 0004_doctor_user_link.py's actual `revision` id is "0004_doctor_user_link"
# (not "0004"). That mismatch meant Alembic could never resolve this
# migration's parent, so `alembic upgrade head` would fail outright with
# "Can't locate revision identified by '0004'" -- this migration (and
# everything chained after it, including 0006) would never apply.
down_revision = "0004_doctor_user_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("department", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "department")
