from pydantic import BaseModel
from typing import Optional, Tuple
from datetime import date


class PatientSearchRequest(BaseModel):
    name: Optional[str] = None
    # `age` and `gender` were previously accepted here but Patient has no
    # such columns (see models/patient.py: id, user_id, name, dob, phone,
    # address) — any search using them raised an unhandled AttributeError
    # in services/search.py, surfaced to the client as a generic 500.
    # dob/phone are real columns and useful disambiguators when two
    # patients share a name.
    dob: Optional[date] = None
    phone: Optional[str] = None


class AppointmentSearchRequest(BaseModel):
    # No one — admin included — has a doctor's UUID memorized. Search by
    # name instead; the service resolves it to doctor_id(s) internally.
    doctor_name: Optional[str] = None
    date: Optional[str] = None
    # `department` was previously accepted here but Appointment has no
    # such column (see models/appointment.py: id, patient_id, doctor_id,
    # scheduled_time, status) — using it raised an unhandled
    # AttributeError. `status` is a real column and a useful filter.
    status: Optional[str] = None


class EMRSearchRequest(BaseModel):
    # Same reasoning as AppointmentSearchRequest.doctor_name: search by
    # patient name, not a UUID no one can recall.
    patient_name: Optional[str] = None
    diagnosis: Optional[str] = None
    date_range: Optional[Tuple[str, str]] = None
