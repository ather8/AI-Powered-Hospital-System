from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class AppointmentCreate(BaseModel):
    # Optional: for "patient"-role bookings, the server resolves this from
    # the authenticated user's own Patient profile rather than trusting a
    # client-supplied value (see routes/appointment.py). Receptionists,
    # who book on behalf of a patient, must supply it explicitly.
    patient_id: UUID | None = None
    doctor_id: UUID
    scheduled_time: datetime
    # Optional department label supplied at booking time (e.g. "Cardiology").
    # When omitted the analytics service falls back to "Unknown" so no row
    # is silently dropped from department-level breakdowns.
    department: str | None = None


class AppointmentUpdate(BaseModel):
    scheduled_time: datetime | None = None
    status: str | None = None
    department: str | None = None


class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    scheduled_time: datetime
    status: str
    department: str | None = None

    model_config = ConfigDict(from_attributes=True)