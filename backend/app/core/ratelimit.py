"""Perimeter rate limiting (SEC-01).

Central policy table + token-bucket store. Route handlers must never keep
their own counters — they either ride the middleware or call this limiter with
an explicit key (the login handler does that to throttle *failed* attempts per
account).

Storage: in-process token buckets. Chosen because the application is a single
uvicorn process, Redis is deployed nowhere and used by no code, and a DB write
per request is explicitly unacceptable. The `RateLimitStore` protocol keeps a
Redis/other backend a drop-in replacement.

  ⚠️ LIMITATION: counters are per-process. Running more than one worker or
  container multiplies every limit by the number of instances. Before scaling
  out, implement a shared store behind RateLimitStore (see docs/DECISIONS.md).

Algorithm: token bucket — smooth (no fixed-window edge bursts), cheap (two
floats per key), and it refills continuously, so an attacker can add friction
to an account but can never permanently lock it out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol

from prometheus_client import Counter

RATE_LIMIT_HITS = Counter(
    "homies_rate_limit_hits_total",
    "Rate limit decisions",
    ["policy", "outcome"],  # outcome: allowed | rejected | error
)


@dataclass(frozen=True)
class Policy:
    """capacity = burst size; refill_per_second = sustained rate.

    on_store_failure: what to do if the store raises.
      "closed" — deny (authentication: an unavailable limiter must not open
                 the door to credential stuffing)
      "open"   — allow (availability matters more than the perimeter, and a
                 deeper control is authoritative — e.g. the DB exclusion
                 constraint still prevents double booking)
    """

    name: str
    capacity: int
    refill_per_second: float
    on_store_failure: str = "open"


# --- Policy table -----------------------------------------------------------
# Tuned for a pilot: generous for humans, hostile to scripts.
AUTH_LOGIN_IP = Policy("auth_login_ip", capacity=10, refill_per_second=0.1, on_store_failure="closed")
AUTH_LOGIN_ACCOUNT = Policy(
    "auth_login_account", capacity=8, refill_per_second=0.05, on_store_failure="closed"
)
AUTH_REGISTER = Policy("auth_register", capacity=5, refill_per_second=0.02, on_store_failure="closed")
AUTH_REFRESH = Policy("auth_refresh", capacity=30, refill_per_second=0.5, on_store_failure="closed")
BOOKING_CREATE = Policy("booking_create", capacity=10, refill_per_second=0.2)
BOOKING_MUTATE = Policy("booking_mutate", capacity=20, refill_per_second=0.5)
LISTING_WRITE = Policy("listing_write", capacity=20, refill_per_second=0.5)
ADMIN = Policy("admin", capacity=120, refill_per_second=5.0)
PUBLIC_READ = Policy("public_read", capacity=120, refill_per_second=10.0)

# Future Product B categories (documented, deliberately not wired — no routes
# exist yet): free_listing_create, free_listing_edit, free_listing_delete,
# image_upload, search, contact_request, messaging, report, moderation_action.

# Paths that must NEVER be throttled. Payment webhooks are retried by the
# provider; throttling them would create inconsistent financial state, and the
# handler is already idempotent and signature-verified.
EXEMPT_PREFIXES = ("/v1/payments/webhook", "/healthz", "/metrics", "/docs", "/openapi.json", "/redoc")


class Clock(Protocol):
    def now(self) -> float: ...


class MonotonicClock:
    def now(self) -> float:
        return time.monotonic()


class RateLimitStore(Protocol):
    def consume(self, key: str, policy: Policy, cost: float = 1.0) -> tuple[bool, float]: ...
    def peek(self, key: str, policy: Policy) -> tuple[bool, float]: ...
    def reset(self) -> None: ...


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class InMemoryTokenBucketStore:
    """Thread-safe token buckets. Sized for a pilot; keys are evicted lazily
    once a bucket is full again (a full bucket carries no state)."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or MonotonicClock()
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def consume(self, key: str, policy: Policy, cost: float = 1.0) -> tuple[bool, float]:
        now = self._clock.now()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(policy.capacity), updated_at=now)
            else:
                elapsed = max(now - bucket.updated_at, 0.0)
                bucket.tokens = min(
                    float(policy.capacity), bucket.tokens + elapsed * policy.refill_per_second
                )
                bucket.updated_at = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                allowed, retry_after = True, 0.0
            else:
                missing = cost - bucket.tokens
                retry_after = (
                    missing / policy.refill_per_second if policy.refill_per_second > 0 else 60.0
                )
                allowed = False
            bucket.updated_at = now
            if bucket.tokens >= policy.capacity:
                self._buckets.pop(key, None)  # full bucket = no state worth keeping
            else:
                self._buckets[key] = bucket
        return allowed, retry_after

    def peek(self, key: str, policy: Policy) -> tuple[bool, float]:
        """Is at least one token available? Refills but consumes nothing — lets
        the login path reject an exhausted account before verifying a password."""
        now = self._clock.now()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return True, 0.0  # untouched key: full bucket
            elapsed = max(now - bucket.updated_at, 0.0)
            tokens = min(
                float(policy.capacity), bucket.tokens + elapsed * policy.refill_per_second
            )
            bucket.tokens = tokens
            bucket.updated_at = now
            if tokens >= 1.0:
                return True, 0.0
            retry_after = (
                (1.0 - tokens) / policy.refill_per_second if policy.refill_per_second > 0 else 60.0
            )
            return False, retry_after

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


