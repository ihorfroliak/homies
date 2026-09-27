# TASK-012 — Listing freshness, availability & marketplace quality

| Field | Value |
|---|---|
| Status | IN_REVIEW — builder complete; ChatGPT/founder adjudication and independent audit requested |
| Owner (writer) | Claude Code |
| Accepted starting SHA | `ed9cf1b49f70716bd214a3212b2e7497ca5078ec` (TASK-010 Phase-1A slice, accepted by TASK-011R) |
| Branch | `claude/TASK-012-listing-freshness-availability-quality` |
| Decisions | D-59…D-65 (this task), D-66 (TASK-010 acceptance record); 04a §18–§19 |

## Goal

Make every published LONG_TERM listing reliably **current** (someone with
authority recently said so), make its **move-in availability** honest, and
tell the owner **exactly what would improve it** — so stale supply leaves the
board by itself instead of poisoning liquidity.

## Product & Growth Doctrine (07 §2)

| Dim. | Effect |
|---|---|
| A2 Trust | Public "confirmed current" signal (`confirmed_on`, FRESH / RECONFIRM_DUE), never labelled as verification; unknown move-in dates shown as unknown |
| A5 Liquidity | Stale supply leaves the board at 21 days automatically; renters stop contacting let flats |
| A3 Automation | Idempotent sweep (CLI / off-by-default worker) + reminder events; no human moderation needed |
| A1 UX | One owner action to stay current and to come back; `GET /v1/me/classifieds` shows status, freshness dates, completeness and concrete next steps |
| A4 Efficiency | Derived state, no stored scores or dates to drift; one visibility rule |
| A8 Growth | Events for time-to-reconfirm, stale rate, reactivation rate; SEO consequence recorded (stale = unpublished) |
| A9 Scalability | Policy is data in one module; the sweep batches, skips locked rows and is safe to run in parallel |
| A10 Necessity | Canon (02 §1 Phase 1A "freshness", 04 §43/§127) and 07 A2/A5 |

## AS-IS (at `ed9cf1b`)

* `classified_offers.status` free text (no CHECK): draft / active / paused /
  archived (archived only via SQL); `PUBLISHABLE_FROM = draft, paused,
  active`; `published_at` from the process clock; `version` = price CAS.
* Manual pause: unconditional ORM write (could turn archived into paused,
  which publish then made active again).
* Availability: `available_from` (date, nullable), `min_term_months` ≥ 1 or
  `open_ended`; no edit endpoint; `available_by` treated NULL as "now".
* Public visibility checked separately in seven places: list, detail, contact
  reveal, conversation start, viewing slots, viewing request, media GET.
* No owner view of the owner's own listings; no freshness column; no quality
  concept; events: append-only DomainEvent + outbox, routing booking-only;
  workers: BackgroundWorker seam in `composition.py`; DB decision clock in
  `authority.decision_date`.
* Canon 04 §43 defines `last_confirmed_available_at`, `reconfirm_at`,
  `stale_at`, STALE; §127 the search freshness rule; §44 rental terms.

## Design (as built)

| Area | Decision |
|---|---|
| Stored fact | `last_confirmed_available_at timestamptz` (canonical name). Publication and confirmation set it from the database clock |
| Policy | `properties/freshness.py`: `CONFIRMATION_VALID_FOR = 14d`, `STALE_GRACE_PERIOD = 7d`, `AUTO_PAUSE_AFTER = 21d`; mutable Phase-1A policy (D-60) |
| Derived | FRESH (< 14d), RECONFIRM_DUE (14d ≤ age < 21d), STALE (≥ 21d); `reconfirm_at`, `stale_at` computed, not stored |
| Visibility | `freshness.public_clause(db)` (SQL) and `freshness.is_public(offer, now)` (loaded row): `active` AND confirmed within 21 days on the DB clock. Used by all seven public paths |
| Status | canonical `stale`; status CHECK `draft/active/paused/stale/archived`; `PUBLISHABLE_FROM` gains `stale`; `CONFIRMABLE_FROM = active, stale`; `PAUSABLE_FROM` excludes archived |
| Confirm | `POST /v1/classifieds/{id}/confirm` — VERIFIED authority, property lock, `authorize_for_mutation`, then the offer row FOR UPDATE; refuses draft/paused/archived (409); runs listable-space and publishable-type checks; no `version` bump; audit + `ListingConfirmed` / `ListingReactivated` |
| Reactivation | stale → active through confirm (one action) or publish; never from archived |
| Sweep | `freshness.sweep`: one conditional `UPDATE … WHERE id IN (… FOR UPDATE SKIP LOCKED LIMIT n) AND status='active' AND last ≤ cutoff RETURNING`; reconfirmation-due events once per cycle. CLI `python -m app.scripts.listing_freshness sweep|preflight`; BackgroundWorker `listing-freshness`, off by default |
| Availability | NULL = unknown (D-64); `available_by` excludes NULL; `move_in` = NOW / FROM_DATE / UNKNOWN derived; `PUT /v1/classifieds/{id}/availability` with `expected_version` |
| Quality | `properties/quality.py`, derived, owner-only (D-63) |
| Owner view | `GET /v1/me/classifieds` (authority `PUBLISH_LISTING`): public shape + `published_at`, `freshness_detail`, `quality` |
| Public signal | `confirmed_on` (date), `freshness` (FRESH / RECONFIRM_DUE), `move_in` |
| Events | D-65; no routing / transport |
| Migration | `b8d0f2a4c6e8`: unknown-status preflight, column, backfill from `published_at`, CHECK, index; no status change (D-62). Downgrade: stale → paused |

