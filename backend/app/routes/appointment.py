from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentResponse
from app.services.audit import log_action
from app.services.appointment_conflicts import has_conflict, available_slots, SLOT_MINUTES
from app.utils.rbac import require_roles
from app.utils.pagination import PageParams, PagedResponse


router = APIRouter(
    prefix="/appointments",
    tags=["appointments"]
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_no_conflict(
    db: Session,
    doctor_id,
    scheduled_time: datetime,
    exclude_id=None,
) -> None:
    """Raise HTTP 409 if the requested slot conflicts with an existing booking."""
    if has_conflict(db, doctor_id, scheduled_time, exclude_appointment_id=exclude_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"This doctor already has a scheduled appointment within "
                f"{SLOT_MINUTES} minutes of {scheduled_time.isoformat()}. "
                f"Please choose a different time."
            ),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=AppointmentResponse)
def create_appointment(
    request: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "receptionist"])),
):
    data = request.model_dump()

    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
        if not patient:
            raise HTTPException(status_code=400, detail="Create your patient profile before booking an appointment.")
        data["patient_id"] = patient.id
    elif not data.get("patient_id"):
        raise HTTPException(status_code=400, detail="patient_id is required.")

    _assert_no_conflict(db, data["doctor_id"], data["scheduled_time"])

    appointment = Appointment(**data)
    db.add(appointment)
    db.commit()
    log_action(db, current_user["sub"], "CREATE_APPOINTMENT", "Appointment", str(appointment.id), details="appointment created")
    db.refresh(appointment)
    return appointment


@router.get("/available", response_model=list[str])
def get_available_slots(
    doctor_id: str = Query(..., description="Doctor UUID"),
    date: str = Query(..., description="ISO date string, e.g. 2026-07-01"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "receptionist", "admin", "nurse", "doctor"])),
):
    """Return free 30-minute slots for a doctor on a given date (08:00–18:00 UTC)."""
    try:
        parsed_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: '{date}'. Expected ISO date e.g. '2026-07-01'.")

    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")

    slots = available_slots(db, doctor_id, parsed_date)
    return [s.isoformat() for s in slots]


@router.get("/", response_model=PagedResponse[AppointmentResponse])
def list_appointments(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "receptionist", "doctor", "nurse", "patient"])),
    page: PageParams = Depends(),
):
    """List appointments with pagination.

    - Patients see only their own appointments.
    - Doctors (linked to a Doctor profile) see only their own appointments.
    - All other staff see all appointments.

    Pagination applies to all branches so large schedules don't cause
    full-table scans and slow page loads.
    """
    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
        if not patient:
            return PagedResponse.create([], 0, page)
        query = db.query(Appointment).filter(Appointment.patient_id == patient.id)
    elif current_user["role"] == "doctor":
        doctor = db.query(Doctor).filter(Doctor.user_id == int(current_user["sub"])).first()
        if doctor:
            query = db.query(Appointment).filter(Appointment.doctor_id == doctor.id)
        else:
            query = db.query(Appointment)
    else:
        query = db.query(Appointment)

    query = query.order_by(Appointment.scheduled_time.desc())
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    return PagedResponse.create(items, total, page)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: str,
    request: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin", "receptionist", "patient"])),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    update_data = request.model_dump(exclude_unset=True)

    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
        if not patient or appointment.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Access Forbidden")
        if "status" in update_data and update_data["status"] != "cancelled":
            raise HTTPException(
                status_code=403,
                detail="Patients can only cancel their own appointment, not set its status to anything else.",
            )

    new_time = update_data.get("scheduled_time")
    if new_time is not None:
        doctor_id = update_data.get("doctor_id", appointment.doctor_id)
        _assert_no_conflict(db, doctor_id, new_time, exclude_id=appointment.id)

    for key, value in update_data.items():
        setattr(appointment, key, value)
    db.commit()
    log_action(db, current_user["sub"], "UPDATE_APPOINTMENT", "Appointment", str(appointment.id), details="appointment updated")
    db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}")
def delete_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin", "patient"])),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
        if not patient or appointment.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Access Forbidden")

    db.delete(appointment)
    db.commit()
    log_action(db, current_user["sub"], "DELETE_APPOINTMENT", "Appointment", str(appointment.id), details="appointment deleted")
    return {"message": "Appointment deleted"}
