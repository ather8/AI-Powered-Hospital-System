from datetime import date, datetime, timedelta
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.emr import EMR
from app.models.billing import Billing
from app.models.audit_log import AuditLog


def get_dashboard_data(role: str, user_id: str, db) -> dict:
    """
    Return role-appropriate summary stats for the dashboard.
    Only queries columns and models that actually exist in the schema.
    """

    if role == "admin":
        total_users = db.query(User).count()
        total_patients = db.query(Patient).count()
        total_doctors = db.query(Doctor).count()
        total_appointments = db.query(Appointment).count()
        pending_billing = db.query(Billing).filter(Billing.status == "unpaid").count()
        recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(5).count()
        return {
            "total_users": total_users,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_appointments": total_appointments,
            "unpaid_invoices": pending_billing,
            "recent_audit_events": recent_logs,
        }

    elif role == "doctor":
        # Doctor.user_id links a logged-in User (integer id) to "their own"
        # Doctor profile (UUID id). Appointment.doctor_id / EMR.doctor_id
        # are UUID FKs to doctors.id, so we resolve the Doctor row first,
        # then filter by its UUID — never by user_id directly.
        doctor = db.query(Doctor).filter(Doctor.user_id == int(user_id)).first()
        if not doctor:
            return {
                "message": "No doctor profile is linked to this account yet. Ask an admin to link your account under Doctors.",
            }
        total_appointments = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
        ).count()
        upcoming = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == "scheduled",
        ).count()
        my_emrs = db.query(EMR).filter(EMR.doctor_id == doctor.id).count()
        return {
            "total_appointments": total_appointments,
            "upcoming_appointments": upcoming,
            "emr_records_authored": my_emrs,
        }

    elif role == "nurse":
        # Nurses share appointment visibility with doctors
        total_appointments = db.query(Appointment).count()
        scheduled = db.query(Appointment).filter(
            Appointment.status == "scheduled"
        ).count()
        return {
            "total_appointments": total_appointments,
            "scheduled_appointments": scheduled,
        }

    elif role == "receptionist":
        # Show today's appointments and billing overview
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = today_start + timedelta(days=1)
        appointments_today = db.query(Appointment).filter(
            Appointment.scheduled_time >= today_start,
            Appointment.scheduled_time < today_end,
        ).count()
        pending_billing = db.query(Billing).filter(Billing.status == "unpaid").count()
        return {
            "appointments_today": appointments_today,
            "unpaid_invoices": pending_billing,
        }

    elif role == "patient":
        # Patient sees their own appointments and EMRs
        # patient_id in appointments/emrs is the Patient.id (UUID),
        # but user_id here is the User.id (integer string from JWT sub).
        # Look up the Patient record for this user first.
        patient = db.query(Patient).filter(
            Patient.user_id == int(user_id)
        ).first()
        if not patient:
            return {"message": "No patient profile found. Create one under Patients."}
        my_appointments = db.query(Appointment).filter(
            Appointment.patient_id == patient.id
        ).count()
        upcoming = db.query(Appointment).filter(
            Appointment.patient_id == patient.id,
            Appointment.status == "scheduled",
        ).count()
        my_emrs = db.query(EMR).filter(EMR.patient_id == patient.id).count()
        return {
            "upcoming_appointments": upcoming,
            "total_appointments": my_appointments,
            "emr_records": my_emrs,
        }

    else:
        return {"message": "Role not recognized"}
