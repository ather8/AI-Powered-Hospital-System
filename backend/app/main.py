import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.routes import (
    stripe_mock,
    auth, auth_google, patient, doctor, appointment,
    emr, billing, ocr, ocr_emr, ocr_summary, ai_clinical_search,
    ai_notes, ai_summary, chatbot,
    audit_log, notifications, search,
    dashboard, analytics, export
)
from app.utils.rate_limit import limiter

from app.config import FRONTEND_URL
from dotenv import load_dotenv
load_dotenv()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

app = FastAPI(
    title="Hospital Management Platform",
    description="Secure hospital management APIs with JWT and Google OAuth.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "patients", "description": "Patient CRUD operations"},
        {"name": "appointments", "description": "Appointment scheduling"},
        {"name": "emr", "description": "Electronic Medical Records"},
        {"name": "analytics", "description": "System analytics and reporting"},
    ]
)

# CORS configuration.
# Always include the full set of common local dev origins so this works
# regardless of which port Vite/the dev server happens to pick, and
# regardless of .env load ordering. FRONTEND_URL is added on top for
# staging/production deployments.
_dev_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
_extra = FRONTEND_URL if FRONTEND_URL else ""
allow_origins = list(dict.fromkeys(  # preserves order, removes duplicates
    ([_extra] if _extra and _extra not in _dev_origins else []) + _dev_origins
))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ────────────────────────────────────────────────────────────
# slowapi needs two things on the app object:
#   1. app.state.limiter — the Limiter instance used by @limiter.limit decorators
#   2. An exception handler for RateLimitExceeded → HTTP 429
# SlowAPIMiddleware runs the limit check before the route handler so the
# 429 is returned even if the route raises its own exception first.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Register routers
app.include_router(auth.router)
app.include_router(auth_google.router)
app.include_router(patient.router)
app.include_router(doctor.router)
app.include_router(appointment.router)
app.include_router(emr.router)
app.include_router(billing.router)
app.include_router(ocr.router)
app.include_router(ocr_emr.router)
app.include_router(ocr_summary.router)
app.include_router(ai_clinical_search.router)
app.include_router(ai_notes.router)
app.include_router(ai_summary.router)
app.include_router(chatbot.router)
app.include_router(audit_log.router)
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(export.router)
app.include_router(stripe_mock.router)

# Catch-all handler for unhandled exceptions.
# Without this, an unhandled exception (e.g. a bad DB query, a type
# mismatch) is caught by Starlette's default ServerErrorMiddleware, which
# sits OUTSIDE the CORSMiddleware layer added above. That means the 500
# response it generates never passes back through CORSMiddleware and ships
# with no Access-Control-Allow-Origin header — the browser then reports a
# misleading "CORS policy" error that hides the real 500/stack trace.
# An @app.exception_handler runs INSIDE the CORS layer, so its response
# always carries the correct CORS headers, and the real error is visible
# in both the browser network tab and the server logs below.
logger = logging.getLogger("uvicorn.error")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check the server logs for the full traceback."},
    )
