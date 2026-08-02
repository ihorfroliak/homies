"""CI-03 — real PostgreSQL concurrency validation.

These run against a real Postgres (gated by TEST_DATABASE_URL) with separate
connections per thread, so they exercise actual row locks and the exclusion
constraint — the guarantees SQLite cannot model. This is the authoritative
concurrency evidence; the SQLite suite is not.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.modules.booking.expiry import expire_due_bookings
from app.modules.booking.models import Booking
from app.modules.identity.models import User
from app.modules.payments import service as payments_service
from app.modules.payments.models import WebhookEvent
from tests.conftest import auth, fire_webhook, register_and_login
from tests.test_fin01_stripe_signature import event_body, sign

CI = (date.today() + timedelta(days=25)).isoformat()
CO = (date.today() + timedelta(days=28)).isoformat()


def _sessionmaker(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _admin_token(pg_client, engine):
    from app.core.security import hash_password

    Session = _sessionmaker(engine)
    with Session() as db:
        db.add(User(email="admin@example.com", password_hash=hash_password("admin-password-123"),
                    role="admin"))
        db.commit()
    return pg_client.post("/v1/auth/login",
                          json={"email": "admin@example.com",
                                "password": "admin-password-123"}).json()["access_token"]


def _listing(pg_client):
    host = register_and_login(pg_client, "host@example.com", "host")
    pg_client.post("/v1/hosts/onboarding", json={"payout_iban": "PL61109010140000071219812874"},
                   headers=auth(host))
    lid = pg_client.post("/v1/listings", json={"title": "Studio", "city": "Warsaw",
                         "address": "ul. Testowa 1", "capacity": 2, "nightly_price_amount": 40000},
                         headers=auth(host)).json()["id"]
    pg_client.post(f"/v1/listings/{lid}/publish", headers=auth(host))
    return lid


# 1 & 2 & 9. Two+ users book the same inventory simultaneously -> exactly one wins
def test_concurrent_double_booking_only_one_succeeds(pg_client, pg_migrated_engine):
    lid = _listing(pg_client)
    guests = [register_and_login(pg_client, f"g{i}@example.com", "guest") for i in range(12)]

    def book(hdr):
        import uuid
        return pg_client.post(
            "/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
            headers=auth(hdr) | {"Idempotency-Key": uuid.uuid4().hex},
        ).status_code

    with ThreadPoolExecutor(max_workers=12) as ex:
        codes = list(ex.map(book, guests))
    assert codes.count(201) == 1, codes  # exactly one booking (exclusion constraint)
    assert codes.count(409) == 11


# 3 & 8. Duplicate webhook delivery under concurrency -> single capture
def test_concurrent_webhook_delivery_captures_once(pg_client, pg_migrated_engine):
    lid = _listing(pg_client)
    admin = _admin_token(pg_client, pg_migrated_engine)
    guest = register_and_login(pg_client, "guest@example.com", "guest")
    r = pg_client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                       headers=auth(guest) | {"Idempotency-Key": "ci03-wh-01"})
    assert r.status_code == 201, r.text
    bk = r.json()
    intent = bk["payment_intent_id"]
    Session = _sessionmaker(pg_migrated_engine)

    def deliver(_):
        with Session() as db:
            try:
                payments_service.process_intent_succeeded(db, intent)
                db.commit()
                return "ok"
            except Exception:
                db.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(deliver, range(10)))

    rec = pg_client.get("/v1/admin/payments/reconciliation", headers=auth(admin)).json()
    assert rec["ok"] is True
    assert rec["double_capture"] == []
    entries = pg_client.get("/v1/admin/ledger/entries", headers=auth(admin)).json()
    captures = [e for e in entries if e["kind"] == "payment_captured" and e["booking_id"] == bk["id"]]
    assert len(captures) == 1


# 10 (H2). Concurrent deliveries of the SAME signed event race on the unique
# stripe_event_id. Exactly one audit row must exist and money must move once —
# this exercises the IntegrityError branch on a real engine (SQLite cannot).
def test_concurrent_same_stripe_event_persists_one_row(
    pg_client, pg_migrated_engine, stripe_webhook
):
    lid = _listing(pg_client)
    admin = _admin_token(pg_client, pg_migrated_engine)
    guest = register_and_login(pg_client, "guest@example.com", "guest")
    bk = pg_client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                        headers=auth(guest) | {"Idempotency-Key": "ci03-h2-01"}).json()
    body = event_body(bk["payment_intent_id"], event_id="evt_ci03_race")

    def deliver(_):
        return pg_client.post("/v1/payments/webhook/stripe", content=body,
                              headers={"Stripe-Signature": sign(body, stripe_webhook)}).status_code

    with ThreadPoolExecutor(max_workers=8) as ex:
        codes = list(ex.map(deliver, range(8)))
    assert all(c == 200 for c in codes), codes  # no 5xx from the insert race

    Session = _sessionmaker(pg_migrated_engine)
    with Session() as db:
        rows = list(db.scalars(
            select(WebhookEvent).where(WebhookEvent.stripe_event_id == "evt_ci03_race")
        ))
    assert len(rows) == 1 and rows[0].processed_at is not None

    entries = pg_client.get("/v1/admin/ledger/entries", headers=auth(admin)).json()
    captures = [e for e in entries
                if e["kind"] == "payment_captured" and e["booking_id"] == bk["id"]]
    assert len(captures) == 1
    rec = pg_client.get("/v1/admin/payments/reconciliation", headers=auth(admin)).json()
    assert rec["ok"] is True and rec["double_capture"] == []


# 4 & 5. Two workers expire the same booking -> exactly one transition
def test_concurrent_expiry_sweeps_expire_once(pg_client, pg_migrated_engine):
    lid = _listing(pg_client)
    guest = register_and_login(pg_client, "guest@example.com", "guest")
    bk = pg_client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                        headers=auth(guest) | {"Idempotency-Key": "ci03-exp-01"}).json()
    Session = _sessionmaker(pg_migrated_engine)
    with Session() as db:
        db.get(Booking, bk["id"]).payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    def sweep(_):
        with Session() as db:
            return expire_due_bookings(db)["expired"]

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(sweep, range(6)))
    assert sum(results) == 1  # exactly one worker won the row
    with Session() as db:
        assert db.get(Booking, bk["id"]).status == "expired"


# 6 & 7. Payment completion races expiration -> safe, never PAID+EXPIRED
def test_payment_racing_expiry_is_safe(pg_client, pg_migrated_engine):
    lid = _listing(pg_client)
    admin = _admin_token(pg_client, pg_migrated_engine)
    guest = register_and_login(pg_client, "guest@example.com", "guest")
    bk = pg_client.post("/v1/bookings", json={"listing_id": lid, "check_in": CI, "check_out": CO},
                        headers=auth(guest) | {"Idempotency-Key": "ci03-race-01"}).json()
    Session = _sessionmaker(pg_migrated_engine)
    with Session() as db:
        db.get(Booking, bk["id"]).payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    def sweep():
        with Session() as db:
            expire_due_bookings(db)

    with ThreadPoolExecutor(max_workers=2) as ex:
        ex.submit(sweep)
        ex.submit(lambda: fire_webhook(pg_client, bk["payment_intent_id"]))

    # whichever won, the outcome is consistent and the ledger nets to zero
    final = pg_client.get(f"/v1/bookings/{bk['id']}/state", headers=auth(admin)).json()
    assert final["lifecycle_state"] in ("confirmed", "expired")
    rec = pg_client.get("/v1/admin/payments/reconciliation", headers=auth(admin)).json()
    assert rec["ok"] is True and rec["ledger_grand_total"] == 0
    if final["lifecycle_state"] == "expired":
        assert rec["balances"].get("booking_escrow", 0) == 0  # money not held
