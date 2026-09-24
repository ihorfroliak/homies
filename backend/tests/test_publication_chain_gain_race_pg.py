"""A chain gained while publication waits for its locks cannot carry it
(TASK-005 N-01, TASK-006) — real PostgreSQL.

TASK-004 reads the proof, locks it, and re-decides. TASK-005 found the gap
between the read and the locks: the lock step can wait (here, on a membership
revoke in flight), and a chain that becomes valid during that wait is not in
the proof and holds no lock. Before TASK-006 the re-decision accepted such a
chain; its later revoke then did not wait, and the listing went public with no
valid chain at commit:

    Y revoke in flight  ->  publication blocks on Y  ->  X granted
    ->  Y revoke commits  ->  decision passes on X (unlocked)
    ->  X revoke returns 200 at once  ->  publication commits ACTIVE

Now the decision is made only through locked rows. The attempt that raced is
refused (409) — the serial order "Y revoked, publication refused, X granted"
— and a new attempt reads a proof that contains X.

Every step below is a real API call. Y's revoke is held open inside its own
transaction (after it has locked and changed the row, before commit), so the
waits are observed in pg_stat_activity, not assumed from timing.
"""

import threading
import time

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.identity import organizations
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope
from tests.conftest import auth, register_and_login
from tests.test_organizations import _mandate
from tests.test_publication_authority_race_pg import (
    _blocked_on,
    _can_publish_now,
    _org_agent,
    _status,
)
from tests.test_publication_race_pg import _pause_publication_at

WAIT = 15


def _hold_membership_revoke(monkeypatch):
    """Pause revoke_member after it has locked and changed the row, before it
    commits. Returns (reached, resume, info) — info["pid"] is its backend."""
    reached, resume, info = threading.Event(), threading.Event(), {}
    real_audit = organizations.audit

    def held(db, **kwargs):
        if kwargs.get("action") == "organization.member_revoked":
            info["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
            reached.set()
            assert resume.wait(WAIT)
        return real_audit(db, **kwargs)

    monkeypatch.setattr(organizations, "audit", held)
    return reached, resume, info


def _second_holder(c, engine, prop):
    """A co-owner whose personal party holds a VERIFIED PUBLISH_LISTING
    authority on the property — but the agent has no path to it yet."""
    coowner = register_and_login(c, "gain-coowner@race.example", "host")
    assert c.get("/v1/me/mandates", headers=auth(coowner)).status_code == 200  # creates party
    with engine.connect() as conn:
        party = conn.scalar(text(
            "SELECT p.legal_party_id FROM person_legal_parties p JOIN users u "
            "ON u.id = p.linked_user_id WHERE u.email = 'gain-coowner@race.example'"))
    with Session(engine) as db:
        first = db.scalar(select(PropertyAuthority).where(PropertyAuthority.property_id == prop))
        second = PropertyAuthority(
            property_id=prop, holder_legal_party_id=party, authority_type="CO_OWNER",
            status="ACTIVE", verification_state="VERIFIED",
            effective_from=first.effective_from, created_by_user_id=first.created_by_user_id)
        db.add(second)
        db.flush()
        db.add(PropertyAuthorityScope(property_authority_id=second.id, scope="PUBLISH_LISTING"))
        db.commit()
    return coowner


def _race_to_gain(c, engine, monkeypatch):
    """Drive the TASK-005 interleaving up to "Y revoke committed". Returns the
    context, the running publisher, its result, the post-decision gate, and
    the new mandate X."""
    ctx = _org_agent(c)
    coowner = _second_holder(c, engine, ctx["prop"])
    assert not c.get("/v1/me/mandates", headers=auth(ctx["publisher"])).json()

    revoke_held, revoke_resume, revoke = _hold_membership_revoke(monkeypatch)
    decided, decided_resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}
    order: list[str] = []

    def revoke_y():
        result["revoke_y"] = c.post(
            f"/v1/organizations/{ctx['org']}/members/{ctx['agent_id']}/revoke",
            headers=auth(ctx["boss"])).status_code

    def publish():
        result["publish"] = c.post(f"/v1/classifieds/{ctx['offer']}/publish",
                                   headers=auth(ctx["publisher"]))
        order.append("publish")

    revoker = threading.Thread(target=revoke_y)
    publisher = threading.Thread(target=publish)
    revoker.start()
    assert revoke_held.wait(WAIT), "the membership revoke never reached its write"
    try:
        # 1-2. Y is being revoked; publication blocks on Y's row.
        publisher.start()
        assert _blocked_on(engine, "organization_memberships", revoke["pid"]), \
            "publication did not wait on the revoke in flight"
        # 3. X is granted while publication waits. The grant itself must not
        # wait: new authority is never blocked globally.
        started = time.monotonic()
        assert _mandate(c, coowner, "agent@race.example", ["PUBLISH_LISTING"]).status_code == 202
        assert time.monotonic() - started < 5
        mandate_x = c.get("/v1/me/mandates", headers=auth(coowner)).json()[0]["id"]
    finally:
        # 4. Y's revoke commits.
        revoke_resume.set()
        revoker.join(WAIT)
    assert result["revoke_y"] == 200
    # 5. Publication resumes: it either refuses, or (the TASK-005 defect)
    # passes its decision and stops at the gate.
    deadline = time.monotonic() + WAIT
    while publisher.is_alive() and not decided.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)
    return {"ctx": ctx, "coowner": coowner, "publisher": publisher, "result": result,
            "order": order, "decided": decided, "decided_resume": decided_resume,
            "mandate_x": mandate_x}


