"""Guest tests (admin-only listing, ownership via reservations)."""

from tests.helpers import admin_token, auth, guest_token


def test_guest_auto_created_and_listed(client):
    atok = admin_token(client)
    guest_token(client, "g@tst.example")
    r = client.get("/guests", headers=auth(atok)).json()
    assert r["pagination"]["total_items"] == 1
    assert "password" not in str(r) and "hash" not in str(r)


def test_guest_cannot_list(client):
    gtok = guest_token(client, "g@tst.example")
    assert client.get("/guests", headers=auth(gtok)).status_code == 403
    assert client.get("/guests").status_code == 401


def test_guest_search(client):
    atok = admin_token(client)
    guest_token(client, "hammy@tst.example")
    assert len(client.get("/guests?search=hammy", headers=auth(atok)).json()["items"]) == 1
    assert len(client.get("/guests?search=HAMMY@TST.EXAMPLE", headers=auth(atok)).json()["items"]) == 1


def test_guest_crud_admin(client):
    atok = admin_token(client)
    from tests.conftest import TestingSessionLocal
    from app.models.user import User
    from app.utils.security import hash_password

    db = TestingSessionLocal()
    try:
        u = User(name="Manual", email="manual@tst.example", password_hash=hash_password("ManualPass1"), role="guest")
        db.add(u)
        db.commit()
        db.refresh(u)
        uid = u.id
    finally:
        db.close()
    # admin creates profile for a user without one
    r = client.post("/guests", json={"user_id": uid, "phone": "123"}, headers=auth(atok))
    assert r.status_code == 201
    gid = r.json()["id"]
    assert client.get(f"/guests/{gid}", headers=auth(atok)).status_code == 200
    u = client.put(f"/guests/{gid}", json={"phone": "999"}, headers=auth(atok))
    assert u.json()["phone"] == "999"
    # duplicate profile rejected
    assert client.post("/guests", json={"user_id": uid}, headers=auth(atok)).status_code == 409
    assert client.delete(f"/guests/{gid}", headers=auth(atok)).status_code == 204


def test_blank_fields_cleaned(client):
    atok = admin_token(client)
    from tests.conftest import TestingSessionLocal
    from app.models.user import User
    from app.utils.security import hash_password

    db = TestingSessionLocal()
    try:
        u = User(name="B", email="b@tst.example", password_hash=hash_password("Bpass1234"), role="guest")
        db.add(u)
        db.commit()
        db.refresh(u)
        uid = u.id
    finally:
        db.close()
    r = client.post("/guests", json={"user_id": uid, "phone": "   "}, headers=auth(atok))
    assert r.status_code == 201 and r.json()["phone"] is None
