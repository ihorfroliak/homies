# TASK-001 — Codex independent audit: canonical convergence + C1–C8

| Field | Value |
|---|---|
| Status | DONE — audit of `988b31b` delivered 2026-09-24 (report: Codex evidence directory `%TEMP%/homies-task001-988b31b/TASK-001-audit.md`, outside the repo); repairs in TASK-002 |
| Owner | Codex, **read-only** |
| Bounded contexts written | none |
| Baseline SHA | the TASK-000 commit on `claude/TASK-000-canonical-governance`, given by the founder at handoff (code is identical to `782c833f100f1bf2e86888b664c9b30b27cbc1dd` apart from legacy docstrings and one boundary test) |
| Codex audit required | This is the audit |

## Goal

Independent evidence on whether the C1–C8 Schema v1 port is safe to build
Phase 1A on, and whether the convergence map is accurate.

## Canonical references

04, 04a, 03 §10–§11, IMPLEMENTATION-CONVERGENCE §2–§5.

## In scope

1. **Authorisation** — `properties/authority.py` (`_holder_parties`, the three
   chains), revocation, mandates, organisation roles; any path that grants
   access by `properties.owner_id` or `listings.host_id` in Phase-1 code.
2. **Privacy** — exact location never in a public DTO or search response;
   public grid point cannot be inverted to the exact point; owner/contact
   data exposure; lead stage and assignee hidden from tenants.
3. **Migrations C1–C8** — data transformations (authority backfill, spaces,
   price components), reversibility, locking on large tables.
4. **Concurrency** — price optimistic concurrency; viewing capacity under the
   settings lock; reveal quota.
5. **C8 media — security focus** (IMPLEMENTATION-CONVERGENCE §5): malformed
   images, parser differentials, resource exhaustion, metadata leakage,
   polyglots, MIME confusion, unsupported formats, memory/CPU bounds;
   recommend keep / harden / replace with a maintained library or isolated
   processing.
6. **Test quality** — would the tests catch the regressions they claim to?
7. **Convergence map accuracy** — classifications and the 22 dispositions.
8. **Parity** — spot-check constraints and indexes against
   `reference/ts-drizzle-schema-v1` (reference only).

## Out of scope

Legacy booking/payments/ledger (dormant); fixes; new features.

## Expected report

AGENTS.md format, exact SHA audited, findings P0–P3/NOTE.
