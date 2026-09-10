"""Room type tests (Step 13 §8)."""

from tests.helpers import admin_token, auth, guest_token


def _tid(client, atok, name="T Std", price="1000", capacity=2):
    return client.post("/room-types", json={"name": name, "price_per_night": price, "capacity": capacity},
                       headers=auth(atok)).json()["id"]


def test_crud(client):
    atok = admin_token(client)
    tid = _tid(client, atok)
    assert client.get(f"/room-types/{tid}").status_code == 200
    r = client.put(f"/room-types/{tid}", json={"capacity": 3}, headers=auth(atok))
    assert r.status_code == 200 and r.json()["capacity"] == 3
    assert r.json()["price_per_night"] == "1000.00"
    assert client.delete(f"/room-types/{tid}", headers=auth(atok)).status_code == 204
    assert client.get(f"/room-types/{tid}").status_code == 404


def test_guest_cannot_write(client):
    gtok = guest_token(client, "g@tst.example")
    assert client.post("/room-types", json={"name": "X"}, headers=auth(gtok)).status_code == 403


def test_price_capacity_validation(client):
    atok = admin_token(client)
    assert client.post("/room-types", json={"name": "X", "price_per_night": "-5"}, headers=auth(atok)).status_code == 422
    assert client.post("/room-types", json={"name": "X", "price_per_night": "0"}, headers=auth(atok)).status_code == 422
    assert client.post("/room-types", json={"name": "X", "capacity": 0}, headers=auth(atok)).status_code == 422
    assert client.post("/room-types", json={"name": "  "}, headers=auth(atok)).status_code == 422


def test_search_price_capacity_sort_page(client):
    atok = admin_token(client)
    _tid(client, atok, "Cheap", "500", 1)
    _tid(client, atok, "Luxe", "9000", 4)
    assert len(client.get("/room-types?search=lux").json()["items"]) == 1
    assert len(client.get("/room-types?min_price=1000&max_price=2000").json()["items"]) == 0
    assert len(client.get("/room-types?min_capacity=2").json()["items"]) == 1
    top = client.get("/room-types?sort_by=price_per_night&sort_order=desc").json()["items"][0]
    assert top["name"] == "Luxe"
    assert client.get("/room-types?min_price=9&max_price=1").status_code == 400
    p = client.get("/room-types?page=2&page_size=1").json()
    assert len(p["items"]) == 1 and p["pagination"]["total_items"] == 2
