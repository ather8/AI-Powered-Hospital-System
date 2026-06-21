"""Shared LLM provider configuration.

Every AI feature in this app (report summaries, structured notes, the
triage chatbot, clinical search) used to each construct its own
`OpenAI(api_key=OPENAI_API_KEY)` client and redefine the same
`CHATBOT_MODEL` env-var default independently. That meant "swap providers"
required editing four files and kept them subtly able to drift out of sync.

This module is the single place that decides which provider backs the AI
features and exposes that decision two ways:
  - get_client() — a ready-to-use OpenAI-SDK client, for services calling
    `client.chat.completions.create(...)` directly (ai_summary, ai_notes).
  - langchain_kwargs() — the same provider config as kwargs for LangChain's
    ChatOpenAI/OpenAIEmbeddings, which take `api_key`/`base_url` directly
    rather than a pre-built client (langchain_chatbot, ai_clinical_search).

Provider choice: Gemini is preferred when GEMINI_API_KEY is set, because
Google's Gemini API has a genuinely free tier (unlike OpenAI, which
requires a paid account) and exposes an OpenAI-compatible
/chat/completions + /embeddings surface — so switching providers is just
pointing the existing `openai` SDK at a different base_url, no new
dependency or rewritten call sites needed. OPENAI_API_KEY still works as a
fallback (or if both are set, OPENAI_API_KEY is left untouched and Gemini
is simply tried first) so nothing breaks for anyone already paying for
OpenAI.
"""
import os
from openai import OpenAI
from app.config import OPENAI_API_KEY, GEMINI_API_KEY

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

if GEMINI_API_KEY:
    PROVIDER = "gemini"
    _API_KEY = GEMINI_API_KEY
    _BASE_URL = GEMINI_BASE_URL
elif OPENAI_API_KEY:
    PROVIDER = "openai"
    _API_KEY = OPENAI_API_KEY
    _BASE_URL = None  # OpenAI SDK's own default
else:
    PROVIDER = None
    _API_KEY = None
    _BASE_URL = None

# gemini-2.5-flash is broadly available on free-tier Gemini API keys as of
# mid-2026. gpt-4o-mini remains the OpenAI fallback default (a prior fix —
# see the "phased out" note below — moved off "gpt-4" for the same reason).
# Either is overridable without a code change via CHATBOT_MODEL.
_DEFAULT_CHAT_MODELS = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}
CHATBOT_MODEL = os.getenv("CHATBOT_MODEL") or _DEFAULT_CHAT_MODELS.get(PROVIDER, "gpt-4o-mini")

# Only consumed by ai_clinical_search's RAG pipeline today. Gemini's
# embedding model produces different-dimension vectors than OpenAI's, so a
# FAISS index built under one provider isn't reusable after switching —
# not a concern currently since that index isn't shipped/built in this repo.
_DEFAULT_EMBEDDING_MODELS = {"gemini": "gemini-embedding-001", "openai": "text-embedding-3-small"}
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL") or _DEFAULT_EMBEDDING_MODELS.get(PROVIDER, "text-embedding-3-small")


def get_client() -> OpenAI | None:
    """A ready-to-use OpenAI-SDK client pointed at whichever provider is
    configured, or None if neither GEMINI_API_KEY nor OPENAI_API_KEY is set."""
    if not _API_KEY:
        return None
    kwargs: dict = {"api_key": _API_KEY}
    if _BASE_URL:
        kwargs["base_url"] = _BASE_URL
    return OpenAI(**kwargs)


def langchain_kwargs() -> dict:
    """Provider kwargs for LangChain's ChatOpenAI(...)/OpenAIEmbeddings(...).
    Empty dict (not None) when nothing is configured, so callers can always
    do `ChatOpenAI(model=CHATBOT_MODEL, **langchain_kwargs())` — LangChain
    will then raise its own clear "missing api_key" error, which the
    existing try/except in each caller already turns into a friendly
    "unavailable" message instead of crashing.
    """
    if not _API_KEY:
        return {}
    kwargs: dict = {"api_key": _API_KEY}
    if _BASE_URL:
        kwargs["base_url"] = _BASE_URL
    return kwargs
