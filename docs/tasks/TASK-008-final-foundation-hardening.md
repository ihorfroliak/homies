# TASK-008 — Final foundation concurrency and invitation hardening

| Field | Value |
|---|---|
| Status | IN_AUDIT — N-05…N-10 CLOSED BY BUILDER — PENDING INDEPENDENT REVIEW |
| Owner (writer) | Claude Code — sole writer for TASK-008 |
| Bounded contexts written | `properties/authority`, `properties/router` (publish contract), `identity/organizations` (accept, invite), tests, mutation harness, docs |
| Baseline SHA | `1b2458c0aa2e73d97475733f68e424e62c7ba0e6` (TASK-006; HOMIES FOUNDATION BASELINE 002 **candidate — not yet accepted**) |
| Branch | `claude/TASK-008-final-foundation-hardening` |
| Independent audit required | **Yes** — authorisation and concurrency (05 §9); must not be performed by the TASK-008 builder session |

## Goal

Close the findings of the TASK-007 re-audit of `1b2458c` that block Baseline
002 (N-05) and the test-coverage and invitation defects it recorded
(N-06…N-10), plus the undocumented publish 409. No product feature, no
migration, no change to authority or validity semantics.

## Findings and repairs

### N-05 (P3, Baseline-002 blocker) — a replaced proof row carried the decision

**Root cause.** TASK-006 restricted the protected decision to the proof *keys*
read before the locks. A proof row deleted while its FOR SHARE waited is
skipped by PostgreSQL READ COMMITTED; a row re-inserted under the same key
after that statement took its snapshot is not returned either. Nothing was
locked, yet the key still matched, and the publication went public on a row
nobody held (TASK-007: four variants on real PostgreSQL).

**Repair.** `_lock_proof` now returns the rows its locking statements
**actually returned** — per single-key table the ids `SELECT … FOR SHARE`
yielded, per scope table the (mandate, scope) / (authority, scope) pairs whose
locking statement returned a row — and the decision is evaluated through that
set (`within=locked`). The restricted evaluation additionally requires the
authority's (authority, scope) row itself to be locked, and the mandate id to
be locked. Lock order unchanged; no new lock; no loop.

**Contract.** A replaced row fails the attempt like any lost link: **409 with
`Retry-After: 0`** when a valid chain exists now (the replacement, unlocked);
404/403 otherwise. A new request reads and locks the replacement and publishes.
An unchanged proof row that merely made the lock wait (cosmetic UPDATE)
publishes normally (200).

Observation while testing: a NEW authority row cannot appear during the wait
at all — its INSERT key-share-locks the property row, which the publication
holds FOR UPDATE. The authority-side gain that can happen is an existing
UNVERIFIED right of the same holder being verified; it is not in the (VERIFIED)
proof and does not count.

### N-06 (P3) — `within` restrictions untested

Each load-bearing restriction is now killed by a behavioural test: the
replacement tests replace exactly the row each restriction guards (personal
link, organisation link, membership, (mandate, scope), (authority, scope)),
and two gain tests cover a second mandate from the same principal and a
second right of the same holder verified during the wait. Restrictions the
schema already implies (mandate id given the locked pairs; organisation id
given the locked membership and link; holder party given the locked authority
and RESTRICT FKs; authority id given the locked (authority, scope) pairs) are
kept as defence in depth and reported as equivalent mutants.

### N-07 (P3) — accept lock strength unpinned

`test_two_accepts_of_one_invitation_are_serialised_before_either_reads_it`:
with the first accept held inside its transaction, the second waits on that
backend **before acting on the row** (it never reaches its own write), then
answers 404; one audit row; no deadlock (pg_stat_database). A FOR SHARE lock
lets the second read INVITED and write — the test fails.

### N-08 (P3) — final 403 unexecuted

`test_the_protected_decision_distinguishes_403_404_409_and_200`: one
interleaving (publication waits on a held change to one proof row, the change
commits), four outcomes — verification lost → **403** (the final branch),
link cut → 404, link replaced → 409 with Retry-After, cosmetic change → 200.

### N-09 (P3, pre-existing) — invitation could demote an ACTIVE member

**Root cause.** `invite_member` read the row unlocked and wrote INVITED by
primary key. **Lifecycle** (canon 04 §20 gives statuses INVITED/ACTIVE/REVOKED
and UNIQUE(organization, user), no transition table; this is the rule
implemented): no row → INVITED; REVOKED → INVITED with the new role (an
explicit re-invitation by a manager — the only way back under the uniqueness
constraint); INVITED or ACTIVE → unchanged. The row is locked FOR UPDATE
before it is read, like accept and revoke.

### N-10 (P3, pre-existing) — concurrent first invitations → 500

The INSERT runs in a savepoint; on the unique violation the loser re-reads the
winner's row under the lock and applies the lifecycle (no-op on INVITED), so
both answer the same 202. The database unique index stays the final authority.

### Publish 409 contract

OpenAPI now documents 403, 404 and 409 for `POST /v1/classifieds/{id}/publish`.
The project has no machine-readable error-code convention; the smallest safe
improvement uses its existing retry signal: the authority-change 409 alone
carries `Retry-After: 0` and a stable detail (`authority.AUTHORITY_CHANGED`).
The other publish 409s (archived space, listing state, aparthotel policy) carry
none. A general error-code scheme remains debt.

### Lock-queue comment

Corrected: PostgreSQL grants a share lock ahead of an UPDATE already waiting on
the row, so a continuous stream of publications resting on one row can delay a
revoke of it. A delay, never a cycle or a lost revoke. Carried as operational
debt; no redesign in TASK-008.

## Preserved

N-01 locked-proof semantics (now stricter), N-02 accept/revoke serialisation,
N-03 proof-row locks, N-04 UTC tests, F-04, direct authority revoke, space
archive, listing lifecycle CAS, multiple chains, no scope pooling, database
decision clock.

## Out of scope

Every product feature (geography, address, classification, search, saved
items, alerts, applications, growth, payments, short stay). No migration.

## Evidence

Tests: `tests/test_publication_proof_replacement_pg.py` (N-05, N-06, N-08,
409), `tests/test_membership_invite_race_pg.py` (N-07, N-09, N-10). Mutation:
[`docs/reviews/2026-09-25-task008-mutation.md`](../reviews/2026-09-25-task008-mutation.md).
