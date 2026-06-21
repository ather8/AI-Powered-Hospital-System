from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.doctor import DoctorCreate, DoctorUpdate, DoctorResponse
from app.services.audit import log_action
from app.utils.rbac import require_roles
from app.utils.pagination import PageParams, PagedResponse


router = APIRouter(
    prefix="/doctors",
    tags=["doctors"]
)


def _validate_user_link(db: Session, user_id: int | None, *, exclude_doctor_id: str | None = None) -> None:
    """Guard for create/update: user_id, if given, must point at a real User
    with role="doctor", and that User must not already be linked to a
    different Doctor row (keeps the mapping 1:1)."""
    if user_id is None:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "doctor":
        raise HTTPException(status_code=400, detail="user_id must reference a User with role='doctor'")
    existing = db.query(Doctor).filter(Doctor.user_id == user_id).first()
    if existing and str(existing.id) != str(exclude_doctor_id):
        raise HTTPException(status_code=400, detail="This user account is already linked to another doctor profile")


@router.get("/unlinked-users")
def list_unlinked_doctor_users(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    """Doctor-role User accounts not yet linked to a Doctor profile —
    powers the "link account" dropdown on the admin Doctors page."""
    linked_ids = {d.user_id for d in db.query(Doctor.user_id).filter(Doctor.user_id.isnot(None)).all()}
    users = db.query(User).filter(User.role == "doctor").all()
    return [{"id": u.id, "email": u.email} for u in users if u.id not in linked_ids]


@router.post("/", response_model=DoctorResponse)
def create_doctor(request: DoctorCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    _validate_user_link(db, request.user_id)
    doctor = Doctor(**request.model_dump())
    db.add(doctor)
    db.commit()
    log_action(db, current_user["sub"], "CREATE_DOCTOR", "Doctor", str(doctor.id), details="Doctor profile created")
    db.refresh(doctor)
    return doctor


@router.get("/", response_model=PagedResponse[DoctorResponse])
def list_doctors(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "receptionist", "doctor", "nurse", "patient"])),
    page: PageParams = Depends(),
):
    """List doctors with pagination.

    All authenticated roles can list doctors (used for booking dropdowns,
    staff directories, etc.). Results are paginated; the frontend should
    use `meta.has_next` to determine whether to show a "load more" control.
    """
    query = db.query(Doctor).order_by(Doctor.name)
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    return PagedResponse.create(items, total, page)


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(doctor_id: str, request: DoctorUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    data = request.model_dump(exclude_unset=True)
    if "user_id" in data:
        _validate_user_link(db, data["user_id"], exclude_doctor_id=doctor_id)
    for key, value in data.items():
        setattr(doctor, key, value)
    db.commit()
    log_action(db, current_user["sub"], "UPDATE_DOCTOR", "Doctor", str(doctor.id), details="Doctor profile updated")
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: str, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    db.delete(doctor)
    db.commit()
    log_action(db, current_user["sub"], "DELETE_DOCTOR", "Doctor", str(doctor.id), details="Doctor profile deleted")
    return {"message": "Doctor deleted"}
