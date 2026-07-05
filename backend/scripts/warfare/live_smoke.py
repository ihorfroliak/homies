"""Live e2e smoke against the running docker stack."""

import datetime as dt
import sys

import httpx

BASE = "http://localhost:8000/v1"
c = httpx.Client(base_url=BASE, timeout=20)


def register(email, role):
    r = c.post("/auth/register", json={"email": email, "password": "password-123456", "role": role})
    assert r.status_code in (201, 409), r.text


def login(email, password="password-123456"):
    r = c.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


register("host1@homies.example", "host")
register("guest1@homies.example", "guest")
H = login("host1@homies.example")
G = login("guest1@homies.example")
A = login("admin@homies.example", "admin-live-password-1")

r = c.post("/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"}, headers=H)
assert r.status_code == 200, r.text

r = c.post(
    "/listings",
    json={
        "title": "Mokotow Studio",
        "city": "Warsaw",
        "address": "ul. Pilotow 1",
        "capacity": 2,
        "nightly_price_amount": 35000,
    },
    headers=H,
)
assert r.status_code == 201, r.text
listing = r.json()
c.post(f"/listings/{listing['id']}/publish", headers=H).raise_for_status()

ci = (dt.date.today() + dt.timedelta(days=30)).isoformat()
co = (dt.date.today() + dt.timedelta(days=33)).isoformat()
r = c.post(
    "/bookings",
    json={"listing_id": listing["id"], "check_in": ci, "check_out": co},
    headers=G | {"Idempotency-Key": "live-smoke-0001"},
)
assert r.status_code == 201, r.text
bk = r.json()
print("BOOKING:", bk["status"], "total:", bk["total_amount"])

# Race check at DB level: parallel-ish duplicate with другим guest
register("guest2@homies.example", "guest")
G2 = login("guest2@homies.example")
r = c.post(
    "/bookings",
    json={"listing_id": listing["id"], "check_in": ci, "check_out": co},
    headers=G2 | {"Idempotency-Key": "live-smoke-0002"},
)
print("DOUBLE-BOOK ATTEMPT:", r.status_code)
assert r.status_code == 409

# Wrong webhook secret must bounce
r = c.post(
    "/payments/webhook/simulated",
    json={"intent_id": bk["payment_intent_id"], "event": "payment_intent.succeeded"},
    headers={"X-Webhook-Secret": "wrong"},
)
print("WEBHOOK wrong secret:", r.status_code)
assert r.status_code == 401

r = c.post(
    "/payments/webhook/simulated",
    json={"intent_id": bk["payment_intent_id"], "event": "payment_intent.succeeded"},
    headers={"X-Webhook-Secret": "dev-webhook-secret"},
)
assert r.status_code == 200, r.text
print("WEBHOOK:", r.json()["status"])

r = c.post(f"/bookings/{bk['id']}/complete", headers=A)
assert r.status_code == 200, r.text

host_id = c.get("/me", headers=H).json()["id"]
r = c.post(f"/hosts/{host_id}/payouts/run", headers=A)
assert r.status_code == 200, r.text
po = r.json()
print("PAYOUT: bookings:", po["bookings_paid"], "net:", po["paid_total"], "fee:", po["fee_total"])

rec = c.get("/admin/ledger/reconciliation", headers=A).json()
print("RECON ok:", rec["ok"], "grand_total:", rec["grand_total"])
print("BALANCES:", rec["balances"])
sys.exit(0 if rec["ok"] else 1)
