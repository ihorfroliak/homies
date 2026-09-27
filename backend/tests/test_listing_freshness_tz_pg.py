"""TASK-012R — temporal invariants independent of the PostgreSQL session TimeZone
(TASK-012A F12A-01, D-67).

The same stored instant and the same decision instant must give the same
business result whatever `TimeZone` the database session uses:

* freshness is elapsed time — 14 × 24 h and 21 × 24 h — never calendar days,
  so a DST change cannot move a boundary (A);
* "today" for move-in is the database decision instant's UTC date (B);
* a reminder cycle's identity is the confirmation instant in canonical UTC,
  whatever offset the value was read with (C).

Every case runs under several session zones, set on each pooled connection
AFTER it is established (the checkout hook below), so correctness cannot rest
on connection setup. The decision instant is pinned by replacing the two clock
seams, `freshness._now_sql` (SQL) and `freshness.db_now` (Python), with the
same instant *read back from the database* — so the Python side receives it in
the session's zone, exactly as the real clock read does.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, literal, select, text
from sqlalchemy.orm import Session
from sqlalchemy.types import DateTime

from app.modules.properties import freshness
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership, verify_phone
from tests.test_media import _approved, _attach

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — Postgres tests skipped"
)

ZONES = ["UTC", "Europe/Warsaw", "Pacific/Kiritimati"]  # +14, no DST
PROPERTY = {"category": "APARTMENT", "city": "Toruń", "address": "ul. Czasowa 1",
            "area_m2": 42, "rooms": 2, "capacity": 2}
OFFER = {"title": "Strefy czasowe", "rent_amount": 230000, "min_term_months": 12,
         "contact_mode": "phone", "contact_phone": "+48 600 100 200"}


def Z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.fixture(params=ZONES)
def zone(request, pg_migrated_engine):
    """Every connection the test checks out runs in this session TimeZone."""
    name = request.param

    def set_zone(dbapi_conn, record, proxy):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET TIME ZONE '{name}'")
        cursor.close()
        dbapi_conn.commit()

    event.listen(pg_migrated_engine, "checkout", set_zone)
    yield name
    event.remove(pg_migrated_engine, "checkout", set_zone)


def _pin(monkeypatch, instant: datetime):
    """Decide at `instant`, delivered by the database like the real clock."""
    original = freshness._now_sql

    def now_sql(db, as_of=None):
        return original(db, instant if as_of is None else as_of)

    def db_now(db):
        return db.scalar(select(literal(instant, DateTime(timezone=True))))

    monkeypatch.setattr(freshness, "_now_sql", now_sql)
    monkeypatch.setattr(freshness, "db_now", db_now)


def _published(pg_client, email="tz-owner@example.com", **extra):
    owner = register_and_login(pg_client, email, "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    offer = pg_client.post(f"/v1/properties/{prop}/classifieds", json={**OFFER, **extra},
                           headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                          headers=auth(owner)).status_code == 200
    return owner, prop, offer


def _confirmed_at(engine, offer, instant: datetime):
    with engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET last_confirmed_available_at = :t "
                          "WHERE id = :o"), {"t": instant, "o": offer})


def _listed(pg_client, offer):
    items = pg_client.get("/v1/classifieds").json()["items"]
    return next((o for o in items if o["id"] == offer), None)


# --- A. freshness is elapsed time: both DST directions, every zone ---------------------------

AUTUMN_DECISION = Z("2026-11-01T12:00:00Z")   # Warsaw left DST on 2026-10-25
SPRING_DECISION = Z("2026-04-01T12:00:00Z")   # Warsaw entered DST on 2026-03-29

CASES = [
    # decision, confirmation, expected state (None = not public)
    pytest.param(AUTUMN_DECISION, Z("2026-10-11T12:00:00Z"), None, id="autumn-exactly-21x24h"),
    pytest.param(AUTUMN_DECISION, Z("2026-10-11T12:00:00.000001Z"), "RECONFIRM_DUE",
                 id="autumn-just-before-21x24h"),
    pytest.param(AUTUMN_DECISION, Z("2026-10-18T12:00:00Z"), "RECONFIRM_DUE",
                 id="autumn-exactly-14x24h"),
    pytest.param(AUTUMN_DECISION, Z("2026-10-18T12:00:00.000001Z"), "FRESH",
                 id="autumn-just-before-14x24h"),
    pytest.param(SPRING_DECISION, Z("2026-03-11T12:30:00Z"), "RECONFIRM_DUE",
                 id="spring-20d23h30m"),
    pytest.param(SPRING_DECISION, Z("2026-03-11T12:00:00Z"), None, id="spring-exactly-21x24h"),
    pytest.param(Z("2026-04-05T12:00:00Z"), Z("2026-03-22T12:00:00Z"), "RECONFIRM_DUE",
                 id="spring-exactly-14x24h"),
    pytest.param(Z("2026-04-05T12:00:00Z"), Z("2026-03-22T12:00:00.000001Z"), "FRESH",
                 id="spring-just-before-14x24h"),
]


@pytest.mark.parametrize("decision, confirmation, expected", CASES)
def test_freshness_is_elapsed_time_in_every_session_zone(
        pg_client, pg_migrated_engine, monkeypatch, zone, decision, confirmation, expected):
    _, _, offer = _published(pg_client)
    _confirmed_at(pg_migrated_engine, offer, confirmation)
    _pin(monkeypatch, decision)
    listed = _listed(pg_client, offer)
    detail = pg_client.get(f"/v1/classifieds/{offer}")
    if expected is None:
        assert listed is None, f"stale listing still on the board ({zone})"
        assert detail.status_code == 404, detail.text
    else:
        assert listed is not None and listed["freshness"] == expected, (zone, listed)
        assert detail.status_code == 200 and detail.json()["freshness"] == expected
    # The derived dates are the same instants in every zone.
    assert freshness.stale_at(confirmation) == confirmation + freshness.AUTO_PAUSE_AFTER
    # The sweep draws the same line as visibility (maintenance ≡ public rule).
    with Session(pg_migrated_engine) as db:
        result = freshness.sweep(db, as_of=decision)
        db.commit()
    assert (offer in result.staled) == (expected is None), (zone, result)
    assert (offer in result.reminded) == (expected == "RECONFIRM_DUE"), (zone, result)


@pytest.mark.parametrize("decision, confirmation, public", [
    pytest.param(AUTUMN_DECISION, Z("2026-10-11T12:00:00Z"), False, id="autumn-exactly-21x24h"),
    pytest.param(SPRING_DECISION, Z("2026-03-11T12:30:00Z"), True, id="spring-20d23h30m"),
])
def test_all_seven_public_paths_agree_in_every_session_zone(
        pg_client, pg_migrated_engine, monkeypatch, zone, decision, confirmation, public):
    owner, prop, offer = _published(pg_client)
    asset = _approved(pg_client, owner, prop)
    assert _attach(pg_client, owner, offer, asset, cover=True).status_code in (200, 201)
    tenant = register_and_login(pg_client, "tz-tenant@example.com", "guest")
    verify_phone(pg_client, tenant, "+48511222333")
    _confirmed_at(pg_migrated_engine, offer, confirmation)
    _pin(monkeypatch, decision)

    listed = _listed(pg_client, offer) is not None
    detail = pg_client.get(f"/v1/classifieds/{offer}").status_code
    contact = pg_client.post(f"/v1/classifieds/{offer}/contact", headers=auth(tenant)).status_code
    conversation = pg_client.post(f"/v1/classifieds/{offer}/conversations",
                                  json={"body": "Czy aktualne?"}, headers=auth(tenant)).status_code
    slots = pg_client.get(f"/v1/classifieds/{offer}/viewing-slots",
                          headers=auth(tenant)).status_code
    request_ = pg_client.post(f"/v1/classifieds/{offer}/viewings",
                              json={"starts_at": "2030-01-01T10:00:00Z"},
                              headers=auth(tenant)).status_code
    media = pg_client.get(f"/v1/media/{asset}").status_code
    paths = {"list": listed, "detail": detail != 404, "contact": contact != 404,
             "conversation": conversation != 404, "slots": slots != 404,
             "viewing_request": request_ != 404, "media": media != 404}
    assert paths == {name: public for name in paths}, (zone, paths)


# --- B. move-in uses the database decision instant's UTC date ------------------------------


@pytest.mark.parametrize("decision, expected", [
    pytest.param(Z("2026-09-27T20:25:21Z"), "FROM_DATE", id="utc-27th-session-28th"),
    pytest.param(Z("2026-09-27T23:59:59.999999Z"), "FROM_DATE", id="utc-last-instant-of-27th"),
    pytest.param(Z("2026-09-28T00:00:00Z"), "NOW", id="utc-28th"),
])
def test_move_in_is_decided_on_the_utc_date(
        pg_client, pg_migrated_engine, monkeypatch, zone, decision, expected):
    _, _, dated = _published(pg_client, available_from="2026-09-28")
    _, _, unknown = _published(pg_client, "tz-owner-2@example.com")
    for offer in (dated, unknown):
        _confirmed_at(pg_migrated_engine, offer, Z("2026-09-27T00:00:00Z"))
    _pin(monkeypatch, decision)
    assert _listed(pg_client, dated)["move_in"] == expected, zone
    assert pg_client.get(f"/v1/classifieds/{dated}").json()["move_in"] == expected, zone
    assert _listed(pg_client, unknown)["move_in"] == "UNKNOWN"
    ids = {o["id"] for o in pg_client.get(
        "/v1/classifieds", params={"available_by": "2026-09-30"}).json()["items"]}
    assert dated in ids and unknown not in ids  # D-64 unchanged


# --- C. one reminder per confirmation cycle, whatever zone reads the instant ---------------


@pytest.mark.parametrize("first, second", [("UTC", "Europe/Warsaw"),
                                           ("Europe/Warsaw", "UTC"),
                                           ("Pacific/Kiritimati", "Europe/Warsaw")])
def test_a_reminder_cycle_is_one_identity_across_session_zones(
        pg_client, pg_migrated_engine, first, second):
    _, _, offer = _published(pg_client)
    _confirmed_at(pg_migrated_engine, offer, Z("2026-09-11T12:00:00Z"))
    decision = Z("2026-09-27T12:00:00Z")
    reminded = []
    for name in (first, second):
        with Session(pg_migrated_engine) as db:
            db.execute(text(f"SET TIME ZONE '{name}'"))
            reminded.append(freshness.sweep(db, as_of=decision).reminded)
            db.commit()
    assert reminded == [[offer], []], reminded
    with pg_migrated_engine.connect() as conn:
        keys = conn.execute(text(
            "SELECT dedup_key FROM domain_events WHERE correlation_id = :o "
            "AND event_type = :t"), {"o": offer, "t": freshness.LISTING_RECONFIRMATION_DUE}
        ).scalars().all()
    assert len(keys) == 1, keys


# --- the real clock read is normalised; the database stays the authority --------------------


def test_db_now_is_the_database_instant_in_utc(pg_migrated_engine, zone):
    with Session(pg_migrated_engine) as db:
        db.execute(text(f"SET TIME ZONE '{zone}'"))
        now = freshness.db_now(db)
        db_instant = db.scalar(text("SELECT statement_timestamp()"))
    assert now.utcoffset() is not None and now.utcoffset().total_seconds() == 0
    assert abs((now - db_instant).total_seconds()) < 5
    assert now.tzinfo == timezone.utc


def test_application_sessions_start_in_utc_as_defence_in_depth():
    """Not the fix — the rules above hold in any zone — but the application's
    engine opens sessions in UTC, so logs and ad-hoc SQL read the same way."""
    from sqlalchemy import create_engine

    from app.core.db import _connect_args

    engine = create_engine(TEST_DATABASE_URL, connect_args=_connect_args(TEST_DATABASE_URL))
    try:
        with engine.connect() as conn:
            assert conn.scalar(text("SHOW TimeZone")) == "UTC"
    finally:
        engine.dispose()
