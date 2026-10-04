# FE-003 — Save → Conversation → Viewing · READINESS + TASK CONTRACT DRAFT

| Field | Value |
|---|---|
| Status | **DRAFT — implementation NOT authorised.** Finalised only after the approved DESIGN-001C handoff (D-103), then founder + GPT-5.6 Sol approval |
| Baseline | `main` after the PROGRAM-001 merge (`c32ac63`) and the D-102 integration commit (F6 enforced) |
| Risk class (implementation) | **R2** (auth/session, private engagement, privacy, concurrency) |
| Canon | 02 §2; 03 §2; 04a §16, §21, §22, §23, §24; 07; DESIGN-001 (+ DESIGN-001C when approved); FE-001, FE-002 |
| Out of scope | final 1C visuals; owner panel; moderator app; applications/Housing Passport; payments |

Classification used below: **CURRENT** (backend ready, FE can call it) ·
**CURRENT + CLIENT COMPOSITION** (ready; the client combines calls/state) ·
**BACKEND/API GAP** · **PRODUCT PROPOSAL** · **DESIGN-DEPENDENT** ·
**BETA BLOCKER** · **FUTURE**.

## 1. Readiness inventory (verified in code at `c32ac63` + D-102 commit)

### 1.1 Save

| Item | State | Class |
|---|---|---|
| Saved listings: `POST/DELETE /v1/me/saved-listings/{listing_id}`, `GET /v1/me/saved-listings` (04a §22; `SAVED_WRITE` limit) | built, TASK-014 accepted | CURRENT |
| Saved searches: `POST/GET/DELETE /v1/me/saved-searches[/{id}]`, `GET …/{id}/matches`; alerts in-app/e-mail with unsubscribe | built; a new query gets a new baseline (no initial alert flood) | CURRENT |
| "Is this listing saved?" on cards/detail | no saved-state on `ClassifiedOut`; client can read the user's saved ids (`GET /v1/me/saved-listings`) once per session | CURRENT + CLIENT COMPOSITION (gap G8 for an efficient flag) |
| Save the current FE-002 search | FE codec → canonical API query string; backend validates it | CURRENT + CLIENT COMPOSITION |
| BFF allowlist entries for these routes (FE-001 §3) | not yet listed | CURRENT + CLIENT COMPOSITION (FE work) |
| Save button placement, saved list UI | — | DESIGN-DEPENDENT |

### 1.2 Conversation

| Item | State | Class |
|---|---|---|
| Start requires a real first message: `POST /v1/classifieds/{id}/conversations` with `{body}` | built | CURRENT |
| One active thread per requester × listing (writing again continues it; partial unique index backstop) | built | CURRENT |
| Requester needs only a signed-in account (no phone/e-mail gate for messages) | built (messages are the channel for unverified users) | CURRENT |
| Provider side by authority (`MANAGE_MESSAGES` via PropertyAuthority), assign, stage (`NEW, REPLIED, VIEWING, APPLICATION, SHORTLISTED, ACCEPTED, REJECTED, ARCHIVED`) | built | CURRENT (provider UI is out of FE-003 seeker scope) |
| Moderation: message reports, redaction for participants, `CLOSED` threads with the SYSTEM line `system.conversation_closed_by_homies`; `409 CONVERSATION_CLOSED` on send | built (TASK-015) | CURRENT |
| Re-contact block G-14: `409 RECONTACT_BLOCKED` for the same publication generation | built | CURRENT |
| Rate limits: `CONVERSATION_START` (10, 1 per 20 s), `MESSAGE_WRITE` (30, 0.5/s), daily new-conversation quota 30 | built | CURRENT |
| `can_send` / `closed_by` on `ConversationOut` (gap G9 in DESIGN-001 §9) | client infers from status + last SYSTEM line | CURRENT + CLIENT COMPOSITION; BACKEND/API GAP for an explicit field |
| Real-time delivery (push/websocket) | polling only | FUTURE |
| Conversation hierarchy, composer, closed-state presentation | — | DESIGN-DEPENDENT |

