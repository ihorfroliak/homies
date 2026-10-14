"""BP-8 PostgreSQL: observed serialization of G-14 against new/repeat disclosure."""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.audit import AuditLog
from app.modules.properties.models import ContactReveal
from app.modules.properties.router import reveal_contact
from tests.conftest import TEST_DATABASE_URL
from tests.test_engagement_safety_pg import _setup, _paused, _restrict, _blocked_count
from tests.test_reports_moderation_pg import _account, _deadlocks, _pid, _run, _session, _user

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


def _act(db, setup, moderator, action):
    if action == "restrict":
        result = _restrict(db, setup["conv"], moderator)
    else:
        result = reveal_contact(setup["offer"], user=_user(db, setup["tenant"]), db=db)
    db.commit()
    return result


@pytest.mark.parametrize("repeat", [False, True])
@pytest.mark.parametrize("restriction_first", [False, True])
def test_restriction_serializes_new_and_repeat_reveal_both_orders(
        pg_client, pg_migrated_engine, repeat, restriction_first):
    engine = pg_migrated_engine
    setup = _setup(pg_client)
    moderator = _account(engine, role="admin")
    with _session(engine) as db:
        viewer = _user(db, setup["tenant"])
        viewer.phone = "+48600100201"
        viewer.phone_verified_at = datetime.now(timezone.utc)
        db.commit()
        if repeat:
            reveal_contact(setup["offer"], user=viewer, db=db)
    deadlocks = _deadlocks(engine)
    paused, gate, reached = _paused(engine)
    blocker = _pid(paused)
    first, second = ("restrict", "reveal") if restriction_first else ("reveal", "restrict")
    results, threads = {}, []
    try:
        threads.append(_run(results, first, lambda: _act(paused, setup, moderator, first)))
        assert reached.wait(15), results

        def following():
            with _session(engine) as db:
                return _act(db, setup, moderator, second)
        threads.append(_run(results, second, following))
        assert _blocked_count(engine, blocker, 1), "second operation did not wait on first"
    finally:
        gate.set()
        for thread in threads:
            thread.join(25)
        paused.close()
        assert all(not thread.is_alive() for thread in threads)
    assert not isinstance(results[first], Exception), results[first]
    if restriction_first:
        assert getattr(results["reveal"], "status_code", None) == 409, results["reveal"]
        assert results["reveal"].detail == "RECONTACT_BLOCKED: contact is unavailable for this publication"
    else:
        assert not isinstance(results["restrict"], Exception), results["restrict"]
        assert results["reveal"].contact_phone == "+48 600 300 400"
    with _session(engine) as db:
        expected = int(repeat or not restriction_first)
        assert db.scalar(select(func.count()).select_from(ContactReveal)) == expected
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "classified.contact_revealed")) == expected
        with pytest.raises(HTTPException) as denied:
            reveal_contact(setup["offer"], user=_user(db, setup["tenant"]), db=db)
        assert getattr(denied.value, "status_code", None) == 409
        assert denied.value.detail.startswith("RECONTACT_BLOCKED")
    assert _deadlocks(engine) == deadlocks

def test_preloaded_generation_is_refreshed_after_legitimate_republish(pg_client, pg_migrated_engine):
    from tests.conftest import auth
    from app.modules.properties.models import ClassifiedOffer

    engine = pg_migrated_engine
    setup = _setup(pg_client)
    moderator = _account(engine, role="admin")
    with _session(engine) as db:
        viewer = _user(db, setup["tenant"])
        viewer.phone = "+48600100202"
        viewer.phone_verified_at = datetime.now(timezone.utc)
        db.commit()
        _restrict(db, setup["conv"], moderator)
        db.commit()
        cached = db.get(ClassifiedOffer, setup["offer"])
        old_generation = cached.public_generation
        for action in ("pause", "publish"):
            response = pg_client.post(f"/v1/classifieds/{setup['offer']}/{action}",
                                      headers=auth(setup["owner_token"]))
            assert response.status_code == 200, response.text
        assert cached.public_generation == old_generation
        result = reveal_contact(setup["offer"], user=viewer, db=db)
        assert result.contact_phone == "+48 600 300 400"
        assert cached.public_generation == old_generation + 1
