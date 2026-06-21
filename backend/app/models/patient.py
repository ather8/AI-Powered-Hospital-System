from sqlalchemy import Column, String, Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # users.id is an Integer primary key (see models/user.py), so this FK
    # must be Integer too — it was previously UUID, which can never match
    # and would fail at insert/query time.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    dob = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)