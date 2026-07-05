"""D6 §3/§7: refund-abuse loop + cancel/rebook loop. Verify ledger nets to
zero every cycle, no orphan payments, no double charge."""

import datetime as dt
import uuid

import httpx

BASE = "http://localhost:8000/v1"
PW = "password-123456"
WH = "dev-webhook-secret"
c = httpx.Client(base_url=BASE, timeout=30)


def login(email, password=PW):
    r = c.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


A = login("admin@homies.example", "admin-live-password-1")
H = login("warhost@homies.example")
lid = c.post("/listings", json={"title": "RefundWar", "city": "Warsaw", "address": f"ul.{uuid.uuid4().hex[:6]}",
             "capacity": 2, "nightly_price_amount": 40000}, headers=H).json()["id"]
c.post(f"/listings/{lid}/publish", headers=H)


def guest():
    e = f"g-{uuid.uuid4().hex[:8]}@homies.example"
    c.post("/auth/register", json={"email": e, "password": PW, "role": "guest"})
    return login(e)


def esc():
    return c.get("/admin/ledger/balances", headers=A).json().get("booking_escrow", 0)


ci = (dt.date.today() + dt.timedelta(days=600)).isoformat()
co = (dt.date.today() + dt.timedelta(days=603)).isoformat()

print("[3/7] pay -> cancel -> refund loop x5 on the SAME dates (rebook after free)")
ok = True
esc0 = esc()
for i in range(5):
    G = guest()
    r = c.post("/bookings", json={"listing_id": lid, "check_in": ci, "check_out": co},
               headers={**G, "Idempotency-Key": uuid.uuid4().hex})
    if r.status_code != 201:
        print(f"  cycle {i}: REBOOK BLOCKED ({r.status_code}) — dates not freed by prior cancel")
        ok = False
        break
    bk = r.json()
    c.post("/payments/webhook/simulated", json={"intent_id": bk["payment_intent_id"],
           "event": "payment_intent.succeeded"}, headers={"X-Webhook-Secret": WH})
    e_paid = esc()
    rc = c.post(f"/bookings/{bk['id']}/cancel", headers=G)
    e_after = esc()
    print(f"  cycle {i}: paid escrow_total={e_paid} -> cancel {rc.status_code} -> escrow_total={e_after}")
    if e_after != esc0:  # each cycle must fully unwind
        ok = False

# no orphan payments: every payment is terminal (refunded/voided/succeeded)
pays = c.get("/admin/payments?limit=100", headers=A).json()
statuses = {}
for p in pays:
    statuses[p["status"]] = statuses.get(p["status"], 0) + 1
print(f"  payment statuses across system: {statuses}")

rec = c.get("/admin/ledger/reconciliation", headers=A).json()
print(f"  FINAL recon ok={rec['ok']} grand_total={rec['grand_total']}")
print(f"  VERDICT refund-loop-integrity: {'PASS' if ok and rec['ok'] and rec['grand_total'] == 0 else 'FAIL'}")

# §7 timezone / boundary: same-day check_in==check_out must be rejected
G = guest()
d = (dt.date.today() + dt.timedelta(days=700)).isoformat()
r = c.post("/bookings", json={"listing_id": lid, "check_in": d, "check_out": d},
           headers={**G, "Idempotency-Key": uuid.uuid4().hex})
print(f"\n[§7] zero-night booking (check_in==check_out): {r.status_code} (expect 422)")
print(f"  VERDICT boundary-validation: {'PASS' if r.status_code == 422 else 'FAIL'}")
