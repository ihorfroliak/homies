# TASK-014 — Saved Listings, Saved Search & Alerts

| Field | Value |
|---|---|
| Status | IN_REVIEW — builder complete (Phase B); ChatGPT/founder adjudication and independent audit (TASK-014A) requested. **Not accepted.** |
| Owner (writer) | Claude Code |
| Accepted starting SHA | `3f324b6ddff6c7557894eb5f65736729d956f7eb` (TASK-013 accepted — `TASK_013_PHASE_1A_SLICE_ACCEPTED`, D-77) |
| Branch | `claude/TASK-014-saved-search-alerts` (no PR-001 / PR-001R / PR-002 ancestry) |
| Decisions | D-77 (TASK-013 acceptance record), D-78…D-82; 04a §22 |
| Migration | `f3b5d7e9a1c2` ← `d0f2b4c6e8a1` (TASK-013 head); one head; additive |

## Goal

The first retention loop: **Search → Save → new relevant supply appears →
honest notification → user returns → contact / viewing** — without an alert
flood, without spam, without exposing a home's exact location, and on the
architecture that already exists.

## Phase-A findings applied

* Old canon (04 §51, §81 inv. 20) saved the **Property**; superseded for
  Phase 1A by the founder/Product-Arbiter decision: **SavedListing (user,
  listing)** — 04a §22, D-78.
* `notifications` is the booking-era delivery queue, not a user inbox → a
  dedicated `user_notifications` inbox (`GET /v1/me/inbox`); the old
  `GET /v1/me/notifications` feed is left unchanged (no consumer breaks).
* SMTP defect: `recipient_user_id` was passed as SMTP `To` → every email now
  resolves the account's current address at send time (D-81); the stub
  channel no longer logs addresses.
* No account deletion/status model → "account valid" = user exists (+
  verified email for EMAIL); no parallel lifecycle (04a §22).

## Design (as built)

**One search language.** `search.build_query` is the single validated
constructor of `SearchQuery`, used by the list/map dependency and by
`search.parse_query_string` (strict: unknown parameter or repeated scalar =
error). Stored queries = `SearchQuery.canonical()` + `query_schema_version` (1)
+ `SHA-256(version \n canonical)`; UNIQUE (user, fingerprint). Loading a
stored query re-validates it and requires every named place to exist and be
ACTIVE; otherwise **INVALID** (never matched, never broadened). A
`QueryContext` reads the catalogue and referenced places once per batch.

**Public generation** (`properties/publicity.py`). `make_public` is the only
seam for publish (from draft/paused/active/stale) and confirm (active/stale):
row lock → prior eligibility by the §18 rule at the DB instant → conditional
UPDATE → if it was not public: generation + 1, `public_since`,
`ListingBecamePublic` event (dedup `listing:generation`) and the work item
`listing_public_generations (listing, generation)` — one transaction.
Transitions to not-public need no bookkeeping.

