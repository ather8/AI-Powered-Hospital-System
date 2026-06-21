"""Tests for app/routes/stripe_mock.py: checkout-session creation and the
mock webhook that marks a bill paid.

Same layering convention as test_billing.py: a minimal standalone FastAPI
app mounting only the stripe_mock router (not app.main, so importing this
test module doesn't pull in the AI dependency stack), a real SQLite
in-memory database, and auth bypassed via dependency_overrides on
get_current_user (require_roles wraps it, so overriding the underlying
function is what actually takes effect — see the long comment on
app_client in test_billing.py for why patch() doesn't work here).
"""
import pytest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.billing import Billing, BillingLineItem
from app.models.patient import Patient
from app.models.user import User
from app.config import STRIPE_WEBHOOK_SECRET


@pytest.fixture(scope="module")
def engine():
    # StaticPool: see test_billing.py's identical fixture for why this
    # matters with TestClient's threaded request handling + SQLite memory DBs.
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.query(BillingLineItem).delete()
    session.query(Billing).delete()
    session.query(Patient).delete()
    session.query(User).delete()
    session.commit()
    session.close()


class _StripeTestClient:
    """Thin TestClient wrapper with an as_role() context manager, identical
    in spirit to _BillingTestClient in test_billing.py."""

    def __init__(self, app, client, get_current_user_fn):
        self.app = app
        self.client = client
        self._get_current_user = get_current_user_fn

    def as_role(self, role: str, sub: str = "1"):
        return _as_role(self.app, self._get_current_user, role, sub)

    def get(self, *a, **k):
        return self.client.get(*a, **k)

    def post(self, *a, **k):
        return self.client.post(*a, **k)