### 1.3 Viewing

| Item | State | Class |
|---|---|---|
| `ViewingSettings` (`booking_mode` `INSTANT_BOOKING` \| `REQUEST_APPROVAL`, duration, minimum notice, `max_concurrent_bookings`, timezone), `ViewingWindows` (one-off/recurring), `ViewingBlackouts` | built (provider APIs) | CURRENT |
| Offered slots **derived** from settings + windows − blackouts − capacity: `GET /v1/classifieds/{id}/viewing-slots` (DST-safe, 04a §14) | built; no persisted slot entity — none is needed | CURRENT |
| Request: `POST /v1/classifieds/{id}/viewings` `{starts_at, attendee_count, note}`; instant → `CONFIRMED`, else `REQUESTED` | built | CURRENT |
| States `REQUESTED / CONFIRMED / DECLINED / CANCELLED / COMPLETED / NO_SHOW`; provider confirm/decline, either side cancel, provider outcome | built | CURRENT |
| Capacity/conflict: capacity read under a settings lock; slot must be offered | built | CURRENT |
| Existing-viewing restriction: one future REQUESTED/CONFIRMED viewing per requester × listing (409) | built | CURRENT |
| Held listing: confirm refused `409 LISTING_HELD`; `close_engagement` cancels future viewings (`cancelled_by_homies`) | built | CURRENT |
| **F6**: G-14-restricted requester cannot request a viewing for the same generation (`409 RECONTACT_BLOCKED`) | **enforced** (D-102 integration commit) | CURRENT |
| Viewing ↔ Conversation link (auto-create a thread on request) | not built; no canonical decision | PRODUCT PROPOSAL (needs canonical/backend decision; do **not** auto-create) |
| Explicit immutable cancellation source REQUESTER / PROVIDER / HOMIES | derived today (`cancelled_by_homies` from decision-instant equality) | BETA BLOCKER (before disputes/UI rely on it) |
| Slot presentation, booking flow, bottom-sheet anatomy | — | DESIGN-DEPENDENT |

### 1.4 Contact reveal

| Item | State | Class |
|---|---|---|
| `contact_mode` `phone` \| `message` per listing; `POST /v1/classifieds/{id}/contact` discloses the phone | built | CURRENT |
| Gate: **verified phone** of the viewer (`403` otherwise); `409` when the owner accepts messages only; daily quota (20) `GET /v1/me/reveal-quota`; every reveal recorded; `CONTACT_REVEAL` limit | built | CURRENT |
| Phone verification: `POST /v1/me/verify/phone/start`, `/confirm` (dev channel; no paid SMS provider active) | built | CURRENT; production SMS provider = BETA BLOCKER (founder/provider decision) |
| Separation: reveal ≠ conversation ≠ viewing (independent endpoints and limits) | built | CURRENT |

### 1.5 Auth

| Item | State | Class |
|---|---|---|
| E-mail + password register/login, refresh (rotating, revoked on use), `/v1/me` | built | CURRENT |
| BFF session in `__Host-` cookies, CSRF, `/bff/auth/{login,logout,session}` | built (FE-001) | CURRENT |
| BFF register route | not built | CURRENT + CLIENT COMPOSITION (backend `/v1/auth/register` exists) |
| Pending-intent preservation (save / message / viewing interrupted by sign-in) | no backend support needed; client keeps the intent (route + action + non-sensitive params) across the auth step | CURRENT + CLIENT COMPOSITION; UI = DESIGN-DEPENDENT |
| **BG-1** logout / refresh revocation endpoint | missing | BETA BLOCKER |
| **BG-5** refresh reuse/grace semantics (FE 120 s rotation memory is a mitigation only; do not extend it) | missing | BETA BLOCKER |
| OTP / magic link / Google sign-in | **do not exist** (prototype only) | FUTURE (founder decision; not added by FE-003) |

### 1.6 Privacy

