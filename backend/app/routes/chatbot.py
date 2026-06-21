# backend/app/routes/chatbot.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.patient_input import PatientInput
from app.services.langchain_chatbot import chatbot_flow, clear_session
from app.utils.rbac import require_roles
from app.utils.rate_limit import limiter, RATE_CHATBOT

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

# All hospital roles can use the triage chatbot.
_CHATBOT_ROLES = ["patient", "doctor", "nurse", "receptionist", "admin"]


@router.post("/conversation")
@limiter.limit(RATE_CHATBOT)
def chatbot_conversation(
    request: Request,
    input: PatientInput,
    current_user: dict = Depends(require_roles(_CHATBOT_ROLES)),
):
    """Triage chatbot — authenticated, rate-limited, and multi-turn.

    **Session management**: include a `session_id` (UUID string) in the
    request body to maintain conversation history across calls. On the first
    request, either omit `session_id` or generate a fresh UUID client-side;
    the server echoes it back in the response so you can reuse it for
    subsequent turns.

    Example multi-turn flow::

        POST /chatbot/conversation
        {"name": "Alice", "age": 32, "symptoms": "chest pain", "session_id": null}
        → {"conversation_reply": "How long have you had chest pain?",
           "session_id": "a1b2c3d4-..."}

        POST /chatbot/conversation
        {"name": "Alice", "age": 32, "symptoms": "since this morning",
         "session_id": "a1b2c3d4-..."}
        → {"conversation_reply": "Is the pain sharp or dull? ...", ...}

    `request: Request` must be the first positional parameter so slowapi
    can find it when resolving the rate-limit key function.
    """
    # If the client didn't supply a session_id, mint one now so this turn
    # is still stored and the id is returned for the client to reuse.
    session_id = input.session_id or str(uuid.uuid4())

    try:
        result = chatbot_flow(input.model_dump(), session_id=session_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Chatbot service unavailable: {e}"
        )


@router.delete("/conversation/{session_id}")
def end_conversation(
    session_id: str,
    current_user: dict = Depends(require_roles(_CHATBOT_ROLES)),
):
    """Clear the conversation history for a session.

    Call this when the user clicks "New Conversation" so the next message
    starts fresh. This is a soft delete — if `session_id` doesn't exist
    (already expired or never created) the call is a no-op.
    """
    clear_session(session_id)
    return {"message": "Conversation cleared", "session_id": session_id}
