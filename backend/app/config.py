import os
import warnings
from dotenv import load_dotenv

load_dotenv(override=True)

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("SECRET")
JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Shared-secret header check for the mock Stripe webhook (POST
# /billing/stripe/webhook). Real Stripe webhooks are authenticated via a
# signed payload (stripe.Webhook.construct_event with a per-endpoint
# signing secret from the Stripe dashboard) rather than a static header —
# see the migration note in app/routes/stripe_mock.py. Until that's wired
# up, this is the minimum bar: without it, any unauthenticated caller who
# finds the endpoint can mark an arbitrary bill "paid". A default is
# provided so local/dev runs work out of the box, same convention as the
# rest of this file's optional settings.
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock_dev_only_change_me")

# ── Runtime validation ──────────────────────────────────────────────────────
# In production (ENV=production or ENFORCE_SECRETS=1) a missing JWT secret is
# a critical security vulnerability — the app would sign tokens with None,
# which jose silently accepts, making every forged token valid.
# We raise at startup so the misconfiguration is caught immediately rather
# than discovered via a security incident.
#
# In development (the default) we warn so local runs without a .env still
# work out of the box.

_ENFORCE = os.getenv("ENV", "development").lower() == "production" or \
           os.getenv("ENFORCE_SECRETS", "0") == "1"

_missing: list[str] = []
if not SECRET_KEY:
    _missing.append("SECRET_KEY")
if not JWT_SECRET:
    _missing.append("JWT_SECRET")

if _missing:
    msg = (
        f"Missing critical secrets: {', '.join(_missing)}. "
        "Set them in backend/.env or your environment. "
        "A missing JWT_SECRET allows arbitrary token forgery."
    )
    if _ENFORCE:
        raise RuntimeError(msg)
    else:
        warnings.warn(msg, stacklevel=2)
