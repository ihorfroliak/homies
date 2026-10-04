# FE-003 — Save → Conversation → Viewing · TASK CONTRACT

| Field | Value |
|---|---|
| Status | **CONTRACT FINAL CANDIDATE r2** — founder/GPT review *PASS WITH REQUIRED CHANGES + FOUNDER DECISIONS* (2026-10-04) applied; awaiting **final contract approval**. **`FE-003 IMPLEMENTATION AUTHORIZED: NO`** |
| Baseline | `main` = `995b05fe72bc15a86141e214bf1c4fc63b8bc570`; schema head `a3c5e7f9b1d4` (no later revision) |
| Design input | DESIGN-001C *Homies 001C Dzielnica Product Convergence* (`.dc.html`) — approved by founder/GPT **at design-contract level**; implementation needs the repository handoff of §0.2 (P-0) |
| Founder decisions | **D-104** (OD-1…OD-6, BP-9 security gate, BP-10, BP-7 required, DEBT-1) — canon 04a §24 |
| Risk class (implementation) | **R2** (auth/session, private engagement, privacy, concurrency, moderation states); BP-6, BP-9, BP-10, BP-11 are R2 backend tasks with security review |
| Canon | 00-AUTHORITY; 02 §2 (authority chain); 03 §2; 04 §73 (idempotency keys); 04a §6, §14, §16, §18, §21–§24; 07; DECISIONS D-98 (G-11…G-15), D-100…D-104; DESIGN-001; FE-001; FE-002; GROWTH-001 EVENTS-v1 |
| File name | kept as `…-DRAFT.md` so existing references stay valid |
| Out of scope | final 1C token/visual layer (**FE-VIS-001**, OD-5); owner panel (listing create/edit, viewing settings/windows editors); notification-centre UI; moderator app; applications / Housing Passport; payments; OTP / magic link / Google sign-in; exact address delivery (G9) |

## 0. How to read this contract

### 0.1 Classes

| Class | Meaning |
|---|---|
| **CURRENT BACKEND** | exists in `backend/` at the baseline, verified in code and tests |
| **CURRENT FE/BFF** | exists in `frontend/web/` at the baseline |
| **CLIENT COMPOSITION** | no new backend; the client combines existing calls/state. Never invents a domain fact |
| **FE-003 IMPLEMENTATION** | work FE-003 itself does once authorised |
| **BACKEND/API GAP** | missing backend capability; a separate bounded backend task (§10.1) |
| **BETA BLOCKER** | must be closed before any external beta (§10.2) |
| **FUTURE / OUT OF SCOPE** | not FE-003 |

Rule: **no UI design redefines backend semantics.** Where the approved design
needs something the API cannot do yet, the contract names the backend
prerequisite; the UI neither guesses nor silently substitutes another flow.

### 0.2 Design input — P-0

The raw `.dc.html` was not readable by the builder (not on disk; the Claude
Design connector answered HTTP 403). This contract binds the component names,
responsibilities and focus rules from the founder brief to the verified
backend.

**P-0 (implementation precondition, generalised):** implementation does
**not** need the raw `.dc.html` if the connector stays inaccessible. It
**does** need a versioned, repository-readable, approved DESIGN-001C
implementation handoff, e.g. `docs/design/DESIGN-001C-HANDOFF.md`, containing
every implementation-relevant rule: component anatomy and variants, all
states of §3/§6, copy keys, responsive breakpoints and layout, focus and
keyboard behaviour, motion limits, and which artboards belong to FE-003 vs
FE-VIS-001. The `.dc.html` remains the source visual artifact. Any conflict
between the handoff and §1–§9 is raised as a contract question before code.

## 1. Verified backend/API facts (at `995b05f`)

### 1.1 Save (TASK-014; 04a §22) — CURRENT BACKEND

| Fact | Source |
|---|---|
| `POST /v1/me/saved-listings/{listing_id}` → 201 new, **200 already saved (idempotent)**, 404 not public, 409 at 500 per user | `saved/router.py:82–124`, `core/config.py:111` |
| `DELETE /v1/me/saved-listings/{listing_id}` → 204 always (idempotent; works for gone listings) | `saved/router.py:127–136` |
| `GET /v1/me/saved-listings?limit≤100&offset` → `SavedListingOut{saved_id, listing_id, saved_at, availability_status AVAILABLE \| NO_LONGER_AVAILABLE, listing \| null}`; not public = **tombstone** | `saved/router.py:139–150`, `saved/schemas.py` |
| **No saved-state on `ClassifiedOut`**, no "is it saved?" endpoint (gap G8) | `properties/schemas.py:287–352` |
| Saved searches `POST/GET/PATCH/DELETE /v1/me/saved-searches[/{id}]`, `GET …/{id}/matches`; `{name ≤80, query (API canonical), notifications_enabled}`; 409 duplicate + `Location`; 409 at 50; 422 invalid; `query_state VALID \| INVALID` | `saved/router.py:200–368`, `config.py:112` |
| Bucket `SAVED_WRITE` (30, 0.5/s, per IP) | `core/ratelimit.py:89, 286` |

### 1.2 Conversations (04 §53–§55; TASK-015) — CURRENT BACKEND

| Fact | Source |
|---|---|
| Start `POST /v1/classifieds/{id}/conversations {body}` → 201 `ConversationDetail`; **first non-empty message required**; body 1…**4000**, stripped, blank → 422 | `engagement/router.py:76–84, 287–357` |
| One ACTIVE thread per requester × listing: a second start **continues** it (appends) | `router.py:313–344`, `models.py:76` |
| Start refusals: 404 not public; 409 own listing (no code); 409 `RECONTACT_BLOCKED:`; 429 daily quota 30 / 24 h (no code, no `Retry-After`) | `router.py:298–327` |
| Continue `POST /v1/conversations/{id}/messages`; non-ACTIVE → 409 `CONVERSATION_CLOSED:` | `router.py:389–406` |
| Statuses `ACTIVE \| ARCHIVED \| CLOSED`; only Homies closes in 1A, with a SYSTEM message body code `system.conversation_closed_by_homies` | `models.py:48, 54`; `trust/effects.py:35–61` |
| Redacted: `body: null`, `moderation_state: "REMOVED"` | `router.py:87–121` |
| Inbox `GET /v1/conversations` (no paging): own threads + threads on listings where the user holds MANAGE_MESSAGES via `authorized_property_ids(…)` **with `verified=False`** | `router.py:360–371` |
| No `can_send`/`closed_by`, unread, listing summary or counterpart name | `router.py:124–141` |
| Buckets `CONVERSATION_START` (10, 0.05/s), `MESSAGE_WRITE` (30, 0.5/s), per IP; middleware 429 has `Retry-After` | `ratelimit.py:75–76`; `composition.py:220–236` |
| **Not idempotent**: no client request id; a lost response can be followed by a duplicate. The canonical `platform.idempotency_keys` (04 §73) is not implemented for Phase-1 routes | `router.py:287–406`; `grep idempotency app/` |
| Message report `POST /v1/reports {target_type: "MESSAGE", target_id, reason HARASSMENT\|SCAM\|DISCRIMINATION\|SAFETY\|SPAM\|OTHER, text ≤2000}`; 200 already reported; **403 without a verified e-mail or phone**; 404 not a current side; 409 SYSTEM or own message; 429 quota (10/24 h, 20 waiting) | `trust/router.py:83–150` |

### 1.3 Viewings (04 §57–§60; 04a §14; TASK-015 S4b; D-102 F6) — CURRENT BACKEND

