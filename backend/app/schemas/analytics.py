from pydantic import BaseModel
from typing import Dict

class AnalyticsResponse(BaseModel):
    total_patients: int
    total_appointments: int
    appointments_by_department: Dict[str, int]
    billing_summary: Dict[str, int]
    diagnosis_counts: Dict[str, int]
