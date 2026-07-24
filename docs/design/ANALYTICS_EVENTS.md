# Analytics event taxonomy

UI-01. The event contract the frontend emits. The showcase already fires these
via `track()` (console + an on-page feed) to prove the taxonomy; **no analytics
backend is built** — a sink (self-hosted or a vendor) is a future decision.

## Principles

- **Data minimisation** — collect only what answers a product question. No raw
  PII in event properties: use opaque ids (`listing_id`), never names, emails or
  card data.
- **Consent-gated** — behavioural analytics only after consent (GDPR); before
  consent, anonymous/aggregate only. (Consent mode is a future implementation.)
- **Server-authoritative money** — `payment_completed` etc. are UX signals only;
  the ledger/webhooks remain the source of truth for anything financial. A
  client event is never trusted for accounting.
- **Stable names** — `snake_case`, past-tense where it marks completion.

## Events

| Event | Trigger | Properties | User context | Privacy note |
|---|---|---|---|---|
| `search_started` | search submitted | `city`, `guests`, date range | role, anon id | city is coarse (not precise geo) |
| `search_completed` | results rendered | `results_count`, `filters[]` | role | — |
| `listing_viewed` | detail opened | `listing_id`, `position` | role | — |
| `filter_applied` | filter toggled | `filter`, `on` | role | — |
| `favorite_added` / `favorite_removed` | heart toggled | `listing_id` | requires auth | tie to user only when logged in |
| `booking_started` | reserve clicked | `listing_id`, nights | auth | — |
| `payment_started` | checkout opened | `method` | auth | **no card data** |
| `payment_completed` | success screen | `booking_id`, `amount_minor`, `currency` | auth | amount in minor units; UX signal only |
| `booking_cancelled` | cancel confirmed | `booking_id`, `reason` | auth | — |
| `booking_expired` | server-emitted (BK-01) | `booking_id` | system | emitted server-side, not client |
| `host_listing_started` | create-listing opened | — | host | — |
| `host_listing_published` | listing published | `listing_id`, `type` | host | — |
| `free_listing_created` | free listing submitted | `listing_id`, `city` | any | Product B (future) |
| `free_listing_approved` | moderation approved | `listing_id` | moderator | Product B (future) |

## Funnels these enable

- Discovery → booking: `search_started → listing_viewed → booking_started →
  payment_started → payment_completed` (conversion + drop-off per step).
- Host supply: `host_listing_started → host_listing_published`.
- Product B growth: `free_listing_created → free_listing_approved → search…`.

## Implementation status

Showcase emits events client-side (`showcase.js` `track()`). A production
pipeline needs: a consent gate, a sink, and server-side emission for money and
lifecycle events (`booking_expired` already exists as a real domain event and
Prometheus metric; it should feed analytics from the server, not the client).
