from fastapi import APIRouter, UploadFile, File, Depends
from app.schemas.ocr_summary import OCRSummaryResponse
from app.services.ocr_summary import ocr_and_summarize
from app.utils.rbac import require_roles

router = APIRouter(prefix="/ocr-summary", tags=["OCR-Summary"])

@router.post("/", response_model=OCRSummaryResponse)
async def ocr_summary(file: UploadFile = File(...), current_user: dict = Depends(require_roles(["doctor", "nurse", "admin"]))):
    file_bytes = await file.read()
    result = await ocr_and_summarize(file_bytes)
    return result
