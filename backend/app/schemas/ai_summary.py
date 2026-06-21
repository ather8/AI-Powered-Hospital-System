from pydantic import BaseModel


class ReportRequest(BaseModel):
    report_text: str


class ReportSummary(BaseModel):
    summary: str