from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas.search import PatientSearchRequest, AppointmentSearchRequest, EMRSearchRequest
from app.services.search import search_patients, search_appointments, search_emrs
from app.utils.rbac import require_roles

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/patients")
def search_patients_route(request: PatientSearchRequest, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse", "admin"]))):
    return search_patients(db, request.name, request.dob, request.phone)

@router.post("/appointments")
def search_appointments_route(request: AppointmentSearchRequest, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse", "admin", "receptionist"]))):
    return search_appointments(db, request.doctor_name, request.date, request.status)

@router.post("/emrs")
def search_emrs_route(request: EMRSearchRequest, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse", "admin"]))):
    return search_emrs(db, request.patient_name, request.diagnosis, request.date_range)
