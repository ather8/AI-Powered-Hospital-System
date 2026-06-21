from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db import get_db
from app.models.emr import EMR
from app.models.patient import Patient
from app.schemas.emr import EMRCreate, EMRUpdate, EMRResponse
from app.services.audit import log_action
from app.utils.rbac import require_roles


router = APIRouter(
    prefix="/emrs",
    tags=["EMRs"]
)


@router.post("/", response_model=EMRResponse)
def create_emr(request: EMRCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse"]))):
    emr = EMR(**request.model_dump(), created_at=datetime.now(timezone.utc))
    db.add(emr)
    db.commit()
    log_action(db, current_user["sub"], "CREATE_EMR", "EMR", str(emr.id), details="emr created")
    db.refresh(emr)
    return emr


# Registered before /{patient_id} for the same reason as billing's /me:
# route matching is order-sensitive, and "me" would otherwise be swallowed
# by the {patient_id} path param.
@router.get("/me", response_model=list[EMRResponse])
def get_my_emr(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["patient"]))):
    """
    Get EMR records for the current logged-in patient.
    """
    patient = db.query(Patient).filter(Patient.user_id == int(current_user["sub"])).first()
    if not patient:
        return []
    return db.query(EMR).filter(EMR.patient_id == patient.id).all()


@router.get("/{patient_id}", response_model=list[EMRResponse])
def get_patient_emr(patient_id: str, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse", "patient", "admin"]))):
    # Same IDOR pattern fixed elsewhere: a patient must own the record
    # they're requesting, not just hold the "patient" role.
    if current_user["role"] == "patient":
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient or patient.user_id != int(current_user["sub"]):
            raise HTTPException(status_code=403, detail="Access Forbidden")
    records = db.query(EMR).filter(EMR.patient_id == patient_id).all()
    if not records:
        raise HTTPException(status_code=404, detail="EMR not found")
    return records


@router.put("/{emr_id}", response_model=EMRResponse)
def update_emr(emr_id: str, request: EMRUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse"]))):
    emr = db.query(EMR).filter(EMR.id == emr_id).first()
    if not emr:
        raise HTTPException(status_code=404, detail="EMR not found")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(emr, key, value)
    db.commit()
    log_action(db, current_user["sub"], "UPDATE_EMR", "EMR", str(emr.id), details="emr updated")
    db.refresh(emr)
    return emr


@router.delete("/{emr_id}")
def delete_emr(emr_id: str, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    emr = db.query(EMR).filter(EMR.id == emr_id).first()
    if not emr:
        raise HTTPException(status_code=404, detail="EMR not found")
    db.delete(emr)
    db.commit()
    log_action(db, current_user["sub"], "DELETE_EMR", "EMR", str(emr.id), details="emr deleted")
    return {"message": "EMR deleted successfully"}