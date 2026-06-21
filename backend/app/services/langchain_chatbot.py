"""Triage chatbot service with per-session conversation memory.

Previously the chatbot was entirely stateless — every message was sent
to the LLM in isolation with no history, so the assistant could never
ask follow-up questions across turns (item 9 in the review).

Architecture
------------
* **Session store**: a plain in-process dict keyed by `session_id` (a UUID
  the caller generates and reuses across turns). Values are lists of
  `{"role": "user"|"assistant", "content": str}` message dicts — the
  minimal representation the OpenAI-compatible endpoint understands.

* **Session expiry**: entries expire after SESSION_TTL_MINUTES (default 30)
  of inactivity and are pruned lazily on each request. This prevents
  unbounded memory growth on a busy server without requiring Redis.
  For production with multiple workers, replace the dict with a Redis-backed
  store (e.g. `redis.StrictRedis`) — the interface is the same.

* **Max turns**: sessions are capped at MAX_HISTORY_TURNS (default 20)
  message pairs (40 messages). Older messages are dropped to stay within
  the model's context window and avoid inflated token costs.

* **Thread safety**: the store and its lock are module-level singletons;
  FastAPI runs routes in a thread pool so a `threading.Lock` is sufficient.
  Switch to `asyncio.Lock` if you ever move to async route handlers.

* **Lazy chain init**: the LangChain chain is still built lazily (first
  chatbot call) so a missing API key doesn't crash the entire app at
  startup — same design as before.
"""
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services.symptom_classifier import classify_symptom
from app.services.department_mapper import get_department
from app.services.ai_client import CHATBOT_MODEL, langchain_kwargs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SESSION_TTL_MINUTES: int = int(os.getenv("CHATBOT_SESSION_TTL_MINUTES", "30"))
MAX_HISTORY_TURNS: int = int(os.getenv("CHATBOT_MAX_HISTORY_TURNS", "20"))

# ---------------------------------------------------------------------------
# In-process session store
# ---------------------------------------------------------------------------

_store_lock = threading.Lock()

# { session_id: {"messages": [...], "last_active": datetime} }
_sessions: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _prune_expired() -> None:
    """Remove sessions that haven't been active within TTL.
    Must be called with _store_lock held."""
    cutoff = _now() - timedelta(minutes=SESSION_TTL_MINUTES)
    expired = [sid for sid, s in _sessions.items() if s["last_active"] < cutoff]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> list[dict]:
    """Return the message list for session_id, creating it if new.
    Prunes expired sessions opportunistically on each call."""
    with _store_lock:
        _prune_expired()
        if session_id not in _sessions:
            _sessions[session_id] = {"messages": [], "last_active": _now()}
        _sessions[session_id]["last_active"] = _now()
        return _sessions[session_id]["messages"]


def _trim_history(messages: list[dict]) -> list[dict]:
    """Keep at most MAX_HISTORY_TURNS * 2 messages (user + assistant pairs),
    dropping the oldest pairs first so the system prompt is never lost."""
    max_msgs = MAX_HISTORY_TURNS * 2
    if len(messages) > max_msgs:
        return messages[-max_msgs:]
    return messages


def clear_session(session_id: str) -> None:
    """Remove a session (called when the user clicks 'New Conversation')."""
    with _store_lock:
        _sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# LangChain chain (lazy init)
# ---------------------------------------------------------------------------

_chain = None
_chain_error: Exception | None = None


def _get_chain():
    """Build the LangChain chain lazily.

    All langchain imports live inside this function on purpose: importing
    them at module level previously crashed the entire FastAPI app at startup
    (ModuleNotFoundError: langchain.prompts), defeating the lazy pattern.
    """
    global _chain, _chain_error
    if _chain is not None:
        return _chain
    if _chain_error is not None:
        raise _chain_error
    try:
        from langchain_openai import ChatOpenAI

        # We now manage history ourselves, so the chain only needs to receive
        # the pre-assembled message list and return a reply — no memory
        # middleware required.
        _chain = ChatOpenAI(model=CHATBOT_MODEL, temperature=0, **langchain_kwargs())
        return _chain
    except Exception as e:
        _chain_error = RuntimeError(
            f"Chatbot LLM unavailable (check GEMINI_API_KEY/OPENAI_API_KEY): {e}"
        )
        raise _chain_error


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a hospital triage assistant. Your job is to help patients and "
    "staff by gathering information about the patient's symptoms. Ask "
    "follow-up questions about age, gender, onset, severity, and duration of "
    "symptoms. Be concise and professional. Do not diagnose — always recommend "
    "consulting a doctor for a final assessment."
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chatbot_flow(patient_input: dict, session_id: Optional[str] = None) -> dict:
    """Conversational triage flow with persistent session memory.

    Parameters
    ----------
    patient_input:
        Dict with at minimum ``symptoms`` (str). May also contain ``name``
        and ``age`` which are appended to the user message for context.
    session_id:
        Opaque string identifying the conversation. The caller (route) should
        generate a UUID on first load and send it back with every subsequent
        message. Pass None to run stateless (single-turn, no history stored).

    Returns
    -------
    dict with keys:
        - conversation_reply: the assistant's next message
        - disease / severity / department / confidence: triage classification
        - disclaimer: always-present safety notice
        - session_id: echoed back so the caller can persist it
    """
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    llm = _get_chain()

    # Build the user message text
    symptoms = patient_input.get("symptoms", "")
    name = patient_input.get("name", "")
    age = patient_input.get("age", "")
    user_text_parts = []
    if name:
        user_text_parts.append(f"Patient name: {name}")
    if age:
        user_text_parts.append(f"Age: {age}")
    user_text_parts.append(f"Symptoms: {symptoms}")
    user_text = "\n".join(user_text_parts)

    # Retrieve or create session history
    if session_id:
        history = _get_or_create_session(session_id)
    else:
        history = []

    # Assemble the full message list for the LLM
    lc_messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    for msg in _trim_history(history):
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=user_text))

    # Call the LLM
    response = llm.invoke(lc_messages)
    reply_text = getattr(response, "content", str(response))

    # Persist both turns in the session
    if session_id:
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})

    # Run symptom classification with an honest fallback.
    # classify_symptom raises RuntimeError when the ClinicalBERT model is not
    # installed (the default state — no trained model ships with this repo).
    # Rather than letting that exception bubble up as an opaque 500, we catch
    # it here and return explicit "unavailable" fields so the frontend can
    # surface a clear, user-friendly message instead of a broken UI.
    try:
        result = classify_symptom(symptoms)
        disease = result["disease"]
        severity = result["severity"]
        department = get_department(disease)
        classification_available = True
        confidence = result["confidence"]
    except RuntimeError:
        disease = None
        severity = None
        department = None
        classification_available = False
        confidence = None

    return {
        "conversation_reply": reply_text,
        "disease": disease,
        "severity": severity,
        "department": department,
        "confidence": confidence,
        "classification_available": classification_available,
        "disclaimer": "This is not medical advice. Please consult a doctor.",
        "session_id": session_id,
    }
