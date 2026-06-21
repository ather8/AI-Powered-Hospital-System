"""Billing business logic: total calculation and status-transition rules.

Pulled out of routes/billing.py (rather than left inline) for two reasons:
  1. The same recalculation needs to run after every line-item add/remove,
     not just on bill update -- keeping it in one place avoids the totals
     drifting out of sync with the line items that produced them.
  2. It's unit-testable without spinning up the FastAPI app (see
     tests/test_billing.py).
"""
from app.models.billing import Billing


# Status lifecycle. Keys are the *current* status, values are the set of
# statuses it may transition to. "paid" and "cancelled" are terminal --
# absent as keys here, so any transition attempted from them is rejected.
VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "unpaid": {"partially_paid", "paid", "cancelled"},
    "partially_paid": {"paid", "cancelled"},
}

ALL_STATUSES = {"unpaid", "partially_paid", "paid", "cancelled"}

# Constrained payment method vocabulary. Kept here (not just in the Pydantic
# schema) so services/tests that bypass the API schema layer still get the
# same source of truth.
PAYMENT_METHODS = {"cash", "card", "insurance", "bank_transfer", "online"}


class InvalidStatusTransition(ValueError):
    """Raised when a bill's status would move along a disallowed edge."""


def validate_status_transition(current_status: str, new_status: str) -> None:
    """Raise InvalidStatusTransition unless current_status -> new_status is
    an allowed edge in VALID_STATUS_TRANSITIONS. A status "transitioning" to
    itself (no-op) is always allowed.
    """
    if new_status == current_status:
        return
    if new_status not in ALL_STATUSES:
        raise InvalidStatusTransition(f"'{new_status}' is not a valid billing status")
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise InvalidStatusTransition(
            f"Cannot move a bill from '{current_status}' to '{new_status}'"
        )


def recalculate_totals(bill: Billing) -> None:
    """Recompute subtotal/amount from the bill's current line items, tax,
    and discount. Mutates *bill* in place; caller is responsible for
    db.commit(). Must be called after any change to line_items, tax_amount,
    or discount_amount -- the route layer never sets `amount` directly.
    """
    subtotal = sum(item.quantity * item.unit_price for item in bill.line_items)
    bill.subtotal = subtotal
    bill.amount = max(subtotal - bill.discount_amount, 0.0) + bill.tax_amount
