from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.analytics import get_analytics
from app.schemas.analytics import AnalyticsResponse
from app.utils.rbac import require_roles

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin"]))):
    return get_analytics(db)
