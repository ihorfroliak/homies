# Implementation convergence map

Where the existing implementation stands against the canonical documents, as
of TASK-000 (2026-09-24). Baseline: `main` at
`782c833f100f1bf2e86888b664c9b30b27cbc1dd`. Nothing here is accepted merely
because it is committed: the C1–C8 port is a **candidate** pending independent
audit ([05 §9](05-DEVELOPMENT-GOVERNANCE-v1.md)).

Classifications: **CANONICAL_ACTIVE** · **ADAPT** · **LEGACY_DORMANT** ·
**REFERENCE_ONLY** · **REMOVE_LATER** · **UNKNOWN**.

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
| DB role / privileges (`ops/sql/app_role.sql`) | App role without ledger UPDATE/DELETE | Cross-cutting | **CANONICAL_ACTIVE** | Preserved engineering (03 §11) | Extend to new append-only tables (audit, moderation decisions) | — |
| backup / restore drill | CI restore cycle, DR scripts | Cross-cutting | **CANONICAL_ACTIVE** | Preserved engineering | Offsite target needs an account | — |
| monitoring (Prometheus rules, alertmanager) | Metrics + alert tests | Cross-cutting | **CANONICAL_ACTIVE** | Cheap and tested | — | — |
| Redis | Compose service; config key; unused by code | Not Phase 1 (03 §7) | **LEGACY_DORMANT** → **REMOVE_LATER** from compose | No code uses it | Drop from compose when compose is next touched | Local dev starts an unused service |
| Meilisearch | Compose service; config key; unused | Not Phase 1 (03 §6) | **LEGACY_DORMANT** → **REMOVE_LATER** from compose | Unused | As Redis | As Redis |
| NATS | Compose service; config key; unused | Not Phase 1 (03 §5) | **LEGACY_DORMANT** → **REMOVE_LATER** from compose | Unused | As Redis | As Redis |
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
