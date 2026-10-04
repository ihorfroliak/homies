# FE-003 — Save → Conversation → Viewing · TASK CONTRACT

| Field | Value |
|---|---|
| Status | **CONTRACT FINAL CANDIDATE — awaiting founder + GPT-5.6 Sol review. `FE-003 IMPLEMENTATION AUTHORIZED: NO`** |
| Baseline | `main` = `995b05fe72bc15a86141e214bf1c4fc63b8bc570`; schema head `a3c5e7f9b1d4` (no later revision) |
| Design input | DESIGN-001C *Homies 001C Dzielnica Product Convergence* (`.dc.html`) — approved by founder/GPT **at design-contract level**. See §0.2 for what the builder could and could not read |
| Risk class (implementation) | **R2** (auth/session, private engagement, privacy, concurrency, moderation states) |
| Canon | 00-AUTHORITY; 02 §2 (authority chain); 03 §2; 04a §14, §16, §18, §21–§24; 07; DECISIONS D-98 (G-11…G-15), D-100, D-101, D-102, D-103; DESIGN-001; FE-001; FE-002; GROWTH-001 EVENTS-v1 |
| File name | kept as `…-DRAFT.md` so existing references (06-ROADMAP, PROJECT-STATUS, DESIGN-001) stay valid; this text supersedes the 2026-10-04 draft |
| Out of scope | final 1C token/visual layer for FE-002 surfaces (§7); owner panel (listing create/edit, viewing settings/windows editors); moderator app; applications / Housing Passport; payments; OTP / magic link / Google sign-in; exact address delivery (G9) |

## 0. How to read this contract

### 0.1 Classes

Every item carries exactly one class:

| Class | Meaning |
|---|---|
| **CURRENT BACKEND** | exists in `backend/` at the baseline, verified in code and tests |
| **CURRENT FE/BFF** | exists in `frontend/web/` at the baseline |
| **CLIENT COMPOSITION** | no new backend; the client combines existing calls/state. Never invents a domain fact |
| **FE-003 IMPLEMENTATION** | work FE-003 itself does once authorised |
| **BACKEND/API GAP** | missing backend capability; a separate bounded backend task (§10.1) |
| **BETA BLOCKER** | must be closed before any external beta, whatever FE-003 does (§10.2) |
| **FUTURE / OUT OF SCOPE** | not FE-003 |

Rule: **no UI design redefines backend semantics.** Where the approved design
shows something the API cannot express, the contract names the gap and the UI
shows less, never a guess.

### 0.2 Design input — what the builder verified

The approved artifact `Homies 001C Dzielnica Product Convergence.dc.html` was
**not readable by the builder** when this contract was finalised: it is not
on disk (`Downloads/` holds only `Homies Seeker v1.dc.html` and empty
canvases) and the Claude Design connector failed with HTTP 403. This contract
therefore binds the component **names and responsibilities** given in the
founder brief (SaveButton, EngagementRail, MobileActionDock, ViewingSlot,
ViewingState, ConversationComposer, ConversationItem, AuthInterrupt,
ContextSwitch, ProviderViewingRow) and the DESIGN-001C focus rules, to the
**verified backend**. Visual specifics (spacing, colour, motion, exact copy)
stay with the handoff.

**Precondition P-0 for implementation:** the approved handoff file is added to
the repository (e.g. `docs/design/DESIGN-001C/`) or its path is given to the
builder, and any conflict between it and §1–§9 below is raised as a contract
question before code, not resolved in code.

## 1. Verified backend/API facts (at `995b05f`)

### 1.1 Save (TASK-014; 04a §22) — CURRENT BACKEND

| Fact | Source |
|---|---|
| `POST /v1/me/saved-listings/{listing_id}` → 201 new save, **200 already saved (idempotent)**, 404 listing not public, 409 at `saved_listings_per_user` = 500 | `saved/router.py:82–124`, `core/config.py:111` |
| `DELETE /v1/me/saved-listings/{listing_id}` → 204 whether or not it was saved (idempotent; works for gone listings) | `saved/router.py:127–136` |
| `GET /v1/me/saved-listings?limit≤100&offset` → `SavedListingOut{saved_id, listing_id, saved_at, availability_status AVAILABLE \| NO_LONGER_AVAILABLE, listing: ClassifiedOut \| null}`; a not-public listing is a **tombstone** (no title/price/media/place) | `saved/router.py:139–150`, `saved/schemas.py` |
| **No saved-state on `ClassifiedOut`** and no "is this id saved?" endpoint (gap G8) → saved-state needs CLIENT COMPOSITION | `properties/schemas.py:287–352` |
| Saved searches: `POST/GET/PATCH/DELETE /v1/me/saved-searches[/{id}]`, `GET …/{id}/matches`; body `{name ≤80, query (API canonical query string), notifications_enabled}`; 409 duplicate with `Location`, 409 at 50 per user; 422 invalid query; `query_state VALID \| INVALID` | `saved/router.py:200–368`, `config.py:112` |
| Rate bucket `SAVED_WRITE` (30 burst, 0.5/s, per IP) | `core/ratelimit.py:89, 286` |

### 1.2 Conversations (04 §53–§55; TASK-015) — CURRENT BACKEND

| Fact | Source |
|---|---|
| Start: `POST /v1/classifieds/{id}/conversations {body}` → 201 `ConversationDetail`. **A first non-empty message is required**; `MessageIn.body` 1…**4000** chars, stripped, blank → 422 | `engagement/router.py:76–84, 287–357` |
| One ACTIVE thread per requester × listing: a second start **continues** the thread (appends the message) — partial unique index backstop | `router.py:313–344`, `models.py:76` |
| Start refusals: 404 listing not public (paused, held, stale); 409 "This is your own listing" (**no stable code**); 409 `RECONTACT_BLOCKED:` (G-14); 429 daily quota 30 new threads / 24 h (**no stable code, no `Retry-After`**) | `router.py:298–327` |
| Continue: `POST /v1/conversations/{id}/messages {body}`; non-ACTIVE → 409 `CONVERSATION_CLOSED:` | `router.py:389–406` |
| Statuses `ACTIVE \| ARCHIVED \| CLOSED`; in 1A only Homies closes (FEATURE_RESTRICTED or close_engagement) with a SYSTEM message whose body is the code `system.conversation_closed_by_homies` (`sender_user_id` null) | `models.py:48, 54`; `trust/effects.py:35–61` |
| Redacted message: `body: null`, `moderation_state: "REMOVED"` (the model drops the body however it is built) | `router.py:87–121` |
| Inbox `GET /v1/conversations` (no pagination): requester's threads + threads on listings where the user holds **MANAGE_MESSAGES** now; `my_side` tenant/provider; provider rows add `requester_user_id`, `provider_stage`, `assigned_to_user_id` | `router.py:124–141, 360–371` |
| `GET /v1/conversations/{id}`: all messages, oldest first; 404 for non-participants | `router.py:374–386` |
| Provider: `assign` (assignee must hold MANAGE_MESSAGES), `stage` (`NEW, REPLIED, VIEWING, APPLICATION, SHORTLISTED, ACCEPTED, REJECTED, ARCHIVED`); first provider reply moves NEW → REPLIED | `router.py:240–251, 409–452` |
| **No** `can_send` / `closed_by` fields, no unread state, no listing summary, no counterpart name on `ConversationOut` | `router.py:124–141` |
| Buckets `CONVERSATION_START` (10, 0.05/s) and `MESSAGE_WRITE` (30, 0.5/s), per IP, 429 + `Retry-After` from the middleware | `ratelimit.py:75–76`; `composition.py:220–236` |
| Message send is **not idempotent** (no key): a lost response can be followed by a duplicate | `router.py:389–406` |

### 1.3 Viewings (04 §57–§60; 04a §14; TASK-015 S4b; D-102 F6) — CURRENT BACKEND

