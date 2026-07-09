"""OAT-03 — reliable delivery: transactional outbox + worker + retry state
machine. Injects controllable channels to exercise timeout/recovery/retry/
dead paths. Asserts the money core never changes under delivery failure."""

from datetime import date, datetime, timedelta, timezone

import pytest

import app.modules.events.worker as worker_mod
from app.modules.events.providers import DeliveryResult
from tests.conftest import (
    TestingSession,
    auth,
    drain_notifications,
    fire_webhook,
    register_and_login,
)

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


class FlakyChannel:
    """Fails transiently `fail_n` times, then succeeds."""

    def __init__(self, fail_n):
        self.calls = 0
        self.fail_n = fail_n

    def send(self, to, subject, body, idem_key):
        self.calls += 1
        if self.calls <= self.fail_n:
            return DeliveryResult(ok=False, transient=True, error="provider timeout")
        return DeliveryResult(ok=True)


class PermanentFailChannel:
    def send(self, to, subject, body, idem_key):
        return DeliveryResult(ok=False, transient=False, error="bad recipient")


@pytest.fixture()
def no_backoff(monkeypatch):
    # Make retries immediately due so drain is deterministic.
    from app.core.config import settings
    monkeypatch.setattr(settings, "notification_backoff_base_seconds", 0.0)


def _book(client, key="oat3-0001"):
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    bk = client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                     headers=auth(guest) | {"Idempotency-Key": key}).json()
    return host, guest, bk


def _statuses(client, admin_token, booking_id):
    rows = client.get("/v1/admin/notifications", headers=auth(admin_token)).json()
    return [r["status"] for r in rows if r["booking_id"] == booking_id]


# 1. booking created -> outbox pending -> worker delivers
def test_booking_created_delivered(client, admin_token):
    _, guest, bk = _book(client)
    assert "pending" in _statuses(client, admin_token, bk["id"])
    drain_notifications()
    assert all(s == "delivered" for s in _statuses(client, admin_token, bk["id"]))
    q = client.get("/v1/admin/notifications/queue", headers=auth(admin_token)).json()
    assert q.get("pending", 0) == 0 and q.get("failed", 0) == 0  # queue drains to zero


# 2+3+4. provider timeout -> retry -> recovery succeeds
def test_provider_timeout_then_recovers(client, admin_token, monkeypatch, no_backoff):
    _, guest, bk = _book(client)
    flaky = FlakyChannel(fail_n=2)
    monkeypatch.setattr(worker_mod, "channel_for", lambda name: flaky)
    drain_notifications()
    statuses = _statuses(client, admin_token, bk["id"])
    assert all(s == "delivered" for s in statuses)
    assert flaky.calls >= 3  # 2 failures + success


# 5. retry exhausted -> DEAD (permanent failure)
def test_permanent_failure_goes_dead(client, admin_token, monkeypatch, no_backoff):
    _, guest, bk = _book(client)
    monkeypatch.setattr(worker_mod, "channel_for", lambda name: PermanentFailChannel())
    drain_notifications()
    statuses = _statuses(client, admin_token, bk["id"])
    assert all(s == "dead" for s in statuses)
    # DEAD notifications are permanently observable (founder audit)
    dead = client.get("/v1/admin/notifications?status=dead", headers=auth(admin_token)).json()
    assert any(d["booking_id"] == bk["id"] and d["last_error"] for d in dead)


# 6. worker restart mid-flight: PROCESSING reclaimed, no loss
def test_worker_restart_reclaims_stale(client, admin_token):
    _, guest, bk = _book(client)
    from app.modules.events.models import Notification

    # Simulate a crashed worker: a row stuck in PROCESSING with an old claim.
    with TestingSession() as db:
        n = db.query(Notification).filter_by(correlation_id=bk["id"]).first()
        n.status = "processing"
        n.claimed_at = datetime.now(timezone.utc) - timedelta(seconds=999)
        db.commit()
        nid = n.id
    # New worker run reclaims stale processing rows and delivers them.
    drain_notifications()
    with TestingSession() as db:
        assert db.get(Notification, nid).status == "delivered"


# 7. duplicate event -> no duplicate notifications (idempotent emit)
def test_duplicate_event_no_duplicate_notifications(client, admin_token):
    _, guest, bk = _book(client)
    for _ in range(3):
        fire_webhook(client, bk["payment_intent_id"])  # BookingConfirmed emitted once
    drain_notifications()
    rows = client.get("/v1/admin/notifications", headers=auth(admin_token)).json()
    confirmed = [r for r in rows if r["booking_id"] == bk["id"]
                 and r["type"] == "BookingConfirmed"]
    # one per routed recipient (guest, host, founder) = 3, none duplicated
    assert len(confirmed) == 3
    assert all(r["status"] == "delivered" for r in confirmed)


# 8. delivery failure must NOT corrupt booking/payment/event
def test_delivery_failure_does_not_touch_money(client, admin_token, monkeypatch, no_backoff):
    _, guest, bk = _book(client)
    fire_webhook(client, bk["payment_intent_id"])  # confirmed + ledger capture
    monkeypatch.setattr(worker_mod, "channel_for", lambda name: PermanentFailChannel())
    drain_notifications()
    # booking confirmed, payment succeeded, ledger balanced despite dead notifications
    state = client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin_token)).json()
    assert state["lifecycle_state"] == "confirmed"
    assert state["financial"]["payment_status"] == "succeeded"
    rec = client.get("/v1/admin/payments/reconciliation", headers=auth(admin_token)).json()
    assert rec["ok"] is True
    # timeline (events) intact regardless of delivery outcome
    assert "BookingConfirmed" in [e["type"] for e in state["timeline"]]


# 9. transaction rollback: if the business txn fails, no orphan event/notif
def test_no_notification_without_committed_booking(client, admin_token):
    # A booking that fails validation (past date) creates neither event nor notif.
    host = register_and_login(client, "host@example.com", "host")
    client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                headers=auth(host))
    lid = client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                      "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                      headers=auth(host)).json()["id"]
    client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    guest = register_and_login(client, "guest@example.com", "guest")
    r = client.post("/v1/bookings",
                    json={"listing_id": lid, "check_in": (date.today() - timedelta(days=1)).isoformat(),
                          "check_out": CO},
                    headers=auth(guest) | {"Idempotency-Key": "oat3-rollback"})
    assert r.status_code == 422
    rows = client.get("/v1/admin/notifications", headers=auth(admin_token)).json()
    assert rows == []  # nothing committed -> nothing to deliver
