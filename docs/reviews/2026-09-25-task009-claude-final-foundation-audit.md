# TASK-009 — Claude Code final independent foundation audit (archived)

> **Archived verbatim** in TASK-010 (2026-09-25) so the audit outcome does not
> live only in agent session history. Nothing below the provenance block was
> edited, summarised or reconstructed. Links and paths inside the report point
> to the auditor's evidence outside the repository and may not resolve here.

| Field | Value |
|---|---|
| Auditor | Claude Code (independent session, did not build TASK-008) |
| Audit | TASK-009 — Final Independent Foundation Audit |
| Audited SHA | `36231840ee52d6185e73fda07e54eab33ffe41f3` |
| Verdict | `TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES` · `HOMIES_FOUNDATION_BASELINE_002_ACCEPTED` |
| Section A source | `C:/Users/ihorf/Projects/homies-audit-evidence/TASK-009/FINAL-REPORT.md` |
| Section A SHA-256 (as archived) | `ffc44d547840ad573fd8847301c5a4c46775e7ca060c7602a7d49e9df954302d` |
| Section B source | last assistant message of the Claude Code audit session, 2026-09-25T14:14:10Z (summary of Section A) |
| Section B SHA-256 (as archived) | `3060f03ad248047f4c0d290ec76e1e3670b1f687a91331f347bf60337acd1aa3` |
| Session | `Claude Code session 7251f4fb-69eb-4ef2-ab71-741ca99cee4f` |

Adjudication: the founder, with ChatGPT, accepted Foundation Baseline 002 on
the basis of this report and its independent counterpart — see
[IMPLEMENTATION-CONVERGENCE](../canonical/IMPLEMENTATION-CONVERGENCE.md).

---

## Section A — full report file (verbatim)

# TASK-009 FINAL INDEPENDENT FOUNDATION AUDIT

