from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from app.services.audit import log_action
from app.utils.rbac import require_roles
from app.utils.pagination import PageParams, PagedResponse


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/", response_model=PatientResponse)
def create_patient(
    request: PatientCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "admin", "receptionist"])),
):
    """Create a patient profile.

    - Patients create their own profile (user_id bound to their JWT sub).
    - Admins and receptionists can create a profile on behalf of a patient
      during intake; they must supply user_id explicitly in the request body.
    """
    if current_user["role"] == "patient":
        user_id = int(current_user["sub"])
        # A user can only ever have one Patient record. Every /me-style
        # endpoint (billing/me, emrs/me) and the appointment-booking flow
        # all do `.filter(Patient.user_id == ...).first()` — a second row
        # for the same user would silently become unreachable through any
        # of those paths, so block it here rather than let it happen.
        existing = db.query(Patient).filter(Patient.user_id == user_id).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="A patient profile already exists for this account.",
            )
    else:
        if request.user_id is None:
            raise HTTPException(
                status_code=400,
                detail="user_id is required when creating a patient profile on behalf of another user.",
            )
        user_id = request.user_id

    patient = Patient(user_id=user_id, **{k: v for k, v in request.model_dump().items() if k != "user_id"})
    db.add(patient)
    db.commit()
    log_action(db, current_user["sub"], "CREATE_PATIENT", "Patient", str(patient.id), details="Patient profile created")
    db.refresh(patient)
    return patient


@router.get("/", response_model=PagedResponse[PatientResponse])
def list_patients(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin", "doctor", "nurse", "receptionist"])),
    page: PageParams = Depends(),
):
    """List patients with cursor-style pagination.

    Not accessible by patient role — patients use GET /patients/{id} to see
    only their own record.

    Returns a paginated envelope with `data` and `meta` fields so the
    frontend can render page controls without a separate count request.
    """
    query = db.query(Patient).order_by(Patient.id)
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    return PagedResponse.create(items, total, page)


# Registered before /{patient_id} for the same reason as billing's and
# emrs' sibling /me endpoints: route matching is order-sensitive, and
# "me" would otherwise be swallowed by the {patient_id} path param.
@router.get("/me", response_model=PatientResponse)
def get_my_patient_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient"])),
):
    """Get the current logged-in patient's own profile.

    Returns 404 if the patient hasn't created a profile yet — the frontend
    uses this to decide whether to show a "create your profile" prompt
    before letting the patient book an appointment.
    """
    patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient profile found for this account.")
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["doctor", "nurse", "patient", "admin", "receptionist"])),
):
    """Get a single patient record.

    - Patients may only fetch their own record (ownership enforced below).
    - All clinical/admin staff can fetch any record.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current_user["role"] == "patient" and patient.user_id != int(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Access Forbidden")
    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: str,
    request: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "admin"])),
):
    """Update a patient record.

    - Patients may only update their own record.
    - Admins may update any record.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current_user["role"] == "patient" and patient.user_id != int(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Access Forbidden")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    db.commit()
    log_action(db, current_user["sub"], "UPDATE_PATIENT", "Patient", str(patient.id), details="Patient profile updated")
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["patient", "admin"])),
):
    """Delete a patient record.

    - Patients may delete their own profile (account closure).
    - Admins may delete any profile (data governance, GDPR erasure).
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current_user["role"] == "patient" and patient.user_id != int(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Access Forbidden")
    db.delete(patient)
    log_action(db, current_user["sub"], "DELETE_PATIENT", "Patient", str(patient.id), details="Patient profile deleted")
    db.commit()
    return {"detail": "Patient deleted successfully"}
