from datetime import date, timedelta

from tests.conftest import auth, register_and_login

D30 = (date.today() + timedelta(days=30)).isoformat()
D33 = (date.today() + timedelta(days=33)).isoformat()
D32 = (date.today() + timedelta(days=32)).isoformat()
D35 = (date.today() + timedelta(days=35)).isoformat()


def _setup_listing(client):
    host_token = register_and_login(client, "host@example.com", "host")
    client.post(
        "/v1/hosts/onboarding",
        json={"payout_iban": "PL61109010140000071219812874"},
        headers=auth(host_token),
    )
    listing = client.post(
        "/v1/listings",
        json={
            "title": "Test flat",
            "city": "Warsaw",
            "address": "ul. Testowa 2",
            "capacity": 2,
            "nightly_price_amount": 20000,
        },
        headers=auth(host_token),
    ).json()
    client.post(f"/v1/listings/{listing['id']}/publish", headers=auth(host_token))
    return listing["id"], host_token


def test_overlap_partial_dates_conflict(client):
    listing_id, _ = _setup_listing(client)
    guest = register_and_login(client, "g1@example.com", "guest")
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D30, "check_out": D33},
        headers=auth(guest) | {"Idempotency-Key": "rules-0001"},
    )
    assert resp.status_code == 201

    # Overlapping tail [32, 35) conflicts with [30, 33)
    guest2 = register_and_login(client, "g2@example.com", "guest")
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D32, "check_out": D35},
        headers=auth(guest2) | {"Idempotency-Key": "rules-0002"},
    )
    assert resp.status_code == 409

    # Back-to-back [33, 35) is fine: check_out is exclusive
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D33, "check_out": D35},
        headers=auth(guest2) | {"Idempotency-Key": "rules-0003"},
    )
    assert resp.status_code == 201


def test_host_block_prevents_booking_and_shows_in_calendar(client):
    listing_id, host_token = _setup_listing(client)
    client.post(
        f"/v1/listings/{listing_id}/blocks",
        json={"start_date": D30, "end_date": D33},
        headers=auth(host_token),
    )
    guest = register_and_login(client, "g3@example.com", "guest")
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D30, "check_out": D33},
        headers=auth(guest) | {"Idempotency-Key": "rules-0004"},
    )
    assert resp.status_code == 409

    resp = client.get(f"/v1/listings/{listing_id}/availability?from={D30}&to={D35}")
    days = {d["date"]: d["status"] for d in resp.json()["days"]}
    assert days[D30] == "blocked"
    assert days[D33] == "available"


def test_validation_rules(client):
    listing_id, _ = _setup_listing(client)
    guest = register_and_login(client, "g4@example.com", "guest")

    # past check-in
    resp = client.post(
        "/v1/bookings",
        json={
            "listing_id": listing_id,
            "check_in": (date.today() - timedelta(days=1)).isoformat(),
            "check_out": D30,
        },
        headers=auth(guest) | {"Idempotency-Key": "rules-0005"},
    )
    assert resp.status_code == 422

    # check_out before check_in
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D33, "check_out": D30},
        headers=auth(guest) | {"Idempotency-Key": "rules-0006"},
    )
    assert resp.status_code == 422

    # over capacity
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D30, "check_out": D33, "guests": 5},
        headers=auth(guest) | {"Idempotency-Key": "rules-0007"},
    )
    assert resp.status_code == 422

    # missing idempotency key
    resp = client.post(
        "/v1/bookings",
        json={"listing_id": listing_id, "check_in": D30, "check_out": D33},
        headers=auth(guest),
    )
    assert resp.status_code == 422
