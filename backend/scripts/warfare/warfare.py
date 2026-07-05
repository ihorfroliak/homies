"""D6 production warfare harness — runs REAL concurrent attacks against the
live docker+Postgres stack and reports actual numbers. No fabricated logs."""

import datetime as dt
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://localhost:8000/v1"
WEBHOOK_SECRET = "dev-webhook-secret"
PW = "password-123456"

admin = httpx.Client(base_url=BASE, timeout=30)


def reg(email, role):
    admin.post("/auth/register", json={"email": email, "password": PW, "role": role})


def login(email, password=PW):
    r = admin.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def uniq(p):
    return f"{p}-{uuid.uuid4().hex[:8]}@homies.example"


def new_listing(host_hdr, price=30000, cap=2):
    r = admin.post(
        "/listings",
        json={"title": "War flat", "city": "Warsaw", "address": f"ul. {uuid.uuid4().hex[:6]}",
              "capacity": cap, "nightly_price_amount": price},
        headers=host_hdr,
    )
    r.raise_for_status()
    lid = r.json()["id"]
    admin.post(f"/listings/{lid}/publish", headers=host_hdr).raise_for_status()
    return lid


def make_guest():
    e = uniq("g")
    reg(e, "guest")
    return login(e)


print("=" * 60)
admin.post("/auth/register", json={"email": "warhost@homies.example", "password": PW, "role": "host"})
H = login("warhost@homies.example")
admin.post("/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"}, headers=H)
try:
    A = login("admin@homies.example", "admin-live-password-1")
except Exception:
    import subprocess
    subprocess.run(["docker", "exec", "homies-api-1", "python", "-m", "app.scripts.create_admin",
                    "admin@homies.example", "admin-live-password-1"], check=False)
    A = login("admin@homies.example", "admin-live-password-1")
host_id = admin.get("/me", headers=H).json()["id"]


def balances():
    return admin.get("/admin/ledger/balances", headers=A).json()


def recon():
    return admin.get("/admin/ledger/reconciliation", headers=A).json()


def call(method, path, hdr, json=None):
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.request(method, path, headers=hdr, json=json)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else None)


# ---- SCENARIO 1: concurrent booking storm, SAME listing + SAME dates ----
print("\n[1] CONCURRENCY: N guests book same listing+dates simultaneously")
N = 60
lid = new_listing(H)
ci = (dt.date.today() + dt.timedelta(days=40)).isoformat()
co = (dt.date.today() + dt.timedelta(days=43)).isoformat()
guests = [make_guest() for _ in range(N)]


def try_book(hdr):
    return call("POST", "/bookings",
                {**hdr, "Idempotency-Key": uuid.uuid4().hex},
                {"listing_id": lid, "check_in": ci, "check_out": co})


with ThreadPoolExecutor(max_workers=N) as ex:
    results = list(ex.map(try_book, guests))
codes = Counter(c for c, _ in results)
success = [b for c, b in results if c == 201]
print(f"  attempts={N} results={dict(codes)}")
print(f"  VERDICT double-booking: {'PASS' if len(success) == 1 else 'FAIL'} (exactly 1 success expected, got {len(success)})")

# ---- SCENARIO 2: concurrent booking, DIFFERENT dates (all should pass) ----
print("\n[2] CONCURRENCY: N guests book same listing, DIFFERENT non-overlapping dates")
lid2 = new_listing(H)
M = 30
guests2 = [make_guest() for _ in range(M)]


def try_book_distinct(args):
    i, hdr = args
    d1 = (dt.date.today() + dt.timedelta(days=100 + i * 2)).isoformat()
    d2 = (dt.date.today() + dt.timedelta(days=101 + i * 2)).isoformat()
    return call("POST", "/bookings", {**hdr, "Idempotency-Key": uuid.uuid4().hex},
                {"listing_id": lid2, "check_in": d1, "check_out": d2})


with ThreadPoolExecutor(max_workers=M) as ex:
    r2 = list(ex.map(try_book_distinct, enumerate(guests2)))
codes2 = Counter(c for c, _ in r2)
print(f"  attempts={M} results={dict(codes2)}")
print(f"  VERDICT distinct-dates: {'PASS' if codes2.get(201) == M else 'FAIL'} (all {M} should succeed)")

# ---- SCENARIO 3: idempotency retry storm (same guest+key, concurrent) ----
print("\n[3] RETRY STORM: same guest + same Idempotency-Key, concurrent")
lid3 = new_listing(H)
gk = make_guest()
key = uuid.uuid4().hex
di = (dt.date.today() + dt.timedelta(days=200)).isoformat()
do = (dt.date.today() + dt.timedelta(days=203)).isoformat()


