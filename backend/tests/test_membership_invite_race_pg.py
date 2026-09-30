"""Membership invitations and acceptances are serialised on the membership row
(TASK-007 N-07, N-09, N-10; TASK-008) — real PostgreSQL.

* N-07: accept_invitation must take an EXCLUSIVE row lock before reading the
  status. With a shared lock two concurrent accepts of one invitation both
  read INVITED, both write, and PostgreSQL has to kill one of them as a
  deadlock. The TASK-006 accept-vs-revoke tests could not tell the difference.
* N-09: invite_member read the row without a lock and wrote INVITED by primary
  key; a re-invitation racing a join turned the ACTIVE member back into a
  pending invitation. It now locks the row first and only ever moves a
  REVOKED row to INVITED; INVITED and ACTIVE rows are left as they are.
* N-10: two first invitations of the same person both saw no row; the loser's
  INSERT hit the unique index and escaped as a 500. The loser now decides on
  the winner's row and answers the same 202.

One side is held inside its transaction (row locked / inserted, not yet
committed) and the other is observed waiting on that backend.
"""

import threading

import pytest
from sqlalchemy import text

from app.modules.identity import organizations
from tests.conftest import auth, register_and_login
from tests.test_membership_accept_race_pg import _accept, _invited, _row
from tests.test_organizations import _join
from tests.test_publication_authority_race_pg import _blocked_on

WAIT = 15


class _HoldFirst:
    """Pause the FIRST request whose audit entry is `action`, inside its
    transaction; later calls pass. `calls` counts every request that got as
    far as its audit call — i.e. that had already acted on the row."""

    def __init__(self, monkeypatch, action):
        self.reached, self.resume = threading.Event(), threading.Event()
        self.calls = 0
        self.pid = None
        real_audit = organizations.audit

        def held(db, **kwargs):
            if kwargs.get("action") == action:
                self.calls += 1
                if self.calls == 1:
                    self.pid = db.scalar(text("SELECT pg_backend_pid()"))
                    self.reached.set()
                    assert self.resume.wait(WAIT)
            return real_audit(db, **kwargs)

        monkeypatch.setattr(organizations, "audit", held)


def _run(target, result, key):
    def body():
        try:
            result[key] = target()
        except Exception as exc:  # reported by the assertions, never swallowed
            result[key + "_error"] = repr(exc)
    thread = threading.Thread(target=body)
    thread.start()
    return thread


def _deadlocks(engine):
    with engine.connect() as conn:
        return conn.scalar(text(
            "SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()"))


def _audits(engine, action):
    with engine.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM audit_log WHERE action = :a"),
                           {"a": action})


def _invite(c, token, org, email, role):
    return c.post(f"/v1/organizations/{org}/members", json={"email": email, "role": role},
                  headers=auth(token))


# --- N-07: the accept lock is exclusive ----------------------------------------------------


@pytest.mark.parametrize("role", ["ADMIN", "AGENT"])
def test_two_accepts_of_one_invitation_are_serialised_before_either_reads_it(
    pg_client, pg_migrated_engine, monkeypatch, role
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, role)
    before = _row(engine, ctx["org"], ctx["invitee_id"])
    deadlocks = _deadlocks(engine)
    hold = _HoldFirst(monkeypatch, "organization.member_joined")
    result: dict = {}
    first = _run(lambda: _accept(c, ctx), result, "first")
    second = None
    try:
        assert hold.reached.wait(WAIT), "the first accept never reached its write"
        second = _run(lambda: _accept(c, ctx), result, "second")
        assert _blocked_on(engine, "organization_memberships", hold.pid), \
            "the second accept did not wait for the first"
        # Waiting BEFORE it could act: it has not read the row as INVITED and
        # gone on to its own write (a shared lock would let it).
        assert hold.calls == 1, "the second accept acted on the row while the first held it"
    finally:
        hold.resume.set()
        first.join(WAIT)
        if second is not None:
            second.join(WAIT)
    assert "first_error" not in result and "second_error" not in result, result
    assert (result["first"].status_code, result["first"].json()["status"]) == (200, "ACTIVE")
    assert result["second"].status_code == 404, result["second"].text
    status, kept_role, revoked, version = _row(engine, ctx["org"], ctx["invitee_id"])
    assert (status, kept_role, revoked, version) == ("ACTIVE", role, False, before[3] + 1)
    assert _audits(engine, "organization.member_joined") == 1
    assert _deadlocks(engine) == deadlocks


