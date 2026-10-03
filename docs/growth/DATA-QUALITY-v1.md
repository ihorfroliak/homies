# DATA-QUALITY-v1 — checks that make growth numbers trustworthy

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md). Each check
is a predicate that must hold; violations are observable (counted, alerted
when a destination exists), never transactional — analytics failure never
blocks the product. Now: schema/payload tests in CI (`test_measurement_facts.py`,
event payload pins); the rest run as SQL once ingestion and snapshots exist.

| ID | Check |
|---|---|
| DQ-1 | every `listing_public_generations` row has its `ListingBecamePublic` event (`event_id`) and vice versa |
| DQ-2 | `classified_offers.public_generation` = max generation; `public_since` = its `became_public_at` |
| DQ-3 | generations per listing are contiguous 1…n |
| DQ-4 | a conversation's first message is the tenant's; `conversations.created_at ≤ min(messages.created_at)` |
| DQ-5 | viewing state coherence: CANCELLED ⇔ `cancelled_at`; COMPLETED/NO_SHOW ⇒ `completed_at` and `responded_at`; every CANCELLED viewing after GROWTH-001 has exactly one `ViewingCancelled` |
| DQ-6 | clock skew: client `occurred_at` vs `received_at` > 24 h → late flag; outbox `occurred_at` (application clock) never used for windows |
| DQ-7 | CONFIRMED viewings with `ends_at < now − 72 h` (outcome unrecorded), per provider |
| DQ-8 | exclusion leakage: no metric numerator contains an EXCL account (anti-join test) |
| DQ-9 | bot screen: sessions above X searches/min or without rendered events are flagged and excluded |
| DQ-10 | search reconciliation: client `result_count` buckets vs Prometheus `homies_search_requests_total` ratios, within tolerance (directional) |
| DQ-11 | duplicates: > 1 public listing per space; the same normalized address across properties |
| DQ-12 | envelope: unknown event or version → quarantined; duplicate `event_id` → dropped and counted; `anonymous_id` without analytics consent → **P1 privacy violation** (drop, alert) |
| DQ-13 | forbidden fields: payload scanner for e-mail/phone patterns, coordinates with > 3 decimals, keys on the forbidden list |
| DQ-14 | cost CSV: no gaps per date × channel for live campaigns; currency matches the cell; integer minor units; unique keys |
| DQ-15 | NULL-category share among public Kraków listings (cell-membership loss) |
| DQ-16 | Prometheus counter resets detected; operational counters never summed across restarts |
| DQ-17 | impossible funnel order: a viewing responded/outcome fact before its request; a stage change on a conversation that does not exist |
