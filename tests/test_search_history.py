"""Search history tests (Step 13 §15, MongoDB)."""

from tests.helpers import admin_token, auth, guest_token


def test_crud_and_ownership(client):
    atok = admin_token(client)
    g1 = guest_token(client, "s1@tst.example")
    g2 = guest_token(client, "s2@tst.example")
    r = client.post("/search-history", json={"city": "Kochi", "guests_count": 2}, headers=auth(g1))
    assert r.status_code == 201 and r.json()["city"] == "Kochi"
    sid = r.json()["id"]
    assert [s["id"] for s in client.get("/search-history", headers=auth(g1)).json()] == [sid]
    assert client.get("/search-history", headers=auth(g2)).json() == []
    assert client.get(f"/search-history/{sid}", headers=auth(g2)).status_code == 403
    assert client.get("/search-history?user_id=1", headers=auth(g2)).status_code == 403
    assert len(client.get("/search-history", headers=auth(atok)).json()) >= 1
    assert client.delete(f"/search-history/{sid}", headers=auth(g2)).status_code == 403
    assert client.delete(f"/search-history/{sid}", headers=auth(g1)).status_code == 204
    assert client.post("/search-history", json={"city": "X"}).status_code == 401
