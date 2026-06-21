"""Central rate-limiting configuration (slowapi).

All AI endpoints in this app call out to an external LLM provider (Gemini
free tier or OpenAI). Without limits a single user — or a runaway client
bug — can drain the quota in minutes, degrade the service for everyone,
and rack up unexpected costs.

Design decisions
----------------
* **One limiter instance**, imported by every route that needs it.
  slowapi requires the same Limiter object to be attached to the FastAPI
  app in main.py *and* used in route decorators. Splitting them would
  silently create two independent limit stores that never talk to each
  other.

* **Per-user key, not per-IP.**  Hospital staff share office NAT — an
  IP-based limit would pool the entire nursing station into one bucket
  and hit the ceiling after the first few requests. We extract the user
  id from the JWT instead, which gives each account its own independent
  counter. Unauthenticated requests (should not reach AI routes, but
  handled defensively) fall back to remote IP.

* **In-memory storage** (default for slowapi / limits library).  This
  is intentionally simple: it resets on restart and is not shared across
  multiple worker processes. For a single-worker dev/staging deployment
  it's perfectly fine. If you scale to multiple workers, swap the storage
  backend to Redis:

      from limits.storage import RedisStorage
      from app.config import REDIS_URL
      limiter = Limiter(key_func=_ai_key, storage_uri=REDIS_URL)

* **Conservative limits** that reflect the free Gemini tier (~60 RPM
  across the whole project, 1 500 RPD per model).  All values are
  overridable via environment variables so they can be raised in
  production without a code change.

Limit constants
---------------
Each constant is read from the environment first; the fallback is the
safe default for the free Gemini tier:

  RATE_CHATBOT          e.g. "20/minute"   – conversational, higher cadence
  RATE_AI_SUMMARY       e.g. "10/minute"   – long-form, more expensive
  RATE_AI_NOTES         e.g. "10/minute"
  RATE_AI_CLINICAL      e.g. "10/minute"   – RAG pipeline, hits embeddings too
  RATE_OCR              e.g. "15/minute"   – CPU-heavy but no LLM cost
"""
import os
from fastapi import Request
from slowapi import Limiter

# ---------------------------------------------------------------------------
# Key function — per authenticated user, fallback to IP
# ---------------------------------------------------------------------------

def _ai_key(request: Request) -> str:
    """Return a rate-limit key scoped to the authenticated user.

    slowapi calls this function for every decorated endpoint. We pull the
    user id out of the JWT payload that get_current_user / require_roles
    already attached to request.state (FastAPI stores Depends() results
    there when the dependency is called before the route function runs —
    but it doesn't expose them on request.state automatically).

    The most reliable cross-middleware approach is to decode the
    Authorization header ourselves here. We only need the `sub` claim,
    not full verification (the RBAC dependency already rejected the
    request if the token is invalid before we reach the route body).
    A missing/malformed token falls back to the client IP so unauthenticated
    requests are still bucketed rather than all sharing a single key.
    """
    try:
        from jose import jwt as jose_jwt
        from app.config import JWT_SECRET

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            # decode without verification — we only want the sub claim for
            # bucketing; auth is already enforced by the RBAC dependency.
            payload = jose_jwt.get_unverified_claims(token)
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
    except Exception:
        pass  # fall through to IP-based key

    # Fallback: use the real client IP (respects X-Forwarded-For via
    # request.client, which Starlette populates from the proxy headers
    # when ProxyHeadersMiddleware is in use).
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Limiter instance (imported by main.py and all AI route modules)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=_ai_key)

# ---------------------------------------------------------------------------
# Per-endpoint limit strings (overridable via environment variables)
# ---------------------------------------------------------------------------

# Format understood by the `limits` library: "<count>/<period>"
# Period can be: second, minute, hour, day, month, year.

RATE_CHATBOT: str = os.getenv("RATE_CHATBOT", "20/minute")
RATE_AI_SUMMARY: str = os.getenv("RATE_AI_SUMMARY", "10/minute")
RATE_AI_NOTES: str = os.getenv("RATE_AI_NOTES", "10/minute")
RATE_AI_CLINICAL: str = os.getenv("RATE_AI_CLINICAL", "10/minute")
RATE_OCR: str = os.getenv("RATE_OCR", "15/minute")
