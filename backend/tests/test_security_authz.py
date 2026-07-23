"""Security audit probes: object-level authorization (IDOR), role boundaries
and auth bypass. Written as executable evidence — every question the audit
asks ("can User A touch User B's data?") is answered by a running test, not by
reading the code."""

from datetime import date, timedelta

from tests.conftest import auth, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def _host_with_listing(client, email="hostA@example.com"):
    host = register_and_login(client, email, "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    return host, lid


def _booking(client, guest, lid, key):
    return client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": key}).json()


# ---- IDOR: guest A vs guest B -------------------------------------------
def test_guest_cannot_read_or_cancel_another_guests_booking(client):
    _, lid = _host_with_listing(client)
    guest_a = register_and_login(client, "a@example.com", "guest")
    guest_b = register_and_login(client, "b@example.com", "guest")
    bk = _booking(client, guest_a, lid, "sec-idor-0001")

    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(guest_b)).status_code == 404
    assert client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(guest_b)).status_code == 404
    assert client.post(f"/v1/bookings/{bk['id']}/cancel", headers=auth(guest_b)).status_code == 404
    assert client.post(f"/v1/bookings/{bk['id']}/checkin", headers=auth(guest_b)).status_code == 404
    # A's booking is untouched
    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(guest_a)).json()["status"] == "pending"


def test_booking_list_is_scoped_to_the_caller(client):
    _, lid = _host_with_listing(client)
    guest_a = register_and_login(client, "a@example.com", "guest")
    guest_b = register_and_login(client, "b@example.com", "guest")
    _booking(client, guest_a, lid, "sec-scope-0001")
    assert client.get("/v1/bookings", headers=auth(guest_b)).json() == []


# ---- IDOR: host A vs host B ---------------------------------------------
def test_host_cannot_modify_another_hosts_listing(client):
    _, lid_a = _host_with_listing(client, "hostA@example.com")
    host_b = register_and_login(client, "hostB@example.com", "host")

    assert client.patch(f"/v1/listings/{lid_a}", json={"nightly_price_amount": 1},
                        headers=auth(host_b)).status_code == 404
    assert client.post(f"/v1/listings/{lid_a}/publish", headers=auth(host_b)).status_code == 404
    assert client.post(f"/v1/listings/{lid_a}/blocks",
                       json={"start_date": CI, "end_date": CO},
                       headers=auth(host_b)).status_code == 404
    # price unchanged
    assert client.get(f"/v1/listings/{lid_a}").json()["nightly_price_amount"] == 40000


def test_host_cannot_trigger_another_hosts_payout(client, admin_token):
    host_a, _ = _host_with_listing(client, "hostA@example.com")
    host_b = register_and_login(client, "hostB@example.com", "host")
    host_a_id = client.get("/v1/me", headers=auth(host_a)).json()["id"]
    # payouts are admin-only: a host (even the owner) must be refused
    assert client.post(f"/v1/hosts/{host_a_id}/payouts/run",
                       headers=auth(host_b)).status_code == 403
    assert client.post(f"/v1/hosts/{host_a_id}/payouts/run",
                       headers=auth(host_a)).status_code == 403


# ---- Private data: notifications ----------------------------------------
def test_notifications_are_private_to_recipient(client):
    _, lid = _host_with_listing(client)
    guest_a = register_and_login(client, "a@example.com", "guest")
    guest_b = register_and_login(client, "b@example.com", "guest")
    _booking(client, guest_a, lid, "sec-notif-0001")
    assert client.get("/v1/me/notifications", headers=auth(guest_b)).json() == []
    assert client.get("/v1/me/notifications", headers=auth(guest_a)).json() != []


# ---- Role boundaries -----------------------------------------------------
def test_non_admin_cannot_reach_admin_surface(client):
    guest = register_and_login(client, "g@example.com", "guest")
    host = register_and_login(client, "h@example.com", "host")
    admin_paths = [
        "/v1/admin/users", "/v1/admin/bookings", "/v1/admin/payments",
        "/v1/admin/ledger/balances", "/v1/admin/ledger/reconciliation",
        "/v1/admin/payments/reconciliation", "/v1/admin/audit",
        "/v1/admin/incidents", "/v1/admin/founder-feed", "/v1/admin/notifications",
        "/v1/admin/notifications/queue",
    ]
    for path in admin_paths:
        assert client.get(path, headers=auth(guest)).status_code == 403, path
        assert client.get(path, headers=auth(host)).status_code == 403, path


def test_guest_cannot_use_host_surface_and_vice_versa(client):
    guest = register_and_login(client, "g@example.com", "guest")
    assert client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                       "address": "ul. Testowa 1", "capacity": 2,
                       "nightly_price_amount": 100}, headers=auth(guest)).status_code == 403
    assert client.get("/v1/hosts/me", headers=auth(guest)).status_code == 403
    host = register_and_login(client, "h@example.com", "host")
    _, lid = _host_with_listing(client, "hostA@example.com")
    # booking is guest-only
    assert client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(host) | {"Idempotency-Key": "sec-role-0001"}).status_code == 403


def test_privilege_escalation_via_registration_is_blocked(client):
    for role in ("admin", "Admin", "ADMIN", "superuser"):
        r = client.post("/v1/auth/register",
                        json={"email": f"esc-{role}@example.com", "password": "password-123456",
                              "role": role})
        assert r.status_code == 422, role


# ---- Auth bypass ---------------------------------------------------------
def test_protected_endpoints_reject_missing_or_bad_tokens(client):
    protected = ["/v1/me", "/v1/me/notifications", "/v1/bookings", "/v1/hosts/me",
                 "/v1/admin/users"]
    for path in protected:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
        assert client.get(path, headers={"Authorization": "Basic abc"}).status_code == 401


def test_token_signed_with_wrong_secret_is_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "someone", "role": "admin", "type": "access"},
                        "attacker-secret", algorithm="HS256")
    assert client.get("/v1/admin/users",
                      headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    register_and_login(client, "u@example.com", "guest")
    pair = client.post("/v1/auth/login",
                       json={"email": "u@example.com", "password": "password-123456"}).json()
    assert client.get("/v1/me",
                      headers={"Authorization": f"Bearer {pair['refresh_token']}"}).status_code == 401


# ---- Webhook trust boundary ---------------------------------------------
def test_webhook_cannot_confirm_a_booking_without_the_secret(client, admin_token):
    _, lid = _host_with_listing(client)
    guest = register_and_login(client, "g@example.com", "guest")
    bk = _booking(client, guest, lid, "sec-wh-0001")
    r = client.post("/v1/payments/webhook/simulated",
                    json={"intent_id": bk["payment_intent_id"],
                          "event": "payment_intent.succeeded"})
    assert r.status_code == 401
    assert client.get(f"/v1/bookings/{bk['id']}", headers=auth(guest)).json()["status"] == "pending"
