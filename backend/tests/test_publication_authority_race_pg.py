"""Publication authorisation is atomic across all three authority chains
(TASK-003 F-04 remainder, TASK-004) — real PostgreSQL.

TASK-002 serialised publication with a direct PropertyAuthority revoke and a
space archive (test_publication_race_pg.py). TASK-003 then showed the same
gap through the other links of a chain: a membership revoked, a mandate
revoked, an organisation suspended, a legal party archived or a mandate
expiring after publication's last check — and the listing went public on a
chain that no longer existed.

Every chain-loss path is tested in both serial orders:

* "decided first": publication has made its protected decision
  (authorize_for_mutation) and holds its locks; the loss must WAIT — observed
  in pg_stat_activity through pg_blocking_pids, naming the table — and lands
  after the publication commits. Outcome A of the contract.
* "lost first": the loss commits after publication's lock-free pre-check but
  before its protected decision; publication must be refused. Outcome B.

Never: the loss reports success and a stale publication then commits.
"""

import threading
import time
from datetime import timedelta

import pytest
from sqlalchemy import Date, literal, select, text
from sqlalchemy.orm import Session

from app.modules.identity import organizations, parties
from app.modules.properties import authority
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope
from tests.conftest import auth, authorization_date, register_and_login
from tests.test_organizations import _draft, _join, _mandate, _org, _org_property
from tests.test_publication_race_pg import _draft_listing, _pause_publication_at

WAIT = 15


# --- helpers ------------------------------------------------------------------------


def _blocked_on(engine, table: str, blocker: int | None = None) -> bool:
    """True once some backend running a statement on `table` is blocked — by
    the backend `blocker` when given (the publisher's, so the wait is shown to
    be on the publication's own locks, not on anything else)."""
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            queries = conn.scalars(text(
                "SELECT query FROM pg_stat_activity WHERE datname = current_database() "
                "AND cardinality(pg_blocking_pids(pid)) > 0 "
                "AND (CAST(:b AS integer) IS NULL OR :b = ANY(pg_blocking_pids(pid)))"
            ), {"b": blocker}).all()
        if any(table in q for q in queries):
            return True
        time.sleep(0.05)
    return False


def _status(engine, offer):
    with engine.connect() as conn:
        return conn.scalar(text("SELECT status FROM classified_offers WHERE id = :o"),
                           {"o": offer})


def _backend_xid(engine, pid: int) -> str | None:
    """The transaction id backend `pid` is running now (assigned once it has
    written or taken row locks — the publication's FOR SHARE locks do)."""
    with engine.connect() as conn:
        return conn.scalar(text(
            "SELECT backend_xid::text FROM pg_stat_activity WHERE pid = :p"), {"p": pid})


def _transaction_open(engine, xid: str) -> bool:
    """Whether transaction `xid` is still running — database evidence of
    commit order, where HTTP/thread completion order is not (TASK-009 P3: a
    later commit's response can return first). By xid, not by backend state:
    after committing, the same backend may already run its next transaction."""
    with engine.connect() as conn:
        return bool(conn.scalar(text(
            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE backend_xid::text = :x)"),
            {"x": xid}))


def _uid(client, token):
    return client.get("/v1/me", headers=auth(token)).json()["id"]


def _org_agent(c):
    """An organisation property, published-ready; an AGENT who will publish."""
    boss = register_and_login(c, "boss@race.example", "host")
    org = _org(c, boss)
    prop = _org_property(c, boss, org["id"])["id"]
    agent = _join(c, boss, org["id"], "agent@race.example", "AGENT")
    offer = _draft(c, agent, prop).json()["id"]
    return {"boss": boss, "org": org["id"], "prop": prop, "publisher": agent,
            "agent_id": _uid(c, agent), "offer": offer}