| Fact | Source |
|---|---|
| Availability **derived**: settings + windows − blackouts − capacity (buffers), DST-safe, minimum notice; **no slot entity** | `viewings.py:287–336` |
| `GET /v1/classifieds/{id}/viewing-slots?start&days=1..31` → `{"slots": [UTC instants], "duration_minutes": int \| null}`; **requires authentication**; 404 not public; no settings → empty | `viewings.py:400–412` |
| Slot computation runs one overlap count per candidate slot (bounded by `days ≤ 31` × windows) | `viewings.py:332–334` |
| Response **untyped** in OpenAPI; **no timezone** returned | `docs/api/openapi.json` |
| Request `POST /v1/classifieds/{id}/viewings {starts_at, attendee_count 1–10, note ≤1000}` → INSTANT ⇒ CONFIRMED, APPROVAL ⇒ REQUESTED; auth required | `viewings.py:164–168, 415–466` |
| Request refusals: 404 not public/held; 409 own listing; 409 `RECONTACT_BLOCKED:`; 409 no settings; 409 not an offered slot; 409 already booked. Only RECONTACT_BLOCKED has a code | `viewings.py:419–450` |
| Provider (MANAGE_VIEWINGS via `can_act(…, verified=False)`): confirm (REQUESTED, future, capacity, not held → `LISTING_HELD:`), decline, outcome (CONFIRMED after start), list `ProviderViewingOut{…, requester_user_id, requester_note}` | `viewings.py:222–230, 511–602` |
| `cancel` from REQUESTED/CONFIRMED by either side — **no time guard** | `viewings.py:561–576` |
| A passed REQUESTED viewing **stays REQUESTED** (no expiry); it stops blocking new requests | `viewings.py:445–450` |
| State conflicts without codes ("The viewing is X", "changed meanwhile", "slot is already full", "time has passed", "has not happened yet") | `viewings.py:480–496, 526–590` |
| `GET /v1/me/viewings` → `ViewingOut{…, cancelled_by_homies}`; no listing summary | `viewings.py:605–608` |
| `cancelled_by_homies` **derived** (cancelled_at == a LISTING close_engagement instant); actor recorded only in the outbox fact `ViewingCancelled.cancelled_by` | `trust/effects.py:113–126`; `viewings.py:572–574` |
| **Viewings carry no publication generation** | `engagement/models.py:288–307` |
| A G-14 restriction today closes the conversation only; existing viewings untouched; the provider can still confirm a REQUESTED one | `trust/decisions.py:507–600`; `viewings.py:511–546` |
| Settings/windows/blackouts writes (MANAGE_VIEWINGS); **no GET** | `viewings.py:349–394` |
| Viewing writes ride `PROPERTY_WRITE` (20, 0.5/s) | `ratelimit.py:299–302` |

### 1.4 Contact reveal — CURRENT BACKEND

| Fact | Source |
|---|---|
| `POST /v1/classifieds/{id}/contact` → `{offer_id, contact_phone}`; gate `phone_verified_at` else 403 | `properties/router.py:1012–1035` |
| 404 not public; 409 messages only (no code) | `router.py:1036–1045` |
| Repeat reveal: returned **before** the quota check, free, no new row; quota 20 / 24 h → 429 + `Retry-After`; new reveal → row + audit | `router.py:1047–1094` |
| `GET /v1/me/reveal-quota` | `router.py:996–1009` |
| Bucket `CONTACT_REVEAL` (10, 0.05/s) | `ratelimit.py:72` |
| **Not covered by G-14 today** | `router.py:1012–1094` |
| Phone verification start/confirm; `phone` + `phone_verified_at` set together at confirm; SMS = dev stub | `identity/router.py:233–283`; `verification.py:9–34` |

### 1.5 Pricing / CostSignature — CURRENT BACKEND (verified)

`ClassifiedOut`: `rent_amount, admin_fee, utilities_amount,
utilities_included, utilities_basis (INCLUDED | ESTIMATED | NOT_STATED),
parking_fee, deposit_amount, other_costs, monthly_total_estimate,
move_in_total, currency` (`properties/schemas.py:317–348`; `router.py:205–218`).

**Parking (G4):** a stated `parking_fee` is stored `OTHER_MANDATORY/parking`,
MONTHLY, mandatory (`pricing.py:84–87`) and summed (`pricing.py:94–114`):
**`monthly_total_estimate` includes it** — `tests/test_pricing.py:110–115,
118–129, 199–202` and `_assert_summaries_match_rows`. Matches 04a §24 G4 as
written → **no inconsistency, no STOP.** Optional/mandatory input stays BB-4.
Deposit: one-off refundable — outside monthly, inside `move_in_total`.
Utilities included → shown, not added twice. `other_costs` never summed.

### 1.6 Auth and BFF

| Fact | Source |
|---|---|
| `POST /v1/auth/register {email, password 10–128, full_name (optional, default ""), role guest\|host}` → 201 `UserOut`, **no tokens** (no session) | `identity/router.py:60–76`; `identity/schemas.py:8–11` |
| Refresh revokes on use, no grace (BG-5); no logout/revocation (BG-1) | `identity/router.py:79–120` |
| BFF has `/bff/auth/{login,logout,session}`, **no register**; session derives `phoneVerified` from `phone` | `frontend/web/src/app/bff/auth/*` |
| Allowlist has no engagement writes; `viewing-slots` listed `optional` while the backend requires auth | `src/server/bff-routes.ts` |
| Error model: non-GET 503 = `outcome_unknown`; BFF 502/504 on upstream failure; code = `^[A-Z][A-Z0-9_]{2,63}: ` prefix | `src/api/errors.ts` |

### 1.7 Authority (02 §2) — CURRENT BACKEND

Roles: OWNER/ADMIN all scopes; AGENT = EDIT_PROPERTY, PUBLISH_LISTING,
MANAGE_MEDIA, **MANAGE_VIEWINGS, MANAGE_MESSAGES**; mandates 1:1
(`authority.py:77–97`). Engagement routes authorise through `can_act` /
`authorized_property_ids`. **`verified=False` adds no
`PropertyAuthority.verification_state == "VERIFIED"` condition**
(`authority.py:168–203`: the filter is applied only `if verified`), so any
in-force chain to an **unverified** PropertyAuthority currently reads and
writes provider-side messages, requester notes and viewing controls.
Legacy `require_role("host")` remains on property/listing writes
(`properties/router.py:285–762`). `GET /v1/me/classifieds` enumerates by
PUBLISH_LISTING only (`router.py:791–800`).

## 2. Contract findings

| # | Finding | Disposition |
|---|---|---|
| CF-1 | Parking in `monthly_total_estimate` — consistent with G4 | verified; BB-4 stays |
| CF-2 | `viewing-slots` requires auth; the approved guest flow lets a guest inspect/select a slot before auth; BFF marks it `optional` | **OD-6 decided → BP-11** (public derived slots, security review). Not replaced by auth-first. BFF level follows BP-11 |
| CF-3 | Slots untyped, no timezone | BP-2 |
| CF-4 | Most refusals lack stable codes | BP-1 |
| CF-5 | Conversation quota 429 lacks `Retry-After` | in BP-1 |
| CF-6 | `cancel` has no time guard | **BP-7 REQUIRED** for FE-003e |
| CF-7 | Passed REQUESTED stays REQUESTED | **DEBT-1** (future expiry decision); FE shows the derived label only |
| CF-8 | G-14 leaves viewings untouched | **OD-1 = C → BP-6** with BP-5 |
| CF-9 | G-14 does not bar reveal | **OD-2 = YES → BP-8** |
| CF-10 | No provider enumeration by MANAGE_VIEWINGS/MESSAGES | BP-3 |
| CF-11 | Provider DTOs: opaque `requester_user_id` only | **OD-3 → BP-4** |
| CF-12 | Register returns no session; role client-selectable | FE-003a: register → login; never send `role` |
| CF-13 | BFF `phoneVerified` from `phone` | FE-003a uses `phone_verified_at` |
| CF-14 | `verified=False` admits unverified PropertyAuthority to private engagement | **BP-9 security gate + BB-10** |
| CF-15 | Message writes not idempotent | **BP-10 + BB-11** |
| CF-16 | Lists lack listing summary/counterpart/unread/paging | CLIENT COMPOSITION + FUTURE |
| CF-17 **new** | Reporting a message needs a verified e-mail or phone; messaging needs neither → an unverified recipient of harassment can message but cannot report | **OD-7** (§5.2) |
| CF-18 **new** | OD-2 says "new" reveal; the backend answers a **repeat** reveal before any check, so a restricted requester could still re-read a number disclosed before the restriction | **OD-8** (§5.2) |
| CF-19 **new** | Viewings have no generation column: OD-1's "same publication generation" can only mean the requester's viewings of that listing that are future **at the decision instant** | recorded as BP-6 semantics (§4); no schema change needed |
| CF-20 **new** | `full_name` is optional free text, unverified: OD-3's projection can be empty or arbitrary | BP-4 fallback "Użytkownik Homies"; never labelled verified |
| CF-21 **new** | Public derived slots expose occupancy patterns (absence of a slot after a booking) and cost one DB count per candidate | BP-11 security/performance review items |
| CF-22 **new** | Canon has `platform.idempotency_keys` (04 §73; 04a §6 forbids storing sensitive bodies) | BP-10 uses it; stores the message id reference and a request hash, never the message body |

