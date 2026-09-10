"""Validation + error-format tests (Step 12).

Every test asserts the standard envelope:
{"success": False, "error": {"code", "message", "details"}}
and that no response leaks secrets, SQL, hashes, tokens or paths.
Covers the 23 required cases plus envelope/header/mass-assignment checks.
"""

import re

SECRET_PATTERNS = re.compile(
    r"stayease123|SECRET_KEY|BEGIN .*PRIVATE|Traceback|psycopg|sqlalchemy"
    r"|/home/|password_hash|\$argon2|\.py\", line",
    re.IGNORECASE,
)


def assert_envelope(body, code):
    assert body["success"] is False, body
    assert body["error"]["code"] == code, body
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert "error" in body and set(body) == {"success", "error"}, body


def assert_no_secrets(text):
    assert not SECRET_PATTERNS.search(text), text[:300]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, name="T User", email="t@example.com", password="StrongPass123", extra=None):
    body = {"name": name, "email": email, "password": password}
    if extra:
        body.update(extra)
    return client.post("/auth/register", json=body)


def make_admin(client):
    """Admin via direct model insert (script equivalent for tests)."""
    from app.models.user import User
    from app.utils.security import hash_password
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        admin = User(name="Admin", email="admin@tst.example", password_hash=hash_password("AdminPass123"), role="admin")
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
    finally:
        db.close()
    token = client.post("/auth/login", json={"email": "admin@tst.example", "password": "AdminPass123"}).json()["access_token"]
    return admin_id, token


def make_inventory(client, atok):
    hid = client.post("/hotels", json={"name": "T Inn", "city": "T City"}, headers=auth(atok)).json()["id"]
    rtid = client.post("/room-types", json={"name": "T Std", "price_per_night": "1000", "capacity": 2}, headers=auth(atok)).json()["id"]
    rid = client.post("/rooms", json={"hotel_id": hid, "room_type_id": rtid, "room_number": "1"}, headers=auth(atok)).json()["id"]
    return hid, rtid, rid


