"""Notification tests (Step 13 §15, MongoDB)."""

from tests.helpers import admin_token, auth, guest_token


def test_crud_and_ownership(client):
    atok = admin_token(client)
    g1 = guest_token(client, "n1@tst.example")
    g2 = guest_token(client, "n2@tst.example")
    r = client.post("/notifications", json={"type": "system", "title": "Hi", "message": "Hello"}, headers=auth(g1))
    assert r.status_code == 201 and r.json()["is_read"] is False
    nid = r.json()["id"]
    assert [n["id"] for n in client.get("/notifications", headers=auth(g1)).json()] == [nid]
    assert client.get("/notifications", headers=auth(g2)).json() == []
    assert client.get(f"/notifications/{nid}", headers=auth(g2)).status_code == 403
    assert len(client.get("/notifications", headers=auth(atok)).json()) >= 1
    r = client.put(f"/notifications/{nid}/read", headers=auth(g1))
    assert r.json()["is_read"] is True
    assert client.get("/notifications?unread_only=true", headers=auth(g1)).json() == []
    assert client.delete(f"/notifications/{nid}", headers=auth(g2)).status_code == 403
    assert client.delete(f"/notifications/{nid}", headers=auth(g1)).status_code == 204
    assert client.post("/notifications", json={"type": "bogus", "title": "X", "message": "Y"}, headers=auth(g1)).status_code == 400
    assert client.post("/notifications", json={"title": "X", "message": "Y"}).status_code == 401
