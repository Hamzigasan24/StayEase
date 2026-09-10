"""Advanced search tests (Step 13 §17, DB-side filtering)."""

from tests.helpers import admin_token, auth, booking, guest_token, pay


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "q@tst.example")
    hid = client.post("/hotels", json={"name": "Search Grand", "city": "Kochi"}, headers=auth(atok)).json()["id"]
    t1 = client.post("/room-types", json={"name": "Q Std", "price_per_night": "1500", "capacity": 2}, headers=auth(atok)).json()["id"]
    t2 = client.post("/room-types", json={"name": "Q Suite", "price_per_night": "6000", "capacity": 4}, headers=auth(atok)).json()["id"]
    r1 = client.post("/rooms", json={"hotel_id": hid, "room_type_id": t1, "room_number": "11", "floor": 1}, headers=auth(atok)).json()["id"]
    r2 = client.post("/rooms", json={"hotel_id": hid, "room_type_id": t2, "room_number": "22", "floor": 2}, headers=auth(atok)).json()["id"]
    return atok, gtok, hid, t1, t2, r1, r2


def test_hotel_search(client):
    atok, *_ = setup(client)
    assert len(client.get("/hotels?search=grand").json()["items"]) == 1
    assert len(client.get("/hotels?city=KOCHI").json()["items"]) == 1
    assert client.get("/hotels?sort_by=name&sort_order=asc").status_code == 200


def test_room_search(client):
    atok, gtok, hid, t1, t2, r1, r2 = setup(client)
    assert len(client.get(f"/rooms?hotel_id={hid}").json()["items"]) == 2
    assert len(client.get(f"/rooms?room_type_id={t2}").json()["items"]) == 1
    assert len(client.get("/rooms?status=available").json()["items"]) == 2
    assert len(client.get("/rooms?floor=2").json()["items"]) == 1
    assert len(client.get("/rooms?room_number=1").json()["items"]) == 1


def test_availability_search(client):
    atok, gtok, hid, t1, t2, r1, r2 = setup(client)
    booking(client, gtok, hid, r1, "2026-09-15", "2026-09-18")
    busy = client.get(f"/rooms/available?hotel_id={hid}&check_in=2026-09-16&check_out=2026-09-17").json()["items"]
    assert {x["room_number"] for x in busy} == {"22"}
    free = client.get(f"/rooms/available?hotel_id={hid}&check_in=2026-09-18&check_out=2026-09-20").json()["items"]
    assert {x["room_number"] for x in free} == {"11", "22"}
    cap = client.get(f"/rooms/available?hotel_id={hid}&check_in=2026-11-01&check_out=2026-11-02&guests_count=3").json()["items"]
    assert [x["room_number"] for x in cap] == ["22"]
    price = client.get(f"/rooms/available?hotel_id={hid}&min_price=1000&max_price=2000").json()["items"]
    assert [x["room_number"] for x in price] == ["11"]
    assert price[0]["hotel_name"] == "Search Grand" and price[0]["price_per_night"] == "1500.00"


def test_reservation_search(client):
    atok, gtok, hid, t1, t2, r1, r2 = setup(client)
    booking(client, gtok, hid, r1, "2026-09-15", "2026-09-18")
    assert client.get("/reservations?status=pending", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert len(client.get(f"/reservations?hotel_id={hid}", headers=auth(atok)).json()["items"]) == 1
    assert len(client.get(f"/reservations?room_id={r1}", headers=auth(atok)).json()["items"]) == 1
    assert len(client.get("/reservations?check_in_from=2026-09-01&check_in_to=2026-09-30", headers=auth(atok)).json()["items"]) == 1
    by = client.get("/reservations?sort_by=total_amount&sort_order=desc", headers=auth(atok))
    assert by.status_code == 200


def test_payment_search(client):
    atok, gtok, hid, t1, t2, r1, r2 = setup(client)
    res = booking(client, gtok, hid, r1)
    pay(client, gtok, res["id"], "100", "gcash", process=False)
    assert client.get("/payments?status=pending", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert client.get("/payments?payment_method=gcash", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert client.get(f"/payments?reservation_id={res['id']}", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert client.get("/payments?sort_by=amount&sort_order=desc", headers=auth(atok)).status_code == 200


def test_guest_and_type_search(client):
    atok, gtok, hid, t1, t2, r1, r2 = setup(client)
    assert len(client.get("/guests?search=q@tst", headers=auth(atok)).json()["items"]) == 1
    assert len(client.get("/room-types?min_price=1000&max_price=2000").json()["items"]) == 1
    assert len(client.get("/room-types?min_capacity=3").json()["items"]) == 1
