"""The protected decision rests only on rows its locks actually returned
(TASK-007 N-05, N-06, N-08; TASK-008) — real PostgreSQL.

TASK-006 decided through the proof *keys* read before the locks. TASK-007
reproduced the gap that left: a proof row deleted while its FOR SHARE waited
and re-inserted under the same key. PostgreSQL READ COMMITTED skips the
deleted version, the new version is not in the locking statement's snapshot,
so nothing is locked — yet the key still matched, and the publication went
public on a row nobody held; deleting it again did not wait.

Now `_lock_proof` returns the rows its statements returned, and the decision
is evaluated through those alone. A replaced row fails the attempt like any
other lost link: 409 with Retry-After (a valid chain exists now, unlocked),
and a new request reads, locks and uses it.

Each replacement is one held transaction (DELETE + INSERT of the same row,
uncommitted); the publication is observed waiting on that transaction's
backend in pg_stat_activity, then the transaction commits.
"""

import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.properties import authority
from app.modules.properties.models import PropertyAuthority, PropertyAuthorityScope
from tests.conftest import auth
from tests.test_organizations import _mandate
from tests.test_publication_authority_race_pg import (
    _blocked_on,
    _org_agent,
    _representative,
    _status,
)
from tests.test_publication_race_pg import _draft_listing, _pause_publication_at

WAIT = 15


class _Held:
    """A raw transaction that has run `stmts` and not committed."""

    def __init__(self, engine, *stmts):
        self.conn = engine.connect()
        self.tx = self.conn.begin()
        for sql, params in stmts:
            self.conn.execute(text(sql), params)
        self.pid = self.conn.scalar(text("SELECT pg_backend_pid()"))

    def commit(self):
        self.tx.commit()
        self.conn.close()

    def release(self):
        if self.tx.is_active:
            self.tx.rollback()
        self.conn.close()


def _one(engine, sql, **params):
    with engine.connect() as conn:
        return conn.scalar(text(sql), params)


def _row(engine, table, where, params):
    with engine.connect() as conn:
        return dict(conn.execute(text(f"SELECT * FROM {table} WHERE {where}"), params)
                    .mappings().one())


def _replace(table, where, params, row):
    """DELETE the row and INSERT it again, same key and values."""
    cols = ", ".join(row)
    return [(f"DELETE FROM {table} WHERE {where}", params),
            (f"INSERT INTO {table} ({cols}) VALUES ({', '.join(':' + c for c in row)})", row)]


def _personal(c, engine):
    owner, prop, offer = _draft_listing(c)
    aid = _one(engine, "SELECT id FROM property_authorities WHERE property_id = :p", p=prop)
    party = _one(engine, "SELECT holder_legal_party_id FROM property_authorities WHERE id = :a",
                 a=aid)
    return {"owner": owner, "publisher": owner, "prop": prop, "offer": offer,
            "authority": aid, "party": party}


def _org(c, engine):
    ctx = _org_agent(c)
    ctx["org_party"] = _one(engine, "SELECT legal_party_id FROM organization_legal_parties "
                                    "WHERE organization_id = :o", o=ctx["org"])
    ctx["membership"] = _one(engine, "SELECT id FROM organization_memberships "
                                     "WHERE organization_id = :o AND user_id = :u",
                             o=ctx["org"], u=ctx["agent_id"])
    return ctx


# kind -> (context, table, WHERE for the one proof row, its key from ctx)
REPLACED = {
    "person_link": (_personal, "person_legal_parties", "legal_party_id = :k", "party"),
    "org_link": (_org, "organization_legal_parties", "legal_party_id = :k", "org_party"),
    "membership": (_org, "organization_memberships", "id = :k", "membership"),
    "mandate_scope": (lambda c, e: _representative(c), "representation_mandate_scopes",
                      "mandate_id = :k AND scope = 'PUBLISH_LISTING'", "mandate"),
    "authority_scope": (_personal, "property_authority_scopes",
                        "property_authority_id = :k AND scope = 'PUBLISH_LISTING'", "authority"),
}


def _publish_async(c, ctx, result, key="publish", order=None):
    def run():
        try:
            result[key] = c.post(f"/v1/classifieds/{ctx['offer']}/publish",
                                 headers=auth(ctx["publisher"]))
        except Exception as exc:  # surfaced as an assertion below, never swallowed
            result[key + "_error"] = repr(exc)
        if order is not None:
            order.append("publish")
    thread = threading.Thread(target=run)
    thread.start()
    return thread


def _settle(thread, decided):
    """Until the publication finished, or passed its decision and stopped at
    the gate (which only the defect reaches for a replaced row)."""
    deadline = time.monotonic() + WAIT
    while thread.is_alive() and not decided.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)


