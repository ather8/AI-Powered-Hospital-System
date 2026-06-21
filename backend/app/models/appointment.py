from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default="scheduled")  # scheduled, completed, cancelled
    # Department the appointment belongs to (e.g. "Cardiology", "General").
    # Nullable so existing rows and appointments booked without an explicit
    # department remain valid. The analytics query groups by this field —
    # NULL rows appear under a "Unknown" bucket rather than being silently
    # dropped (see services/analytics.py).
    department = Column(String, nullable=True)