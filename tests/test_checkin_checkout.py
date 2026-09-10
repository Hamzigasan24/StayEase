"""Check-in/check-out lifecycle tests (Step 13 §14)."""

from datetime import timedelta

from app.controllers.reservation_controller import _today
from tests.helpers import admin_token, auth, booking, guest_token, inventory

TODAY = _today()


def D(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "c@tst.example")
    inv = inventory(client, atok, price="1000")
    return atok, gtok, inv


def full_pay(client, gtok, resid, total):
    pid = client.post("/payments", json={"reservation_id": resid, "amount": total, "payment_method": "cash"},
                      headers=auth(gtok)).json()["id"]
    client.post(f"/payments/{pid}/process", headers=auth(gtok))


def test_full_lifecycle(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"], D(0), D(2))
    full_pay(client, gtok, res["id"], res["total_amount"])
    r = client.post(f"/reservations/{res['id']}/check-in", headers=auth(atok))
    assert r.status_code == 200 and r.json()["status"] == "checked_in" and r.json()["checked_in_at"]
    assert client.get(f"/rooms/{inv['room']}").json()["status"] == "occupied"
    assert client.post(f"/reservations/{res['id']}/check-in", headers=auth(atok)).status_code == 400
    r = client.post(f"/reservations/{res['id']}/check-out", headers=auth(atok))
    assert r.status_code == 200 and r.json()["status"] == "checked_out" and r.json()["checked_out_at"]
    assert client.get(f"/rooms/{inv['room']}").json()["status"] == "available"
    assert client.post(f"/reservations/{res['id']}/check-out", headers=auth(atok)).status_code == 400


def test_guests_forbidden(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"], D(0), D(2))
    assert client.post(f"/reservations/{res['id']}/check-in", headers=auth(gtok)).status_code == 403
    assert client.post(f"/reservations/{res['id']}/check-out", headers=auth(gtok)).status_code == 403
    assert client.post(f"/reservations/{res['id']}/check-in").status_code == 401


def test_unpaid_and_early_rejected(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"], D(5), D(7))
    full_pay(client, gtok, res["id"], res["total_amount"])
    assert client.post(f"/reservations/{res['id']}/check-in", headers=auth(atok)).status_code == 400
    res2 = booking(client, gtok, inv["hotel"], inv["room"], D(10), D(12))
    assert client.post(f"/reservations/{res2['id']}/check-in", headers=auth(atok)).status_code == 400


def test_cancelled_rejected_and_invalid_transitions(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"], D(0), D(2))
    full_pay(client, gtok, res["id"], res["total_amount"])
    client.post(f"/reservations/{res['id']}/cancel", headers=auth(gtok))
    assert client.post(f"/reservations/{res['id']}/check-in", headers=auth(atok)).status_code == 400
    res2 = booking(client, gtok, inv["hotel"], inv["room"], D(0), D(1))
    full_pay(client, gtok, res2["id"], res2["total_amount"])
    client.post(f"/reservations/{res2['id']}/check-in", headers=auth(atok))
    assert client.post(f"/reservations/{res2['id']}/cancel", headers=auth(gtok)).status_code == 400


def test_maintenance_preserved(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"], D(0), D(1))
    full_pay(client, gtok, res["id"], res["total_amount"])
    client.post(f"/reservations/{res['id']}/check-in", headers=auth(atok))
    client.put(f"/rooms/{inv['room']}", json={"status": "maintenance"}, headers=auth(atok))
    client.post(f"/reservations/{res['id']}/check-out", headers=auth(atok))
    assert client.get(f"/rooms/{inv['room']}").json()["status"] == "maintenance"


def test_today_dashboard(client):
    atok, gtok, inv = setup(client)
    booking(client, gtok, inv["hotel"], inv["room"], D(0), D(2))
    d = client.get("/reservations/today", headers=auth(atok))
    assert d.status_code == 200 and d.json()["date"] == TODAY.isoformat()
    assert len(d.json()["check_ins"]) == 1
    assert client.get("/reservations/today", headers=auth(gtok)).status_code == 403
