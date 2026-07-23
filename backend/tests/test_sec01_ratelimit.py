"""SEC-01 — perimeter rate limiting.

Deterministic: the token-bucket store is driven by an injectable clock, so no
test sleeps. Covers thresholds, refill, isolation between subjects, proxy trust,
exemptions, and the two abuse scenarios that matter most — credential stuffing
and account-lockout denial of service.
"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core import ratelimit as rl
from tests.conftest import auth, register_and_login

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float):
        self.t += seconds


@pytest.fixture()
def clock():
    """Swap the global limiter onto a store we control, then restore."""
    original = rl.limiter.store
    fake = FakeClock()
    rl.limiter.store = rl.InMemoryTokenBucketStore(clock=fake)
    yield fake
    rl.limiter.store = original


# --- store semantics (unit) ------------------------------------------------
def test_bucket_allows_burst_then_rejects_and_refills(clock):
    policy = rl.Policy("t", capacity=3, refill_per_second=1.0)
    store = rl.limiter.store
    assert [store.consume("k", policy)[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = store.consume("k", policy)
    assert allowed is False and retry_after > 0
    clock.advance(1.0)  # one token back
    assert store.consume("k", policy)[0] is True
    assert store.consume("k", policy)[0] is False


def test_peek_does_not_consume(clock):
    policy = rl.Policy("t", capacity=1, refill_per_second=0.0)
    store = rl.limiter.store
    assert store.peek("k", policy)[0] is True
    assert store.peek("k", policy)[0] is True  # still there
    assert store.consume("k", policy)[0] is True
    assert store.peek("k", policy)[0] is False  # now empty


def test_keys_are_isolated(clock):
    policy = rl.Policy("t", capacity=1, refill_per_second=0.0)
    store = rl.limiter.store
    assert store.consume("a", policy)[0] is True
    assert store.consume("a", policy)[0] is False
    assert store.consume("b", policy)[0] is True  # a different subject is unaffected


def test_store_failure_honours_policy_semantics(clock):
    class Broken:
        def consume(self, *a, **k):
            raise RuntimeError("store down")

        def peek(self, *a, **k):
            raise RuntimeError("store down")

        def reset(self):
            pass

    rl.limiter.store = Broken()
    # authentication: fail CLOSED (an unavailable limiter must not open the door)
    assert rl.limiter.check("k", rl.AUTH_LOGIN_IP)[0] is False
    # availability-sensitive traffic: fail OPEN (deeper controls stay authoritative)
    assert rl.limiter.check("k", rl.BOOKING_CREATE)[0] is True
    assert rl.limiter.check("k", rl.PUBLIC_READ)[0] is True


# --- proxy trust ------------------------------------------------------------
def test_forwarded_header_is_ignored_unless_proxies_are_declared():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
        client=SimpleNamespace(host="10.0.0.9"),
    )
    # 0 hops declared => spoofed header must not be honoured
    assert rl.client_ip(request, trust_proxy_hops=0) == "10.0.0.9"
    # 1 declared proxy => take the hop nearest to us, not the attacker-controlled left edge
    assert rl.client_ip(request, trust_proxy_hops=1) == "5.6.7.8"
    assert rl.client_ip(request, trust_proxy_hops=2) == "1.2.3.4"


def test_missing_client_does_not_crash():
    request = SimpleNamespace(headers={}, client=None)
    assert rl.client_ip(request, trust_proxy_hops=0) == "unknown"


# --- policy resolution ------------------------------------------------------
def test_policy_resolution_matches_route_categories():
    assert rl.resolve_policy("POST", "/v1/auth/login") is rl.AUTH_LOGIN_IP
    assert rl.resolve_policy("POST", "/v1/auth/register") is rl.AUTH_REGISTER
    assert rl.resolve_policy("POST", "/v1/auth/refresh") is rl.AUTH_REFRESH
    assert rl.resolve_policy("POST", "/v1/bookings") is rl.BOOKING_CREATE
    assert rl.resolve_policy("POST", "/v1/bookings/abc/cancel") is rl.BOOKING_MUTATE
    assert rl.resolve_policy("POST", "/v1/listings") is rl.LISTING_WRITE
    assert rl.resolve_policy("GET", "/v1/listings") is rl.PUBLIC_READ
    assert rl.resolve_policy("GET", "/v1/admin/users") is rl.ADMIN
    # payment webhooks must NEVER be throttled — provider retries would break
    # financial consistency
    assert rl.resolve_policy("POST", "/v1/payments/webhook/stripe") is None
    assert rl.resolve_policy("POST", "/v1/payments/webhook/simulated") is None
    assert rl.resolve_policy("GET", "/healthz") is None
    assert rl.resolve_policy("GET", "/metrics") is None


# --- HTTP behaviour ---------------------------------------------------------
def test_login_burst_is_throttled_but_normal_login_works(client, clock):
    register_and_login(client, "victim@example.com", "guest")
    # a normal login succeeds
    ok = client.post("/v1/auth/login",
                     json={"email": "victim@example.com", "password": "password-123456"})
    assert ok.status_code == 200

    # credential stuffing from one source is stopped
    codes = [
        client.post("/v1/auth/login",
                    json={"email": "victim@example.com", "password": "wrong-password"}).status_code
        for _ in range(30)
    ]
    assert 429 in codes
    assert codes[-1] == 429
    # 429 carries Retry-After
    blocked = client.post("/v1/auth/login",
                          json={"email": "victim@example.com", "password": "wrong-password"})
    assert blocked.status_code == 429 and "retry-after" in {k.lower() for k in blocked.headers}


def test_throttled_login_recovers_after_refill(client, clock):
    register_and_login(client, "u@example.com", "guest")
    for _ in range(30):
        client.post("/v1/auth/login", json={"email": "u@example.com", "password": "bad-password"})
    assert client.post("/v1/auth/login",
                       json={"email": "u@example.com",
                             "password": "password-123456"}).status_code == 429
    clock.advance(3600)  # buckets refill
    assert client.post("/v1/auth/login",
                       json={"email": "u@example.com",
                             "password": "password-123456"}).status_code == 200


def test_account_bucket_is_spent_only_by_failures(client, clock):
    """Successful logins must not spend the account budget — otherwise a busy
    legitimate user would throttle themselves out of their own account."""
    register_and_login(client, "good@example.com", "guest")
    account_key = f"{rl.AUTH_LOGIN_ACCOUNT.name}:account:good@example.com"

    for _ in range(5):  # stay inside the per-IP budget; these all succeed
        assert client.post("/v1/auth/login",
                           json={"email": "good@example.com",
                                 "password": "password-123456"}).status_code == 200
    # account bucket is still at full capacity
    allowed = [rl.limiter.store.consume(account_key, rl.AUTH_LOGIN_ACCOUNT)[0]
               for _ in range(rl.AUTH_LOGIN_ACCOUNT.capacity)]
    assert all(allowed)

    # by contrast, a failed attempt does spend one
    rl.limiter.reset()
    client.post("/v1/auth/login", json={"email": "good@example.com", "password": "wrong"})
    spent = [rl.limiter.store.consume(account_key, rl.AUTH_LOGIN_ACCOUNT)[0]
             for _ in range(rl.AUTH_LOGIN_ACCOUNT.capacity)]
    assert spent[-1] is False  # one token already gone


def test_rate_limit_response_does_not_reveal_account_existence(client, clock):
    register_and_login(client, "real@example.com", "guest")
    real = [client.post("/v1/auth/login",
                        json={"email": "real@example.com", "password": "bad"}).status_code
            for _ in range(30)]
    rl.limiter.reset()
    fake = [client.post("/v1/auth/login",
                        json={"email": "ghost@example.com", "password": "bad"}).status_code
            for _ in range(30)]
    assert real == fake  # identical treatment for existing and non-existing accounts


def test_booking_burst_is_throttled_but_normal_booking_works(client, clock):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")

    first = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                        headers=auth(guest) | {"Idempotency-Key": "sec01-ok-1"})
    assert first.status_code == 201  # legitimate booking unaffected

    codes = []
    for i in range(30):
        d1 = (date.today() + timedelta(days=100 + i * 3)).isoformat()
        d2 = (date.today() + timedelta(days=101 + i * 3)).isoformat()
        codes.append(client.post("/v1/bookings",
                                 json={"listing_id": lid, "check_in": d1, "check_out": d2},
                                 headers=auth(guest) | {"Idempotency-Key": f"sec01-spam-{i}"}
                                 ).status_code)
    assert 429 in codes


def test_payment_webhooks_are_never_throttled(client, clock):
    """Stripe retries aggressively; throttling would create inconsistent
    financial state. Exemption must hold under sustained volume."""
    codes = {client.post("/v1/payments/webhook/simulated",
                         json={"intent_id": "pi_missing", "event": "payment_intent.succeeded"},
                         headers={"X-Webhook-Secret": "dev-webhook-secret"}).status_code
             for _ in range(60)}
    assert 429 not in codes


def test_rate_limiter_never_grants_access(client, clock):
    """Passing the limiter must not bypass authn/authz."""
    for _ in range(5):
        assert client.get("/v1/admin/users").status_code == 401
    guest = register_and_login(client, "g@example.com", "guest")
    assert client.get("/v1/admin/users", headers=auth(guest)).status_code == 403


def test_health_and_metrics_stay_available_under_load(client, clock):
    codes = {client.get("/healthz").status_code for _ in range(200)}
    assert codes == {200}