def _representative(c, **dates):
    """A personal property; a representative publishing under a mandate."""
    owner, prop, offer = _draft_listing(c)
    rep = register_and_login(c, "rep@race.example", "host")
    assert _mandate(c, owner, "rep@race.example", ["PUBLISH_LISTING"], **dates).status_code == 202
    mandate = c.get("/v1/me/mandates", headers=auth(owner)).json()[0]["id"]
    return {"owner": owner, "prop": prop, "offer": offer, "publisher": rep, "mandate": mandate}


def _publisher_thread(c, ctx, result):
    return threading.Thread(target=lambda: result.update(
        publish=c.post(f"/v1/classifieds/{ctx['offer']}/publish",
                       headers=auth(ctx["publisher"]))))


def _can_publish_now(engine, c, ctx) -> bool:
    with Session(engine) as db:
        return authority.can_act(db, _uid(c, ctx["publisher"]), ctx["prop"],
                                 "PUBLISH_LISTING", verified=True)


def _holder_party(engine, prop):
    with engine.connect() as conn:
        return conn.scalar(text(
            "SELECT holder_legal_party_id FROM property_authorities WHERE property_id = :p "
            "ORDER BY created_at LIMIT 1"), {"p": prop})


# --- the losses ----------------------------------------------------------------------
# Each returns a callable performing the loss through the supported path and
# returning something truthy on success, plus the table its write touches.


def _loss(kind, c, engine, ctx):
    if kind == "membership":
        return ("organization_memberships", lambda: c.post(
            f"/v1/organizations/{ctx['org']}/members/{ctx['agent_id']}/revoke",
            headers=auth(ctx["boss"])).status_code == 200)
    if kind == "mandate":
        return ("representation_mandates", lambda: c.post(
            f"/v1/me/mandates/{ctx['mandate']}/revoke",
            headers=auth(ctx["owner"])).status_code == 200)
    if kind == "organization":
        def suspend():
            with Session(engine) as db:
                organizations.set_organization_status(db, ctx["org"], "SUSPENDED")
                db.commit()
            return True
        return ("organizations", suspend)
    if kind == "organization_sql":
        def suspend_sql():
            with engine.begin() as conn:
                conn.execute(text("UPDATE organizations SET status = 'SUSPENDED' WHERE id = :o"),
                             {"o": ctx["org"]})
            return True
        return ("organizations", suspend_sql)
    if kind == "party":
        party = _holder_party(engine, ctx["prop"])

        def archive():
            with Session(engine) as db:
                parties.set_legal_party_status(db, party, "ARCHIVED")
                db.commit()
            return True
        return ("legal_parties", archive)
    if kind == "party_sql":
        party = _holder_party(engine, ctx["prop"])

        def archive_sql():
            with engine.begin() as conn:
                conn.execute(text("UPDATE legal_parties SET status = 'ARCHIVED' WHERE id = :p"),
                             {"p": party})
            return True
        return ("legal_parties", archive_sql)
    # The relationship and scope rows of a chain (TASK-006 N-03). Raw SQL: no
    # supported path changes them today, which is exactly why the guarantee
    # must not depend on one.
    if kind == "person_link_sql":
        party = _holder_party(engine, ctx["prop"])

        def unlink_person():
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE person_legal_parties SET linked_user_id = NULL "
                    "WHERE legal_party_id = :p"), {"p": party})
            return True
        return ("person_legal_parties", unlink_person)
    if kind == "org_link_sql":
        def unlink_org():
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE organization_legal_parties SET organization_id = NULL "
                    "WHERE organization_id = :o"), {"o": ctx["org"]})
            return True
        return ("organization_legal_parties", unlink_org)
    if kind == "mandate_scope_sql":
        def drop_mandate_scope():
            with engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM representation_mandate_scopes "
                    "WHERE mandate_id = :m AND scope = 'PUBLISH_LISTING'"),
                    {"m": ctx["mandate"]})
            return True
        return ("representation_mandate_scopes", drop_mandate_scope)
    if kind == "authority_scope_sql":
        def drop_authority_scope():
            with engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM property_authority_scopes WHERE scope = 'PUBLISH_LISTING' "
                    "AND property_authority_id IN "
                    "(SELECT id FROM property_authorities WHERE property_id = :p)"),
                    {"p": ctx["prop"]})
            return True
        return ("property_authority_scopes", drop_authority_scope)
    raise AssertionError(kind)