**Matching** (`alerts/matching.py`). Work claimed `FOR UPDATE SKIP LOCKED`.
Superseded (listing now in N+1) or not-public episodes are acknowledged
without matches. Candidates: `saved_search_anchors` (L/G/A/C/*) ∈ listing
keys (its locality, search area, every ancestor admin area, country, `*`),
active, notifying, `baseline_at < became_public_at`. Truth:
`search.evaluate_for_listing` — the same `filters()`, as boolean columns over
the listing's single row, public clause once in the WHERE, identical queries
once, 200 per statement. Matches UNIQUE (search, listing, generation);
deliveries UNIQUE (user, listing, generation, channel), EMAIL only to verified
users.

**Delivery** (`alerts/delivery.py`). Send-time revalidation in order: user,
PRODUCT preference, verified email, listing public, same generation, a
linked search exists / is active & notifying, stored query valid, still
matches → else `suppressed` with a machine reason. IN_APP = inbox row
(UNIQUE delivery_id). EMAIL = verified address + two fresh unsubscribe tokens
(one search / all PRODUCT email). Transient failures back off; permanent → dead.

**Worker & recovery** (`alerts/worker.py`, `app/scripts/saved_search_alerts.py`).
BackgroundWorker `saved-search-alerts` (on by default): work batch 20,
delivery batch 50, every 5 s; reconcile every 60 passes (stale claims → pending;
missing work item restored for public episodes < 7 days, bounded 200).

**API** — `/v1/me/saved-listings[/{id}]` (POST/DELETE/GET),
`/v1/me/saved-searches[/{id}[/matches]]` (POST/GET/PATCH/DELETE),
`/v1/me/inbox`, `/v1/me/inbox/{id}/read`, `/v1/me/notification-preferences`
(GET/PUT), `/v1/notifications/unsubscribe` (POST, unauthenticated, generic).
Rate-limit policies `saved_write`, `preference_write`, `unsubscribe`.

**Metrics** (counts only): `homies_saved_listings_total{action}`,
`homies_saved_searches_total{action}`, `homies_saved_searches_active`,
`homies_saved_search_match_created_total`,
`homies_alert_delivery_total{channel,status}`,
`homies_saved_search_worker_batch_total{stage}`,
`homies_saved_search_work_items_total{outcome}`,
`homies_saved_search_invalid_query_total`, `homies_saved_search_candidates`
(histogram), `homies_unsubscribe_requests_total{outcome}`.

## Product & Growth Doctrine (07) evaluation

| Dimension | TASK-014 |
|---|---|
| UX | Save anything from the search page as-is (page state dropped); zero-result searches are first-class; current matches visible without waiting; saves survive the listing (tombstone), searches survive invalidity (explicit reason) |
| Trust | Alerts only for genuinely new public supply; no flood on saving; a queued alert that stopped being true is never sent; one-click unsubscribe with no account |
| Automation | Worker + reconciliation; no manual step between publication and notification |
| Efficiency | Anchor-narrowed candidates; one statement per 200 distinct queries; fixed reads per batch |
| Liquidity | New supply reaches waiting renters within one worker pass (seconds) |
| Competitive advantage | Notifications honest about freshness (TASK-012) and privacy (public point only) |
| Beauty / desirability | Inbox uses localisation keys; email is short and link-only (frontend work not in scope) |
| Growth | Measurable: saves, active searches, matches, deliveries by channel/status |
| Scalability | ~10⁴ searches × 10³ listings measured locally (below); no cartesian scan |
| Necessity | Nothing speculative: no digest scheduler, no push/SMS, no recommendation engine |

## Deferred, with reasons

* **Digest / cadence**: instant only. A digest needs scheduling and grouping
  semantics; not required for Phase 1A. The unique delivery key already
  prevents instant + digest duplicates when one is added.
* **Alert families** while continuously public (price drop, availability
  date, attributes, media) and **Follow Property** (04a §22).
* **Email locale**: alert emails render in `en` (no user locale field yet).
* **Retention** of done work items / old deliveries: unbounded growth
  proportional to publications; purge job later.

## Scale evidence (LOCAL, not a production benchmark)

PostgreSQL 16.4 / PostGIS 3.4.3 in Docker on a developer laptop; Python 3.12.14.
Synthetic: 500 users; saved searches anchored 40 % Kraków, 30 % Warszawa,
10 % Małopolskie, 10 % country, 10 % no place; each with a max rent and one
other filter. `tests/test_saved_search_scale_pg.py`.

| Shape | New listing in | Candidates | Matches | SQL statements | Evaluation statements | Local seconds | Cartesian equivalent |
|---|---|---|---|---|---|---|---|
| 10 000 searches, 1 000 listings | Kraków | 7 096 | 4 304 | 49 | 15 | 12.5 | 10⁷ |
| | Warszawa | 4 903 | 2 906 | 40 | 12 | 6.1 | 10⁷ |
| | Balice (village) | 3 016 | 1 832 | 35 | 10 | 8.5 | 10⁷ |
| 2 000 searches, 300 listings | Kraków | 1 405 | 876 | 28 | 6 | 3.9 | 6·10⁵ |
| | Warszawa | 969 | 595 | 24 | 4 | 2.1 | |
| | Balice | 560 | 354 | 23 | 3 | 1.8 | |

Candidate selection: bitmap index scans on `ix_saved_search_anchors_key`
(EXPLAIN ANALYZE, 10 000 searches: 13 ms). Before the batching work the same
Kraków case took 33.5 s (per-predicate public clause, no de-duplication,
per-query reference reads); after: 12.5 s with identical results. The
synthetic distribution is deliberately city-concentrated (worst case for
anchors); the per-listing cost scales with candidates, never with the board.

## Out of scope

Property following; price-drop/availability-change alerts; recommendations;
marketing campaigns; SMS; push; paid email provider activation; applications;
tenant profile; contracts; payments; short-stay; SEO pages; agency import;
Redis/Kafka/NATS/Celery/Airflow; PR-001R integration; PR-002 migrations;
staging/deployment.

## Independent audit (TASK-014A) — requested focus

Public-generation correctness across every publication path and under races;
the atomicity of generation/event/work item; send-time revalidation and
unsubscribe; SMTP recipient resolution; stored-query INVALID handling (no
broadening); anchor narrowing never excluding a true match; privacy of
tombstones, inbox, events, logs, metrics; migration backfill/round trip.

## Evidence

See `docs/reviews/2026-09-28-task014-mutation.md` (mutations, scale) and the
final builder report. CI: **NOT RUN** (branch not pushed).

## Known debt

* Alert email locale fixed to `en`; no digest; no retention/purge for work
  items, deliveries, tokens.
* Race window: a search saved while a publication's transaction is in flight
  (publication instant < baseline, commit after) is not notified about that
  listing — by design of "no historical alert"; documented, not repaired.
* Anchors choose one dimension; a search with only non-geographic filters is
  a candidate for every listing in its market (bounded by the '*'/country
  share; measured above).
* `evaluate_for_listing` cost is dominated by building/compiling one SQL
  expression per distinct query (~1–2 ms each locally); a cached predicate
  or denormalised prefilter columns are the next step if needed.
* The booking-era `GET /v1/me/notifications` feed remains (legacy shape).
