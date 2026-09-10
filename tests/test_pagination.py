"""Pagination tests (Step 13 §18, DB-side LIMIT/OFFSET)."""

from tests.helpers import admin_token, auth


def setup_hotels(client, atok, n=5):
    for i in range(n):
        client.post("/hotels", json={"name": f"Page Inn {i:02d}"}, headers=auth(atok))


def test_pages(client):
    atok = admin_token(client)
    setup_hotels(client, atok)
    p1 = client.get("/hotels?page=1&page_size=2").json()
    assert len(p1["items"]) == 2
    assert p1["pagination"] == {"page": 1, "page_size": 2, "total_items": 5,
                                "total_pages": 3, "has_next": True, "has_previous": False}
    p2 = client.get("/hotels?page=2&page_size=2").json()
    assert len(p2["items"]) == 2 and p2["pagination"]["has_previous"] is True
    p3 = client.get("/hotels?page=3&page_size=2").json()
    assert len(p3["items"]) == 1 and p3["pagination"]["has_next"] is False
    assert client.get("/hotels?page=9&page_size=2").json()["items"] == []


def test_sizes_and_invalid(client):
    atok = admin_token(client)
    setup_hotels(client, atok, 3)
    assert len(client.get("/hotels?page=1&page_size=1").json()["items"]) == 1
    assert len(client.get("/hotels?page=1&page_size=100").json()["items"]) == 3
    assert client.get("/hotels?page=0").status_code == 400
    assert client.get("/hotels?page_size=0").status_code == 400
    assert client.get("/hotels?page_size=101").status_code == 400


def test_pagination_other_resources(client):
    atok = admin_token(client)
    from tests.helpers import guest_token, inventory
    gtok = guest_token(client, "pg@tst.example")
    inv = inventory(client, atok)
    for i in range(3):
        client.post("/reservations", json={"guest_id": 1, "hotel_id": inv["hotel"], "room_id": inv["room"],
                                           "check_in": f"2026-09-{10 + i * 5:02d}",
                                           "check_out": f"2026-09-{12 + i * 5:02d}", "guests_count": 1},
                    headers=auth(gtok))
    r = client.get("/reservations?page=1&page_size=2", headers=auth(atok)).json()
    assert len(r["items"]) == 2 and r["pagination"]["total_items"] == 3
    g = client.get("/rooms?page=1&page_size=10").json()
    assert g["pagination"]["total_items"] == 1
