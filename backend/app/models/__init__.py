# Import every SQLAlchemy model here so that Base.metadata is fully
# populated as soon as `app.models` (or anything that imports it) is
# imported — this is required for Alembic autogenerate and for
# Base.metadata.create_all() to know about all tables. Without this,
# only whichever individual model modules happened to already be
# imported elsewhere would register with Base.metadata.
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.emr import EMR
from app.models.billing import Billing, BillingLineItem
from app.models.notification import Notification
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "Patient",
    "Doctor",
    "Appointment",
    "EMR",
    "Billing",
    "BillingLineItem",
    "Notification",
    "AuditLog",
]
