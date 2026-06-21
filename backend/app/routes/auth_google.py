from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
import requests
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, FRONTEND_URL
from app.utils.jwt import create_access_token
from app.db import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.services.audit import log_action

router = APIRouter(prefix="/auth/google", tags=["auth-google"])


@router.get("/")
def google_login():
    """Redirect the browser to Google's OAuth consent screen."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI in .env"
        )
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid email profile"
    )
    return RedirectResponse(google_auth_url)


@router.get("/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Google redirects here after the user consents.
    Exchange the code for a token, look up or create the user,
    then redirect back to the frontend with the JWT in the URL fragment
    so the SPA can pick it up and store it.
    """
    # Exchange auth code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_response = requests.post(token_url, data=data).json()
    access_token_google = token_response.get("access_token")

    if not access_token_google:
        # Redirect to frontend login with an error flag instead of returning JSON
        frontend = FRONTEND_URL or "http://localhost:5173"
        return RedirectResponse(f"{frontend}/login?error=google_failed")

    # Fetch user info from Google
    userinfo = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token_google}"}
    ).json()

    email = userinfo.get("email")
    if not email:
        frontend = FRONTEND_URL or "http://localhost:5173"
        return RedirectResponse(f"{frontend}/login?error=no_email")

    # Look up existing user or create one
    # User.hashed_password is NOT NULL — Google users get a sentinel value
    # since they never use a password. A separate "set password" flow would
    # be needed if you want them to be able to also log in with email/password.
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password="__google_oauth__",  # sentinel: no password login
            role="patient",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token({"sub": str(user.id), "role": user.role})

    log_action(
        db,
        user_id=str(user.id),
        action="LOGIN_GOOGLE",
        entity="User",
        entity_id=str(user.id),
        details="Google OAuth login successful",
    )

    # Redirect browser back to frontend — token in the URL fragment so it
    # never hits server logs. The frontend /auth/callback route reads it.
    frontend = FRONTEND_URL or "http://localhost:5173"
    return RedirectResponse(f"{frontend}/auth/callback#token={jwt_token}")
