import pytest
from app.services.audit import log_action
from app.models.audit_log import AuditLog

def test_log_action_creates_entry(db_session, test_user):
    log_action(
        db_session,
        user_id=test_user.id,
        action="TEST_ACTION",
        entity="Patient",
        entity_id="123",
        details="Unit test log"
    )
    result = db_session.query(AuditLog).filter_by(action="TEST_ACTION").first()
    assert result is not None
    assert result.details == "Unit test log"
