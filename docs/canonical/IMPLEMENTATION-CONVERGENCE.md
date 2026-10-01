# Implementation convergence map

Where the existing implementation stands against the canonical documents, as
of TASK-000 (2026-09-24). Baseline: `main` at
`782c833f100f1bf2e86888b664c9b30b27cbc1dd`. Nothing here is accepted merely
because it is committed: the C1–C8 port is a **candidate** pending independent
audit ([05 §9](05-DEVELOPMENT-GOVERNANCE-v1.md)).

Classifications: **CANONICAL_ACTIVE** · **ADAPT** · **LEGACY_DORMANT** ·
**REFERENCE_ONLY** · **REMOVE_LATER** · **UNKNOWN**.

## FOUNDATION BASELINE 002 — ACCEPTED (2026-09-25)

| | |
|---|---|
| SHA | `36231840ee52d6185e73fda07e54eab33ffe41f3` |
| Accepted after | TASK-008 builder implementation · TASK-009 Codex independent audit · TASK-009 Claude Code independent audit |
| Verdict (both audits) | `TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES` · `HOMIES_FOUNDATION_BASELINE_002_ACCEPTED` |
| Findings | P0 0 · P1 0 · P2 0 (P3/NOTE only, below) |
| Accepted for | continued Phase 1A development |
| Not equivalent to | production readiness — **NOT ASSESSED / NOT READY**; **NOT DEPLOYED** |
| Evidence (verbatim) | [Codex report](../reviews/2026-09-25-task009-codex-final-foundation-audit.md) · [Claude Code report](../reviews/2026-09-25-task009-claude-final-foundation-audit.md) |
| Decision | [D-56](../DECISIONS.md) |

Earlier sections of this map are the history that led here and are kept as
written. Where they say "pending re-audit", the TASK-009 audits and this
acceptance are the outcome.

### Foundation freeze

Not reopened or redesigned without concrete new evidence: C1–C8; F-01…F-09
(incl. F-04); N-01…N-10; atomic publication authorisation; membership
lifecycle protections; authority proof locking; Listing lifecycle CAS;
media/privacy foundation. A new concrete correctness issue may still be
reported.

### Nonblocking foundation debt (carried forward, not reopened)

**Protected-proof regression evidence** — conservative final adjudication:

| Restriction | Adjudication | Basis |
|---|---|---|
| E01 (mandate id) | **LOAD-BEARING** | Codex and Claude Code both killed it with raw-SQL probes |
| E02 (organization id) | **LOAD-BEARING** | same |
| E03 (legal-party id) | **TREAT AS LOAD-BEARING** | Claude Code killed it (FK re-pointing); Codex found it redundant under the current schema |
| E04 (authority id) | currently schema-redundant / equivalent | both; depends on the property FK, the FOR UPDATE coordination lock and the scope FK |

The accepted code **retains all four restrictions** — no live defect. Do not
remove any of them because an earlier mutation review called it equivalent.
Required maintenance: direct PostgreSQL regression tests for E01/E02/E03, and
corrected equivalence wording in the TASK-008 mutation review.

**Test-evidence debt (P3):** HTTP/thread response completion order is not
proof of PostgreSQL commit order (`test_publication_proof_replacement_pg.py`,
`test_publication_authority_race_pg.py`). When next touched, assert database
blocking, blocker PID, transaction state, committed state or explicit gates
instead. No foundation repair cycle is opened for it.

**Other nonblocking debt:** possible revoke starvation under sustained
publication traffic; no project-wide machine-readable error-code convention;
manager revoked mid-invite race; legal-name update vs admin verification
race; raw/direct Space mutation bypasses the Property coordination lock (the
API path is serialised); organization ↔ LegalParty cardinality (UNIQUE vs 04a
§1); automatic `Retry-After: 0` retries must eventually be capped; production
DR drill; production-readiness work. Codex verified Python 3.12 targeted
behaviour and a local synthetic PostgreSQL/PostGIS `pg_dump`/`pg_restore`
during TASK-009 — this is **not** production DR verification.

## PR-003 — database client deadlines and failure containment (2026-10-01, builder)

**BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (R2, D-88).** Candidate on
`claude/PR-003-db-failure-containment` from `main` `13a92ef` (PR-002
integrated); **not merged to `main`** — founder decision. Not independently
verified; part of the milestone / production-readiness audit. Production:
**NOT READY · NOT DEPLOYED.** [Task](../tasks/PR-003-db-failure-containment.md) ·
D-89 … D-91.

| Area | Classification | State |
|---|---|---|
| database deadline policy (`app/core/db.py`, `db_deadline.py`) | **CANDIDATE (builder verified)** | one policy; connect 3 s, pool wait 5 s, server statement 5 s / lock 2 s / idle-in-transaction 60 s / client check 2 s, client deadline 7 s with socket shutdown and invalidation |
| failure semantics (`app/core/db_failures.py`) | **CANDIDATE (builder verified)** | 503 + Retry-After by bounded reason; abandoned COMMIT = outcome unknown |
| health isolation | **CANDIDATE (builder verified)** | ops endpoints async; single-flight async readiness; no SQL on the event loop — closes PR-001RA RA-3 |
| workers (`app/core/worker_loop.py`) | **CANDIDATE (builder verified)** | shared loop, failure backoff, liveness metric and alerts |
| migration job connect/statement bounds | **DEBT** | `migrate.py` (PR-002) unchanged; relies on the job runner's timeout |
| idempotency of creates (property, classified, message) | **DEBT** | a retry after an unknown COMMIT can duplicate; follow-up |

## PR-002 — release and migration compatibility (2026-10-01, builder)

**BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (R2, D-88).** Branch
`claude/PR-002-release-migration-compatibility` from `main` `dacbe9e` (which
descends from IBB-001); integrated into `main` for continued development once
CI is 5/5 green. Not independently verified — the review is part of the
milestone / production-readiness audit. Production: **NOT READY · NOT
DEPLOYED.** [Task](../tasks/PR-002-release-migration-compatibility.md) ·
[policy](../production/RELEASE-AND-MIGRATION.md) · D-83 … D-87.

| Area | Classification | State |
|---|---|---|
| startup schema gate (`app/core/schema.py`) | **CANONICAL_ACTIVE (builder verified)** | compatibility decision from release manifest + migration graph + `schema_lineage` (missing/mismatched lineage refused), replacing exact-head (TD-01) outside `ENV=local`; build identity required outside local/test/ci |
| release manifest (`app/release.json`, `app/core/release.py`) | **CANONICAL_ACTIVE (builder verified)** | committed policy: schema head, lineage boundaries, schema_transition, explicit rollback_to_previous; no commit id — the build identity is injected (`RuntimeReleaseIdentity`) |
| `schema_lineage` (migration `0c4e6a8b2d91`) | **CANONICAL_ACTIVE (builder verified)** | 26 historical steps backfilled; later steps recorded by env.py |
| migration job (`app/scripts/migrate.py`) | **CANONICAL_ACTIVE (builder verified)** | migration role; session advisory lock on the migrating connection, 10 s try-lock budget; grant convergence; post-verify incl. privileges on every table/sequence; runs in CI |
| roles (`app/core/sql/`) | **CANONICAL_ACTIVE (builder verified)** | `homies_migrator` / `homies_app` separation; `migration_owner.sql` for pre-PR-002 databases; closes Phase A F-A3, F-A4, F-A5 by builder |
| PR-003 debt (request DB deadlines, health isolation) | **DEFERRED** | addressed by the PR-003 candidate (section above), not merged |

## Integrated Backend Baseline 001 — ACCEPTED (2026-09-30)

