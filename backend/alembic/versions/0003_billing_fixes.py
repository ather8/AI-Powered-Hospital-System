"""billing created_at server default

Revision ID: 0003_billing_fixes
Revises: 0002_emr_nullable_and_defaults
Create Date: 2026-06-20

Fixes two bugs in the `billing` table:

1. `created_at` had `default=datetime.now(timezone.utc)` in the SQLAlchemy
   model — evaluated ONCE at module import time, so every billing row created
   in a single server process got the same frozen timestamp. Fixed by switching
   to `server_default=func.now()`, which generates a fresh timestamp per row
   at the database level.

2. `get_patient_bills`, `update_bill`, and `delete_bill` route params were
   typed as `int`, but Billing.id / Billing.patient_id are UUID columns.
   FastAPI would 422-reject any real UUID before the function body ran, making
   those three endpoints completely unusable. Fixed in routes/billing.py
   (no schema migration needed — pure Python/routing change).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_billing_fixes'
down_revision = '0002_emr_nullable_and_defaults'
branch_labels = None
depends_on = None


def upgrade():
    # Add a server-side default for created_at so the DB generates a fresh
    # timestamp per row instead of inheriting the frozen Python-side value.
    op.alter_column(
        'billing',
        'created_at',
        server_default=sa.text('now()'),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        'billing',
        'created_at',
        server_default=None,
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
