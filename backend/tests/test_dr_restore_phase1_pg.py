"""Backup → destroy → restore drill for the Phase-1A data (PR-001).

tests/test_dr_restore_pg.py proves the cycle for the ledger and bookings,
seeded through the dormant booking routes. This drill seeds what the deployable
Phase-1A application actually holds — reference geography, structured
addresses, properties with exact (private) and public points, spaces,
listings with price components and freshness, authorities — and the durable
TASK-014 state (public-listing generations, a saved listing, a saved search
with its anchors, matches, deliveries on both channels, the inbox, a
notification preference and unsubscribe capabilities; MICRO-001, CONV-001A
CV-N2) — then:

1. dumps it with pg_dump (custom format, streamed),
2. restores it into a brand-new database with pg_restore,
3. proves the copy is one the business could run on: same migration head,
   same rows, same generated PostGIS columns, the same public search answer,
   and the database invariants still refusing what they must refuse.

Disposable databases only. What this does NOT prove: offsite storage,
encryption at rest, point-in-time recovery, restore time at production volume,
or that a real production backup job runs — see docs/production/BACKUP-RESTORE.md.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.schema import alembic_config
from app.modules.alerts import delivery, worker
from app.modules.geography import service
from app.modules.geography.models import GeoArea, GeoSource
from app.modules.properties import freshness
from app.modules.properties import router as properties_router
from app.modules.properties.models import ClassifiedOffer
from app.modules.saved import service as saved_service
from app.modules.saved.models import SavedSearch
from app.modules.identity.models import User
from app.modules.trust import decisions, effects, hold
from app.modules.trust.models import ModerationReviewRequest, Report
from tests.conftest import (
    TEST_DATABASE_URL,
    auth,
    last_code,
    register_and_login,
    verify_ownership,
)
# Importing it also applies its HOMIES_REQUIRE_RESTORE_DRILL check (PR-001R F7).
from tests.test_dr_restore_pg import (
    DRILL_AVAILABLE,
    DRILL_SKIP_REASON,
    PG_DUMP,
    PG_RESTORE,
    _libpq,
    _run,
    _with_database,
)
from tests.test_engagement_safety import WARSAW, _slot
from tests.test_geography import PL_AREAS, PL_LOCALITIES, SOURCE
from tests.test_media import _approved
from tests.test_saved_search_alerts import Mailbox

pytestmark = pytest.mark.skipif(not DRILL_AVAILABLE, reason=DRILL_SKIP_REASON)

# Tables whose every row must come back identical.
TABLES = ("countries", "geo_sources", "admin_areas", "localities", "geo_areas",
          "geo_external_refs", "addresses", "properties", "spaces", "classified_offers",
          "listing_price_components", "legal_parties", "person_legal_parties",
          "property_authorities", "property_authority_scopes", "attribute_definitions",
          # TASK-014 durable state (CONV-001A CV-N2)
          "listing_public_generations", "saved_listings", "saved_searches",
          "saved_search_anchors", "saved_search_matches", "alert_deliveries",
          "user_notifications", "notification_preferences", "unsubscribe_tokens",
          # the schema's own record survives with it (PR-002): a restored
          # database is judged by the same compatibility decision
          "schema_lineage",
          # TASK-015: reports and the immutable moderation decision chain
          "reports", "moderation_decisions", "moderation_review_requests",
          # TASK-015 closure: the engagement and media state moderation acts on
          # — conversations (one closed by Homies), messages (one redacted, the
          # SYSTEM closure line), viewings, and photos (one RESTRICTED)
          "conversations", "conversation_participants", "messages", "viewing_settings",
          "viewing_windows", "viewings", "file_objects", "media_assets", "listing_media")
TASK014_TABLES = ("listing_public_generations", "saved_listings", "saved_searches",
                  "saved_search_anchors", "saved_search_matches", "alert_deliveries",
                  "user_notifications", "notification_preferences", "unsubscribe_tokens")
TASK015_TABLES = ("reports", "moderation_decisions", "moderation_review_requests",
                  "conversations", "conversation_participants", "messages", "viewing_settings",
                  "viewing_windows", "viewings", "file_objects", "media_assets", "listing_media")
# Redacted by moderation before the backup: it must stay redacted after the restore.
REDACTED_TEXT = "tekst usuniety przez moderacje"
TOKEN = re.compile(r"/unsubscribe\?token=([A-Za-z0-9_-]+)")


def _seed(pg_client, pg_session, pg_migrated_engine, monkeypatch):
    db = pg_session
    db.add(GeoSource(code=SOURCE, name="Test fixture (not an official register)"))
    db.flush()
    service.import_areas(db, "PL", SOURCE, PL_AREAS)
    service.import_localities(db, "PL", SOURCE, PL_LOCALITIES)
    db.commit()
    krakow = service._by_ref(db, SOURCE, "L-KRK", "locality_id")
    kazimierz = GeoArea(country_code="PL", locality_id=krakow, kind="NEIGHBOURHOOD",
                        name="Kazimierz")
    db.add(kazimierz)
    db.commit()

    owner = register_and_login(pg_client, "dr-phase1@example.com", "host")
    # A renter who saved a search before the listings went public, and set a
    # notification preference: the publications below become alerts.
    renter = register_and_login(pg_client, "dr-phase1-renter@example.com", "guest")
    pg_client.post("/v1/me/verify/email/start", headers=auth(renter))
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(renter)).status_code == 200
    saved = pg_client.post("/v1/me/saved-searches", headers=auth(renter), json={
        "name": "Kraków", "query": f"locality_id={krakow}&max_rent=300000"})
    assert saved.status_code == 201, saved.text
    assert pg_client.put("/v1/me/notification-preferences", headers=auth(renter), json={
        "category": "PRODUCT", "channel": "IN_APP", "enabled": True}).status_code == 200
    offers = []
    for i, extra in enumerate(({}, {"admin_fee": 45000, "utilities_amount": 30000,
                                     "deposit_amount": 500000}, {})):
        prop = pg_client.post("/v1/properties", json={
            "category": "APARTMENT", "locality_id": krakow, "geo_area_id": kazimierz.id,
            "thoroughfare": "ul. Odtworzona", "building_number": str(10 + i),
            "unit_number": str(i), "postcode": "31-000", "latitude": 50.051 + i / 1000,
            "longitude": 19.945, "area_m2": 40 + i, "rooms": 2, "capacity": 2,
        }, headers=auth(owner))
        assert prop.status_code == 201, prop.text
        verify_ownership(pg_client, owner, prop.json()["id"])
        offer = pg_client.post(f"/v1/properties/{prop.json()['id']}/classifieds", json={
            "title": f"Przywrócone {i}", "rent_amount": 260000 + i, "min_term_months": 12,
            "contact_mode": "message", **extra}, headers=auth(owner)).json()["id"]
        assert pg_client.post(f"/v1/classifieds/{offer}/publish",
                              headers=auth(owner)).status_code == 200
        offers.append(offer)
    assert pg_client.post(f"/v1/me/saved-listings/{offers[0]}",
                          headers=auth(renter)).status_code == 201
    mailbox = Mailbox()
    monkeypatch.setattr(delivery, "channel_for", lambda name: mailbox)
    sessions = sessionmaker(bind=pg_migrated_engine, expire_on_commit=False)
    worker.process_work(sessions)
    worker.process_deliveries(sessions)
    tokens = [t for mail in mailbox.sent for t in TOKEN.findall(mail["body"])]
    assert tokens, "no alert email carried an unsubscribe capability"
    # One listing past its freshness window: it must stay non-public after restore.
    db.execute(text("UPDATE classified_offers SET last_confirmed_available_at = :t "
                    "WHERE id = :o"),
               {"t": datetime.now(timezone.utc) - timedelta(days=30), "o": offers[2]})
    db.commit()
    _seed_moderation(pg_client, sessions, offers[2], renter_email="dr-phase1-renter@example.com")
    engagement = _seed_engagement(pg_client, sessions, owner, renter, offers)
    return offers, saved.json()["id"], tokens, engagement


def _seed_engagement(pg_client, sessions, owner, renter, offers):
    """On the public listings (the drill's public answer is unchanged):
    a live conversation with one message redacted by moderation, a second
    conversation closed by Homies (G-14 re-contact block), a CONFIRMED
    viewing, and two photos — one public cover, one RESTRICTED."""
    assert pg_client.post("/v1/me/verify/email/start", headers=auth(owner)).status_code == 200
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(owner)).status_code == 200
    live = pg_client.post(f"/v1/classifieds/{offers[0]}/conversations",
                          json={"body": "Dzień dobry, czy aktualne?"}, headers=auth(renter))
    assert live.status_code == 201, live.text
    live_id = live.json()["conversation"]["id"]
    sent = pg_client.post(f"/v1/conversations/{live_id}/messages",
                          json={"body": REDACTED_TEXT}, headers=auth(renter))
    assert sent.status_code == 201, sent.text
    other = register_and_login(pg_client, "dr-phase1-tenant2@example.com", "guest")
    assert pg_client.post("/v1/me/verify/email/start", headers=auth(other)).status_code == 200
    assert pg_client.post("/v1/me/verify/email/confirm", json={"code": last_code()},
                          headers=auth(other)).status_code == 200
    closed = pg_client.post(f"/v1/classifieds/{offers[1]}/conversations",
                            json={"body": "Pytanie o mieszkanie"}, headers=auth(other))
    assert closed.status_code == 201, closed.text
    closed_id = closed.json()["conversation"]["id"]

    day = datetime.now(WARSAW).date() + timedelta(days=5)
    assert pg_client.put(f"/v1/classifieds/{offers[0]}/viewing-settings", json={
        "booking_mode": "REQUEST_APPROVAL", "duration_minutes": 30,
        "minimum_notice_minutes": 0, "max_concurrent_bookings": 5},
        headers=auth(owner)).status_code == 200
    assert pg_client.post(f"/v1/classifieds/{offers[0]}/viewing-windows", json={
        "window_type": "ONE_OFF", "local_date": day.isoformat(), "local_start_time": "10:00",
        "local_end_time": "12:00"}, headers=auth(owner)).status_code == 201
    viewing = pg_client.post(f"/v1/classifieds/{offers[0]}/viewings",
                             json={"starts_at": _slot(day, 10)}, headers=auth(renter))
    assert viewing.status_code == 201, viewing.text
    assert pg_client.post(f"/v1/viewings/{viewing.json()['id']}/confirm",
                          headers=auth(owner)).status_code == 200

    with sessions() as db:
        prop = db.scalar(select(ClassifiedOffer.property_id).where(ClassifiedOffer.id == offers[1]))
    cover = _approved(pg_client, owner, prop)
    stolen = _approved(pg_client, owner, prop)
    for asset, is_cover in ((cover, True), (stolen, False)):
        assert pg_client.post(f"/v1/classifieds/{offers[1]}/media",
                              json={"media_asset_id": asset, "is_cover": is_cover},
                              headers=auth(owner)).status_code == 201

    with sessions() as db:
        moderator = db.scalar(select(User).where(User.email == "dr-phase1-moderator@example.com"))
        message_id = db.scalar(text("SELECT id FROM messages WHERE body = :b"),
                               {"b": REDACTED_TEXT})
        decisions.apply_message_decision(
            db, actor=moderator, message_id=message_id, action="CONTENT_REMOVED",
            reason_code="HARASSMENT", expected_head_decision_id=None)
        db.commit()
        decisions.apply_conversation_decision(
            db, actor=moderator, conversation_id=closed_id, action="FEATURE_RESTRICTED",
            reason_code="HARASSMENT", expected_head_decision_id=None)
        db.commit()
        decisions.apply_media_decision(
            db, actor=moderator, media_asset_id=stolen, action="CONTENT_REMOVED",
            reason_code="STOLEN_MEDIA", expected_head_decision_id=None)
        db.commit()
        other_id = db.scalar(select(User.id).where(User.email == "dr-phase1-tenant2@example.com"))
    return {"live": live_id, "closed": closed_id, "message": message_id,
            "viewing": viewing.json()["id"], "cover": cover, "stolen": stolen,
            "closed_requester": other_id}


def _seed_moderation(pg_client, sessions, listing_id, *, renter_email):
    """A report and a hold → release → hold chain on the already non-public
    listing (the public answer of the drill is unchanged), plus an open review
    request on the current hold."""
    moderator_email = "dr-phase1-moderator@example.com"
    register_and_login(pg_client, moderator_email, "guest")
    with sessions() as db:
        db.execute(text("UPDATE users SET role = 'admin' WHERE email = :e"),
                   {"e": moderator_email})
        moderator = db.scalar(select(User).where(User.email == moderator_email))
        renter_id = db.scalar(select(User.id).where(User.email == renter_email))
        report = Report(reporter_user_id=renter_id, target_type="LISTING",
                        target_id=listing_id, listing_id=listing_id, category="SCAM",
                        severity="HIGH", snapshot={"title": "Przywrócone 2"})
        db.add(report)
        db.commit()
        first = decisions.apply_listing_decision(
            db, actor=moderator, listing_id=listing_id, action="VISIBILITY_LIMITED",
            reason_code="SCAM", expected_head_decision_id=None, report_id=report.id)
        db.commit()
        release = decisions.apply_listing_decision(
            db, actor=moderator, listing_id=listing_id, action="NO_ACTION",
            reason_code="REINSTATED_DECISION_ERROR",
            expected_head_decision_id=first.decision_id)
        db.commit()
        again = decisions.apply_listing_decision(
            db, actor=moderator, listing_id=listing_id, action="CONTENT_EDIT_REQUIRED",
            reason_code="MISLEADING_PRICE", expected_head_decision_id=release.decision_id)
        db.add(ModerationReviewRequest(decision_id=again.decision_id,
                                       requested_by_user_id=moderator.id, note="poprawione"))
        db.commit()


def _rows(conn, table):
    # Sorted on the whole row, not on the first column: tables with a
    # composite key (property_authority_scopes) tie on column 1, and tied rows
    # come back in no defined order — the comparison was order-flaky (PR-001R).
    return sorted(conn.execute(text(f"SELECT * FROM {table}")).all(), key=repr)  # noqa: S608


def _public_ids(url):
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            return set(db.scalars(select(ClassifiedOffer.id).where(freshness.public_clause(db))))
    finally:
        engine.dispose()


def test_phase1_data_survives_backup_destroy_restore(pg_client, pg_session,
                                                     pg_migrated_engine, monkeypatch):
    offers, search_id, tokens, e = _seed(pg_client, pg_session, pg_migrated_engine, monkeypatch)
    with pg_migrated_engine.connect() as conn:
        before = {t: _rows(conn, t) for t in TABLES}
        # Every TASK-014 table holds real state, or "identical after restore" proves nothing.
        assert all(before[t] for t in TASK014_TABLES), \
            {t: len(before[t]) for t in TASK014_TABLES}
        assert all(before[t] for t in TASK015_TABLES), \
            {t: len(before[t]) for t in TASK015_TABLES}
        # 3 on the held listing + message removal, conversation restriction, photo removal
        assert len(before["moderation_decisions"]) == 6
        assert conn.scalar(text("SELECT count(DISTINCT channel) FROM alert_deliveries")) == 2
        geogs_before = conn.execute(text(
            "SELECT p.id, ST_AsText(p.exact_geog::geometry), ST_AsText(o.public_geog::geometry) "
            "FROM properties p JOIN classified_offers o ON o.property_id = p.id ORDER BY 1")).all()
        head = conn.scalar(text("SELECT version_num FROM alembic_version"))
    public_before = _public_ids(TEST_DATABASE_URL)
    assert public_before == {offers[0], offers[1]}

    # 1. backup
    artifact = _run([PG_DUMP, "--format=custom", "--no-owner", "--no-privileges",
                     f"--dbname={_libpq(TEST_DATABASE_URL)}"])
    assert artifact[:5] == b"PGDMP", "not a custom-format dump"

    # 2. restore into a database that never saw the data
    scratch = f"homies_dr1_{uuid.uuid4().hex[:8]}"
    admin = create_engine(_with_database(TEST_DATABASE_URL, "postgres"),
                          isolation_level="AUTOCOMMIT")
    with admin.begin() as conn:
        conn.execute(text(f'CREATE DATABASE "{scratch}"'))
    target = _with_database(TEST_DATABASE_URL, scratch)
    restored = create_engine(target)
    try:
        _run([PG_RESTORE, "--no-owner", "--no-privileges", "--exit-on-error",
              f"--dbname={_libpq(target)}"], stdin=artifact)

        # 3. the copy is the same business
        with restored.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == head
            from alembic.script import ScriptDirectory

            assert head == ScriptDirectory.from_config(alembic_config()).get_current_head()
            for table in TABLES:
                assert _rows(conn, table) == before[table], table
            assert conn.execute(text(
                "SELECT p.id, ST_AsText(p.exact_geog::geometry), "
                "ST_AsText(o.public_geog::geometry) FROM properties p "
                "JOIN classified_offers o ON o.property_id = p.id ORDER BY 1")).all() \
                == geogs_before
            assert conn.scalar(text(
                "SELECT count(*) FROM pg_indexes WHERE indexname = "
                "'ix_classified_offers_public_geog'")) == 1
        assert _public_ids(target) == public_before  # same public answer, stale stays hidden

        # TASK-014 on the copy: the saved search is still a VALID stored query
        # (canonical form and fingerprint intact), and the emailed unsubscribe
        # capabilities still resolve by their hash.
        with Session(restored) as db:
            saved_service.load_query(db, db.get(SavedSearch, search_id))
        with restored.connect() as conn:
            stored = set(conn.scalars(text("SELECT token_hash FROM unsubscribe_tokens")))
        assert {delivery.token_hash(t) for t in tokens} <= stored

        # ...and the guards still refuse on the copy.
        with pytest.raises(IntegrityError) as caught, restored.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET public_location_precision = "
                              "'EXACT' WHERE id = :o"), {"o": offers[0]})
        assert caught.value.orig.diag.constraint_name == "ck_classified_offers_location_precision"
        with pytest.raises(IntegrityError), restored.begin() as conn:
            conn.execute(text("UPDATE classified_offers SET status = 'published' "
                              "WHERE id = :o"), {"o": offers[0]})
        with pytest.raises(DBAPIError), restored.begin() as conn:  # hierarchy trigger
            top = conn.scalar(text("SELECT id FROM admin_areas WHERE parent_id IS NULL "
                                   "ORDER BY id LIMIT 1"))
            child = conn.scalar(text("SELECT id FROM admin_areas WHERE parent_id = :p "
                                     "LIMIT 1"), {"p": top})
            conn.execute(text("UPDATE admin_areas SET parent_id = :c, level = 3 "
                              "WHERE id = :t"), {"c": child, "t": top})
        with pytest.raises(IntegrityError) as caught, restored.begin() as conn:  # one alert per episode
            # the same delivery again under a new id: only the UNIQUE episode key differs
            conn.execute(text("CREATE TEMP TABLE twin AS SELECT * FROM alert_deliveries LIMIT 1"))
            conn.execute(text("UPDATE twin SET id = gen_random_uuid()::text"))
            conn.execute(text("INSERT INTO alert_deliveries SELECT * FROM twin"))
        assert caught.value.orig.diag.constraint_name == \
            "uq_alert_deliveries_user_episode_channel"
        with pytest.raises(IntegrityError), restored.begin() as conn:  # one match per episode
            conn.execute(text("INSERT INTO saved_search_matches SELECT * FROM "
                              "saved_search_matches LIMIT 1"))
        # TASK-015 closure on the copy: engagement and media moderation state.
        with restored.connect() as conn:
            assert conn.scalar(text("SELECT status FROM conversations WHERE id = :c"),
                               {"c": e["closed"]}) == "CLOSED"
            assert conn.scalar(text("SELECT status FROM conversations WHERE id = :c"),
                               {"c": e["live"]}) == "ACTIVE"
            last = conn.execute(text("SELECT message_type, body FROM messages "
                                     "WHERE conversation_id = :c ORDER BY created_at DESC, id "
                                     "LIMIT 1"), {"c": e["closed"]}).one()
            assert tuple(last) == ("SYSTEM", effects.CLOSED_BY_HOMIES)
            assert conn.scalar(text("SELECT redacted_at IS NOT NULL AND redaction_reason_code "
                                    "= 'HARASSMENT' FROM messages WHERE id = :m"),
                               {"m": e["message"]})
            assert conn.scalar(text("SELECT status FROM viewings WHERE id = :v"),
                               {"v": e["viewing"]}) == "CONFIRMED"
            states = dict(conn.execute(text(
                "SELECT id, moderation_state FROM media_assets WHERE id IN (:a, :b)"),
                {"a": e["cover"], "b": e["stolen"]}).all())
            assert states == {e["cover"]: "APPROVED", e["stolen"]: "RESTRICTED"}
        with Session(restored) as db:
            offer = db.get(ClassifiedOffer, offers[1])
            # G-14 holds on the copy, and the public projection still shows only
            # the approved photo (the restricted one stays linked, never public).
            assert hold.recontact_blocked(db, offers[1], e["closed_requester"],
                                          offer.public_generation)
            assert [m.id for m in properties_router.public_listing(offer).media] == [e["cover"]]
            assert db.scalar(text("SELECT count(*) FROM listing_media WHERE media_asset_id = :s"),
                             {"s": e["stolen"]}) == 1
        # TASK-015 on the copy: the chain and its head survive, the decisions
        # stay immutable, and the chain still cannot fork.
        with Session(restored) as db:
            held = [hold.listing_held(db, o) for o in offers]
        assert held == [False, False, True]
        with pytest.raises(DBAPIError), restored.begin() as conn:  # append-only trigger
            conn.execute(text("UPDATE moderation_decisions SET reason_code = 'OTHER'"))
        with pytest.raises(DBAPIError), restored.begin() as conn:
            conn.execute(text("DELETE FROM moderation_decisions"))
        with pytest.raises(IntegrityError) as caught, restored.begin() as conn:  # no fork
            conn.execute(text("CREATE TEMP TABLE twin AS SELECT * FROM moderation_decisions "
                              "WHERE supersedes_decision_id IS NOT NULL LIMIT 1"))
            conn.execute(text("UPDATE twin SET id = gen_random_uuid()::text"))
            conn.execute(text("INSERT INTO moderation_decisions SELECT * FROM twin"))
        assert caught.value.orig.diag.constraint_name == "uq_moderation_decisions_supersedes"
        with pytest.raises(IntegrityError), restored.begin() as conn:  # one live report
            conn.execute(text("CREATE TEMP TABLE r2 AS SELECT * FROM reports LIMIT 1"))
            conn.execute(text("UPDATE r2 SET id = gen_random_uuid()::text, status = 'OPEN', "
                              "resolution_decision_id = NULL"))
            conn.execute(text("INSERT INTO reports SELECT * FROM r2"))
            conn.execute(text("UPDATE r2 SET id = gen_random_uuid()::text"))
            conn.execute(text("INSERT INTO reports SELECT * FROM r2"))  # a second live one
        with pytest.raises(IntegrityError), restored.begin() as conn:  # one address, one property
            conn.execute(text("UPDATE properties SET address_id = "
                              "(SELECT address_id FROM properties ORDER BY id LIMIT 1) "
                              "WHERE id = (SELECT id FROM properties ORDER BY id DESC LIMIT 1)"))
    finally:
        restored.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": scratch})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
        admin.dispose()
