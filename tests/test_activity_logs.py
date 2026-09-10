"""Activity log tests (Step 13 §15, MongoDB append-only)."""

from tests.helpers import admin_token, auth, guest_token


def test_admin_only_and_append_only(client):
    atok = admin_token(client)
    gtok = guest_token(client, "a@tst.example")
    assert client.get("/activity-logs", headers=auth(gtok)).status_code == 403
    assert client.get("/activity-logs").status_code == 401
    assert client.post("/activity-logs", json={"action": "fake", "resource": "x"}, headers=auth(gtok)).status_code == 403
    r = client.post("/activity-logs", json={"action": "manual", "resource": "test", "details": {"k": "v"}}, headers=auth(atok))
    assert r.status_code == 201 and len(r.json()["id"]) == 24
    logs = client.get("/activity-logs", headers=auth(atok)).json()
    assert any(e["action"] == "manual" for e in logs)
    assert any(e["action"] == "login" for e in logs)  # backend auto-logged
    assert client.get(f"/activity-logs/{r.json()['id']}", headers=auth(atok)).status_code == 200
    assert client.get("/activity-logs/bad-id", headers=auth(atok)).status_code == 400