def _under_hold(c, engine, monkeypatch, ctx, table, *stmts):
    """Publish while `stmts` are held in another transaction on a proof row of
    `table`: the publication must wait on that transaction; then it commits.
    Returns the publication's response, or the error it raised."""
    decided, resume = _pause_publication_at(monkeypatch, "protected")
    held = _Held(engine, *stmts)
    result: dict = {}
    publisher = None
    try:
        publisher = _publish_async(c, ctx, result)
        assert _blocked_on(engine, table, held.pid), \
            f"publication did not wait on the transaction holding {table}"
        held.commit()
        _settle(publisher, decided)
        result["passed_decision"] = decided.is_set()
    finally:
        held.release()
        resume.set()
        if publisher is not None:
            publisher.join(WAIT)
    assert "publish_error" not in result, result["publish_error"]
    return result["publish"], result["passed_decision"]


# --- N-05: a replaced proof row cannot carry the decision -------------------------------


@pytest.mark.parametrize("kind", list(REPLACED))
def test_a_proof_row_replaced_while_its_lock_waits_does_not_carry_the_publication(
    pg_client, pg_migrated_engine, monkeypatch, kind
):
    c, engine = pg_client, pg_migrated_engine
    build, table, where, key = REPLACED[kind]
    ctx = build(c, engine)
    params = {"k": ctx[key]}
    row = _row(engine, table, where, params)

    response, passed = _under_hold(c, engine, monkeypatch, ctx, table,
                                   *_replace(table, where, params, row))

    # Forbidden: the replacement, locked by nobody, carries a 200.
    assert not passed, f"decision passed through the unlocked replacement {table} row"
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == authority.AUTHORITY_CHANGED
    assert response.headers.get("Retry-After") == "0"
    assert _status(engine, ctx["offer"]) == "draft"
    assert c.get(f"/v1/classifieds/{ctx['offer']}").status_code == 404


@pytest.mark.parametrize("kind", list(REPLACED))
def test_the_next_attempt_locks_the_replacement_and_publishes(
    pg_client, pg_migrated_engine, monkeypatch, kind
):
    """Refusing the racing attempt is not refusing the row: a new request
    reads a proof containing it, locks it (a DELETE now waits for the
    publication), and publishes."""
    c, engine = pg_client, pg_migrated_engine
    build, table, where, key = REPLACED[kind]
    ctx = build(c, engine)
    params = {"k": ctx[key]}
    row = _row(engine, table, where, params)
    first, _ = _under_hold(c, engine, monkeypatch, ctx, table,
                           *_replace(table, where, params, row))
    assert first.status_code == 409, first.text

    decided, resume = _pause_publication_at(monkeypatch, "protected")
    result: dict = {}
    order: list[str] = []

    def delete_again():
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table} WHERE {where}"), params)
        order.append("delete")

    publisher = _publish_async(c, ctx, result, order=order)
    loser = threading.Thread(target=delete_again)
    try:
        assert decided.wait(WAIT), "the new attempt did not pass its decision"
        loser.start()
        assert _blocked_on(engine, table, decided.pid), \
            f"the {table} row the new attempt rests on is not locked"
    finally:
        resume.set()
        publisher.join(WAIT)
        if loser.ident:
            loser.join(WAIT)
    assert "publish_error" not in result, result.get("publish_error")
    assert result["publish"].status_code == 200, result["publish"].text
    assert order == ["publish", "delete"], order
    assert _status(engine, ctx["offer"]) == "active"


# --- N-06: each restriction of the protected evaluation matters --------------------------
# The replacement tests above fail if the decision stops using the rows the
# locks returned, or drops the personal-link, organisation-link, membership,
# mandate-scope or authority-scope restriction (each kind replaces exactly the
# row that restriction guards). The two below gain a NEW row of the same
# principal / holder while the lock waits — the TASK-007 load-bearing shapes.