def _context(kind, c):
    if kind in ("membership", "organization", "organization_sql", "org_link_sql"):
        return _org_agent(c)
    if kind in ("mandate", "mandate_scope_sql"):
        return _representative(c)
    owner, prop, offer = _draft_listing(c)
    return {"owner": owner, "prop": prop, "offer": offer, "publisher": owner}


LOSSES = ["membership", "mandate", "organization", "organization_sql", "party", "party_sql",
          "person_link_sql", "org_link_sql", "mandate_scope_sql", "authority_scope_sql"]


# --- outcome A: the decision is made first; the loss waits ---------------------------


@pytest.mark.parametrize("kind", LOSSES)
def test_a_loss_arriving_after_the_decision_waits_for_the_publication(
    pg_client, pg_migrated_engine, monkeypatch, kind
):
    ctx = _context(kind, pg_client)
    table, lose = _loss(kind, pg_client, pg_migrated_engine, ctx)
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}

    def publish():
        result["publish"] = pg_client.post(f"/v1/classifieds/{ctx['offer']}/publish",
                                           headers=auth(ctx["publisher"]))

    def loss():
        result["lost"] = lose()
        # The loss has committed. Was the publication's transaction still open?
        result["publisher_open_at_loss"] = _transaction_open(pg_migrated_engine,
                                                             result["publisher_xid"])

    publisher = threading.Thread(target=publish)
    loser = threading.Thread(target=loss)
    publisher.start()
    try:
        assert reached.wait(WAIT), "publication never reached its protected decision"
        result["publisher_xid"] = _backend_xid(pg_migrated_engine, reached.pid)
        assert result["publisher_xid"], "the paused publication holds no transaction id"
        loser.start()
        assert _blocked_on(pg_migrated_engine, table, reached.pid), \
            f"the {kind} loss did not wait on the publication"
        assert "lost" not in result, "the loss completed while publication held its proof"
    finally:
        resume.set()
        publisher.join(WAIT)
        if loser.ident:
            loser.join(WAIT)

    # Serial order: publication (on a valid chain), then the loss. Database
    # evidence: the loss was blocked by the publisher's backend (above), and
    # when the loss committed that backend's transaction was already closed.
    # (Thread completion order proves nothing: TASK-009 P3.)
    assert result["publisher_open_at_loss"] is False
    assert result["publish"].status_code == 200, result["publish"].text
    assert result["lost"] is True
    assert _status(pg_migrated_engine, ctx["offer"]) == "active"
    # After the loss the same user can no longer act on this property.
    assert not _can_publish_now(pg_migrated_engine, pg_client, ctx)


# --- outcome B: the loss commits first; publication is refused -----------------------


@pytest.mark.parametrize("kind", LOSSES)
def test_a_loss_committed_before_the_decision_refuses_the_publication(
    pg_client, pg_migrated_engine, monkeypatch, kind
):
    ctx = _context(kind, pg_client)
    _, lose = _loss(kind, pg_client, pg_migrated_engine, ctx)
    reached, resume = _pause_publication_at(monkeypatch, "precheck")
    result: dict = {}
    publisher = _publisher_thread(pg_client, ctx, result)
    publisher.start()
    try:
        assert reached.wait(WAIT), "publication never passed its pre-check"
        assert lose() is True  # nothing held yet: commits at once
        assert not _can_publish_now(pg_migrated_engine, pg_client, ctx)
    finally:
        resume.set()
        publisher.join(WAIT)

    assert result["publish"].status_code in (403, 404), result["publish"].text
    assert _status(pg_migrated_engine, ctx["offer"]) == "draft"
    assert pg_client.get(f"/v1/classifieds/{ctx['offer']}").status_code == 404


