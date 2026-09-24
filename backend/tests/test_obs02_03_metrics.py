"""OBS-02/03: HTTP metrics and business event counters.

Two properties carry most of the weight here and are tested directly:

1. **Cardinality is bounded.** HTTP metrics label by route *template*, so a
   thousand booking ids produce one series, not a thousand.
2. **Counters only move on committed facts.** A Prometheus counter cannot be
   decremented, so a rolled-back transaction must leave it untouched.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import business_metrics as bm


def _sample(counter_name: str, **labels) -> float:
    value = REGISTRY.get_sample_value(counter_name, labels)
    return 0.0 if value is None else value


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return sessionmaker(bind=engine)()


# --- OBS-03: commit semantics -------------------------------------------------


def test_counter_moves_only_after_commit(session):
    from sqlalchemy import text

    before = _sample("homies_bookings_total", outcome="created")
    session.execute(text("SELECT 1"))
    bm.record_booking(session, "created")
    assert _sample("homies_bookings_total", outcome="created") == before, (
        "counter moved before the transaction committed"
    )
    session.commit()
    assert _sample("homies_bookings_total", outcome="created") == before + 1


def test_rollback_discards_the_increment(session):
    """The property that makes these counters trustworthy.

    Services mutate state but do not commit; the router does. Incrementing at
    the transition would count a payment that raced and lost as a success, and
    a counter cannot be decremented to repair it.
    """
    from sqlalchemy import text

    before = _sample("homies_payments_total", outcome="succeeded")
    session.execute(text("SELECT 1"))  # open a real unit of work, as callers do
    assert session.in_transaction()
    bm.record_payment(session, "succeeded")
    session.rollback()
    assert _sample("homies_payments_total", outcome="succeeded") == before
    # And the discarded increment must not resurface on a later commit.
    session.commit()
    assert _sample("homies_payments_total", outcome="succeeded") == before


def test_queued_increments_do_not_leak_between_transactions(session):
    from sqlalchemy import text

    before = _sample("homies_payouts_total", outcome="paid")
    session.execute(text("SELECT 1"))
    bm.record_payout(session, "paid")
    session.commit()
    session.commit()  # a second commit must not replay the same increment
    assert _sample("homies_payouts_total", outcome="paid") == before + 1


# --- OBS-02: HTTP metrics -----------------------------------------------------


def test_http_metrics_recorded_for_a_request(client):
    before = _sample("homies_http_requests_total", method="GET", route="/healthz", status="2xx")
    client.get("/healthz")
    after = _sample("homies_http_requests_total", method="GET", route="/healthz", status="2xx")
    assert after == before + 1
    assert (
        REGISTRY.get_sample_value(
            "homies_http_request_duration_seconds_count", {"method": "GET", "route": "/healthz"}
        )
        is not None
    )


@pytest.mark.legacy_runtime
def test_route_template_not_raw_path_bounds_cardinality(client, admin_token):
    """A thousand booking ids must not mint a thousand time series."""
    for booking_id in ("aaaa1111", "bbbb2222", "cccc3333"):
        client.get(f"/v1/bookings/{booking_id}", headers={"Authorization": f"Bearer {admin_token}"})

    series = {
        s.labels["route"]
        for metric in REGISTRY.collect()
        if metric.name == "homies_http_requests"
        for s in metric.samples
    }
    assert not any(bid in r for r in series for bid in ("aaaa1111", "bbbb2222", "cccc3333")), (
        f"raw path leaked into labels: {series}"
    )


def test_route_label_carries_the_router_prefix(client):
    """Regression: `scope["route"].path` is router-*relative*.

    Using it directly labelled this endpoint `/auth/login`, so two routers
    mounted under different prefixes would have merged into one series and the
    label would not have matched any real URL.
    """
    client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert _sample(
        "homies_http_requests_total", method="POST", route="/v1/auth/login", status="4xx"
    ) > 0
    assert _sample(
        "homies_http_requests_total", method="POST", route="/auth/login", status="4xx"
    ) == 0, "prefix-stripped label reappeared"


def test_unmatched_routes_collapse_to_one_series(client):
    before = _sample(
        "homies_http_requests_total", method="GET", route="unmatched", status="4xx"
    )
    client.get("/no-such-route-1")
    client.get("/no-such-route-2")
    after = _sample("homies_http_requests_total", method="GET", route="unmatched", status="4xx")
    assert after == before + 2, "404 scanning must not grow the label set"


def test_metrics_endpoint_excluded_from_its_own_metrics(client):
    client.get("/metrics")
    assert (
        REGISTRY.get_sample_value(
            "homies_http_requests_total", {"method": "GET", "route": "/metrics", "status": "2xx"}
        )
        is None
    )


def test_throttled_requests_are_still_counted(client, monkeypatch):
    """Metrics middleware is registered outside the rate limiter on purpose:
    a rate-limit storm must read as a spike in 429s, not a drop in traffic."""
    from app.core import ratelimit as rl
    from app.core.config import settings

    settings.rate_limit_enabled = True
    rl.limiter.reset()
    try:
        codes = [client.post("/v1/auth/login", json={"email": "x@y.z", "password": "nope"}).status_code
                 for _ in range(40)]
    finally:
        settings.rate_limit_enabled = False
        rl.limiter.reset()

    assert 429 in codes, "test did not actually trip the limiter"
    assert _sample(
        "homies_http_requests_total", method="POST", route="/v1/auth/login", status="4xx"
    ) > 0


def test_money_amounts_are_not_exposed_as_counters():
    """D-38: GMV/commission live in the ledger, never in a resettable counter.

    A counter resets on restart and cannot be recomputed for a past window;
    a second, lossy financial record that disagreed with the ledger would be
    worse than none.
    """
    names = {m.name for m in REGISTRY.collect()}
    forbidden = {"homies_gmv", "homies_revenue", "homies_commission", "homies_booking_amount"}
    assert not (names & forbidden), f"monetary total exposed as a metric: {names & forbidden}"

    for metric in REGISTRY.collect():
        if metric.name.startswith(("homies_payments", "homies_bookings", "homies_payouts")):
            assert "amount" not in metric.documentation.lower() or "never amounts" in (
                metric.documentation.lower()
            ), metric.documentation
