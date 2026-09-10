"""Shared test helpers (Step 13).

Thin wrappers around the API so feature tests stay readable.
Isolation comes from conftest (per-test TRUNCATE + Mongo cleanup),
so fixed emails/names are safe to reuse.
"""

from tests.conftest import TestingSessionLocal


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, email, name="Test User", password="TestPass123", extra=None):
    body = {"name": name, "email": email, "password": password}
    if extra:
        body.update(extra)
    return client.post("/auth/register", json=body)


def login(client, email, password="TestPass123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def admin_token(client, email="admin@tst.example"):
    """Create an admin directly (script equivalent) and return its JWT."""
    from app.models.user import User
    from app.utils.security import hash_password

    db = TestingSessionLocal()
    try:
        db.add(User(name="Admin", email=email, password_hash=hash_password("AdminPass123"), role="admin"))
        db.commit()
    finally:
        db.close()
    return login(client, email, "AdminPass123").json()["access_token"]


def guest_token(client, email):
    """Register + log in a guest, returning its JWT."""
    register(client, email=email)
    return login(client, email).json()["access_token"]


def inventory(client, atok, hotel="T Inn", city="T City", rtype="T Std",
              price="1000", capacity=2, number="1", status="available"):
    """Hotel + room type + room; returns ids dict."""
    hid = client.post("/hotels", json={"name": hotel, "city": city}, headers=auth(atok)).json()["id"]
    tid = client.post("/room-types", json={"name": rtype, "price_per_night": price, "capacity": capacity},
                      headers=auth(atok)).json()["id"]
    rid = client.post("/rooms", json={"hotel_id": hid, "room_type_id": tid, "room_number": number, "status": status},
                      headers=auth(atok)).json()["id"]
    return {"hotel": hid, "type": tid, "room": rid}


def booking(client, gtok, hid, rid, ci="2026-09-15", co="2026-09-18", guests=1):
    """Create a reservation as the token owner; returns the response dict."""
    return client.post("/reservations", json={"guest_id": 1, "hotel_id": hid, "room_id": rid,
                                              "check_in": ci, "check_out": co, "guests_count": guests},
                       headers=auth(gtok)).json()


def pay(client, gtok, resid, amount, method="cash", process=True):
    """Create (+optionally process) a payment; returns the payment dict."""
    pay = client.post("/payments", json={"reservation_id": resid, "amount": amount, "payment_method": method},
                      headers=auth(gtok)).json()
    if process:
        pay = client.post(f"/payments/{pay['id']}/process", headers=auth(gtok)).json()
    return pay