def retry_same(_):
    return call("POST", "/bookings", {**gk, "Idempotency-Key": key},
                {"listing_id": lid3, "check_in": di, "check_out": do})


with ThreadPoolExecutor(max_workers=20) as ex:
    r3 = list(ex.map(retry_same, range(20)))
codes3 = Counter(c for c, _ in r3)
booking_ids = {b["id"] for c, b in r3 if c == 201 and b}
print(f"  attempts=20 results={dict(codes3)} distinct_booking_ids={len(booking_ids)}")
# money-safety: at most ONE booking/payment must exist for this key
print(f"  VERDICT no-duplicate-booking: {'PASS' if len(booking_ids) <= 1 else 'FAIL'}")

# ---- SCENARIO 4: webhook replay storm ----
print("\n[4] WEBHOOK REPLAY STORM: 1 booking, same succeeded event x200 concurrent")
lid4 = new_listing(H)
g4 = make_guest()
wi = (dt.date.today() + dt.timedelta(days=300)).isoformat()
wo = (dt.date.today() + dt.timedelta(days=303)).isoformat()
_, bk4 = call("POST", "/bookings", {**g4, "Idempotency-Key": uuid.uuid4().hex},
              {"listing_id": lid4, "check_in": wi, "check_out": wo})
intent = bk4["payment_intent_id"]
esc_before = balances().get("booking_escrow", 0)


def fire_wh(_):
    return call("POST", "/payments/webhook/simulated",
                {"X-Webhook-Secret": WEBHOOK_SECRET},
                {"intent_id": intent, "event": "payment_intent.succeeded"})


with ThreadPoolExecutor(max_workers=50) as ex:
    r4 = list(ex.map(fire_wh, range(200)))
codes4 = Counter(c for c, _ in r4)
# count capture entries for this booking
entries = admin.get("/admin/ledger/entries?limit=100", headers=A).json()
caps = [e for e in entries if e["kind"] == "payment_captured" and e["booking_id"] == bk4["id"]]
esc_after = balances().get("booking_escrow", 0)
print(f"  webhook_calls=200 results={dict(codes4)}")
print(f"  capture_entries_for_booking={len(caps)} escrow_delta={esc_after - esc_before} (expect -{bk4['total_amount']})")
print(f"  VERDICT single-capture: {'PASS' if len(caps) == 1 else 'FAIL'}")

# ---- SCENARIO 5: concurrent payout runs (double-payout attempt) ----
print("\n[5] DOUBLE PAYOUT: complete booking, then fire payout run x10 concurrent")
call("POST", f"/bookings/{bk4['id']}/complete", A)
rev_before = balances().get("platform_revenue", 0)


def fire_payout(_):
    return call("POST", f"/hosts/{host_id}/payouts/run", A)


with ThreadPoolExecutor(max_workers=10) as ex:
    r5 = list(ex.map(fire_payout, range(10)))
paid_counts = [b["bookings_paid"] for c, b in r5 if c == 200 and b]
total_paid = sum(paid_counts)
print(f"  payout_runs=10 total_bookings_paid_across_runs={total_paid}")
print(f"  VERDICT no-double-payout: {'PASS' if total_paid == 1 else 'FAIL'} (booking must be paid exactly once)")

# ---- SCENARIO 6: ghost booking (KNOWN GAP — inventory block via never-pay) ----
print("\n[6] FRAUD: ghost booking blocks inventory (never pay, dates stay locked)")
lid6 = new_listing(H)
gg = make_guest()
gi = (dt.date.today() + dt.timedelta(days=400)).isoformat()
go = (dt.date.today() + dt.timedelta(days=403)).isoformat()
call("POST", "/bookings", {**gg, "Idempotency-Key": uuid.uuid4().hex},
     {"listing_id": lid6, "check_in": gi, "check_out": go})
# another guest tries same dates — pending (unpaid) booking should block
gg2 = make_guest()
code6, _ = call("POST", "/bookings", {**gg2, "Idempotency-Key": uuid.uuid4().hex},
                {"listing_id": lid6, "check_in": gi, "check_out": go})
print(f"  second guest on same dates got {code6} (409 = inventory blocked by unpaid pending)")
print(f"  VERDICT ghost-booking-gap: {'CONFIRMED GAP (P1: need auto-void)' if code6 == 409 else 'no gap'}")

# ---- FINAL: full-system reconciliation after all chaos ----
print("\n[7] LEDGER RECONCILIATION after all warfare")
rc = recon()
print(f"  reconciliation ok={rc['ok']} grand_total={rc['grand_total']}")
print(f"  balances={rc['balances']}")
print(f"  VERDICT ledger-integrity: {'PASS' if rc['ok'] and rc['grand_total'] == 0 else 'FAIL'}")
print("=" * 60)