Project: Homies · Audited SHA `36231840ee52d6185e73fda07e54eab33ffe41f3` · Date 2026-09-25
Evidence root: `C:\Users\ihorf\Projects\homies-audit-evidence\TASK-009\` (raw outputs in `out\`, probe sources in `probes\`)

## EXECUTIVE VERDICT

TASK-008 does what it claims for N-05, N-07, N-08, N-09 and N-10, verified independently on real
PostgreSQL 16.4 / PostGIS 3.4.3 with raw-SQL races. The decision set is built from the rows the locks
returned, and pgrowlocks shows it equals the row locks the backend actually holds in every case.
One NEW FINDING (P3): three of the four "expected equivalent" mutants (E01, E02, E03) are **not**
equivalent. Each restriction they remove carries weight, and removing it gives a forbidden 200 through an
unlocked row. No repository test fails without them. The audited code keeps all three, so this is a
test and documentation gap, not a live defect. N-06 = PARTIALLY_CLOSED. No regression of N-01, N-02 or
F-04. No P0, P1 or P2.

**TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES · HOMIES_FOUNDATION_BASELINE_002_ACCEPTED (SHA 36231840ee52d6185e73fda07e54eab33ffe41f3)**

## INDEPENDENCE

YES. This audit ran in a fresh Claude Code session (7251f4fb) that did not build or edit TASK-008 or any
earlier task. Builder claims were treated as hypotheses. The core outcomes were reproduced with my own
probe harness, written for this audit: a direct decision thread, raw-SQL holds, pgrowlocks lock
inspection and lock_timeout protection checks. My own mutants were run against it.
A parallel Codex TASK-009 audit was running on the same machine (containers `homies-task009-3623184-*`,
worktree `.codex\worktrees\b65c`). I did not read, use or touch it.

## EXACT SHA

- `git rev-parse HEAD` = `36231840ee52d6185e73fda07e54eab33ffe41f3`. The main checkout was on branch
  `claude/TASK-008-final-foundation-hardening`, clean, with log `3623184, 63686b6, 1b2458c, 0f1cb33`.
- Audit worktree: detached at that SHA, clean before and after (`git status --short` empty). The main checkout is still clean at the same SHA.
- Diff audited: `1b2458c..3623184`, 16 files, +1300/−68 (authority.py, organizations.py, router.py, two new PG test files, four mutation harnesses, docs, openapi.json).

## ENVIRONMENT

- Windows 11, Git Bash. Docker `postgis/postgis:16-3.4`: PostgreSQL 16.4 (Debian 16.4-1.pgdg110+2), PostGIS 3.4.3.
  Five disposable containers `t9c-pg1..5` on 127.0.0.1:55591–55595. The contrib `pgrowlocks` extension was created in these disposable databases only.
- Python 3.14.3 (venv of the main checkout, used read-only as an interpreter), pytest 9.1.1, SQLAlchemy 2.0.51, FastAPI 0.139.0,
  psycopg 3.3.4, ruff 0.15.20 (pyproject pins 0.15.22, see NOTE), mypy 2.3.0.
- Code was executed from `git archive` exports of the SHA (`probe\`, `mut\`, `mut2\`, `mut3\`), so the audited worktree was never mutated.
  Every mutant restore was verified by SHA-256.

## COMMANDS ACTUALLY RUN

```
git rev-parse HEAD / status --short / branch --show-current / log -4 --oneline   (main + worktree)
git worktree add --detach <evidence>\TASK-009\wt 36231840ee52…
git diff 1b2458c..3623184 (stat, app/, tests, harnesses, docs, openapi.json)
pytest (targeted PG, 7 files)                    -> 86 passed, exit 0
ruff check --no-cache .                           -> All checks passed, exit 0
mypy (77 files)                                   -> Success, exit 0
pytest tests/test_tst01_openapi_contract.py       -> 5 passed, exit 0
pytest (full, SQLite; TEST_DATABASE_URL unset)    -> 705 passed, 188 skipped, exit 0
pytest (full, PostgreSQL/PostGIS pg2)             -> 883 passed, 10 skipped, exit 0
own probes (tests/test_audit9_*.py in probe\ copy): publication 41+2, membership 18, F-04/stress 4
own mutants (mutate.py / mutate2.py): D01 E01 E02 E03 E04 ACC_SHARE INV_UNLOCKED INV_NO_RECOVERY INV_ANY_NON_INVITED
E01/E02/E03 vs 9 relevant repo test files (136 tests)
builder harness rerun with kill-reason capture (harness_check.py): task008 D01–D17, E01–E04; task006; task004; task002 M03/M04/M05/M19
```

The targeted PG files were test_publication_proof_replacement_pg, test_membership_invite_race_pg,
test_publication_chain_gain_race_pg, test_membership_accept_race_pg, test_publication_authority_race_pg,
test_publication_race_pg and test_concurrency_r4_pg. CI did **not** run.

## N-05 ACTUAL LOCKED-PROOF AUDIT — CLOSED

**Code** (`authority.py:402-442, 476`). For single-key tables, `locked[key] = sorted(db.scalars(SELECT col … FOR SHARE).all())` records the ids PostgreSQL returned.
For pair tables, a (mandate, scope) or (authority, scope) pair is kept only if its own `SELECT … FOR SHARE` returned a row (`.first() is not None`).
The decision is `_chains(…, within=locked)`. `within=proof` no longer appears on the decision path.
Every lock key is a primary key (`person_legal_parties.legal_party_id`, `organization_legal_parties.legal_party_id`, the ids, and both scope PKs), so a returned key names exactly one locked tuple.
In the restricted evaluation, every table the decision reads carries a restriction: authority id, (authority, scope) pair, legal party, personal link,
membership, organization, org link, mandate id and (mandate, scope) pair.

**Raw-SQL reproductions** (a DELETE + INSERT of the same key held in a raw transaction; the publication was observed blocked **by that transaction's pid**, then the transaction committed):

| class | direct decision | HTTP | returned set == pgrowlocks | next attempt |
|---|---|---|---|---|
| person_legal_parties | 409, Retry-After 0 | 409, detail, draft, anon GET 404 | yes | 200, replacement write **blocked** |
| organization_legal_parties | 409 | same | yes | 200, blocked |
| organization_memberships | 409 | same | yes | 200, blocked |
| representation_mandate_scopes | 409 | same | yes | 200, blocked |
| property_authority_scopes | 409 | same | yes | 200, blocked |
| representation_mandates (parent row, beyond the TASK-008 tests) | 409 | same | yes | 200, blocked |
| organizations (parent row, beyond the TASK-008 tests) | 409 | same | yes | next HTTP 200 |

- **The forbidden outcome was never produced on the audited code.** Forbidden here means the replacement row is not locked and the publication still returns 200.
- With the pre-lock-key mutant D01 (`within=proof`), all 14 probes produced it: 200, the replacement row writable, and the HTTP listing `active`. The probes therefore catch the N-05 defect.
- **Unchanged proof that was waited on** (a cosmetic UPDATE held on each of the 9 proof tables): 9/9 returned 200, with proof == locked == pgrowlocks.
- **A replacement that stays valid** is discovered, locked and used by the next independent request: 6/6 returned 200, and a DELETE or revoke of the replacement then waited.
- **Holder / legal-party constraint**: the authority holder and the mandate principal were re-pointed by FK UPDATE to another ACTIVE party P2 while the lock waited. The audited code returned 409 (the `LegalParty.id` restriction holds).
- **Actual return set**: the recorded set matched `pgrowlocks` (the lock owner's pid) for every probe: 7 replacement, 9 cosmetic, 6 next-attempt and 2 multi-row. No stale expected row is ever counted as protected.

## N-06 RESTRICTED-PROOF AUDIT — PARTIALLY_CLOSED

1. **Required for correctness, now tested.** These are the personal link, membership, org link, (mandate, scope) pair, (authority, scope) pair, whole-mandate (D10) and whole-authority (D12) restrictions.
   Builder mutants D06–D12 were re-killed by AssertionError.
2. **Called "equivalent" by the builder, but they carry weight.** In each case below, the listing goes public although the row it rests on is not locked:
   - **E01 (mandate id).** The mandate row is deleted (its scope rows cascade) and re-inserted with the same scopes while the mandate lock waits.
     The mandate lock returns nothing, but the scope lock runs later with a fresh snapshot and locks the new scope row.
     Without E01: 200, `representation_mandates` lock set `[]`, a mandate revoke does **not** wait, and over HTTP the listing is `active` with anonymous GET 200.
   - **E02 (organization id).** The organization row is replaced (memberships and org link deleted and re-inserted) while the org lock waits.
     Without E02: 200, and org suspension does not wait. Over HTTP the listing is `active`.
   - **E03 (legal-party id).** The authority holder and the mandate principal are re-pointed by FK UPDATE to P2 while the legal_parties lock waits.
     Without E03: 200, and archiving P2 does not wait.
   The builder's reasoning ("cannot be replaced without cascading" / "RESTRICT") covers deletes but misses two things:
   (a) child rows are locked **after** their parent, with a new snapshot, so they lock the replacement children;
   (b) FK re-pointing. None of E01/E02/E03 is killed by the 136 relevant repository tests either. → **NEW FINDING NF-1 (P3).**
3. **E04 (authority id) is genuinely equivalent under the current schema.** An authority row cannot be re-inserted while a publication runs:
   the INSERT needs a key-share lock on the property row, which the publication holds FOR UPDATE. In the probe, a raw delete-and-reinsert deadlocked and PostgreSQL resolved it; E04 survived 9 probes.
   This equivalence depends on the FK `property_authorities.property_id → properties`, on the coordination lock being **FOR UPDATE** (not FOR NO KEY UPDATE), and on the scope-to-authority FK.
4. **A schema change would invalidate these assumptions.** E04 would fail if any of those three dependencies changes. E01 to E03 are already not equivalent.
   `organization_legal_parties` currently allows one legal party per organization (`organization_id UNIQUE`), although 04a allows several. This is a pre-existing divergence, so there are no multi-link organization scenarios yet. If it is relaxed, revisit the org-link and organization restrictions.
- **Multiple rows of the same kind**: two VERIFIED authorities of one holder, and two mandates from one principal, with one row replaced while the lock waited.
  Result: 200 through the survivor, the survivor's rows blocked and the replaced row free (not relied on).
  A second mandate gained during the wait was not used and the next attempt succeeded.
  No holder, scope or authority pooling was observed. The decision query joins only locked rows, so any match is a real chain made of locked rows.

## N-07 ACCEPT LOCK-STRENGTH AUDIT — CLOSED

- Accept vs accept (AGENT and ADMIN): I paused the first accept after its lock with my own `_now` hook.
  The second accept waited **in `SELECT … FOR UPDATE`**, blocked by the first accept's pid, and never reached its write.
  Final results: 200 and 404, one `member_joined` audit row, version +1, and pg_stat_database deadlocks +0.
- FOR SHARE mutant: the second accept reached its write, the transactions deadlocked (+1) and one request errored. This fails my probe and the repository test (D13 re-killed by AssertionError).
- Accept vs revoke was also tested, in both orders (see N-02).

## N-08 AUTHORIZATION OUTCOME AUDIT — CLOSED

All four outcomes come from the real route, and the pre-check passed first (spy count = 1):

| outcome | how it was produced | result |
|---|---|---|
| 403 (final branch) | held `verification_state = UNVERIFIED` on the authority | draft, no Retry-After. Not mocked: the protected decision saw the committed change after waiting on that pid |
| 404 | `linked_user_id = NULL`, or a raw authority revoke | "Offer not found", draft |
| 409 | replacement or gained chain | Retry-After: 0 |
| 200 | cosmetic change on a waited-on row | listing active |

Also verified: 403 at the pre-check, and 404 for a stranger.
These codes match the project's meanings: 404 means no usable relationship (and cannot be told apart from "does not exist"), 403 means the caller holds only an unverified authority, 409 means the chain changed during the protected decision, and 200 means a protected valid chain exists.

## N-09 INVITATION LIFECYCLE AUDIT — CLOSED

- Lifecycle table (probe): no row → INVITED. REVOKED → INVITED with the new role and version +1. INVITED is unchanged, including its role. ACTIVE is unchanged.
- Stale invite: the row was REVOKED and a raw transaction held REVOKED → ACTIVE. The invite waited in `SELECT … FOR UPDATE` on the raw transaction's pid, then answered 202 and left the member ACTIVE (AGENT).
  So the lock is taken before the lifecycle decision. Rollback variant: the re-invite applied.
- Re-invite held vs accept: the accept waited at FOR UPDATE, then joined with the re-invite's role.
- Mutants on my probes:
  - unlocked read: ACTIVE was demoted to INVITED
  - `!= INVITED` guard: ACTIVE was demoted
  - Builder D14/D15/D16 were re-killed by AssertionError.

## N-10 CONCURRENT FIRST-INVITE AUDIT — CLOSED

- API vs API with the first call held after its INSERT: the second waited in its INSERT on the first's pid.
  Both returned 202 with identical bodies, one row was created (INVITED, the winner's role), the loser's audit row committed after the savepoint rollback (2 audits), and there were 0 aborted sessions.
  The savepoint does not poison the outer transaction.
- API vs API free-running: 10/10 rounds returned 202/202 with one row.
- API vs an uncommitted raw INSERT, crossed with (INVITED | ACTIVE) × (COMMIT | ROLLBACK): the API waited in its INSERT and returned 202.
  After COMMIT, the raw row was kept (ACTIVE was **not** demoted). After ROLLBACK, the API's own INVITED row was created. One audit row each time.
- Mutant (IntegrityError not handled): raw UniqueViolation escaped (500) in API vs API and API vs raw commit. Builder D17 re-killed.
- Two 202s is intentional and consistent: the endpoint always answers the same 202 ("If the address has an account…"), which is the anti-enumeration contract. See the NOTE on audit semantics.

## N-01 REGRESSION — NONE

- Probe: chain A was valid and waited on while a second mandate B was gained. The decision returned 200 through A; a revoke of A was **blocked** and a revoke of B was **free** (B not held).
- Probe: A was revoked and B gained during the wait. The decision returned 409 with Retry-After, and the next attempt returned 200 through B.
- The repository chain-gain and pooling tests pass. There is no global mutex: the only in-process lock in `app` is the rate limiter.

## N-02 REGRESSION — NONE

Accept vs revoke, in both orders, for AGENT and ADMIN. The second operation waited at FOR UPDATE.

| first | accept | revoke | final state |
|---|---|---|---|
| accept | 200 | 200 | REVOKED |
| revoke | 404 | 200 | REVOKED |

24 free-running rounds produced no ACTIVE-after-revoke and no ACTIVE row with `revoked_at` set. Repository tests pass.

## F-04 REGRESSION — NONE

- **Repository tests (passed in the targeted and full PG runs):**
  - LOSSES × both orders: membership, mandate, organization (function and SQL), party (function and SQL), person link, org link, mandate scope, authority scope
  - authority revoke and space archive (both orders)
  - mandate expiry and the midnight boundary
  - surviving and multiple chains, partial scopes
  - `test_no_invalid_chain_passes…` (11 cases)
- **Independently reproduced:**
  - After a 200 decision (held open), all 19 loss writes across personal, organisational and mandate chains waited: archive, link cut or delete, revoke, unverify, expire, scope delete, role downgrade, suspension, and the property-lock path.
  - Loss before the decision: unverified → 403, unlinked → 404, raw authority revoke → 404.
  - Replacement losses → 409 (N-05).
- The one probe write that did not wait was a raw `UPDATE spaces` that bypasses the property lock. This is by design and pre-existing: space archive goes through the property coordination lock, and the repository test for it passes. It is not part of the authority proof and is not TASK-008.

## 409 API CONTRACT

- The authority-change conflict returns HTTP 409, `Retry-After: 0`, and detail = `authority.AUTHORITY_CHANGED`, whose value is "The authority for this property changed while publishing. Try again.". OpenAPI documents 403, 404 and 409 plus the Retry-After header.
- Other publish 409s were verified to carry **no** Retry-After: archived listing and archived space (probe), and the aparthotel policy (code: `listing_rules.py:30`).
- Answers:
  1. **Is it unambiguous enough?** Yes for a machine client that keys on the presence of Retry-After. The detail is a human sentence, not an error code (known debt). The repository has no client code (`frontend/` holds only the design system).
  2. **Is retry safe?** The refusal path writes nothing. Retrying after a lost 200 returns 200 again (`PUBLISHABLE_FROM` includes `active`), re-stamps `published_at` and adds an audit row. The state converges, but the call is not strictly idempotent (NOTE).
  3. **Does it leak authority information?** No. 409 is returned only when the caller holds a valid VERIFIED chain right now.
  4. **Can a client loop forever?** Yes, if authority churn never stops, because `Retry-After: 0` invites immediate retries. Recorded as NOTE/operational debt: clients should cap retries and back off.

## DEADLOCK / LOCK ORDER

- TASK-008 adds one lock: `invite` takes FOR UPDATE on the membership row. The `_lock_proof` statements and their order are unchanged.
- Each of `accept`, `invite` and `revoke_member` locks one membership row and then writes only that row and `audit_log`. Mandate revoke, org status and party status each lock one row. Authority revoke and space archive lock the property first.
  None of them waits for a lock a publication holds while holding one the publication needs, so **no feasible cycle** exists.
- A first-invite INSERT's key-share lock on `organizations` is compatible with a publication's FOR SHARE.
- 40 s stress on real PG (10 concurrent loops: publish ×3, member revoke/invite/accept, double accept, first invites ×2, revoke newbie, mandate revoke/grant, raw status toggles): **0 deadlocks, 0 errors or 5xx**, no duplicate memberships, no ACTIVE row with `revoked_at` set.
- Only a raw writer that breaks the documented order can deadlock: delete an authority, then re-insert it while a publication holds the property. PostgreSQL resolves it and the publication is the victim (NOTE NF-3). Revoke starvation remains operational debt, not deadlock.

## RAW-SQL GUARANTEE

Every N-05 and N-06 race above used raw SQL transactions (DELETE/INSERT/UPDATE) in the disposable database, not API routes. The guarantee holds at the PostgreSQL level for all 7 replacement classes and for FK re-pointing.

## MUTATION REVIEW

- **TASK-008, rerun independently with kill reasons captured:**
  - D01–D17: **17/17 killed.** Every baseline was green and every kill was an **AssertionError** (no syntax, collection or setup failures).
  - E01–E04 survive the REPL file, as the builder claims.
  - My probes kill E01, E02 and E03. They are **not** equivalent (NF-1). E04 survives (equivalent).
- **My own mutants on my probes:**
  - D01 → FORBIDDEN 14/14
  - FOR SHARE accept → deadlock (my accept-vs-revoke probes do not distinguish it, as TASK-007 predicted)
  - unlocked invite → demotion
  - `!= INVITED` guard → demotion
  - no IntegrityError recovery → 500
- **Regression reruns:** see "TEST RESULTS / regression mutants".
  The harness re-pointing diffs (B03, B04, B05, A05, M19) target the same invariants in the reshaped code; none was weakened.

## TEST QUALITY

- **Strengths:**
  - The N-05, N-07 and N-10 tests are tied to pids (`pg_blocking_pids` with the specific blocker).
  - They assert HTTP code, detail, Retry-After, listing state, anonymous public GET, audit counts and the pg_stat deadlock counter.
  - Polling waits have deadlines and wait for events. They are not bare sleeps.
- **Gaps:**
  - NF-1: parent-row replacement (mandate, organization) and FK re-pointing are untested. The three restrictions that guard them survive the whole relevant suite.
  - The harness kill criterion (exit 1 plus "failed") would also count non-assertion exceptions. My rerun confirmed that all TASK-008 kills are AssertionErrors.

## TEST RESULTS

| gate | result |
|---|---|
| targeted PG (7 files) | 86 passed, exit 0 |
| full SQLite | 705 passed, 188 skipped (PG-only), exit 0 |
| full PG/PostGIS | 883 passed, 10 skipped (9 DR restore: no pg_dump/pg_restore; 1 Stripe live), exit 0 |
| ruff | All checks passed (0.15.20) |
| mypy | Success, 77 source files |
| OpenAPI drift | 5 passed. `openapi.json` equals the generated spec, and the added 403/404/409 text comes from the route's `responses=`, so it was not edited by hand |
| own probes, audited code | publication 43/43, membership 18/18, F-04 3/3 (plus 1 expected by-design raw-spaces note), stress 1/1 |
| builder TASK-008 mutants | 17/17 killed (AssertionError), 4 survived |
| regression mutants TASK-006 / 004 / 002 | see the addendum at the end |

## PYTHON 3.12 STATUS

PYTHON 3.12 TARGETED RUNTIME NOT VERIFIED.

- The host has only Python 3.14.3.
- The local `homies-api:latest` image (Python 3.12.14, 5 weeks old) lacks Pillow (now required) and pytest, so it is not a governed environment.
- CI (`.github/workflows/ci.yml`, python-version "3.12") was not run.

## DR RESTORE STATUS

DR RESTORE NOT VERIFIED. `pg_dump` and `pg_restore` are absent on the host, and 9 DR tests were skipped. Nothing was installed.

## NEW FINDINGS

- **NEW FINDING NF-1 (P3): three restrictions called equivalent are needed for correctness and are untested.**
  - Location: `authority.py:151,159,197`, `docs/reviews/2026-09-25-task008-mutation.md` (E01–E03), `docs/tasks/TASK-008…md` (N-06), `scripts/mutation/task008_mutants.py:147-172`.
  - Violated invariant: D-49 test obligation ("each load-bearing restriction is killed by a behavioural test"). The documents invite removing these three restrictions.
  - Evidence: raw SQL, with the restriction removed.
    - E01: mandate-row replacement gives 200 and a public listing, and a mandate revoke does not wait.
    - E02: organization-row replacement gives 200 and public, and suspension does not wait.
    - E03: re-pointing the holder and principal gives 200, and archiving the party does not wait.
    - All three survive 136 relevant repository tests.
  - The audited code keeps all three restrictions and returns 409 in every scenario, so there is no live defect.
  - Repair:
    - Add three PG tests: mandate-row replacement, organization-row replacement, and holder/principal re-pointing (the probes in `probes\test_audit9_publication_pg.py` can serve as templates).
    - Reclassify E01–E03 as killable.
    - Document E04's actual dependency: the property FK, FOR UPDATE on the coordination lock, and the scope FK.
  - No canonical decision is required.
- **NEW FINDING NF-3 (NOTE): raw-SQL deadlock with publication as the victim.**
  - Scenario: a raw writer deletes and re-inserts an authority while a publication holds the property.
  - Result: deadlock; the publication is aborted with an unhandled OperationalError (an HTTP 500 if it came through the API).
  - Not reachable through the API (no route deletes authorities). It fails closed and has been present since TASK-004.
- **NEW FINDING NF-4 (NOTE): refusal classification is not atomic.**
  - `require` and the refusal branch of `authorize_for_mutation` classify 404, 403 and 409 with separate statements.
  - Under churn a refusal can get an imprecise code. In the stress run the org publisher got 403 three times while the org status toggled.
  - It never authorizes and reveals no new information. Pre-existing.
- **NEW FINDING NF-5 (NOTE): invitation audit semantics.**
  - An invitation that changes nothing still writes `organization.member_invited`: this happens for INVITED or ACTIVE targets and for the loser of a first-invite race.
  - The loser's requested role is dropped silently behind the uniform 202.
  - This is consistent with the anti-enumeration contract, but the audit entry may mislead.
- **NEW FINDING NF-6 (NOTE): retry after a lost 200 is not strictly idempotent.** The call returns 200 again, re-stamps `published_at` and adds an audit row.
- **NOTE: tool version drift.** The venv has ruff 0.15.20, but pyproject pins 0.15.22.

## NONBLOCKING DEBT (carried, not escalated)

- Possible revoke starvation under sustained publication traffic. The authority.py comment is now correct.
- No project-wide machine-readable error-code convention. The retry signal is `Retry-After` plus a sentence.
- An unbounded client retry loop is possible with `Retry-After: 0`.
- Race: a manager revoked in the middle of an invite (`_require_role` does not lock).
- Race: a legal-name update against admin verification.
- A raw `spaces` UPDATE bypasses the property lock. The API path is serialised.
- Python 3.12 not verified.
- DR restore not verified.
- 04a divergence: `organization_legal_parties.organization_id` is UNIQUE, but 04a allows several legal parties per organization.

## FINAL VERDICTS

```
N-05 = CLOSED
N-06 = PARTIALLY_CLOSED
N-07 = CLOSED
N-08 = CLOSED
N-09 = CLOSED
N-10 = CLOSED

