from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class EMRCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    diagnosis: str
    prescription: str | None = None
    lab_results: str | None = None


class EMRUpdate(BaseModel):
    diagnosis: str | None = None
    prescription: str | None = None
    lab_results: str | None = None


class EMRResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    diagnosis: str
    prescription: str | None
    lab_results: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)