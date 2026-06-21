from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.emr import EMR
from app.services.ocr import extract_text_from_image

def save_ocr_to_emr(file_bytes: bytes, patient_id: str, doctor_id: str, db: Session) -> EMR:
    """
    Extract text from image and store it as an EMR record.
    """
    text = extract_text_from_image(file_bytes)
    emr = EMR(
        patient_id=patient_id,
        doctor_id=doctor_id,
        diagnosis=text,   # OCR text stored as diagnosis (can be refined later)
        created_at=datetime.now(timezone.utc)  # Fixed: was datetime.now(datetime.UTC) — datetime.UTC
                                                # doesn't exist on the class, only on the module
    )
    db.add(emr)
    db.commit()
    db.refresh(emr)
    return emr
