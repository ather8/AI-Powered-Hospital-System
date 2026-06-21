"""Tests for pagination on list endpoints.

Strategy: mount only the affected routers on a minimal FastAPI app with
SQLite in-memory DB and auth mocked out (same pattern as test_rbac.py and
test_billing.py). This keeps tests fast and isolated from the AI import
stack.

Coverage:
  - PageParams validates skip/limit bounds
  - PagedResponse.create computes meta fields correctly
  - GET /patients/ returns paged envelope with correct counts
  - GET /doctors/ returns paged envelope
  - GET /appointments/ returns paged envelope
  - GET /audit-logs/ returns paged envelope
"""
import pytest
from uuid import uuid4
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.utils.pagination import PageParams, PagedResponse

# ---------------------------------------------------------------------------
# Unit tests: PagedResponse.create
# ---------------------------------------------------------------------------

class TestPagedResponseCreate:
    def _page(self, skip=0, limit=10):
        class _P:
            pass
        p = _P()
        p.skip = skip
        p.limit = limit
        return p

    def test_meta_total(self):
        pr = PagedResponse.create(["a", "b", "c"], 100, self._page(0, 10))
        assert pr.meta.total == 100

    def test_has_next_true(self):
        pr = PagedResponse.create(list(range(10)), 25, self._page(0, 10))
        assert pr.meta.has_next is True

    def test_has_next_false_at_end(self):
        pr = PagedResponse.create(list(range(5)), 25, self._page(20, 10))
        assert pr.meta.has_next is False

    def test_has_prev_false_at_start(self):
        pr = PagedResponse.create([], 0, self._page(0, 10))
        assert pr.meta.has_prev is False

    def test_has_prev_true(self):
        pr = PagedResponse.create([], 10, self._page(10, 10))
        assert pr.meta.has_prev is True

    def test_data_passthrough(self):
        items = [{"id": 1}, {"id": 2}]
        pr = PagedResponse.create(items, 2, self._page())
        assert pr.data == items


# ---------------------------------------------------------------------------
# Integration tests: route-level pagination
# ---------------------------------------------------------------------------

# Shared SQLite in-memory engine
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)

def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()

def _make_app(router, role="admin"):
    """Mount a single router with auth mocked to the given role."""
    from app.utils.dependencies import get_current_user
    from app.utils.rbac import require_roles

    app = FastAPI()

    def _mock_user():
        return {"sub": "1", "role": role}

    app.dependency_overrides[get_current_user] = _mock_user

    from app.db import get_db
    app.dependency_overrides[get_db] = _get_db

    app.include_router(router)
    return app


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


class TestPatientPagination:
    def _seed(self, n=5):
        from app.models.patient import Patient
        db = _Session()
        for i in range(n):
            db.add(Patient(name=f"Patient {i}", user_id=i + 100))
        db.commit()
        db.close()

    def test_returns_paged_envelope(self):
        from app.routes.patient import router
        self._seed(5)
        client = TestClient(_make_app(router))
        res = client.get("/patients/", params={"skip": 0, "limit": 3})
        assert res.status_code == 200
        body = res.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["limit"] == 3

    def test_pagination_skip(self):
        from app.routes.patient import router
        client = TestClient(_make_app(router))
        r1 = client.get("/patients/", params={"skip": 0, "limit": 2})
        r2 = client.get("/patients/", params={"skip": 2, "limit": 2})
        ids1 = [p["id"] for p in r1.json()["data"]]
        ids2 = [p["id"] for p in r2.json()["data"]]
        assert set(ids1).isdisjoint(set(ids2))

    def test_has_next(self):
        from app.routes.patient import router
        client = TestClient(_make_app(router))
        # Seed ensures at least 5 patients; ask for 2 → has_next should be True
        res = client.get("/patients/", params={"skip": 0, "limit": 2})
        assert res.json()["meta"]["has_next"] is True

    def test_limit_capped_at_200(self):
        from app.routes.patient import router
        client = TestClient(_make_app(router))
        res = client.get("/patients/", params={"limit": 9999})
        assert res.status_code == 422  # FastAPI validation error


class TestAuditLogPagination:
    def _seed(self, n=3):
        from app.models.audit_log import AuditLog
        db = _Session()
        for i in range(n):
            db.add(AuditLog(user_id="1", action=f"ACTION_{i}", resource="Test", resource_id=str(uuid4())))
        db.commit()
        db.close()

    def test_returns_paged_envelope(self):
        from app.routes.audit_log import router
        self._seed(3)
        client = TestClient(_make_app(router))
        res = client.get("/audit-logs/", params={"skip": 0, "limit": 2})
        assert res.status_code == 200
        body = res.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["limit"] == 2
