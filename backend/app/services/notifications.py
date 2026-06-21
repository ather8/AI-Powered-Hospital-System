from app.models.notification import Notification
from datetime import datetime

def create_notification(db, user_id: int, message: str, scheduled_for: datetime = None):
    notif = Notification(
        user_id=user_id,
        message=message,
        scheduled_for=scheduled_for
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def mark_notification_read(db, notif: Notification) -> Notification:
    if not notif.read:
        notif.read = True
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_read(db, user_id: int) -> int:
    """Bulk-marks every unread notification for a user as read.
    Returns the number of rows updated (0 if there was nothing to do)."""
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read.is_(False))
        .update({"read": True}, synchronize_session=False)
    )
    db.commit()
    return updated


def count_unread(db, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read.is_(False))
        .count()
    )
