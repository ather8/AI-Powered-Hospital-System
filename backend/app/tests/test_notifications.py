from passlib.context import CryptContext
from app.models.user import User
from app.models.notification import Notification
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


def test_admin_can_send_notification(client, db_session):
    admin = _make_user(db_session, "notif-admin@example.com", "admin")
    recipient = _make_user(db_session, "notif-recipient@example.com", "patient")

    response = client.post(
        "/notifications/",
        json={"user_id": recipient.id, "message": "Your results are ready."},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == recipient.id
    assert body["message"] == "Your results are ready."

    stored = db_session.query(Notification).filter_by(user_id=recipient.id).first()
    assert stored is not None


def test_send_notification_unknown_recipient_returns_404(client, db_session):
    admin = _make_user(db_session, "notif-admin2@example.com", "admin")

    response = client.post(
        "/notifications/",
        json={"user_id": 999999, "message": "hi"},
        headers=_auth_headers(admin),
    )
    assert response.status_code == 404


def test_patient_cannot_send_notification(client, db_session):
    patient = _make_user(db_session, "notif-patient@example.com", "patient")
    recipient = _make_user(db_session, "notif-recipient2@example.com", "patient")

    response = client.post(
        "/notifications/",
        json={"user_id": recipient.id, "message": "hi"},
        headers=_auth_headers(patient),
    )
    assert response.status_code == 403


def test_list_recipients_admin_only(client, db_session):
    admin = _make_user(db_session, "notif-admin3@example.com", "admin")
    patient = _make_user(db_session, "notif-patient2@example.com", "patient")

    ok = client.get("/notifications/recipients", headers=_auth_headers(admin))
    assert ok.status_code == 200
    assert any(u["email"] == "notif-patient2@example.com" for u in ok.json())

    forbidden = client.get("/notifications/recipients", headers=_auth_headers(patient))
    assert forbidden.status_code == 403


def test_unread_count_reflects_only_own_unread(client, db_session):
    admin = _make_user(db_session, "notif-admin4@example.com", "admin")
    alice = _make_user(db_session, "notif-alice@example.com", "patient")
    bob = _make_user(db_session, "notif-bob@example.com", "patient")

    client.post("/notifications/", json={"user_id": alice.id, "message": "for alice"}, headers=_auth_headers(admin))
    client.post("/notifications/", json={"user_id": bob.id, "message": "for bob"}, headers=_auth_headers(admin))

    resp = client.get("/notifications/unread-count", headers=_auth_headers(alice))
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_mark_one_read_updates_only_that_notification(client, db_session):
    admin = _make_user(db_session, "notif-admin5@example.com", "admin")
    alice = _make_user(db_session, "notif-alice2@example.com", "patient")

    created = client.post(
        "/notifications/", json={"user_id": alice.id, "message": "hello"}, headers=_auth_headers(admin)
    ).json()

    resp = client.patch(f"/notifications/{created['id']}/read", headers=_auth_headers(alice))
    assert resp.status_code == 200
    assert resp.json()["read"] is True


def test_cannot_mark_another_users_notification_read(client, db_session):
    admin = _make_user(db_session, "notif-admin6@example.com", "admin")
    alice = _make_user(db_session, "notif-alice3@example.com", "patient")
    bob = _make_user(db_session, "notif-bob2@example.com", "patient")

    created = client.post(
        "/notifications/", json={"user_id": alice.id, "message": "hello"}, headers=_auth_headers(admin)
    ).json()

    resp = client.patch(f"/notifications/{created['id']}/read", headers=_auth_headers(bob))
    assert resp.status_code == 403

    still_unread = db_session.query(Notification).filter_by(id=created["id"]).first()
    assert still_unread.read is False


def test_mark_all_read_only_affects_caller(client, db_session):
    admin = _make_user(db_session, "notif-admin7@example.com", "admin")
    alice = _make_user(db_session, "notif-alice4@example.com", "patient")
    bob = _make_user(db_session, "notif-bob3@example.com", "patient")

    client.post("/notifications/", json={"user_id": alice.id, "message": "a1"}, headers=_auth_headers(admin))
    client.post("/notifications/", json={"user_id": alice.id, "message": "a2"}, headers=_auth_headers(admin))
    client.post("/notifications/", json={"user_id": bob.id, "message": "b1"}, headers=_auth_headers(admin))

    resp = client.post("/notifications/read-all", headers=_auth_headers(alice))
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    bob_unread = client.get("/notifications/unread-count", headers=_auth_headers(bob))
    assert bob_unread.json()["count"] == 1