N-01 REGRESSION = NONE
N-02 REGRESSION = NONE
F-04 REGRESSION = NONE

TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES
```

## FOUNDATION BASELINE 002

Gate conditions met: N-05, N-09 and N-10 are CLOSED, there is no N-01, N-02 or F-04 regression, and there is no new P0, P1 or P2.

```
HOMIES_FOUNDATION_BASELINE_002_ACCEPTED
SHA 36231840ee52d6185e73fda07e54eab33ffe41f3
```

This means the SHA is accepted for continued Phase 1A development. It does NOT mean production ready.
Recommended before the next authority-touching task: repair NF-1 (tests plus documentation only).

## PRODUCTION READINESS

NOT ASSESSED / NOT READY

## DEPLOYMENT STATUS

NOT DEPLOYED

## Cleanup performed

The audit worktree was removed with `git worktree remove`, and containers `t9c-pg1..5` were removed. Exports and evidence are kept under the evidence root.
The audited repository was not modified: no commit, push or PR.

## Addendum — regression mutant reruns (harness_check.py, pg5, kill reasons captured)

| harness | result | kill type |
|---|---|---|
| TASK-006 B01–B07 | 7/7 killed, baselines green | AssertionError. B05 also shows the known KeyError in one test (TASK-007 note); its other test kills by assertion |
| TASK-004 A01–A09 | 9/9 killed, baselines green | AssertionError |
| TASK-002 M03 / M04 / M05 / M19 | 4/4 killed, baselines green | AssertionError |
| TASK-008 D01–D17 | 17/17 killed | AssertionError |
| TASK-008 E01–E04 | survive the REPL file | E01–E03 killed by the auditor probes (NF-1) |

---

## Section B — final message delivered in the audit session (verbatim)

# TASK-009 FINAL INDEPENDENT FOUNDATION AUDIT

## EXECUTIVE VERDICT
TASK-008 does what it claims for N-05, N-07, N-08, N-09 and N-10. I reproduced each one myself on real PostgreSQL, using raw SQL.

- **Main finding.** The publication decision now uses only the rows its locks actually returned. PostgreSQL's own row-lock view (`pgrowlocks`) matched that set in every probe.
- **One NEW FINDING (P3).** The builder calls three mutants "equivalent": E01, E02 and E03. They are not. Removing any of those restrictions lets a publication return 200 through a row nobody locked. No repository test catches it.
- **No live defect.** The audited code keeps all three restrictions and correctly returns 409 in each of those scenarios.
- No P0, P1 or P2 findings.

**TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES** · **HOMIES_FOUNDATION_BASELINE_002_ACCEPTED** (SHA `36231840ee52d6185e73fda07e54eab33ffe41f3`)

## INDEPENDENCE
YES. This was a fresh session that did not build TASK-008. I wrote my own probe harness: a direct decision thread, raw-SQL holds, `pgrowlocks` checks, and `lock_timeout` checks of whether a row is protected. I ran my own mutants against it.

A Codex audit of the same SHA was running at the same time. I did not touch it.

## EXACT SHA
- HEAD is `36231840…`, on branch `claude/TASK-008-final-foundation-hardening`. Status was clean and the last 4 commits matched.
- The audit ran in a detached worktree at that SHA. It was clean before and after.
- Diff audited: `1b2458c..3623184`, 16 files.

## ENVIRONMENT
- PostgreSQL 16.4 with PostGIS 3.4.3, in five disposable containers (`t9c-pg1..5`).
- Python 3.14.3 from the host venv.
- Code ran from `git archive` exports of the SHA. The audited tree was never changed, and every mutant restore was checked by SHA-256.

## COMMANDS ACTUALLY RUN
- Targeted PG tests (7 files), ruff, mypy, OpenAPI drift.
- Full SQLite suite and full PostgreSQL suite.
- My probes: 65 tests.
- My mutants: 9.
- E01–E03 against the relevant repository tests (136 tests).
- The builder's mutants from TASK-008, TASK-006, TASK-004 and a TASK-002 subset, rerun with the reason for each kill recorded.

CI was not run.

## N-05 — CLOSED
I replaced a proof row (DELETE and INSERT with the same key, in a raw SQL transaction) while the publication waited on that transaction. I did this for 7 kinds of row: the 5 the builder tests, plus whole mandate rows and whole organization rows.

- **Result every time:** 409 with `Retry-After: 0` and the authority-change detail. The listing stayed a draft and an anonymous GET returned 404.
- **Next independent request:** 200. It locked the replacement row: a later delete or revoke had to wait.
- **Unchanged row that the publication waited on:** 200 on all 9 proof tables.
- **Lock set:** the set the code records as locked equalled `pgrowlocks` in every probe.
- **Control:** with the old behaviour (decide through the keys read before locking, mutant D01), all 14 probes produced the forbidden outcome: 200, an unlocked replacement row, and a public listing.

## N-06 — PARTIALLY_CLOSED
- **Tested and working:** the restrictions covered by mutants D06–D12. I re-killed all of them with assertion failures.
- **E01 (mandate id):** replacing the mandate row lets the publication return 200 while the mandate row is unlocked and a revoke doesn't wait.
- **E02 (organization id):** replacing the organization row gives 200, and suspending the organization doesn't wait.
- **E03 (legal party id):** re-pointing the authority's holder and the mandate's principal to another party gives 200, and archiving that party doesn't wait.
- **E04 (authority id):** truly equivalent under the current schema. That depends on the property foreign key, the property lock being FOR UPDATE, and the scope foreign key.
- **Several rows of one kind:** with two authorities of one holder, or two mandates from one principal, the publication succeeded through the surviving row. That row was fully locked. There was no pooling across chains.

## N-07 — CLOSED
- **Accept vs accept:** the second accept waits in `SELECT … FOR UPDATE` on the first one's backend, before acting on the row. Results were 200 and 404, with one audit row and no deadlocks.
- **FOR SHARE mutant:** a deadlock. The builder's D13 mutant was re-killed.

## N-08 — CLOSED
All four outcomes come from the real route:
- **403** from the final branch, after the pre-check had passed. It is not mocked.
- **404** when the link is cut, or the authority is revoked.
- **409** with `Retry-After` when the proof changed.
- **200** after a cosmetic change.

The meanings match the project's semantics.

## N-09 — CLOSED
- **Lifecycle:** no row becomes INVITED. REVOKED becomes INVITED with the new role. INVITED and ACTIVE are left unchanged.
- **Stale invite:** it waits at FOR UPDATE on the raw transaction and then leaves an ACTIVE member alone. The row is locked before the lifecycle decision.
- **Mutants:** an unlocked read, or a weaker status check, demotes an ACTIVE member.

## N-10 — CLOSED
- **API vs API:** both return 202 with the same body, and exactly one row exists.
- **Outer transaction:** it stays healthy, because the losing request's audit row committed.
- **API vs an uncommitted raw INSERT:** tested with the raw row INVITED or ACTIVE, then committed or rolled back. The API returned 202 each time, and an ACTIVE row was never demoted.
- **Mutant:** without the recovery, the loser gets a 500 (UniqueViolation).
- **Both 202:** matches the endpoint's contract. It always answers the same 202, so it can't reveal whether an email has an account.

## N-01 REGRESSION — NONE
- If chain A is still valid when chain B appears, the publication succeeds through A. A is locked and B is not held.
- If A is lost and B appears, the publication gets 409. The next attempt succeeds through B.
- There is no global mutex.

## N-02 REGRESSION — NONE
Accept and revoke, both orders, for AGENT and ADMIN:
- accept first → 200, then 200, final state REVOKED
- revoke first → 200 for the revoke, then 404 for the accept, final state REVOKED

24 free-running rounds never produced a stale ACTIVE.

## F-04 REGRESSION — NONE
- **Repository tests:** they cover every loss type in both orders, plus authority revoke, space archive, expiry and multiple chains. All pass.
- **Losses after the decision:** in my own sample, 19 writes that break the chain all waited for the publication, across personal, organisation and mandate chains.
- **Losses before the decision:** these gave 403 or 404 as expected.

## 409 API CONTRACT
**Contract:**
- 409 with `Retry-After: 0` and detail `authority.AUTHORITY_CHANGED`, documented in OpenAPI.
- The other 409s carry no `Retry-After`: archived listing, archived space, aparthotel policy.

**Answers to the four questions:**
1. **Unambiguous?** Yes for a client that checks whether `Retry-After` is present. There is no client code in the repo.
2. **Safe to retry?** The refusal path writes nothing. Retrying after a lost 200 gets 200 again, but also re-stamps the publish time and adds an audit row.
3. **Leaks information?** No. The 409 is only returned when the caller holds a valid chain right now.
4. **Endless retry loop?** Possible under constant authority churn. Recorded as NOTE and operational debt.

## DEADLOCK / LOCK ORDER
- **Analysis:** no feasible lock-order cycle.
- **Stress:** 40 seconds, 10 concurrent loops. 0 deadlocks, 0 errors or 5xx, and no duplicate memberships.
- **Raw-SQL exception:** only a raw writer that breaks the lock order can deadlock with a publication (NF-3, NOTE).

## RAW-SQL GUARANTEE
Every N-05 and N-06 race was driven by raw SQL transactions, not API routes. The guarantee holds at the PostgreSQL level.

## MUTATION REVIEW
- **TASK-008:** D01–D17 killed 17/17, every one by an AssertionError. E01–E04 survived the builder's test file. My probes kill E01, E02 and E03.
- **Reruns:** TASK-006 7/7, TASK-004 9/9, TASK-002 subset 4/4 killed. All by AssertionError. One B05 test also shows a KeyError already recorded in the TASK-007 audit.

## TEST QUALITY
**Strong:** the repository race tests check:
- which backend blocked which, by process id
- HTTP status, detail and `Retry-After`
- listing state and anonymous GET
- audit row counts and the deadlock counter

**Gap:** nothing tests replacing a whole mandate or organization row, or re-pointing a foreign key (NF-1).

## TEST RESULTS

| Gate | Result |
|---|---|
| Targeted PG (7 files) | 86 passed |
| Full SQLite | 705 passed, 188 skipped |
| Full PG | 883 passed, 10 skipped (9 DR-restore tests need `pg_dump`; 1 Stripe live test) |
| ruff | clean |
| mypy | 77 files clean |
| OpenAPI drift | 5/5; spec is generated, not hand-edited |

## PYTHON 3.12 STATUS
PYTHON 3.12 TARGETED RUNTIME NOT VERIFIED. The only local 3.12 image is stale: it has no Pillow and no pytest.

## DR RESTORE STATUS
DR RESTORE NOT VERIFIED. `pg_dump` and `pg_restore` are missing on this machine.

## NEW FINDINGS
- **NEW FINDING NF-1 (P3):** E01, E02 and E03 are killable, not equivalent. The restrictions they remove are needed for correctness, and no repository test catches their removal. The mutation review and the TASK-008 contract describe them as removable.
  - **Fix:** add 3 PG tests (mandate-row replacement, organization-row replacement, holder re-pointing). Then correct the mutation review.
- **NF-3 (NOTE):** a raw-SQL delete-and-reinsert of an authority deadlocks with a running publication. PostgreSQL aborts the publication, which would surface as a 500. It can't happen through the API.
- **NF-4 (NOTE):** the refusal code (403, 404 or 409) is worked out with separate queries. Under heavy churn a refusal can get an imprecise code. It never authorizes anything. This predates TASK-008.
- **NF-5 (NOTE):** an invitation that changes nothing still writes an audit event. The losing invite's requested role is dropped without telling the caller.
- **NF-6 (NOTE):** retrying a publish is not strictly idempotent (see 409 answer 2).
- **NOTE:** the local ruff is 0.15.20, but the project pins 0.15.22.

## NONBLOCKING DEBT
- Possible revoke starvation under sustained publication traffic.
- No machine-readable error codes.
- A client can retry forever on `Retry-After: 0`.
- Race: a manager revoked mid-invite.
- Race: a legal-name update against admin verification.
- A raw `spaces` update bypasses the property lock. The API path does not; this predates TASK-008.
- The schema allows one legal party per organization. The canonical 04a text allows several.
- Python 3.12 not verified.
- DR restore not verified.

## FINAL VERDICTS
```
N-05 = CLOSED
N-06 = PARTIALLY_CLOSED
N-07 = CLOSED
N-08 = CLOSED
N-09 = CLOSED
N-10 = CLOSED
N-01 REGRESSION = NONE
N-02 REGRESSION = NONE
F-04 REGRESSION = NONE
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES
```

## FOUNDATION BASELINE 002
```
HOMIES_FOUNDATION_BASELINE_002_ACCEPTED
36231840ee52d6185e73fda07e54eab33ffe41f3
```
This means accepted for continued Phase 1A development. It does not mean production ready.

## PRODUCTION READINESS
NOT ASSESSED / NOT READY

## DEPLOYMENT STATUS
NOT DEPLOYED

The audit worktree and my containers have been removed. The repository was not modified: no commit, push or PR. Full report: `homies-audit-evidence\TASK-009\FINAL-REPORT.md`.

```text
CHATGPT HANDOFF