def test_a_second_mandate_from_the_same_principal_gained_during_the_wait_does_not_count(
    pg_client, pg_migrated_engine, monkeypatch
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _representative(c)
    decided, resume = _pause_publication_at(monkeypatch, "protected")
    held = _Held(engine, ("UPDATE representation_mandates SET status = 'REVOKED', "
                          "revoked_at = now() WHERE id = :m", {"m": ctx["mandate"]}))
    result: dict = {}
    publisher = None
    try:
        publisher = _publish_async(c, ctx, result)
        assert _blocked_on(engine, "representation_mandates", held.pid)
        # Same principal grants a NEW mandate while the publication waits.
        assert _mandate(c, ctx["owner"], "rep@race.example", ["PUBLISH_LISTING"]).status_code \
            == 202
        held.commit()
        _settle(publisher, decided)
        assert not decided.is_set(), "decision passed through the unlocked second mandate"
    finally:
        held.release()
        resume.set()
        if publisher is not None:
            publisher.join(WAIT)
    assert result["publish"].status_code == 409, result["publish"].text
    assert _status(engine, ctx["offer"]) == "draft"
    again = c.post(f"/v1/classifieds/{ctx['offer']}/publish", headers=auth(ctx["publisher"]))
    assert again.status_code == 200, again.text  # through the second mandate, now locked


def test_a_second_authority_of_the_same_holder_gained_during_the_wait_does_not_count(
    pg_client, pg_migrated_engine, monkeypatch
):
    """A NEW authority row cannot appear during the wait at all: its INSERT
    key-share-locks the property row, which the publication holds FOR UPDATE.
    What can appear is an existing UNVERIFIED right of the same holder being
    verified — not in the (VERIFIED) proof, so not locked."""
    c, engine = pg_client, pg_migrated_engine
    ctx = _personal(c, engine)
    with Session(engine) as db:  # the same holder's second right, not yet verified
        first = db.get(PropertyAuthority, ctx["authority"])
        second = PropertyAuthority(
            property_id=ctx["prop"], holder_legal_party_id=ctx["party"],
            authority_type="CO_OWNER", status="ACTIVE", verification_state="UNVERIFIED",
            effective_from=first.effective_from, created_by_user_id=first.created_by_user_id)
        db.add(second)
        db.flush()
        db.add(PropertyAuthorityScope(property_authority_id=second.id, scope="PUBLISH_LISTING"))
        db.commit()
        second_id = second.id
    decided, resume = _pause_publication_at(monkeypatch, "protected")
    held = _Held(engine, ("UPDATE property_authorities SET verification_state = 'UNVERIFIED' "
                          "WHERE id = :a", {"a": ctx["authority"]}))
    result: dict = {}
    publisher = None
    try:
        publisher = _publish_async(c, ctx, result)
        assert _blocked_on(engine, "property_authorities", held.pid)
        with engine.begin() as conn:  # verified while the publication waits; does not wait
            conn.execute(text("UPDATE property_authorities SET verification_state = 'VERIFIED' "
                              "WHERE id = :a"), {"a": second_id})
        held.commit()
        _settle(publisher, decided)
        assert not decided.is_set(), "decision passed through the unlocked second authority"
    finally:
        held.release()
        resume.set()
        if publisher is not None:
            publisher.join(WAIT)
    assert result["publish"].status_code == 409, result["publish"].text
    assert _status(engine, ctx["offer"]) == "draft"


# --- N-08: one interleaving, four outcomes -------------------------------------------------
# The same path through the protected decision — the publication waits on a
# held change to one of its proof rows, the change commits, the decision is
# made — distinguishes every refusal from success.


OUTCOMES = {
    # verification lost between the pre-check and the decision: still held, not
    # VERIFIED — the final 403 of authorize_for_mutation (never reached before)
    "unverified": ("property_authorities",
                   "UPDATE property_authorities SET verification_state = 'UNVERIFIED' "
                   "WHERE id = :a", 403, "draft"),
    # the only link cut: nothing held any more
    "unlinked": ("person_legal_parties",
                 "UPDATE person_legal_parties SET linked_user_id = NULL "
                 "WHERE legal_party_id = :p", 404, "draft"),
    # the link replaced under the same key: valid now, but not locked
    "replaced": ("person_legal_parties", None, 409, "draft"),
    # a change that leaves the chain valid: the lock waited, the decision stands
    "untouched": ("property_authorities",
                  "UPDATE property_authorities SET version = version + 1 WHERE id = :a",
                  200, "active"),
}


@pytest.mark.parametrize("change", list(OUTCOMES))
def test_the_protected_decision_distinguishes_403_404_409_and_200(
    pg_client, pg_migrated_engine, monkeypatch, change
):
    c, engine = pg_client, pg_migrated_engine
    ctx = _personal(c, engine)
    table, sql, expected, listing = OUTCOMES[change]
    params = {"a": ctx["authority"], "p": ctx["party"]}
    if sql is None:
        where, key = "legal_party_id = :k", {"k": ctx["party"]}
        stmts = _replace(table, where, key, _row(engine, table, where, key))
    else:
        stmts = [(sql, params)]
    response, _ = _under_hold(c, engine, monkeypatch, ctx, table, *stmts)
    assert response.status_code == expected, (change, response.text)
    assert _status(engine, ctx["offer"]) == listing
    if expected == 409:
        assert response.headers.get("Retry-After") == "0"
    else:
        assert "Retry-After" not in response.headers


def test_retry_after_marks_only_the_authority_change_conflict(pg_client, pg_migrated_engine):
    """The other publish 409 (listing no longer publishable) carries no
    Retry-After, so a client can tell retryable from final."""
    c, engine = pg_client, pg_migrated_engine
    ctx = _personal(c, engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE classified_offers SET status = 'archived' WHERE id = :o"),
                     {"o": ctx["offer"]})
    response = c.post(f"/v1/classifieds/{ctx['offer']}/publish", headers=auth(ctx["publisher"]))
    assert response.status_code == 409
    assert "Retry-After" not in response.headers
    assert response.json()["detail"] != authority.AUTHORITY_CHANGED
