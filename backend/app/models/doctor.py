from sqlalchemy import Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Links this Doctor profile to the User account that logs in as this
    # doctor. users.id is an Integer primary key (see models/user.py), so
    # this FK mirrors Patient.user_id. Nullable so existing/legacy Doctor
    # rows created before this link existed don't break, and so admins can
    # create a Doctor profile before the corresponding staff account has
    # registered. unique=True enforces a 1:1 mapping — one User can't be
    # linked to two different Doctor rows.
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    experience_years = Column(Integer, nullable=True)
    available = Column(Boolean, default=True)