# EVENTS-v1 — event contract and ownership

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md). Supersedes
`docs/design/ANALYTICS_EVENTS.md` (booking-era). The machine-readable catalogue
of domain events is [`docs/api/events.asyncapi.yaml`](../api/events.asyncapi.yaml)
(Phase-1 events first; booking-era channels marked LEGACY_DORMANT).

## 1. Principle: business facts come from the server

A business fact is emitted by the server — from the transactional outbox, or
derived exactly from operational tables. The browser emits only what the
server cannot see (exposure, navigation, attribution). Where both could, the
server is authoritative and the client value is a cross-check — never a second
count of the same action.

## 2. Server facts (outbox `domain_events`)

Common rules: ids, closed codes and database instants only; never a message
body, note, report text, explanation, address, coordinate, price input or
contact; unrouted (not in `events.ROUTING` — nobody is notified); written in
the transaction that makes the change (a rollback leaves no fact); payloads
only gain optional keys — a breaking change gets a new name (so no version key
inside the payload, as for `ModerationDecisionRecorded`, Phase A §12). Tests
pin each payload (`tests/test_measurement_facts.py`, S1–S4b tests).

| Event | Emitter | Trigger | Payload keys | Dedup key | State |
|---|---|---|---|---|---|
| ListingBecamePublic | `properties/publicity.py` | not public → public (new generation) | listing_id, property_id, public_generation, became_public_at | `…:{listing}:{generation}` | existing |
| ListingConfirmed / ListingReactivated | `properties/freshness.py` | owner confirms availability | listing_id, property_id, last_confirmed_available_at, confirmation_valid_days, auto_pause_after_days | `…:{listing}:{instant}` | existing |
| ListingReconfirmationDue / ListingAutoPausedStale | freshness sweep | 14 d / 21 d | same | same | existing |
| ModerationDecisionRecorded | `trust/decisions.py` | any decision | decision_id, target_type, target_id, listing_id, action, reason_code, supersedes_decision_id, effective_from | `…:{decision}` | existing |
| **ListingStatusChanged** | `events/facts.py` from every status writer | publish/reconfirm, owner pause, moderation hold, authority lost, space archived, stale sweep | listing_id, property_id, from_status, to_status, reason_code ∈ {PUBLISHED, RECONFIRMED, OWNER_PAUSE, MODERATION_HOLD, AUTHORITY_LOST, SPACE_ARCHIVED, STALE_SWEEP}, public_generation, changed_at | `…:{listing}:{uuid}` | **built (GROWTH-001)** |
| **ViewingRequested** | `engagement/viewings.py` | request | viewing_id, listing_id, booking_mode, initial_status, starts_at, requested_at | `…:{viewing}` | **built** |
| **ViewingResponded** | `engagement/viewings.py` | confirm / decline | viewing_id, listing_id, to_status, responded_at | `…:{viewing}` | **built** |
| **ViewingCancelled** | viewings `cancel`; `trust/effects.py` | requester / provider cancel; close_engagement | viewing_id, listing_id, prior_status, cancelled_by ∈ {REQUESTER, PROVIDER, HOMIES}, moderation_decision_id, cancelled_at | `…:{viewing}` | **built** |
| **ViewingOutcomeRecorded** | viewings `record_outcome` | COMPLETED / NO_SHOW | viewing_id, listing_id, outcome, starts_at, recorded_at | `…:{viewing}` | **built** |
| **ConversationStageChanged** | conversations `set_stage` | provider lead stage change | conversation_id, listing_id, from_stage, to_stage, changed_at | `…:{conversation}:{version}` | **built** |
| ListingOutcomeReported | owner flow (G-15) | provider answers at pause/end: RENTED_VIA_HOMIES / RENTED_ELSEWHERE / WITHDRAWN / OTHER | listing_id, public_generation, outcome_code, attributed_conversation_id?, reported_at | `…:{listing}:{generation}` | **designed** (§5) |

**Derived exactly from tables (no event needed):** user signed up
(`users.created_at`), property / listing / authority created, authority
verified (audit), contact revealed (`contact_reveals`, unique offer × viewer),
conversation started, messages, provider first response, saved searches
(audit). Saved-listing removal is hard-deleted today (gap — an audit row on
unsave is the smallest fix, NORMAL DEBT).

