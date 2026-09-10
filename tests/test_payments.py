"""Payment tests (Step 13 §13). No card data anywhere by design."""

import re
from decimal import Decimal

from tests.helpers import admin_token, auth, booking, guest_token, inventory


def setup(client):
    atok = admin_token(client)
    gtok = guest_token(client, "p@tst.example")
    inv = inventory(client, atok, price="2500")
    res = booking(client, gtok, inv["hotel"], inv["room"])
    return atok, gtok, res


def test_create_pending_with_reference(client):
    atok, gtok, res = setup(client)
    r = client.post("/payments", json={"reservation_id": res["id"], "amount": "1000", "payment_method": "gcash"},
                    headers=auth(gtok))
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert re.fullmatch(r"STAY-\d{8}-[0-9A-F]{6}(-\w+)?", r.json()["transaction_reference"])
    assert "cvv" not in r.text.lower() and "card number" not in r.text.lower()


def test_cancelled_reservation_rejected(client):
    atok, gtok, res = setup(client)
    client.post(f"/reservations/{res['id']}/cancel", headers=auth(gtok))
    r = client.post("/payments", json={"reservation_id": res["id"], "amount": "100", "payment_method": "cash"},
                    headers=auth(gtok))
    assert r.status_code == 400


def test_amount_method_validation(client):
    atok, gtok, res = setup(client)
    assert client.post("/payments", json={"reservation_id": res["id"], "amount": "0", "payment_method": "cash"},
                       headers=auth(gtok)).status_code == 422
    assert client.post("/payments", json={"reservation_id": res["id"], "amount": "-5", "payment_method": "cash"},
                       headers=auth(gtok)).status_code == 422
    assert client.post("/payments", json={"reservation_id": res["id"], "amount": "100", "payment_method": "bitcoin"},
                       headers=auth(gtok)).status_code == 400
    assert client.post("/payments", json={"reservation_id": 999999, "amount": "100", "payment_method": "cash"},
                       headers=auth(gtok)).status_code == 404


def test_no_overpayment(client):
    atok, gtok, res = setup(client)  # total 7500
    assert client.post("/payments", json={"reservation_id": res["id"], "amount": "99999", "payment_method": "cash"},
                       headers=auth(gtok)).status_code == 400


def test_process_confirms_and_history(client):
    atok, gtok, res = setup(client)
    p = client.post("/payments", json={"reservation_id": res["id"], "amount": "7500", "payment_method": "card"},
                    headers=auth(gtok)).json()
    r = client.post(f"/payments/{p['id']}/process", headers=auth(gtok)).json()
    assert r["status"] == "paid" and r["paid_at"]
    assert client.get(f"/reservations/{res['id']}", headers=auth(gtok)).json()["status"] == "confirmed"
    h = client.get(f"/reservations/{res['id']}/payments", headers=auth(gtok)).json()
    assert h["total_paid"] == "7500.00" and h["remaining_balance"] == "0.00"
    assert client.post(f"/payments/{p['id']}/process", headers=auth(gtok)).status_code == 400


def test_ownership(client):
    atok, gtok, res = setup(client)
    g2 = guest_token(client, "p2@tst.example")
    p = client.post("/payments", json={"reservation_id": res["id"], "amount": "100", "payment_method": "cash"},
                    headers=auth(gtok)).json()["id"]
    assert client.get(f"/payments/{p}", headers=auth(g2)).status_code == 403
    assert client.get(f"/reservations/{res['id']}/payments", headers=auth(g2)).status_code == 403
    assert client.get("/payments", headers=auth(g2)).json()["items"] == []
    assert len(client.get("/payments", headers=auth(atok)).json()["items"]) >= 1


def test_refund_admin_only_and_kept(client):
    atok, gtok, res = setup(client)
    p = client.post("/payments", json={"reservation_id": res["id"], "amount": "7500", "payment_method": "cash"},
                    headers=auth(gtok)).json()["id"]
    client.post(f"/payments/{p}/process", headers=auth(gtok))
    assert client.post(f"/payments/{p}/refund", headers=auth(gtok)).status_code == 403
    r = client.post(f"/payments/{p}/refund", headers=auth(atok))
    assert r.status_code == 200 and r.json()["status"] == "refunded"
    assert client.post(f"/payments/{p}/refund", headers=auth(atok)).status_code == 400
    h = client.get(f"/reservations/{res['id']}/payments", headers=auth(atok)).json()
    assert len(h["payments"]) == 1 and Decimal(h["total_paid"]) == 0


def test_filters_sort(client):
    atok, gtok, res = setup(client)
    client.post("/payments", json={"reservation_id": res["id"], "amount": "100", "payment_method": "gcash"},
                headers=auth(gtok))
    assert client.get("/payments?status=pending", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert client.get("/payments?payment_method=gcash", headers=auth(atok)).json()["pagination"]["total_items"] == 1
    assert client.get("/payments?sort_by=amount&sort_order=desc", headers=auth(atok)).status_code == 200
    assert client.get("/payments?status=nope", headers=auth(atok)).status_code == 400