@pytest.fixture
def app_client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import stripe_mock as stripe_routes
    from app.db import get_db
    from app.utils.dependencies import get_current_user

    app = FastAPI()
    app.include_router(stripe_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    return _StripeTestClient(app, TestClient(app), get_current_user)


def _user(role: str, sub: str = "1") -> dict:
    return {"role": role, "sub": sub}


class _as_role:
    def __init__(self, app, get_current_user_fn, role: str, sub: str = "1"):
        self.app = app
        self.key = get_current_user_fn
        self.role = role
        self.sub = sub
        self._previous = None

    def __enter__(self):
        self._previous = self.app.dependency_overrides.get(self.key)
        self.app.dependency_overrides[self.key] = lambda: _user(self.role, self.sub)
        return self

    def __exit__(self, *exc):
        if self._previous is None:
            self.app.dependency_overrides.pop(self.key, None)
        else:
            self.app.dependency_overrides[self.key] = self._previous


@pytest.fixture
def patient_with_user(db):
    user = User(id=1, email="p1@example.com", hashed_password="x", role="patient")
    db.add(user)
    db.commit()
    patient = Patient(id=uuid4(), user_id=user.id, name="Jane Doe")
    db.add(patient)
    db.commit()
    return patient


def _make_unpaid_bill(db, patient, amount=100.0) -> Billing:
    bill = Billing(id=uuid4(), patient_id=patient.id, subtotal=amount, amount=amount, status="unpaid")
    bill.line_items = [BillingLineItem(description="Consultation", quantity=1, unit_price=amount)]
    db.add(bill)
    db.commit()
    return bill


# ---------------------------------------------------------------------------
# POST /billing/stripe/checkout/{bill_id}
# ---------------------------------------------------------------------------

class TestCreateCheckoutSession:
    def test_patient_can_checkout_own_unpaid_bill(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user, amount=150.0)
        with app_client.as_role("patient", sub="1"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["bill_id"] == str(bill.id)
        assert body["amount"] == 150.0
        assert body["session_id"] == f"cs_mock_{bill.id}"
        assert body["checkout_url"].startswith("https://checkout.stripe.mock/pay/")
        assert body["session_id"] in body["checkout_url"]

    def test_receptionist_can_checkout_any_patients_bill(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        with app_client.as_role("receptionist"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 200

    def test_patient_cannot_checkout_another_patients_bill(self, app_client, db, patient_with_user):
        other_user = User(id=2, email="p2@example.com", hashed_password="x", role="patient")
        db.add(other_user)
        db.commit()
        other_patient = Patient(id=uuid4(), user_id=other_user.id, name="John Roe")
        db.add(other_patient)
        db.commit()
        bill = _make_unpaid_bill(db, other_patient)

        with app_client.as_role("patient", sub="1"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 403

    def test_doctor_cannot_create_checkout_session(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        with app_client.as_role("doctor"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 403

    def test_already_paid_bill_cannot_be_checked_out(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        bill.status = "paid"
        db.commit()
        with app_client.as_role("patient", sub="1"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 400

    def test_cancelled_bill_cannot_be_checked_out(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        bill.status = "cancelled"
        db.commit()
        with app_client.as_role("patient", sub="1"):
            r = app_client.post(f"/billing/stripe/checkout/{bill.id}")
        assert r.status_code == 400

    def test_unknown_bill_returns_404(self, app_client, patient_with_user):
        with app_client.as_role("patient", sub="1"):
            r = app_client.post(f"/billing/stripe/checkout/{uuid4()}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /billing/stripe/webhook
# ---------------------------------------------------------------------------

def _webhook_event(bill_id) -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"bill_id": str(bill_id)}}},
    }


class TestStripeWebhook:
    def test_missing_secret_header_is_rejected(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        r = app_client.post("/billing/stripe/webhook", json=_webhook_event(bill.id))
        assert r.status_code == 401
        db.refresh(bill)
        assert bill.status == "unpaid"

    def test_wrong_secret_header_is_rejected(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        r = app_client.post(
            "/billing/stripe/webhook",
            json=_webhook_event(bill.id),
            headers={"X-Webhook-Secret": "totally-wrong"},
        )
        assert r.status_code == 401
        db.refresh(bill)
        assert bill.status == "unpaid"

    def test_correct_secret_marks_bill_paid(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        r = app_client.post(
            "/billing/stripe/webhook",
            json=_webhook_event(bill.id),
            headers={"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "marked_paid"
        db.refresh(bill)
        assert bill.status == "paid"
        assert bill.method == "online"

    def test_webhook_is_idempotent_on_already_paid_bill(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        headers = {"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET}
        first = app_client.post("/billing/stripe/webhook", json=_webhook_event(bill.id), headers=headers)
        second = app_client.post("/billing/stripe/webhook", json=_webhook_event(bill.id), headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["action"] == "already_paid"

    def test_unhandled_event_type_is_ignored(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        event = _webhook_event(bill.id)
        event["type"] = "charge.refunded"
        r = app_client.post(
            "/billing/stripe/webhook",
            json=event,
            headers={"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET},
        )
        assert r.status_code == 200
        assert r.json()["action"] == "ignored"
        db.refresh(bill)
        assert bill.status == "unpaid"

    def test_unknown_bill_id_returns_404(self, app_client):
        r = app_client.post(
            "/billing/stripe/webhook",
            json=_webhook_event(uuid4()),
            headers={"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET},
        )
        assert r.status_code == 404

    def test_malformed_bill_id_returns_400(self, app_client):
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"bill_id": "not-a-uuid"}}},
        }
        r = app_client.post(
            "/billing/stripe/webhook",
            json=event,
            headers={"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET},
        )
        assert r.status_code == 400

    def test_cancelled_bill_rejects_payment(self, app_client, db, patient_with_user):
        bill = _make_unpaid_bill(db, patient_with_user)
        bill.status = "cancelled"
        db.commit()
        r = app_client.post(
            "/billing/stripe/webhook",
            json=_webhook_event(bill.id),
            headers={"X-Webhook-Secret": STRIPE_WEBHOOK_SECRET},
        )
        assert r.status_code == 422