| Item | State | Class |
|---|---|---|
| Public location: city/district + APPROXIMATE grid point or DISTRICT only (04a §16) | built, E2E-asserted | CURRENT |
| D-101: `floor` public, `floors_total` withheld | built | CURRENT |
| **G9**: exact address / meeting point only after `CONFIRMED`, only to that viewing's parties, only via a participant-safe surface; never in public DTO, SEO, analytics, attribution, generic logs | no participant-only delivery model (no field, no endpoint) | BACKEND/API GAP + BETA BLOCKER — nothing is disclosed until it exists |
| Analytics: consent gate, closed catalogue, no message/address/phone/free text; `user_id` never from the client | built (FE-001/GROWTH-001) | CURRENT; FE-003 events (save, contact intent) = additions to EVENTS-v1 |
| Supply: legacy `require_role("host")` on property/listing write routes (`POST /v1/properties`, `GET /v1/properties`, create listing, price, availability, pause, price history, …) | inconsistent with the authority chain (02 §2) | BETA BLOCKER (authority-correct supply routes); not an FE-003 seeker dependency |

## 2. Contract draft

### 2.1 Goal

A signed-in seeker can save a listing or a search, start and continue a
conversation, reveal a phone where the owner allows it, and request or manage
a viewing — on the real backend, with every refusal state honest.

### 2.2 API invariants the UI must respect (not negotiable by design)

1. A conversation starts only with a real first message; writing again
   continues the one active thread.
2. Refusals are states, not errors to hide: `CONVERSATION_CLOSED`,
   `RECONTACT_BLOCKED`, `LISTING_HELD`, "already have a viewing", "not an
   offered slot", quotas (429 with Retry-After), phone not verified (403),
   messages-only (409). A 503 on a write is "outcome unknown — check before
   repeating" (FE-001 error model).
3. Slots are always read from `viewing-slots`; the client never computes
   availability.
4. No viewing creates a conversation (or vice versa) unless a canonical
   decision says so.
5. No exact address or meeting detail anywhere until the G9 model exists.
6. Money and totals come from the API; parking follows 04a §24 G4.
7. Analytics only through the consent gate; FE-003 events added to EVENTS-v1
   with forbidden-field review.

### 2.3 Likely slices (order; each a separately reviewable candidate)

| Slice | Content | Depends on |
|---|---|---|
| FE-003a | auth completion in the BFF (register, session UI hooks), pending-intent capture/resume | BG-1/BG-5 decision (may start behind them, must not ship to beta without) |
| FE-003b | save listing + saved list; save search + list/matches | — |
| FE-003c | conversation start/continue/list, closed/blocked states | — |
| FE-003d | contact reveal (phone-verified flow, quota) | production SMS provider for beta |
| FE-003e | viewing request/manage from derived slots; my viewings | G9 for any address/meeting detail |

### 2.4 Test strategy

Vitest for state/intent/codec logic; Playwright against the seeded API
(extend `seed_e2e.py` with viewing settings/windows and a phone-mode listing)
for every refusal state; axe on each new surface; PG race tests only where
backend changes are made; analytics payload assertions as in FE-002.

### 2.5 Sections that AWAIT DESIGN-001C HANDOFF

Final Listing engagement rail/dock · save affordance · slot presentation ·
conversation visual hierarchy and composer · bottom-sheet anatomy · mobile
responsive presentation · auth-interruption UI · 1C visual treatment and
tokens. **AWAIT DESIGN-001C HANDOFF** — not frozen here.

### 2.6 Backend work required (separate bounded tasks)

BG-1 logout/revocation · BG-5 refresh grace · G9 participant-only
address/meeting delivery · G4 mandatory/optional parking input · explicit
cancellation source · `ConversationOut.can_send` / `closed_by` (optional,
client can compose) · saved flag on listings (G8, optional).

## 3. Next synchronisation point

Input: the founder/GPT-approved DESIGN-001C handoff. Then: finalise this
contract (resolve §2.5, confirm slices and backend prerequisites) for founder
and GPT-5.6 Sol approval. No FE-003 production code before that.
