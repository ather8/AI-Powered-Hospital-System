from app.models.audit_log import AuditLog
from datetime import datetime

def log_action(db, user_id: str, action: str, entity: str, entity_id: str, details: str = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        timestamp=datetime.utcnow(),
        details=details
    )
    db.add(log)
    db.commit()