## 3. Scope contract by area

### 3.1 Save

| Item | Class | Contract |
|---|---|---|
| Save / unsave | CURRENT BACKEND → FE-003 | `POST`/`DELETE /bff/v1/me/saved-listings/{id}` (`auth: required`) |
| Saved-state | CLIENT COMPOSITION (G8) | after sign-in page `GET /v1/me/saved-listings?limit=100` once per session (≤ 5 pages), keep the id set in memory, update on confirmed save/unsave; anonymous = "not saved" + AuthInterrupt; never probe by saving |
| Behaviour | FE-003 | **non-optimistic**: pending (`aria-busy`, disabled), pressed state only on 200/201/204; network error → one automatic retry (idempotent) then inline retry; 502/503/504 → re-read the set |
| 404 / 409 cap / 429 | FE-003 | "Ta oferta nie jest już dostępna" / "Masz już 500 zapisanych ofert…" + link / wait `Retry-After` |
| Saved list `/zapisane` (PROPOSED; handoff decides) | FE-003 | AVAILABLE via ListingCard; tombstone "Oferta niedostępna" + `saved_at` + "Usuń", no cached data; paging; empty state |
| Save current search | CLIENT COMPOSITION → FE-003 | FE-002 codec → **API canonical query**; name ≤ 80; 409 duplicate → link from `Location`; 409 cap; 422 |
| Saved searches list | FE-003 | name, alert toggle (`PATCH` + `expected_version`), pause, delete; INVALID shown honestly, never broadened; open via reverse codec or `…/matches` |
| Saved flag on DTO | BACKEND/API GAP (G8, optional) | not required |

### 3.2 Conversations

| Item | Class | Contract |
|---|---|---|
| Start = first non-empty message | CURRENT BACKEND | no "open empty thread" action |
| Max length | CURRENT BACKEND | 4000 after trim; counter from 3600; blank/over-limit blocked; 422 handled |
| One thread per requester × listing | CURRENT BACKEND + CLIENT COMPOSITION | "Napisz" opens the existing ACTIVE tenant thread for the listing (from the inbox); a start that reaches the backend continues it |
| CLOSED / ARCHIVED | CURRENT BACKEND | read-only notice "Homies zamknął tę rozmowę" / "Rozmowa zarchiwizowana"; 409 `CONVERSATION_CLOSED` → same state, draft visible for copying, no retry |
| SYSTEM line | CURRENT BACKEND | code mapped to Polish; unknown code → "Wiadomość systemowa Homies" |
| Redacted | CURRENT BACKEND | "Wiadomość usunięta przez Homies"; no body, no reason |
| RECONTACT_BLOCKED | CURRENT BACKEND | "Nie możesz rozpocząć nowej rozmowy o tej ofercie"; no reason, no retry; viewing and phone CTAs also unavailable (F6, OD-2) |
| Own listing / quotas | BP-1 | `OWN_LISTING` "To Twoja oferta"; `CONVERSATION_QUOTA` daily copy; middleware 429 → `Retry-After` |
| **Send outcome (BP-10)** | BACKEND/API GAP → FE-003 | every start/append carries a client-generated **`client_message_id`** (UUID v4) minted when the user presses send and kept for retries of that same draft. After 502/503/504/timeout the client **retries with the same id**; the server returns the original result (no duplicate). No matching of body/timestamp. Until BP-10 lands the client shows "Nie wiemy, czy wiadomość dotarła — sprawdź rozmowę" and offers a manual re-read; **that interim state is dev/test only and not acceptable for external beta (BB-11)** |
| Hierarchy | FE-003 | inbox (newest first) → thread (listing header, messages oldest→newest, composer); tenant/provider via ContextSwitch |
| Composer states | FE-003 | `idle → typing → sending → sent \| failed(final) \| retrying(same id) \| closed \| blocked`; draft in memory only |
| **Report a message (OD-4)** | CURRENT BACKEND → FE-003c | "Zgłoś wiadomość" on every **other participant's USER** message (not SYSTEM, not own, not REMOVED): reason (6 codes, Polish labels) + optional text ≤ 2000 (≥ 20 for OTHER per backend); 201/200 → "Zgłoszenie przyjęte" (no decision shown, L13); 403 → verification step (OD-7); 404/409 → neutral "Nie można zgłosić tej wiadomości"; 429 quota |
| Auth interruption | CLIENT COMPOSITION | §3.7; draft never persisted, never auto-sent |
| Provider authority | CURRENT BACKEND + **BP-9** | provider side only where the user holds MANAGE_MESSAGES; external beta requires the BP-9 verification rule |
| `can_send` / `closed_by` | BACKEND/API GAP (optional) | not assumed |
| Real-time / unread / paging | FUTURE | refresh on focus/visibility |
| Viewing ↔ conversation | **forbidden** | neither creates the other |

### 3.3 Viewings

**State machine (CURRENT BACKEND + decided changes) and UI binding:**

| From | Event | Actor | To | UI (requester) | UI (provider) |
|---|---|---|---|---|---|
| — | request, REQUEST_APPROVAL | requester | REQUESTED | "Prośba wysłana — czeka na potwierdzenie" | Confirm / Decline / Cancel |
| — | request, INSTANT_BOOKING | requester | CONFIRMED | "Oglądanie potwierdzone" | "Potwierdzone" |
| REQUESTED | confirm (future, capacity, not held) | provider | CONFIRMED | "Potwierdzone" | — |
| REQUESTED | decline | provider | DECLINED | "Właściciel nie przyjął tego terminu" + "Wybierz inny termin" | — |
| REQUESTED / CONFIRMED, **before start** | cancel | either | CANCELLED | "Oglądanie odwołane" (no actor, §3.10) | same |
| REQUESTED / CONFIRMED, **after start** | cancel | either | **refused (BP-7, `VIEWING_STARTED`)** | no cancel action | no cancel action |
| REQUESTED / CONFIRMED (future) | close_engagement | Homies | CANCELLED | "Oglądanie odwołane" | same |
| REQUESTED / CONFIRMED (future at decision) | **G-14 restriction (OD-1, BP-6)** | Homies | CANCELLED | "Oglądanie odwołane" | same |
| CONFIRMED (after start) | outcome | provider | COMPLETED / NO_SHOW | "Odbyło się" / "Oznaczone jako nieodbyte" | recorded |
| REQUESTED (start passed) | none (DEBT-1) | — | REQUESTED | **display-only** "Bez odpowiedzi — termin minął"; no actions | same; no Confirm |

The derived label never changes the stored state and is never sent anywhere
as DECLINED/CANCELLED. DECLINED/CANCELLED semantics are not invented.

