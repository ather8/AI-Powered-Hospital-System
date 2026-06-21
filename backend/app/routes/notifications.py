from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationCreate, NotificationResponse, UserSummary
from app.services.notifications import create_notification, mark_notification_read, mark_all_read, count_unread
from app.services.audit import log_action
from app.utils.rbac import require_roles

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Any authenticated user can read/manage their own notifications; only
# admin/receptionist can send new ones (see send_notification below).
RECIPIENT_ROLES = ["doctor", "nurse", "patient", "admin", "receptionist"]


# Registered before any /{...} path param routes for the same reason as
# patient/billing/emr's sibling endpoints: route matching is order-sensitive.
# Powers the recipient dropdown on the admin "send notification" form —
# there was previously no way to list users at all, so the only way to
# generate a notification was a backend job calling create_notification()
# directly with a known user_id.
@router.get("/recipients", response_model=list[UserSummary])
def list_recipients(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    return db.query(User).order_by(User.role, User.email).all()


@router.post("/", response_model=NotificationResponse)
def send_notification(request: NotificationCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(["admin", "receptionist"]))):
    # Validate the recipient exists before inserting, so a bad/typo'd
    # user_id returns a clean 404 instead of an unhandled FK-violation
    # IntegrityError surfacing as a generic 500.
    recipient = db.query(User).filter(User.id == request.user_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient user not found")
    notif = create_notification(db, request.user_id, request.message, request.scheduled_for)
    log_action(db, current_user["sub"], "SEND_NOTIFICATION", "Notification", str(notif.id), details=f"Notification sent to user {request.user_id}")
    return notif


@router.get("/", response_model=list[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(RECIPIENT_ROLES))):
    return db.query(Notification).filter(Notification.user_id == current_user["sub"]).order_by(Notification.created_at.desc()).all()


# Static path registered before /{notification_id}/read so it can never be
# shadowed, same rule as /recipients above — kept as a habit here even
# though "/unread-count" and "/{id}/read" don't actually collide (different
# segment counts), since the project convention is to put literal routes
# first regardless.
@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(RECIPIENT_ROLES))):
    return {"count": count_unread(db, int(current_user["sub"]))}


@router.post("/read-all", response_model=dict)
def read_all(db: Session = Depends(get_db), current_user: dict = Depends(require_roles(RECIPIENT_ROLES))):
    updated = mark_all_read(db, int(current_user["sub"]))
    return {"updated": updated}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def read_one(notification_id: UUID, db: Session = Depends(get_db), current_user: dict = Depends(require_roles(RECIPIENT_ROLES))):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    # Ownership check: a notification's id alone doesn't prove it belongs to
    # the caller. Without this, any authenticated user could mark (or learn
    # the existence of) another user's notification just by guessing/
    # enumerating UUIDs.
    if notif.user_id != int(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Access Forbidden")
    return mark_notification_read(db, notif)