Lock order in confirm = publication's: property → proof rows FOR SHARE →
offer FOR UPDATE. The sweep locks offer rows only (skip-locked), so no cycle
with publication, revoke or space archive.

## SEO consequence (recorded, not built)

A stale or otherwise unpublished listing must eventually be removed from the
index / served `noindex` by the future routing layer; the public API already
answers 404 for it exactly as for an unpublished listing.

## Out of scope

Search/map UX, saved property/search, alert delivery, tenant profile,
applications, viewing redesign, contracts, payments, ledger, short-stay
calendar, iCal, ML ranking, recommendations, referral, frontend redesign,
`expires_at`, `available_until`, `maximum_lease_months`.

## Acceptance tests

`tests/test_listing_freshness.py` (SQLite), `tests/test_listing_freshness_pg.py`
(PostgreSQL: thresholds, DB clock, races, migration), updated
`test_classifieds_search.py` (D-64), `test_phase1_runtime.py` (worker
registered, off). Mutation: `scripts/mutation/task012_mutants.py`.

## Maintenance carried with this task

* TASK-011R N11R-01: stale "owner opt-in EXACT" comment in `ClassifiedOut`
  corrected.
* TASK-011R N11R-02: R08/R11 kill descriptions in the TASK-010R mutation
  report corrected to the observed mechanisms.

## Independent audit

**Required** (05 §9): a data-transforming migration and a change to what the
public can see (visibility of every listing), plus new concurrency paths
(confirm / sweep / reactivation).

## Evidence (2026-09-27, local; Python 3.14.3 venv, PostgreSQL 16.4 / PostGIS 3.4.3 container)

| Check | Result |
|---|---|
| Full suite, SQLite | 779 passed, 245 skipped |
| Full suite, PostgreSQL/PostGIS | 1024 passed, 1 skipped (Stripe Test Mode suite) |
| After later test-only edits: `test_listing_freshness.py` (SQLite) / both freshness files (PG) | 36 passed / 47 passed |
| ruff · mypy · OpenAPI `--check` | clean · no issues (86 files) · up to date |
| Migration | TASK-010R head `a7c9e1f3b5d7` → `b8d0f2a4c6e8` on draft/active(old)/active(recent)/paused/archived rows; full-row compare; downgrade (stale → paused) and up; unknown status refused; fresh → head every PG session |
| Mutation | 16 / 16 killed ([report](../reviews/2026-09-27-task012-mutation.md)) |
| Query amplification (PG, 10 listings, out-of-repo probe) | public list limit 1/5/10: 6/10/15 SELECTs vs 5/9/14 at `ed9cf1b` — **+1 per request** (the DB clock read), none per row; owner view: 25 for 10 listings (~2 per listing: authority check, address) |

Python 3.12 and CI not run.

## Known debt

* Public `place` N+1 (from TASK-010) unchanged; owner view ~2 queries per listing.
* No reminder delivery; events only (D-65).
* `expires_at`, `available_until`, `maximum_lease_months` (04 §43/§44) not built.
* Status names still lower-case (`active` for 04's PUBLISHED) — Listing
  aggregate convergence.
* `published_at` is re-stamped when a paused/stale listing is published again
  (existing behaviour); confirmation does not touch it.
* Sweep scheduling is the operator's choice (CLI or worker flag); visibility
  never depends on it.
* The mutation inspector hit a transient Windows file-write error once while
  restoring `router.py`; the file was restored by reversing the exact mutation
  and verified against the saved SHA-256 before anything else ran.
