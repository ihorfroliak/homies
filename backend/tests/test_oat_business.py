"""OAT-01 — Operational Acceptance Testing. Validates whole-business flows
from an empty system (fresh DB per test via conftest). Where a business
capability does not exist, the scenario STOPS and asserts its absence as
evidence (endpoint 404/405) rather than pretending.

Result matrix and gaps: docs/reviews/2026-07-06-oat-01-report.md.
"""

from datetime import date, timedelta

from tests.conftest import auth, fire_webhook, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()  # 3 nights
NIGHTLY = 40000
TOTAL = 3 * NIGHTLY
FEE = TOTAL * 1500 // 10_000
NET = TOTAL - FEE


def _host_with_listing(client):
    host = register_and_login(client, "host@example.com", "host")
    r = client.post("/v1/hosts/onboarding",
                    json={"payout_iban": "PL61109010140000071219812874"}, headers=auth(host))
    assert r.status_code == 200 and r.json()["onboarding_state"] == "payout_ready"
    lid = client.post("/v1/listings", json={"title": "Managed Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": NIGHTLY},
                      headers=auth(host)).json()["id"]
    # calendar config: host blocks a maintenance window
    client.post(f"/v1/listings/{lid}/blocks",
                json={"start_date": (date.today() + timedelta(days=1)).isoformat(),
                      "end_date": (date.today() + timedelta(days=2)).isoformat()}, headers=auth(host))
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    return host, lid


# ---------- SCENARIO 1: Host onboarding -> property bookable ----------
def test_s1_host_onboarding_to_bookable(client):
    host, lid = _host_with_listing(client)
    listed = client.get("/v1/listings?city=Warsaw").json()
    assert any(x["id"] == lid and x["status"] == "active" for x in listed)
    # OUTCOME: property is bookable. PASS.


# ---------- SCENARIO 2: Guest booking -> confirmed + reconciled ----------
def test_s2_guest_booking_confirmed_and_reconciled(client, admin_token):
    _host_with_listing(client)
    lid = client.get("/v1/listings?city=Warsaw").json()[0]["id"]
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": "oat-s2-0001"}).json()
    assert bk["status"] == "pending" and bk["total_amount"] == TOTAL
    fire_webhook(client, bk["payment_intent_id"])
    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(guest)).json()["status"] == "confirmed"
    # availability updated
    avail = client.get(f"/v1/listings/{lid}/availability?from={CI}&to={CO}").json()
    assert all(d["status"] == "booked" for d in avail["days"])
    # money reconciled
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] and rec["balances"]["booking_escrow"] == -TOTAL
    # GAP: no notifications module -> guest/host are not notified in-platform.


# ---------- SCENARIO 3: Check-in (instructions, ops tasks, cleaning) ----------
def test_s3_checkin_is_a_dead_end(client):
    _host_with_listing(client)
    # STOP: no check-in instructions, no operations/cleaning task endpoints.
    assert client.get("/v1/operations/tasks").status_code in (404, 405)
    assert client.get("/v1/bookings/any/checkin").status_code in (404, 405)
    # Evidence: the Operations/check-in capability is not built.


# ---------- SCENARIO 4: Stay completion (payout closes; ops steps absent) ----------
def test_s4_completion_payout_closes_but_no_inspection(client, admin_token):
    host, lid = _host_with_listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": "oat-s4-0001"}).json()
    fire_webhook(client, bk["payment_intent_id"])
    # completion + payout (financial close) — EXISTS
    client.post(f"/v1/bookings/{bk['id']}/complete", headers=auth(admin_token))
    host_id = client.get("/v1/me", headers=auth(host)).json()["id"]
    payout = client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token)).json()
    assert payout["bookings_paid"] == 1 and payout["paid_total"] == NET
    rec = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] and rec["grand_total"] == 0
    # STOP: inspection / damage / cleaning-turnover steps do not exist.
    assert client.post(f"/v1/bookings/{bk['id']}/inspection").status_code in (404, 405)


# ---------- SCENARIO 5: Cancellation -> refund + availability recovery ----------
def test_s5_cancellation_refund_no_orphan(client, admin_token):
    host, lid = _host_with_listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": "oat-s5-0001"}).json()
    fire_webhook(client, bk["payment_intent_id"])
    r = client.post(f"/v1/bookings/{bk['id']}/cancel", headers=auth(guest))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    rec = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] and rec["balances"]["booking_escrow"] == 0  # no orphan financial state
    # availability recovered
    avail = client.get(f"/v1/listings/{lid}/availability?from={CI}&to={CO}").json()
    assert all(d["status"] == "available" for d in avail["days"])
    # GAP: host-cancellation with penalty and platform-cancellation policy are
    # not distinct flows (only guest/admin cancel exists, no penalty engine).


# ---------- SCENARIO 6: Support tickets ----------
def test_s6_support_is_a_dead_end(client):
    assert client.get("/v1/support/tickets").status_code in (404, 405)
    assert client.post("/v1/support/tickets").status_code in (404, 405)
    # STOP: Support module not built.


# ---------- SCENARIO 7: Operational incident (reassign cleaner, etc.) ----------
def test_s7_operational_incident_is_a_dead_end(client):
    assert client.get("/v1/operations/incidents").status_code in (404, 405)
    # STOP: no operations module -> incident handling is off-platform/manual.


# ---------- SCENARIO 8: Dispute ----------
def test_s8_dispute_is_a_dead_end(client):
    assert client.get("/v1/disputes").status_code in (404, 405)
    assert client.post("/v1/disputes").status_code in (404, 405)
    # STOP: Disputes/Resolution Center not built.


# ---------- SCENARIO 9: Financial closing (end-of-day reconciliation) ----------
def test_s9_financial_closing_reconciles(client, admin_token):
    # empty system -> everything zero
    rec0 = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert rec0["ok"] and rec0["grand_total"] == 0
    # run a full booking+payout, then close
    host, lid = _host_with_listing(client)
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": "oat-s9-0001"}).json()
    fire_webhook(client, bk["payment_intent_id"])
    client.post(f"/v1/bookings/{bk['id']}/complete", headers=auth(admin_token))
    host_id = client.get("/v1/me", headers=auth(host)).json()["id"]
    client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token))
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    b = rec["balances"]
    assert rec["ok"]
    assert b["booking_escrow"] == 0             # refund liabilities settled
    assert b["platform_revenue"] == -FEE        # our revenue (credit-normal)
    assert b["provider_cash"] == FEE            # what remains at the provider is our fee
    assert b[f"host_payable:{host_id}"] == 0    # host paid out


# ---------- SCENARIO 10: Founder visibility (no SQL) ----------
def test_s10_founder_visibility_partial(client, admin_token):
    # Money questions ARE answerable via admin endpoints (no SQL):
    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token))
    assert balances.status_code == 200            # ours / host / provider balances
    recon = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token))
    assert recon.status_code == 200               # pending / divergence
    # NOT answerable: "which bookings require attention", "unresolved incidents"
    assert client.get("/v1/admin/attention").status_code in (404, 405)
    assert client.get("/v1/admin/incidents").status_code in (404, 405)
    # GAP: no operational dashboard for attention/incidents; money view only.