# --- N-09: an invitation never demotes a member ----------------------------------------------


def test_a_reinvitation_racing_a_join_cannot_demote_the_new_member(
    pg_client, pg_migrated_engine, monkeypatch
):
    """REVOKED member; a second manager's re-invitation (ADMIN) is held inside
    its transaction. The owner re-invites (AGENT) and the invitee accepts
    meanwhile. Both must wait for the held one; whatever order they then run
    in, the member ends ACTIVE — never back to INVITED."""
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, "AGENT", slug="reinvite-race")
    assert _accept(c, ctx).status_code == 200
    assert c.post(f"/v1/organizations/{ctx['org']}/members/{ctx['invitee_id']}/revoke",
                  headers=auth(ctx["boss"])).status_code == 200
    admin2 = _join(c, ctx["boss"], ctx["org"], "admin2@reinvite.example", "ADMIN")
    email = "invitee@accept.example"

    hold = _HoldFirst(monkeypatch, "organization.member_invited")
    result: dict = {}
    held = _run(lambda: _invite(c, admin2, ctx["org"], email, "ADMIN"), result, "admin2")
    others = []
    try:
        assert hold.reached.wait(WAIT), "the held re-invitation never reached its write"
        others.append(_run(lambda: _invite(c, ctx["boss"], ctx["org"], email, "AGENT"),
                           result, "boss"))
        assert _blocked_on(engine, "organization_memberships", hold.pid), \
            "the second re-invitation did not wait for the first"
        others.append(_run(lambda: _accept(c, ctx), result, "accept"))
    finally:
        hold.resume.set()
        held.join(WAIT)
        for t in others:
            t.join(WAIT)
    assert not [k for k in result if k.endswith("_error")], result
    assert result["admin2"].status_code == 202 and result["boss"].status_code == 202
    # The accept waited behind the held re-invitation, so it found INVITED.
    assert result["accept"].status_code == 200, result["accept"].text
    status, role, revoked, _ = _row(engine, ctx["org"], ctx["invitee_id"])
    assert (status, role, revoked) == ("ACTIVE", "ADMIN", False)  # never demoted to INVITED
    orgs = c.get("/v1/organizations", headers=auth(ctx["invitee"])).json()
    assert [o["id"] for o in orgs] == [ctx["org"]]


@pytest.mark.parametrize("state", ["ACTIVE", "INVITED"])
def test_an_invitation_leaves_an_active_member_or_pending_invitation_untouched(
    pg_client, pg_migrated_engine, state
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, "AGENT", slug=f"untouched-{state.lower()}")
    if state == "ACTIVE":
        assert _accept(c, ctx).status_code == 200
    before = _row(engine, ctx["org"], ctx["invitee_id"])
    assert _invite(c, ctx["boss"], ctx["org"], "invitee@accept.example", "ADMIN").status_code \
        == 202
    assert _row(engine, ctx["org"], ctx["invitee_id"]) == before  # status, role, version


def test_a_revoked_member_can_be_invited_again_explicitly(pg_client, pg_migrated_engine):
    """Under UNIQUE(organization, user) re-invitation of a REVOKED row is the
    only way back in; it is an explicit manager action, not a reactivation."""
    c, engine = pg_client, pg_migrated_engine
    ctx = _invited(c, "AGENT", slug="revoked-again")
    assert c.post(f"/v1/organizations/{ctx['org']}/members/{ctx['invitee_id']}/revoke",
                  headers=auth(ctx["boss"])).status_code == 200
    before = _row(engine, ctx["org"], ctx["invitee_id"])
    assert _invite(c, ctx["boss"], ctx["org"], "invitee@accept.example", "ADMIN").status_code \
        == 202
    status, role, revoked, version = _row(engine, ctx["org"], ctx["invitee_id"])
    assert (status, role, revoked, version) == ("INVITED", "ADMIN", False, before[3] + 1)