| Item | Class | Contract |
|---|---|---|
| Derived availability | CURRENT BACKEND | the client renders `viewing-slots` only; `ViewingSlot` is a UI representation of one derived instant, **not a domain entity** |
| **Guest slot inspection (OD-6)** | **BP-11** | per the approved guest-conversion flow a guest may open the slot picker and select a slot **before** auth; request stays auth-required. FE-003e's guest path depends on BP-11; the contract does **not** substitute auth-first. Until BP-11, FE-003e is not implementable for guests |
| Time display | BP-2 | the response timezone; no hard-coded zone |
| No settings / no free terms | CURRENT BACKEND | "Właściciel nie udostępnia jeszcze terminów oglądania" + message CTA / "Brak wolnych terminów w najbliższych 14 dniach" + "Pokaż kolejne dni" (≤ 31) |
| Request | FE-003 | slot → confirm sheet (date/time, duration, attendees 1–10, optional note ≤ 1000 with a privacy hint) → `POST …/viewings` with the exact `starts_at` received; for a guest: AuthInterrupt → resume with the selected instant re-validated against fresh slots |
| INSTANT vs APPROVAL | CURRENT BACKEND | the result state comes from the response, never predicted |
| 409 not offered / full | BP-1 | re-fetch slots, sheet stays, "Ten termin właśnie się zajął — wybierz inny"; focus to the status |
| 409 already booked | BP-1 | "Masz już umówione oglądanie tego mieszkania" + link |
| 409 RECONTACT_BLOCKED | CURRENT BACKEND | "Nie możesz umówić oglądania tej oferty"; no reason, no retry |
| 404 | CURRENT BACKEND | "Ta oferta nie jest już dostępna" |
| LISTING_HELD | CURRENT BACKEND | provider: "Oferta jest sprawdzana przez Homies — potwierdzanie wstrzymane" |
| Unknown outcome on request | FE-003 | re-read `GET /v1/me/viewings`; the one-future-viewing rule (409 already booked) prevents duplicates server-side |
| Cancel | FE-003 + **BP-7** | offered only before `starts_at`; the backend enforces it; `VIEWING_STARTED` → re-read and render |
| My viewings `/ogledziny` (PROPOSED) | CLIENT COMPOSITION | `GET /v1/me/viewings` + per-row listing GET (404 → "Oferta niedostępna", viewing still shown) |
| Address / meeting point | not in FE-003 | §3.8 |

### 3.4 Pricing binding (CostSignature)

| Rule | Contract |
|---|---|
| Authoritative fields | `rent_amount, admin_fee, utilities_amount, utilities_basis, parking_fee, deposit_amount, other_costs, monthly_total_estimate, move_in_total, currency` from `ClassifiedOut` only |
| No recomputation | totals never computed/adjusted; parity test with non-additive fixture |
| Breakdown | structured fields only (FE-002 CostBreakdown, DESIGN-001 §5.5) |
| `other_costs` | verbatim, "Opis właściciela — nie wliczone w sumy"; never parsed |
| Deposit | outside monthly; inside "Na start" ("pierwszy miesiąc + kaucja") |
| Utilities | INCLUDED "w cenie najmu" (not added); ESTIMATED "ok. X zł (szacunkowo)"; NOT_STATED "nie podano", total "od X zł + media" |
| Parking (G4 exactly) | `parking_fee > 0` → row inside the monthly total as stored; never labelled optional, no exclude toggle, never subtracted; input gap = BB-4 |
| Surfaces | EngagementRail, MobileActionDock, thread/viewing listing header — FE-002 formatter |

### 3.5 Contact reveal

| Item | Class | Contract |
|---|---|---|
| CTA presence | CURRENT BACKEND | only for `contact_mode == "phone"` |
| Verified-phone gate | CURRENT BACKEND + BP-1 | unverified (`phone_verified_at`) → verification step, then a deliberate second press; endpoint 403 `PHONE_NOT_VERIFIED` → same step (never confused with a BFF CSRF 403) |
| **G-14 (OD-2)** | **BP-8** | a restricted requester gets 409 `RECONTACT_BLOCKED` for a **new** reveal on that listing for the same publication generation; UI "Nie możesz zobaczyć numeru do tej oferty", no retry; repeat-reveal handling per OD-8 |
| Messages-only | BP-1 `MESSAGES_ONLY` | "Ten właściciel przyjmuje tylko wiadomości" + message CTA |
| Quota | CURRENT BACKEND | "Pozostało dziś: N z 20"; 429 → countdown from `Retry-After`; repeat reveal never blocked by the UI |
| Display | FE-003 | text + `tel:` link; never in storage, analytics, URL, logs; cleared on navigation |
| Independence | CURRENT BACKEND | reveal ≠ conversation ≠ viewing |
| SMS provider | **BB-7** | dev channel only until then |

### 3.6 Supply-side surfaces

See §3.9 and §6.9–§6.10.

### 3.7 Auth interruption (CLIENT COMPOSITION)

```
pending action (save | message | viewing | reveal | save_search | report)
  → AuthInterrupt dialog (in page)
  → login  OR  register → login          (register returns no session)
  → session established = GET /bff/auth/session → {authenticated: true}
  → saved-id set loaded when needed
  → pending action resumed
```

| Rule | Contract |
|---|---|
| Intent record | `{action, listing_id, starts_at?, search_query?, message_id?, initiator_id, created_at}` in memory; mirrored to `sessionStorage` without free text; expires after 30 min |
| Resume | **save** automatic; **message** composer reopened with the in-memory draft, user sends; **viewing** fresh slots, the selected instant kept only if still offered, user confirms; **reveal** user presses again; **save_search** dialog reopened; **report** report dialog reopened |
| Register | new `/bff/auth/register` forwards `{email, password, full_name}` — **never `role`** — then logs in; 409 → switch to login with the e-mail kept |
| Failure | 401 generic; 429 countdown; 502/503 retry; user closes → intent discarded, focus to initiator, `auth_resumed: abandoned` |
| Session expiry | 401 on a write after the BFF refresh failed → AuthInterrupt with the same intent |
| Not hidden | BG-1/BG-5 not mitigated by composition; beta blocked (BB-1/BB-2); 120 s rotation memory not extended |
| Accessibility | WCAG 3.3.8; focus §9.3 |

### 3.8 G9 — exact address / meeting point

Not implemented in FE-003 (no participant-only delivery model, 04a §24). No
address, street, building, coordinates or meeting instructions anywhere —
including CONFIRMED viewings, threads, analytics, URLs, logs, `aria` text. A
CONFIRMED viewing shows date/time only; copy does not promise Homies will
deliver an address. **BB-3.**

### 3.9 Supply-side authorization

| Capability | Authority | Route | Status |
|---|---|---|---|
| Provider conversations, notes on leads | MANAGE_MESSAGES | `/v1/conversations…` | CURRENT BACKEND (authority model) — **verification requirement = BP-9** |
| Assign / stage | MANAGE_MESSAGES | `…/assign`, `…/stage` | CURRENT BACKEND; UI optional in FE-003f |
| Provider viewings (list, confirm, decline, cancel, outcome) | MANAGE_VIEWINGS | `/v1/classifieds/{id}/viewings`, `/v1/viewings/{id}/…` | CURRENT BACKEND (authority model) — **BP-9** |
| Requester display | server projection (OD-3) | provider DTOs | **BP-4** |
| Enumerate provider listings by scope | — | — | **BP-3** |
| Settings/windows editor | MANAGE_VIEWINGS | `PUT/POST …` | FUTURE |
| Property/listing writes | legacy `host` | `properties/router.py` | **BB-6** |

Rules: provider context only from authority-backed data (`my_side=provider`
rows or non-empty `GET /v1/me/classifieds`), **never** `user.role`; no role
choice at registration; `host` is not the product model. **BP-9 (security
gate):** before provider-side external beta, the canonical verification
requirement for MANAGE_MESSAGES / MANAGE_VIEWINGS private reads and writes is
decided and enforced; **recommended rule: private engagement access requires a
VERIFIED PropertyAuthority** in the chain. FE-003 does not assume an
unverified authority may see requester messages, notes or identity merely
because current routes allow it.

### 3.10 Cancellation attribution

