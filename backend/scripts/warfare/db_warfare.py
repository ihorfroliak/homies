"""D6 DB failure warfare: kill Postgres mid-load, verify graceful
degradation + ACID recovery (no partial corruption)."""

import datetime as dt
import subprocess
import time
import uuid

import httpx

BASE = "http://localhost:8000/v1"
PW = "password-123456"
c = httpx.Client(base_url=BASE, timeout=10)


def login(email, password=PW):
    r = c.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


A = login("admin@homies.example", "admin-live-password-1")
H = login("warhost@homies.example")
host_id = c.get("/me", headers=H).json()["id"]
lid = c.post("/listings", json={"title": "DBwar", "city": "Warsaw", "address": f"ul.{uuid.uuid4().hex[:6]}",
             "capacity": 2, "nightly_price_amount": 30000}, headers=H).json()["id"]
c.post(f"/listings/{lid}/publish", headers=H)

print("BEFORE: recon =", c.get("/admin/ledger/reconciliation", headers=A).json()["ok"])

print("\n>>> docker stop homies-db-1 (simulate DB crash)")
subprocess.run(["docker", "stop", "homies-db-1"], check=True, capture_output=True)

# Fire a booking during the outage
e = f"g-{uuid.uuid4().hex[:8]}@homies.example"
c.post("/auth/register", json={"email": e, "password": PW, "role": "guest"})
try:
    G = login(e)
    ci = (dt.date.today() + dt.timedelta(days=500)).isoformat()
    co = (dt.date.today() + dt.timedelta(days=503)).isoformat()
    r = c.post("/bookings", json={"listing_id": lid, "check_in": ci, "check_out": co},
               headers={**G, "Idempotency-Key": uuid.uuid4().hex})
    print(f"  booking during outage: HTTP {r.status_code} (expect 5xx, NOT a silent success)")
    outage_status = r.status_code
except httpx.HTTPError as ex:
    print(f"  booking during outage raised {type(ex).__name__} (connection failed cleanly)")
    outage_status = "conn_error"

print("\n>>> docker start homies-db-1 + wait healthy")
subprocess.run(["docker", "start", "homies-db-1"], check=True, capture_output=True)
for _ in range(30):
    h = subprocess.run(["docker", "inspect", "-f", "{{.State.Health.Status}}", "homies-db-1"],
                       capture_output=True, text=True)
    if h.stdout.strip() == "healthy":
        break
    time.sleep(2)
time.sleep(3)  # let API reconnect pool

# Recovery verification
for attempt in range(10):
    try:
        rc = c.get("/admin/ledger/reconciliation", headers=login("admin@homies.example", "admin-live-password-1")).json()
        break
    except httpx.HTTPError:
        time.sleep(2)
print(f"\nAFTER RECOVERY: recon ok={rc['ok']} grand_total={rc['grand_total']}")
print(f"  VERDICT ACID-survival: {'PASS' if rc['ok'] and rc['grand_total'] == 0 else 'FAIL'}")
print(f"  degradation was: {outage_status} (safe = error, unsafe = 201 phantom)")
