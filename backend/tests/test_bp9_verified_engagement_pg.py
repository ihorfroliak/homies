"""BP-9 causal PostgreSQL waits: a pre-wait authority snapshot is not access."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.modules.engagement import router, viewings
from app.modules.engagement.models import Conversation, Message, Viewing, ViewingSettings
from app.modules.properties.models import ClassifiedOffer, PropertyAuthority
from tests.conftest import TEST_DATABASE_URL
from tests.test_engagement_safety_pg import _setup
from tests.test_publication_authority_race_pg import _blocked_on
from tests.test_reports_moderation_pg import _deadlocks, _pid, _run, _session, _user

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


@pytest.mark.parametrize("operation", ["send-row", "send-advisory", "replay-advisory",
                                      "stage", "assign", "settings", "confirm-settings", "decline",
                                      "cancel", "outcome"])
def test_revocation_during_observed_wait_denies_private_action(pg_client, pg_migrated_engine,
                                                              operation):
    engine = pg_migrated_engine
    setup = _setup(pg_client, viewing="CONFIRMED" if operation == "outcome" else "REQUESTED")
    key = str(uuid4())
    with _session(engine) as db:
        owner = _user(db, setup["owner"])
        owner_id = owner.id
        if operation == "replay-advisory":
            router.send_message(setup["conv"], router.MessageIn(body="private replay", client_message_id=key),
                                owner, db)
        before = db.scalar(select(func.count()).select_from(Message))
    deadlocks = _deadlocks(engine)
    blocker = _session(engine)
    table = "conversations"
    if "advisory" in operation:
        router._serialise_send(blocker, owner_id, key)
        table = "pg_advisory_xact_lock"
    elif operation in ("settings", "confirm-settings"):
        blocker.execute(select(ViewingSettings).where(
            ViewingSettings.listing_id == setup["offer"]).with_for_update())
        table = "viewing_settings"
    elif operation in ("decline", "cancel", "outcome"):
        blocker.execute(select(Viewing).where(Viewing.id == setup["viewing"]).with_for_update())
        table = "viewings"
    else:
        blocker.execute(select(Conversation).where(Conversation.id == setup["conv"]).with_for_update())
    pid = _pid(blocker)
    results = {}

    def act():
        with _session(engine) as db:
            owner = _user(db, setup["owner"])
            # Keep the ORM instances live across the wait: SQL must re-evaluate authority.
            cached_offer = db.get(ClassifiedOffer, setup["offer"])
            cached_root = db.scalar(select(PropertyAuthority).where(
                PropertyAuthority.property_id == cached_offer.property_id))
            assert cached_root.verification_state == "VERIFIED"
            if operation.startswith("send") or operation == "replay-advisory":
                return router.send_message(setup["conv"], router.MessageIn(
                    body="private replay", client_message_id=key), owner, db)
            if operation == "stage":
                return router.set_stage(setup["conv"], router.StageIn(provider_stage="SHORTLISTED"), owner, db)
            if operation == "assign":
                return router.assign(setup["conv"], router.AssignIn(user_id=owner_id), owner, db)
            if operation == "settings":
                return viewings.put_settings(setup["offer"], viewings.SettingsIn(duration_minutes=45), owner, db)
            if operation == "confirm-settings":
                return viewings.confirm(setup["viewing"], owner, db)
            if operation == "outcome":
                return viewings.record_outcome(setup["viewing"], viewings.OutcomeIn(outcome="COMPLETED"), owner, db)
            return getattr(viewings, operation)(setup["viewing"], owner, db)

    thread = _run(results, "action", act)
    try:
        assert _blocked_on(engine, table, pid), "action never waited on the held lock"
        with _session(engine) as db:
            property_id = db.scalar(select(ClassifiedOffer.property_id).where(ClassifiedOffer.id == setup["offer"]))
            db.execute(update(PropertyAuthority).where(PropertyAuthority.property_id == property_id)
                       .values(status="REVOKED"))
            db.commit()
    finally:
        blocker.rollback()
        blocker.close()
        thread.join(25)
        assert not thread.is_alive()
    assert getattr(results["action"], "status_code", None) == 404, results
    with _session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == before
        conv = db.get(Conversation, setup["conv"])
        assert conv.assigned_to_user_id is None
        assert conv.provider_stage == ("REPLIED" if operation == "replay-advisory" else "NEW")
        viewing = db.get(Viewing, setup["viewing"])
        assert viewing.status == ("CONFIRMED" if operation == "outcome" else "REQUESTED")
        assert db.scalar(select(ViewingSettings.duration_minutes).where(
            ViewingSettings.listing_id == setup["offer"])) == 30
    assert _deadlocks(engine) == deadlocks


def test_preloaded_property_link_cannot_keep_former_provider_access(pg_client, pg_migrated_engine):
    from tests.test_reports_moderation_pg import _listing

    engine = pg_migrated_engine
    setup = _setup(pg_client)
    _, _, other_listing = _listing(pg_client)
    with _session(engine) as db, _session(engine) as change:
        owner = _user(db, setup["owner"])
        cached_offer = db.get(ClassifiedOffer, setup["offer"])
        old_property = cached_offer.property_id
        router._load(db, owner, setup["conv"])
        replacement = change.get(ClassifiedOffer, other_listing)
        change.execute(update(ClassifiedOffer).where(ClassifiedOffer.id == setup["offer"])
                       .values(property_id=replacement.property_id, space_id=replacement.space_id))
        change.commit()
        assert cached_offer.property_id == old_property
        with pytest.raises(Exception) as denied:
            router._load(db, owner, setup["conv"])
        assert getattr(denied.value, "status_code", None) == 404
