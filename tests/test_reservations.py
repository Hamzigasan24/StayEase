"""Reservation tests (Step 13 §11-12)."""

from tests.helpers import admin_token, auth, booking, guest_token, inventory


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "r@tst.example")
    inv = inventory(client, atok, price="2500")
    return atok, gtok, inv


def test_create_and_total(client):
    atok, gtok, inv = setup(client)
    r = client.post("/reservations", json={"guest_id": 999, "hotel_id": inv["hotel"], "room_id": inv["room"],
                                           "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 2},
                    headers=auth(gtok))
    assert r.status_code == 201
    assert r.json()["total_amount"] == "7500.00" and r.json()["status"] == "pending"


def test_unauthenticated_rejected(client):
    assert client.post("/reservations", json={}).status_code == 401
    assert client.get("/reservations").status_code == 401


def test_fk_and_hotel_rules(client):
    atok, gtok, inv = setup(client)
    base = {"guest_id": 1, "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 1}
    assert client.post("/reservations", json={**base, "hotel_id": 999999, "room_id": inv["room"]}, headers=auth(gtok)).status_code == 404
    assert client.post("/reservations", json={**base, "hotel_id": inv["hotel"], "room_id": 999999}, headers=auth(gtok)).status_code == 404
    hid2 = client.post("/hotels", json={"name": "Other"}, headers=auth(atok)).json()["id"]
    r = client.post("/reservations", json={**base, "hotel_id": hid2, "room_id": inv["room"]}, headers=auth(gtok))
    assert r.status_code == 400


def test_date_and_capacity_rules(client):
    atok, gtok, inv = setup(client)
    base = {"guest_id": 1, "hotel_id": inv["hotel"], "room_id": inv["room"]}
    assert client.post("/reservations", json={**base, "check_in": "2026-09-18", "check_out": "2026-09-15", "guests_count": 1}, headers=auth(gtok)).status_code == 400
    assert client.post("/reservations", json={**base, "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 0}, headers=auth(gtok)).status_code == 422
    assert client.post("/reservations", json={**base, "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 9}, headers=auth(gtok)).status_code == 400


def test_overlap_and_cancel_free(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"])
    clash = {"guest_id": 1, "hotel_id": inv["hotel"], "room_id": inv["room"], "guests_count": 1,
             "check_in": "2026-09-16", "check_out": "2026-09-17"}
    assert client.post("/reservations", json=clash, headers=auth(gtok)).status_code == 409
    client.post(f"/reservations/{res['id']}/cancel", headers=auth(gtok))
    assert client.post("/reservations", json=clash, headers=auth(gtok)).status_code == 201
    assert client.post(f"/reservations/{res['id']}/cancel", headers=auth(gtok)).status_code == 400


def test_server_controls_protected_fields(client):
    atok, gtok, inv = setup(client)
    r = client.post("/reservations", json={"guest_id": 1, "hotel_id": inv["hotel"], "room_id": inv["room"],
                                           "check_in": "2026-09-15", "check_out": "2026-09-18", "guests_count": 1,
                                           "total_amount": "1.00", "status": "confirmed"},
                    headers=auth(gtok)).json()
    assert r["total_amount"] == "7500.00" and r["status"] == "pending"
    assert client.put(f"/reservations/{r['id']}", json={"status": "checked_in"}, headers=auth(gtok)).status_code == 422


def test_ownership(client):
    atok, gtok, inv = setup(client)
    g2 = guest_token(client, "r2@tst.example")
    res = booking(client, gtok, inv["hotel"], inv["room"])
    assert client.get(f"/reservations/{res['id']}", headers=auth(g2)).status_code == 403
    assert [x["id"] for x in client.get("/reservations", headers=auth(g2)).json()["items"]] == []
    assert len(client.get("/reservations", headers=auth(atok)).json()["items"]) == 1


def test_filters_sort_page(client):
    atok, gtok, inv = setup(client)
    booking(client, gtok, inv["hotel"], inv["room"], "2026-09-15", "2026-09-18")
    booking(client, gtok, inv["hotel"], inv["room"], "2026-10-01", "2026-10-03")
    assert client.get("/reservations?status=pending", headers=auth(atok)).json()["pagination"]["total_items"] == 2
    assert len(client.get("/reservations?check_in_from=2026-10-01&check_in_to=2026-10-31", headers=auth(atok)).json()["items"]) == 1
    ids = [x["id"] for x in client.get("/reservations?sort_by=check_in&sort_order=asc", headers=auth(atok)).json()["items"]]
    assert ids == sorted(ids)
    p = client.get("/reservations?page=2&page_size=1", headers=auth(atok)).json()
    assert len(p["items"]) == 1 and p["pagination"]["total_items"] == 2
    assert client.get("/reservations?status=bogus", headers=auth(atok)).status_code == 400


def test_update_rechecks_and_reprices(client):
    atok, gtok, inv = setup(client)
    res = booking(client, gtok, inv["hotel"], inv["room"])
    r = client.put(f"/reservations/{res['id']}", json={"check_out": "2026-09-20"}, headers=auth(gtok)).json()
    assert r["total_amount"] == "12500.00"
    assert client.delete(f"/reservations/{res['id']}", headers=auth(gtok)).status_code == 403
    assert client.delete(f"/reservations/{res['id']}", headers=auth(atok)).status_code == 204
