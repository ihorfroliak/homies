# TASK-006 — Authority integrity and audit-debt closure

| Field | Value |
|---|---|
| Status | IN_AUDIT — N-01…N-04 CLOSED BY BUILDER, PENDING REVIEW |
| Owner (writer) | Claude Code — sole writer for TASK-006 |
| Bounded contexts written | `properties/authority`, `identity/organizations` (accept), tests, mutation harness, docs |
| Baseline SHA | `dfa3254cb8f8d321c278f1d815bbb7e14a514561` — HOMIES FOUNDATION BASELINE 001 (C1–C8 accepted for continued Phase 1A development) |
| Branch | `claude/TASK-006-authority-integrity-cleanup` |
| Independent audit required | **Yes** for N-01 and N-02 (authorisation, concurrency — 05 §9) |

## Goal

Close the four findings of the TASK-005 independent audit of `dfa3254`
before the next Phase-1A vertical slice. No product feature, no migration, no
change to authority semantics. TASK-005's own findings are the input and are
not rewritten here.

## Findings and repairs

### N-02 (P2) — a stale accept could overwrite a successful revoke

**Root cause.** `accept_invitation` read the `INVITED` row without a lock and
wrote `ACTIVE` by primary key. An admin revoke committing between the two was
overwritten: revoke answered 200, the row ended `ACTIVE` with `revoked_at`
set and the role kept (an ADMIN invitation → an active ADMIN).

**Repair.** Same convention as `revoke_member`: `SELECT … FOR UPDATE`
(populate_existing) on the `(organization, user)` row, then accept only if it
is still `INVITED`, else 404. PostgreSQL orders the two:

* accept first → the revoke waits on the row, then revokes the `ACTIVE`
  membership (serial: accept, revoke);
* revoke first → the accept waits, reads `REVOKED`, answers 404, changes
  nothing (serial: revoke, accept refused).

No Python lock; no schema change.

### N-01 (P3) — a chain gained during the lock wait was not protected

**Root cause.** `authorize_for_mutation` read the proof (plain SELECTs), locked
it, then re-evaluated **all** chains. The lock step can wait — on a revoke in
flight — and a chain that became valid during that wait (a mandate granted,
an invitation accepted) was accepted by the re-evaluation although none of its
rows was locked. TASK-005: Y revoke in flight → publication waits on Y → X
granted → Y commits → decision passes on X → X revoke returns 200 at once →
publication commits ACTIVE with no valid chain.

**Repair — Option B, decide only through the locked proof.** After the locks,
the chains are evaluated with the same predicates as before (`_chains` /
`_holder_parties`, one definition of validity) **restricted to the locked
rows**: the locked authorities and holder parties, the locked personal links,
the locked memberships + organisations + organisation links, and the exact
locked `(mandate, scope)` rows. A chain not in the proof cannot carry this
attempt.

* **Refusal.** If no locked chain is valid: 409 when a valid chain exists
  now (it appeared during the wait — the next attempt reads a proof that
  contains it and locks it); otherwise 404/403 exactly as before.
* **Why it is safe.** Every row the decision can rely on is locked FOR SHARE
  until commit, so the postcondition of TASK-004 now holds as written. The
  refused attempt is serialisable as "Y revoked → publication refused → X
  granted". Scopes are still evaluated per chain; restricting can only remove
  chains, never combine them.
* **Why it terminates.** One pass: read, lock, one restricted evaluation.
  No loop (Option A's stabilisation loop is not needed and would need a
  bound against a stream of new grants).
* **Not over-fixed.** Grants are never blocked: the X grant in the test
  completes while the publication waits. No global lock.

### N-03 (P3) — four proof-row locks had no builder test

`test_publication_authority_race_pg.py` now covers, in both serial orders,
mutations of `person_legal_parties` (unlink), `organization_legal_parties`
(unlink), `representation_mandate_scopes` (delete PUBLISH_LISTING) and
`property_authority_scopes` (delete PUBLISH_LISTING), by raw SQL — no
supported path changes these rows, which is why the guarantee must not depend
on one. Waits are now attributed to the **publisher's backend pid**
(`_blocked_on(…, blocker=reached.pid)`), not "someone is blocked". The
two-chain tests now revoke either chain, in both orders, and check the
finish order.

Mutants B01–B04 (`scripts/mutation/task006_mutants.py`) remove each lock.

### N-04 (P3) — tests used the local date for a UTC rule

Product rule (unchanged): **authority effective dates are evaluated against
the UTC calendar date** (`CAST(timezone('UTC', statement_timestamp()) AS
DATE)` at the protected decision; `authority._today()` elsewhere). Tests built
"yesterday"/"today" from `date.today()` — the machine's local date, a day
ahead of UTC in Poland between local midnight and 01:00/02:00 — so "expired
yesterday" was still valid and three tests failed nightly.

`tests/conftest.authorization_date()` returns the UTC date; every test whose
date means "authorisation date under the current rule" uses it:
`test_no_invalid_chain_passes_the_protected_decision[expired_mandate]`,
`test_a_mandate_works_only_inside_its_dates`,
`test_an_expired_right_authorises_nothing`, the mandate-expiry and
decision-clock tests, and the partial-scopes test (its authority
`effective_from` was the local date, which made the authority not yet in force
in the same window and the refusal it asserts trivially true). Booking-date
fixtures (legacy), and the date-ordering validation test, keep `date.today()`:
their meaning is not the authorisation date. A test built within milliseconds
of UTC midnight can still straddle it; that is a product-clock boundary, not
the local/UTC split.

**UTC domain note.** Current technical rule: authority effective dates are
evaluated against the UTC calendar date. This remains a controlled
product/legal question for internationalisation (Polish civil date vs UTC);
TASK-006 does not change it.

## Preserved (TASK-002 / TASK-004)

Property coordination lock; full proof protection FOR SHARE in the documented
order; database decision clock; listing lifecycle CAS; multiple independent
chains; no scope pooling. Direct authority revoke and space archive unchanged.

## Known operational debt (not changed)

From TASK-005: a cosmetic UPDATE of a proof row (e.g. an organisation's
display name) waits for an in-flight publication; a share request queues
behind an UPDATE already waiting on the same row, so a second publication can
be delayed (head-of-line), never deadlocked. Correctness first; not optimised.

## Out of scope

Everything product-facing (geography, structured address, subtype migration,
search features, SALE/MONTHLY/SHORT_STAY, frontend, payments). No migration.

## Evidence

Tests: `tests/test_membership_accept_race_pg.py` (N-02),
`tests/test_publication_chain_gain_race_pg.py` (N-01),
`tests/test_publication_authority_race_pg.py` (N-03, N-04).
Mutation: [`docs/reviews/2026-09-25-task006-mutation.md`](../reviews/2026-09-25-task006-mutation.md).
