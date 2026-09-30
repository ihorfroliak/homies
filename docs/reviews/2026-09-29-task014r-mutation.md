# TASK-014R — mutation / fault evidence (builder, 2026-09-29)

Harness: `backend/scripts/mutation/task014r_mutants.py` (runner of
task002_mutants.py: green baseline first; one exact textual replacement;
**killed** only when pytest exits 1 with failures and no errors; source bytes
restored and SHA-256 verified after every mutant). Environment: Python 3.12.14
(test image), PostgreSQL 16.4 / PostGIS 3.4.3 (disposable Docker container
`homies-task014r-pg`), run on a private copy of the tree.
Result: **16 / 16 killed, 0 survived, 0 invalid**; every baseline green on
the first run.

| ID | Invariant | Mutation | Killing test | How it is killed |
|---|---|---|---|---|
| X13 | revalidation counts only the delivery user's searches | drop `SavedSearch.user_id == d.user_id` from the send-time lookup | test_task014r_repairs::test_x13_another_users_search_never_keeps_a_delivery_alive | delivered ≠ `suppressed/search_deleted`: another user's matching search kept the delivery alive |
| X18 | a paused search is never a candidate | drop `SavedSearch.status == "active"` from candidate selection | ::test_x18_a_paused_search_is_never_a_candidate | the paused search is returned as a candidate (list ≠ []) |
| X06 | an address unverified after queueing is not emailed | remove the send-time `email_not_verified` check | ::test_x06_an_address_unverified_after_queueing_is_not_emailed | EMAIL delivery left `processing` (send attempted) ≠ `suppressed/email_not_verified` |
| X07 | an older-episode delivery is superseded | remove the `public_generation` comparison at send time | ::test_x07_a_delivery_for_an_older_episode_is_superseded | generation-1 delivery `delivered` ≠ `suppressed/superseded` |
| X08 | an expired token changes nothing | remove the expiry check in `unsubscribe` | ::test_unknown_expired_and_used_tokens_answer_identically | the expired token switched notifications off (`notifications_enabled` False) |
| X10 | reconcile is bounded | `public_since >= now - RECONCILE_WINDOW` → `IS NOT NULL` | ::test_x10_reconcile_restores_only_recent_episodes | 2 episodes restored ≠ 1 |
| F1-a | links exist before SMTP | remove the `db.commit()` before the send | ::test_a_link_from_an_email_sent_before_a_crash_works; test_task014r_repairs_pg::test_links_committed_before_smtp_survive_a_crash_and_a_retry_reuses_them | after the crash no capability row exists (0 ≠ 1): the emailed link does nothing |
| F1-b | a retry reuses the same links | a random component in the HMAC input | ::test_a_retry_after_a_crash_reuses_the_same_working_links | the retry email carries different links than the first |
| N3 | single-use effect | remove the `used_at` replay guard | ::test_an_old_link_cannot_undo_a_later_re_enable | the replay switched the re-enabled search off again |
| F2-a | canonical form required | remove the canonical-form check in `load_query` | ::test_a_corrupted_stored_query_is_invalid_everywhere[non_canonical] | non-canonical stored query `VALID` ≠ `INVALID` |
| F2-b | fingerprint required | remove the fingerprint check in `load_query` | ::test_a_corrupted_stored_query_is_invalid_everywhere[4 cases]; ::test_corruption_after_queueing_suppresses_the_send | 4 of the 6 selected tests fail: e.g. zeroed and foreign fingerprints `VALID` ≠ `INVALID` |
| F3 | re-upgrade resumes generations | remove `_reconcile_surviving_generations()` | test_task014r_repairs_pg::test_re_upgrade_resumes_generations_from_surviving_history | `two_public` back at generation 1 ≠ 2 |
| F4 | PATCH race answers 409 | re-raise the fingerprint unique violation | test_task014r_repairs_pg::test_a_patch_blocked_on_the_unique_fingerprint_answers_409 | the unique violation escapes the handler as a server error (asserted explicitly) |
| F5-a | SMTP 5xx is permanent | every reply code transient | ::test_smtp_errors_are_classified_by_code_without_provider_text[5xx cases] | `SMTPDataError:554`, `SMTPSenderRefused:553` classified transient |
| F5-b | no raw provider text stored | `error=str(e)[:255]` | ::test_the_smtp_channel_reports_a_machine_reason_only; ::test_a_refused_transactional_email_stores_no_address | provider text (with the address and a secret-looking string) returned / stored as the reason |
| N4 | exhausted ≠ rejected | exhausted retries labelled `permanent_failure` | ::test_a_permanent_refusal_and_exhausted_retries_end_differently | `dead/permanent_failure` ≠ `dead/retries_exhausted` |

Honesty notes:
* X06, X07, X08, X10 were TASK-014A ports: the named behaviours were already
  guarded by the TASK-014 suite in part; these tests make each guard the
  single killing point.
* X04 (claim CAS) stays a TASK-014A note, not a mutant here: the CAS fails
  closed and is exercised by the TASK-014 worker tests.
* F4: the first kill arrived as `KeyError` (the server error killed the
  request thread before it stored a response). The test now records an
  unhandled server error and asserts on it explicitly; the committed runner
  re-verifies the kill (see below).
* A first run of the scratch runner stopped at X07 because its baseline was
  red once (Docker VM clock step, see the TASK-014R report); the runner now
  allows one recorded baseline rerun — none was needed in the reported run.
* A first run of the scratch runner reported X06 as INVALID because it
  counted pytest's captured log line `ERROR homies.alerts:…` as a test error;
  the rule was narrowed to pytest `ERROR tests/…` lines, and the rerun killed
  all 16. The same mutants are committed in the repository runner above,
  whose rule is the task002 one (the summary line, not log lines).
