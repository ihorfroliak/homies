# BP-5 / BP-6 — Viewing cancellation attribution and G-14 safety cleanup

| Field | Value |
|---|---|
| Authority | Final founder execution authorization (2026-10-11), D-110; D-104/D-105, 04a section 24, FE-003 sections 3.10/4 |
| Owner | Codex, temporary sole bounded implementation writer; separate independent reviewer required |
| Base | Integrated main `74a7065e167e6cea8d4251a17138ffe775b02a54`, tree `735e1557a1362c0070f815c4875bab7fa69920f8` |
| Branch | `codex/BP-5-BP-6-viewing-cancellation` |
| Risk | R2: migration/data transformation, immutable attribution, moderation, locking and private engagement |
| State | BP-5 and BP-6 IMPLEMENTED CANDIDATE; full verification and independent review in progress |
| Delivery | Coherent feature-branch commits, tests, required exact-head CI, Draft PR, one separate exact-SHA independent review; new PR merge NOT authorized |

## Scope and preserved boundaries

BP-5 adds durable `Viewing.cancelled_by`: REQUESTER, PROVIDER or HOMIES.
Every new cancellation has a source; non-CANCELLED rows have none. Recorded
sources cannot be overwritten, including by repeated cancellation. Existing
status semantics and the `cancelled_by_homies` compatibility field remain.
A requester is still REQUESTER even if they also manage the listing.

Historical backfill uses authoritative `ViewingCancelled` facts bound to the
same viewing/listing with the canonical event identity and a valid source.
Absent, malformed or conflicting evidence never becomes a guessed actor.
Such pre-migration CANCELLED rows retain NULL with a private legacy marker.
The database rejects new legacy exceptions and alteration of that marker;
it is not exposed as another public cancellation-source value.

The migration's compatibility declaration follows actual previous-writer
behavior under RELEASE-AND-MIGRATION section 2. Strict new cancellation
checks cannot be advertised as EXPAND if the previous writer omits the
required source. In that case use BARRIER / rollback BLOCKED and prove the
old write is rejected; this refines FE-003's preliminary EXPAND estimate,
without changing cancellation business semantics or authorizing deployment.
The historical BP-10 EXPAND/BLOCKED record, migrate-first requirement and
BB-11 all-serving-instances gate remain intact. Recovery is forward repair;
a downgrade is a disposable-development operation, never an approved rollback.

BP-6 implements OD-1 option C: a G-14 conversation restriction cancels only
the requester's currently existing REQUESTED/CONFIRMED viewings on the same
listing with `starts_at > decision.effective_from` (the database instant).
Equal/past/terminal and unrelated rows stay unchanged. This cleanup is not
publication-generation-scoped; F6's gate on new engagement remains generation-
scoped, and no generation column is introduced on Viewing.

Restriction, cancellations, timestamps, immutable HOMIES sources,
ViewingCancelled facts with the actual moderation_decision_id and neutral
inbox notices to requester and current MANAGE_VIEWINGS providers commit or
roll back together. Notices carry only viewing/listing IDs and instant, never
an allegation, private reason, contact information or exact address. Lock
order remains listing before conversation before sorted viewing rows.

## Allowed changes

Viewing model/service/projection; trust cancellation effects, conversation
restriction locking and neutral notices; one migration and release metadata;
OpenAPI snapshot and generated frontend API types; focused tests and their
necessary fixtures/head pins; this contract, integration receipt, DEVLOG,
PROJECT-STATUS and relevant convergence/release/FE-003 metadata.

No BP-10 idempotency changes, agent definitions/permissions, unrelated product
or authority repairs, FE-003/FE-VIS UI, payments, production or deployment.
D-109 debt stays open. IBB-001 stays the last formal baseline.

## Verification and delivery gates

- BP-5: requester/provider/platform attribution, non-cancelled shape, repeat
  immutability, raw PostgreSQL constraints/guards, deterministic backfill,
  unknown/conflicting historical evidence, non-destructive migration round trip,
  honest prior-writer compatibility and restored cancellation attribution.
- BP-6: real PostgreSQL restriction versus confirm/new request/requester cancel/
  provider cancel in both serial orders, observed blocking and committed final
  states, strict time boundary, requester/listing isolation, repeated restriction
  and side-effect deduplication, rollback, republish/new generation, no deadlocks.
- Targeted and relevant SQLite/PostgreSQL suites, ruff/mypy, OpenAPI drift,
  generated types/typecheck, migration/release checks, restore where relevant,
  required CI and a genuinely separate exact-SHA independent review.
- Only executed results are recorded. SQLite is not lock evidence; thread
  completion order is not commit-order proof; cleanup always releases/joins
  worker threads. No unsupported mutation-kill claim.

Product doctrine relevance: A1 clear attribution; A2 privacy and home-visit
safety; A3 automatic cleanup; A4 atomic operations prevent manual repair;
A9 no city/country-specific coupling.

## Evidence

BP-5 slice verification on Python 3.12.15 / PostgreSQL 16.4 / PostGIS 3.4.3,
synthetic task-only database: targeted SQLite 85 passed; backfill/immutability/
old-writer/round-trip PostgreSQL test 1 passed; release/schema/OpenAPI 87 passed;
PostgreSQL viewing/engagement/release/migration/restore regression 68 passed;
strengthened attribution/guard restore drill 1 passed. Ruff clean; mypy clean
(126 files); generated types/typecheck pass. An initial release test expected
one fewer migration and the new restore fixture used the wrong requester token;
both test fixtures were corrected and rerun successfully. Host Node 24.14 emitted
transitive engine warnings; only generation/typecheck success is claimed.

Commands: `pytest -q -p no:cacheprovider` on `test_bp5_cancellation_source.py`,
`test_viewings.py`, `test_engagement_safety.py`; separately the BP-5 `_pg` test;
`test_release_manifest.py`, `test_schema_compat.py`, `test_tst01_openapi_contract.py`;
then `test_viewings_pg.py`, `test_engagement_safety_pg.py`, `test_release_pg.py`,
`test_td01_migrations.py`, `test_dr_restore_phase1_pg.py`. The amended restore
module was rerun separately with `HOMIES_REQUIRE_RESTORE_DRILL=1` and real
pg_dump/pg_restore. `ruff check --no-cache app tests` plus the new migration;
`mypy app`; frontend `npm run gen:api` and `npm run typecheck`.

BP-6 implemented after coherent BP-5 commit
`423c53f2ff4c684326b06222688edbde06348153`. Only FEATURE_RESTRICTED takes
listing FOR NO KEY UPDATE before the conversation and sorted viewing locks.
A shared cancellation helper applies the strict requester/listing/time/state
scope; listing close-engagement retains its prior scope. Row changes, HOMIES
attribution, facts and neutral both-party inbox notices share the decision
transaction. Existing F6 generation semantics are preserved.

Targeted PostgreSQL BP-6 tests: 10 passed, including eight observed blocking
schedules (both orders against confirm/request/requester cancel/provider cancel),
strict database-instant equality, unrelated/terminal isolation, rollback,
repeat refusal without duplicate effects, and republish behavior. An initial
test assumed republish replaces an ACTIVE conversation; corrected to assert the
actual incremented publication generation while the active conversation persists.
Ruff clean, mypy clean (126 files). Full candidate CI and separate exact-SHA
review remain pending; the full SQLite+PostgreSQL suite is running.
No mutation-test result is claimed. Not deployed.
BP-6 HTTP privacy/late-rollback checks: 2 passed after correcting the provider
inbox URL in the test fixture; previous combined targeted run also passed the
other 29 regression cases. This correction changes no implementation behavior.
