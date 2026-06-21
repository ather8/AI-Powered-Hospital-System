from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.audit_log import AuditLog
from app.utils.rbac import require_roles
from app.utils.pagination import PageParams, PagedResponse

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=PagedResponse[dict])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles(["admin"])),
    page: PageParams = Depends(),
):
    """List audit log entries, newest first, with pagination.

    Without pagination the audit log becomes unusable as it grows — a busy
    hospital can generate thousands of entries per day and a full-table scan
    on every admin page load is both slow and expensive.

    The default page size (20) is intentionally small; the admin UI should
    default to showing recent activity at a glance, not load everything.
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    total = query.count()
    items = query.offset(page.skip).limit(page.limit).all()
    # AuditLog rows don't have a Pydantic schema yet; return as dicts so the
    # response validates cleanly. A dedicated AuditLogResponse schema can be
    # added in a follow-up without touching this pagination wiring.
    rows = [
        {
            "id": str(row.id),
            "user_id": row.user_id,
            "action": row.action,
            "resource": row.resource,
            "resource_id": row.resource_id,
            "details": row.details,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }
        for row in items
    ]
    return PagedResponse.create(rows, total, page)
