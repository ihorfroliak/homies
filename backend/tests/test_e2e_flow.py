"""End-to-end vertical slice: host onboards -> listing -> guest books ->
payment webhook -> confirmed -> completed -> payout. Ledger must balance
at every step and reflect every money movement."""

from datetime import date, timedelta

from tests.conftest import auth, fire_webhook, register_and_login

CHECK_IN = date.today() + timedelta(days=30)
CHECK_OUT = CHECK_IN + timedelta(days=3)  # 3 nights
NIGHTLY = 35000  # 350.00 PLN
TOTAL = 3 * NIGHTLY
FEE = TOTAL * 1500 // 10_000  # 15% platform fee
NET = TOTAL - FEE


def full_flow(client, admin_token):
    host_token = register_and_login(client, "host@example.com", "host")
    guest_token = register_and_login(client, "guest@example.com", "guest")

    resp = client.post(
        "/v1/hosts/onboarding",
        json={"payout_iban": "PL61109010140000071219812874"},
        headers=auth(host_token),
    )
    assert resp.status_code == 200
    assert resp.json()["onboarding_state"] == "payout_ready"

    resp = client.post(
        "/v1/listings",
        json={
            "title": "Mokotów studio",
            "city": "Warsaw",
            "address": "ul. Testowa 1",
            "capacity": 2,
            "nightly_price_amount": NIGHTLY,
        },
        headers=auth(host_token),
    )
    assert resp.status_code == 201
    listing_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    resp = client.post(f"/v1/listings/{listing_id}/publish", headers=auth(host_token))
    assert resp.json()["status"] == "active"

    resp = client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": CHECK_IN.isoformat(),
            "check_out": CHECK_OUT.isoformat(),
        },
        headers=auth(guest_token) | {"Idempotency-Key": "e2e-key-0001"},
    )
    assert resp.status_code == 201, resp.text
    booking = resp.json()
    assert booking["status"] == "pending"
    assert booking["total_amount"] == TOTAL
    return listing_id, booking, host_token, guest_token


def test_booking_payment_payout_and_ledger(client, admin_token):
    listing_id, booking, host_token, guest_token = full_flow(client, admin_token)

    # Idempotent replay returns the same booking, not a duplicate
    resp = client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": CHECK_IN.isoformat(),
            "check_out": CHECK_OUT.isoformat(),
        },
        headers=auth(guest_token) | {"Idempotency-Key": "e2e-key-0001"},
    )
    assert resp.json()["id"] == booking["id"]

    # Payment webhook (replayed twice -> processed once)
    for _ in range(2):
        resp = fire_webhook(client, booking["payment_intent_id"])
        assert resp.status_code == 200

    resp = client.get(f"/v1/bookings/{booking['id']}", headers=auth(guest_token))
    assert resp.json()["status"] == "confirmed"

    # Ledger after capture: cash at provider = TOTAL, escrow owes TOTAL
    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token)).json()
    assert balances["provider_cash"] == TOTAL
    assert balances["booking_escrow"] == -TOTAL

    # Dates now blocked for another guest
    other_token = register_and_login(client, "guest2@example.com", "guest")
    resp = client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": CHECK_IN.isoformat(),
            "check_out": CHECK_OUT.isoformat(),
        },
        headers=auth(other_token) | {"Idempotency-Key": "e2e-key-0002"},
    )
    assert resp.status_code == 409

    # Complete stay (admin simulates the post-checkout timer)
    resp = client.post(f"/v1/bookings/{booking['id']}/complete", headers=auth(admin_token))
    assert resp.json()["status"] == "completed"

    # Payout run: escrow empties into host payable (net) + platform revenue (fee),
    # then the transfer leaves provider cash. Running twice pays only once.
    host_id = client.get("/v1/me", headers=auth(host_token)).json()["id"]
    for expected_paid in (1, 0):
        resp = client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["bookings_paid"] == expected_paid

    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token)).json()
    assert balances["booking_escrow"] == 0
    assert balances[f"host_payable:{host_id}"] == 0  # allocated and sent
    assert balances["platform_revenue"] == -FEE  # income (credit-normal)
    assert balances["provider_cash"] == FEE  # our fee remains at the provider

    recon = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert recon["ok"] is True
    assert recon["grand_total"] == 0

    # Audit captured the financial trail
    audit_rows = client.get("/v1/admin/audit", headers=auth(admin_token)).json()
    actions = {row["action"] for row in audit_rows}
    assert {"booking.created", "payment.succeeded", "booking.completed", "payout.run"} <= actions


def test_refund_flow(client, admin_token):
    listing_id, booking, host_token, guest_token = full_flow(client, admin_token)

    resp = fire_webhook(client, booking["payment_intent_id"])
    assert resp.status_code == 200

    resp = client.post(f"/v1/bookings/{booking['id']}/cancel", headers=auth(guest_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token)).json()
    assert balances["provider_cash"] == 0
    assert balances["booking_escrow"] == 0
    recon = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert recon["ok"] is True

    # Dates are free again
    other_token = register_and_login(client, "guest3@example.com", "guest")
    resp = client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": CHECK_IN.isoformat(),
            "check_out": CHECK_OUT.isoformat(),
        },
        headers=auth(other_token) | {"Idempotency-Key": "e2e-key-0003"},
    )
    assert resp.status_code == 201


def test_cancel_unpaid_booking_voids_payment(client, admin_token):
    _, booking, _, guest_token = full_flow(client, admin_token)
    resp = client.post(f"/v1/bookings/{booking['id']}/cancel", headers=auth(guest_token))
    assert resp.status_code == 200
    payments = client.get("/v1/admin/payments", headers=auth(admin_token)).json()
    assert payments[0]["status"] == "voided"
    balances = client.get("/v1/admin/ledger/balances", headers=auth(admin_token)).json()
    assert balances == {} or all(v == 0 for v in balances.values())
