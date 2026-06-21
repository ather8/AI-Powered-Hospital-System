from pydantic import BaseModel, ConfigDict
from datetime import date
from uuid import UUID


class PatientCreate(BaseModel):
    name: str
    dob: date | None = None
    phone: str | None = None
    address: str | None = None
    # Only used when an admin or receptionist creates a profile on behalf of
    # a patient. When the caller is a patient, the route ignores this field
    # and binds user_id to the authenticated user's own JWT sub instead
    # (preventing IDOR). When the caller is admin/receptionist, this field
    # is required (enforced in the route, not here, so the error message
    # can be role-aware).
    user_id: int | None = None


class PatientUpdate(BaseModel):
    name: str | None = None
    dob: date | None = None
    phone: str | None = None
    address: str | None = None


class PatientResponse(BaseModel):
    id: UUID
    name: str
    dob: date | None
    phone: str | None
    address: str | None

    model_config = ConfigDict(from_attributes=True)
