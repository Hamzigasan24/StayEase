"""Room CRUD + filtering tests (Step 13 §9)."""

from tests.helpers import admin_token, auth, guest_token, inventory


def test_crud(client):
    atok = admin_token(client)
    inv = inventory(client, atok)
    r = client.get(f"/rooms/{inv['room']}")
    assert r.status_code == 200 and r.json()["status"] == "available"
    u = client.put(f"/rooms/{inv['room']}", json={"floor": 2}, headers=auth(atok))
    assert u.status_code == 200 and u.json()["floor"] == 2
    assert client.delete(f"/rooms/{inv['room']}", headers=auth(atok)).status_code == 204
    assert client.get(f"/rooms/{inv['room']}").status_code == 404


def test_fk_validation(client):
    atok = admin_token(client)
    inv = inventory(client, atok)
    assert client.post("/rooms", json={"hotel_id": 999999, "room_type_id": inv["type"], "room_number": "X"},
                       headers=auth(atok)).status_code == 404
    assert client.post("/rooms", json={"hotel_id": inv["hotel"], "room_type_id": 999999, "room_number": "X"},
                       headers=auth(atok)).status_code == 404
    assert client.post("/rooms", json={"hotel_id": inv["hotel"], "room_type_id": inv["type"], "room_number": "1"},
                       headers=auth(atok)).status_code == 409


def test_admin_only_writes(client):
    gtok = guest_token(client, "g@tst.example")
    assert client.post("/rooms", json={}, headers=auth(gtok)).status_code in (403, 422)
    atok = admin_token(client)
    inv = inventory(client, atok)
    assert client.put(f"/rooms/{inv['room']}", json={"floor": 1}, headers=auth(gtok)).status_code == 403
    assert client.delete(f"/rooms/{inv['room']}", headers=auth(gtok)).status_code == 403


def test_filters_sort_page(client):
    atok = admin_token(client)
    hid = client.post("/hotels", json={"name": "F Inn"}, headers=auth(atok)).json()["id"]
    t1 = client.post("/room-types", json={"name": "A", "price_per_night": "100", "capacity": 1}, headers=auth(atok)).json()["id"]
    t2 = client.post("/room-types", json={"name": "B", "price_per_night": "200", "capacity": 2}, headers=auth(atok)).json()["id"]
    client.post("/rooms", json={"hotel_id": hid, "room_type_id": t1, "room_number": "10", "floor": 1}, headers=auth(atok))
    client.post("/rooms", json={"hotel_id": hid, "room_type_id": t2, "room_number": "20", "floor": 2, "status": "occupied"}, headers=auth(atok))
    assert len(client.get(f"/rooms?hotel_id={hid}").json()["items"]) == 2
    assert len(client.get(f"/rooms?room_type_id={t2}").json()["items"]) == 1
    assert len(client.get("/rooms?status=available").json()["items"]) == 1
    assert len(client.get("/rooms?floor=2").json()["items"]) == 1
    assert len(client.get("/rooms?room_number=1").json()["items"]) == 1
    nums = [x["room_number"] for x in client.get("/rooms?sort_by=room_number&sort_order=asc").json()["items"]]
    assert nums == sorted(nums)
    p = client.get("/rooms?page=1&page_size=1").json()
    assert len(p["items"]) == 1 and p["pagination"]["total_items"] == 2
    assert client.get("/rooms?status=bogus").status_code == 400
    assert client.get("/rooms?page=0").status_code == 400
