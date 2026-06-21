from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.ocr_emr import save_ocr_to_emr
from app.schemas.emr import EMRResponse
from app.utils.rbac import require_roles

router = APIRouter(prefix="/ocr-emr", tags=["OCR-EMR"])

@router.post("/", response_model=EMRResponse)
async def ocr_to_emr(patient_id: str, doctor_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["doctor", "nurse"]))):
    file_bytes = await file.read()
    emr = save_ocr_to_emr(file_bytes, patient_id, doctor_id, db)
    return emr
