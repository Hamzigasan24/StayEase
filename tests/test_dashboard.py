"""Dashboard tests (Step 13 §16, admin-only live aggregates)."""

from tests.helpers import admin_token, auth, booking, guest_token, inventory, pay


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "d@tst.example")
    inv = inventory(client, atok, hotel="D Inn", price="2000")
    res = booking(client, gtok, inv["hotel"], inv["room"])
    pay(client, gtok, res["id"], res["total_amount"])
    return atok, gtok, inv, res


def test_summary_and_auth(client):
    atok, gtok, inv, res = setup(client)
    d = client.get("/admin/dashboard", headers=auth(atok))
    assert d.status_code == 200
    body = d.json()
    assert body["users"] == {"total": 2, "guests": 1, "admins": 1}
    assert body["rooms"] == {"total": 1, "available": 1, "occupied": 0, "maintenance": 0}
    assert body["reservations"]["total"] == 1 and body["reservations"]["confirmed"] == 1
    assert body["payments"]["total_paid"] == "6000.00"
    assert "password" not in d.text and "hash" not in d.text
    assert client.get("/admin/dashboard", headers=auth(gtok)).status_code == 403
    assert client.get("/admin/dashboard").status_code == 401


def test_sub_endpoints(client):
    atok, gtok, inv, res = setup(client)
    assert client.get("/admin/dashboard/reservations", headers=auth(atok)).json()["total"] == 1
    rooms = client.get("/admin/dashboard/rooms", headers=auth(atok)).json()
    assert rooms["total_rooms"] == 1 and rooms["occupancy_rate"] == 0.0
    rev = client.get("/admin/dashboard/revenue", headers=auth(atok)).json()
    assert rev["total_paid"] == "6000.00" and rev["paid_transactions"] == 1
    occ = client.get("/admin/dashboard/occupancy", headers=auth(atok)).json()
    assert occ["total_rooms"] == 1 and occ["hotels"][0]["hotel_name"] == "D Inn"
    year = client.get("/admin/dashboard/monthly-revenue", headers=auth(atok)).json()
    assert year["year"] >= 2026 and sum(float(m["revenue"]) for m in year["months"]) == 6000.0
    assert client.get("/admin/dashboard/monthly-revenue?year=1999", headers=auth(atok)).status_code == 400
    rec = client.get("/admin/dashboard/recent-reservations", headers=auth(atok)).json()
    assert rec[0]["guest_name"] == "Test User" and "password" not in str(rec)
    pay_ = client.get("/admin/dashboard/recent-payments", headers=auth(atok)).json()
    assert pay_[0]["status"] == "paid" and "transaction_reference" in pay_[0]
    assert client.get("/admin/dashboard/recent-reservations?limit=0", headers=auth(atok)).status_code == 400
    hotels = client.get("/admin/dashboard/hotels", headers=auth(atok)).json()
    assert hotels["hotels"][0]["active_reservations"] == 1
    act = client.get("/admin/dashboard/activity", headers=auth(atok)).json()
    assert len(act["activities"]) >= 1
    assert client.get("/admin/dashboard/activity", headers=auth(gtok)).status_code == 403
