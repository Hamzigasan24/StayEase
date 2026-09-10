"""Review tests (Step 13 §15, MongoDB)."""

from tests.helpers import admin_token, auth, booking, guest_token, inventory


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "v@tst.example")
    inv = inventory(client, atok)
    res = booking(client, gtok, inv["hotel"], inv["room"])
    return atok, gtok, inv, res


def test_crud_and_ownership(client):
    atok, gtok, inv, res = setup(client)
    g2 = guest_token(client, "v2@tst.example")
    r = client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 5, "comment": "Nice"},
                    headers=auth(gtok))
    assert r.status_code == 201 and len(r.json()["id"]) == 24
    rid = r.json()["id"]
    assert client.get(f"/reviews/{rid}").status_code == 200
    assert client.put(f"/reviews/{rid}", json={"rating": 1}, headers=auth(g2)).status_code == 403
    assert client.put(f"/reviews/{rid}", json={"rating": 4}, headers=auth(gtok)).json()["rating"] == 4
    assert client.delete(f"/reviews/{rid}", headers=auth(g2)).status_code == 403
    assert client.delete(f"/reviews/{rid}", headers=auth(gtok)).status_code == 204
    assert client.delete(f"/reviews/{rid}", headers=auth(atok)).status_code == 404


def test_rating_validation(client):
    atok, gtok, inv, res = setup(client)
    assert client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 0},
                       headers=auth(gtok)).status_code == 422
    assert client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 6},
                       headers=auth(gtok)).status_code == 422
    assert client.post("/reviews", json={}, headers=auth(gtok)).status_code in (401, 422)
    assert client.get("/reviews/bad-id").status_code == 400


def test_other_guests_stay_rejected_and_dup(client):
    atok, gtok, inv, res = setup(client)
    g2 = guest_token(client, "v3@tst.example")
    assert client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 3},
                       headers=auth(g2)).status_code == 403
    client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 5},
                headers=auth(gtok))
    assert client.post("/reviews", json={"hotel_id": inv["hotel"], "reservation_id": res["id"], "rating": 4},
                       headers=auth(gtok)).status_code == 409
    assert len(client.get(f"/reviews?hotel_id={inv['hotel']}").json()) >= 1
