"""Tests for app/services/appointment_conflicts.py

These tests use an in-memory SQLite database so they run without a real
Postgres instance — no docker-compose needed for CI.
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.appointment import Appointment
from app.services.appointment_conflicts import has_conflict, available_slots, SLOT_MINUTES

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    # Clean up appointments between tests
    session.query(Appointment).delete()
    session.commit()
    session.close()


def _make_appointment(db, doctor_id, scheduled_time, status="scheduled"):
    a = Appointment(
        id=uuid4(),
        patient_id=uuid4(),
        doctor_id=doctor_id,
        scheduled_time=scheduled_time,
        status=status,
    )
    db.add(a)
    db.commit()
    return a


BASE_TIME = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# has_conflict
# ---------------------------------------------------------------------------

class TestHasConflict:
    def test_no_conflict_when_empty(self, db):
        assert has_conflict(db, uuid4(), BASE_TIME) is False

    def test_exact_same_time_conflicts(self, db):
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME)
        assert has_conflict(db, doctor_id, BASE_TIME) is True

    def test_overlap_within_slot_conflicts(self, db):
        """Booking 15 min into an occupied 30-min slot should conflict."""
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME)
        assert has_conflict(db, doctor_id, BASE_TIME + timedelta(minutes=15)) is True

    def test_adjacent_slot_does_not_conflict(self, db):
        """Booking exactly SLOT_MINUTES after an existing booking is fine."""
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME)
        next_slot = BASE_TIME + timedelta(minutes=SLOT_MINUTES)
        assert has_conflict(db, doctor_id, next_slot) is False

    def test_one_minute_before_adjacent_conflicts(self, db):
        """Booking one minute before the next clean slot still overlaps."""
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME)
        near = BASE_TIME + timedelta(minutes=SLOT_MINUTES - 1)
        assert has_conflict(db, doctor_id, near) is True

    def test_cancelled_appointment_does_not_block(self, db):
        """Cancelled appointments must not prevent rebooking the same slot."""
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME, status="cancelled")
        assert has_conflict(db, doctor_id, BASE_TIME) is False

    def test_completed_appointment_does_not_block(self, db):
        doctor_id = uuid4()
        _make_appointment(db, doctor_id, BASE_TIME, status="completed")
        assert has_conflict(db, doctor_id, BASE_TIME) is False

    def test_different_doctor_does_not_conflict(self, db):
        """Two different doctors can have appointments at the same time."""
        doctor_a, doctor_b = uuid4(), uuid4()
        _make_appointment(db, doctor_a, BASE_TIME)
        assert has_conflict(db, doctor_b, BASE_TIME) is False

    def test_exclude_own_id_on_update(self, db):
        """Rescheduling to the same time should not conflict with itself."""
        doctor_id = uuid4()
        appt = _make_appointment(db, doctor_id, BASE_TIME)
        # Without exclusion it would conflict with itself
        assert has_conflict(db, doctor_id, BASE_TIME) is True
        # With exclusion it should not
        assert has_conflict(db, doctor_id, BASE_TIME, exclude_appointment_id=appt.id) is False

    def test_multiple_bookings_only_free_slot_passes(self, db):
        """With back-to-back bookings only the truly free slot passes."""
        doctor_id = uuid4()
        t0 = BASE_TIME
        t1 = BASE_TIME + timedelta(minutes=SLOT_MINUTES)
        _make_appointment(db, doctor_id, t0)
        _make_appointment(db, doctor_id, t1)
        t2 = BASE_TIME + timedelta(minutes=SLOT_MINUTES * 2)
        assert has_conflict(db, doctor_id, t0) is True
        assert has_conflict(db, doctor_id, t1) is True
        assert has_conflict(db, doctor_id, t2) is False


# ---------------------------------------------------------------------------
# available_slots
# ---------------------------------------------------------------------------

class TestAvailableSlots:
    def test_fully_free_day_returns_all_slots(self, db):
        doctor_id = uuid4()
        slots = available_slots(db, doctor_id, BASE_TIME)
        # 08:00–18:00 = 10 hours = 600 minutes → 600/SLOT_MINUTES slots
        expected = 600 // SLOT_MINUTES
        assert len(slots) == expected

    def test_booked_slot_excluded_from_available(self, db):
        doctor_id = uuid4()
        booked = datetime(2026, 7, 1, 9, 0, 0, tzinfo=timezone.utc)  # 09:00 UTC
        _make_appointment(db, doctor_id, booked)
        slots = available_slots(db, doctor_id, BASE_TIME)
        assert booked not in slots

    def test_cancelled_slot_still_available(self, db):
        doctor_id = uuid4()
        booked = datetime(2026, 7, 1, 9, 0, 0, tzinfo=timezone.utc)
        _make_appointment(db, doctor_id, booked, status="cancelled")
        slots = available_slots(db, doctor_id, BASE_TIME)
        assert booked in slots
