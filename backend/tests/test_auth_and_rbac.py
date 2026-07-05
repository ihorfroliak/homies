from tests.conftest import auth, register_and_login


def test_register_login_me_refresh(client):
    token = register_and_login(client, "user@example.com", "guest")
    resp = client.get("/v1/me", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"

    # duplicate email
    resp = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "password-123456", "role": "guest"},
    )
    assert resp.status_code == 409

    # wrong password
    resp = client.post(
        "/v1/auth/login", json={"email": "user@example.com", "password": "wrong-password-1"}
    )
    assert resp.status_code == 401

    # refresh rotation: token works once
    pair = client.post(
        "/v1/auth/login", json={"email": "user@example.com", "password": "password-123456"}
    ).json()
    resp = client.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert resp.status_code == 200
    resp = client.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert resp.status_code == 401  # reuse of rotated token is rejected


def test_rbac_boundaries(client, admin_token):
    guest_token = register_and_login(client, "guest@example.com", "guest")
    host_token = register_and_login(client, "host@example.com", "host")

    # guest cannot create listings
    resp = client.post(
        "/v1/listings",
        json={
            "title": "Nope",
            "city": "Warsaw",
            "address": "x",
            "nightly_price_amount": 100,
        },
        headers=auth(guest_token),
    )
    assert resp.status_code == 403

    # host cannot access admin endpoints
    resp = client.get("/v1/admin/users", headers=auth(host_token))
    assert resp.status_code == 403

    # anonymous cannot book
    resp = client.post("/v1/bookings", json={}, headers={"Idempotency-Key": "k" * 10})
    assert resp.status_code == 401

    # admin can list users
    resp = client.get("/v1/admin/users", headers=auth(admin_token))
    assert resp.status_code == 200

    # public API never creates admins
    resp = client.post(
        "/v1/auth/register",
        json={"email": "evil@example.com", "password": "password-123456", "role": "admin"},
    )
    assert resp.status_code == 422