# --- expiry: the clock is read at the decision ---------------------------------------


def _tomorrow_on_the_database(monkeypatch):
    tomorrow = authorization_date() + timedelta(days=1)
    monkeypatch.setattr(authority, "decision_date", lambda db: literal(tomorrow, Date))


def test_a_mandate_expiring_before_the_decision_refuses_the_publication(
    pg_client, pg_migrated_engine, monkeypatch
):
    """TASK-003 reproduction: valid through today at the pre-check; midnight
    passes before the decision. The decision reads the date then, so the
    mandate is expired and publication is refused."""
    ctx = _representative(pg_client, effective_until=authorization_date())
    reached, resume = _pause_publication_at(monkeypatch, "precheck")
    result: dict = {}
    publisher = _publisher_thread(pg_client, ctx, result)
    publisher.start()
    try:
        assert reached.wait(WAIT)
        _tomorrow_on_the_database(monkeypatch)
    finally:
        resume.set()
        publisher.join(WAIT)
    assert result["publish"].status_code in (403, 404), result["publish"].text
    assert _status(pg_migrated_engine, ctx["offer"]) == "draft"


def test_a_mandate_valid_at_the_decision_publishes_even_if_midnight_follows(
    pg_client, pg_migrated_engine, monkeypatch
):
    """The decision is the linearisation point. A boundary crossed after it is
    the serial order "published, then expired" — legal, and the next attempt
    is refused."""
    ctx = _representative(pg_client, effective_until=authorization_date())
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}
    publisher = _publisher_thread(pg_client, ctx, result)
    publisher.start()
    try:
        assert reached.wait(WAIT)
        _tomorrow_on_the_database(monkeypatch)
    finally:
        resume.set()
        publisher.join(WAIT)
    assert result["publish"].status_code == 200, result["publish"].text
    pause = pg_client.post(f"/v1/classifieds/{ctx['offer']}/pause", headers=auth(ctx["owner"]))
    assert pause.status_code == 200
    again = pg_client.post(f"/v1/classifieds/{ctx['offer']}/publish",
                           headers=auth(ctx["publisher"]))
    assert again.status_code in (403, 404)


