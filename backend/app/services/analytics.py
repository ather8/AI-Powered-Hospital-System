from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.billing import Billing
from app.models.emr import EMR

def get_analytics(db: Session) -> dict:
    # Group appointments by department, coalescing NULL to "Unknown" so that
    # appointments created before the department column existed (or without
    # an explicit department) still appear in the breakdown rather than being
    # silently dropped. Previously, querying Appointment.department crashed
    # because the column didn't exist on the model at all.
    dept_col = func.coalesce(Appointment.department, "Unknown")
    appointments_by_department = dict(
        db.query(dept_col, func.count(Appointment.id))
        .group_by(dept_col)
        .all()
    )

    return {
        "total_patients": db.query(func.count(Patient.id)).scalar(),
        "total_appointments": db.query(func.count(Appointment.id)).scalar(),
        "appointments_by_department": appointments_by_department,
        "billing_summary": {
            "total_invoices": db.query(func.count(Billing.id)).scalar(),
            "paid_invoices": db.query(func.count()).filter(Billing.status == "paid").scalar(),
            # Was filtering on Billing.status == "pending" -- that value
            # never existed in the status vocabulary (unpaid /
            # partially_paid / paid / cancelled, see
            # app/services/billing.py:ALL_STATUSES), so this always
            # silently returned 0 regardless of how many bills were
            # actually outstanding. "Pending" here means "not yet fully
            # paid and not cancelled" -- i.e. unpaid or partially_paid.
            "pending_invoices": db.query(func.count())
                .filter(Billing.status.in_(["unpaid", "partially_paid"]))
                .scalar(),
            "cancelled_invoices": db.query(func.count()).filter(Billing.status == "cancelled").scalar(),
        },
        "diagnosis_counts": dict(
            db.query(EMR.diagnosis, func.count(EMR.id)).group_by(EMR.diagnosis).all()
        )
    }