Every CANCELLED viewing shows **"Oglądanie odwołane"** with no actor until an
explicit immutable cancellation source is in the API (**BP-5 / BB-5**).
`cancelled_by_homies` is not displayed as attribution. Notices
(`MODERATION_VIEWING_CANCELLED`, and the new OD-1 notices) live in
`/v1/me/inbox`; a notification-centre UI is FUTURE.

## 4. G-14 existing-viewing decision — **DECIDED: C** (D-104)

**Decision.** A later G-14 restriction (`FEATURE_RESTRICTED` on a
conversation) **cancels** that requester's **future** REQUESTED and CONFIRMED
viewings of the **same listing** for the restricted publication generation.

**Requirements (BP-6, together with BP-5):**

* atomic with the restriction — same transaction as the decision, lock order
  listing → conversation → viewings (as close_engagement);
* scope = viewings with `requester_user_id` = the conversation's requester,
  `listing_id` = the conversation's listing, status REQUESTED/CONFIRMED,
  `starts_at` > the decision's database instant. Viewings have no generation
  column; at the decision instant every such viewing belongs to the
  restricted generation (CF-19);
* terminal and past viewings untouched;
* `ViewingCancelled(cancelled_by = HOMIES, moderation_decision_id)` and the
  **explicit immutable cancellation source** written on the viewing (BP-5);
* neutral notices to the requester (ids + instant, as
  `MODERATION_VIEWING_CANCELLED`) and to the provider (ids + instant, no
  reason, no allegation);
* tests SQLite + PG: restriction ↔ concurrent confirm / request / cancel;
  a viewing starting exactly at the instant is not cancelled; other
  requesters' viewings untouched; republish (new generation) allows a new
  request (F6).

**FE impact:** none beyond "Oglądanie odwołane" and the absent actions.
FE-003e/f depend on BP-6 + BP-5 being on `main`.

## 5. Decisions

### 5.1 Founder decisions (D-104, final)

| # | Decision | Contract effect |
|---|---|---|
| OD-1 | **C** — cancel future REQUESTED/CONFIRMED viewings of the restricted requester + listing, atomically, neutral notices, with immutable cancellation source | §4; BP-6, BP-5 |
| OD-2 | **YES** — G-14 blocks new contact reveal for the same publication generation, stable `RECONTACT_BLOCKED` | §3.5; BP-8 |
| OD-3 | Provider receives a **server-projected first name + surname initial** only; no e-mail/phone; never described as verified without a separate verified identity fact | BP-4; §6.10 |
| OD-4 | **YES** — "Zgłoś wiadomość" in FE-003c on the existing reporting backend | §3.2; §6.7 |
| OD-5 | **YES** — 1C visual/token rollout = separate **FE-VIS-001**; FE-003 consumes semantic tokens only | §7 |
| OD-6 | **CHANGE** — public PUBLIC listings may expose **only the derived offered slots**; settings/windows/blackouts stay private; viewing request stays auth-required; the public read is rate-limited; public-listing privacy boundary and no exact address retained. Canon does not forbid it (checked: 04 §57–§60, §113–§115; 04a §14, §16, §24; 02 §2) | BP-11 (security review) |

### 5.2 Still open (raised by this pass)

| # | Question | Recommendation | Blocks |
|---|---|---|---|
| OD-7 | Message reporting needs a verified e-mail or phone (CF-17), messaging needs neither | Keep the gate (anti-abuse of the report queue) but make e-mail verification reachable inline in the report dialog; revisit if beta data shows harassment reports abandoned at the gate | FE-003c copy/flow |
| OD-8 | OD-2 covers "new" reveals; the backend serves a **repeat** reveal before any check (CF-18) | Refuse **repeat** reveals too for the restricted requester (same code): the number may have changed since, and the restriction should stop Homies acting as the channel | BP-8 scope |
| DEBT-1 | Passed REQUESTED viewings never expire (CF-7) | Future product/backend decision on explicit expiry semantics (e.g. an `EXPIRED` state or a derived metric rule) so analytics and provider-performance metrics do not keep stale REQUESTED; FE shows the derived label only | none for FE-003; metrics debt |
| BP-9 rule | Verification requirement for private engagement (CF-14) | VERIFIED PropertyAuthority required | provider-side beta (BB-10) |

## 6. Component inventory (FE-003 IMPLEMENTATION)

Common: Polish strings (`i18n/pl.ts`, EN/UK keys reserved); errors via
`api/errors.ts`; one exhaustive code→copy table (§9.2); never colour-only;
targets ≥ 44 px; focus not obscured (`scroll-padding`); analytics only through
the consent gate; **semantic tokens only** (OD-5); rail ≥ 1024 px, dock
< 1024 px.

### 6.1 SaveButton

| Aspect | Contract |
|---|---|
| Purpose | Save / unsave one listing |
| Route | results cards, map card, detail (rail + dock), saved list |
| Data | saved-id set (composition); listing id |
| API/BFF | `POST`/`DELETE /bff/v1/me/saved-listings/{id}`; `GET /bff/v1/me/saved-listings` |
| I/O | `listingId`, `initialSaved`, `variant` → set-store update |
| Loading | `aria-busy`, disabled, spinner inside the target |
| Empty | n/a |
| Error | 404 / 409 cap / 429 / network retry; polite live region |
| Auth | anonymous → AuthInterrupt(`save`) → automatic resume |
| A11y | `<button aria-pressed>`, name "Zapisz: {title}" |
| Responsive | icon on cards, labelled in rail/dock |
| Analytics | `save_toggled` |
| Tests | unit, component, BFF allowlist, E2E save → list → unsave, tombstone, axe |
| Acceptance | AC-S1…S6 |

### 6.2 EngagementRail (≥ 1024)

| Aspect | Contract |
|---|---|
| Purpose | Sticky price summary + engagement actions on detail |
| Route | `/oferta/[id]` |
| Data | `ClassifiedOut`, session, saved set, own active thread, own future viewing (composed) |
| API/BFF | hosts SaveButton, message, viewing, reveal CTAs |
| I/O | opens composer / slot picker / reveal step |
| Loading | price server-rendered; actions skeleton; CLS ≤ 0.1 |
| Empty | actions of unshipped slices absent (no dead buttons) |
| Error | summary failure → actions usable, hints omitted |
| Auth | CTAs open AuthInterrupt with intent (viewing: slot picker first, per OD-6/BP-11) |
| A11y | `complementary` "Koszty i kontakt"; order price → save → message → viewing → phone |
| Responsive | hidden < 1024 |
| Analytics | none own |
| Tests | component (presence by `contact_mode`, slice flags, session), visual regression, axe |
| Acceptance | AC-R1…R4 |

### 6.3 MobileActionDock (< 1024)

| Aspect | Contract |
|---|---|
| Purpose | Bottom bar: monthly total + primary action + save |
| Route | `/oferta/[id]` |
| Data | `monthly_total_estimate`, `utilities_basis`, engagement summary |
| API/BFF | none own |
| I/O | primary = viewing when FE-003e shipped, else message; sheet for the rest |
| Loading/empty/error/auth | as EngagementRail |
| A11y | `region` "Akcje oferty"; safe-area inset; page padding keeps focus visible (2.4.11); sheet = dialog rules |
| Responsive | < 1024 only; hidden with the keyboard open |
| Analytics | none own |
| Tests | Playwright mobile overlap/focus, axe |
| Acceptance | AC-D1…D3 |

### 6.4 ViewingSlot

| Aspect | Contract |
|---|---|
| Purpose | Render one **derived** offered instant, grouped by local day; select one |
| Route | slot picker (detail), "Wybierz inny termin" |
| Data | typed `viewing-slots` (BP-2: instants, duration, timezone) |
| API/BFF | `GET /bff/v1/classifieds/{id}/viewing-slots` — `auth: optional` **after BP-11** (guest allowed), else `required` |
| I/O | → selected `starts_at` (exact string) |
| Loading | skeleton day groups, stable height |
| Empty | no settings / no free terms |
| Error | 404; 429 (public rate limit) countdown; 503 retry |
| Auth | guest may inspect/select (BP-11); request needs auth |
| A11y | `radiogroup` per day, radios "10:00–10:30", arrow keys, selection not colour-only |
| Responsive | day tabs + list on mobile; grid ≥ 1024 |
| Analytics | `viewing_slot_selected` |
| Tests | unit (DST grouping in response tz), component, E2E guest select → auth → request, axe |
| Acceptance | AC-V1…V4 |

