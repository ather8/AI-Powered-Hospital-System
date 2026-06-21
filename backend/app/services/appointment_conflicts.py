"""Appointment conflict detection.

A "conflict" means a doctor already has a *scheduled* (non-cancelled,
non-completed) appointment whose time window overlaps the requested slot.

Default slot duration is 30 minutes — long enough to cover a standard
GP visit without accidentally blocking half a day. It is intentionally
overridable via the APPOINTMENT_SLOT_MINUTES environment variable so
the value can be tuned per deployment without a code change.

Why keep this in a service rather than inline in the route?
  - The same check must run on both CREATE and UPDATE (rescheduling).
  - The availability query is reused by the GET /appointments/available
    endpoint so the frontend can grey-out taken slots before the user
    even submits the form.
  - Unit-testable in isolation without standing up a full FastAPI app.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment

# Slot length in minutes. Each appointment is assumed to occupy this window;
# any new booking whose window overlaps an existing window is rejected.
SLOT_MINUTES: int = int(os.getenv("APPOINTMENT_SLOT_MINUTES", "30"))


def _slot_window(t: datetime) -> tuple[datetime, datetime]:
    """Return (start, end) for a slot beginning at *t*."""
    # Normalise to UTC-aware if the value is naive (SQLite/some drivers
    # store naive datetimes even when the original was timezone-aware).
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t, t + timedelta(minutes=SLOT_MINUTES)


def has_conflict(
    db: Session,
    doctor_id: UUID,
    scheduled_time: datetime,
    exclude_appointment_id: UUID | None = None,
) -> bool:
    """Return True if *doctor_id* already has a scheduled appointment whose
    slot overlaps the requested *scheduled_time* slot.

    *exclude_appointment_id* should be the id of the appointment being
    updated so we don't flag the appointment as conflicting with itself
    when only its department or status is being changed.

    Overlap condition (two intervals [a,b) and [c,d) overlap when a < d
    and c < b):
        existing_start  < new_end   AND   new_start  < existing_end
    Which in terms of our fixed-width slots is:
        existing_time   < new_time + SLOT_MINUTES
        AND
        new_time        < existing_time + SLOT_MINUTES
    """
    new_start, new_end = _slot_window(scheduled_time)

    query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        # Only active (not yet cancelled/completed) appointments block a slot.
        Appointment.status == "scheduled",
        # Overlap: existing slot starts before new slot ends …
        Appointment.scheduled_time < new_end,
        # … and new slot starts before existing slot ends.
        Appointment.scheduled_time >= new_start - timedelta(minutes=SLOT_MINUTES),
    )

    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)

    return db.query(query.exists()).scalar()


def available_slots(
    db: Session,
    doctor_id: UUID,
    date: datetime,
    working_hours: tuple[int, int] = (8, 18),
) -> list[datetime]:
    """Return all free slot start-times for *doctor_id* on the calendar day
    of *date* (in UTC), between *working_hours* (inclusive start, exclusive end).

    This is used by GET /appointments/available so the frontend can render
    a time-picker that only shows open slots, preventing the user from
    selecting a time they'll immediately be rejected for.
    """
    day_start = date.replace(hour=working_hours[0], minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    day_end = date.replace(hour=working_hours[1], minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

    slots: list[datetime] = []
    current = day_start
    while current < day_end:
        if not has_conflict(db, doctor_id, current):
            slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)
    return slots
