"""TASK-014R mutation / fault harness — TASK-014A repairs (F-1..F-6, N-3, N-4).

Same rules and runner as task002_mutants.py: green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256 verified.
Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task014r_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

harness.MUTANTS = [
    {
        "id": "X13",  # revalidation ignores the delivery user's ownership
        "invariant": "send-time revalidation only counts the delivery user's own searches",
        "file": 'app/modules/alerts/delivery.py',
        "old": '               SavedSearch.user_id == d.user_id)\n',
        "new": '               )\n',
        "tests": ['tests/test_task014r_repairs.py::test_x13_another_users_search_never_keeps_a_delivery_alive'],
    },
    {
        "id": "X18",  # paused searches become candidates
        "invariant": 'a paused saved search is never a matching candidate',
        "file": 'app/modules/alerts/matching.py',
        "old": '               SavedSearch.status == "active",\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_x18_a_paused_search_is_never_a_candidate'],
    },
    {
        "id": "X06",  # send-time verified-email check removed
        "invariant": 'an address unverified after queueing is never emailed',
        "file": 'app/modules/alerts/delivery.py',
        "old": '    if d.channel == "EMAIL" and (not user.email or user.email_verified_at is None):\n        return Check("email_not_verified")\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_x06_an_address_unverified_after_queueing_is_not_emailed'],
    },
    {
        "id": "X07",  # superseded-generation check removed
        "invariant": 'a delivery for an older public episode is superseded',
        "file": 'app/modules/alerts/delivery.py',
        "old": '    if offer.public_generation != d.public_generation:\n        return Check("superseded")\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_x07_a_delivery_for_an_older_episode_is_superseded'],
    },
    {
        "id": "X08",  # expired unsubscribe token accepted
        "invariant": 'an expired unsubscribe token changes nothing (generic answer)',
        "file": 'app/modules/alerts/delivery.py',
        "old": '    if freshness.to_utc(row.expires_at) <= now:\n        return "expired"\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_unknown_expired_and_used_tokens_answer_identically'],
    },
    {
        "id": "X10",  # reconcile window unbounded
        "invariant": 'reconcile restores only recent unhandled episodes',
        "file": 'app/modules/alerts/worker.py',
        "old": '        .where(ClassifiedOffer.public_since >= now - RECONCILE_WINDOW,\n',
        "new": '        .where(ClassifiedOffer.public_since.is_not(None),\n',
        "tests": ['tests/test_task014r_repairs.py::test_x10_reconcile_restores_only_recent_episodes'],
    },
    {
        "id": "F1-a",  # capabilities not committed before SMTP
        "invariant": 'unsubscribe capabilities are committed before SMTP',
        "file": 'app/modules/alerts/delivery.py',
        "old": '        db.commit()\n        locked = db.execute(',
        "new": '        locked = db.execute(',
        "tests": ['tests/test_task014r_repairs.py::test_a_link_from_an_email_sent_before_a_crash_works', 'tests/test_task014r_repairs_pg.py::test_links_committed_before_smtp_survive_a_crash_and_a_retry_reuses_them'],
    },
    {
        "id": "F1-b",  # a fresh random capability on every attempt
        "invariant": 'a retry of the same delivery reuses the same capabilities',
        "file": 'app/modules/alerts/delivery.py',
        "old": '    mac = hmac.new(key, f"{delivery_id}\\n{scope}\\n{saved_search_id or \'\'}".encode(),',
        "new": '    mac = hmac.new(key, f"{delivery_id}\\n{scope}\\n{saved_search_id or \'\'}{uuid4()}".encode(),',
        "tests": ['tests/test_task014r_repairs.py::test_a_retry_after_a_crash_reuses_the_same_working_links'],
    },
    {
        "id": "N3",  # replayed token applies again
        "invariant": 'an unsubscribe token has a single-use effect',
        "file": 'app/modules/alerts/delivery.py',
        "old": '    if row.used_at is not None:\n        return "replayed"\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_an_old_link_cannot_undo_a_later_re_enable'],
    },
    {
        "id": "F2-a",  # canonical-form check removed
        "invariant": 'a stored query that is not its own canonical form is INVALID',
        "file": 'app/modules/saved/service.py',
        "old": '    if q.canonical() != saved.canonical_query:\n        raise InvalidSearchQuery("the stored query is not in its canonical form")\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_a_corrupted_stored_query_is_invalid_everywhere'],
    },
    {
        "id": "F2-b",  # fingerprint check removed
        "invariant": 'a stored query whose fingerprint does not match is INVALID',
        "file": 'app/modules/saved/service.py',
        "old": '    if fingerprint(saved.query_schema_version, saved.canonical_query) != saved.query_fingerprint:\n        raise InvalidSearchQuery("the stored query does not match its fingerprint")\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs.py::test_a_corrupted_stored_query_is_invalid_everywhere', 'tests/test_task014r_repairs.py::test_corruption_after_queueing_suppresses_the_send'],
    },
    {
        "id": "F3",  # no reconciliation with surviving history
        "invariant": 're-upgrade resumes public generations from surviving history',
        "file": 'alembic/versions/f3b5d7e9a1c2_saved_search_alerts.py',
        "old": '    _reconcile_surviving_generations()\n',
        "new": '',
        "tests": ['tests/test_task014r_repairs_pg.py::test_re_upgrade_resumes_generations_from_surviving_history'],
    },
    {
        "id": "F4",  # unique violation on PATCH escapes as 500
        "invariant": 'the fingerprint unique violation on PATCH answers 409',
        "file": 'app/modules/saved/router.py',
        "old": '        raise HTTPException(status.HTTP_409_CONFLICT, "This search is already saved") from None\n',
        "new": '        raise\n',
        "tests": ['tests/test_task014r_repairs_pg.py::test_a_patch_blocked_on_the_unique_fingerprint_answers_409'],
    },
    {
        "id": "F5-a",  # 5xx treated as transient
        "invariant": 'SMTP 5xx is permanent',
        "file": 'app/modules/events/providers.py',
        "old": '        return not (500 <= code < 600), f"{name}:{code}"\n',
        "new": '        return True, f"{name}:{code}"\n',
        "tests": ['tests/test_task014r_repairs.py::test_smtp_errors_are_classified_by_code_without_provider_text'],
    },
    {
        "id": "F5-b",  # raw provider text stored again
        "invariant": 'no raw provider text is stored',
        "file": 'app/modules/events/providers.py',
        "old": '            return DeliveryResult(ok=False, transient=transient, error=reason)\n',
        "new": '            return DeliveryResult(ok=False, transient=transient, error=str(e)[:255])\n',
        "tests": ['tests/test_task014r_repairs.py::test_the_smtp_channel_reports_a_machine_reason_only', 'tests/test_task014r_repairs.py::test_a_refused_transactional_email_stores_no_address'],
    },
    {
        "id": "N4",  # exhausted retries labelled permanent
        "invariant": 'exhausted transient retries are not labelled a provider rejection',
        "file": 'app/modules/alerts/delivery.py',
        "old": '        _finish(d, "dead", "retries_exhausted", now)\n',
        "new": '        _finish(d, "dead", "permanent_failure", now)\n',
        "tests": ['tests/test_task014r_repairs.py::test_a_permanent_refusal_and_exhausted_retries_end_differently'],
    },
]


if __name__ == "__main__":
    harness.main()