def test_the_decision_date_is_the_database_clock(pg_session):
    """Not a Python date captured earlier in the request."""
    from sqlalchemy.dialects import postgresql

    compiled = str(authority.decision_date(pg_session).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "statement_timestamp()" in compiled and "UTC" in compiled
    utc_today = pg_session.scalar(select(authority.decision_date(pg_session)))
    assert utc_today == authority._today()


# --- another valid chain survives ------------------------------------------------------


def _two_chains(c, engine):
    """The agent publishes through an organisation membership AND through a
    mandate from a second, personal authority holder on the same property."""
    ctx = _org_agent(c)
    other = register_and_login(c, "coowner@race.example", "host")
    # The co-owner's personal legal party, created by granting the mandate.
    assert _mandate(c, other, "agent@race.example", ["PUBLISH_LISTING"]).status_code == 202
    with engine.connect() as conn:
        party = conn.scalar(text(
            "SELECT p.legal_party_id FROM person_legal_parties p JOIN users u "
            "ON u.id = p.linked_user_id WHERE u.email = 'coowner@race.example'"))
        first = conn.scalar(select(PropertyAuthority).where(
            PropertyAuthority.property_id == ctx["prop"]).limit(1))
    with Session(engine) as db:
        existing = db.get(PropertyAuthority, first)
        second = PropertyAuthority(
            property_id=ctx["prop"], holder_legal_party_id=party, authority_type="CO_OWNER",
            status="ACTIVE", verification_state="VERIFIED",
            effective_from=existing.effective_from, created_by_user_id=existing.created_by_user_id,
        )
        db.add(second)
        db.flush()
        db.add(PropertyAuthorityScope(property_authority_id=second.id, scope="PUBLISH_LISTING"))
        db.commit()
    ctx["coowner"] = other
    ctx["mandate"] = c.get("/v1/me/mandates", headers=auth(other)).json()[0]["id"]
    return ctx


def _lose_one_of_two(c, ctx, which):
    if which == "membership":
        return c.post(f"/v1/organizations/{ctx['org']}/members/{ctx['agent_id']}/revoke",
                      headers=auth(ctx["boss"])).status_code
    return c.post(f"/v1/me/mandates/{ctx['mandate']}/revoke",
                  headers=auth(ctx["coowner"])).status_code


@pytest.mark.parametrize("which", ["membership", "mandate"])
def test_a_surviving_chain_still_publishes_when_another_is_revoked_first(
    pg_client, pg_migrated_engine, monkeypatch, which
):
    ctx = _two_chains(pg_client, pg_migrated_engine)
    reached, resume = _pause_publication_at(monkeypatch, "precheck")
    result: dict = {}
    publisher = _publisher_thread(pg_client, ctx, result)
    publisher.start()
    try:
        assert reached.wait(WAIT)
        assert _lose_one_of_two(pg_client, ctx, which) == 200  # one chain is gone
        assert _can_publish_now(pg_migrated_engine, pg_client, ctx)  # the other remains
    finally:
        resume.set()
        publisher.join(WAIT)
    assert result["publish"].status_code == 200, result["publish"].text
    assert _status(pg_migrated_engine, ctx["offer"]) == "active"


@pytest.mark.parametrize("which", ["membership", "mandate"])
def test_every_valid_chain_is_protected_not_just_one(
    pg_client, pg_migrated_engine, monkeypatch, which
):
    """With two valid chains, revoking EITHER waits for the decided publication."""
    ctx = _two_chains(pg_client, pg_migrated_engine)
    table = "organization_memberships" if which == "membership" else "representation_mandates"
    reached, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}

    def publish():
        result["publish"] = pg_client.post(f"/v1/classifieds/{ctx['offer']}/publish",
                                           headers=auth(ctx["publisher"]))

    def revoke():
        result["revoked"] = _lose_one_of_two(pg_client, ctx, which)
        result["publisher_open_at_loss"] = _transaction_open(pg_migrated_engine,
                                                             result["publisher_xid"])

    publisher = threading.Thread(target=publish)
    revoker = threading.Thread(target=revoke)
    publisher.start()
    try:
        assert reached.wait(WAIT)
        result["publisher_xid"] = _backend_xid(pg_migrated_engine, reached.pid)
        assert result["publisher_xid"], "the paused publication holds no transaction id"
        revoker.start()
        assert _blocked_on(pg_migrated_engine, table, reached.pid)
    finally:
        resume.set()
        publisher.join(WAIT)
        if revoker.ident:
            revoker.join(WAIT)
    assert result["publisher_open_at_loss"] is False
    assert result["publish"].status_code == 200
    assert result["revoked"] == 200


# --- no scope widening ------------------------------------------------------------------