### 6.5 ViewingState

| Aspect | Contract |
|---|---|
| Purpose | One viewing's state + currently allowed actions |
| Route | detail hint, `/ogledziny`, provider variant |
| Data | `ViewingOut` |
| API/BFF | `POST /bff/v1/viewings/{id}/cancel` |
| I/O | viewing + now → label + actions (§3.3) |
| Loading | action pending; re-read after 409 |
| Empty | "Nie masz umówionych oglądań" |
| Error | `VIEWING_STARTED` / state conflict → re-read; 404 → removed with status |
| Auth | signed-in |
| A11y | text + icon; `<time datetime>`; confirm dialog for cancel |
| Responsive | card / row |
| Analytics | `viewing_cancel_submitted` |
| Tests | unit matrix 6 states × before/after start; E2E request → confirm → cancel; refused after start; passed REQUESTED label |
| Acceptance | AC-V5…V9 |

### 6.6 ConversationComposer

| Aspect | Contract |
|---|---|
| Purpose | First message (creates the thread) or the next |
| Route | detail sheet, `/wiadomosci/[id]` (PROPOSED) |
| Data | thread status, `my_side` |
| API/BFF | start / append routes with `client_message_id` (BP-10) |
| I/O | text ≤ 4000 + `client_message_id` → `MessageOut` |
| Loading | `sending`: read-only, `aria-busy` |
| Empty | send disabled when blank |
| Error | §3.2; outcome unknown → retry with the same id |
| Auth | AuthInterrupt(`message`), draft in memory only |
| A11y | labelled textarea; polite counter near limit; Enter newline, Ctrl/Cmd+Enter send; errors via `aria-describedby` |
| Responsive | above the keyboard (`visualViewport`); dock hidden |
| Analytics | `conversation_start_submitted`, `message_send_submitted` (outcome only) |
| Tests | unit state machine incl. same-id retry; component; E2E start/continue/closed/blocked; BP-10 dedupe E2E (drop the first response) |
| Acceptance | AC-C1…C8 |

### 6.7 ConversationItem (+ MessageItem)

