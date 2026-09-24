"""H1 (audit 2026-07-28) — currency consistency.

The ledger sums account balances across all currencies without scoping, so a
non-default currency on a listing would silently corrupt escrow math and the I5
invariant. Listing creation is the single choke point; these tests pin that only
the configured default currency is accepted (and case-normalized)."""

import pytest

from app.core.config import settings
from tests.conftest import auth, register_and_login

# LEGACY_DORMANT runtime (TASK-002 R1): see tests/legacy_runtime.py.
pytestmark = pytest.mark.legacy_runtime

_LISTING = {
    "title": "Studio",
    "city": "Warsaw",
    "address": "ul. Testowa 1",
    "capacity": 2,
    "nightly_price_amount": 40000,
}


def _create(client, host_token, **overrides):
    return client.post("/v1/listings", json={**_LISTING, **overrides}, headers=auth(host_token))


def test_default_currency_when_omitted(client):
    host = register_and_login(client, "host-cur1@example.com", "host")
    resp = _create(client, host)
    assert resp.status_code == 201, resp.text
    assert resp.json()["currency"] == settings.default_currency


def test_explicit_default_currency_accepted(client):
    host = register_and_login(client, "host-cur2@example.com", "host")
    resp = _create(client, host, currency=settings.default_currency)
    assert resp.status_code == 201, resp.text
    assert resp.json()["currency"] == settings.default_currency


def test_lowercase_currency_is_normalized(client):
    host = register_and_login(client, "host-cur3@example.com", "host")
    resp = _create(client, host, currency=settings.default_currency.lower())
    assert resp.status_code == 201, resp.text
    assert resp.json()["currency"] == settings.default_currency


def test_non_default_currency_rejected(client):
    host = register_and_login(client, "host-cur4@example.com", "host")
    # USD is a valid ISO code but unsupported until the ledger is currency-scoped.
    other = "USD" if settings.default_currency != "USD" else "EUR"
    resp = _create(client, host, currency=other)
    assert resp.status_code == 422, resp.text
    assert "currency" in resp.text
