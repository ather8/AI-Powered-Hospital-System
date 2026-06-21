from app.services.ocr import extract_text_from_image
from app.services.ai_summary import summarize_medical_report

async def ocr_and_summarize(file_bytes: bytes) -> dict:
    """
    Extract text from image/PDF using OCR, then summarize with AI.
    """
    text = extract_text_from_image(file_bytes)
    summary = summarize_medical_report(text)
    return {"extracted_text": text, "summary": summary["summary"]}