class RateLimiter:
    def __init__(self, store: RateLimitStore | None = None, enabled: bool = True) -> None:
        self.store = store or InMemoryTokenBucketStore()
        self.enabled = enabled

    def check(self, key: str, policy: Policy) -> tuple[bool, float]:
        """Consume one token. Returns (allowed, retry_after_seconds)."""
        return self._run(policy, lambda: self.store.consume(key, policy))

    def peek(self, key: str, policy: Policy) -> tuple[bool, float]:
        """Is a token available, without spending one?"""
        return self._run(policy, lambda: self.store.peek(key, policy))

    def _run(self, policy: Policy, op) -> tuple[bool, float]:
        if not self.enabled:
            return True, 0.0
        try:
            allowed, retry_after = op()
        except Exception:  # noqa: BLE001 — store failure must be an explicit policy decision
            RATE_LIMIT_HITS.labels(policy=policy.name, outcome="error").inc()
            return (policy.on_store_failure == "open"), 0.0
        RATE_LIMIT_HITS.labels(
            policy=policy.name, outcome="allowed" if allowed else "rejected"
        ).inc()
        return allowed, retry_after

    def reset(self) -> None:
        self.store.reset()


limiter = RateLimiter()


# --- Keying -----------------------------------------------------------------
def client_ip(request, trust_proxy_hops: int) -> str:
    """Resolve the caller's address.

    X-Forwarded-For is NEVER trusted unless the deployment declares how many
    proxies sit in front (`TRUST_PROXY_HOPS`). With 0 hops we use the socket
    peer, so a spoofed header cannot be used to evade or frame anyone.
    """
    if trust_proxy_hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= trust_proxy_hops:
            return parts[-trust_proxy_hops]
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"


def resolve_policy(method: str, path: str) -> Policy | None:
    """Central route → policy resolution. None means 'not rate limited'."""
    if any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return None
    if path.startswith("/v1/auth/login"):
        return AUTH_LOGIN_IP
    if path.startswith("/v1/auth/register"):
        return AUTH_REGISTER
    if path.startswith("/v1/auth/refresh"):
        return AUTH_REFRESH
    if path.startswith("/v1/admin"):
        return ADMIN
    if method in ("GET", "HEAD", "OPTIONS"):
        return PUBLIC_READ
    if path.startswith("/v1/bookings"):
        # exact collection POST = creation; anything deeper is a mutation
        return BOOKING_CREATE if path.rstrip("/") == "/v1/bookings" else BOOKING_MUTATE
    if path.startswith("/v1/listings"):
        return LISTING_WRITE
    return PUBLIC_READ
