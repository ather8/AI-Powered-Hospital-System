"""Tests for billing: line-item totals, status transitions, and the
/billing routes.

Two layers, matching the convention in test_appointment_conflicts.py
(pure service logic, SQLite-friendly) and test_rbac.py (route-level via
TestClient with auth mocked):

  - TestRecalculateTotals / TestStatusTransitions: pure unit tests against
    app/services/billing.py. No HTTP, no app.main import, so they don't
    pull in the AI dependency stack.
  - TestBillingRoutes: integration tests against the real /billing routes,
    mounted on a minimal standalone FastAPI app (not app.main, to avoid
    importing the AI services) with auth mocked the same way test_rbac.py
    does and a real database session (SQLite in-memory).
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
from app.services.billing import (
    recalculate_totals,
    validate_status_transition,
    InvalidStatusTransition,
)


# ---------------------------------------------------------------------------
# Pure unit tests: recalculate_totals
# ---------------------------------------------------------------------------

class TestRecalculateTotals:
    def test_subtotal_is_sum_of_quantity_times_unit_price(self):
        bill = Billing(tax_amount=0, discount_amount=0)
        bill.line_items = [
            BillingLineItem(description="Consultation", quantity=1, unit_price=120.0),
            BillingLineItem(description="Lab test", quantity=2, unit_price=30.0),
        ]
        recalculate_totals(bill)
        assert bill.subtotal == 180.0
        assert bill.amount == 180.0

    def test_tax_is_added_after_discount(self):
        bill = Billing(tax_amount=10.0, discount_amount=20.0)
        bill.line_items = [BillingLineItem(description="X", quantity=1, unit_price=100.0)]
        recalculate_totals(bill)
        assert bill.subtotal == 100.0
        # (100 - 20) + 10 = 90
        assert bill.amount == 90.0

    def test_discount_cannot_drive_amount_negative(self):
        bill = Billing(tax_amount=0, discount_amount=500.0)
        bill.line_items = [BillingLineItem(description="X", quantity=1, unit_price=50.0)]
        recalculate_totals(bill)
        # discount exceeds subtotal -> floored at 0 before tax is added
        assert bill.amount == 0.0

    def test_no_line_items_gives_zero_subtotal(self):
        bill = Billing(tax_amount=5.0, discount_amount=0)
        bill.line_items = []
        recalculate_totals(bill)
        assert bill.subtotal == 0.0
        assert bill.amount == 5.0


# ---------------------------------------------------------------------------
# Pure unit tests: validate_status_transition
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    @pytest.mark.parametrize("frm,to", [
        ("unpaid", "partially_paid"),
        ("unpaid", "paid"),
        ("unpaid", "cancelled"),
        ("partially_paid", "paid"),
        ("partially_paid", "cancelled"),
    ])
    def test_allowed_transitions(self, frm, to):
        validate_status_transition(frm, to)  # should not raise

    @pytest.mark.parametrize("frm,to", [
        ("paid", "unpaid"),
        ("paid", "partially_paid"),
        ("cancelled", "unpaid"),
        ("cancelled", "paid"),
        ("partially_paid", "unpaid"),
    ])
    def test_disallowed_transitions_raise(self, frm, to):
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition(frm, to)

    def test_unknown_status_raises(self):
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("unpaid", "refunded")

    @pytest.mark.parametrize("status", ["unpaid", "partially_paid", "paid", "cancelled"])
    def test_transition_to_self_is_a_noop(self, status):
        validate_status_transition(status, status)  # should not raise


# ---------------------------------------------------------------------------
# Route-level integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    # StaticPool is required here, not just check_same_thread=False:
    # FastAPI's TestClient runs each request's dependant.call in a
    # worker thread (run_in_threadpool). With the default pool class,
    # a SQLite ":memory:" engine hands out a brand-new, empty database
    # per physical connection -- so a connection opened from the worker
    # thread would see none of the tables created on the main thread.
    # StaticPool forces the whole engine to share a single underlying
    # connection across all threads, which is what makes the in-memory
    # DB actually behave like one shared database for these tests.
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


class _BillingTestClient:
    """Thin wrapper around TestClient that adds an as_role() context
    manager for swapping the authenticated user via dependency_overrides.
    HTTP verb methods pass straight through to the underlying TestClient.
    """

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

    def put(self, *a, **k):
        return self.client.put(*a, **k)

    def delete(self, *a, **k):
        return self.client.delete(*a, **k)


@pytest.fixture
def app_client(db):
    """A minimal FastAPI app mounting only the billing router, with
    get_db overridden to the test session.

    Auth is bypassed via app.dependency_overrides[get_current_user], not
    unittest.mock.patch. require_roles([...]) is evaluated once, at import
    time, as a default-argument expression in each route signature -- by
    the time any test runs, FastAPI has already captured the *function
    object* `get_current_user` inside its dependant tree. Patching the
    `get_current_user` name on either app.utils.dependencies or
    app.utils.rbac afterwards does not change that already-captured
    reference, so request-time mock.patch has no effect (verified: routes
    still 401 under patch). dependency_overrides keys off the actual
    function object FastAPI resolved, which does work.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import billing as billing_routes
    from app.db import get_db
    from app.utils.dependencies import get_current_user

    app = FastAPI()
    app.include_router(billing_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    return _BillingTestClient(app, TestClient(app), get_current_user)


def _user(role: str, sub: str = "1") -> dict:
    return {"role": role, "sub": sub}


class _as_role:
    """Context manager: set app.dependency_overrides[get_current_user] for
    the duration of the block, then restore whatever was there before.
    Usage: with _as_role(app, get_current_user, "admin"): client.get(...)
    """
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
    """A User+Patient pair linked the way /billing/me expects."""
    user = User(id=1, email="p1@example.com", hashed_password="x", role="patient")
    db.add(user)
    db.commit()
    patient = Patient(id=uuid4(), user_id=user.id, name="Jane Doe")
    db.add(patient)
    db.commit()
    return patient


class TestCreateBill:
    def test_create_with_line_items_computes_total(self, app_client, patient_with_user):
        payload = {
            "patient_id": str(patient_with_user.id),
            "line_items": [
                {"description": "Consultation", "quantity": 1, "unit_price": 120.0},
                {"description": "X-ray", "quantity": 1, "unit_price": 80.0},
            ],
            "tax_amount": 10.0,
            "discount_amount": 20.0,
            "method": "card",
        }
        with app_client.as_role("receptionist"):
            r = app_client.post("/billing/", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["subtotal"] == 200.0
        assert body["amount"] == 190.0  # 200 - 20 + 10
        assert body["status"] == "unpaid"
        assert len(body["line_items"]) == 2

    def test_create_requires_at_least_one_line_item(self, app_client, patient_with_user):
        payload = {"patient_id": str(patient_with_user.id), "line_items": []}
        with app_client.as_role("admin"):
            r = app_client.post("/billing/", json=payload)
        assert r.status_code == 422

    def test_create_rejects_unknown_payment_method(self, app_client, patient_with_user):
        payload = {
            "patient_id": str(patient_with_user.id),
            "line_items": [{"description": "X", "quantity": 1, "unit_price": 10.0}],
            "method": "venmo",
        }
        with app_client.as_role("admin"):
            r = app_client.post("/billing/", json=payload)
        assert r.status_code == 422

    def test_patient_cannot_create_bill(self, app_client, patient_with_user):
        payload = {
            "patient_id": str(patient_with_user.id),
            "line_items": [{"description": "X", "quantity": 1, "unit_price": 10.0}],
        }
        with app_client.as_role("patient"):
            r = app_client.post("/billing/", json=payload)
        assert r.status_code == 403


class TestStatusTransitionRoute:
    def _create_bill(self, app_client, patient):
        payload = {
            "patient_id": str(patient.id),
            "line_items": [{"description": "Consultation", "quantity": 1, "unit_price": 100.0}],
        }
        with app_client.as_role("receptionist"):
            r = app_client.post("/billing/", json=payload)
        return r.json()["id"]

    def test_valid_transition_succeeds(self, app_client, patient_with_user):
        bill_id = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("admin"):
            r = app_client.put(f"/billing/{bill_id}", json={"status": "paid"})
        assert r.status_code == 200
        assert r.json()["status"] == "paid"

    def test_invalid_transition_rejected(self, app_client, patient_with_user):
        bill_id = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("admin"):
            # unpaid -> paid first
            app_client.put(f"/billing/{bill_id}", json={"status": "paid"})
            # paid -> partially_paid should be rejected (terminal state)
            r = app_client.put(f"/billing/{bill_id}", json={"status": "partially_paid"})
        assert r.status_code == 400

    def test_unknown_status_rejected_at_schema_layer(self, app_client, patient_with_user):
        bill_id = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("admin"):
            r = app_client.put(f"/billing/{bill_id}", json={"status": "refunded"})
        assert r.status_code == 422


class TestLineItemRoutes:
    def _create_bill(self, app_client, patient):
        payload = {
            "patient_id": str(patient.id),
            "line_items": [{"description": "Consultation", "quantity": 1, "unit_price": 100.0}],
        }
        with app_client.as_role("receptionist"):
            r = app_client.post("/billing/", json=payload)
        return r.json()

    def test_add_line_item_recomputes_total(self, app_client, patient_with_user):
        bill = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("receptionist"):
            r = app_client.post(
                f"/billing/{bill['id']}/line-items",
                json={"description": "Lab test", "quantity": 1, "unit_price": 50.0},
            )
        assert r.status_code == 200
        assert r.json()["subtotal"] == 150.0
        assert len(r.json()["line_items"]) == 2

    def test_cannot_add_line_item_to_paid_bill(self, app_client, patient_with_user):
        bill = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("admin"):
            app_client.put(f"/billing/{bill['id']}", json={"status": "paid"})
        with app_client.as_role("receptionist"):
            r = app_client.post(
                f"/billing/{bill['id']}/line-items",
                json={"description": "Late add", "quantity": 1, "unit_price": 10.0},
            )
        assert r.status_code == 400

    def test_remove_line_item_recomputes_total(self, app_client, patient_with_user):
        bill = self._create_bill(app_client, patient_with_user)
        with app_client.as_role("receptionist"):
            added = app_client.post(
                f"/billing/{bill['id']}/line-items",
                json={"description": "Lab test", "quantity": 1, "unit_price": 50.0},
            ).json()
            new_item_id = next(li["id"] for li in added["line_items"] if li["description"] == "Lab test")
            r = app_client.delete(f"/billing/{bill['id']}/line-items/{new_item_id}")
        assert r.status_code == 200
        assert r.json()["subtotal"] == 100.0

    def test_cannot_remove_last_line_item(self, app_client, patient_with_user):
        bill = self._create_bill(app_client, patient_with_user)
        only_item_id = bill["line_items"][0]["id"]
        with app_client.as_role("receptionist"):
            r = app_client.delete(f"/billing/{bill['id']}/line-items/{only_item_id}")
        assert r.status_code == 400


class TestBillingMeRoute:
    def test_patient_sees_own_bills_only(self, app_client, db, patient_with_user):
        other_user = User(id=2, email="p2@example.com", hashed_password="x", role="patient")
        db.add(other_user)
        db.commit()
        other_patient = Patient(id=uuid4(), user_id=other_user.id, name="John Roe")
        db.add(other_patient)
        db.commit()

        with app_client.as_role("receptionist"):
            app_client.post("/billing/", json={
                "patient_id": str(patient_with_user.id),
                "line_items": [{"description": "Visit", "quantity": 1, "unit_price": 50.0}],
            })
            app_client.post("/billing/", json={
                "patient_id": str(other_patient.id),
                "line_items": [{"description": "Visit", "quantity": 1, "unit_price": 75.0}],
            })

        with app_client.as_role("patient", sub="1"):
            r = app_client.get("/billing/me")
        assert r.status_code == 200
        bills = r.json()
        assert len(bills) == 1
        assert bills[0]["patient_id"] == str(patient_with_user.id)
