"""BP-10 mutation harness — proves the idempotent-send tests bite (D-108).

Same rules and runner as task002_mutants.py: green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256 verified.
Usage from backend/ (the PostgreSQL tests DROP and recreate the schema of a
disposable test database):

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/bp10_mutants.py [MUTANT_ID ...]

The advisory-lock mutants (B04–B07) are killed by PostgreSQL evidence — the
three-party interleaving T22, the savepoint branch T27 — never by the unique
index, which still holds two-party races without the lock.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

ROUTER = "app/modules/engagement/router.py"
MODELS = "app/modules/engagement/models.py"
MIGRATION = "alembic/versions/11d778ab87a3_bp10_message_client_id.py"
DB = "app/core/db.py"
UNIT = "tests/test_bp10_message_idempotency.py"
PG = "tests/test_bp10_message_idempotency_pg.py"
T22 = PG + "::test_t22_a_retry_of_a_delivered_send_is_never_refused_because_a_closure_overtook_it"

START_SEND = ("    _serialise_send(db, user_id, key)\n"
              "    earlier = _keyed(db, user_id, key)\n"
              "    if earlier is not None:\n"
              "        return _replay_start(db, user_id, offer_id, body.body, earlier, \"replay\")\n")
APPEND_SEND = ("    _serialise_send(db, user_id, key)\n"
               "    earlier = _keyed(db, user_id, key)\n"
               "    if earlier is not None:\n"
               "        return _replay_append(conv_id, body.body, earlier, \"replay\")\n")
APPEND_LOCK = ("        locked = _lock(db, conv_id)\n"
               "        if locked is None or locked.status != \"ACTIVE\":\n"
               "            raise _closed()\n"
               "        message = _post(db, user, locked, side, body.body, key)\n")
GUARD = ("    if db.in_nested_transaction():\n"
         "        raise RuntimeError(\"the message-send lock belongs to the top-level transaction\")\n")

harness.MUTANTS = [
    {
        "id": "B01-unique-index-not-migrated",
        "invariant": "INV-1 at most one message per (sender, key): the database backstop",
        "file": MIGRATION,
        "old": "    op.create_index(\"uq_messages_sender_client_message\", \"messages\",\n"
               "                    [\"sender_user_id\", \"client_message_id\"], unique=True,\n"
               "                    postgresql_where=sa.text(KEYED), sqlite_where=sa.text(KEYED))\n",
        "new": "    pass\n",
        "tests": [PG + "::test_p2b_after_the_winner_commits_the_loser_is_refused_by_name"],
    },
    {
        "id": "B01b-unique-index-dropped-from-model",
        "invariant": "INV-1 backstop (ORM schema, SQLite suite): a lost race is caught",
        "file": MODELS,
        "old": "        Index(\"uq_messages_sender_client_message\", \"sender_user_id\", "
               "\"client_message_id\",\n              unique=True,\n",
        "new": "        Index(\"uq_messages_sender_client_message\", \"sender_user_id\", "
               "\"client_message_id\",\n              unique=False,\n",
        "tests": [UNIT + "::test_a_lost_unique_race_on_sqlite_is_answered_with_the_winner"],
    },
    {
        "id": "B02-key-not-stored",
        "invariant": "INV-1 every keyed send carries its key",
        "file": ROUTER,
        "old": "        client_message_id=client_message_id,\n",
        "new": "",
        "tests": [UNIT + "::test_t1_a_repeated_append_is_one_message_and_the_same_answer"],
    },
    {
        "id": "B03-key-not-scoped-by-sender",
        "invariant": "INV-7 actor isolation",
        "file": ROUTER,
        "old": "        select(Message).where(Message.sender_user_id == user_id,\n"
               "                              Message.client_message_id == client_message_id)\n",
        "new": "        select(Message).where(Message.client_message_id == client_message_id)\n",
        "tests": [UNIT + "::test_another_account_with_the_same_uuid_sends_its_own_message"],
    },
    {
        "id": "B04-no-send-lock-on-start",
        "invariant": "FD-2 / INV-3 / INV-4 start: no false refusal of a delivered send",
        "file": ROUTER,
        "old": START_SEND,
        "new": START_SEND.replace("    _serialise_send(db, user_id, key)\n", ""),
        "tests": [T22 + "[with_send_lock-start]"],
    },
    {
        "id": "B05-no-send-lock-on-append",
        "invariant": "FD-2 / INV-3 / INV-4 append: no false refusal of a delivered send",
        "file": ROUTER,
        "old": APPEND_SEND,
        "new": APPEND_SEND.replace("    _serialise_send(db, user_id, key)\n", ""),
        "tests": [T22 + "[with_send_lock-append]"],
    },
    {
        "id": "B06-send-lock-after-the-conversation-lock",
        "invariant": "lock order: the send lock precedes every row lock and refusal",
        "file": ROUTER,
        "old": APPEND_SEND,
        "new": APPEND_SEND.replace("    _serialise_send(db, user_id, key)\n", ""),
        "extra": [(APPEND_LOCK, APPEND_LOCK.replace(
            "        locked = _lock(db, conv_id)\n",
            "        locked = _lock(db, conv_id)\n        _serialise_send(db, user_id, key)\n"))],
        "tests": [T22 + "[with_send_lock-append]"],
    },
    {
        "id": "B06b-send-lock-after-the-users-lock-on-start",
        "invariant": "lock order on start: the send lock precedes the lookup's refusals",
        "file": ROUTER,
        "old": START_SEND,
        "new": START_SEND.replace("    _serialise_send(db, user_id, key)\n", ""),
        "extra": [("    db.execute(select(User.id).where(User.id == user.id)"
                   ".with_for_update(key_share=True))\n",
                   "    db.execute(select(User.id).where(User.id == user.id)"
                   ".with_for_update(key_share=True))\n    _serialise_send(db, user.id, key)\n")],
        "tests": [T22 + "[with_send_lock-start]"],
    },
    {
        "id": "B07-send-lock-inside-the-savepoint",
        "invariant": "T27: the lock is transaction-scoped, never savepoint-scoped",
        "file": ROUTER,
        "old": GUARD,
        "new": "",
        "extra": [(START_SEND, START_SEND.replace("    _serialise_send(db, user_id, key)\n", "")),
                  ("            with db.begin_nested():\n                db.add(conv)\n",
                   "            with db.begin_nested():\n"
                   "                _serialise_send(db, user.id, key)\n                db.add(conv)\n")],
        "tests": [PG + "::test_t27_the_send_lock_outlives_the_starts_savepoint_branch"],
    },
    {
        "id": "B07b-no-savepoint-guard",
        "invariant": "T27: taking the lock inside a savepoint is refused",
        "file": ROUTER,
        "old": GUARD,
        "new": "",
        "tests": [PG + "::test_t27_the_send_lock_outlives_the_starts_savepoint_branch"],
    },
    {
        "id": "B08-unsigned-lock-key",
        "invariant": "T28 the key always fits int4",
        "file": ROUTER,
        "old": "    return int.from_bytes(digest[:4], \"big\", signed=True)\n",
        "new": "    return int.from_bytes(digest[:4], \"big\", signed=False)\n",
        "tests": [UNIT + "::test_t28_the_lock_key_is_a_signed_int4_of_sender_and_key_only",
                  PG + "::test_t28_signed_int4_keys_bind_for_both_signs_and_unsigned_would_not"],
    },
    {
        "id": "B09-lock-without-integer-casts",
        "invariant": "T28 explicit (integer, integer) binding",
        "file": ROUTER,
        "old": "SELECT pg_advisory_xact_lock(CAST(:cls AS integer), CAST(:obj AS integer))",
        "new": "SELECT pg_advisory_xact_lock(:cls, :obj)",
        "tests": [UNIT + "::test_t28_the_lock_class_is_the_repositorys_only_two_int_advisory_class"],
    },
    {
        "id": "B10-no-lookup-before-the-start-gates",
        "invariant": "INV-3 a committed start replays before 404/G-14/quota",
        "file": ROUTER,
        "old": START_SEND,
        "new": "    _serialise_send(db, user_id, key)\n",
        "tests": [UNIT + "::test_t16_a_start_committed_before_the_listing_was_withdrawn_replays"],
    },
    {
        "id": "B11-lookup-before-access-on-append",
        "invariant": "FD-6 the key is never a capability",
        "file": ROUTER,
        "old": "    conv, side = _load(db, user, conversation_id)\n"
               "    user_id, conv_id, key = user.id, conv.id, str(body.client_message_id)\n"
               + APPEND_SEND,
        "new": "    user_id, conv_id, key = user.id, conversation_id, str(body.client_message_id)\n"
               + APPEND_SEND + "    conv, side = _load(db, user, conversation_id)\n",
        "tests": [UNIT + "::test_t14_a_provider_who_lost_the_right_gets_404_on_a_retry"],
    },
    {
        "id": "B12-append-skips-body-comparison",
        "invariant": "INV-8 same key, other body → 409",
        "file": ROUTER,
        "old": "    if message.conversation_id != conversation_id or message.body != body:\n",
        "new": "    if message.conversation_id != conversation_id:\n",
        "tests": [UNIT + "::test_t2_the_same_key_with_another_body_is_refused"],
    },
    {
        "id": "B12b-start-skips-body-comparison",
        "invariant": "INV-8 same key, other body → 409 (start)",
        "file": ROUTER,
        "old": "            or message.body != body):\n",
        "new": "            ):\n",
        "tests": [UNIT + "::test_t2_the_same_key_with_another_body_is_refused"],
    },
    {
        "id": "B13-append-skips-target-comparison",
        "invariant": "INV-8 same key, other conversation → 409",
        "file": ROUTER,
        "old": "    if message.conversation_id != conversation_id or message.body != body:\n",
        "new": "    if message.body != body:\n",
        "tests": [UNIT + "::test_t2_the_same_key_for_another_conversation_or_listing_is_refused"],
    },
    {
        "id": "B13b-start-skips-listing-comparison",
        "invariant": "INV-8 same key, other listing → 409",
        "file": ROUTER,
        "old": "    if (conv is None or conv.listing_id != offer_id or conv.requester_user_id != user_id\n",
        "new": "    if (conv is None or conv.requester_user_id != user_id\n",
        "tests": [UNIT + "::test_t2_the_same_key_for_another_conversation_or_listing_is_refused"],
    },
    {
        "id": "B13c-start-skips-requester-comparison",
        "invariant": "a start replays only the caller's own thread",
        "file": ROUTER,
        "old": "    if (conv is None or conv.listing_id != offer_id or conv.requester_user_id != user_id\n",
        "new": "    if (conv is None or conv.listing_id != offer_id\n",
        "tests": [UNIT + "::test_t2_a_start_cannot_replay_a_message_the_caller_sent_in_someone_elses_thread"],
    },
    {
        "id": "B14-no-rollback-before-the-race-lookup",
        "invariant": "INV-9 full rollback after a lost race",
        "file": ROUTER,
        "old": "        failure = _integrity_failure(exc)\n    db.rollback()\n"
               "    winner = _winner_of_lost_race(db, \"append\", user_id, key, failure)\n",
        "new": "        failure = _integrity_failure(exc)\n"
               "    winner = _winner_of_lost_race(db, \"append\", user_id, key, failure)\n",
        "tests": [UNIT + "::test_a_lost_unique_race_on_sqlite_is_answered_with_the_winner"],
    },
    {
        "id": "B15-replay-touches-the-conversation",
        "invariant": "INV-5 a replay writes nothing",
        "file": ROUTER,
        "old": APPEND_SEND,
        "new": APPEND_SEND.replace(
            "        return _replay_append(conv_id, body.body, earlier, \"replay\")\n",
            "        conv.last_message_at = _now()\n        db.commit()\n"
            "        return _replay_append(conv_id, body.body, earlier, \"replay\")\n"),
        "tests": [UNIT + "::test_t17_t18_t20_a_replay_writes_nothing"],
    },
    {
        "id": "B16-non-canonical-key",
        "invariant": "INV-13 one canonical spelling per UUID",
        "file": ROUTER,
        "old": "    user_id, key = user.id, str(body.client_message_id)\n",
        "new": "    user_id, key = user.id, body.client_message_id.hex\n",
        "tests": [UNIT + "::test_t23_other_spellings_of_one_uuid_are_one_key"],
    },
    {
        "id": "B17-written-before-the-closed-refusal",
        "invariant": "INV-11 a refusal writes nothing and leaves the key unused",
        "file": ROUTER,
        "old": APPEND_LOCK,
        "new": "        locked = _lock(db, conv_id)\n"
               "        message = _post(db, user, locked, side, body.body, key)\n"
               "        db.commit()\n"
               "        if locked is None or locked.status != \"ACTIVE\":\n"
               "            raise _closed()\n",
        "tests": [UNIT + "::test_t11_a_refused_send_does_not_use_its_key"],
    },
    {
        "id": "B18-original-integrity-error-escapes",
        "invariant": "INV-12 DETAIL never leaves the route",
        "file": ROUTER,
        "old": "    except IntegrityError as exc:\n        failure = _integrity_failure(exc)\n    db.rollback()\n"
               "    winner = _winner_of_lost_race(db, \"append\", user_id, key, failure)\n",
        "new": "    except IntegrityError:\n        raise\n",
        "tests": [UNIT + "::test_t24_an_unexpected_integrity_error_is_sanitized"],
    },
    {
        "id": "B19-detail-in-the-sanitized-error",
        "invariant": "INV-12 only SQLSTATE and constraint name are reported",
        "file": ROUTER,
        "old": "            str(getattr(diag, \"constraint_name\", None) or \"unknown\"))\n",
        "new": "            str(orig))\n",
        "tests": [UNIT + "::test_t24_an_unexpected_integrity_error_is_sanitized"],
    },
    {
        "id": "B20-postgres-parameters-rendered",
        "invariant": "FD-8 hide_parameters on PostgreSQL engines",
        "file": DB,
        "old": "        kwargs[\"hide_parameters\"] = True\n",
        "new": "",
        "tests": [PG + "::test_fd8_a_postgres_error_never_renders_its_parameters"],
    },
    {
        "id": "B22-lookup-before-the-send-lock",
        "invariant": "INV-4 the lookup follows the lock (a separate, later statement)",
        "file": ROUTER,
        "old": APPEND_SEND,
        "new": APPEND_SEND.replace(
            "    _serialise_send(db, user_id, key)\n    earlier = _keyed(db, user_id, key)\n",
            "    earlier = _keyed(db, user_id, key)\n    _serialise_send(db, user_id, key)\n"),
        "tests": [PG + "::test_t5_a_concurrent_same_key_append_waits_then_replays_the_committed_message",
                  T22 + "[with_send_lock-append]"],
    },
    {
        "id": "B21-no-lookup-on-append",
        "invariant": "INV-3 append: a committed send replays before CONVERSATION_CLOSED",
        "file": ROUTER,
        "old": APPEND_SEND,
        "new": "    _serialise_send(db, user_id, key)\n",
        "tests": [T22 + "[with_send_lock-append]",
                  UNIT + "::test_t13_a_send_committed_before_closure_replays_on_both_routes"],
    },
]


if __name__ == "__main__":
    harness.main()
