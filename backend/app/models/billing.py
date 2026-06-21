from sqlalchemy import Column, Float, DateTime, String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db import Base


class Billing(Base):
    __tablename__ = "billing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # `amount` is now the computed grand total (subtotal - discount + tax),
    # kept as its own column (rather than computed on every read) so existing
    # consumers (export, dashboards, the /me list) keep working unchanged.
    # It is recomputed server-side any time line items, tax, or discount
    # change -- see services/billing.py:recalculate_totals(). Clients should
    # treat it as read-only/derived; BillingUpdate no longer accepts it.
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)

    # Status lifecycle (see services/billing.py:VALID_STATUS_TRANSITIONS):
    #   unpaid -> partially_paid -> paid
    #   unpaid -> cancelled
    #   partially_paid -> cancelled
    # "paid" and "cancelled" are terminal; no transition leaves them.
    status = Column(String, default="unpaid", nullable=False)

    # Constrained to a fixed set of payment methods (see schemas/billing.py
    # PAYMENT_METHODS) instead of arbitrary freetext, so reporting/analytics
    # can group on it reliably. Nullable until a payment is actually taken.
    method = Column(String, nullable=True)

    # server_default=func.now() generates a fresh timestamp per-row at the DB
    # level. Using default=datetime.now(timezone.utc) evaluates ONCE at module
    # import time, so every row in a process lifetime gets the same timestamp.
    created_at = Column(DateTime, server_default=func.now())

    line_items = relationship(
        "BillingLineItem",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillingLineItem.created_at",
    )


class BillingLineItem(Base):
    """A single charge within an invoice (e.g. 'Consultation fee', qty 1,
    unit_price 120.00). An invoice's subtotal is the sum of
    quantity * unit_price across all of its line items.

    Kept as a real table rather than a JSON blob on Billing so individual
    items remain queryable/auditable (e.g. "show all consultation-fee
    charges this month") and so SQLAlchemy enforces the FK relationship
    instead of trusting arbitrary client-supplied JSON shape.
    """

    __tablename__ = "billing_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("billing.id"), nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    bill = relationship("Billing", back_populates="line_items")
