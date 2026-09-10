"""Hotel CRUD + search tests (Step 13 §7)."""

from tests.helpers import admin_token, auth, guest_token


def _hid(client, atok, name="H Inn", city="H City"):
    return client.post("/hotels", json={"name": name, "city": city}, headers=auth(atok)).json()["id"]


def test_admin_create_hotel(client):
    atok = admin_token(client)
    r = client.post("/hotels", json={"name": "Grand", "city": "Kochi"}, headers=auth(atok))
    assert r.status_code == 201 and r.json()["city"] == "Kochi"


def test_guest_cannot_create(client):
    gtok = guest_token(client, "g@tst.example")
    assert client.post("/hotels", json={"name": "X"}, headers=auth(gtok)).status_code == 403
    assert client.post("/hotels", json={"name": "X"}).status_code == 401


def test_get_hotel(client):
    atok = admin_token(client)
    hid = _hid(client, atok)
    r = client.get(f"/hotels/{hid}")
    assert r.status_code == 200 and r.json()["name"] == "H Inn"


def test_missing_hotel_404(client):
    r = client.get("/hotels/999999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_update_hotel(client):
    atok = admin_token(client)
    hid = _hid(client, atok)
    r = client.put(f"/hotels/{hid}", json={"city": "Goa"}, headers=auth(atok))
    assert r.status_code == 200 and r.json()["city"] == "Goa"
    assert client.put("/hotels/999999", json={"city": "X"}, headers=auth(atok)).status_code == 404


def test_delete_hotel(client):
    atok = admin_token(client)
    hid = _hid(client, atok)
    assert client.delete(f"/hotels/{hid}", headers=auth(atok)).status_code == 204
    assert client.get(f"/hotels/{hid}").status_code == 404


def test_invalid_hotel_input(client):
    atok = admin_token(client)
    assert client.post("/hotels", json={"name": "   "}, headers=auth(atok)).status_code == 422
    assert client.post("/hotels", json={}, headers=auth(atok)).status_code == 422


def test_hotel_pagination(client):
    atok = admin_token(client)
    for i in range(3):
        _hid(client, atok, name=f"P Inn {i}")
    r = client.get("/hotels?page=1&page_size=2").json()
    assert len(r["items"]) == 2 and r["pagination"]["total_items"] == 3
    assert r["pagination"]["has_next"] is True
    r2 = client.get("/hotels?page=2&page_size=2").json()
    assert len(r2["items"]) == 1 and r2["pagination"]["has_previous"] is True


def test_hotel_search_city_sort(client):
    atok = admin_token(client)
    _hid(client, atok, name="Seaside Grand", city="Kochi")
    _hid(client, atok, name="Hill View", city="Munnar")
    assert len(client.get("/hotels?search=grand").json()["items"]) == 1
    assert len(client.get("/hotels?city=kochi").json()["items"]) == 1
    names = [x["name"] for x in client.get("/hotels?sort_by=name&sort_order=asc").json()["items"]]
    assert names == sorted(names)
    assert client.get("/hotels?sort_by=nope").status_code == 400
