# UI-STATE-MAP — what the UI may show for each domain state

Part of [DESIGN-001](DESIGN-001-product-ui-foundation.md). Every UI state maps
to an API value; the UI may simplify wording, never invent a state or
contradict the backend. The backend is authoritative for publication,
authority, moderation, conversation and viewing status, outcomes and QAL.

| Object | API truth | Seeker sees | Owner / provider sees |
|---|---|---|---|
| Listing | `status ∈ draft, active, paused, stale, archived`; `freshness ∈ FRESH, RECONFIRM_DUE, STALE`; owner view `moderation.state ∈ NONE, HELD` (+ action, reason code, since, review NONE/OPEN/ANSWERED) | public only when active + fresh + not held; anything else is **404, identical to never-existed** (D-59) → the Unavailable screen | one primary chip, by priority: **Wstrzymana przez Homies** (HELD) > Zarchiwizowana > Nieaktualna (stale) > Wstrzymana (paused) > Szkic > Aktywna; on Aktywna a freshness chip (Aktualna / Wymaga potwierdzenia) |
| Saved listing | `availability_status ∈ AVAILABLE, NO_LONGER_AVAILABLE` | tombstone "Ta zapisana oferta nie jest już dostępna" with `saved_at` and remove only — no title, price or photo | — |
| Saved search | `status ∈ active, paused`; `query_state ∈ VALID, INVALID` (+ `invalid_reason`); `match_count` | INVALID → "Tego wyszukiwania nie da się już wykonać" + edit; never silently broadened | — |
| Conversation | `status ∈ ACTIVE, ARCHIVED, CLOSED`; SYSTEM line `system.conversation_closed_by_homies` | CLOSED with that line → "Rozmowa została zamknięta przez Homies."; the composer is replaced by a notice; no reason. A new conversation on the same publication may be refused (409 `RECONTACT_BLOCKED`, G-14) | same notice; `provider_stage` only on the provider side |
| Message | `moderation_state ∈ NONE, REMOVED`; `body: null` when removed | "Wiadomość usunięta przez Homies" (muted, italic) | same |
| Viewing | `status ∈ REQUESTED, CONFIRMED, DECLINED, CANCELLED, COMPLETED, NO_SHOW`; `cancelled_by_homies` | Oczekuje na potwierdzenie · Potwierdzone · Odrzucone · Odwołane / **Odwołane przez Homies** · Odbyte · Nieobecność | same + confirm / decline / outcome; confirm on a held listing → 409 `LISTING_HELD` ("Oferta jest w przeglądzie moderacji") |
| Media | `moderation_state ∈ PENDING, APPROVED, REJECTED, RESTRICTED` | only APPROVED and servable photos ever appear | per-photo chip: W weryfikacji · Zatwierdzone · Odrzucone · Ograniczone (RESTRICTED: cannot be attached; 409 `MEDIA_RESTRICTED` in upload review) |
| Report | reporter view `received` / `reviewed` | "Zgłoszenie przyjęte" / "Zgłoszenie rozpatrzone"; never the outcome (L13) | — |

## Errors (frontend error model)

| HTTP | Meaning | UI |
|---|---|---|
| 401 | session expired | refresh through the BFF once, then sign in again (return-to-intent) |
| 403 | not allowed | "Nie masz dostępu do tej strony." — no detail |
| 404 | not found / not public | Unavailable screen (D-59 wording) |
| 409 | conflict with a stable code (`STALE_HEAD`, `CONVERSATION_CLOSED`, `LISTING_HELD`, `RECONTACT_BLOCKED`, `MEDIA_RESTRICTED`) | reload + an explanation per code |
| 422 | validation | field errors from `detail[]`; invalid search params dropped |
| 429 | rate limited | `Retry-After`-aware message; automatic retry for reads |
| 503 | database unavailable | reads: one retry when `Retry-After ≤ 2 s`; writes are never retried — when the commit outcome is unknown: "Nie możemy potwierdzić, czy zapisano. Odśwież przed ponowieniem." |
| network | offline | offline banner; inputs and filters kept |
