# TASK-002 — Foundational repair and Phase-1 runtime isolation

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Owner (writer) | Claude Code — sole writer of the contexts below for this task |
| Bounded contexts written | app composition (`main`), admin, properties (publication, authority revoke, location, contact reveal, listing terms, property subtype), media, engagement (conversations, viewings), tests |
| Baseline SHA | `988b31b138436cb69ad20e5cb06e6e3be116fe64` (TASK-000) |
| Branch | `claude/TASK-002-foundational-repair` |
| Codex audit required | **Yes** — targeted re-audit of F-01…F-09 closure plus regression of the C1–C8 protections TASK-001 confirmed (authorisation, concurrency, media, migrations are all on the 05 §9 list) |

## Goal

Close every defect the independent TASK-001 audit confirmed at `988b31b`,
by repairing the underlying invariant — not by adjusting tests — so that
C1–C8 remains the foundation and Phase 1A has one runtime truth.

## Findings addressed

| Finding | Severity | Context | Repair cycle |
|---|---|---|---|
| F-01 legacy runtime still active | P1 | composition, admin | R1 |
| F-04 publication commits after authority revoke | P1 | properties | R2 |
| F-07 invalid coordinates accepted | P2 | properties/location | R2 |
| F-02 media metadata / GPS leakage | P1 | media | R3 |
| F-05 upload limit checked after unbounded read | P1 | media | R3 |
| F-03 contact reveal quota race | P1 | properties/contact | R4 |
| F-06 confirm resurrects cancelled viewing | P2 | engagement/viewings | R4 |
| F-08 nonexistent DST wall time offered | P2 | engagement/viewings | R4 |
| F-09 conversation create race | P2 | engagement/conversations | R4 |

Also: the false-positive negative-price test (audit §13) and the boundary
detector gaps (`from .. import booking`, dynamic imports).

## In scope

* **R1** — explicit Phase-1 application composition; legacy routers and
  workers not registered or started; Phase-1 admin split from legacy admin;
  a narrowly scoped legacy test composition; runtime + static boundary tests.
* **R2** — publication/revoke serialisation with one documented lock order and
  a conditional lifecycle update; coordinate range/finite/pair validation at
  API and DB with a preflight that refuses invalid existing rows.
* **R3** — Pillow-based decode → bound → orientation → re-encode pipeline
  replacing the custom walker as trust boundary; streaming ingress bound;
  quarantine of assets processed by the old sanitiser; real-image test corpus.
* **R4** — contact-reveal quota serialised on the viewer row; viewing
  lifecycle transitions conditional on current state, with a lock order
  compatible with the capacity lock; DST round-trip validation;
  conversation uniqueness at DB level plus sender-serialised quota.
* Canonical decisions below, recorded in the canon and applied in code where
  bounded.
* Migration/release operational note (audit §10).

## Out of scope

C9; structured address; safety; reports/moderation decisions; authority
evidence; saved search/property; listing texts; freshness; EPC; legal
acceptance; marketing consent; media derivatives beyond safe processing;
applications; Housing Passport; SALE; payments; contracts; MONTHLY;
Short-Stay modernisation (F-01 is fixed by isolation, not by adapting legacy);
provider-level contact quotas; full property-type migration if not bounded;
deployment of any kind.

## Canonical decisions (founder, 2026-09-24, TASK-002 §23–§24, §44)

* **LONG_TERM** is the non-transactional residential-rental marketplace mode.
  It has **no mandatory six-month minimum**. `min_term_months` is NULL
  (open-ended) or ≥ 1. MONTHLY remains the future transactional product and is
  not activated.
* **APARTHOTEL_UNIT** is an `APARTMENT` subtype, not a property type.
  Publication of such units fails closed until an explicit residential-use
  eligibility policy exists — **LEGAL/POLICY REVIEW REQUIRED**. ROOM is never
  a property type.
* **DST**: a Phase-1 viewing slot maps one local wall time to exactly one UTC
  instant. Nonexistent (spring-forward) and ambiguous (fall-back) wall times
  are not offered.

## Hard invariants

1. The normal application registers no legacy short-stay, booking or payment
   route and starts no legacy worker.
2. After a PropertyAuthority revoke commits, no in-flight publication relying
   only on that authority can commit an active listing.
3. Public media bytes are produced by decode + re-encode; no original metadata
   survives. Upload ingress never buffers beyond the configured limit.
4. Persistent contact-reveal quota holds across concurrent sessions.
5. A viewing cannot leave a terminal state; `CONFIRMED` never co-exists with
   `cancelled_at`.
6. Exact coordinates are finite, in range, and either both present or both
   absent — at API and DB level.
7. At most one active conversation per requester + listing; new-conversation
   quota holds under concurrency.
8. Every C1–C8 protection TASK-001 confirmed stays green.

## Acceptance criteria

TASK-002 §58: F-01…F-09 each closed by a regression test that fails against
`988b31b` (demonstrated by mutation/restore), existing suites green.

## Required tests

* Runtime composition tests on the real app object (routes, OpenAPI, workers).
* PostgreSQL concurrency tests with deterministic synchronisation (barriers,
  lock waits observed in `pg_stat_activity`), not sleeps alone.
* Real decodable images (Pillow-generated) incl. EXIF/GPS, XMP, PNG text,
  ICC, malformed, oversized, pixel bombs, wrong MIME, unsupported, trailing
  payload.
* DST tests for Europe/Warsaw winter, summer, spring-forward, fall-back.
* Mutation checks for each repaired invariant; green baseline first; only
  assertion failures count; exact source bytes restored.

## Security and privacy considerations

Media is untrusted binary input: the decoder has its own attack surface —
pixel budget, decompression-bomb errors, decoder exceptions all map to a
rejection, never a 500 with a partial file. Legacy public DTO with exact
address and `host_id` must be unreachable in Phase-1 runtime.

## Forbidden regressions

Price CAS, capacity lock, three authority chains, public DTO privacy, DB
append-only triggers/privileges, DR restore.

## Expected report

TASK-002 §63 format, ending with `DEPLOYMENT STATUS: NOT DEPLOYED` and the
exact SHA for Codex.
