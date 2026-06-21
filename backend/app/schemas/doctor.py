from pydantic import BaseModel, ConfigDict
from uuid import UUID


class DoctorCreate(BaseModel):
    name: str
    specialty: str
    experience_years: int | None = None
    # Optional User account (must have role="doctor") to link this profile
    # to, so the doctor can see their own appointments/patients/dashboard
    # stats. Admins choose this from a list of doctor-role users.
    user_id: int | None = None


class DoctorUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    experience_years: int | None = None
    available: bool | None = None
    user_id: int | None = None


class DoctorResponse(BaseModel):
    id: UUID
    name: str
    specialty: str
    experience_years: int | None
    available: bool
    user_id: int | None

    model_config = ConfigDict(from_attributes=True)