def test_partial_scopes_on_different_chains_do_not_add_up(pg_client, pg_migrated_engine):
    """A mandate that may manage but not publish, plus a membership role that
    may read finances but not publish: neither chain carries PUBLISH_LISTING,
    so their union must not."""
    boss = register_and_login(pg_client, "boss@scope.example", "host")
    org = _org(pg_client, boss)
    prop = _org_property(pg_client, boss, org["id"])["id"]
    offer = _draft(pg_client, boss, prop).json()["id"]
    finance = _join(pg_client, boss, org["id"], "finance@scope.example", "FINANCE")
    # Org-principal mandates are frozen (dev. 18), so the MANAGE_PROPERTY-only
    # chain comes from a personal principal holding a second authority.
    other = register_and_login(pg_client, "manager@scope.example", "host")
    assert _mandate(pg_client, other, "finance@scope.example",
                    ["MANAGE_PROPERTY"]).status_code == 202
    with pg_migrated_engine.connect() as conn:
        party = conn.scalar(text(
            "SELECT p.legal_party_id FROM person_legal_parties p JOIN users u "
            "ON u.id = p.linked_user_id WHERE u.email = 'manager@scope.example'"))
    with Session(pg_migrated_engine) as db:
        auth_row = PropertyAuthority(
            property_id=prop, holder_legal_party_id=party, authority_type="CO_OWNER",
            status="ACTIVE", verification_state="VERIFIED", effective_from=authorization_date(),
            created_by_user_id=_uid(pg_client, boss))
        db.add(auth_row)
        db.flush()
        for scope in ("PUBLISH_LISTING", "EDIT_PROPERTY", "MANAGE_MEDIA"):
            db.add(PropertyAuthorityScope(property_authority_id=auth_row.id, scope=scope))
        db.commit()
    response = pg_client.post(f"/v1/classifieds/{offer}/publish", headers=auth(finance))
    assert response.status_code in (403, 404), response.text
    assert _status(pg_migrated_engine, offer) == "draft"


# --- sequential negatives through the protected path -----------------------------------


@pytest.mark.parametrize("case", [
    "unrelated", "removed_member", "expired_mandate", "revoked_mandate",
    "suspended_org", "inactive_party", "revoked_authority", "missing_scope", "unverified",
])
def test_no_invalid_chain_passes_the_protected_decision(pg_client, pg_migrated_engine, case):
    c, engine = pg_client, pg_migrated_engine
    if case in ("removed_member", "suspended_org"):
        ctx = _org_agent(c)
        if case == "removed_member":
            assert _loss("membership", c, engine, ctx)[1]()
        else:
            assert _loss("organization", c, engine, ctx)[1]()
    elif case in ("expired_mandate", "revoked_mandate", "missing_scope"):
        if case == "expired_mandate":
            ctx = _representative(c, effective_from=authorization_date() - timedelta(days=10),
                                  effective_until=authorization_date() - timedelta(days=1))
        elif case == "missing_scope":
            owner, prop, offer = _draft_listing(c)
            rep = register_and_login(c, "rep@race.example", "host")
            assert _mandate(c, owner, "rep@race.example", ["MANAGE_PROPERTY"]).status_code == 202
            ctx = {"owner": owner, "prop": prop, "offer": offer, "publisher": rep}
        else:
            ctx = _representative(c)
            assert _loss("mandate", c, engine, ctx)[1]()
    elif case == "unverified":
        owner = register_and_login(c, "unverified@race.example", "host")
        from tests.test_publication_race_pg import PROPERTY, OFFER
        prop = c.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
        offer = c.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                       headers=auth(owner)).json()["id"]
        ctx = {"owner": owner, "prop": prop, "offer": offer, "publisher": owner}
    else:
        owner, prop, offer = _draft_listing(c)
        ctx = {"owner": owner, "prop": prop, "offer": offer, "publisher": owner}
        if case == "unrelated":
            ctx["publisher"] = register_and_login(c, "stranger@race.example", "host")
        elif case == "inactive_party":
            assert _loss("party", c, engine, ctx)[1]()
        elif case == "revoked_authority":
            from tests.conftest import admin_login

            with engine.connect() as conn:
                aid = conn.scalar(select(PropertyAuthority.id).where(
                    PropertyAuthority.property_id == prop))
            assert c.post(f"/v1/admin/property-authorities/{aid}/revoke",
                          headers=auth(admin_login(c))).status_code == 200
    response = c.post(f"/v1/classifieds/{ctx['offer']}/publish", headers=auth(ctx["publisher"]))
    assert response.status_code in (403, 404), (case, response.text)
    assert _status(engine, ctx["offer"]) == "draft"
