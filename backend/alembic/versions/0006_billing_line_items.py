"""Add billing line items and invoice totals breakdown

Revision ID: 0006_billing_line_items
Revises: 0005
Create Date: 2026-06-21

Step 5 of the project review: billing was previously a single freetext
`amount` + freetext `method` string with no breakdown of what was actually
charged. This migration:

1. Adds a new `billing_line_items` table (description, quantity, unit_price)
   FK'd to `billing`, so an invoice can itemize multiple charges instead of
   being a single opaque number.
2. Adds `subtotal`, `tax_amount`, and `discount_amount` to `billing`.
   `amount` is kept as the existing column but its meaning narrows to
   "computed grand total" (subtotal - discount + tax), recomputed
   server-side by services/billing.py:recalculate_totals() any time line
   items/tax/discount change.
3. Backfills existing rows: each pre-existing bill gets exactly one
   synthetic line item ("Invoice total (migrated)") with unit_price equal
   to its old `amount`, so historical invoices remain internally consistent
   (subtotal == amount, tax/discount == 0) without losing their original
   total.
4. `status` becomes NOT NULL (was nullable with a Python-side default that
   could still end up NULL via bulk inserts bypassing the ORM default).

`method` is NOT constrained at the database level here -- the fixed
vocabulary (cash/card/insurance/bank_transfer/online) is enforced at the
Pydantic schema layer (schemas/billing.py) instead, consistent with how
`Appointment.status` is also a plain nullable String validated in the
service/schema layer rather than a DB-level CHECK or enum.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0006_billing_line_items"
down_revision = "0005"
branch_labels = None
depends_on = None


billing_line_items = sa.table(
    "billing_line_items",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("bill_id", postgresql.UUID(as_uuid=True)),
    sa.column("description", sa.String()),
    sa.column("quantity", sa.Integer()),
    sa.column("unit_price", sa.Float()),
)

billing = sa.table(
    "billing",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("amount", sa.Float()),
    sa.column("subtotal", sa.Float()),
)


def upgrade() -> None:
    op.create_table(
        "billing_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("billing.id"), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.add_column("billing", sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"))
    op.add_column("billing", sa.Column("tax_amount", sa.Float(), nullable=False, server_default="0"))
    op.add_column("billing", sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0"))

    # Backfill: give every existing bill one line item equal to its current
    # `amount`, and set subtotal to match, so old invoices stay internally
    # consistent (subtotal - discount + tax == amount) under the new model.
    # UUIDs are generated in Python (uuid.uuid4(), same as the ORM model
    # defaults) rather than via gen_random_uuid(), to avoid introducing a
    # dependency on the pgcrypto extension being installed.
    conn = op.get_bind()
    existing_bills = conn.execute(sa.select(billing.c.id, billing.c.amount)).fetchall()
    for bill_id, amount in existing_bills:
        conn.execute(
            billing_line_items.insert().values(
                id=uuid.uuid4(),
                bill_id=bill_id,
                description="Invoice total (migrated)",
                quantity=1,
                unit_price=amount,
            )
        )
    op.execute("UPDATE billing SET subtotal = amount")

    op.alter_column("billing", "status", nullable=False, server_default="unpaid")


def downgrade() -> None:
    op.drop_table("billing_line_items")
    op.drop_column("billing", "discount_amount")
    op.drop_column("billing", "tax_amount")
    op.drop_column("billing", "subtotal")
    op.alter_column("billing", "status", nullable=True, server_default=None)
