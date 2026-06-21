from pydantic import BaseModel

class OCRSummaryResponse(BaseModel):
    extracted_text: str
    summary: str
