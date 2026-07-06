"""OAT-02 — Operational Notification Layer. Every scenario asserts:
event emitted -> notification triggered (logged/stored) -> state consistent.
Empty system per test (conftest)."""

from datetime import date, timedelta

from tests.conftest import auth, fire_webhook, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()
NIGHTLY = 40000


def _setup(client):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Managed Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": NIGHTLY},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    return host, guest, lid


def _book(client, guest, lid, key):
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": key}).json()


def _types(timeline):
    return [e["type"] for e in timeline]


# 1. booking -> BookingCreated event + guest notification
def test_booking_emits_event_and_notifies_guest(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0001")
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(guest)).json()
    assert "BookingCreated" in _types(state["timeline"])
    notes = client.get("/v1/me/notifications", headers=auth(guest)).json()
    assert any(n["type"] == "BookingCreated" and n["status"] == "sent" for n in notes)


# 2. confirmation -> BookingConfirmed + CheckInAvailable, operational state + all parties notified
def test_confirmation_notifies_all_and_advances_operational_state(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0002")
    fire_webhook(client, bk["payment_intent_id"])
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    assert state["lifecycle_state"] == "confirmed"
    assert state["operational_state"] == "checkin_available"
    assert {"BookingConfirmed", "CheckInAvailable"} <= set(_types(state["timeline"]))
    # guest + host in-app feeds, founder feed
    assert any(n["type"] == "BookingConfirmed" for n in
               client.get("/v1/me/notifications", headers=auth(guest)).json())
    assert any(n["type"] == "BookingConfirmed" for n in
               client.get("/v1/me/notifications", headers=auth(host)).json())
    feed = client.get("/v1/admin/founder-feed", headers=auth(admin_token)).json()
    assert any(n["type"] == "BookingConfirmed" for n in feed)


# 3. check-in -> CheckInCompleted, operational state checked_in, host notified
def test_checkin_updates_state_and_notifies_host(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0003")
    fire_webhook(client, bk["payment_intent_id"])
    r = client.post(f"/v1/bookings/{bk['id']}/checkin", headers=auth(guest))
    assert r.status_code == 200
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(guest)).json()
    assert state["operational_state"] == "checked_in"
    assert "CheckInCompleted" in _types(state["timeline"])
    assert any(n["type"] == "CheckInCompleted" for n in
               client.get("/v1/me/notifications", headers=auth(host)).json())


# 4. cancellation -> refund + CancellationProcessed, notification consistency, no orphan
def test_cancellation_refund_and_notification_consistency(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0004")
    fire_webhook(client, bk["payment_intent_id"])
    client.post(f"/v1/bookings/{bk['id']}/cancel", headers=auth(guest))
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(guest)).json()
    assert state["lifecycle_state"] == "cancelled"
    assert "CancellationProcessed" in _types(state["timeline"])
    # financial consistency: refund settled
    rec = client.get("/v1/admin/ledger/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] and rec["balances"]["booking_escrow"] == 0
    assert any(n["type"] == "CancellationProcessed" for n in
               client.get("/v1/me/notifications", headers=auth(guest)).json())


# 5. incident opened -> IncidentOpened, founder visibility
def test_incident_opened_reaches_founder_feed(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0005")
    r = client.post("/v1/admin/incidents",
                    json={"booking_id": bk["id"], "kind": "checkin_problem", "note": "no key"},
                    headers=auth(admin_token))
    assert r.status_code == 201
    feed = client.get("/v1/admin/founder-feed", headers=auth(admin_token)).json()
    assert any(n["type"] == "IncidentOpened" and n["booking_id"] == bk["id"] for n in feed)
    incidents = client.get("/v1/admin/incidents?status=open", headers=auth(admin_token)).json()
    assert any(i["booking_id"] == bk["id"] for i in incidents)


# 6. payout -> PayoutExecuted, host notified, operational state checked_out
def test_payout_notifies_host(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0006")
    fire_webhook(client, bk["payment_intent_id"])
    client.post(f"/v1/bookings/{bk['id']}/complete", headers=auth(admin_token))
    host_id = client.get("/v1/me", headers=auth(host)).json()["id"]
    client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token))
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    assert state["operational_state"] == "checked_out"
    assert "PayoutExecuted" in _types(state["timeline"])
    assert any(n["type"] == "PayoutExecuted" for n in
               client.get("/v1/me/notifications", headers=auth(host)).json())


# Acceptance: event-to-state idempotency (duplicate webhook -> no duplicate events)
def test_idempotent_events_no_duplicates(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0007")
    for _ in range(3):
        fire_webhook(client, bk["payment_intent_id"])
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    types = _types(state["timeline"])
    assert types.count("BookingConfirmed") == 1
    assert types.count("CheckInAvailable") == 1


# Acceptance: founder can reconstruct the full timeline from events only
def test_founder_reconstructs_timeline_from_events(client, admin_token):
    host, guest, lid = _setup(client)
    bk = _book(client, guest, lid, "oat2-0008")
    fire_webhook(client, bk["payment_intent_id"])
    client.post(f"/v1/bookings/{bk['id']}/checkin", headers=auth(guest))
    client.post(f"/v1/bookings/{bk['id']}/complete", headers=auth(admin_token))
    host_id = client.get("/v1/me", headers=auth(host)).json()["id"]
    client.post(f"/v1/hosts/{host_id}/payouts/run", headers=auth(admin_token))
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    ordered = _types(state["timeline"])
    assert ordered == ["BookingCreated", "BookingConfirmed", "CheckInAvailable",
                       "CheckInCompleted", "PayoutExecuted"]
