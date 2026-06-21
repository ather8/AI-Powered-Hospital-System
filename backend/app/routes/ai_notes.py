from fastapi import APIRouter, Depends, Request
from app.schemas.ai_notes import NoteRequest, NoteResponse
from app.services.ai_notes import generate_medical_note
from app.utils.rbac import require_roles
from app.utils.rate_limit import limiter, RATE_AI_NOTES

router = APIRouter(prefix="/ai-notes", tags=["AI Notes"])


@router.post("/", response_model=NoteResponse)
@limiter.limit(RATE_AI_NOTES)
def create_ai_note(
    request: Request,
    body: NoteRequest,
    current_user: dict = Depends(require_roles(["doctor", "nurse"])),
):
    """Generate a structured medical note from free-form text using AI.
    Accessible by doctors and nurses. Rate-limited per user.
    """
    note = generate_medical_note(body.raw_text)
    return note
