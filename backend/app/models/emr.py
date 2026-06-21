from sqlalchemy import Column, Text, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base


class EMR(Base):
    __tablename__ = "emrs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    diagnosis = Column(Text, nullable=False)
    # EMRCreate/EMRUpdate schemas allow prescription and lab_results to be
    # omitted (str | None = None) — these must be nullable here too, or
    # inserting a record without them raises a NOT NULL IntegrityError.
    prescription = Column(Text, nullable=True)
    lab_results = Column(Text, nullable=True)
    # Server-side default so created_at is always populated even if a
    # future code path creates an EMR without explicitly passing it.
    created_at = Column(DateTime, nullable=False, server_default=func.now())