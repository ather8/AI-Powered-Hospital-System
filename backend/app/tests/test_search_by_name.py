from datetime import date, datetime, timezone
from passlib.context import CryptContext
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.emr import EMR
from app.utils.jwt import create_access_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _make_user(db_session, email: str, role: str) -> User:
    user = User(email=email, hashed_password=pwd_context.hash("password"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_search_patients_by_name(client, db_session):
    admin = _make_user(db_session, "search-admin@example.com", "admin")
    patient_user = _make_user(db_session, "search-pt-user@example.com", "patient")
    patient = Patient(user_id=patient_user.id, name="Jordan Blake", dob=date(1990, 1, 1), phone="555-1234")
    db_session.add(patient)
    db_session.commit()

    response = client.post(
        "/search/patients",
        json={"name": "Jordan"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    results = response.json()
    assert any(p["name"] == "Jordan Blake" for p in results)


def test_search_appointments_by_doctor_name(client, db_session):
    admin = _make_user(db_session, "search-admin2@example.com", "admin")
    patient_user = _make_user(db_session, "search-pt-user2@example.com", "patient")
    patient = Patient(user_id=patient_user.id, name="Sam Rivera")
    doctor = Doctor(name="Dr. Casey Lee", specialty="Cardiology")
    db_session.add_all([patient, doctor])
    db_session.commit()

    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        scheduled_time=datetime.now(timezone.utc),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()

    # Searching by name finds the appointment — no UUID required.
    response = client.post(
        "/search/appointments",
        json={"doctor_name": "Casey"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["doctor_name"] == "Dr. Casey Lee"
    assert results[0]["patient_name"] == "Sam Rivera"


def test_search_emrs_by_patient_name(client, db_session):
    admin = _make_user(db_session, "search-admin3@example.com", "admin")
    patient_user = _make_user(db_session, "search-pt-user3@example.com", "patient")
    patient = Patient(user_id=patient_user.id, name="Taylor Morgan")
    doctor = Doctor(name="Dr. Avery Quinn", specialty="Neurology")
    db_session.add_all([patient, doctor])
    db_session.commit()

    emr = EMR(
        patient_id=patient.id,
        doctor_id=doctor.id,
        diagnosis="Migraine",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(emr)
    db_session.commit()

    response = client.post(
        "/search/emrs",
        json={"patient_name": "Taylor"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_name"] == "Taylor Morgan"
    assert results[0]["doctor_name"] == "Dr. Avery Quinn"