| | |
|---|---|
| ID | `IBB-001` — [baseline record](../baselines/IBB-001.md) |
| SHA | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` (tag `backend-baseline-001`) |
| Product parent | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` — TASK-014, accepted by TASK-014RA |
| Infra parent | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` — PR-001, accepted by PR-001RA2 |
| Audit | CONV-001A ([archived verbatim](../reviews/2026-09-30-conv001a-independent-integration-audit.md)) — 21 integration gates ACCEPTED |
| Verdict | **`CONV_001_ACCEPTED_WITH_NONBLOCKING_NOTES`** → `INTEGRATED_BASELINE_ACCEPTED`; P0–P3 0, NOTE 3 (CV-N1 harness drill count, CV-N2 restore drill omits TASK-014 tables, CV-N3 `assert_unhandled_500` request-id assertion → MICRO-001) |
| Accepted for | continued engineering development — **not** production readiness, **not** a release |
| Production | **NOT READY · NOT DEPLOYED** |

All subsequent backend implementation work MUST descend from IBB-001
or a documented successor baseline unless an explicit governance decision
authorizes another ancestry.

The sections below are the history that led here and are kept as written:
where they say "candidate", "pending audit" or "not accepted", this section
and the TASK-014 / PR-001 ACCEPTED sections are the outcome. Verification
from here on is risk-based (R0–R3,
[AUDIT-HISTORY](../reviews/AUDIT-HISTORY.md)); next serialized task:
MICRO-001 ([PROJECT-STATUS](../PROJECT-STATUS.md)).

## CONV-001 — product / infrastructure baseline convergence (2026-09-30, builder)

**INTEGRATION CANDIDATE — CONV-001A REQUIRED.** One non-fast-forward merge
commit on `claude/CONV-001-product-infra` whose parents are exactly the two
accepted lines (the SHA is named in the CONV-001 builder report; this page
cannot contain its own commit's SHA):

| Line | Accepted SHA | Verdict |
|---|---|---|
| PRODUCT (parent 1) | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` | TASK-014 ACCEPTED |
| INFRA (parent 2) | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` | PR-001 ACCEPTED |
| Common ancestor | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` | TASK-012 accepted line |

No new product behaviour, schema, release architecture or deployment. One
Alembic head (`f3b5d7e9a1c2`); git divergence is not Alembic divergence (the
infra line added no migration). The TASK-014 stable evidence proves only the
product parent and PR-001's acceptance only the infra parent: the integrated
candidate needs its own exact-SHA certification and the independent
**CONV-001A**. Not accepted until then. PR-002 Phase B stays blocked until
CONV-001 is accepted; PR-003 (health isolation), MICRO-001 and TASK-015 are
untouched. Production: **NOT READY · NOT DEPLOYED.**

## TASK-014 — ACCEPTED (2026-09-29)

