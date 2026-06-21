from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.audit import log_action
from app.utils.jwt import create_access_token, verify_access_token
from app.utils.dependencies import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": str(user.id), "role": user.role})
    log_action(
        db,
        user_id=str(user.id),
        action="LOGIN_LOCAL",
        entity="User",
        entity_id=str(user.id),
        details="Local login successful"
    )    
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = pwd_context.hash(request.password)
        new_user = User(email=request.email, hashed_password=hashed_password, role=request.role)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        token = create_access_token({"sub": str(new_user.id), "role": new_user.role})
        return TokenResponse(access_token=token, token_type="bearer")
    except HTTPException:
        # Re-raise known HTTP errors (e.g., duplicate email)
        raise
    except Exception as e:
        # Log the error server-side and return a sanitized 500 to the client
        import traceback, sys
        tb = traceback.format_exc()
        print("[ERROR] /auth/register failed:\n", tb, file=sys.stderr)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/refresh", response_model=TokenResponse)
def refresh(token: str, db: Session = Depends(get_db)):
    payload = verify_access_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_token = create_access_token({"sub": payload.get("sub"), "role": payload.get("role")})
    return TokenResponse(access_token=new_token, token_type="bearer")


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Audit log
    log_action(
        db,
        user_id=current_user["sub"],
        action="LOGOUT",
        entity="User",
        entity_id=current_user["sub"],
        details="User logged out"
    )
    return {"message": "Logged out successfully"}