from fastapi import APIRouter, Depends, Request
from app.schemas.ai_summary import ReportRequest, ReportSummary
from app.services.ai_summary import summarize_medical_report
from app.utils.rbac import require_roles
from app.utils.rate_limit import limiter, RATE_AI_SUMMARY

router = APIRouter(prefix="/ai-summary", tags=["AI Summary"])


@router.post("/", response_model=ReportSummary)
@limiter.limit(RATE_AI_SUMMARY)
def summarize_report(
    request: Request,
    body: ReportRequest,
    current_user: dict = Depends(require_roles(["doctor", "nurse", "admin"])),
):
    summary = summarize_medical_report(body.report_text)
    return summary
