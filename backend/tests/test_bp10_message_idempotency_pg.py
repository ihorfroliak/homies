"""BP-10 (D-108) on PostgreSQL: idempotent sends under real locks.

The PostgreSQL half of the BP-10 proof obligations, on the migration-built
schema (SQLite has no advisory locks and ignores row locks, so it proves none
of this):

* P1/P2b — the unique backstop `uq_messages_sender_client_message` waits for
  an in-flight writer (bounded by lock_timeout) and then refuses by name;
* P5 — the start's users-row lock does not block the sender's own appends,
  the saved-listing account lock (FOR UPDATE) does;
* P6/INV-4/INV-10 — a retry waits on the send's advisory lock, then sees the
  committed message in its next statement; the wait is bounded (503);
* P8 — the two-int key space never meets the migration job's bigint lock;
* T4–T8 — same-key starts and appends, different keys, cross-target reuse;
* T10–T12 — PR-003: COMMIT outcome unknown, a definite rollback;
* T22 — the load-bearing three-party interleaving: without the advisory lock
  a retry of a delivered send is refused RECONTACT_BLOCKED;
* T27/T28 — the lock survives the start's savepoint branch, READ COMMITTED,
  signed int4 keys.

Waits are proven with pg_blocking_pids (`_blocked_on`); a duration is asserted
only where the bound itself is the claim (lock_timeout). Test-side sessions
that must outwait a paused transaction get a longer lock budget (`_patient`),
so a loaded host cannot turn a proven wait into a 55P03.
"""

import time
import uuid
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.modules.engagement import router as conversations
from tests.conftest import TEST_DATABASE_URL, auth
from tests.test_engagement_safety_pg import _paused, _restrict, _setup, _tenant, _wait_for
from tests.test_publication_authority_race_pg import _blocked_on
from tests.test_reports_moderation_pg import (
    _account,
    _deadlocks,
    _listing,
    _pid,
    _run,
    _scalar,
    _session,
    _user,
)

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

LOCK_SQL = text("SELECT pg_advisory_xact_lock(CAST(:cls AS integer), CAST(:obj AS integer))")


def _msg(key, body):
    return conversations.MessageIn(client_message_id=key, body=body)


def _append(db, conv, email, key, body):
    return conversations.send_message(conv, _msg(key, body), user=_user(db, email), db=db)


def _start(db, offer, email, key, body):
    return conversations.start_conversation(offer, _msg(key, body), user=_user(db, email), db=db)


def _patient(db):
    """Outwait the paused transaction under test: the application's 2 s
    lock_timeout is the production bound, not what these interleavings measure
    (both stay under the 7 s client deadline)."""
    db.execute(text("SET LOCAL lock_timeout = '6s'"))
    db.execute(text("SET LOCAL statement_timeout = '6500ms'"))


def _in_session(engine, fn):
    with _session(engine) as db:
        _patient(db)
        return fn(db)


def _idem(route, outcome) -> float:
    from prometheus_client import REGISTRY

    value = REGISTRY.get_sample_value("homies_message_idempotency_total",
                                      {"route": route, "outcome": outcome})
    return 0.0 if value is None else value


def _keyed(engine, key) -> int:
    return _scalar(engine, "SELECT count(*) FROM messages WHERE client_message_id = :k", k=key)


def _user_id(engine, email) -> str:
    return _scalar(engine, "SELECT id FROM users WHERE email = :e", e=email)


def _hold_send_lock(engine, email, key):
    """A transaction holding the BP-10 lock of (sender, key), as a send does."""
    holder = _session(engine)
    holder.execute(LOCK_SQL, {"cls": conversations.SEND_LOCK_CLASS,
                              "obj": conversations.send_lock_key(_user_id(engine, email), key)})
    return holder


def _raw_keyed_insert(db, conv, sender_id, key, body="raw"):
    db.execute(text(
        "INSERT INTO messages (id, conversation_id, sender_user_id, message_type, body, "
        "created_at, client_message_id) VALUES (:id, :c, :s, 'USER', :b, now(), :k)"),
        {"id": str(uuid4()), "c": conv, "s": sender_id, "b": body, "k": key})


# --- P1 / P2b / P5: the unique backstop and lock compatibility on the real schema ----------