# --- N-10: concurrent first invitations ------------------------------------------------------


def test_two_first_invitations_of_one_person_never_fail_with_500(
    pg_client, pg_migrated_engine, monkeypatch
):
    c, engine = pg_client, pg_migrated_engine
    boss = register_and_login(c, "boss@first-invite.example", "host")
    org = c.post("/v1/organizations", json={
        "display_name": "First", "slug": "first-invite", "legal_name": "First Sp. z o.o."},
        headers=auth(boss)).json()["id"]
    admin2 = _join(c, boss, org, "admin2@first-invite.example", "ADMIN")
    register_and_login(c, "new@first-invite.example", "host")

    hold = _HoldFirst(monkeypatch, "organization.member_invited")
    result: dict = {}
    first = _run(lambda: _invite(c, admin2, org, "new@first-invite.example", "ADMIN"),
                 result, "first")
    second = None
    try:
        assert hold.reached.wait(WAIT), "the first invitation never reached its write"
        second = _run(lambda: _invite(c, boss, org, "new@first-invite.example", "AGENT"),
                      result, "second")
        # Its INSERT waits on the first's uncommitted unique-index entry.
        assert _blocked_on(engine, "organization_memberships", hold.pid), \
            "the second invitation did not wait for the first"
    finally:
        hold.resume.set()
        first.join(WAIT)
        if second is not None:
            second.join(WAIT)
    assert not [k for k in result if k.endswith("_error")], result
    assert (result["first"].status_code, result["second"].status_code) == (202, 202)
    assert result["first"].json() == result["second"].json()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT m.status, m.role FROM organization_memberships m JOIN users u "
            "ON u.id = m.user_id WHERE u.email = 'new@first-invite.example'")).all()
    assert [tuple(r) for r in rows] == [("INVITED", "ADMIN")]  # the winner's row decides


@pytest.mark.parametrize("end", ["commit", "rollback"])
def test_a_first_invitation_racing_an_uncommitted_insert(pg_client, pg_migrated_engine, end):
    """Independent of the API on the other side: a raw INSERT of the same
    membership is held; the API invitation waits on it, then either decides on
    the committed row or inserts its own — 202 either way, one row."""
    c, engine = pg_client, pg_migrated_engine
    boss = register_and_login(c, "boss@raw-invite.example", "host")
    org = c.post("/v1/organizations", json={
        "display_name": "Raw", "slug": "raw-invite", "legal_name": "Raw Sp. z o.o."},
        headers=auth(boss)).json()["id"]
    newbie = register_and_login(c, "new@raw-invite.example", "host")
    newbie_id = c.get("/v1/me", headers=auth(newbie)).json()["id"]
    conn = engine.connect()
    tx = conn.begin()
    conn.execute(text(
        "INSERT INTO organization_memberships (id, organization_id, user_id, role, status, "
        "created_at, updated_at, version) VALUES (gen_random_uuid()::text, :o, :u, 'VIEWER', "
        "'INVITED', now(), now(), 1)"), {"o": org, "u": newbie_id})
    raw_pid = conn.scalar(text("SELECT pg_backend_pid()"))
    result: dict = {}
    api = _run(lambda: _invite(c, boss, org, "new@raw-invite.example", "AGENT"), result, "api")
    try:
        assert _blocked_on(engine, "organization_memberships", raw_pid)
    finally:
        (tx.commit if end == "commit" else tx.rollback)()
        conn.close()
        api.join(WAIT)
    assert "api_error" not in result, result["api_error"]
    assert result["api"].status_code == 202
    with engine.connect() as c2:
        rows = c2.execute(text("SELECT status, role FROM organization_memberships "
                               "WHERE organization_id = :o AND user_id = :u"),
                          {"o": org, "u": newbie_id}).all()
    assert [tuple(r) for r in rows] == [("INVITED", "VIEWER" if end == "commit" else "AGENT")]
