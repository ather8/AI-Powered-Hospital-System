"""link doctors to users

Revision ID: 0004_doctor_user_link
Revises: 0003_billing_fixes
Create Date: 2026-06-21

Adds `doctors.user_id`, a nullable, unique FK to `users.id`.

Previously there was no way to map a logged-in User account (integer id)
to "their own" Doctor profile (UUID id). This meant:

1. The dashboard service (services/dashboard.py) couldn't filter
   appointments/EMRs by doctor and silently fell back to hospital-wide
   stats for every doctor-role account.
2. GET /appointments/ returned the entire appointments table to any
   doctor, since there was no column to filter on.

The column is nullable (a Doctor profile can exist before the matching
staff account registers/is linked) and unique (one User account can only
be linked to one Doctor profile, keeping the mapping 1:1).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_doctor_user_link"
down_revision: Union[str, Sequence[str], None] = "0003_billing_fixes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("doctors", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_doctors_user_id_users",
        "doctors",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_unique_constraint("uq_doctors_user_id", "doctors", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_doctors_user_id", "doctors", type_="unique")
    op.drop_constraint("fk_doctors_user_id_users", "doctors", type_="foreignkey")
    op.drop_column("doctors", "user_id")
