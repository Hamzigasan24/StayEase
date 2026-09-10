"""Authentication feature tests (Step 13 §6, A–K)."""

from tests.helpers import admin_token, auth, guest_token, login, register


def test_register_success(client):
    r = register(client, email="a@tst.example", name="Auth User")
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "guest" and body["email"] == "a@tst.example"
    assert "password" not in r.text and "hash" not in r.text


def test_register_duplicate(client):
    register(client, email="b@tst.example")
    assert register(client, email="b@tst.example").status_code == 409


def test_register_invalid_email(client):
    assert register(client, email="nope").status_code == 422


def test_login_success(client):
    register(client, email="c@tst.example")
    r = login(client, "c@tst.example")
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer" and len(r.json()["access_token"]) > 20


def test_login_wrong_password(client):
    register(client, email="d@tst.example")
    r = client.post("/auth/login", json={"email": "d@tst.example", "password": "Wrong12345"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid email or password"


def test_login_wrong_email(client):
    r = client.post("/auth/login", json={"email": "ghost@tst.example", "password": "Whatever123"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid email or password"


def test_me_missing_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_invalid_token(client):
    assert client.get("/auth/me", headers=auth("bad.token")).status_code == 401


def test_me_expired_token(client):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.utils.auth import ALGORITHM, SECRET_KEY

    tok = jwt.encode({"sub": "1", "role": "guest", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                     SECRET_KEY, algorithm=ALGORITHM)
    assert client.get("/auth/me", headers=auth(tok)).status_code == 401


def test_guest_forbidden_on_admin(client):
    tok = guest_token(client, "e@tst.example")
    assert client.post("/hotels", json={"name": "X"}, headers=auth(tok)).status_code == 403


def test_hash_never_returned(client):
    r = register(client, email="f@tst.example")
    assert "password" not in r.text and "hash" not in r.text
    tok = login(client, "f@tst.example").json()["access_token"]
    me = client.get("/auth/me", headers=auth(tok)).text
    assert "password" not in me and "hash" not in me


def test_admin_login_and_me(client):
    atok = admin_token(client)
    assert client.get("/auth/me", headers=auth(atok)).json()["role"] == "admin"