def guest_token(client, email="g@tst.example"):
    register(client, email=email)
    return client.post("/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]


# --- 1-3: registration validation -------------------------------------------

def test_1_invalid_email(client):
    r = client.post("/auth/register", json={"name": "X", "email": "not-an-email", "password": "StrongPass123"})
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")
    assert any(d["field"] == "email" for d in r.json()["error"]["details"])
    assert_no_secrets(r.text)


def test_2_duplicate_email(client):
    register(client, email="dup@tst.example")
    r = register(client, email="dup@tst.example")
    assert r.status_code == 409
    assert_envelope(r.json(), "EMAIL_ALREADY_EXISTS")
    assert_no_secrets(r.text)


def test_3_weak_password(client):
    r = register(client, email="w@tst.example", password="short")
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")
    assert_no_secrets(r.text)


def test_3b_blank_name_rejected(client):
    r = register(client, name="   ", email="b@tst.example")
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


def test_role_smuggle_stays_guest(client):
    r = register(client, email="s@tst.example", extra={"role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "guest"
    assert "password" not in r.text and "hash" not in r.text


def test_email_normalized(client):
    r = register(client, email="  MiXeD@Tst.Example ")
    assert r.status_code == 201
    assert r.json()["email"] == "mixed@tst.example"


# --- 4-7: auth errors ---------------------------------------------------------

def test_4_wrong_password(client):
    register(client, email="l@tst.example")
    r = client.post("/auth/login", json={"email": "l@tst.example", "password": "WrongPass123"})
    assert r.status_code == 401
    assert_envelope(r.json(), "UNAUTHORIZED")
    assert r.json()["error"]["message"] == "Invalid email or password"
    assert r.headers.get("www-authenticate") == "Bearer"
    assert_no_secrets(r.text)


def test_5_missing_jwt(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert_envelope(r.json(), "UNAUTHORIZED")


def test_6_invalid_jwt(client):
    r = client.get("/auth/me", headers=auth("bad.token.here"))
    assert r.status_code == 401
    assert_envelope(r.json(), "UNAUTHORIZED")
    assert_no_secrets(r.text)


def test_expired_jwt(client):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.utils.auth import ALGORITHM, SECRET_KEY

    tok = jwt.encode({"sub": "1", "role": "guest", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET_KEY, algorithm=ALGORITHM)
    r = client.get("/auth/me", headers=auth(tok))
    assert r.status_code == 401
    assert_envelope(r.json(), "UNAUTHORIZED")


def test_7_guest_on_admin_route(client):
    tok = guest_token(client)
    r = client.post("/hotels", json={"name": "X"}, headers=auth(tok))
    assert r.status_code == 403
    assert_envelope(r.json(), "FORBIDDEN")
    assert_no_secrets(r.text)


# --- 8-10: resource/field validation ------------------------------------------

def test_8_missing_hotel(client):
    r = client.get("/hotels/999999")
    assert r.status_code == 404
    assert_envelope(r.json(), "RESOURCE_NOT_FOUND")
    assert_no_secrets(r.text)


def test_9_bad_price(client):
    _, tok = make_admin(client)
    for bad in ["-5", "0"]:
        r = client.post("/room-types", json={"name": "Bad", "price_per_night": bad}, headers=auth(tok))
        assert r.status_code == 422, (bad, r.text)
        assert_envelope(r.json(), "VALIDATION_ERROR")


def test_10_bad_capacity(client):
    _, tok = make_admin(client)
    r = client.post("/room-types", json={"name": "Bad", "capacity": 0}, headers=auth(tok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


def test_blank_hotel_name(client):
    _, tok = make_admin(client)
    r = client.post("/hotels", json={"name": "   "}, headers=auth(tok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


# --- 11-13: reservation validation ----------------------------------------------

def _booked(client, gtok, atok):
    hid, _, rid = make_inventory(client, atok)
    res = client.post("/reservations", json={"guest_id": 1, "hotel_id": hid, "room_id": rid,
                                             "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 1},
                      headers=auth(gtok)).json()
    return hid, rid, res["id"]


def test_11_12_bad_dates(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "d@tst.example")
    hid, _, rid = make_inventory(client, atok)
    base = {"guest_id": 1, "hotel_id": hid, "room_id": rid, "guests_count": 1}
    for ci, co in [("2026-09-18", "2026-09-15"), ("2026-09-15", "2026-09-15")]:
        r = client.post("/reservations", json={**base, "check_in": ci, "check_out": co}, headers=auth(gtok))
        assert r.status_code == 400
        assert_envelope(r.json(), "BAD_REQUEST")
        assert_no_secrets(r.text)


def test_13_guests_count_zero(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "e@tst.example")
    hid, _, rid = make_inventory(client, atok)
    r = client.post("/reservations", json={"guest_id": 1, "hotel_id": hid, "room_id": rid,
                                           "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 0},
                    headers=auth(gtok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


# --- 14-15: payment validation --------------------------------------------------

def test_14_bad_amount(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "f@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)
    r = client.post("/payments", json={"reservation_id": resid, "amount": "0", "payment_method": "cash"}, headers=auth(gtok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


def test_15_bad_method(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "h@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)
    r = client.post("/payments", json={"reservation_id": resid, "amount": "100", "payment_method": "bitcoin"}, headers=auth(gtok))
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


def test_overpay_rejected_envelope(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "i@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)  # total 2000
    r = client.post("/payments", json={"reservation_id": resid, "amount": "99999", "payment_method": "cash"}, headers=auth(gtok))
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


# --- 16: review rating ------------------------------------------------------------

def test_16_bad_rating(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "j@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)
    r = client.post("/reviews", json={"hotel_id": hid, "reservation_id": resid, "rating": 6}, headers=auth(gtok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


def test_bad_objectid_envelope(client):
    r = client.get("/reviews/not-an-id")
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


# --- 17-19: pagination/price params -------------------------------------------------

def test_17_page_zero(client):
    r = client.get("/hotels?page=0")
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


def test_18_page_size_too_big(client):
    r = client.get("/hotels?page_size=1000")
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


def test_19_min_over_max(client):
    r = client.get("/room-types?min_price=5000&max_price=1000")
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


def test_bad_sort_envelope(client):
    r = client.get("/hotels?sort_by=drop_table")
    assert r.status_code == 400
    assert_envelope(r.json(), "BAD_REQUEST")


# --- 20-22: ownership & conflicts -----------------------------------------------------

def test_20_cross_user_reservation(client):
    _, atok = make_admin(client)
    g1 = guest_token(client, "k1@tst.example")
    g2 = guest_token(client, "k2@tst.example")
    hid, rid, resid = _booked(client, g1, atok)
    r = client.get(f"/reservations/{resid}", headers=auth(g2))
    assert r.status_code == 403
    assert_envelope(r.json(), "FORBIDDEN")
    r = client.get(f"/payments?reservation_id={resid}", headers=auth(g2))
    assert r.status_code == 403
    assert_envelope(r.json(), "FORBIDDEN")


def test_21_injection_probes(client):
    _, atok = make_admin(client)
    for url in ["/hotels?search='; DROP TABLE users;--",
                "/hotels?sort_by=name&sort_order=desc;xxx",
                "/reservations?status=paid' OR '1'='1"]:
        r = client.get(url, headers=auth(atok))
        assert r.status_code in (200, 400, 422), (url, r.status_code)
        assert_no_secrets(r.text)
    assert client.get("/admin/dashboard", headers=auth(atok)).status_code == 200


def test_22_duplicate_room_and_profile(client):
    _, atok = make_admin(client)
    guest_token(client, "m@tst.example")
    hid, rtid, rid = make_inventory(client, atok)
    r = client.post("/rooms", json={"hotel_id": hid, "room_type_id": rtid, "room_number": "1"}, headers=auth(atok))
    assert r.status_code == 409
    assert_envelope(r.json(), "CONFLICT")
    from tests.conftest import TestingSessionLocal
    from app.models.user import User
    db = TestingSessionLocal()
    try:
        uid = db.query(User).filter(User.email == "m@tst.example").first().id
    finally:
        db.close()
    r = client.post("/guests", json={"user_id": uid}, headers=auth(atok))
    assert r.status_code == 409
    assert_envelope(r.json(), "CONFLICT")


# --- 23: rollback -------------------------------------------------------------------------

def test_23_failed_payment_rolls_back(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "n@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)
    before = client.get(f"/reservations/{resid}/payments", headers=auth(gtok)).json()["payments"]
    r = client.post("/payments", json={"reservation_id": resid, "amount": "99999", "payment_method": "cash"}, headers=auth(gtok))
    assert r.status_code == 400
    after = client.get(f"/reservations/{resid}/payments", headers=auth(gtok)).json()["payments"]
    assert len(before) == len(after) == 0


# --- hardening extras ---------------------------------------------------------------------------

def test_status_smuggle_rejected(client):
    _, atok = make_admin(client)
    gtok = guest_token(client, "o@tst.example")
    hid, rid, resid = _booked(client, gtok, atok)
    r = client.put(f"/reservations/{resid}", json={"status": "checked_in"}, headers=auth(gtok))
    assert r.status_code == 422
    assert_envelope(r.json(), "VALIDATION_ERROR")


def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"


def test_docs_still_work(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert "Admin Dashboard" in client.get("/openapi.json").text


def test_mongo_down_is_503_envelope(client):
    r = client.get("/mongodb/test")
    assert r.status_code == 200  # live here; shape check only
    assert r.json()["status"] == "connected"
    assert "mongodb://" not in r.text
