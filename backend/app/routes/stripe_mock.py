"""Mock Stripe payment integration.

Real Stripe requires a live secret key and runs webhooks over HTTPS. This
mock replicates the two-step flow — create a checkout session, receive a
webhook that marks the bill paid — without any network calls, so the
feature can be demo'd and tested locally before a real key is wired in.

The mock secret key is ``sk_mock_...`` (never an ``sk_live_`` value), so
accidental production use is obvious.  A ``/billing/stripe/webhook`` POST
endpoint accepts a JSON body that looks like a stripped-down Stripe webhook
event and transitions the matching bill to ``paid``.

Endpoints
---------
POST /billing/stripe/checkout/{bill_id}
    Returns a mock ``checkout_url`` that the frontend can redirect to (or
    display as a "Pay Now" link).  In a real integration you'd call
    ``stripe.checkout.Session.create(...)`` here.

POST /billing/stripe/webhook
    Accepts the mock event body ``{ "type": "checkout.session.completed",
    "data": { "object": { "metadata": { "bill_id": "<uuid>" } } } }`` and
    marks the bill paid.  Idempotent: calling it twice on an already-paid
    bill is a no-op (returns 200).

    Real Stripe has no JWT to send (Stripe's servers call this endpoint
    directly, not a logged-in browser), so it can't go through
    require_roles like every other route here. Instead it must present the
    ``X-Webhook-Secret`` header matching ``STRIPE_WEBHOOK_SECRET`` — without
    that check, anyone who finds the URL could POST a fabricated
    "payment completed" event and mark an arbitrary bill paid for free.
    This is a stand-in for real Stripe's signed-payload verification; see
    the migration note below.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.config import STRIPE_WEBHOOK_SECRET
from app.db import get_db
from app.models.billing import Billing
from app.services.audit import log_action
from app.services.billing import InvalidStatusTransition, validate_status_transition
from app.utils.rbac import require_roles

router = APIRouter(prefix="/billing/stripe", tags=["billing", "payments"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    bill_id: str
    amount: float


class MockWebhookMetadata(BaseModel):
    bill_id: str


class MockWebhookObject(BaseModel):
    metadata: MockWebhookMetadata


class MockWebhookData(BaseModel):
    object: MockWebhookObject


class MockWebhookEvent(BaseModel):
    type: str
    data: MockWebhookData


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/checkout/{bill_id}", response_model=CheckoutSessionResponse)
def create_checkout_session(
    bill_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_roles(["patient", "admin", "receptionist"])
    ),
):
    """Create a mock Stripe Checkout session for an unpaid bill.

    Returns a ``checkout_url`` that encodes the bill ID and amount.  In
    production, replace the body with a real ``stripe.checkout.Session.create``
    call and return ``session.url`` instead.
    """
    bill = (
        db.query(Billing)
        .options(joinedload(Billing.line_items))
        .filter(Billing.id == bill_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Billing record not found")

    if bill.status in ("paid", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Bill is already '{bill.status}' and cannot be checked out.",
        )

    # Patients may only pay their own bills.
    if current_user["role"] == "patient":
        from app.models.patient import Patient

        patient = (
            db.query(Patient)
            .filter(Patient.user_id == int(current_user["sub"]))
            .first()
        )
        if not patient or bill.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Access forbidden")

    # In a real integration you'd call stripe.checkout.Session.create here.
    # For the mock, we build a deterministic session_id from the bill UUID so
    # the webhook can verify it without a live Stripe round-trip.
    session_id = f"cs_mock_{bill_id}"
    # The checkout URL would normally be the Stripe-hosted page.  We return a
    # mock URL so the frontend has something to display / redirect to.
    checkout_url = (
        f"https://checkout.stripe.mock/pay/{session_id}"
        f"?amount={bill.amount:.2f}&currency=usd"
    )

    log_action(
        db,
        current_user["sub"],
        "STRIPE_CHECKOUT_CREATED",
        "Billing",
        str(bill.id),
        details=f"mock checkout session created, amount={bill.amount}",
    )

    return CheckoutSessionResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        bill_id=str(bill_id),
        amount=bill.amount,
    )


@router.post("/webhook")
def stripe_webhook(
    event: MockWebhookEvent,
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    """Handle a Stripe webhook event (mock).

    In production you would:
    1. Verify the ``Stripe-Signature`` header using ``stripe.Webhook.construct_event``
       with ``STRIPE_WEBHOOK_SECRET`` (the per-endpoint signing secret from the
       Stripe dashboard) — that call both authenticates the request and
       confirms the payload wasn't tampered with in transit.
    2. Handle only known event types (``checkout.session.completed``, etc.).
    3. Use idempotency keys to guard against duplicate delivery.

    This mock can't do real signature verification (there's no live key to
    sign with), so it checks a simpler stand-in instead: the caller must
    send the same shared secret back in ``X-Webhook-Secret``. It's not
    cryptographic proof the payload is untampered the way a real Stripe
    signature is, but it closes the actual hole this mock had — an
    unauthenticated POST from anyone who finds the URL — and the call site
    swaps cleanly to ``stripe.Webhook.construct_event`` later.
    """
    if not STRIPE_WEBHOOK_SECRET or x_webhook_secret != STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")

    if event.type != "checkout.session.completed":
        # Stripe sends many event types; silently ignore unhandled ones.
        return {"received": True, "action": "ignored", "event_type": event.type}

    bill_id_str = event.data.object.metadata.bill_id
    try:
        bill_id = UUID(bill_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid bill_id in metadata: {bill_id_str}")

    bill = (
        db.query(Billing)
        .options(joinedload(Billing.line_items))
        .filter(Billing.id == bill_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Billing record not found")

    if bill.status == "paid":
        # Idempotent: Stripe can deliver a webhook more than once.
        return {"received": True, "action": "already_paid", "bill_id": bill_id_str}

    try:
        validate_status_transition(bill.status, "paid")
    except InvalidStatusTransition as e:
        raise HTTPException(status_code=422, detail=str(e))

    bill.status = "paid"
    bill.method = "online"
    db.commit()

    # Log with user_id="stripe_webhook" — no authenticated user in webhook calls.
    log_action(
        db,
        user_id="stripe_webhook",
        action="STRIPE_PAYMENT_COMPLETED",
        entity="Billing",
        entity_id=str(bill.id),
        details=f"bill marked paid via mock Stripe webhook, amount={bill.amount}",
    )

    return {"received": True, "action": "marked_paid", "bill_id": bill_id_str}
