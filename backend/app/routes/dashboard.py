from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.dashboard import get_dashboard_data
from app.utils.rbac import require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Every hospital role has a meaningful dashboard view (see services/dashboard.py
# for the per-role data each one receives). Previously this used the raw
# get_current_user dependency, which authenticated the caller but applied no
# role gate at all — meaning any future role that gets added to the system
# automatically gained dashboard access without an explicit decision being
# made. Using require_roles with the full explicit list makes additions
# intentional and visible in code review.
_DASHBOARD_ROLES = ["admin", "doctor", "nurse", "receptionist", "patient"]


@router.get("/")
def dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(_DASHBOARD_ROLES)),
):
    return get_dashboard_data(current_user["role"], current_user["sub"], db)