def test_a_chain_gained_during_the_lock_wait_cannot_carry_the_publication(
    pg_client, pg_migrated_engine, monkeypatch
):
    c, engine = pg_client, pg_migrated_engine
    race = _race_to_gain(c, engine, monkeypatch)
    ctx, result, order = race["ctx"], race["result"], race["order"]
    x_revoke: dict = {}

    def revoke_x():
        x_revoke["status"] = c.post(f"/v1/me/mandates/{race['mandate_x']}/revoke",
                                    headers=auth(race["coowner"])).status_code
        order.append("revoke_x")

    try:
        if race["decided"].is_set():
            # The decision passed on X. 6. X's revoke must then wait for it.
            loser = threading.Thread(target=revoke_x)
            loser.start()
            x_revoke["waited"] = _blocked_on(engine, "representation_mandates",
                                             race["decided"].pid)
            loser.join(1)
        else:
            revoke_x()  # 6. after the refused attempt
    finally:
        race["decided_resume"].set()
        race["publisher"].join(WAIT)
        if "waited" in x_revoke:
            loser.join(WAIT)

    # Never: X's revoke reported success first, then publication went ACTIVE
    # on a user with no valid chain.
    forbidden = (result["publish"].status_code == 200 and x_revoke["status"] == 200
                 and order.index("revoke_x") < order.index("publish"))
    assert not forbidden, "stale publication committed after its only chain was revoked"
    # The serial outcome now: Y revoked -> publication refused -> X granted
    # -> X revoked.
    assert result["publish"].status_code == 409, result["publish"].text
    assert x_revoke["status"] == 200
    assert _status(engine, ctx["offer"]) == "draft"
    assert c.get(f"/v1/classifieds/{ctx['offer']}").status_code == 404
    assert not _can_publish_now(engine, c, ctx)


def test_a_chain_gained_during_the_wait_is_used_by_the_next_attempt(
    pg_client, pg_migrated_engine, monkeypatch
):
    """Refusing the racing attempt is not refusing the chain: X stays valid,
    and a new request — whose proof contains X and locks it — publishes."""
    c, engine = pg_client, pg_migrated_engine
    race = _race_to_gain(c, engine, monkeypatch)
    ctx = race["ctx"]
    race["decided_resume"].set()
    race["publisher"].join(WAIT)
    assert race["result"]["publish"].status_code == 409, race["result"]["publish"].text
    assert _status(engine, ctx["offer"]) == "draft"

    assert _can_publish_now(engine, c, ctx)  # through X
    again = c.post(f"/v1/classifieds/{ctx['offer']}/publish", headers=auth(ctx["publisher"]))
    assert again.status_code == 200, again.text
    assert _status(engine, ctx["offer"]) == "active"