def test_p1_a_second_writer_of_one_key_waits_and_is_bounded_by_lock_timeout(pg_client,
                                                                          pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    sender, key = _user_id(eng, s["tenant"]), str(uuid4())
    a, b = _session(eng), _session(eng)
    try:
        _raw_keyed_insert(a, s["conv"], sender, key)  # uncommitted index entry
        started = time.monotonic()
        with pytest.raises(OperationalError) as caught:
            _raw_keyed_insert(b, s["conv"], sender, key)
        took = time.monotonic() - started
        assert caught.value.orig.sqlstate == "55P03"  # lock_not_available → PR-003 503
        assert 1.5 < took < 4.0, took  # the application's 2 s lock_timeout
    finally:
        a.rollback(), b.rollback(), a.close(), b.close()


def test_p2b_after_the_winner_commits_the_loser_is_refused_by_name(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    sender, key = _user_id(eng, s["tenant"]), str(uuid4())
    a = _session(eng)
    result: dict = {}
    try:
        _raw_keyed_insert(a, s["conv"], sender, key)

        def loser():
            with _session(eng) as b:
                _raw_keyed_insert(b, s["conv"], sender, key)
                b.commit()
        t = _run(result, "b", loser)
        assert _blocked_on(eng, "INSERT INTO messages", _pid(a))
        a.commit()
        t.join(15)
    finally:
        a.close()
    assert isinstance(result["b"], IntegrityError)
    assert result["b"].orig.sqlstate == "23505"
    assert result["b"].orig.diag.constraint_name == "uq_messages_sender_client_message"
    assert _keyed(eng, key) == 1


def test_p5_a_start_does_not_block_the_senders_appends_but_an_account_lock_does(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    sender = _user_id(eng, s["tenant"])
    holder = _session(eng)
    try:  # the start's coordination lock (FOR NO KEY UPDATE): FK checks pass it at once
        holder.execute(text("SELECT id FROM users WHERE id = :u FOR NO KEY UPDATE"),
                       {"u": sender})
        # not blocked: the default 2 s lock_timeout would have made this a 503
        with _session(eng) as db:
            assert _append(db, s["conv"], s["tenant"], uuid4(), "a").body == "a"
    finally:
        holder.rollback(), holder.close()
    holder, result = _session(eng), {}
    try:  # saved/_lock_account (FOR UPDATE): the message INSERT's FK check waits for it
        holder.execute(text("SELECT id FROM users WHERE id = :u FOR UPDATE"), {"u": sender})
        t = _run(result, "send", lambda: _in_session(
            eng, lambda db: _append(db, s["conv"], s["tenant"], uuid4(), "b")))
        assert _blocked_on(eng, "messages", _pid(holder))
        holder.rollback()
        t.join(15)
    finally:
        holder.close()
    assert result["send"].body == "b"


# --- P6 / INV-4 / INV-10 / T5: the send lock -----------------------------------------------


def test_t5_a_concurrent_same_key_append_waits_then_replays_the_committed_message(
        pg_client, pg_migrated_engine):
    """P6b: the retry waits on the advisory lock — not on a row — and its
    lookup, a separate statement under READ COMMITTED, sees the commit."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = uuid4()
    metric = {o: _idem("append", o) for o in ("replay", "race_recovered")}
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t1 = _run(result, "first", lambda: _append(p, s["conv"], s["tenant"], key, "Hej!"))
        _wait_for(reached)
        t2 = _run(result, "retry", lambda: _in_session(
            eng, lambda db: _append(db, s["conv"], s["tenant"], key, "Hej!")))
        assert _blocked_on(eng, "pg_advisory_xact_lock", _pid(p))
        gate.set()
        t1.join(15), t2.join(15)
    finally:
        gate.set()
        p.close()
    first, retry = result["first"], result["retry"]
    assert first.id == retry.id
    assert first.created_at == retry.created_at  # PostgreSQL: the same instant, exactly
    assert _keyed(eng, str(key)) == 1
    # resolved by the lookup after the lock, not by losing a unique-index race
    assert _idem("append", "replay") == metric["replay"] + 1
    assert _idem("append", "race_recovered") == metric["race_recovered"]


def test_inv4_a_rolled_back_send_leaves_the_key_free_for_its_retry(pg_client,
                                                                   pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = str(uuid4())
    holder = _hold_send_lock(eng, s["tenant"], key)
    _raw_keyed_insert(holder, s["conv"], _user_id(eng, s["tenant"]), key, "never committed")
    result: dict = {}
    try:
        t = _run(result, "retry", lambda: _in_session(eng, lambda db: (
            _append(db, s["conv"], s["tenant"], key, "Hej"), db.commit())[0]))
        assert _blocked_on(eng, "pg_advisory_xact_lock", _pid(holder))
        holder.rollback()
        t.join(15)
    finally:
        holder.close()
    assert result["retry"].body == "Hej"
    assert _scalar(eng, "SELECT body FROM messages WHERE client_message_id = :k", k=key) == "Hej"


def test_inv10_p6a_the_wait_for_a_send_lock_is_bounded_then_the_retry_succeeds(
        pg_client, pg_migrated_engine):
    """A send stuck mid-transaction holds its lock; a retry gets PR-003's 503
    (lock_timeout) within the deadline, and succeeds once the lock is gone."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = str(uuid4())
    holder = _hold_send_lock(eng, s["tenant"], key)
    try:
        started = time.monotonic()
        stuck = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                               json={"body": "Hej", "client_message_id": key},
                               headers=auth(s["tenant_token"]))
        took = time.monotonic() - started
    finally:
        holder.rollback(), holder.close()
    assert stuck.status_code == 503 and stuck.headers["Retry-After"] == "5", stuck.text
    assert 1.5 < took < 4.0, took
    assert _keyed(eng, key) == 0
    again = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                           json={"body": "Hej", "client_message_id": key},
                           headers=auth(s["tenant_token"]))
    assert again.status_code == 201 and _keyed(eng, key) == 1


def test_p8_the_send_lock_never_meets_the_migration_jobs_bigint_lock(pg_client,
                                                                     pg_migrated_engine):
    """The same 64 bits as a bigint key are a different lock (objsubid 1 vs 2)."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = str(uuid4())
    obj = conversations.send_lock_key(_user_id(eng, s["tenant"]), key)
    bits = (conversations.SEND_LOCK_CLASS << 32) | (obj & 0xFFFFFFFF)
    holder = _session(eng)
    try:
        holder.execute(text("SELECT pg_advisory_xact_lock(CAST(:k AS bigint))"), {"k": bits})
        sent = _in_session(eng, lambda db: (_append(db, s["conv"], s["tenant"], key, "x"),
                                            db.commit())[0])
        assert sent.body == "x"
        assert _scalar(eng, "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                            "AND objsubid = 1 AND granted") >= 1
    finally:
        holder.rollback(), holder.close()


# --- T4 / T6 / T7 / T8 ----------------------------------------------------------------------


def test_t4_concurrent_same_key_starts_make_one_thread_one_message_one_audit(
        pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _owner, offer = _listing(pg_client)
    email, _token = _tenant(pg_client)
    key = uuid4()
    metric = {o: _idem("start", o) for o in ("replay", "race_recovered")}
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t1 = _run(result, "first", lambda: _start(p, offer, email, key, "Dzień dobry"))
        _wait_for(reached)
        t2 = _run(result, "retry", lambda: _in_session(
            eng, lambda db: _start(db, offer, email, key, "Dzień dobry")))
        assert _blocked_on(eng, "pg_advisory_xact_lock", _pid(p))
        gate.set()
        t1.join(15), t2.join(15)
    finally:
        gate.set()
        p.close()
    first, retry = result["first"], result["retry"]
    assert first.conversation.id == retry.conversation.id
    assert [m.id for m in first.messages] == [m.id for m in retry.messages]
    conv = first.conversation.id
    assert _scalar(eng, "SELECT count(*) FROM conversations WHERE listing_id = :o", o=offer) == 1
    assert _keyed(eng, str(key)) == 1
    assert _scalar(eng, "SELECT count(*) FROM audit_log WHERE action = 'conversation.started' "
                        "AND entity_id = :c", c=conv) == 1
    assert _scalar(eng, "SELECT count(*) FROM conversation_participants "
                        "WHERE conversation_id = :c", c=conv) == 2
    assert _idem("start", "replay") == metric["replay"] + 1
    assert _idem("start", "race_recovered") == metric["race_recovered"]


def test_t6_different_keys_on_one_conversation_are_both_written(pg_client, pg_migrated_engine):
    """Different sends contend only where the domain does (the conversation row)."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t1 = _run(result, "a", lambda: _append(p, s["conv"], s["tenant"], uuid4(), "jeden"))
        _wait_for(reached)
        t2 = _run(result, "b", lambda: _in_session(eng, lambda db: (
            _append(db, s["conv"], s["tenant"], uuid4(), "dwa"), db.commit())[0]))
        assert _blocked_on(eng, "conversations", _pid(p))  # the row, not the send lock
        gate.set()
        t1.join(15), t2.join(15)
    finally:
        gate.set()
        p.close()
    assert result["a"].id != result["b"].id
    assert _scalar(eng, "SELECT count(*) FROM messages WHERE conversation_id = :c "
                        "AND body IN ('jeden', 'dwa')", c=s["conv"]) == 2


def test_t7_different_keys_racing_for_a_new_thread_share_it(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    _o, _owner, offer = _listing(pg_client)
    email, _token = _tenant(pg_client)
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t1 = _run(result, "a", lambda: _start(p, offer, email, uuid4(), "pierwsza"))
        _wait_for(reached)
        t2 = _run(result, "b", lambda: _in_session(eng, lambda db: _start(
            db, offer, email, uuid4(), "druga")))
        assert _blocked_on(eng, "users", _pid(p))  # the per-sender coordination row
        gate.set()
        t1.join(15), t2.join(15)
    finally:
        gate.set()
        p.close()
    assert result["a"].conversation.id == result["b"].conversation.id
    assert _scalar(eng, "SELECT count(*) FROM conversations WHERE listing_id = :o", o=offer) == 1
    assert _scalar(eng, "SELECT count(*) FROM messages m JOIN conversations c "
                        "ON c.id = m.conversation_id WHERE c.listing_id = :o "
                        "AND m.message_type = 'USER'", o=offer) == 2


def test_t8_one_key_sent_to_two_conversations_at_once_writes_one(pg_client, pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    _o, _owner, other_offer = _listing(pg_client)
    other = _in_session(eng, lambda db: (_start(db, other_offer, s["tenant"], uuid4(), "Hi"),
                                         db.commit())[0].conversation.id)
    key = uuid4()
    conflicts = _idem("append", "conflict")
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t1 = _run(result, "a", lambda: _append(p, s["conv"], s["tenant"], key, "ta sama"))
        _wait_for(reached)
        t2 = _run(result, "b", lambda: _in_session(
            eng, lambda db: _append(db, other, s["tenant"], key, "ta sama")))
        assert _blocked_on(eng, "pg_advisory_xact_lock", _pid(p))
        gate.set()
        t1.join(15), t2.join(15)
    finally:
        gate.set()
        p.close()
    assert result["a"].conversation_id == s["conv"]
    assert getattr(result["b"], "status_code", None) == 409
    assert result["b"].detail.startswith("IDEMPOTENCY_KEY_REUSED: ")
    assert _keyed(eng, str(key)) == 1
    assert _idem("append", "conflict") == conflicts + 1


# --- T10 / T11 / T12: PR-003 failure windows ------------------------------------------------


@pytest.mark.parametrize("branch", ["committed", "rolled_back"])
def test_t10_t12_a_send_whose_commit_outcome_is_unknown_is_retried_safely(
        pg_client, pg_migrated_engine, branch):
    """PR-003: the client deadline fires during COMMIT (503 commit_unknown).
    Whether the COMMIT applied or the backend died, the retry with the same
    key ends with exactly one message — the original, or its fresh write."""
    from sqlalchemy.engine import make_url

    from app.core import db as core_db
    from app.core.db_failures import unavailability_reason
    from tests.pg_fault_proxy import FreezableProxy
    from tests.test_db_deadlines_pg import DEADLINE_S, FAST, SLACK_S, _bounded

    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = uuid4()
    target = make_url(TEST_DATABASE_URL)
    proxy = FreezableProxy((target.host or "127.0.0.1", target.port or 5432), TEST_DATABASE_URL)
    pe = core_db.create_bounded_engine(proxy.url(), deadlines=FAST, pool_size=1, max_overflow=0)
    try:
        db = _session(pe)
        server_pid = _pid(db)
        proxy.freeze_on = b"COMMIT"
        outcome, _took = _bounded(lambda: _append(db, s["conv"], s["tenant"], key, "Hej"),
                                  DEADLINE_S + SLACK_S + 3)
        assert proxy.frozen_on_marker.is_set()
        assert unavailability_reason(outcome) == "commit_unknown", outcome
        if branch == "rolled_back":
            with eng.connect() as admin:
                admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": server_pid})
        proxy.resume()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _scalar(
                eng, "SELECT count(*) FROM pg_stat_activity WHERE pid = :p", p=server_pid):
            if branch == "committed" and _keyed(eng, str(key)) == 1:
                break
            time.sleep(0.05)
        # the abandoned COMMIT applied (committed) or never did (rolled_back)
        assert _keyed(eng, str(key)) == (1 if branch == "committed" else 0)
        replays = _idem("append", "replay")
        retry = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                               json={"body": "Hej", "client_message_id": str(key)},
                               headers=auth(s["tenant_token"]))
        assert retry.status_code == 201, retry.text
        assert _idem("append", "replay") == replays + (1 if branch == "committed" else 0)
        assert _keyed(eng, str(key)) == 1
        stored = _scalar(eng, "SELECT id FROM messages WHERE client_message_id = :k", k=str(key))
        assert retry.json()["id"] == stored
    finally:
        proxy.resume()
        proxy.stop()
        pe.dispose()


def test_t11_a_send_rolled_back_before_commit_leaves_its_key_unused(pg_client,
                                                                    pg_migrated_engine):
    """lock_timeout before COMMIT (a closure holding the conversation): 503,
    definitely not written; the same key then sends once."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    key = str(uuid4())
    holder = _session(eng)
    try:
        holder.execute(text("SELECT id FROM conversations WHERE id = :c FOR UPDATE"),
                       {"c": s["conv"]})
        stuck = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                               json={"body": "Hej", "client_message_id": key},
                               headers=auth(s["tenant_token"]))
    finally:
        holder.rollback(), holder.close()
    assert stuck.status_code == 503 and _keyed(eng, key) == 0
    sent = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                          json={"body": "Hej", "client_message_id": key},
                          headers=auth(s["tenant_token"]))
    assert sent.status_code == 201 and _keyed(eng, key) == 1


# --- T22: the load-bearing three-party interleaving -----------------------------------------


@pytest.mark.parametrize("retry_route", ["start", "append"])
@pytest.mark.parametrize("serialised", [True, False], ids=["with_send_lock", "without"])
def test_t22_a_retry_of_a_delivered_send_is_never_refused_because_a_closure_overtook_it(
        pg_client, pg_migrated_engine, monkeypatch, serialised, retry_route):
    """M2 C1. The original append(K) is in flight (holding the conversation);
    a FEATURE_RESTRICTED decision queues on the conversation; the client
    retries the same draft — through start(K) or append(K).

    With the send lock the retry waits for the original, finds its message
    and replays it: 201. Without it (the mutant) the retry's lookup runs
    before the original commits, it queues behind the closure, finds the
    thread CLOSED and is refused — RECONTACT_BLOCKED (start) or
    CONVERSATION_CLOSED (append) — for a message that was delivered.
    Two-party races cannot show this; the unique index alone does not
    prevent it."""
    if not serialised:
        monkeypatch.setattr(conversations, "_serialise_send", lambda db, user_id, key: None)
    eng = pg_migrated_engine
    s = _setup(pg_client)
    mod = _account(eng, role="admin")
    key = uuid4()
    deadlocks = _deadlocks(eng)
    p, gate, reached = _paused(eng)
    result: dict = {}
    try:
        t_send = _run(result, "send", lambda: _append(p, s["conv"], s["tenant"], key, "Hej!"))
        _wait_for(reached)

        def close():
            with _session(eng) as d:
                _patient(d)
                _restrict(d, s["conv"], mod)
                d.commit()
        t_close = _run(result, "close", close)
        assert _blocked_on(eng, "conversations", _pid(p))  # the closure queues first
        if retry_route == "start":
            def retry(db):
                return _start(db, s["offer"], s["tenant"], key, "Hej!")
        else:
            def retry(db):
                return _append(db, s["conv"], s["tenant"], key, "Hej!")
        t_retry = _run(result, "retry", lambda: _in_session(eng, retry))
        waits_on = "pg_advisory_xact_lock" if serialised else "conversations"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and _scalar(
                eng, "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                     "AND cardinality(pg_blocking_pids(pid)) > 0") < 2:
            time.sleep(0.05)
        assert _blocked_on(eng, waits_on)
        gate.set()
        for t in (t_send, t_close, t_retry):
            t.join(20)
    finally:
        gate.set()
        p.close()
    delivered = result["send"]
    assert _keyed(eng, str(key)) == 1 and result.get("close") is None  # closure committed
    assert _scalar(eng, "SELECT status FROM conversations WHERE id = :c", c=s["conv"]) == "CLOSED"
    retry = result["retry"]
    if serialised:
        assert not isinstance(retry, Exception), retry
        if retry_route == "start":
            assert [m.id for m in retry.messages] == [delivered.id]
            # the thread as it is when the replay reads it: the closure may or
            # may not have committed by then — either is the truth at that instant
            assert retry.conversation.status in ("ACTIVE", "CLOSED")
        else:
            assert retry.id == delivered.id
    else:
        assert getattr(retry, "status_code", None) == 409, retry
        refusal = "RECONTACT_BLOCKED" if retry_route == "start" else "CONVERSATION_CLOSED"
        assert retry.detail.startswith(refusal)
    assert _deadlocks(eng) == deadlocks


# --- T27 / T28 -------------------------------------------------------------------------------


def test_t27_the_send_lock_outlives_the_starts_savepoint_branch(pg_client, pg_migrated_engine,
                                                                monkeypatch):
    """The fallback branch (the thread insert lost on the partial unique
    index; the savepoint rolled back) still holds the send lock at COMMIT,
    under READ COMMITTED; and the lock refuses to be taken inside a savepoint."""
    eng = pg_migrated_engine
    s = _setup(pg_client)
    real_active = conversations._active_thread
    calls = {"n": 0}

    def miss_once(db, listing_id, requester_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_active(db, listing_id, requester_id)

    monkeypatch.setattr(conversations, "_active_thread", miss_once)
    seen: dict = {}
    db = _session(eng)

    @event.listens_for(db, "before_commit")
    def _inspect(session):
        seen["held"] = session.execute(text(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted "
            "AND pid = pg_backend_pid() AND classid = CAST(:cls AS oid)"),
            {"cls": conversations.SEND_LOCK_CLASS}).scalar()
        seen["isolation"] = session.execute(text("SHOW transaction_isolation")).scalar()

    try:
        out = _start(db, s["offer"], s["tenant"], uuid4(), "w savepoincie")
    finally:
        db.close()
    assert calls["n"] == 2  # the IntegrityError branch ran
    assert out.conversation.id == s["conv"]
    assert seen == {"held": 1, "isolation": "read committed"}
    with _session(eng) as nested:
        with pytest.raises(RuntimeError, match="top-level transaction"), nested.begin_nested():
            conversations._serialise_send(nested, "u", "k")


def _key_with_sign(user_id: str, negative: bool) -> str:
    for n in range(1, 10_000):
        key = str(uuid.UUID(int=n << 64 | n, version=4))
        if (conversations.send_lock_key(user_id, key) < 0) == negative:
            return key
    raise AssertionError("no key found")


def test_t28_signed_int4_keys_bind_for_both_signs_and_unsigned_would_not(pg_client,
                                                                         pg_migrated_engine):
    eng = pg_migrated_engine
    s = _setup(pg_client)
    user_id = _user_id(eng, s["tenant"])
    for negative in (True, False):
        key = _key_with_sign(user_id, negative)
        sent = pg_client.post(f"/v1/conversations/{s['conv']}/messages",
                              json={"body": f"znak {negative}", "client_message_id": key},
                              headers=auth(s["tenant_token"]))
        assert sent.status_code == 201, sent.text
    with eng.connect() as conn:
        for edge in (-(2 ** 31), 2 ** 31 - 1):
            conn.execute(LOCK_SQL, {"cls": conversations.SEND_LOCK_CLASS, "obj": edge})
        conn.rollback()
        unsigned = int.from_bytes((-1).to_bytes(4, "big", signed=True), "big")  # 2**32 - 1
        with pytest.raises(Exception) as caught:
            conn.execute(LOCK_SQL, {"cls": conversations.SEND_LOCK_CLASS, "obj": unsigned})
        assert getattr(caught.value, "orig", None) is not None
        assert caught.value.orig.sqlstate == "22003"  # integer out of range
        conn.rollback()


# --- FD-8 ---------------------------------------------------------------------------------


def test_fd8_a_postgres_error_never_renders_its_parameters(pg_client, pg_migrated_engine):
    """hide_parameters on the PostgreSQL engine: the SQLAlchemy error text
    carries no bound values (bodies, keys). SQLite is left as it was."""
    from app.core import db as core_db

    assert pg_migrated_engine.hide_parameters is True
    assert core_db.create_bounded_engine("sqlite://").hide_parameters is False
    eng = pg_migrated_engine
    s = _setup(pg_client)
    sender, key, secret = _user_id(eng, s["tenant"]), str(uuid4()), f"sekret-{uuid4().hex}"
    with _session(eng) as db:
        _raw_keyed_insert(db, s["conv"], sender, key, secret)
        db.commit()
    with _session(eng) as db, pytest.raises(IntegrityError) as caught:
        _raw_keyed_insert(db, s["conv"], sender, key, secret)
    rendered = str(caught.value)
    assert "SQL parameters hidden" in rendered
    assert secret not in rendered  # neither the statement part nor DETAIL (key only) has it
