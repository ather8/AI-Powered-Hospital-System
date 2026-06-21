from fastapi import APIRouter, UploadFile, File, Depends, Request
from app.services.ocr import extract_text_from_image
from app.utils.rbac import require_roles
from app.utils.rate_limit import limiter, RATE_OCR

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/extract")
@limiter.limit(RATE_OCR)
async def ocr_extract(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(["doctor", "nurse", "admin"])),
):
    """Extract text from an uploaded image via Tesseract OCR.
    Rate-limited per user — OCR is CPU-heavy and file uploads can be large.
    """
    file_bytes = await file.read()
    text = extract_text_from_image(file_bytes)
    return {"extracted_text": text}
