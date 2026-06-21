"""emr nullable fields and created_at default

Revision ID: 0002_emr_nullable_and_defaults
Revises: 0001_initial
Create Date: 2026-06-20

This fixes two related schema bugs in `emrs`:

1. `prescription` and `lab_results` were NOT NULL, but the EMRCreate /
   EMRUpdate schemas allow both to be omitted (str | None = None). Any
   request without them would hit a NOT NULL IntegrityError.
2. `created_at` had no default. The only thing populating it was a route
   call to `datetime.now(datetime.UTC)`, which is invalid (`datetime` is
   the class imported via `from datetime import datetime`, not the
   module — `.UTC` only exists on the module), so every POST /emrs/
   request raised AttributeError before ever reaching the database. A
   server-side default makes this resilient even if a future code path
   creates an EMR without explicitly setting created_at.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_emr_nullable_and_defaults"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("emrs", "prescription", existing_type=sa.Text(), nullable=True)
    op.alter_column("emrs", "lab_results", existing_type=sa.Text(), nullable=True)
    op.alter_column(
        "emrs",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("emrs", "created_at", existing_type=sa.DateTime(), server_default=None)
    op.alter_column("emrs", "lab_results", existing_type=sa.Text(), nullable=False)
    op.alter_column("emrs", "prescription", existing_type=sa.Text(), nullable=False)