Re-audit **TASK-014RA** (independent Claude session) of
`7ffb4f51dd315363362df1a5f8fc5c19a57767dc`:
**TASK_014_ACCEPTED_WITH_NONBLOCKING_NOTES** → `TASK_014_PHASE_1A_SLICE_ACCEPTED`
([archived verbatim](../reviews/2026-09-29-task014ra-independent-task014r-audit.md)).
P0–P3 0, NOTE 5: RA-N1 a channel exception outside SMTP/OS errors is retried
without a cap (pre-existing debt, with TASK-014A N-2); RA-N2 stale token wording
in the contract and D-81; RA-N3 the canonical-form check is defence in depth;
RA-N4 raw CI logs and artifacts need authentication (acceptance rests on the
public annotations and the auditor's own runs); RA-N5 the migration backfill
trusts well-formed `ListingBecamePublic` payloads. Stable evidence: run
`36595074447` / job `109497758765`, harness `3d37a7e`. Not production
readiness. Production: NOT DEPLOYED.

## PR-001 — ACCEPTED (2026-09-29)

Re-audit **PR-001RA2** (independent Claude session) of
`5cad442f07264ab25b3024c96fc691ad9c7a75fa`:
**PR_001_ACCEPTED_WITH_NONBLOCKING_NOTES** → `PR_001_BASELINE_ACCEPTED`
([archived verbatim](../reviews/2026-09-29-pr001ra2-independent-pr001r2-audit.md)).
RA-1 and RA-2 closed, m12 and the canary mutation killed; P0–P3 0 (RA-3 stays
PR-003 debt, not counted), NOTE 6: RA2-N1 the decision-budget value is not
pinned by a test; carried N-A, N-C, N-D, N-E, N-F. Accepting PR-001 does not
mean production readiness. Production: NOT READY, NOT DEPLOYED.

## TASK-014 → TASK-014A → TASK-014R — alert integrity repair (2026-09-29, builder)

History: TASK-014 candidate `196c88796cf34a6b19860259cc6ff81c94dbe8d2` → independent
**TASK-014A**: **TASK_014_REQUIRES_TARGETED_FIXES**, P0–P2 0 / P3 6 / NOTE 8,
EVIDENCE NOT_VERIFIED ([archived verbatim](../reviews/2026-09-29-task014a-independent-task014-audit.md))
→ **TARGETED FIX REQUIRED** → TASK-014R on `claude/TASK-014R-alert-integrity-repair`,
**pending TASK-014RA. TASK-014 is NOT accepted.** Accepted by TASK-014A and not reopened:
saved listing, saved search semantics, public generation, atomicity, concurrency, anchor
completeness, baseline/no flood, match and delivery dedup, N/N+1 isolation, send-time
revalidation, unsubscribe core, privacy, worker recovery.

| Finding | State after TASK-014R |
|---|---|
| F-1 SMTP crash left dead unsubscribe links | **CLOSED BY BUILDER** — capabilities derived per delivery, committed before SMTP, reused on retry |
| N-3 token replay after re-enable | **CLOSED BY BUILDER** — single-use effect, idempotent generic answer |
| F-2 stored query never verified | **CLOSED BY BUILDER** — canonical form + fingerprint required, else INVALID |
| F-3 downgrade → re-upgrade → publish 500 | **CLOSED BY BUILDER** — generation resumes from surviving event history; migration row added (N-5) |
| F-4 concurrent PATCH → 500 | **CLOSED BY BUILDER** — the fingerprint unique violation answers 409 |
| F-5 SMTP classification / provider text | **CLOSED BY BUILDER** — reply-code classification, machine reason only |
| N-4 exhausted retries labelled permanent | **CLOSED BY BUILDER** |
| F-6 surviving mutants X13, X18 (+X06/X07/X08/X10) | **CLOSED BY BUILDER** — behavioural tests; X04 stays a note (CAS fails closed) |
| N-2 poison work item uncapped | **DEBT** — dedicated retry-policy follow-up |
| N-7 F13RA-N01 wording | **MICRO-001** (unchanged here) |
| EVIDENCE | exact-SHA stable-clock run required (see the TASK-014R report) |

## PR-001R → PR-001RA → PR-001R2 — readiness contract & canary repair (2026-09-29, builder)

Re-audit **PR-001RA** (independent Claude session) of `70be78b`:
**PR_001_REQUIRES_TARGETED_FIXES**, P0 0 / P1 0 / P2 1 / P3 2
([archived verbatim](../reviews/2026-09-29-pr001ra-independent-pr001r-audit.md)).
F1–F10, N1, N5, N7 CLOSED; F11 PARTIAL. PR-001R2 on
`claude/PR-001R2-readiness-repair`, **pending PR-001RA2. PR-001 NOT accepted.
Production: NOT READY, NOT DEPLOYED.**

| Finding | State after PR-001R2 |
|---|---|
| RA-1 (P2) readiness "3 s end to end" false; deadline untested | **CLOSED BY BUILDER** — decision budget vs measured finite completion documented (code, row 6); freeze-after-connect PostgreSQL regression; m12 killed |
| RA-2 (P3) canary green on advisory-lookup failure | **CLOSED BY BUILDER** — structured JSON proof required; failure fixtures tested |
| RA-3 (P3) health endpoints share the business thread pool | **DEFERRED — PR-003 debt**, canonical decision on health isolation |
| N-B README stale lines | cleaned (status, process wording, layout) |
| N-A, N-C, N-D, N-E, N-F | open notes, unchanged |

## TASK-013 — ACCEPTED (2026-09-28)

Re-audit **TASK-013RA** (Codex) of `3f324b6ddff6c7557894eb5f65736729d956f7eb`: **TASK_013_ACCEPTED_WITH_NONBLOCKING_NOTES** → `TASK_013_PHASE_1A_SLICE_ACCEPTED` (D-77; [archived verbatim](../reviews/2026-09-28-task013ra-codex-task013r-audit.md)). F13A-01 and F13A-02 closed; P0–P3 0. Nonblocking notes retained: **F13RA-N01** — the worst-case canonical-length test and D-76 wording overstate the per-field guarantee (percent-encoded Unicode ids can reach the 16 384 backstop within per-field budgets; the backstop itself works: 16 384 accepted, 16 385 refused) → test/doc improvement, open; **F13RA-N02** — the audit host's wall clock stepped backwards, which limits full-suite certification there (environment, not code). Production: NOT DEPLOYED.

## TASK-014 — saved listings, saved search & alerts (2026-09-28, builder)

Candidate on `claude/TASK-014-saved-search-alerts`, started from the accepted
TASK-013 baseline `3f324b6ddff6c7557894eb5f65736729d956f7eb` (D-77).
**Not accepted** — TASK-014A independent audit pending. **Production: NOT
READY, NOT DEPLOYED.** Contract:
[TASK-014](../tasks/TASK-014-saved-listings-saved-search-alerts.md);
decisions D-78…D-82; 04a §22.

| Area | State |
|---|---|
| Saved Listing | `saved_listings (user, listing)` — **supersedes Saved Property for Phase 1A** (04a §22, D-78); tombstone for non-public listings |
| Saved Search | TASK-013 canonical query + schema version + SHA-256 fingerprint; INVALID never broadened (D-79) |
| Public generation | `classified_offers.public_generation`/`public_since`; every public transition through `publicity.make_public` with `ListingBecamePublic` + work item atomically (D-80) |
| Alerts | PostgreSQL work items → anchor-narrowed candidates → canonical match → UNIQUE matches → UNIQUE per-user-channel deliveries → send-time revalidation (D-82) |
| Notifications | PRODUCT category (product policy, not legal/marketing consent); `notification_preferences`; inbox `user_notifications` at `/v1/me/inbox`; hashed 256-bit unsubscribe tokens (D-81) |
| SMTP recipient | Phase-A defect fixed: address resolved at send time, never the user id (D-81) |
| Deferred | digest; alert families while continuously public; Follow Property; email locale; retention/purge |

| Component | Classification |
|---|---|
| `app/modules/saved` (saved listings, saved searches, stored-query validation) | **CANONICAL_ACTIVE** (candidate) |
| `app/modules/alerts` (work, matches, deliveries, inbox, preferences, unsubscribe, worker) | **CANONICAL_ACTIVE** (candidate) |
| `app/modules/properties/publicity.py` | **CANONICAL_ACTIVE** (candidate) — the one public-transition seam |
| booking-era `GET /v1/me/notifications` feed | **LEGACY_DORMANT** shape, kept unchanged; the inbox is `/v1/me/inbox` |

## TASK-013 → TASK-013A → TASK-013R — search validation & map count (2026-09-28, builder)

History: TASK-013 candidate `56567d24bd764563bc21707c0c027e637a206e16` → independent **TASK-013A** (Codex): **TASK_013_REQUIRES_TARGETED_FIXES**, P0 0 / P1 0 / **P2 1** / P3 1 ([archived verbatim](../reviews/2026-09-28-task013a-codex-task013-audit.md)) → **TARGETED FIX REQUIRED** → TASK-013R on `claude/TASK-013R-search-validation-map-count`, **pending narrow re-audit (TASK-013RA)**. **TASK-013 is NOT accepted.** Accepted by TASK-013A and not reopened: public eligibility, geography, spatial privacy, price semantics, availability, sort/pagination, query count, indexes/migration, URL-state concept, archive integrity.

| Finding | Severity | State |
|---|---|---|
| F13A-01 invalid anonymous query values reach PostgreSQL → HTTP 500 | P2 | **CLOSED BY BUILDER** (TASK-013R) — validated before SQL (D-76); reproduced first on `56567d2` |
| F13A-02 map `without_point` negative under a concurrent publication | P3 | **CLOSED BY BUILDER** — one aggregate statement; deterministic interleaving test |
| F13A-03 no URL/input budgets or normalization | NOTE | **CLOSED BY BUILDER** — budgets and normalization (D-76) before TASK-014 persists canonical queries |
| regression-environment clock (Docker wall clock moving backwards) | NOTE | environment, not code; JWT validation unchanged |

## PR-001 → PR-001A → PR-001R — targeted runtime & CI repair (2026-09-28, builder)

History: PR-001 candidate `4416e2b14b007ba50aab41cad8e23deea32c4678` →
independent **PR-001A** (Codex): **PR_001_REQUIRES_TARGETED_FIXES**, P0 0 /
P1 0 / P2 4 / P3 7 → **TARGETED FIX REQUIRED** → PR-001R on
`claude/PR-001R-runtime-ci-repair`, **pending narrow re-audit (PR-001RA)**.
[Archived verbatim](../reviews/2026-09-28-pr001a-codex-pr001-audit.md); [verdict record and disposition](../reviews/2026-09-28-pr001a-verdict-record.md).
**PR-001 is NOT accepted. Production: NOT READY, NOT DEPLOYED.**

| Finding | State after PR-001R |
|---|---|
| F1 unhandled 500 loses request id (P2) | **CLOSED BY BUILDER** — caught in the outermost middleware: generic 500 + `X-Request-ID`, logged once under the id |
| F2 CI audits an unpinned resolution (P2) | **CLOSED BY BUILDER** — `pip-audit -r constraints.txt --no-deps --disable-pip`; installed set proven equal to the pins; canary must be flagged |
| F3 missing ENV fails open as local (P2) | **CLOSED BY BUILDER** — image `ENV=production`; implicit `local` announced |
| F11 readiness hangs on a warm pool (P2) | **CLOSED BY BUILDER** — fresh dedicated connection under a wall-clock deadline; proven on real PostgreSQL incl. frozen-after-warm-pool |
| F4 dev DATABASE_URL guard exact-string | **CLOSED BY BUILDER** — parsed-URL rules, documented guarantee |
| F5 Alembic wipes logging | **CLOSED BY BUILDER** |
| F6 backlog alert × replicas; worker-death claim | **CLOSED BY BUILDER** — `max by (status)`; claim removed; heartbeat → observability track |
| F7 restore drill can skip in CI | **CLOSED BY BUILDER** — `HOMIES_REQUIRE_RESTORE_DRILL=1` |
| F8 runtime drift | **CLOSED BY BUILDER** — image asserts 3.12; Dependabot ignores python minor/major |
| F9 canonical TASK-012 heading lost | **CLOSED BY BUILDER** — restored byte-identical to `879bf56` |
| F10 main CI runs cancelled | **CLOSED BY BUILDER** — per-commit group on `main` |
| N1 / N5 / N7 | **CLOSED BY BUILDER** — `fullmatch`; README stack; real 429 test |

## PR-001 — CI, runtime & production-readiness baseline (2026-09-28, builder)

Independent engineering track on the accepted `879bf56` (no TASK-013/014
code). **Production: NOT READY, NOT DEPLOYED.** Measured baseline and gaps:
[docs/production/PRODUCTION-READINESS.md](../production/PRODUCTION-READINESS.md).

| Area | State after PR-001 |
|---|---|
| Python 3.12 | verified: full SQLite + full PostgreSQL/PostGIS suites green in `ops/test/Dockerfile.py312` |
| dependencies | `backend/constraints.txt` pins the verified set for CI, test and production images |
| CI | also runs on `claude/**` pushes (before: no Phase-1A commit ever triggered CI); single-head and PG/PostGIS version gates |
| logging | entry-point logging (text/JSON), request id on records and responses |
| config | production-like env refuses the development `DATABASE_URL`; Redis/Meilisearch/NATS removed |
| monitoring | outbox backlog alert (promtool-tested) |
| restore drill | Phase-1A backup→destroy→restore drill in CI |
| open decisions | RPO/RTO; alert destination; schema-compatibility policy for rollback/rolling deploys; hosting |

## TASK-013 — search, map & marketplace discovery (2026-09-28, builder)

**CLOSED BY BUILDER — PENDING ADJUDICATION / AUDIT.** Starts from the
accepted TASK-012 slice `879bf56`. [Contract](../tasks/TASK-013-search-map-marketplace-discovery.md).

| Area | Classification | State |
|---|---|---|
| discovery query (`properties/search.py`) | **CANONICAL_ACTIVE (candidate)** | one `SearchQuery` for list and map; D-68 |
| public map (`GET /v1/classifieds/map`) | **CANONICAL_ACTIVE (candidate)** | light projection, public point only, cap 500, with/without-point counts |
| public place N+1 | **CLOSED** | 10/49/105 SELECTs (limit 1/10/24) at `879bf56` → 8/9/9 |
| provider / agency-fee facets | **deferred** | needs canonical `provider_legal_party_id` and a recordable agency fee |
| clustering | **deferred** | public grid points; client-side clustering; server-side when evidence demands |
| dedicated search infrastructure | **not introduced** | D-74 |

## TASK-012 — ACCEPTED (2026-09-28)

History: TASK-012 `c4c8bfa` → **TASK-012A**: TASK_012_REQUIRES_TARGETED_FIXES
(F12A-01, P2) → **TASK-012R** `879bf56` → **TASK-012RA**:
**TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES**, F12A-01 CLOSED, P0–P3 0 →
**TASK_012_PHASE_1A_SLICE_ACCEPTED at `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`**
(D-75; [archive](../reviews/2026-09-28-task012ra-codex-task012r-audit.md)). Not
production readiness. Production: NOT DEPLOYED.


## TASK-012 → TASK-012A → TASK-012R — UTC temporal repair (2026-09-27)

History: TASK-012 candidate `c4c8bfac7f59a0930d9403d1100f35dccf003ae6` →
independent **TASK-012A** (Codex): **TASK_012_REQUIRES_TARGETED_FIXES**, P0 0 /
P1 0 / **P2 1** / P3 0 ([archived verbatim](../reviews/2026-09-27-task012a-codex-task012-audit.md)).
Accepted by the audit: concurrency, migration, quality, privacy/security (and
NULL availability, CAS updates). Needs fix: freshness, public visibility,
availability (UTC date), events (dedup) — one grouped finding:

| Finding | Severity | State |
|---|---|---|
| F12A-01 session-TimeZone-dependent temporal invariants: (A) DST moves the 14/21-day lines, (B) move-in NOW/FROM_DATE on the session date, (C) one reminder cycle emitted twice across zones | P2 | **CLOSED BY BUILDER** (TASK-012R) — pending narrow re-audit |

Canonical temporal invariant: D-67 / 04a §20. **TASK-012 is NOT accepted.**
[Contract](../tasks/TASK-012R-utc-temporal-invariants.md). Production: NOT DEPLOYED.

## TASK-012 — listing freshness, availability, quality (2026-09-27, builder)

**CLOSED BY BUILDER — PENDING ADJUDICATION / AUDIT.** Starts from the
accepted TASK-010 slice `ed9cf1b`. [Contract](../tasks/TASK-012-listing-freshness-availability-quality.md).

| Area | Classification | State |
|---|---|---|
| freshness (`properties/freshness.py`) | **CANONICAL_ACTIVE (candidate)** | `last_confirmed_available_at` (04 §43); policy 14/7/21 days, derived `reconfirm_at`/`stale_at` (04a §18); one public-visibility rule on the DB clock, used by all seven public paths |
| listing lifecycle | **ADAPT** | adds canonical `stale`; status CHECK; confirm/reactivate endpoint; pause refuses archived. Lower-case status names still differ from 04's (Listing aggregate convergence, roadmap 1A-4) |
| freshness sweep | **CANONICAL_ACTIVE (candidate)** | idempotent, skip-locked conditional UPDATE; CLI + BackgroundWorker (off by default); no new scheduler stack |
| availability | **ADAPT** | existing `available_from` / `min_term_months` / `open_ended`; `PUT …/availability` with CAS; NULL = unknown (D-64); `maximum_lease_months`, `available_until` (04 §44) not built |
| owner quality guidance | **CANONICAL_ACTIVE (candidate)** | derived, deterministic, owner-only (`GET /v1/me/classifieds`) |
| reminder delivery | **not built** | events only (D-65) |

## TASK-010 — ACCEPTED (2026-09-27)

History: TASK-010 candidate `e87352a` → **TASK-011** (Codex):
TASK_010_REQUIRES_TARGETED_FIXES (GEO-01/02/03 P2; public EXACT decision) →
**TASK-010R** `ed9cf1b` → **TASK-011R** (Codex, narrow re-audit):
**TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES**, P0–P3 0, NOTE 2 →
**TASK_010_PHASE_1A_SLICE_ACCEPTED at `ed9cf1b49f70716bd214a3212b2e7497ca5078ec`**
(D-66; [archive](../reviews/2026-09-27-task011r-codex-task010r-audit.md)).
GEO-01/02/03 and PUBLIC_EXACT: **CLOSED**; private exact preservation,
migration, privacy boundary: **ACCEPTED**. Notes N11R-01/N11R-02 fixed in
TASK-012. Not production readiness. Production: NOT DEPLOYED.

## TASK-011 → TASK-010R — targeted geography/privacy repair (2026-09-26)

History: TASK-010 candidate `e87352a9862408e76e7ebee08b846dab728d4dac` →
independent **TASK-011** (Codex) → **TASK_010_REQUIRES_TARGETED_FIXES**
(P0 0 / P1 0 / P2 3 / P3 0; [archived verbatim](../reviews/2026-09-26-task011-codex-task010-audit.md)).
Gates: migration ACCEPTED, Europe-readiness ACCEPTED (data model only),
classification ACCEPTED, doctrine ACCEPTED; privacy boundary NEEDS_FIX
(EXACT decision), geography model NEEDS_FIX.

| Finding | Severity | State |
|---|---|---|
| GEO-01 contradictory admin area + locality-bound GeoArea accepted/published | P2 | **CLOSED BY BUILDER** (TASK-010R) — pending re-audit |
| GEO-02 valid reference names overflow compatibility columns → HTTP 500 | P2 | **CLOSED BY BUILDER** (TASK-010R) — pending re-audit |
| GEO-03 authoritative rename leaves public display/search stale | P2 | **CLOSED BY BUILDER** (TASK-010R) — pending re-audit |
| Public EXACT (inherited owner opt-in) | canonical decision | **ADJUDICATED: PROHIBITED** (D-58, 04a §16); implemented in TASK-010R — pending re-audit |

Structured-vs-legacy authority rule: D-57 / 04a §17. **TASK-010 is NOT
accepted yet**: it becomes acceptable only after a narrow independent
re-audit of the TASK-010R SHA. Foundation Baseline 002 unchanged and still
accepted. Production: NOT DEPLOYED. [Contract](../tasks/TASK-010R-geography-correctness-privacy.md).

| Area | Classification | State after TASK-010R |
|---|---|---|
| legacy location mirrors (`properties.city/district`, address typed text) | **ADAPT** (fallback only) | hold typed text only for a part the address does not reference; never read while a reference exists |
| public listing location | **CANONICAL_ACTIVE** | APPROXIMATE grid point or DISTRICT (no point); no public EXACT at API, code or DB level |

## TASK-010 — geography, address, classification (2026-09-25, builder)

**CLOSED BY BUILDER — PENDING ADJUDICATION** (ChatGPT/founder; targeted
independent audit recommended). [Contract](../tasks/TASK-010-geography-address-property-classification.md).

| Area | Classification | State |
|---|---|---|
| geography (`app/modules/geography`) | **CANONICAL_ACTIVE (candidate)** | Country (ISO alpha-2) → AdministrativeArea (any depth, country `kind_code`, cycle-proof trigger) → Locality; GeoArea search-area seam; GeoSource + GeoExternalRef for official ids; idempotent import seam; `/v1/geo` read API. PostGIS boundary/centroid columns exist, empty |
| addresses | **CANONICAL_ACTIVE (candidate)** | Structured, building-level, source-aware; Property-owned 1:1; unit on Property; exact point unchanged on Property. Existing properties backfilled UNSTRUCTURED (country PL, text as typed) — resolving them against reference data is future work |
| properties — classification | **CANONICAL_ACTIVE (candidate)** | category APARTMENT \| HOUSE + subtype; legacy `property_type` kept and mapped; ROOM refused; APARTHOTEL_UNIT fail-closed. Closes deviation #11 in substance (the legacy column remains) |
| properties — legacy location columns | **ADAPT** (deprecated, still written/read) | `city`/`district` mirror structured names; `municipality` optional |
| public listing DTO | **CANONICAL_ACTIVE** | adds `place` (country, areas, locality, search area); no street/building/unit/postal code |
| search | **ADAPT** | adds `country_code`, `admin_area_id` (descendants), `locality_id`, `geo_area_id`; no ranking, no full search engine |
| Building entity | **not built** (decision D-55) | the address model does not prevent one building → many apartments |
| Reference data | **not ingested** | no national dataset imported; only country PL and source namespaces are seeded |

Deviation #15 (structured address / geo areas): **closed by builder** in
substance; deviation #11 (property type + subtype): **closed by builder**,
legacy column retained. Both pending adjudication.

Foundation test-evidence debt (TASK-009 P3) is **retired for the three race
tests TASK-010 touched** (`test_publication_authority_race_pg.py`,
`test_publication_proof_replacement_pg.py`): commit order is now proven by
the paused publisher's transaction id (`pg_stat_activity.backend_xid`)
having ended when the competitor commits, alongside the unchanged
`pg_blocking_pids` and committed-state evidence. Still carrying the debt
(untouched by TASK-010, green): `test_membership_accept_race_pg.py`
(`finished == ["accept", "revoke"]`) and `test_publication_chain_gain_race_pg.py`
(branches on `order.index`). No foundation production code changed.

## 0000. State after TASK-007 and TASK-008 (2026-09-25)

The TASK-007 re-audit of `1b2458c` (report outside the repo) accepted N-02,
N-03 and N-04 and found **N-01 PARTIALLY_CLOSED** through a new finding,
N-05. **HOMIES FOUNDATION BASELINE 002 is a CANDIDATE — NOT YET ACCEPTED**;
it may be accepted only after an independent review of TASK-008. Production:
NOT READY, NOT DEPLOYED.

TASK-008 ([contract](../tasks/TASK-008-final-foundation-hardening.md)) repairs
the TASK-007 findings, each recorded on its own:

| Finding | Severity | What it was | Status |
|---|---|---|---|
| N-05 | P3 (Baseline-002 blocker) | A proof row deleted and re-inserted under the same key while its lock waited carried the decision unlocked | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** The decision is evaluated through the rows the locking statements actually returned; a replaced row → 409 with Retry-After |
| N-06 | P3 | `within` sub-restrictions of the protected evaluation were untested | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** Behavioural tests per load-bearing restriction; schema-implied ones reported as equivalent mutants |
| N-07 | P3 | The accept lock strength (FOR UPDATE) was not pinned by any test | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** Accept-vs-accept test: the second waits before acting on the row; no deadlock |
| N-08 | P3 | The final 403 of the protected decision was never executed | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** One interleaving, four outcomes (403/404/409/200) |
| N-09 | P3, pre-existing | `invite_member` could demote a concurrently ACTIVE member to INVITED | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** Row locked before read; only REVOKED → INVITED |
| N-10 | P3, pre-existing | Two concurrent first invitations → unhandled IntegrityError (500) | **CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW.** Savepointed INSERT; the loser decides on the winner's row (202) |

Publish 409 contract documented in OpenAPI; the retryable authority-change 409
alone carries `Retry-After: 0` (no machine-readable error-code convention
exists yet — recorded debt). Revoke starvation under a continuous stream of
publications resting on one row is carried as operational debt (TASK-007
note). Membership lifecycle as implemented (canon 04 §20 has no transition
table): none → INVITED; REVOKED → INVITED by explicit re-invitation; INVITED
and ACTIVE unchanged by an invitation.

## 000. State after TASK-005 and TASK-006 (2026-09-25)

The TASK-005 independent re-audit of `dfa3254` (report supplied by the
founder, kept outside the repo) concluded **F-04 CLOSED**,
**TASK_004_ACCEPTED_WITH_NONBLOCKING_NOTES** and
**C1_C8_FOUNDATION_ACCEPTED_FOR_CONTINUED_PHASE_1A_DEVELOPMENT**. `dfa3254`
is **HOMIES FOUNDATION BASELINE 001**. Production: NOT READY, NOT DEPLOYED.

TASK-005 raised four new findings. TASK-006
([contract](../tasks/TASK-006-authority-integrity-cleanup.md)) repairs them;
each is recorded on its own:

| Finding | Severity | What it was | Status |
|---|---|---|---|
| N-01 | P3 | A chain that became valid while publication waited for its locks was not locked, yet could carry the decision; its revoke then did not wait | **CLOSED BY BUILDER — PENDING REVIEW.** The protected decision is evaluated only through the locked proof rows; a chain gained during the wait gets 409 and is used by the next attempt |
| N-02 | P2 | `accept_invitation` (unlocked read-modify-write) could overwrite a committed membership revoke — ACTIVE with `revoked_at` set | **CLOSED BY BUILDER — PENDING REVIEW.** Row locked FOR UPDATE before it is read; accepted only while still INVITED |
| N-03 | P3 | Locks on `person_legal_parties`, `organization_legal_parties`, `representation_mandate_scopes`, `property_authority_scopes` were implemented but unproven by repository tests | **CLOSED BY BUILDER — PENDING REVIEW.** Both-order tests per row, waits attributed to the publisher's pid, mutants B01–B04 killed |
| N-04 | P3 | Tests built authorisation dates from the local `date.today()` while the rule is the UTC date; three failed nightly | **CLOSED BY BUILDER — PENDING REVIEW.** `tests/conftest.authorization_date()` (UTC) where the date means the authorisation date |

**UTC domain note.** Current technical rule: authority effective dates are
evaluated against the **UTC calendar date**. This remains a controlled
product/legal question for internationalisation (Polish civil date vs UTC); it
has not been changed.

Operational debt carried (TASK-005 notes, not changed): FOR SHARE on proof rows
makes cosmetic updates of those rows wait for an in-flight publication, and a
share request can queue behind a waiting UPDATE (head-of-line), never deadlock.

## 00. State after TASK-003 and TASK-004 (2026-09-24)

The TASK-003 Codex re-audit of `0d6c554` (report in the Codex evidence
directory, outside the repo) **accepted F-01, F-02, F-03, F-05, F-06, F-07,
F-08 and F-09 as CLOSED**, and found **F-04 PARTIALLY_CLOSED (P1)**: direct
authority revoke and space archive were serialised with publication, but a
membership revoke, mandate revoke, organisation suspension, legal-party
archival or mandate expiry could take effect after publication's last check
and the listing still went public.

**F-04: CLOSED BY BUILDER — PENDING CODEX RE-AUDIT** (TASK-004,
[contract](../tasks/TASK-004-atomic-publication-auth.md)). Publication now
makes its final decision through `authority.authorize_for_mutation`: under the
Property lock it locks every row of every currently valid chain `FOR SHARE`
and re-evaluates the chains on the database clock, in the same transaction as
the conditional status UPDATE. Any change to those rows — through the API, the
new service primitives `set_organization_status` / `set_legal_party_status`,
or raw SQL — commits before the decision (publication refused, or another
valid chain used) or waits for the publication to commit. Evidence:
`tests/test_publication_authority_race_pg.py` (both serial orders per loss,
lock waits via `pg_blocking_pids`, expiry, surviving chain, no scope
widening, negatives) and `scripts/mutation/task004_mutants.py`.

C2 and C6 remain PARTIALLY_VERIFIED in the TASK-003 matrix until TASK-005
accepts this repair.

## 0. State after TASK-002 (2026-09-24)

The independent TASK-001 audit of `988b31b` returned
`SAFE_TO_CONTINUE_WITH_BLOCKING_FIXES_IN_NAMED_CONTEXTS` (P0 0, P1 5, P2 4).
TASK-002 ([contract](../tasks/TASK-002-foundational-repair.md)) repaired each
finding on branch `claude/TASK-002-foundational-repair`. **Closed by Claude
with regression tests; an independent Codex re-audit of the exact SHA is still
required before the closures count as accepted** (05 §9).

| Finding | Repair | Regression evidence |
|---|---|---|
| F-01 P1 legacy runtime active | `app/composition.py` — `create_phase1_app()` routes no short-stay/booking/payment/host-payout/legacy-admin endpoint and starts only the notification worker; legacy composed only by `tests/legacy_runtime.py` | `test_phase1_runtime.py` (real app: routes, OpenAPI, 18 representative legacy requests → 404, lifespan workers, fresh interpreter loads no legacy module); `test_phase1_boundaries.py` (static, incl. `from .. import x`, importlib) |
| F-04 P1 publish after revoke | Property row = coordination lock for publish, revoke, space archive; re-check under lock; conditional status UPDATE | `test_publication_race_pg.py` (revoke between check and write → refused; revoke during publish → waits, then pauses; archive likewise; archived not republished) |
| F-02 P1 media metadata leak | Pillow decode → budget → orientation → sRGB → fresh image from pixels → re-encode → re-decode; old C8 files quarantined (`processing_version`) until reprocessed | `test_media_regressions.py` (TASK-001's four JPEG variants + PNG iCCP through upload → approval → attach → anonymous GET), `test_media_pipeline.py` (real-image corpus, 400 mutations) |
| F-05 P1 unbounded body | Incremental read abandoned past the limit; decoding under a per-process slot budget | `test_media_regressions.py::test_f05_*` (chunked, false Content-Length, over HTTP) |
| F-03 P1 contact quota race | Per-viewer `users` row lock (FOR NO KEY UPDATE) around repeat check, count, insert | `test_concurrency_r4_pg.py::test_f03_*` |
| F-06 P2 viewing resurrection | Row re-read under lock + conditional UPDATE on (status, version); lock order settings → viewing; CHECK `ck_viewings_cancelled_state` | `test_concurrency_r4_pg.py::test_f06_*`, `::test_no_viewing_is_ever_confirmed_with_a_cancellation_time` |
| F-07 P2 invalid coordinates | API finite/range/pair validation; DB CHECKs on exact and public point; preflighting migration; grid edge fix | `test_coordinates.py`, `test_coordinates_pg.py` (constraint names + SQLSTATE, migration refuses to guess) |
| F-08 P2 DST slot outside window | One wall time → one instant or not offered; real local end inside window | `test_viewing_dst.py` (Warsaw winter, summer, spring-forward, fall-back) |
| F-09 P2 conversation race | Per-sender lock; partial UNIQUE on active (listing, requester); lost insert continues the thread | `test_concurrency_r4_pg.py::test_f09_*` |
| §13 false-positive test | Negative-price test uses valid FKs, a control row, and asserts the CHECK by name/SQLSTATE | `test_pricing_pg.py::test_a_negative_price_never_reaches_a_row` |

Operational migration gate: [MIGRATION-ROLLOUT.md](../database/MIGRATION-ROLLOUT.md).

## 1. State preserved in TASK-000

Before this task the shared checkout held 159 uncommitted foreign paths
(10 modified tracked files, the rest untracked), last written 2026-09-24
12:19 by another agent session. They were preserved **losslessly** into local
branches, verified blob-for-blob against the files on disk (0 mismatches),
then removed from the `main` working tree:

| Branch | Commit | Content |
|---|---|---|
| `reference/ts-drizzle-schema-v1` | `605cee33bbab507c0d51b70f44842139d11db697` | TypeScript/Drizzle Schema v1 package, its ADRs, evidence, ERD, inventory, the verbatim spec, compose file, and its CI job |
| `preserve/foreign-continuity-2026-09` | `a68496a293904bf6c204376708b5fffdb774230c` | Continuity docs (AGENTS.md, CONTINUITY.md), edits to CLAUDE/README/RELEASE/DEVLOG/PROJECT_*/api/design docs, Claude Design exports, dated design references, 2026-09-13 audit and probes, `ops/scripts/check_context.py` |
| `preserve/worktree-snapshot-2026-09-24` | `51b7bba4c8871663822ee65716cb90eaf2b1ef5e` | All 159 paths in one commit — the lossless fallback independent of classification |

`packages/database/node_modules` was excluded by the package's own
`.gitignore` and is reproducible from `package-lock.json`. The branches are
**local only**; pushing them (the repository is public) is the founder's call.

Restore everything as it was: `git checkout preserve/worktree-snapshot-2026-09-24 -- .`
(then `git reset` to unstage).

Authorship of the preserved work cannot be attributed with certainty. By
content it came from at least two sessions other than this Claude Code
session: the 2026-09-13 integration audit, and the 2026-09-23/24 TypeScript
Schema v1 implementation (whose DEVLOG entry also records a fix to Claude's
Python code — see §6).

## 2. C1–C8 port — status

All SHAs verified unique; CI (5 jobs: backend, contracts, monitoring,
secrets, image) green on each.

| Cycle | Commit | Scope | Status |
|---|---|---|---|
| C1 | `c3ab28c83528a86b1822ed6f0b73827ddaa4941f` | Money → bigint; public listing drops `owner_id` | Candidate — audit |
| C2 | `49641c0df8669adfbae6262199babf32aab6803b` | LegalParty, PropertyAuthority, authorisation service, verified-publish gate | Candidate — **high-risk audit** (authorisation, data migration) |
| C3 | `903312cd7acb5f42e550b351032d39cf5920e3eb` | Space; composite FK listing→space→property | Candidate — audit (data migration) |
| C4 | `dba093a6c3a6642d9ed9f316a293a5c16b99905f` | Temporal price components; summaries; optimistic concurrency | Candidate — **high-risk audit** (data migration, concurrency) |
| C5 | `1cf8130643b935277e2ea570884d8dd9733d4b73` | PostGIS; private exact location; public grid point; map search | Candidate — **high-risk audit** (exact address) |
| C6 | `24b18572e79570d89190f93930f0c644b843cdb3` | Organizations, memberships, mandates; three authority chains | Candidate — **high-risk audit** (authorisation) |
| C7a | `62a4add8fd338123b5e905157d3c279f46fdf392` | Conversations, messages | Candidate — audit; **mixed provenance, see §6** |
| C7b | `08fc99c484a4a17aaba9630c207f3a56da352d3e` | Viewing scheduler | Candidate — **high-risk audit** (concurrency/locking) |
| C8 | `782c833f100f1bf2e86888b664c9b30b27cbc1dd` | Files, media, moderation, sanitiser | Candidate — **REQUIRES_CODEX_SECURITY_AUDIT** (§5) |

TASK-001 verdicts at `988b31b` (Codex, independent): C1 VERIFIED · C2
PARTIALLY_VERIFIED (F-04) · C3 VERIFIED · C4 VERIFIED · C5 PARTIALLY_VERIFIED
(F-07) · C6 VERIFIED · C7a PARTIALLY_VERIFIED (F-09) · C7b PARTIALLY_VERIFIED
(F-06, F-08) · C8 BLOCKED (F-02, F-05). "VERIFIED" means the cycle's implemented
invariants held under test, not full Domain Schema parity or production
approval. Every PARTIALLY/BLOCKED item was repaired in TASK-002 (§0) and
awaits the targeted re-audit.

## 3. Areas

| Area | Current purpose | Canonical relevance | Decision | Reason | Next action | Risk if unchanged |
|---|---|---|---|---|---|---|
| identity (users, auth, phone/email verification, legal parties) | Accounts, JWT, verification codes, PERSON parties, legal identity | Phase 1A core | **CANONICAL_ACTIVE** | Matches User ≠ LegalParty | Audit C2; add audit actor type | Low |
| properties (Property, authority) | Physical object; authority chain; verified publish | 1A core | **ADAPT** | Chain matches canon; `owner_id`, free-text address, rich `property_type` do not | Structured address, type + subtype, deprecate `owner_id`, evidence record | Address/type drift hardens as data grows |
| spaces | WHOLE_PROPERTY / ROOM, composite FK | 1A core | **CANONICAL_ACTIVE** | Matches 04 §28 | Audit C3 | Low |
| listings / classifieds (`classified_offers`) | The LONG_TERM listing on the free board | 1A core | **ADAPT** | Physical name "offer"; public API says "classifieds"; no texts/terms/status history/freshness/eligibility service; ≥6-month rule (§7 decision) | Listing aggregate convergence task | Terminology and missing freshness block 1A completeness |
| pricing | Components with history, summaries, version check | 1A core | **CANONICAL_ACTIVE** | Matches 04 §46–§47 | Audit C4 | Low |
| geolocation | Private exact point, public grid point, bbox/radius | 1A core | **CANONICAL_ACTIVE** (address model ADAPT) | Privacy split matches 04 §80; coordinates finite/in range/paired at API and DB since TASK-002 (F-07) | Structured address + geo areas | Address not structured |
| organizations | Workspace, ORGANIZATION party, memberships | 1A basics | **ADAPT** | `organization_legal_parties.organization_id` is UNIQUE → hard 1:1, contrary to 04a §1 | Multi-relationship with one active primary | Agencies with several legal entities cannot be modelled |
| mandates | Person-to-user representation | 1A | **CANONICAL_ACTIVE** | Self-granted mandate accepted (04a/§20) | Audit C6 | Low |
| engagement — messages | Conversations, participants, messages, lead stage | 1A core | **CANONICAL_ACTIVE** | `requester_user_id` accepted; one active thread per requester+listing enforced by lock + partial UNIQUE (TASK-002, F-09) | Attachments (dev. 20); re-audit | Low once re-audited (TASK-000's "Low" was optimistic — F-09) |
| engagement — viewings | Windows, blackouts, slots, confirm under lock | 1A core | **CANONICAL_ACTIVE** | Matches 04 §57–§60; transitions conditional under row lock, DST-unique slots (TASK-002, F-06/F-08) | Re-audit | Low once re-audited (TASK-000's "Low" was optimistic — F-06/F-08) |
| media | File objects, assets, moderation, listing media, processing | 1A core | **ADAPT** | Custom walker replaced by Pillow decode/re-encode with pixel budget and streaming ingress (TASK-002 R3); old files quarantined; no derivatives yet | Re-audit R3; derivatives (dev. 21); isolated processing when derivatives/scale justify it | Decoder attack surface remains (Pillow, libjpeg, zlib, lcms2) — keep pip-audit and version floor current |
| contact reveal + reveal quota | Verified-phone gated disclosure of owner phone | 1A (trust/anti-scrape) | **CANONICAL_ACTIVE** | Supports trust; quota serialised per viewer since TASK-002 (F-03 — TASK-000's "None now" was wrong); unit = listing | Re-audit; later decide provider/number as quota unit | Phone path unusable in prod without SMS |
| attribute catalogue | Amenity definitions, filters | 1A | **ADAPT** | 04 §34–§35 models amenities as table + join rows; current is JSON attributes validated by catalogue | Reconcile with `property_amenities` | Filter/index shape diverges from 04 |
| trust (verification records, reports, moderation decisions, incidents) | Only media moderation and admin authority verify/revoke exist | 1A basics | **ADAPT** | Evidence record, reports, decisions missing | Trust tasks | Moderation has no audit trail of decisions |
| safety | Nothing | 1A foundation | **UNKNOWN → build** | Not implemented | Safety foundation task | Canon principle 2 unmet |
| admin | Users, audit, notifications, authority and media moderation | Phase 1 | **CANONICAL_ACTIVE** (Phase-1 part) | Split in TASK-002 R1: `admin/router.py` is Phase-1 only; bookings/payments/ledger/KPI/incidents moved to `admin/legacy.py` (LEGACY_DORMANT, not routed) | Next.js admin app later | — |
| events (outbox, notifications, worker) | Transactional outbox + delivery | Canonical async pattern (03 §5) | **CANONICAL_ACTIVE** (ADAPT for event catalogue) | Matches 03 | Outcome events for 1A domain | Analytics lacks server-side outcomes |
| audit log | Append-only audit rows | Cross-cutting | **ADAPT** | `actor` is free text ("system") — no USER/SYSTEM/SERVICE type (04a §5) | Audit actor task | Automated actions indistinguishable |
| rate limiting | Token buckets per policy | Cross-cutting | **CANONICAL_ACTIVE** | In-process store; Redis not required | None | Multi-instance multiplies limits (documented) |
| booking | Short-stay bookings, availability, expiry | Phase 3 | **LEGACY_DORMANT** — runtime-isolated since TASK-002 R1 (TASK-000's dormant label was not true at runtime: F-01) | Authorises by `listings.host_id`, not PropertyAuthority | Do not extend; KEEP/ADAPT/REWRITE audit before Phase 3 | Accidental extension into 1A |
| listings (short-stay `listings` module) | Nightly listings, host blocks | Phase 3 | **LEGACY_DORMANT** — runtime-isolated (TASK-002 R1) | Same `host_id` gap | As booking | As booking |
| payments | Stripe seam, webhooks, disputes, reconciliation; host payout onboarding (`identity/host_payouts.py`) | Phase 2+ | **LEGACY_DORMANT** — runtime-isolated (TASK-002 R1) | Phase 1 has no payments | Audit before Phase 2 | Stripe pulled into Phase 1 by habit |
| ledger | Append-only double-entry | Phase 2+ | **LEGACY_DORMANT** (engineering REFERENCE for Phase 2) | Proven, but Phase 2 needs its own spec | Audit before Phase 2 | — |
| DB role / privileges (`backend/app/core/sql/app_role.sql` (+ `app_grants.sql`)) | App role without ledger UPDATE/DELETE | Cross-cutting | **CANONICAL_ACTIVE** | Preserved engineering (03 §11) | Extend to new append-only tables (audit, moderation decisions) | — |
| backup / restore drill | CI restore cycle, DR scripts | Cross-cutting | **CANONICAL_ACTIVE** | Preserved engineering | Offsite target needs an account | — |
| monitoring (Prometheus rules, alertmanager) | Metrics + alert tests | Cross-cutting | **CANONICAL_ACTIVE** | Cheap and tested | — | — |
| Redis | — | Not Phase 1 (03 §7) | **REMOVED** from compose and config (PR-001) | No code used it | — | — |
| Meilisearch | — | Not Phase 1 (03 §6) | **REMOVED** from compose and config (PR-001) | Unused | — | — |
| NATS | — | Not Phase 1 (03 §5) | **REMOVED** from compose and config (PR-001) | Unused | — | — |
| `infra/{helm,k8s,terraform}`, `data/{airflow,dbt,ml}`, `apps/` | Empty local directories (not tracked by git) | Deferred (03 §8) | **REMOVE_LATER** | Contain nothing | Delete locally when convenient | None |
| design system (`frontend/design-system`) | Tokens, components, mobile CSS | Visual source material | **REFERENCE_ONLY** (visuals) | Colour, type, spacing, components worth keeping; not business behaviour | Reuse in Next.js/Expo work | Old booking/payment flows copied as behaviour |
| Claude Design exports, dated references | Prototype screens incl. booking/payment flows | Visual source only | **REFERENCE_ONLY** — on `preserve/foreign-continuity-2026-09` | Business flows there are obsolete | Redesign screens against 1A flows | Same |
| TypeScript/Drizzle package | Literal Schema v1 implementation, 57 tables, 17 DB tests, 100k benchmark | Parity oracle (03 §9) | **REFERENCE_ONLY** — on `reference/ts-drizzle-schema-v1` | Never a runtime | Use for parity checks during the audit | Mistaken for a second backend |
| `ops/scripts/check_context.py` | Reference-integrity check for docs | Tooling | **UNKNOWN** — preserved, not on main | Written for the pre-canonical doc set | Founder decides whether to restore and adapt it | None |
| `docs/strategy/*`, `docs/business/*`, `PROJECT_CHARTER`, `PRODUCT_MODEL`, `RELEASE_PLAN`, `RELEASE.md` | Managed-hospitality era strategy and plans | Historical (00-AUTHORITY) | **REFERENCE_ONLY** — banner added | Superseded by 01–03 | — | Read as current strategy |

**Boundary enforced in TASK-000:** a test (`tests/test_phase1_boundaries.py`)
fails if any Phase-1 module (properties, engagement, media, identity) imports
booking, payments, ledger or the short-stay listings module.

**TASK-001 showed that static test was not enough** (F-01: the modules were
still routed and started from `main`). Since TASK-002 R1 the authoritative
check is the composed application itself (`tests/test_phase1_runtime.py`);
the static scan was widened to main, composition, admin, events and core and
now also sees `from .. import x` and literal importlib calls. It still cannot
see computed dynamic imports — the runtime test covers that.

## 4. The 22 port deviations — disposition

Source: [SCHEMA-v1-PORT.md](../database/SCHEMA-v1-PORT.md) (history kept as
written). Dispositions per founder instruction 2026-09-24 §20.

| # | Deviation | Disposition | Note |
|---|---|---|---|
| 1 | FastAPI/SQLAlchemy/Alembic instead of Drizzle/Fastify | **ACCEPTED** | 03 §2 |
| 2 | Single `public` schema, ownership by module | **ACCEPTED** | Logical bounded contexts in code |
| 3 | varchar(36) uuid4 ids, no uuidv7 | **CONTROLLED_DEBT** | Normalise by deliberate migration; tied to PG upgrade trigger |
| 4 | PostgreSQL 16 + PostGIS 3.4 | **CONTROLLED_DEBT** | Revisit trigger 03 §10 |
| 5 | Legal names nullable until verification | **ACCEPTED** | 04a |
| 6 | Authority verification = state + audit, no evidence record | **MUST_CLOSE** | 04a §9 — before authority verification is production-complete |
| 7 | Append-only triggers + DB privileges kept | **ACCEPTED** | Defence in depth |
| 8 | Short-stay retained; authorised by `host_id` | **FROZEN_UNTIL_PHASE** (3) | Plus MUST_CLOSE before any reactivation: move to PropertyAuthority. Since TASK-002 R1 the frozen code is not routed or started by the Phase-1 app (TASK-001 had shown it was) |
| 9 | Mixed status casing | **CONTROLLED_DEBT** | — |
| 10 | `properties.owner_id` kept as creator | **MUST_CLOSE** | Deprecate; migrate to `created_by_user_id`; never authorisation (verified: authority service does not read it) |
| 11 | Six lower-case property types; `room` closed | **MUST_CLOSE** | APARTMENT \| HOUSE + subtype. Decided 2026-09-24 (04a §13): `aparthotel_unit` = APARTMENT/APARTHOTEL_UNIT; its publication fails closed since TASK-002. The type/subtype migration itself is a separate bounded task |
| 12 | `properties.area_m2` integer | **CONTROLLED_DEBT** | — |
| 13 | `classified_offers` physical name | **CONTROLLED_DEBT** | Public API/domain language must still converge on Listing |
| 14 | Only rent/fees/utilities/parking/deposit writable | **FROZEN_UNTIL_PHASE** (1B for SALE_ASKING_PRICE) | Other component types when their features exist |
| 15 | No structured address / geo_areas | **MUST_CLOSE** | 04a §8 — before marketplace/search/geography is complete |
| 16 | Fixed-grid approximate public point | **ACCEPTED** | — |
| 17 | Self-granted mandate ACTIVE+VERIFIED | **ACCEPTED** | Requires authenticated principal, authorisation and audit — all present |
| 18 | No organisation-principal mandates; org registration unchecked | **FROZEN_UNTIL_PHASE** (1.5) for org mandates; registration check folds into #6 evidence work | — |
| 19 | `requester_user_id` on conversations | **ACCEPTED** | — |
| 20 | No message attachments | **MUST_CLOSE** | 04 §56 is Phase-1 schema; low priority, needs private file access |
| 21 | No media variants; PHOTO/FLOOR_PLAN only | **MUST_CLOSE** | 04a §11 — derivatives before public scale |
| 22 | Synchronous in-request image processing | **MUST_CLOSE → repaired, pending re-audit** | TASK-002 R3: maintained library (Pillow) with explicit budget, worker thread under a concurrency slot budget. Isolated processing deferred to the derivatives task |

## 5. C8 security flag

**Superseded by TASK-002 R3.** TASK-001 confirmed the concerns below (F-02,
F-05) and recommended `REPLACE_WITH_MAINTAINED_LIBRARY`, which R3 did. The
replacement pipeline itself requires the targeted re-audit. Original flag:

**REQUIRES_CODEX_SECURITY_AUDIT.** The custom JPEG/PNG structure walker in
`backend/app/modules/media/sanitize.py` is not approved for production
untrusted-binary processing because its mutation tests are green. The audit
must consider: malformed images; parser differentials (what browsers and
other decoders accept that the walker does not, and vice versa); resource
exhaustion (memory/CPU bounds; the 10 MB body is read fully into memory);
metadata leakage (EXIF, XMP, IPTC, ICC, PNG text); polyglots; unsupported
formats (WebP, HEIC, GIF are refused); MIME confusion; and whether a
maintained library or isolated service is preferable. Known facts for the
auditor: no pixel decoding happens; APP2 (ICC) and APP14 are kept; JPEG data
after SOS is copied verbatim up to a required trailing EOI.

## 6. Provenance incident — commit `62a4add` (C7a)

The committed `_out()` in `backend/app/modules/engagement/router.py` is not the
version Claude wrote. Another session working in the same checkout replaced
Claude's version (which had 10 mypy errors) with a `model_validate` form; the
fix was present in the working tree when Claude staged the file, so it entered
Claude's commit without attribution. Claude's report at the time attributed the
transient mypy errors to a stale cache — that was wrong; they were real errors,
fixed by the other session. The committed code is correct and tested. The rule
that prevents a repeat is [05 §4](05-DEVELOPMENT-GOVERNANCE-v1.md).

## 7. CANONICAL DECISION REQUIRED

**Both decided by the founder on 2026-09-24 (TASK-002 §23–§24)** and recorded
in [04a §12–§14](04a-DOMAIN-SCHEMA-v1-CLARIFICATIONS.md): LONG_TERM has no
six-month floor (option B); `aparthotel_unit` is an APARTMENT subtype whose
publication fails closed pending a residential-use policy (neither option A
nor C as written — LEGAL/POLICY REVIEW REQUIRED). The records below are kept
as raised.

```text
CANONICAL DECISION REQUIRED — LONG_TERM minimum term vs MONTHLY
Canonical rule:         02 §1–§2: Phase 1A is a LONG_TERM marketplace; MONTHLY
                        is Phase 2 (transactional). The canon defines no minimum
                        lease for LONG_TERM; 04 §44 has minimum_lease_months
                        nullable.
Current implementation: backend/app/modules/properties/models.py:125
                        MIN_CLASSIFIED_TERM_MONTHS = 6, enforced in
                        properties/schemas.py:167; a shorter minimum term is
                        refused with "Shorter stays are booked through Homies"
                        — a product that does not exist in Phase 1A.
Alternatives:           A. Keep ≥6 months as the LONG_TERM floor (the earlier
                           PRODUCT_MODEL rule).
                        B. Allow any minimum term on LONG_TERM listings in 1A;
                           MONTHLY becomes purely the transactional product.
                        C. Another floor (e.g. 3 months, or 12 by default).
Recommended:            B, pending legal view — without Phase-2 payments a
                        4-month rental has nowhere to go, and refusing it
                        loses inventory for no user benefit.
Consequences:           A keeps today's behaviour but turns away real 1A
                        inventory. B needs the refusal and its message changed
                        and the MONTHLY/LONG_TERM distinction redefined as
                        transactional-vs-not. C is A with a different number.
```

```text
CANONICAL DECISION REQUIRED — subtype for aparthotel_unit
Canonical rule:         04a §7: APARTMENT | HOUSE + subtype; aparthotel_unit must
                        not pull hospitality inventory into Phase 1.
Current implementation: PROPERTY_TYPES includes "aparthotel_unit".
Alternatives:           A. APARTMENT + subtype APARTHOTEL_UNIT, allowed only on
                           LONG_TERM listings.  B. Drop the value; existing
                           rows reclassified to APARTMENT.  C. Keep, but block
                           listing until Phase 3.
Recommended:            A — the flat exists and can be let long-term; the rule
                        that matters is the rental mode, not the building type.
Consequences:           A needs a subtype column and a mapping migration.
                        B loses information. C strands existing properties.
```

## 8. Canonical gaps still open (Phase 1A)

Not implemented, or not to canon: structured address + geographic areas;
property type + subtype; listing texts (multilingual), rental terms table,
sale terms, listing status history, freshness (reconfirm/stale/expiry),
publication eligibility service; saved property; saved search; reports,
moderation decisions, incidents; trust verification records (identity,
business, authority evidence); safety profile, requirements, hazards,
versioned attestations; EPC; buildings, house details, property ownership
history; versioned legal-document acceptance; marketing consent separate
from notification preferences; notification preferences, push devices;
audit actor type; outcome events for analytics; message attachments; media
derivatives; Organization ↔ LegalParty multi-relationship.

**Full parity with Domain Schema v1 is not achieved.** The port covers the
identity/authority core, spaces, pricing, location privacy, organisations and
mandates, messaging, viewings and media.
