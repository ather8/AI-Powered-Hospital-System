from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # users.id is an Integer primary key; was incorrectly UUID here.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)   # e.g., CREATE_PATIENT, UPDATE_EMR
    entity = Column(String, nullable=False)   # e.g., Patient, EMR, Billing, User
    # entity_id is polymorphic — most entities (Patient, Doctor, Appointment,
    # EMR, Billing) use UUID ids, but "User" actions (login/logout) use the
    # Integer user id. A strict UUID column rejects the latter, so this is
    # stored as a string and parsed by the caller as needed.
    entity_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(String, nullable=True)   # optional JSON string with extra info
