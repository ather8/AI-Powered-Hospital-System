from sqlalchemy.orm import Session
from datetime import date as date_cls, datetime, timedelta
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.emr import EMR


def search_patients(db: Session, name: str = None, dob=None, phone: str = None):
    query = db.query(Patient)
    if name:
        query = query.filter(Patient.name.ilike(f"%{name}%"))
    if dob:
        query = query.filter(Patient.dob == dob)
    if phone:
        query = query.filter(Patient.phone.ilike(f"%{phone}%"))
    return query.all()


def search_appointments(db: Session, doctor_name: str = None, date: str = None, status: str = None):
    # Join to Doctor so callers search by name, never a UUID they can't be
    # expected to remember. The result still includes doctor_id/patient_id
    # (useful for follow-up actions like "open this appointment"), but adds
    # doctor_name and patient_name so the UI never has to show a bare id.
    query = db.query(Appointment, Doctor.name.label("doctor_name"), Patient.name.label("patient_name")) \
        .join(Doctor, Appointment.doctor_id == Doctor.id) \
        .join(Patient, Appointment.patient_id == Patient.id)
    if doctor_name:
        query = query.filter(Doctor.name.ilike(f"%{doctor_name}%"))
    if date:
        # `date` is a calendar day (e.g. "2026-06-21"); scheduled_time is a
        # full DateTime. Match every appointment within that day rather
        # than relying on string comparison of a partial timestamp.
        day = date_cls.fromisoformat(date)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        query = query.filter(Appointment.scheduled_time >= day_start, Appointment.scheduled_time < day_end)
    if status:
        query = query.filter(Appointment.status == status)
    rows = query.all()
    results = []
    for appt, doctor_name_val, patient_name_val in rows:
        results.append({
            "id": appt.id,
            "patient_id": appt.patient_id,
            "patient_name": patient_name_val,
            "doctor_id": appt.doctor_id,
            "doctor_name": doctor_name_val,
            "scheduled_time": appt.scheduled_time,
            "status": appt.status,
        })
    return results


def search_emrs(db: Session, patient_name: str = None, diagnosis: str = None, date_range: tuple = None):
    # Same reasoning as search_appointments: join to Patient so callers
    # search by name instead of a patient UUID.
    query = db.query(EMR, Patient.name.label("patient_name"), Doctor.name.label("doctor_name")) \
        .join(Patient, EMR.patient_id == Patient.id) \
        .join(Doctor, EMR.doctor_id == Doctor.id)
    if patient_name:
        query = query.filter(Patient.name.ilike(f"%{patient_name}%"))
    if diagnosis:
        query = query.filter(EMR.diagnosis.ilike(f"%{diagnosis}%"))
    if date_range:
        start, end = date_range
        query = query.filter(EMR.created_at.between(start, end))
    rows = query.all()
    results = []
    for emr, patient_name_val, doctor_name_val in rows:
        results.append({
            "id": emr.id,
            "patient_id": emr.patient_id,
            "patient_name": patient_name_val,
            "doctor_id": emr.doctor_id,
            "doctor_name": doctor_name_val,
            "diagnosis": emr.diagnosis,
            "prescription": emr.prescription,
            "lab_results": emr.lab_results,
            "created_at": emr.created_at,
        })
    return results
