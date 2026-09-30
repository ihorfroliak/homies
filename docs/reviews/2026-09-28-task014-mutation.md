# TASK-014 — mutation / fault evidence (builder, 2026-09-28)

Harness: `backend/scripts/mutation/task014_mutants.py` (runner of
task002_mutants.py: green baseline first; one exact textual replacement;
**killed** only when pytest exits 1 with failures and no errors; source bytes
restored and SHA-256 verified after every mutant; working tree clean after the
run). Environment: Python 3.12.14 (test image), PostgreSQL 16.4 / PostGIS 3.4.3
(disposable Docker). Result: **21 / 21 killed, 0 survived, 0 invalid.**

| ID | Invariant | Mutation | Killing test | How it is killed |
|---|---|---|---|---|
| A01 | own saves only (delete) | `DELETE saved_listings` without `user_id = caller` | test_saved_listings::test_saves_are_private_to_their_owner | another account's DELETE removes the save → total 0 ≠ 1 |
| A01b | own saves only (list) | list without owner predicate | same | intruder sees items |
| A02 | tombstone privacy | "public" set without `public_clause` | ::test_non_public_save_is_a_privacy_safe_tombstone | paused listing returned with title/place |
| A03 | evaluation carries the public rule | `evaluate_for_listing` WHERE without `public_clause` | test_saved_search_alerts::test_evaluation_never_matches_a_listing_that_is_not_public | paused / silently-expired listing evaluates True |
| A04 | no initial flood | `baseline_at < became_public_at` → `IS NOT NULL` | ::test_existing_matches_never_alert | pre-existing listing alerts |
| A05 | reconfirm keeps the episode | `opening = True` | test_public_generation::test_already_public_republish_and_reconfirm_open_no_episode | generation 3, extra events |
| A06 | silent expiry opens an episode | `was_public`: `and` → `or` (status label wins) | ::test_silent_freshness_expiry_then_confirm_opens_a_new_episode | generation stays 1 |
| A07 | atomic generation/event/work | `db.commit()` between UPDATE and episode write | ::test_generation_event_and_work_item_are_atomic | status/generation persisted after the failure |
| A08 | match uniqueness is the DB's | migration: `saved_search_matches` without PK | test_saved_search_alerts_pg::test_b_two_searches_one_user_one_delivery | the matcher's `ON CONFLICT` has no arbiter → work item errors → 0 matches ≠ 2 (the test also asserts the PK directly) |
| A09 | delivery dedup is the DB's | migration: drop `uq_alert_deliveries_user_episode_channel` | same | same mechanism; the test also asserts the named constraint on a duplicate insert |
| A10 | send-time public check | only `offer is None` | ::test_listing_no_longer_public_suppresses_queued_delivery | reason `no_longer_matches` ≠ `listing_not_public` — the delivery is still suppressed by the re-match (defence in depth); the mutant is killed on the reason |
| A11 | send-time re-match | `still = all valid searches` | ::test_listing_no_longer_matching_suppresses_queued_delivery | queued alert delivered |
| A12 | unsubscribe suppresses | SAVED_SEARCH scope does not disable | ::test_unsubscribe_from_one_search_suppresses_its_queued_delivery | queued alert delivered |
| A13 | alert SMTP recipient | `to=d.user_id` | ::test_alert_email_goes_to_the_verified_address_never_the_user_id | SMTP `To` = user id |
| A13b | transactional SMTP recipient | `recipient_address` returns user id | ::test_transactional_email_resolves_the_address_at_send_time | SMTP `To` = user id |
| A14 | no broadening (unknown criterion) | parser `continue`s past unknown names | test_saved_searches::test_a_corrupted_stored_query_is_invalid_not_broadened | stored query VALID |
| A14b | no broadening (retired place) | `load_query` without `check_references` | test_saved_search_alerts::test_invalid_stored_query_never_alerts | alert on a retired-place query |
| A15 | ack identity | acknowledge without `public_generation = N` | test_saved_search_alerts_pg::test_c_acknowledging_n_never_consumes_n_plus_one | generation 2 marked superseded |
| A16 | public point only | `_PUBLIC_GEOG` → `properties.exact_geog` | ::test_spatial_matching_uses_the_public_point_only | box/ring around the home alerts |
| A17 | paused search suppressed | `live = linked` | test_saved_search_alerts::test_paused_search_suppresses_queued_delivery | delivered |
| A18 | own saved searches only | `_own_search` without owner | test_saved_searches::test_saved_searches_are_private_to_their_owner | intruder reads/patches/deletes |

Honesty notes:
* A08/A09 are schema mutants: removing the constraint also removes the
  `ON CONFLICT` arbiter the code relies on, so the kill arrives through the
  worker error path (an assertion on counts), not through duplicate rows; the
  same test asserts each constraint by name on a direct duplicate insert.
* A10 is defence in depth: the canonical re-match (public clause inside
  `evaluate_for_listing`) would still suppress; the mutant dies on the
  suppression reason.

## Independent re-run (2026-09-29)

Same harness on a private copy of the tree (host Python 3.14.3, pinned set;
separate disposable PostgreSQL 16.4 / PostGIS 3.4.3): **21 / 21 killed**,
green baseline before each. Added **L01** (stub email channel logs the
address instead of `present`) — killed by
`test_saved_search_alerts::test_the_alert_flow_logs_no_address_or_contact`.

## Scale probe (LOCAL evidence)

`tests/test_saved_search_scale_pg.py` (TASK014_SCALE=full): 10 000 saved
searches, 1 000 listings, 500 users. Per new public listing: Kraków 7 096
candidates / 4 304 matches / 49 statements / 15 evaluation statements /
12.5 s; Warszawa 4 903 / 2 906 / 40 / 12 / 6.1 s; Balice 3 016 / 1 832 / 35 /
10 / 8.5 s. Default shape (2 000 × 300): 1.8–3.9 s. Candidate query: bitmap
index scans on `ix_saved_search_anchors_key`, 13 ms. A cartesian design would
evaluate 10⁷ search×listing pairs per pass.