| Fact | Source |
|---|---|
| Availability is **derived**: settings + windows − blackouts − capacity (with buffers), DST-safe, minimum notice; **no slot entity** | `viewings.py:287–336` |
| `GET /v1/classifieds/{id}/viewing-slots?start=YYYY-MM-DD&days=1..31 (default 14)` → `{"slots": [UTC instants], "duration_minutes": int \| null}`; **requires authentication** (`get_current_user`); 404 not public; no settings → `{"slots": [], "duration_minutes": null}` | `viewings.py:400–412` |
| OpenAPI response schema for viewing-slots is **untyped** (`{}`); the listing's **timezone is not returned** | `docs/api/openapi.json` |
| Request `POST /v1/classifieds/{id}/viewings {starts_at, attendee_count 1–10, note ≤1000}` → `INSTANT_BOOKING` ⇒ `CONFIRMED` at once; `REQUEST_APPROVAL` ⇒ `REQUESTED` | `viewings.py:164–168, 415–466` |
| Request refusals, in order: 404 not public (incl. held = paused); 409 own listing; 409 `RECONTACT_BLOCKED:` (F6); 409 "takes no viewings yet"; 409 "not an offered slot" (exact instant must be in the derived set); 409 "already have a viewing of this flat booked" (one future REQUESTED/CONFIRMED per requester × listing). Only RECONTACT_BLOCKED has a stable code | `viewings.py:419–450` |
| Provider (scope **MANAGE_VIEWINGS** via `authority.can_act(…, verified=False)`): `confirm` (REQUESTED only; future only; capacity re-checked under the settings lock; held listing → 409 `LISTING_HELD:`), `decline` (REQUESTED), `outcome` COMPLETED/NO_SHOW (CONFIRMED, after start), list `GET /v1/classifieds/{id}/viewings` → `ProviderViewingOut{…, requester_user_id, requester_note}` | `viewings.py:222–230, 511–602` |
| Either side `cancel` from REQUESTED/CONFIRMED — **no time guard** (a past CONFIRMED viewing can still be cancelled) | `viewings.py:561–576` |
| A REQUESTED viewing whose time has passed **stays REQUESTED** (no expiry state); it no longer blocks a new request (`ends_at > now`) | `viewings.py:445–450` |
| State conflicts: 409 "The viewing is {STATUS}", 409 "changed meanwhile" (version CAS), 409 "slot is already full", 409 "time has passed", 409 "has not happened yet" — **no stable codes** | `viewings.py:480–496, 526–538, 587–590` |
| Requester list `GET /v1/me/viewings` → `ViewingOut{id, listing_id, starts_at, ends_at, status, attendee_count, cancelled_by_homies}` — no listing summary | `viewings.py:170–181, 605–608` |
| `cancelled_by_homies` is **derived** (cancelled_at == a LISTING close_engagement decision instant); the explicit actor exists only in the outbox fact `ViewingCancelled.cancelled_by` (analytics plane, not API) | `trust/effects.py:113–126`; `viewings.py:572–574` |
| Close-engagement cancels future REQUESTED/CONFIRMED viewings + notice `MODERATION_VIEWING_CANCELLED` (ids + instant only) | `trust/effects.py:70–110`; `trust/notices.py:82–95` |
| **A G-14 conversation restriction does not touch viewings** (it only closes the conversation); a provider can still confirm a REQUESTED viewing of a restricted requester | `trust/decisions.py:507–600`; `viewings.py:511–546` |
| Provider settings/windows/blackouts: `PUT …/viewing-settings`, `POST …/viewing-windows`, `POST …/viewing-blackouts` (MANAGE_VIEWINGS); **no GET** for settings or windows | `viewings.py:349–394` |
| Viewing writes ride the `PROPERTY_WRITE` bucket (20, 0.5/s) | `ratelimit.py:299–302` |

### 1.4 Contact reveal — CURRENT BACKEND

| Fact | Source |
|---|---|
| `POST /v1/classifieds/{id}/contact` → `{offer_id, contact_phone}`; gate **verified phone** (`phone_verified_at`), else 403 | `properties/router.py:1012–1035` |
| 404 not public; 409 owner accepts messages only (`contact_mode != "phone"`) — no stable code | `router.py:1036–1045` |
| Repeat reveal of the same listing: free, no quota, no new row; quota **20 per rolling 24 h** → 429 + `Retry-After`; every new reveal → `contact_reveals` row + audit `classified.contact_revealed` | `router.py:1047–1094`; `config.py:133` |
| `GET /v1/me/reveal-quota` → `{limit, used, remaining, resets_in}` | `router.py:996–1009` |
| Bucket `CONTACT_REVEAL` (10, 0.05/s) | `ratelimit.py:72` |
| Independent of conversation and viewing (separate endpoints, limits, records) | code |
| **Not covered by G-14**: a restricted requester can still reveal the phone of the same listing | `router.py:1012–1094` (no `recontact_blocked`) |
| Phone verification `POST /v1/me/verify/phone/start`, `/v1/me/verify/phone/confirm`; `user.phone` and `phone_verified_at` are set together only at confirm; the SMS channel is a dev stub | `identity/router.py:233–283`; `identity/verification.py:9–34` |

### 1.5 Pricing / CostSignature — CURRENT BACKEND (verified as requested)

`ClassifiedOut` carries `rent_amount, admin_fee, utilities_amount,
utilities_included, utilities_basis (INCLUDED | ESTIMATED | NOT_STATED),
parking_fee, deposit_amount, other_costs (free text), monthly_total_estimate,
move_in_total, currency` (`properties/schemas.py:317–348`; `router.py:205–218`).