Project: Homies
Task: TASK-009 — Final Independent Foundation Audit

Audited SHA:
36231840ee52d6185e73fda07e54eab33ffe41f3

Independent auditor:
YES

N-05:
CLOSED

N-06:
PARTIALLY_CLOSED

N-07:
CLOSED

N-08:
CLOSED

N-09:
CLOSED

N-10:
CLOSED

N-01 regression:
NONE

N-02 regression:
NONE

F-04 regression:
NONE

TASK-008:
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES

Foundation Baseline 002:
ACCEPTED

P0: none
P1: none
P2: none
P3: NF-1 — within-restrictions E01 (mandate id), E02 (organization id), E03 (legal party id) are NOT
    equivalent mutants. Without them, raw-SQL parent-row replacement or FK re-pointing gives publish 200
    through an unlocked row. The restrictions survive 136 relevant repo tests. Audited code keeps them
    (no live defect). Fix: 3 PG tests + reclassify in the mutation review; E04 truly equivalent.

New findings:
NF-1 (P3) above.
NF-3 NOTE: raw-SQL authority delete+reinsert during a publication deadlocks; the publication is the victim (500); not reachable via API.
NF-4 NOTE: refusal code (403/404/409) computed by separate queries, can be imprecise under churn; never authorizes.
NF-5 NOTE: invitations that change nothing still write an audit event; the losing invite's role is dropped silently behind 202.
NF-6 NOTE: retry after a lost 200 gives 200 again, re-stamps published_at and adds an audit row.
NOTE: local ruff 0.15.20 vs pinned 0.15.22.