| Aspect | Contract |
|---|---|
| Purpose | Inbox row; message in a thread with "Zgłoś wiadomość" (OD-4) |
| Route | `/wiadomosci` (PROPOSED), thread |
| Data | `ConversationOut` / `ProviderConversationOut`; listing GET (composition); `MessageOut` |
| API/BFF | `GET /bff/v1/conversations[/{id}]`, listing GET, `POST /bff/v1/reports` |
| I/O | row: title or "Oferta niedostępna", district, `last_message_at`, status; message: side, body/REMOVED/SYSTEM, time, report action |
| Loading | skeletons; lazy titles |
| Empty | "Nie masz jeszcze wiadomości" + search link |
| Error | list retry; per-row 404 tombstone; report errors per §3.2 |
| Auth | signed-in; report 403 → verification step (OD-7) |
| A11y | list of links; `role="log"` without re-announcing history; report = menu button → dialog |
| Responsive | list → thread on mobile; split ≥ 1024 |
| Analytics | `message_report_submitted` (reason code, outcome) |
| Tests | component (REMOVED, SYSTEM, unknown SYSTEM, CLOSED, ARCHIVED, provider fields hidden for tenant, report shown only on other side's USER messages); E2E report → 201, repeat → 200 |
| Acceptance | AC-C9…C13 |

### 6.8 AuthInterrupt

| Aspect | Contract |
|---|---|
| Purpose | Sign in / register without losing the pending action |
| Route | dialog; fallback `/logowanie`, `/rejestracja` (PROPOSED) |
| Data | `/bff/auth/session` |
| API/BFF | `/bff/auth/login`, **new** `/bff/auth/register` (CSRF, 4 KB, no `role`, login chained), `/bff/auth/session` |
| I/O | intent → `resumed \| abandoned \| failed` |
| Loading | submit pending |
| Error | 401 generic; 409 e-mail exists; 422 password ≥ 10; 429; 502 |
| A11y | modal, background `inert`, **e-mail focused on open**, Esc closes, focus per §9.3; 3.3.8 |
| Responsive | full-screen sheet < 1024 |
| Analytics | `auth_interrupted`, `auth_resumed`; `signup_started` on the register tab |
| Tests | unit (intent store, expiry, no free text persisted); BFF register; E2E each intent; focus |
| Acceptance | AC-A1…A8 |

### 6.9 ContextSwitch

| Aspect | Contract |
|---|---|
| Purpose | "Szukam" ↔ "Wynajmuję" for inbox/viewings |
| Route | `/wiadomosci`, `/ogledziny` |
| Data | `my_side=provider` rows; non-empty `GET /v1/me/classifieds`; BP-3 enumeration — never `role` |
| API/BFF | conversations; `GET /bff/v1/me/classifieds` (allowlist, required) |
| I/O | context in URL (`?widok=wynajmujacy`), default tenant |
| Loading / empty / error | hidden until data proves provider context; failure → tenant view still works |
| Auth | signed-in |
| A11y | tablist / segmented radio |
| Responsive | full-width segmented control |
| Analytics | none |
| Tests | shown for AGENT member/mandate holder, hidden for `host` without authority, shown for `guest` with authority; after BP-9, hidden/limited for unverified authority |
| Acceptance | AC-P1…P2 |

### 6.10 ProviderViewingRow

| Aspect | Contract |
|---|---|
| Purpose | One viewing of a managed listing with provider actions |
| Route | provider context of `/ogledziny`, by listing |
| Data | `ProviderViewingOut` + **requester display "Imię N."** (BP-4, OD-3; fallback "Użytkownik Homies"; no e-mail/phone; never "zweryfikowany") |
| API/BFF | `GET /bff/v1/classifieds/{id}/viewings`; `POST /bff/v1/viewings/{id}/{confirm,decline,cancel,outcome}` |
| I/O | REQUESTED & future → Confirm/Decline/Cancel; CONFIRMED & future → Cancel; CONFIRMED & started → Odbyło się / Nie przyszedł; else none |
| Loading | per-action pending |
| Empty | "Brak próśb o oglądanie" |
| Error | `LISTING_HELD`; `SLOT_FULL` / `VIEWING_TIME_PASSED` / `VIEWING_STARTED` / `VIEWING_CHANGED` → re-read; 404 → authority lost, row removed |
| Auth | MANAGE_VIEWINGS (+ BP-9 rule), backend-enforced |
| A11y | `requester_note` plain text; action names include the date |
| Responsive | card on mobile |
| Analytics | none client-side (server facts) |
| Tests | action matrix; E2E confirm/decline/outcome/held; display projection never shows e-mail/phone |
| Acceptance | AC-P3…P6 |

## 7. DESIGN-001C split (OD-5)

| **FE-003** | **FE-VIS-001** (separate task) |
|---|---|
| The ten components of §6 on **semantic tokens only** | 1C token layer (district colour identity, type, radii, elevation) replacing Design System v1 values |
| Detail engagement area, slot picker, inbox/thread, my viewings, saved list, auth dialog, report dialog | Restyle of FE-002 surfaces: home, SearchBox, results, ListingCard, filters, map pills/cards, header/footer, 404 |
| Copy keys for every engagement state | District-colour mapping (never quality/trust/status, D-103) |
| Focus/keyboard rules (§9.3) | Design file maintenance, mobile frames |

Artboard-level assignment is part of the P-0 handoff.

## 8. Analytics — event requirements only

Ingestion stays **off** (G-12; BB-8). Catalogue additions to EVENTS-v1,
emitted through the consent gate to the existing sinks. Server facts are the
source of truth for outcomes.

| Need | Event / source | Safe dimensions | Forbidden |
|---|---|---|---|
| listing exposure | `search_results_viewed`, `listing_viewed` (existing) | search_id, position | — |
| save | `save_toggled` + table | listing_id, action, outcome, surface | — |
| conversation initiation | `conversation_start_submitted` + table | listing_id, outcome | text, length |
| message sent | `message_send_submitted` + table | outcome, side, retried (bool) | text, length, `client_message_id` |
| message report | `message_report_submitted` + `reports` | reason code, outcome | text, message id |
| slot selected | `viewing_slot_selected` | listing_id, days-ahead bucket, hour bucket, authenticated (bool) | exact instant |
| viewing requested | `viewing_request_submitted` + `ViewingRequested` | listing_id, outcome, attendees bucket | note |
| confirmed/declined/cancelled/outcome | `ViewingResponded`, `ViewingCancelled`, `ViewingOutcomeRecorded` (server) | EVENTS-v1 §2 | — |
| contact reveal | `contact_reveal_submitted` + `contact_reveals` | listing_id, outcome, quota bucket | phone |
| auth interruption / resume | `auth_interrupted`, `auth_resumed` (+ `signup_started`) | intent, outcome | e-mail |
| RECONTACT_BLOCKED | `engagement_refused` | surface (conversation/viewing/reveal), code | reason, decision id |
| API conflict/error | `engagement_api_error` | route template, status, code or `none`, kind | `detail`, body |

Closed catalogue; `schema_version` 1; no client `user_id`; route templates
only; payloads pinned by tests. Attributed acquisition is never causal; lift
claims need an EXPERIMENTS-v1 randomised test.

## 9. Testing contract

### 9.1 Matrix

| Layer | a auth | b save | c conversation | d reveal | e viewing | f provider |
|---|---|---|---|---|---|---|
| Unit | intent store/resume/expiry | saved set | composer machine, same-id retry | gate step, quota | DST grouping, label/action matrix | action matrix |
| Integration (mocked BFF) | dialog ↔ session | button ↔ set | thread ↔ inbox ↔ report | verify → reveal | guest picker → auth → request | rows ↔ actions |
| API contract | regenerated types; register has no tokens | saved schemas | BP-1 codes, BP-10 field | BP-1/BP-8 | BP-2, BP-7, BP-11 | BP-3, BP-4 |
| BFF | register route; allowlist + auth levels | allowlist | allowlist incl. `/reports` | allowlist | `viewing-slots` level per BP-11 | `/me/classifieds` |
| Component | AuthInterrupt | SaveButton | Composer, ConversationItem, report dialog | reveal CTA | ViewingSlot, ViewingState | ContextSwitch, ProviderViewingRow |
| Responsive (desktop + mobile) | sheet | card/rail/dock | split | dock sheet | picker | rows |
| A11y (axe) | yes | yes | yes | yes | yes | yes |
| Keyboard/focus | §9.3 | toggle | Ctrl+Enter, log, report menu | step | radios | buttons |
| E2E (seeded) | each intent resumes | save/unsave/tombstone/limit | start, continue, closed, blocked, redacted, report, dedupe on dropped response | verified/unverified/messages-only/quota/blocked | guest select, instant, approval, conflict, booked, blocked, held, cancel refused after start, G-14 cancellation | confirm/decline/cancel/outcome/held, name projection |
| Parity | no `role`; phone from `phone_verified_at` | no save-probing | 4000 = backend; codes table | quota from API | slots exact; totals never recomputed | context never from `role` |

**Backend tests** accompany each BP (SQLite + PG where locks matter): BP-6
races (restriction ↔ confirm/request/cancel); BP-7 refusal at/after start;
BP-8 new and repeat reveal (per OD-8) refused, other users unaffected,
republish lifts; BP-9 unverified authority refused on every private
engagement read/write, verified allowed, mandate/membership chains covered;
BP-10 same id → one row, same response; same id + different body → 409
(`IDEMPOTENCY_KEY_REUSED`); concurrent duplicates → one row; key expiry;
no message body in the idempotency record (04a §6); BP-11 anonymous gets
derived instants only (response schema has no settings/window/blackout or
capacity fields), rate limit enforced, not-public → 404, days cap for
anonymous.

`seed_e2e.py` gains: two listings with viewing settings (INSTANT, APPROVAL), a
phone-mode listing, a verified-phone seeker, a held listing, a closed
conversation, a redacted message, a G-14-restricted requester, an unverified
authority holder (BP-9), all fictional, under the existing opt-ins.

### 9.2 Parity tests

1. Backend refusal codes (generated JSON) = frontend copy table.
2. Non-additive price fixture → API totals shown.
3. Limits (4000, 1000, 1–10, 80, 2000) read from OpenAPI.
4. UI offers exactly the returned instants.
5. Privacy: no address, phone (outside the reveal element), message text,
   note or `client_message_id` in analytics, URLs or storage.
6. Authority: provider surfaces follow authority fixtures, not `role`.

### 9.3 Focus requirements (DESIGN-001C)

* Filter dialog receives focus on open; focus returns to the opener on close.
* Auth dialog focuses the **e-mail** field on open.
* After an auth interruption, focus returns to the **initiating action**; if
  it no longer exists, to the **result status** message.
* Every dialog/sheet traps focus, Esc closes, background `inert`.

## 10. Prerequisites, blockers, slices

### 10.1 Backend prerequisites (separate bounded tasks)

| # | Change | Risk | Needed by |
|---|---|---|---|
| BP-1 | Stable codes: `OWN_LISTING`, `VIEWINGS_NOT_OFFERED`, `SLOT_NOT_OFFERED`, `SLOT_FULL`, `VIEWING_ALREADY_BOOKED`, `VIEWING_STATE_CONFLICT`, `VIEWING_CHANGED`, `VIEWING_TIME_PASSED`, `VIEWING_NOT_STARTED`, `MESSAGES_ONLY`, `PHONE_NOT_VERIFIED`, `REVEAL_QUOTA`, `CONVERSATION_QUOTA` (+ `Retry-After`), `SAVED_LIMIT`, `SAVED_SEARCH_DUPLICATE`, `SAVED_SEARCH_LIMIT` (names proposed), in OpenAPI | R1 | c, d, e |
| BP-2 | Typed `viewing-slots` response incl. `timezone` | R1 | e |
| BP-3 | Provider listing enumeration by MANAGE_VIEWINGS / MANAGE_MESSAGES | R1 | f |
| BP-4 | Requester display projection "first name + surname initial" on provider DTOs (OD-3; fallback; no verified label) | R1 | f |
| BP-5 | Explicit immutable viewing cancellation source REQUESTER / PROVIDER / HOMIES (schema EXPAND) | R2 | e, f, BP-6 |
| BP-6 | OD-1 C: atomic cancellation of future viewings on G-14 restriction (§4) | R2 | e, f |
| BP-7 | **REQUIRED**: backend refuses cancel at/after `starts_at` (`VIEWING_STARTED`) for both sides | R1 | e |
| BP-8 | OD-2: G-14 bars contact reveal (`RECONTACT_BLOCKED`), new + repeat per OD-8 | R1 | d |
| BP-9 | **Security gate**: canonical verification rule for private engagement (MANAGE_MESSAGES / MANAGE_VIEWINGS reads and writes, inbox, notes, requester identity, viewing control) decided and enforced; recommended VERIFIED PropertyAuthority | R2 + security review | f; any provider-side beta (BB-10) |
| BP-10 | Idempotent start-with-first-message and append: `client_message_id` (UUID) with server-side dedup on `platform.idempotency_keys` (04 §73) or an equivalent unique key; response reconstructed from the stored message id, no body stored (04a §6); reuse with a different body → 409 | R2 | c (external beta: BB-11) |
| BP-11 | OD-6: anonymous read of **derived** slots for PUBLIC listings only; no settings/windows/blackouts/capacity in the response; request stays auth-required; dedicated public rate limit and anonymous `days` cap; same §18 visibility rule; security + performance review (CF-21) | R2 + security review | e (guest path) |
| optional | G8 saved flag; `can_send` / `closed_by` | — | — |

### 10.2 Beta blockers

| # | Blocker |
|---|---|
| BB-1 | BG-1 logout / refresh revocation |
| BB-2 | BG-5 refresh reuse/grace |
| BB-3 | G9 participant-only address/meeting delivery |
| BB-4 | G4 mandatory/optional parking input |
| BB-5 | explicit immutable viewing cancellation source (BP-5) |
| BB-6 | authority-correct supply routes (legacy `host` gate) |
| BB-7 | production SMS provider |
| BB-8 | first-party analytics ingestion legal gate |
| BB-9 | OD-1 implemented (BP-6) before viewings reach external users |
| BB-10 | **security**: private-engagement authority verification (BP-9) before provider-side external beta |
| BB-11 | idempotent conversation/message writes (BP-10) before FE-003c reaches external users |

### 10.3 Slices and dependencies

| Slice | Content | Entry criteria (implementation) | Extra for external beta |
|---|---|---|---|
| **FE-003a** | `/bff/auth/register`, AuthInterrupt, intent store, `phoneVerified` fix, fallback pages | final approval; P-0 | BB-1, BB-2 |
| **FE-003b** | SaveButton, saved list, saved searches; rail/dock skeleton (Save only) | a | as a |
| **FE-003c** | Composer, inbox, thread, ConversationItem, **Zgłoś wiadomość**, message CTA | a; BP-1; BP-10; OD-7 answered | BB-11, BB-10 for the provider side of threads |
| **FE-003d** | reveal CTA, phone verification step, quota | a; BP-1; BP-8 (OD-8 answered) | BB-7 |
| **FE-003e** | ViewingSlot (guest path), request sheet, ViewingState, my viewings | a; BP-1; BP-2; BP-5; BP-6; **BP-7**; **BP-11** | BB-3 awareness (no address), BB-5, BB-9 |
| **FE-003f** | ContextSwitch, provider inbox view, ProviderViewingRow | c, e; BP-3; BP-4; BP-5; **BP-9** | BB-6, BB-10 |

Recommended backend order: BP-1, BP-2, BP-7 (small, R1) → BP-10, BP-5 + BP-6,
BP-8 → BP-11, BP-9 (security review) → BP-3, BP-4. No slice reaches external
users while a blocker of its column is open.

## 11. Acceptance criteria

**Global:** AC-G1 no address/street/coordinate/meeting point anywhere.
AC-G2 no client-computed totals. AC-G3 every refusal mapped to Polish; no raw
`detail`. AC-G4 no dead buttons. AC-G5 every new route allowlisted at the
backend's auth level; nothing else proxied. AC-G6 analytics silent without
consent; payloads pinned. AC-G7 axe zero violations on new surfaces (desktop,
mobile). AC-G8 `role` never sent or used for product decisions. AC-G9
semantic tokens only (no 1C values in FE-003 code).

**Auth (a):** AC-A1 each intent resumes per §3.7. AC-A2 register → login →
session in one user step; no tokens in the browser. AC-A3 409 → login with the
e-mail kept. AC-A4 no draft/note/phone/report text in storage. AC-A5 e-mail
focused; focus return per §9.3. AC-A6 401 on a write reopens AuthInterrupt.
AC-A7 intent expires after 30 min. AC-A8 abandoned → intent discarded.

**Save (b):** AC-S1 state changes only on 200/201/204. AC-S2 state consistent
across surfaces after reload. AC-S3 tombstone shows no listing data. AC-S4
404/409/429 states. AC-S5 saved search = API canonical query; duplicate links
to existing. AC-S6 INVALID shown, not broadened.

**Rail/dock:** AC-R1 rail ≥ 1024, dock < 1024, never both. AC-R2 phone CTA
only for `contact_mode=phone`. AC-R3 existing thread/viewing shown instead of a
new start. AC-R4 price summary = FE-002 values. AC-D1 dock never covers focus.
AC-D2 hidden with the keyboard. AC-D3 sheet follows dialog rules.

**Conversation (c):** AC-C1 thread starts only with a non-blank message. AC-C2
4000 limit enforced and counted. AC-C3 writing again continues the thread.
AC-C4 CLOSED/ARCHIVED read-only with notice. AC-C5 REMOVED without body. AC-C6
RECONTACT_BLOCKED state, no retry. AC-C7 a retried send with the same
`client_message_id` never creates a second message (E2E with a dropped first
response). AC-C8 quota/rate states with `Retry-After`. AC-C9 rows survive
listing 404. AC-C10 tenant never sees provider fields. AC-C11 SYSTEM code
mapped; unknown neutral. AC-C12 "Zgłoś wiadomość" only on the other side's USER
messages; 201/200 → "Zgłoszenie przyjęte"; no decision shown. AC-C13 report
403 → verification step per OD-7.

**Reveal (d):** AC-RV1 unverified → verification, then deliberate press.
AC-RV2 quota visible. AC-RV3 repeat reveal free (unrestricted users). AC-RV4
messages-only state. AC-RV5 number never leaves the reveal element. AC-RV6
restricted requester → `RECONTACT_BLOCKED` state.

**Viewing (e):** AC-V1 a guest can open the picker and select a slot (BP-11);
the request requires auth and resumes with the slot re-validated. AC-V2
exactly the returned instants, response timezone. AC-V3 no-settings and
no-free-terms states. AC-V4 "Pokaż kolejne dni" ≤ 31. AC-V5 result state from
the response. AC-V6 conflict → re-fetch, sheet kept. AC-V7 already booked →
link. AC-V8 cancel offered only before start; backend refusal after start
rendered; CANCELLED without actor. AC-V9 passed REQUESTED labelled "Bez
odpowiedzi — termin minął", state unchanged, no actions. AC-V10 a G-14
restriction's cancellations render as "Oglądanie odwołane".

**Provider (f):** AC-P1 ContextSwitch from authority data only. AC-P2 tenant
view works when provider data fails. AC-P3 action matrix §6.10. AC-P4
LISTING_HELD state. AC-P5 `requester_note` plain text. AC-P6 requester shown
as "Imię N." / "Użytkownik Homies", never e-mail/phone, never "verified".
AC-P7 an unverified authority holder gets no private engagement data once
BP-9 lands.

## 12. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Handoff missing or incomplete | P-0 handoff file; conflicts raised before code |
| R-2 | `detail` string parsing | BP-1 entry criterion; test forbids matching `detail` text |
| R-3 | Duplicate messages | BP-10; BB-11 |
| R-4 | Saved-set cost at 500 saves | once per session; G8 if slow |
| R-5 | Home visit survives a restriction | OD-1 C (BP-6), BB-9 |
| R-6 | Phone bypass of G-14 | OD-2 (BP-8), OD-8 |
| R-7 | Unverified authority reads private engagement | BP-9, BB-10 |
| R-8 | Public slots leak schedule/occupancy or cost DB time | BP-11 review: derived instants only, rate limit, days cap |
| R-9 | Wrong local times across DST | BP-2 timezone; DST fixtures |
| R-10 | Session illusions (BG-1) and refresh races (BG-5) | BB-1, BB-2; not masked |
| R-11 | Free text leaking into analytics/storage | parity test §9.2-5 |
| R-12 | Stale REQUESTED pollutes provider metrics | DEBT-1 decision; derived label only |
| R-13 | Unverified harassment recipient cannot report | OD-7 |

## 13. Status

`FE-003 IMPLEMENTATION AUTHORIZED: NO`

Next: founder + GPT-5.6 Sol **final** contract approval, answers to OD-7,
OD-8 and the BP-9 rule, and the P-0 handoff in the repository. No FE-003
production code, merge or deployment before that.