## 3. Client events (FE-001 abstraction; sinks noop / memory / console only)

Envelope:

| Field | Rule |
|---|---|
| event_id | UUID minted on the client; the ingest dedup key |
| event_name, schema_version | closed catalogue below; integer version per name |
| occurred_at | client time; ingest stamps `received_at` (authoritative for windows) |
| anonymous_id | **only with analytics consent**; otherwise absent |
| session_id | always; in memory/session only; rotates after 30 min idle, on a new non-direct touch, at local midnight |
| user_id | **never sent by the client** — the server derives it at authenticated ingest |
| platform | `web` + app version |
| route | the route template (`/oferta/[id]`), never a raw URL or query string |
| market | country, cell id, locale — codes only |
| attribution_ref | opaque id of a stored touch (ATTRIBUTION-v1); absent without consent |
| experiments | `[{experiment_key, version, variant}]` assigned (exposure is its own event) |
| consent | `{policy_version, analytics, marketing}` |

| Event | Trigger | Safe dimensions | Forbidden |
|---|---|---|---|
| session_started | first event of a session | platform, route | referrer path |
| landing_viewed | first page of a session | route, channel code | raw URL |
| attribution_captured | a touch is recorded (consent) | channel code, utm allowlist, click-id **present** flag | raw click ids, referrer path |
| signup_started | auth form opened for an intent | intent code (save, message, viewing, phone) | email |
| search_performed | API response for a new canonical query | `search_id`, filter-dimension set, locality/area ids, space type, category, price band (500 PLN steps on monthly total), sort, `result_count` (= API total), surface | bbox/near values, free text (the API has none) |
| search_results_viewed | a results page rendered | search_id, page index, visible count | — |
| listing_viewed | detail rendered | listing_id, search_id, absolute position | — |
| map_mode_entered | map surface shown | search_id | viewport |
| experiment_exposed | variant-specific UI rendered (first time) | experiment key, version, variant | — |
| consent_updated | banner action | policy version, categories | — |
| web_vital | Core Web Vitals report | metric, value, route | — |

**Derived, not emitted:** `search_zero_results` (= `result_count = 0`),
`successful_search` (the search_id is followed by a listing view or an L0
action in the session).

**Correlation:** `search_id` → results → `listing_viewed` → save / contact
(the server action carries the search reference later) → conversation →
viewing.

## 4. Identity

* No analytics consent: no anonymous_id, nothing persisted; a session_id
  lives in memory. Server facts and table-derived metrics still work for
  logged-in users.
* With consent: a random first-party `anonymous_id`. The login join happens
  on the server (`analytics_identity_links(anonymous_id, user_id, linked_at,
  consent_policy_version)` — designed, not built), never asserted by the
  client. Logout rotates anonymous_id and session_id (shared devices).
  Account deletion deletes the links; aggregates stay. No cross-device
  resolution is promised. Analytics identity is never authentication identity.

## 5. Housing-outcome capture seam (G-15) — designed, built in the owner-flow slice

When a provider pauses, archives or lets a listing lapse, the owner UI asks
once per public generation: *"Czy mieszkanie zostało wynajęte?"* —
RENTED_VIA_HOMIES / RENTED_ELSEWHERE / WITHDRAWN / OTHER (optional), with an
optional pick of the conversation it came from (the provider's own leads
only). Stored as `listing_outcomes(listing_id, public_generation, outcome_code,
attributed_conversation_id, reported_by_user_id, reported_at)` (UNIQUE per
listing × generation; EXPAND migration) and emitted as
`ListingOutcomeReported`. Later: the matched tenant may confirm (L7). Rules:
answering is never required to pause; no incentive for an answer; never
inferred; the tenant is never shown the provider's answer.

## 6. Versioning

Additive keys → same version (client) / same name (server). A rename,
removal or semantic change → new major version with a dual-emit window
(client) or a new event name (server). Unknown names or versions are
rejected by schema tests and quarantined at ingest (DQ-12).