Tests actually run:
targeted PG 86 passed; full SQLite 705 passed / 188 skipped; full PG 883 passed / 10 skipped
(9 DR need pg_dump, 1 Stripe live); ruff clean; mypy clean (77 files); OpenAPI drift 5/5;
auditor probes 65 (all pass on audited code, except one by-design NOTE: raw spaces update not serialised);
builder mutants rerun: TASK-008 D01–D17 17/17, TASK-006 7/7, TASK-004 9/9, TASK-002 subset 4/4 (all AssertionError);
auditor mutants D01/E01/E02/E03/FOR SHARE accept/unlocked invite/no IntegrityError recovery/weak invite guard all killed; E04 survived.
40 s lock-order stress: 0 deadlocks, 0 errors. CI not run.

Python 3.12:
PYTHON 3.12 TARGETED RUNTIME NOT VERIFIED

DR restore:
DR RESTORE NOT VERIFIED

Remaining debt:
revoke starvation under sustained publication traffic; no machine-readable error codes;
unbounded Retry-After: 0 retry loop; manager revoked mid-invite race; legal-name vs verification race;
raw spaces update bypasses property lock (API path serialised); organization_legal_parties.organization_id UNIQUE
vs 04a (several legal parties per organization); Python 3.12 unverified; DR restore unverified; NF-1 test repair.

Production readiness:
NOT ASSESSED / NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-009.

If HOMIES_FOUNDATION_BASELINE_002_ACCEPTED, formally freeze SHA
36231840ee52d6185e73fda07e54eab33ffe41f3
as Foundation Baseline 002 and generate the first new Poland-wide,
Europe-ready Phase-1A product vertical slice, including the canonical
Homies Product & Growth Doctrine.
```
