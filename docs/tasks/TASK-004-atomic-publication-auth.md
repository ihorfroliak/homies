# TASK-004 — Atomic publication authorisation across all authority chains

| Field | Value |
|---|---|
| Status | IN_AUDIT — CLOSED BY BUILDER, PENDING CODEX RE-AUDIT (TASK-005) |
| Owner (writer) | Claude Code — sole writer of properties/authority, publication, identity revoke paths |
| Baseline SHA | `0d6c55451a6e7e9b0e616957e2384449aa374921` (TASK-002 handoff) |
| Branch | `claude/TASK-004-atomic-publication-auth` |
| Codex audit required | **Yes** — authorisation and concurrency (05 §9) |

## Problem

TASK-003 accepted F-01…F-03 and F-05…F-09, and found F-04 **PARTIALLY_CLOSED
(P1)**. TASK-002 serialised publication with a direct PropertyAuthority revoke
and a space archive through the Property coordination row. But a chain is
more than the authority: after publication's last successful check, a
**membership revoke, mandate revoke, organisation suspension, legal-party
archival or mandate expiry** could take effect, and the suspended publication
then committed `active` (publish 200, anonymous GET 200) on a chain that no
longer existed. None of those mutations touches the Property row, so the
Property lock could not order them.

## Invariant

At the point that commits a listing into `active`, at least one complete,
valid authorisation chain exists for the acting user to exercise
`PUBLISH_LISTING` (VERIFIED) on the property:

* User → PERSON LegalParty → PropertyAuthority
* User → ACTIVE membership (role carrying the scope) → ACTIVE Organization →
  its LegalParty → PropertyAuthority
* User → ACTIVE, VERIFIED, in-date mandate (scope) → principal LegalParty →
  PropertyAuthority

with every status, verification state, scope and effective date valid **at
that point**. A result from earlier in the request is not sufficient. Scopes
are never pooled across chains.

## Concurrency model

`authority.authorize_for_mutation(db, user, property_id, scope, verified=True)`,
called by publication inside the same transaction as its conditional status
UPDATE:

1. The caller already holds the Property coordination lock (`FOR UPDATE`).
2. Every row that makes each **currently valid** chain valid is locked
   `FOR SHARE`: legal parties, the personal link, organisations, organisation
   ↔ party links, the acting user's memberships, the user's mandates and their
   scope rows, the property authorities and their scope rows.
3. The chains are evaluated again after the locks, against the database's
   statement-time UTC date (`decision_date`).

`FOR SHARE` conflicts with every `UPDATE`/`DELETE` of those rows, however
issued (API, service primitive, raw SQL), across sessions, workers and
processes. A chain-loss either commits before step 2 (step 3 sees it, the
publication is refused or uses another valid chain) or waits until the
publication commits (serial order: publish, then loss). Two publications
share the locks and do not block each other. No global lock, no process-local
lock.

The decision is the linearisation point: an expiry boundary crossed after it
is the serial order "published, then expired".

## Lock order

```
properties                    FOR UPDATE   (coordination row)
legal_parties                 FOR SHARE    by id
person_legal_parties          FOR SHARE    by id
organizations                 FOR SHARE    by id
organization_legal_parties    FOR SHARE    by id
organization_memberships      FOR SHARE    by id
representation_mandates       FOR SHARE    by id
representation_mandate_scopes FOR SHARE
property_authorities          FOR SHARE    by id
property_authority_scopes     FOR SHARE
classified_offers             conditional UPDATE (TASK-002 lifecycle CAS)
```

Structural review of every write to these tables: membership invite / accept /
revoke, mandate revoke, legal-identity names, authority verify, and the new
organisation / legal-party status primitives each change **one** proof row;
authority revoke and space archive take the Property lock **first**. None
holds a row publication needs while waiting for one publication holds, so no
cycle exists. Price, reveal, conversation and viewing paths touch no proof
table.

## Supported authority-loss paths

| Loss | Path | Coordination |
|---|---|---|
| PropertyAuthority revoke | `POST /v1/admin/property-authorities/{id}/revoke` | Property lock (TASK-002) + authority row FOR SHARE |
| Space archive | `POST /v1/spaces/{id}/archive` | Property lock (TASK-002) |
| Membership revoke | `POST /v1/organizations/{org}/members/{user}/revoke` | row locked `FOR UPDATE` before read; waits on publication's share lock |
| Mandate revoke | `POST /v1/me/mandates/{id}/revoke` | same |
| Organisation suspension | `organizations.set_organization_status` (service only; no endpoint exists — none invented) | same; any UPDATE of the row waits identically |
| LegalParty archival | `parties.set_legal_party_status` (service only) | same |
| Mandate / authority expiry | time | dates evaluated on the database clock at the decision |

## Acceptance tests

`backend/tests/test_publication_authority_race_pg.py` (27) and the TASK-002
`test_publication_race_pg.py` (6):

* each loss (membership, mandate, organisation via service and raw SQL,
  legal party via service and raw SQL) in both serial orders — decided first:
  the loss is observed blocked on its table through `pg_blocking_pids`,
  completes only after the publication, publication 200; lost first:
  publication 403/404, listing stays draft, not public;
* mandate expiry crossed before the decision → refused; after it → published
  (then a new attempt is refused);
* the decision date compiles to `statement_timestamp()` in UTC and matches the
  Python UTC date;
* a surviving chain publishes when the other is revoked first; with two valid
  chains, revoking either waits;
* partial scopes on two chains do not add up to PUBLISH_LISTING;
* nine sequential negatives through the protected path;
* direct authority revoke and space archive regressions unchanged.

Mutation: `backend/scripts/mutation/task004_mutants.py` (9 mutants).

## Out of scope

Everything else; no new endpoints or workflows for suspension or archival;
no change to validity semantics (inclusive `effective_until`, UTC date).

## Codex re-audit

Required on the exact final SHA (TASK-005). F-04 is **CLOSED BY BUILDER —
PENDING CODEX RE-AUDIT** until then.
