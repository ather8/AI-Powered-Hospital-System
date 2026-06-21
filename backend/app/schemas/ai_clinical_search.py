from pydantic import BaseModel

class ClinicalSearchRequest(BaseModel):
    query: str

class ClinicalSearchResponse(BaseModel):
    answer: str
