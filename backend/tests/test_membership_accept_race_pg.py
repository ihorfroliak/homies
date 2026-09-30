"""Accepting an invitation cannot undo a revoke (TASK-005 N-02, TASK-006) —
real PostgreSQL.

TASK-005 reproduced: the invitee's accept read the INVITED row without a lock,
the admin's revoke committed REVOKED and answered 200, and the accept then
wrote ACTIVE over it — role preserved, `revoked_at` still set. An ADMIN
invitation revoked this way became an active ADMIN.

accept_invitation now locks the row before reading it, as revoke_member does,
and accepts only a row that is still INVITED. The two serial outcomes:

* accept first: the revoke waits for it, then revokes the ACTIVE membership;
* revoke first: the accept waits for it, then finds no invitation (404).

Each test holds one side inside its transaction — after it has locked and
changed the row, before it commits — and observes the other side waiting on
that backend in pg_stat_activity.
"""

import threading

import pytest
from sqlalchemy import text

from app.modules.identity import organizations
from tests.conftest import auth, register_and_login
from tests.test_organizations import _org
from tests.test_publication_authority_race_pg import _blocked_on

WAIT = 15


def _invited(c, role, *, email="invitee@accept.example", slug="accept-race"):
    boss = register_and_login(c, f"boss-{slug}@accept.example", "host")
    org = _org(c, boss, slug=slug)
    invitee = register_and_login(c, email, "host")
    assert c.post(f"/v1/organizations/{org['id']}/members",
                  json={"email": email, "role": role}, headers=auth(boss)).status_code == 202
    invitee_id = c.get("/v1/me", headers=auth(invitee)).json()["id"]
    return {"boss": boss, "org": org["id"], "invitee": invitee, "invitee_id": invitee_id}


def _row(engine, org, user):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT status, role, revoked_at IS NOT NULL AS revoked, version "
            "FROM organization_memberships WHERE organization_id = :o AND user_id = :u"),
            {"o": org, "u": user}).one()


def _hold(monkeypatch, action):
    """Pause the request whose audit entry is `action` inside its transaction
    (row already locked and changed, not yet committed)."""
    reached, resume, info = threading.Event(), threading.Event(), {}
    real_audit = organizations.audit

    def held(db, **kwargs):
        if kwargs.get("action") == action:
            info["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
            reached.set()
            assert resume.wait(WAIT)
        return real_audit(db, **kwargs)

    monkeypatch.setattr(organizations, "audit", held)
    return reached, resume, info


def _accept(c, ctx, org=None, token=None):
    return c.post(f"/v1/organizations/{org or ctx['org']}/membership/accept",
                  headers=auth(token or ctx["invitee"]))


def _revoke(c, ctx):
    return c.post(f"/v1/organizations/{ctx['org']}/members/{ctx['invitee_id']}/revoke",
                  headers=auth(ctx["boss"]))


@pytest.mark.parametrize("role", ["ADMIN", "AGENT"])
def test_accept_first_then_the_revoke_waits_and_revokes(
    pg_client, pg_migrated_engine, monkeypatch, role
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, role)
    reached, resume, accept = _hold(monkeypatch, "organization.member_joined")
    result: dict = {}
    finished: list[str] = []

    def do_accept():
        result["accept"] = _accept(c, ctx)
        finished.append("accept")

    def do_revoke():
        result["revoke"] = _revoke(c, ctx)
        finished.append("revoke")

    acceptor, revoker = threading.Thread(target=do_accept), threading.Thread(target=do_revoke)
    acceptor.start()
    try:
        assert reached.wait(WAIT), "accept never reached its write"
        revoker.start()
        assert _blocked_on(engine, "organization_memberships", accept["pid"]), \
            "the revoke did not wait for the accept in flight"
        assert "revoke" not in result
    finally:
        resume.set()
        acceptor.join(WAIT)
        if revoker.ident:
            revoker.join(WAIT)

    assert finished == ["accept", "revoke"], finished
    assert (result["accept"].status_code, result["accept"].json()["status"]) == (200, "ACTIVE")
    assert (result["revoke"].status_code, result["revoke"].json()["status"]) == (200, "REVOKED")
    status, kept_role, revoked, _ = _row(engine, ctx["org"], ctx["invitee_id"])
    assert (status, kept_role, revoked) == ("REVOKED", role, True)


@pytest.mark.parametrize("role", ["ADMIN", "AGENT"])
def test_revoke_first_then_the_accept_finds_no_invitation(
    pg_client, pg_migrated_engine, monkeypatch, role
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, role)
    reached, resume, revoke = _hold(monkeypatch, "organization.member_revoked")
    result: dict = {}
    revoker = threading.Thread(target=lambda: result.update(revoke=_revoke(c, ctx)))
    acceptor = threading.Thread(target=lambda: result.update(accept=_accept(c, ctx)))
    revoker.start()
    try:
        assert reached.wait(WAIT), "revoke never reached its write"
        acceptor.start()
        assert _blocked_on(engine, "organization_memberships", revoke["pid"]), \
            "the accept did not wait for the revoke in flight"
    finally:
        resume.set()
        revoker.join(WAIT)
        if acceptor.ident:
            acceptor.join(WAIT)

    assert (result["revoke"].status_code, result["revoke"].json()["status"]) == (200, "REVOKED")
    assert result["accept"].status_code == 404, result["accept"].text
    status, kept_role, revoked, _ = _row(engine, ctx["org"], ctx["invitee_id"])
    assert (status, kept_role, revoked) == ("REVOKED", role, True)
    # And no chain came back: the invitee cannot act for the organisation.
    assert c.get(f"/v1/organizations/{ctx['org']}/members",
                 headers=auth(ctx["invitee"])).status_code == 404


# --- sequential: nothing but a live invitation of your own is accepted ----------------


def test_an_active_membership_is_not_accepted_again(pg_client, pg_migrated_engine):
    ctx = _invited(pg_client, "AGENT")
    assert _accept(pg_client, ctx).status_code == 200
    before = _row(pg_migrated_engine, ctx["org"], ctx["invitee_id"])
    assert _accept(pg_client, ctx).status_code == 404
    assert _row(pg_migrated_engine, ctx["org"], ctx["invitee_id"]) == before


def test_a_revoked_invitation_cannot_be_accepted(pg_client, pg_migrated_engine):
    ctx = _invited(pg_client, "ADMIN")
    assert _revoke(pg_client, ctx).status_code == 200
    assert _accept(pg_client, ctx).status_code == 404
    status, _, revoked, _ = _row(pg_migrated_engine, ctx["org"], ctx["invitee_id"])
    assert (status, revoked) == ("REVOKED", True)


def test_another_user_cannot_accept_someone_elses_invitation(pg_client, pg_migrated_engine):
    ctx = _invited(pg_client, "ADMIN")
    stranger = register_and_login(pg_client, "stranger@accept.example", "host")
    assert _accept(pg_client, ctx, token=stranger).status_code == 404
    assert _row(pg_migrated_engine, ctx["org"], ctx["invitee_id"])[0] == "INVITED"


def test_an_invitation_is_accepted_only_for_its_own_organisation(pg_client, pg_migrated_engine):
    ctx = _invited(pg_client, "AGENT")
    other = _invited(pg_client, "AGENT", email="someone-else@accept.example", slug="other-org")
    assert _accept(pg_client, ctx, org=other["org"]).status_code == 404
    assert _accept(pg_client, ctx, org="00000000-0000-0000-0000-000000000000").status_code == 404
    assert _row(pg_migrated_engine, ctx["org"], ctx["invitee_id"])[0] == "INVITED"