**Parking verification (G4):** a stated `parking_fee` is stored as
`OTHER_MANDATORY/parking`, `MONTHLY`, `mandatory=True`
(`pricing.py:84–87`), and `summarize` adds every mandatory monthly component
(`pricing.py:94–114`). Therefore **`monthly_total_estimate` includes a stated
`parking_fee`.** Proven by `tests/test_pricing.py:110–115`
(`monthly == 250000 + 50000 + 30000 + 20000`), `:118–129` and `:199–202`
(`== 250000 + 50000 + 20000` with utilities included), and the row/summary
invariant `_assert_summaries_match_rows`. This **matches** 04a §24 G4 as
written ("today the only parking input is a fee the owner states, stored as a
mandatory monthly component"). **No contract/backend inconsistency → no
STOP.** The optional-vs-mandatory input remains a modelling gap (BB-4).

Deposit: `ONE_TIME`, refundable — outside the monthly total, inside
`move_in_total` (`= monthly + one-offs`). Utilities included in rent are
stored non-mandatory → shown, not added twice. `other_costs` is never summed.

### 1.6 Auth and BFF — CURRENT BACKEND / CURRENT FE/BFF

| Fact | Source |
|---|---|
| `POST /v1/auth/register {email, password 10–128, full_name, role "guest"\|"host" (default guest)}` → 201 `UserOut`, **no tokens**: registration does **not** create a session; 409 e-mail exists; bucket `AUTH_REGISTER` (5, fail-closed) | `identity/router.py:60–76`; `identity/schemas.py:8–11` |
| Login → token pair; refresh rotates and **revokes on use, no grace (BG-5)**; **no logout/revocation endpoint (BG-1)** | `identity/router.py:79–120` |
| BFF: `/bff/auth/login` (writes `__Host-` cookies), `/bff/auth/logout` (clears cookies only), `/bff/auth/session` (`{authenticated, user{id,name,role,emailVerified,phoneVerified}}`); **no `/bff/auth/register`** | `frontend/web/src/app/bff/auth/*` |
| BFF session derives `phoneVerified` from `phone !== null` — equal to `phone_verified_at !== null` today (both set at confirm) but not by contract | `app/bff/auth/session/route.ts` |
| BFF proxy allowlist has **no** engagement write routes; `viewing-slots` is listed as `auth: "optional"` although the backend **requires** auth (anonymous → 401) | `src/server/bff-routes.ts` |
| `withSession`: refresh first when only the refresh cookie is left; one retry after a 401 | `src/server/bff.ts:58–80` |
| Error model: 503 on non-GET = `outcome_unknown`; 502/504 from the BFF on upstream failure; domain code = `^[A-Z][A-Z0-9_]{2,63}: ` prefix of `detail` | `src/api/errors.ts` |

### 1.7 Authority (02 §2) — CURRENT BACKEND

Membership roles: OWNER/ADMIN = all scopes; AGENT = EDIT_PROPERTY,
PUBLISH_LISTING, MANAGE_MEDIA, **MANAGE_VIEWINGS, MANAGE_MESSAGES**; FINANCE =
VIEW_FINANCIALS; VIEWER = none. Mandate scopes map 1:1 (`MANAGE_VIEWINGS`,
`MANAGE_MESSAGES`, …) (`properties/authority.py:77–97`). Conversation and
viewing provider routes authorise through `authority.can_act` (correct
model). **Legacy `require_role("host")`** remains on property/listing write
routes (`POST /v1/properties`, `GET /v1/properties`, create listing, price,
price history, pause, availability, …; `properties/router.py:285–762`).
`GET /v1/me/classifieds` enumerates by **PUBLISH_LISTING** only
(`router.py:791–800`); there is no enumeration of listings by MANAGE_VIEWINGS
or MANAGE_MESSAGES and no provider-wide viewing list.

## 2. Contract findings (new since the draft)

| # | Finding | Class | Disposition |
|---|---|---|---|
| CF-1 | Parking is in `monthly_total_estimate` — consistent with G4 as decided | verified | no stop; BB-4 stays |
| CF-2 | `viewing-slots` requires auth; BFF marks it `optional` | CURRENT FE/BFF defect | FE-003 sets `auth: "required"`; slots are a signed-in surface (OD-6) |
| CF-3 | viewing-slots untyped in OpenAPI; listing timezone absent | BACKEND/API GAP | BP-2 (required for FE-003e) |
| CF-4 | Most engagement refusals have no stable code (only `RECONTACT_BLOCKED`, `CONVERSATION_CLOSED`, `LISTING_HELD`) | BACKEND/API GAP | BP-1 (required for FE-003c/d/e; the client never parses English `detail`) |
| CF-5 | Conversation daily quota 429 has no `Retry-After` | BACKEND/API GAP | folded into BP-1 |
| CF-6 | `cancel` has no time guard; past REQUESTED never expires | BACKEND/API GAP | BP-7 (recommended); UI hides cancel after start and labels past REQUESTED (CLIENT COMPOSITION, display only) |
| CF-7 | G-14 does not bar contact reveal | OPEN PRODUCT DECISION | OD-2 |
| CF-8 | G-14 leaves existing viewings unchanged; provider can confirm a restricted requester's REQUESTED viewing | **FOUNDER DECISION REQUIRED** | §4, OD-1 |
| CF-9 | No provider enumeration by MANAGE_VIEWINGS / MANAGE_MESSAGES; no provider-wide viewing list | BACKEND/API GAP | BP-3 (FE-003f only) |
| CF-10 | Provider DTOs carry only `requester_user_id` (no display name) | BACKEND/API GAP + privacy decision | OD-3, BP-4 |
| CF-11 | Registration returns no session; role is client-selectable `guest`/`host` | CURRENT BACKEND | FE-003a: register → login; never send `role`; legacy `host` is not the product model (§3.9) |
| CF-12 | BFF `phoneVerified` derived from `phone` | CURRENT FE/BFF fragility | FE-003a derives from `phone_verified_at` |
| CF-13 | Message send not idempotent | CURRENT BACKEND | §3.2 outcome-unknown rule (re-read before resend) |
| CF-14 | Provider scopes evaluated with `verified=False` for messages/viewings | audit note | flagged for Codex; FE-003 does not change it |
| CF-15 | Inbox/viewing lists lack listing summary, counterpart, unread, pagination | CLIENT COMPOSITION + FUTURE | per-row listing fetch with tombstone fallback; no unread badges |

## 3. Scope contract by area

### 3.1 Save

| Item | Class | Contract |
|---|---|---|
| Save / unsave a listing | CURRENT BACKEND → FE-003 IMPLEMENTATION | `POST` / `DELETE /bff/v1/me/saved-listings/{id}` (allowlist: `auth: "required"`) |
| Saved-state on cards/detail | CLIENT COMPOSITION (gap G8) | after sign-in the client loads the saved-id set once per session by paging `GET /v1/me/saved-listings?limit=100` (≤ 5 pages at the 500 cap), keeps it in memory, updates it on each confirmed save/unsave. Anonymous: every SaveButton shows "not saved" and triggers AuthInterrupt. The API is never asked "is it saved?" by issuing a save |
| Behaviour | FE-003 IMPLEMENTATION | **non-optimistic**: the button enters a pending state (`aria-busy`, disabled against double-submit) and changes pressed state only on 200/201 (save) or 204 (unsave). Network error/timeout: both calls are idempotent → one automatic retry, then an inline retry. 502/503/504 on save: re-read the set (GET) before showing the result |
| 404 on save (listing no longer public) | FE-003 IMPLEMENTATION | status "Ta oferta nie jest już dostępna"; button stays unsaved |
| 409 on save (500 cap) | FE-003 IMPLEMENTATION | status "Masz już 500 zapisanych ofert — usuń którąś, aby zapisać nową" with a link to the saved list (status-only mapping is unambiguous on this endpoint) |
| Saved list `/zapisane` (PROPOSED route; confirm with handoff) | FE-003 IMPLEMENTATION | AVAILABLE rows render `listing` via the FE-002 ListingCard; NO_LONGER_AVAILABLE rows render a tombstone ("Oferta niedostępna", `saved_at`, "Usuń") with **no** cached title/price/media; paging by `limit/offset`; empty state with link to search |
| Save the current search | CLIENT COMPOSITION → FE-003 IMPLEMENTATION | the FE-002 codec maps the Polish URL to the **API canonical query** (`koszt_do` → `max_monthly_total`×100 …); name defaults to a generated label the user can edit (≤ 80); 409 duplicate → "Ta wyszukiwarka jest już zapisana" + link from `Location`; 409 cap 50; 422 → "Tych filtrów nie da się zapisać" |
| Saved searches list | FE-003 IMPLEMENTATION | name, alert on/off (`PATCH` with `expected_version`), pause, delete; `query_state INVALID` shown honestly ("Wyszukiwanie nieaktualne — {invalid_reason mapped}"), never silently broadened; "Zobacz oferty" opens `/wynajem…` from the stored query (reverse codec) or `GET …/matches` |
| Alert e-mail requires a verified e-mail | CURRENT BACKEND | the toggle explains it when `emailVerified` is false (no client gating of the API) |
| Saved-flag on listing DTO / ids endpoint | BACKEND/API GAP (G8, optional) | not required for FE-003 |
| Unsave audit trail | FUTURE (GROWTH debt) | — |

### 3.2 Conversations

| Item | Class | Contract |
|---|---|---|
| Start = first non-empty message | CURRENT BACKEND | the composer for a listing without a thread calls `POST /v1/classifieds/{id}/conversations {body}`; there is **no** "open empty thread" action |
| Max length | CURRENT BACKEND | 4000 characters after trim; the composer counts characters (shown from 3600), blocks submit beyond 4000 and when blank; server 422 is still handled |
| One thread per requester × listing | CURRENT BACKEND + CLIENT COMPOSITION | "Napisz" on a listing where the user already has a thread opens that thread (found in `GET /v1/conversations` by `listing_id`, `my_side=tenant`, `status=ACTIVE`); a start that reaches the backend anyway continues it — the UI then shows the thread |
| CLOSED | CURRENT BACKEND | composer replaced by a closed notice "Homies zamknął tę rozmowę" (from `status != ACTIVE` and the SYSTEM line code); 409 `CONVERSATION_CLOSED` on send → same state, draft kept visible for copy, no retry |
| ARCHIVED | CURRENT BACKEND (unused in 1A) | rendered read-only "Rozmowa zarchiwizowana" |
| SYSTEM line | CURRENT BACKEND | `message_type=SYSTEM`, body is a code → mapped to Polish; unknown code → neutral "Wiadomość systemowa Homies"; never shown raw |
| Redacted message | CURRENT BACKEND | `moderation_state=REMOVED`, `body=null` → "Wiadomość usunięta przez Homies"; no reason, no placeholder of the old text |
| RECONTACT_BLOCKED | CURRENT BACKEND | start refused → state "Nie możesz rozpocząć nowej rozmowy o tej ofercie" (no reason, no allegation), no retry, viewing CTA also unavailable (F6) |
| Own listing | BACKEND/API GAP (BP-1 code `OWN_LISTING`) | "To Twoja oferta" |
| Quotas/limits | CURRENT BACKEND + BP-1 | daily 30 new threads → "Dzisiejszy limit nowych rozmów został wykorzystany. Istniejące rozmowy działają." (code `CONVERSATION_QUOTA`); middleware 429 → wait `Retry-After`, then enable retry |
| Send failure | FE-003 IMPLEMENTATION | 4xx = final state with mapped copy; 401 → AuthInterrupt keeping the draft; **502/503/504/timeout = outcome unknown**: the client re-reads the conversation and, if the last own message equals the draft and is newer than the attempt, marks it sent; otherwise offers "Wyślij ponownie". Never auto-resend |
| Hierarchy | FE-003 IMPLEMENTATION | inbox (ConversationItem rows, newest `last_message_at` first) → thread (listing header, messages oldest→newest, composer). Tenant/provider split by `my_side` (ContextSwitch, §3.9) |
| Composer state | FE-003 IMPLEMENTATION | `idle → typing → sending → sent \| failed(final) \| failed(retryable) \| unknown \| closed \| blocked`; draft in memory only |
| Auth interruption | CLIENT COMPOSITION | §3.7; the draft survives the in-page dialog, is **not** persisted to storage (free text), and is never auto-sent after sign-in |
| Provider authority | CURRENT BACKEND | provider side visible only for listings where the user holds MANAGE_MESSAGES now (any valid chain); assignment/stage are provider-only and FE-003f |
| `can_send` / `closed_by` | BACKEND/API GAP (optional) | **not assumed**; derived as above |
| Report a message | CURRENT BACKEND (`/v1/reports`); scope = OD-4 | not in FE-003 unless OD-4 says so |
| Real-time, unread badges, pagination | FUTURE | polling on focus/visibility only (no timers in background tabs) |
| Viewing → conversation | **forbidden** | no viewing creates a conversation and no conversation creates a viewing |

### 3.3 Viewings

**State machine (CURRENT BACKEND) and UI binding:**

| From | Event | Actor | To | UI (requester) | UI (provider) |
|---|---|---|---|---|---|
| — | request, `REQUEST_APPROVAL` | requester | REQUESTED | "Prośba wysłana — czeka na potwierdzenie" | row with Confirm / Decline |
| — | request, `INSTANT_BOOKING` | requester | CONFIRMED | "Oglądanie potwierdzone" | row "Potwierdzone" |
| REQUESTED | confirm (future, capacity, not held) | provider | CONFIRMED | "Potwierdzone" | — |
| REQUESTED | decline | provider | DECLINED | "Właściciel nie przyjął tego terminu" + "Wybierz inny termin" | — |
| REQUESTED / CONFIRMED | cancel | either | CANCELLED | "Oglądanie odwołane" (**no actor**, §3.10) | same |
| REQUESTED / CONFIRMED | close_engagement | Homies | CANCELLED | "Oglądanie odwołane" (the backend also files the notice `MODERATION_VIEWING_CANCELLED` in `/v1/me/inbox`; a notification-centre UI is FUTURE, not FE-003) | same |
| CONFIRMED (after start) | outcome | provider | COMPLETED / NO_SHOW | "Odbyło się" / "Oznaczone jako nieodbyte" | outcome recorded |
| REQUESTED (start passed) | — (no transition exists) | — | REQUESTED | **display-only** label "Bez odpowiedzi — termin minął" (CLIENT COMPOSITION from `starts_at`); actions hidden | same; Confirm hidden |

| Item | Class | Contract |
|---|---|---|
| Derived availability | CURRENT BACKEND | the client **only** renders `viewing-slots`; never computes, filters or extends slots. `ViewingSlot` is a UI representation of one derived instant, **not a domain entity** |
| Time display | BP-2 | local time in the **listing's timezone from the typed response**; until BP-2 lands FE-003e is not implementable (no `Europe/Warsaw` assumption in code) |
| Signed-in only | CF-2 / OD-6 | anonymous user sees "Zaloguj się, aby zobaczyć wolne terminy" → AuthInterrupt (intent `viewing`) |
| No settings | CURRENT BACKEND | `duration_minutes: null` → "Właściciel nie udostępnia jeszcze terminów oglądania" + message CTA |
| No free terms | CURRENT BACKEND | empty `slots` with a duration → "Brak wolnych terminów w najbliższych 14 dniach" + "Pokaż kolejne dni" (`start` += 14, `days ≤ 31`) |
| Request | FE-003 IMPLEMENTATION | select slot → confirm sheet (date/time, duration, `attendee_count` 1–10, optional note ≤ 1000 with a "nie podawaj tu danych osobowych innych osób" hint) → `POST …/viewings` with the **exact** `starts_at` string received |
| INSTANT vs APPROVAL | CURRENT BACKEND | the result state comes from the **response** (`CONFIRMED` / `REQUESTED`); the UI never predicts it from settings (the seeker cannot read settings) |
| 409 slot not offered / full | BP-1 | re-fetch slots, keep the sheet open, status "Ten termin właśnie się zajął — wybierz inny"; focus to the status |
| 409 already booked | BP-1 | "Masz już umówione oglądanie tego mieszkania" + link to it (`/me/viewings`) |
| 409 RECONTACT_BLOCKED | CURRENT BACKEND | "Nie możesz umówić oglądania tej oferty" — no reason, no retry |
| 404 on request (held / paused / stale) | CURRENT BACKEND | "Ta oferta nie jest już dostępna" |
| LISTING_HELD | CURRENT BACKEND (provider confirm only) | provider row: "Oferta jest sprawdzana przez Homies — potwierdzanie wstrzymane" |
| Duplicate request after unknown outcome | FE-003 IMPLEMENTATION | 502/503/504 → re-read `GET /v1/me/viewings`; a matching viewing = success; never blind resubmit (the backend's one-future-viewing rule would answer 409 anyway) |
| Cancel | FE-003 IMPLEMENTATION | offered only while `now < starts_at` (BP-7 makes it authoritative); confirm dialog; 409 state conflict → re-read and render the new state |
| My viewings `/ogledziny` (PROPOSED) | CLIENT COMPOSITION | `GET /v1/me/viewings` + per-row `GET /v1/classifieds/{listing_id}` (404 → "Oferta niedostępna", viewing still shown) |
| Provider controls | CURRENT BACKEND → FE-003f | §3.9 |
| Address / meeting point | **not in FE-003** | §3.8 |
| Existing viewing after a later G-14 restriction | **FOUNDER DECISION REQUIRED** | §4 |

### 3.4 Pricing binding (CostSignature)

| Rule | Contract |
|---|---|
| Authoritative fields | `rent_amount, admin_fee, utilities_amount, utilities_basis, parking_fee, deposit_amount, other_costs, monthly_total_estimate, move_in_total, currency` from `ClassifiedOut` only |
| No recomputation | the client **never** computes, adds or adjusts `monthly_total_estimate` or `move_in_total`; a parity test feeds a fixture whose parts do not add up and asserts the API totals are shown unchanged |
| Numeric breakdown | structured fields only (FE-002 CostBreakdown rows, DESIGN-001 §5.5) |
| `other_costs` | verbatim text, labelled "Opis właściciela — nie wliczone w sumy"; never parsed for numbers |
| Deposit | outside "Razem miesięcznie"; inside "Na start" with caption "pierwszy miesiąc + kaucja" |
| Utilities | `INCLUDED` → "w cenie najmu" (figure shown if > 0, not added); `ESTIMATED` → "ok. X zł (szacunkowo)", total marked "szacunkowo"; `NOT_STATED` → "nie podano", total shown as "od X zł + media" |
| Parking (G4 exactly) | `parking_fee > 0` → row "Parking" **inside** the monthly total (as stored, mandatory). The UI must not label it optional, must not offer an "exclude parking" toggle and must not subtract it. Optional/mandatory input = BB-4 |
| Where FE-003 shows money | EngagementRail price summary, MobileActionDock total, listing header in thread / viewing sheet — all reuse the FE-002 formatter (`Intl.NumberFormat('pl-PL', useGrouping 'always')`) |

### 3.5 Contact reveal

| Item | Class | Contract |
|---|---|---|
| CTA presence | CURRENT BACKEND | "Pokaż numer" only when `contact_mode == "phone"`; otherwise no phone CTA (messages only) |
| Verified-phone gate | CURRENT BACKEND | before calling, the client reads `phoneVerified` (derived from `phone_verified_at`, CF-12): unverified → verification step (start/confirm), then the user presses "Pokaż numer" again. A 403 from the endpoint lands in the same step (BP-1 code `PHONE_NOT_VERIFIED`, so a BFF CSRF 403 is never mistaken for it) |
| Messages-only 409 | BP-1 `MESSAGES_ONLY` | "Ten właściciel przyjmuje tylko wiadomości" + message CTA (listing changed since render) |
| Quota | CURRENT BACKEND | `GET /v1/me/reveal-quota` shown next to the CTA ("Pozostało dziś: N z 20"); 429 → "Dzienny limit wykorzystany — odnowi się za …" from `Retry-After`; repeat reveal of the same listing costs nothing and is never blocked by the UI |
| Display of the number | FE-003 IMPLEMENTATION | rendered as text + `tel:` link; never written to storage, analytics, URL or logs; cleared from memory on navigation |
| Audit | CURRENT BACKEND | the server records each new reveal; the client adds nothing |
| Independence | CURRENT BACKEND | reveal never starts a conversation or a viewing and vice versa |
| G-14 coverage | **OD-2** | current: not barred |
| Production SMS provider | **BETA BLOCKER (BB-7)** | FE-003d can be built against the dev channel; it cannot ship to beta |

### 3.6 Supply-side surfaces in FE-003 (provider)

Covered in §3.9 and components ContextSwitch / ProviderViewingRow (§6).

### 3.7 Auth interruption (CLIENT COMPOSITION)

```
pending action (save | message | viewing | reveal | save_search)
  → AuthInterrupt dialog (in page; no navigation)
  → login  OR  register → login          (register returns no session: CF-11)
  → session established  = GET /bff/auth/session → {authenticated: true}
  → saved-id set loaded (if the intent needs it)
  → pending action resumed
```

| Rule | Contract |
|---|---|
| Intent record | `{action, listing_id, starts_at?, search_query?, initiator_id, created_at}` in memory; mirrored to `sessionStorage` **without** free text (no message draft, no note, no phone) for a reload; expires after 30 min |
| Resume semantics | **save**: executed automatically (idempotent, reversible). **message**: thread or composer re-opened with the in-memory draft; the user sends. **viewing**: slots re-fetched, the chosen instant pre-selected only if still offered; the user confirms. **reveal**: the user presses again (it spends quota). **save_search**: dialog re-opened with the name |
| Register | `/bff/auth/register` (FE-003a, new BFF route) forwards `{email, password, full_name}` — **never `role`** (backend default `guest`) — then performs the login itself; 409 → "Konto z tym e-mailem już istnieje" + switch to login with the e-mail kept |
| Failure | 401 → generic "Nieprawidłowy e-mail lub hasło"; 429 → wait from `Retry-After`; 502/503 → retry offered; dialog closed by the user → intent discarded, focus returns to initiator, `auth_resume` outcome `abandoned` |
| Session expiry mid-action | a 401 from any engagement write after the BFF's own refresh failed → AuthInterrupt with the same intent (draft kept in memory) |
| Not hidden | BG-1 (logout does not revoke) and BG-5 (no refresh grace) are **not** mitigated by composition; FE-003a may be built, **beta is blocked** until both close. The 120 s rotation memory (D-101) is not extended |
| Accessibility | WCAG 3.3.8: paste allowed, `autocomplete` (`email`, `current-password`, `new-password`), no puzzles; focus rules in §9.3 |

### 3.8 G9 — exact address / meeting point

**Not implemented in FE-003.** No field, endpoint or participant-only delivery
model exists (04a §24). FE-003 renders **no** address, street, building,
coordinates or meeting instructions anywhere — including CONFIRMED viewings,
threads, e-mails, analytics, URLs, logs and `aria` text. A CONFIRMED viewing
says only "Potwierdzone" with date/time; copy must not promise that Homies
will deliver the address. Missing delivery model = **BETA BLOCKER (BB-3)**.

### 3.9 Supply-side authorization (ContextSwitch, ProviderViewingRow)

| Capability | Authority (02 §2; `authority.py`) | Backend route | Status |
|---|---|---|---|
| Read/answer provider conversations | MANAGE_MESSAGES (OWNER, ADMIN, AGENT roles; mandate MANAGE_MESSAGES) | `/v1/conversations…` | CURRENT BACKEND, authority-correct |
| Assign lead / set stage | MANAGE_MESSAGES | `…/assign`, `…/stage` | CURRENT BACKEND; UI = FE-003f (optional) |
| List/confirm/decline/cancel/outcome viewings | MANAGE_VIEWINGS (OWNER, ADMIN, AGENT; mandate MANAGE_VIEWINGS) | `/v1/classifieds/{id}/viewings`, `/v1/viewings/{id}/…` | CURRENT BACKEND, authority-correct |
| Viewing settings/windows/blackouts editor | MANAGE_VIEWINGS | `PUT/POST …` (no GET) | FUTURE (owner panel) |
| Enumerate "my listings" for the provider context | PUBLISH_LISTING only today | `GET /v1/me/classifieds` | **BACKEND/API GAP BP-3** for MANAGE_VIEWINGS/MANAGE_MESSAGES-only holders |
| Create property / listing / price / pause / availability | **legacy `require_role("host")`** | `properties/router.py` | **BETA BLOCKER BB-6**: not authority-correct |

Rules: the provider context is shown **only** when authority-backed data says
so — a provider-side row in `GET /v1/conversations` (`my_side=provider`) or a
non-empty `GET /v1/me/classifieds` — **never** from `user.role == "host"`.
FE-003 does not encode `host` as the product model and does not offer a role
choice at registration. Provider viewing rows exist only per listing the
client can enumerate; MANAGE_VIEWINGS-only mandate holders get the provider
viewing surface only after BP-3.

### 3.10 Cancellation attribution

The UI shows **"Oglądanie odwołane"** for every CANCELLED viewing, with **no
actor** (requester / provider / Homies), until an explicit, immutable
cancellation source exists in the API (**BB-5**). `cancelled_by_homies`
(timestamp-derived, LISTING close_engagement only) is not displayed as
attribution and is not used for dispute-facing UI. The moderation notice
(`MODERATION_VIEWING_CANCELLED`, TASK-015) is a notice in `/v1/me/inbox`, not
an attribution field on the viewing; rendering notices is FUTURE (not FE-003).

## 4. G-14 existing-viewing decision gate — **FOUNDER DECISION REQUIRED**

**Current semantics (verified):** a `FEATURE_RESTRICTED` decision on a
conversation closes that conversation only (`trust/decisions.py:592–594`).
The requester's existing REQUESTED/CONFIRMED viewings of that listing are
untouched; the provider can still confirm a REQUESTED one (no recontact check
in `_respond`); either side can cancel; outcome can be recorded. A new request
is refused (F6). Contact reveal is not barred (OD-2).

| Option | Safety / product consequences | Backend changes | Frontend changes |
|---|---|---|---|
| **A. Leave unchanged** (current) | A person Homies judged abusive (e.g. HARASSMENT) keeps a confirmed visit to someone's home; the provider may unknowingly confirm a pending one; once G9 exists the address would reach them. Inconsistent with the intent of F6 | none | none |
| **B. Freeze future actions, keep the viewing** | No new confirmation, but a CONFIRMED visit still happens unless someone cancels; "frozen" is a new state nobody can resolve; the provider is uncertain whether to open the door | refuse `confirm` for a restricted requester (409 `RECONTACT_BLOCKED`); add an API-visible flag (e.g. `restricted: true`) — **API change**; G9 must withhold for flagged viewings; tests incl. PG race restriction ↔ confirm | new derived "Wstrzymane" state on both sides; action matrix changes |
| **C. Cancel** | Clean: no pending or confirmed contact survives the restriction, matching F6. Cost: if the restriction was a mistake, the viewing is gone (review-request path exists; the requester can rebook after a new generation or a reversal policy) | in `apply_conversation_decision` (FEATURE_RESTRICTED) cancel **that requester's future** REQUESTED/CONFIRMED viewings **of that listing** in the same transaction, lock order listing → conversation → viewings (as close_engagement); `ViewingCancelled(cancelled_by=HOMIES, moderation_decision_id)`; neutral notices to both sides; **requires BB-5** (explicit cancellation source) because the current derivation recognises LISTING decisions only; tests SQLite + PG race (restriction ↔ confirm/request/cancel) | none beyond the generic "Oglądanie odwołane" + notice |
| **D. Vary by state** (e.g. REQUESTED → cancel, CONFIRMED → keep + provider warned) | Most nuanced; needs B's flag/warning machinery and C's cancellation; more states to test and explain | B + C combined | B + C combined |

**Recommendation: C**, scoped exactly as above (one requester, one listing,
future REQUESTED/CONFIRMED only, same transaction), implemented together with
BB-5. Reason: the restriction already asserts the requester must not engage
with this listing for this generation (G-14/F6); a surviving home visit is the
highest-consequence form of engagement, and A/B leave the provider exposed
without information. Terminal and past viewings are never touched.

**Impact on FE-003:** material for **FE-003e** (requester viewing states) and
**FE-003f** (provider rows). FE-003a–d do not depend on it. FE-003e/f
implementation waits for the decision (and, for C, BP-6 + BB-5).

## 5. Open decisions

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| OD-1 | G-14 existing viewings (§4) | C | FE-003e, FE-003f |
| OD-2 | Does G-14 also bar **contact reveal** for the same listing/generation? | Yes (`409 RECONTACT_BLOCKED`, same rule), else the restriction is bypassed by phone | FE-003d copy/state; small backend change |
| OD-3 | What identity of the requester may a provider see (none / first name / first name + initial)? | first name + initial, from `full_name`, server-side projection; no e-mail/phone | FE-003f (BP-4) |
| OD-4 | Is "Zgłoś wiadomość" (message report, backend ready) part of FE-003c? | Yes — reporting is the safety counterpart of messaging; small UI | scope of FE-003c |
| OD-5 | 1C token/visual layer on FE-002 surfaces: separate task before/parallel to FE-003? | Separate task **FE-VIS-001**, parallel; FE-003 components consume semantic tokens only | none (sequencing) |
| OD-6 | Slots for anonymous visitors? | Keep auth-required (the provider's schedule is not public); UI invites sign-in | none (current behaviour) |

## 6. Component inventory (FE-003 IMPLEMENTATION)

Common to all components: Polish strings from `i18n/pl.ts` (EN/UK keys
reserved, G-13); errors through `api/errors.ts`; domain codes mapped by one
exhaustive table (§9.2 parity test); no colour-only meaning; targets ≥ 44 px
for primary/touch; visible focus not obscured by sticky chrome
(`scroll-padding`); analytics only through the consent gate (§8);
responsive split at **1024 px** (DESIGN-001 §4): rail ≥ 1024, dock < 1024.

### 6.1 SaveButton

| Aspect | Contract |
|---|---|
| Purpose | Save / unsave one listing |
| Route/screen | results cards `/wynajem…`, map card, detail `/oferta/[id]` (rail + dock), saved list |
| Authoritative data | saved-id set (CLIENT COMPOSITION from `GET /v1/me/saved-listings`); listing id |
| API/BFF | `POST`/`DELETE /bff/v1/me/saved-listings/{id}` (`auth: required`); `GET /bff/v1/me/saved-listings` |
| Input/output | `listingId`, `initialSaved`, `variant (icon\|labelled)` → emits `saved`/`unsaved` to the set store |
| Loading | pending: `aria-busy="true"`, disabled, spinner inside the 44 px target; label unchanged until confirmed |
| Empty | n/a |
| Error | 404 "Oferta niedostępna"; 409 cap; 429 retry-after; network → 1 auto-retry then inline retry; messages in the shared polite live region |
| Auth | anonymous → AuthInterrupt(intent `save`) → resumes automatically |
| Accessibility | `<button aria-pressed>`; accessible name includes the listing title ("Zapisz: {title}"); state change announced politely |
| Responsive | icon on cards; labelled in rail/dock |
| Analytics | `save_toggled` (§8) |
| Tests | unit (state machine, retry); component (pressed/pending/error); BFF (route allowlisted, auth required); E2E save → saved list → unsave; tombstone; axe |
| Acceptance | AC-S1…S6 |

### 6.2 EngagementRail (desktop ≥ 1024)

| Aspect | Contract |
|---|---|
| Purpose | Sticky right column on detail: price summary + engagement actions |
| Route | `/oferta/[id]` |
| Authoritative data | `ClassifiedOut` (price fields, `contact_mode`, `freshness`), session, saved set, own active thread (composed), own future viewing (composed) |
| API/BFF | none of its own; hosts SaveButton, message CTA, viewing CTA, reveal CTA |
| Input/output | listing + session + engagement summary → opens composer / slot picker / reveal step |
| Loading | price summary renders server-side; action area skeleton while session/engagement summary loads (no layout shift > 0.1 CLS) |
| Empty | actions whose slice has not shipped are **absent** (no dead buttons, DESIGN-001 §5.5) |
| Error | engagement summary failure → actions still usable; only the "already have a thread/viewing" hints are omitted |
| Auth | anonymous sees all shipped CTAs; each opens AuthInterrupt with its intent |
| Accessibility | `complementary` landmark "Koszty i kontakt"; logical tab order: price → save → message → viewing → phone |
| Responsive | hidden < 1024 (MobileActionDock takes over) |
| Analytics | none of its own (actions emit) |
| Tests | component (action presence by `contact_mode`, slice flags, session); visual regression; axe |
| Acceptance | AC-R1…R4 |

### 6.3 MobileActionDock (< 1024)

| Aspect | Contract |
|---|---|
| Purpose | Bottom bar: monthly total + primary action + save |
| Route | `/oferta/[id]` |
| Authoritative data | `monthly_total_estimate`, `utilities_basis`, the same engagement summary as the rail |
| API/BFF | none of its own |
| Input/output | primary action = viewing when FE-003e shipped, else message; secondary opens a sheet with the others |
| Loading / empty / error | as EngagementRail |
| Auth | as EngagementRail |
| Accessibility | `region` "Akcje oferty"; respects `env(safe-area-inset-bottom)`; page gets bottom padding so focused content is never covered (2.4.11); sheet = dialog rules (§9.3) |
| Responsive | only < 1024; hidden while the on-screen keyboard is open in the composer |
| Analytics | none of its own |
| Tests | Playwright mobile project: no overlap with focused elements; sheet focus; axe |
| Acceptance | AC-D1…D3 |

### 6.4 ViewingSlot

| Aspect | Contract |
|---|---|
| Purpose | Render one **derived** offered instant; group by local day; let the user pick one |
| Route | slot picker sheet/dialog from detail; "Wybierz inny termin" from ViewingState |
| Authoritative data | `viewing-slots` response (typed by BP-2: instants, duration, timezone) |
| API/BFF | `GET /bff/v1/classifieds/{id}/viewing-slots?start&days` (`auth: required` — CF-2) |
| Input/output | `slots[]`, `timezone`, `duration` → `selected starts_at` (the exact string received) |
| Loading | skeleton day groups; picker keeps its height |
| Empty | no settings / no free terms (§3.3) with "Pokaż kolejne dni" |
| Error | 401 → AuthInterrupt; 404 → "Oferta niedostępna"; 429/503 retry |
| Auth | signed-in only |
| Accessibility | `radiogroup` per day ("wtorek, 14 października"), each slot a radio "10:00–10:30"; arrow-key navigation; selected state not colour-only |
| Responsive | horizontal day tabs + vertical list on mobile; grid ≥ 1024 |
| Analytics | `viewing_slot_selected` |
| Tests | unit (grouping in the response timezone across DST using fixture instants); component; E2E with seeded windows; axe |
| Acceptance | AC-V1…V4 |

### 6.5 ViewingState

| Aspect | Contract |
|---|---|
| Purpose | Show one viewing's state and the actions the backend allows now |
| Route | detail (own viewing hint), `/ogledziny`, provider rows (variant) |
| Authoritative data | `ViewingOut` (status, starts_at, ends_at, attendee_count) |
| API/BFF | `POST /bff/v1/viewings/{id}/cancel` (requester); provider variant in ProviderViewingRow |
| Input/output | viewing + now → label, allowed actions (§3.3 table) |
| Loading | action pending state; status re-read after any 409 |
| Empty | "Nie masz umówionych oglądań" (list) |
| Error | 409 state conflict → re-read + render; 404 → removed from list with status "Oglądanie niedostępne" |
| Auth | signed-in |
| Accessibility | status text + icon (never colour alone); `<time datetime>`; cancel confirm dialog |
| Responsive | card on mobile, row ≥ 1024 |
| Analytics | `viewing_cancel_submitted` (outcome); confirmations/declines come from server facts |
| Tests | unit (label/action matrix for all 6 states × before/after start); E2E request → confirm (provider) → requester sees CONFIRMED; cancel; past REQUESTED label |
| Acceptance | AC-V5…V9 |

### 6.6 ConversationComposer

| Aspect | Contract |
|---|---|
| Purpose | Write the first message (creates the thread) or the next one |
| Route | detail (first message sheet), `/wiadomosci/[id]` (PROPOSED) |
| Authoritative data | thread status, `my_side` |
| API/BFF | `POST /bff/v1/classifieds/{id}/conversations`, `POST /bff/v1/conversations/{id}/messages` |
| Input/output | text (≤ 4000 after trim) → `MessageOut` appended |
| Loading | `sending` state: input read-only, send disabled, `aria-busy` |
| Empty | send disabled for blank |
| Error | §3.2 failure table; unknown outcome → re-read before "Wyślij ponownie" |
| Auth | anonymous → AuthInterrupt(intent `message`), draft kept in memory only |
| Accessibility | labelled textarea; counter `aria-live="polite"` near the limit; Enter = newline, Ctrl/Cmd+Enter = send (announced in the hint); errors linked by `aria-describedby` |
| Responsive | docked above the keyboard on mobile (`visualViewport`); the dock hides |
| Analytics | `conversation_start_submitted`, `message_send_submitted` (outcome codes only, never text or length) |
| Tests | unit (state machine incl. unknown outcome); component; E2E start → continue → closed by moderation (seeded) → RECONTACT_BLOCKED |
| Acceptance | AC-C1…C8 |

### 6.7 ConversationItem

| Aspect | Contract |
|---|---|
| Purpose | One inbox row (and, as `MessageItem`, one message in a thread) |
| Route | `/wiadomosci` (PROPOSED), thread view |
| Authoritative data | `ConversationOut` / `ProviderConversationOut`; listing via `GET /v1/classifieds/{listing_id}` (CLIENT COMPOSITION); `MessageOut` |
| API/BFF | `GET /bff/v1/conversations`, `GET /bff/v1/conversations/{id}`, listing GET |
| Input/output | row: listing title (or "Oferta niedostępna" on 404), district, `last_message_at`, status badge; message: sender side, body or REMOVED/SYSTEM mapping, time |
| Loading | row skeletons; listing title loads lazily |
| Empty | "Nie masz jeszcze wiadomości" + search link |
| Error | list error with retry; per-row listing 404 handled as tombstone |
| Auth | signed-in |
| Accessibility | list of links; CLOSED badge text; messages as a log (`role="log"`, polite) without re-announcing history |
| Responsive | list → thread navigation on mobile; split ≥ 1024 |
| Analytics | none (server derives) |
| Tests | component (REMOVED, SYSTEM code, unknown SYSTEM code, CLOSED, ARCHIVED, provider fields hidden on tenant side) |
| Acceptance | AC-C9…C11 |

### 6.8 AuthInterrupt

| Aspect | Contract |
|---|---|
| Purpose | Sign in or register without losing the pending action (§3.7) |
| Route | dialog over any page; fallback pages `/logowanie`, `/rejestracja` (PROPOSED) for no-JS |
| Authoritative data | `/bff/auth/session` |
| API/BFF | `/bff/auth/login`, **new** `/bff/auth/register` (CSRF, 4 KB cap, never forwards `role`), `/bff/auth/session` |
| Input/output | intent → `resumed \| abandoned \| failed` |
| Loading | submit pending; fields disabled |
| Empty | n/a |
| Error | 401 generic; 409 e-mail exists (register); 422 password rules (≥ 10 chars) inline; 429 countdown; 502 retry |
| Auth | — |
| Accessibility | modal dialog, background `inert`, **e-mail field focused on open**, Esc closes, focus returns (§9.3); 3.3.8 compliant |
| Responsive | full-screen sheet < 1024 |
| Analytics | `auth_interrupted` (intent), `auth_resumed` (outcome) — existing `signup_started` reused for the register tab |
| Tests | unit (intent store, expiry, no free text persisted); BFF register route (CSRF, size, no role, login after register); E2E each intent resumes as specified; focus tests |
| Acceptance | AC-A1…A8 |

### 6.9 ContextSwitch

| Aspect | Contract |
|---|---|
| Purpose | Switch inbox/viewings between "Szukam" (tenant) and "Wynajmuję" (provider) |
| Route | `/wiadomosci`, `/ogledziny` |
| Authoritative data | presence of `my_side=provider` rows; `GET /v1/me/classifieds` non-empty (PUBLISH_LISTING) — never `role` |
| API/BFF | `GET /bff/v1/conversations`, `GET /bff/v1/me/classifieds` (to be allowlisted, `auth: required`) |
| Input/output | → `context` (URL param, e.g. `?widok=wynajmujacy`), shareable, default tenant |
| Loading | hidden until the data says provider context exists |
| Empty | not rendered for tenant-only users |
| Error | data failure → not rendered (tenant view still works) |
| Auth | signed-in |
| Accessibility | tablist with two tabs or segmented radio; state in text |
| Responsive | full-width segmented control on mobile |
| Analytics | none |
| Tests | component: shows for an AGENT member / mandate holder with provider rows, hidden for a `host`-role user with no authority, shown for a `guest`-role user who holds authority |
| Acceptance | AC-P1…P2 |

### 6.10 ProviderViewingRow

| Aspect | Contract |
|---|---|
| Purpose | One viewing of a managed listing with provider actions |
| Route | provider context of `/ogledziny`, grouped by listing |
| Authoritative data | `ProviderViewingOut` (`requester_user_id`, `requester_note`), requester display per OD-3/BP-4 |
| API/BFF | `GET /bff/v1/classifieds/{id}/viewings`; `POST /bff/v1/viewings/{id}/{confirm,decline,cancel,outcome}` |
| Input/output | allowed actions: REQUESTED & future → Confirm / Decline / Cancel; CONFIRMED & future → Cancel; CONFIRMED & started → Odbyło się / Nie przyszedł; others → none |
| Loading | per-action pending |
| Empty | "Brak próśb o oglądanie" |
| Error | `LISTING_HELD` → held notice; 409 full/passed/changed → re-read; 404 → authority lost → row removed with status |
| Auth | MANAGE_VIEWINGS on the listing (backend-enforced; UI never assumes) |
| Accessibility | `requester_note` rendered as plain text (no HTML/links auto-detected); actions are buttons with the date in their names |
| Responsive | card on mobile |
| Analytics | none client-side (server facts ViewingResponded/Cancelled/OutcomeRecorded) |
| Tests | component (action matrix); E2E provider confirm/decline/outcome on seed; LISTING_HELD with a seeded held listing |
| Acceptance | AC-P3…P6 |

## 7. DESIGN-001C restyles — FE-003 vs visual-system work

| Belongs to **FE-003** | Belongs to **separate visual-system task (FE-VIS-001, OD-5)** |
|---|---|
| The ten components of §6, built on **semantic** tokens (`--c-surface`, `--c-ink`, `--c-brand-*`, status tokens) so they inherit 1C without rework | 1C token layer (district/area colour identity, typography, radii, elevation) replacing Design System v1 values |
| Layout of the detail engagement area (rail/dock), slot picker, inbox/thread, my viewings, saved list, auth dialog | Restyle of FE-002 surfaces: home, SearchBox, results list, ListingCard, filters, map pills/cards, header/footer, 404 |
| Copy keys for every engagement state | Area-colour mapping per district (must never encode quality/trust/status, D-103) |
| Focus/keyboard rules of §9.3 | Figma/Claude Design file maintenance and mobile frames |

Exact assignment of individual 1C artboards is confirmed against the handoff
at P-0.

## 8. Analytics — event requirements only

Ingestion stays **off** (G-12: vendor-neutral, first-party ingestion
legal-gated before external beta — BB-8). FE-003 adds catalogue entries to
EVENTS-v1 and emits through the existing consent gate to the existing sinks
(noop/memory/console). Server facts remain the source of truth for outcomes;
client events describe intent and friction.

| Measurement need | Event / source | Safe dimensions | Forbidden |
|---|---|---|---|
| listing exposure | existing `search_results_viewed`, `listing_viewed` | search_id, position | — |
| save | `save_toggled` (client) + `saved_listings` table | listing_id, action save/unsave, outcome code, surface | — |
| conversation initiation | `conversation_start_submitted` (client) + table `conversations` (server) | listing_id, outcome code | message text, length |
| message sent | `message_send_submitted` (client) + table `messages` | outcome code, side | text, length |
| viewing slot selected | `viewing_slot_selected` | listing_id, days-ahead bucket, hour bucket | exact instant |
| viewing requested | `viewing_request_submitted` (client) + fact `ViewingRequested` | listing_id, outcome code, attendee_count bucket | note |
| viewing confirmed/declined/cancelled | facts `ViewingResponded`, `ViewingCancelled`, `ViewingOutcomeRecorded` (server only) | as EVENTS-v1 §2 | — |
| contact reveal | `contact_reveal_submitted` (client) + table `contact_reveals` | listing_id, outcome code, quota_remaining bucket | phone |
| auth interruption | `auth_interrupted` (+ existing `signup_started`) | intent code | e-mail |
| auth resume | `auth_resumed` | intent, outcome resumed/abandoned/failed | — |
| RECONTACT_BLOCKED | `engagement_refused` | surface (conversation/viewing/reveal), code | reason, decision id |
| API conflict/error | `engagement_api_error` | route template, status, domain code or `none`, kind | `detail` text, request body |

Rules: closed catalogue, `schema_version` 1 per name, no `user_id` from the
client, route templates not URLs, every payload pinned by a test. Attributed
acquisition (ATTRIBUTION-v1) is **never** read as causal effect; any lift
claim needs an EXPERIMENTS-v1 randomised test.

## 9. Testing contract

### 9.1 Matrix

| Layer | FE-003a auth | b save | c conversation | d reveal | e viewing | f provider |
|---|---|---|---|---|---|---|
| Unit (Vitest) | intent store, expiry, resume rules | saved-set store | composer state machine, unknown-outcome reconcile | quota display, gate step | slot grouping (DST fixtures), label/action matrix | action matrix |
| Integration (client + mocked BFF) | dialog ↔ session | button ↔ set | thread ↔ inbox | verify → reveal | picker → request → state | rows ↔ actions |
| API contract | `check:api` regenerated types; register response has no tokens | saved schemas | codes from BP-1 | codes | typed slots (BP-2) | provider DTO (BP-4) |
| BFF (Vitest) | new register route: CSRF, 4 KB, `role` stripped, login chained; allowlist entries + auth levels | allowlist | allowlist | allowlist | `viewing-slots` = required | allowlist incl. `/me/classifieds` |
| Component | AuthInterrupt | SaveButton | Composer, ConversationItem | reveal CTA | ViewingSlot, ViewingState | ContextSwitch, ProviderViewingRow |
| Responsive (Playwright desktop + mobile) | dialog/sheet | card/rail/dock | inbox/thread split | dock sheet | picker | rows |
| Accessibility (axe on every new surface) | yes | yes | yes | yes | yes | yes |
| Keyboard/focus | §9.3 | toggle | Ctrl+Enter, log | step | radios/arrows | buttons |
| E2E (seeded API) | each intent resumes | save/unsave/tombstone/limit | start, continue, closed, blocked, redacted | verified/unverified/messages-only/quota | instant, approval, conflict, already booked, blocked, held | confirm, decline, cancel, outcome, held |
| Semantic parity | role never sent; phoneVerified from `phone_verified_at` | no save-to-probe | 4000 limit = backend constant | quota limit from API | client never computes slots; totals never recomputed | context never from `role` |

Backend tests are added only with backend changes (BP-*), each with SQLite and
PG variants where locks are involved. `seed_e2e.py` gains: viewing settings +
windows on two listings (one INSTANT, one APPROVAL), a phone-mode listing, a
verified-phone seeker, a held listing, a closed conversation, a redacted
message and a G-14-restricted requester (all fictional, existing opt-ins).

### 9.2 Parity tests (backend ↔ frontend)

1. **Codes:** a generated JSON of backend refusal codes (BP-1) is compared with
   the frontend mapping table; a code without Polish copy fails CI.
2. **Totals:** fixture with non-additive parts → UI shows the API totals.
3. **Limits:** message 4000, note 1000, attendees 1–10, name 80 read from
   OpenAPI constraints, not hard-coded twice.
4. **Slots:** UI offers exactly the instants returned (count and values).
5. **Privacy:** E2E asserts no seeded street/address, phone (except after a
   reveal, in the reveal element only), message text or note appears in
   analytics payloads, URLs or `sessionStorage`.
6. **Authority:** ContextSwitch/ProviderViewingRow visibility follows authority
   fixtures, not `role`.

### 9.3 Focus requirements (DESIGN-001C)

* The filter dialog receives focus on open; focus returns to its opener on
  close (FE-002 surface, re-verified in FE-003 E2E because the dock/rail
  changes the detail page's chrome).
* The auth dialog focuses the **e-mail** field on open.
* After an auth interruption, focus returns to the **initiating action**; if
  the initiator no longer exists (e.g. the listing became unavailable, the
  thread replaced the CTA), focus moves to the **result status** message.
* Every dialog/sheet traps focus, Esc closes, background is `inert`.

## 10. Prerequisites, blockers, slices

### 10.1 Backend prerequisites (separate bounded tasks; R1 unless noted)

| # | Change | Needed by |
|---|---|---|
| BP-1 | Stable code prefixes on engagement refusals: `OWN_LISTING`, `VIEWINGS_NOT_OFFERED`, `SLOT_NOT_OFFERED`, `SLOT_FULL`, `VIEWING_ALREADY_BOOKED`, `VIEWING_STATE_CONFLICT`, `VIEWING_CHANGED`, `VIEWING_TIME_PASSED`, `VIEWING_NOT_STARTED`, `MESSAGES_ONLY`, `PHONE_NOT_VERIFIED`, `REVEAL_QUOTA`, `CONVERSATION_QUOTA` (+ `Retry-After`), `SAVED_LIMIT`, `SAVED_SEARCH_DUPLICATE`, `SAVED_SEARCH_LIMIT` (names proposed); documented in OpenAPI | c, d, e (b optional) |
| BP-2 | Typed `viewing-slots` response incl. `timezone` | e |
| BP-3 | Provider enumeration by scope (listings where the user holds MANAGE_VIEWINGS / MANAGE_MESSAGES) | f |
| BP-4 | Requester display projection for provider DTOs (per OD-3) | f |
| BP-5 | = BB-5 explicit immutable cancellation source (R2, schema EXPAND) | e/f display; OD-1 C |
| BP-6 | OD-1 implementation (recommended C) (R2) | e, f |
| BP-7 | `cancel` refused after `starts_at` (stable code) | e (recommended) |
| BP-8 | OD-2 if accepted: G-14 bar on contact reveal | d |
| optional | G8 saved flag/ids; `can_send`/`closed_by` | — |

### 10.2 Beta blockers (unchanged by FE-003; composition never hides them)

| # | Blocker |
|---|---|
| BB-1 | BG-1 logout / refresh revocation endpoint |
| BB-2 | BG-5 refresh reuse/grace semantics |
| BB-3 | G9 participant-only address/meeting delivery model |
| BB-4 | G4 mandatory/optional parking owner input |
| BB-5 | explicit immutable viewing cancellation source |
| BB-6 | authority-correct supply routes (legacy `host` gate) |
| BB-7 | production SMS provider (phone verification) |
| BB-8 | first-party analytics ingestion: storage/retention/consent legal gate |
| BB-9 | OD-1 decided and implemented before viewings reach external users |

### 10.3 Implementation slices (each a separate reviewable candidate, R2)

| Slice | Content | Entry criteria |
|---|---|---|
| **FE-003a** | `/bff/auth/register`, AuthInterrupt, intent store/resume, session `phoneVerified` fix, fallback pages | contract approved; P-0 |
| **FE-003b** | SaveButton, saved list, save search + saved-search list; rail/dock skeleton with Save only | FE-003a |
| **FE-003c** | Composer, inbox, thread, ConversationItem, message CTA in rail/dock | FE-003a; BP-1; OD-4 |
| **FE-003d** | reveal CTA, phone verification step, quota | FE-003a; BP-1; OD-2 (BP-8 if yes); beta needs BB-7 |
| **FE-003e** | ViewingSlot, request sheet, ViewingState, my viewings, viewing CTA | FE-003a; BP-1; BP-2; **OD-1 decided** (+BP-6, BP-5 for C); BP-7 recommended |
| **FE-003f** | ContextSwitch, provider inbox view, ProviderViewingRow | FE-003c/e; BP-3; BP-4/OD-3; BP-5 |

No slice ships to an external beta while any BB is open.

## 11. Acceptance criteria

**Global:** AC-G1 no FE-003 surface shows an address, street, coordinate or
meeting point. AC-G2 no total is computed client-side. AC-G3 every refusal
renders a mapped Polish state; none shows raw `detail`. AC-G4 no dead buttons:
an action appears only when its slice is shipped. AC-G5 every new route is in
the BFF allowlist with the backend's auth level; nothing else is proxied.
AC-G6 analytics silent without consent; payloads pinned. AC-G7 axe: zero
violations on every new surface, desktop and mobile. AC-G8 no `role` is sent
or read for product decisions.

**Auth (a):** AC-A1 each intent resumes per §3.7. AC-A2 register → login →
session in one user step; no tokens reach the browser. AC-A3 409 on register
offers login with the e-mail kept. AC-A4 no message draft/note/phone in
storage. AC-A5 e-mail focused on open; focus return per §9.3. AC-A6 401 on a
write re-opens AuthInterrupt with the intent. AC-A7 intent expires after
30 min. AC-A8 abandoned dialog discards the intent.

**Save (b):** AC-S1 pressed state changes only on 200/201/204. AC-S2 saved
state correct across results, map card, detail and saved list after reload.
AC-S3 tombstone shows no listing data. AC-S4 404/409/429 states. AC-S5 saved
search stores the API canonical query; duplicate → link to existing. AC-S6
INVALID saved search is shown, not run broader.

**Rail/dock:** AC-R1 rail ≥ 1024, dock < 1024, never both. AC-R2 phone CTA
only for `contact_mode=phone`. AC-R3 existing thread/viewing shown instead of
a new start. AC-R4 price summary = FE-002 CostBreakdown values. AC-D1 dock
never covers focused content. AC-D2 dock hidden with the keyboard open.
AC-D3 dock sheet follows dialog rules.

**Conversation (c):** AC-C1 a thread starts only with a non-blank message.
AC-C2 4000-character limit enforced and counted. AC-C3 writing again on the
same listing continues the thread. AC-C4 CLOSED / ARCHIVED read-only with the
mapped notice. AC-C5 REMOVED shows "usunięta przez Homies" with no body.
AC-C6 RECONTACT_BLOCKED state, no retry. AC-C7 unknown outcome never
auto-resends and never duplicates after reconcile. AC-C8 quota/rate states
with Retry-After where given. AC-C9 inbox rows survive listing 404. AC-C10
tenant never sees provider fields. AC-C11 SYSTEM code mapped; unknown code
neutral.

**Reveal (d):** AC-RV1 unverified → verification step, then a deliberate
press. AC-RV2 quota visible before the wall. AC-RV3 repeat reveal free.
AC-RV4 messages-only state. AC-RV5 the number never leaves the reveal
element (no storage/analytics/URL/log).

**Viewing (e):** AC-V1 slots signed-in only. AC-V2 the UI offers exactly the
returned instants in the response timezone. AC-V3 no-settings and no-free-terms
states. AC-V4 "Pokaż kolejne dni" within 31 days. AC-V5 result state taken
from the response (INSTANT → CONFIRMED). AC-V6 conflict → re-fetch, sheet kept.
AC-V7 already-booked → link to it. AC-V8 cancel only before start; CANCELLED
without actor. AC-V9 past REQUESTED labelled "Bez odpowiedzi", no actions.

**Provider (f):** AC-P1 ContextSwitch from authority data only. AC-P2 tenant
view works when provider data fails. AC-P3 action matrix exactly §6.10.
AC-P4 LISTING_HELD state. AC-P5 `requester_note` plain text. AC-P6 requester
identity only per OD-3.

## 12. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Design handoff not inspected by the builder (§0.2) | P-0; conflicts raised before code |
| R-2 | English `detail` parsing creeps in before BP-1 | BP-1 is an entry criterion for c/d/e; lint/test forbids string matching on `detail` |
| R-3 | Duplicate messages on unknown outcome | reconcile-before-resend; future idempotency key (FUTURE) |
| R-4 | Saved-set composition cost (5 calls at 500 saves) | once per session; G8 if measured slow |
| R-5 | Restricted requester keeps a home visit (OD-1 A) | founder decision before FE-003e |
| R-6 | G-14 bypass via phone reveal (OD-2) | founder decision before FE-003d |
| R-7 | Providers without PUBLISH_LISTING cannot reach their viewings | BP-3 before FE-003f |
| R-8 | Session logout illusions (BG-1) and refresh races (BG-5) | beta blocked; not masked |
| R-9 | Time display wrong across DST if timezone assumed | BP-2 entry criterion; DST fixtures |
| R-10 | Provider scopes checked with `verified=False` (CF-14) | Codex audit question; no FE change |
| R-11 | Free text (notes, messages) leaking into analytics/storage | parity test §9.2-5 |

## 13. Status

`FE-003 IMPLEMENTATION AUTHORIZED: NO`

Next step: founder + GPT-5.6 Sol review of this contract, decisions OD-1…OD-6,
and P-0 (handoff file in the repository). No FE-003 production code, merge or
deployment before that.
