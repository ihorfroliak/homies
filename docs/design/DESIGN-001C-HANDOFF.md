# DESIGN-001C — Implementation Handoff (P-0)

| Field | Value |
|---|---|
| Status | **P-0 DRAFT — READY FOR FOUNDER/GPT REVIEW.** Documentation only. `FE-003 IMPLEMENTATION AUTHORIZED: NO` |
| Baseline | `main` = `c87616ad52e61ec2c97899f2f5e5b04c2dcec61d` |
| Direction | **1C Dzielnica** (D-103), DESIGN-001C founder/GPT **APPROVED at design-contract level** (D-104/D-105) |
| Binds | [FE-003 contract](../tasks/FE-003-save-conversation-viewing-DRAFT.md) (approved, §0.2 P-0) and the later FE-VIS-001 |
| Source visual artifact | `Homies 001C Dzielnica Product Convergence.dc.html` — **not accessible to the builder** (not on disk; Claude Design connector HTTP 403). Nothing in this handoff is taken from it |

## How this document was made

Only rules **already approved or recoverable from repository records** are
encoded. Each rule names its source. Anything that only the inaccessible
`.dc.html` could settle is listed in §28 as **UNRESOLVED** — it is not
guessed. Where two repository records disagree, §30 lists the conflict and
the precedence used.

**Sources (precedence high → low for this handoff):**

| Id | Source |
|---|---|
| S0 | Canon: 04a §16, §18, §21–§24; 02 §2; DECISIONS D-100, D-103, D-104, D-105 |
| S1 | FE-003 contract (approved, merged at `c87616a`) |
| S2 | `docs/product/DESIGN-001-product-ui-foundation.md` (D-100) |
| S3 | `docs/product/DESIGN-SYSTEM-v1.md` + `frontend/design-system/tokens.css` |
| S4 | `docs/product/UI-STATE-MAP.md` |
| S5 | `docs/frontend/FE-002-seeker-search-detail.md` + runtime: `frontend/web/src/app/**`, `components/**`, `i18n/pl.ts` |

Later approved decisions (S0, S1) win over earlier design records (S2–S4)
where they conflict; runtime (S5) describes what exists, not what is approved.

## 1. Scope and authority

This handoff is the repository-readable P-0 input required by the FE-003
contract §0.2. It governs the **FE-003 engagement surfaces** and records the
boundary to **FE-VIS-001** (1C visual/token rollout). It does not authorise
implementation, production tokens, FE-VIS-001 or deployment. It ranks below
the canon and the FE-003 contract; a conflict with either is a contract
question, never resolved in code.

## 2. Selected direction

**1C Dzielnica** — expressive district/area colour as visual identity
(D-103, S0). Seeker v1 validated behaviour and the FE-002 architecture are the
implementation foundation; mobile web exists now; native = one Expo/React
Native app for renter, owner and agent; Admin = separate secure web app
(03 §2). The concrete 1C palette, typography and component styling are **not
recoverable** (§27, §28).

## 3. Non-negotiable invariants

| # | Invariant | Source |
|---|---|---|
| I-1 | Area/district colour **never** encodes trust, quality, prestige, safety, recommendation, verification, freshness, moderation or listing status | D-103 |
| I-2 | Monthly total first; base rent second; "czynsz" never alone | S2 P3, §7 |
| I-3 | The client **never computes** `monthly_total_estimate` or `move_in_total` | S1 §3.4; S2 §5.5 |
| I-4 | No exact address, street, building, coordinate or meeting point anywhere (G9) | 04a §24; S1 §3.8 |
| I-5 | No pin; APPROXIMATE drawn as the API's grid cell; DISTRICT shows no map | 04a §16; S2 P14 |
| I-6 | `floors_total` is never shown; `floor` may be | 04a §24 (D-101/D-102) |
| I-7 | No numeric public-location radius in UI copy | founder P-0 brief; §30 C-5 |
| I-8 | Freshness ≠ verification; never "zweryfikowana" for freshness | S2 P6–P7 |
| I-9 | No fake urgency, scores, popularity, counts we cannot source, pre-checked opt-ins, confirmshaming | S2 P8–P9 |
| I-10 | Moderation reasons never public; refusals neutral, no allegation | S2 P13; S1 |
| I-11 | No viewing creates a conversation and no conversation creates a viewing | S1 §3.2 |
| I-12 | Registration does not create a session and does not execute a pending action by itself; the session is established by login, then the action resumes per its own rule | S1 §3.7 |
| I-13 | Provider capability comes from authority data (VERIFIED PropertyAuthority per BP-9), **never** from `user.role` / legacy `host` | 04a §24 (D-105); S1 §3.9 |
| I-14 | No dead buttons: an action appears only when its slice is shipped | S1 AC-G4; S2 §5.5 |
| I-15 | Semantic tokens only in FE-003 code; no 1C values before FE-VIS-001 | D-104 OD-5 |

## 4. Breakpoints

Token source S3 (`tokens.css` layout group); runtime S5 uses the same values
in CSS Modules. **Note:** DESIGN-SYSTEM-v1 says breakpoints are mirrored in
`frontend/web/src/ui/breakpoints.ts`; that file does not exist (§30 C-6).

| Name | Width | Approved layout (S2 §4) | Runtime today (S5) |
|---|---|---|---|
| sm | 0–479 | 4-col grid, 16 px margins; list-first, one card per row | one card per row |
| md | **480**–767 | two-up cards allowed | results grid two-up from 480 |
| lg | **768**–1023 | list two-up; map = full-screen mode with a top segmented control; filters in a right drawer (480 px) | gallery 60 % columns; home rail 3-up; search box inline |
| xl | **1024**–1439 | split view list 45 % / map 55 %, map sticky; filters as a left side panel | list mode 3-up grid; **map mode** split 45/55; detail two columns `1fr / 360px`, aside sticky |
| 2xl | ≥ **1440** | split with the list capped at 760 px, two-up cards in the list | split list two-up |

FE-003 rule: **rail ≥ 1024, dock < 1024, never both** (S1 §6). Specs start at
360 px (S2 P10).

## 5. List/map behaviour (unchanged by FE-003)

From S2 §4, §5.3 and S5: one mode at a time below 1024 (never a shrunk split);
a persistent **Lista / Mapa** segmented switch keeps filters and scroll; map
mode via `?widok=mapa`; price pills show the monthly total; points in one cell
are a **stack**, never spiderfied; "Szukaj w tym obszarze" only after a user
pan/zoom; the bbox becomes a removable "Obszar mapy" chip noting district-only
listings are excluded; `truncated` and `without_point` said in words; tile
failure → message + list. FE-003 adds only SaveButton on cards and map cards.

## 6. Detail-page composition

Approved (S2 §5.5): mobile top → bottom: gallery ("1/12", fullscreen) · title ·
district, city · **CostBreakdown summary** (monthly + move-in, expandable) ·
FreshnessBadge · move-in and term · description · location · platform notes ·
"Zgłoś ofertę" link. Desktop: two columns — gallery + content left; sticky
360 px price card right.

Runtime (S5): header (title, place, freshness) → gallery → columns: main
(facts, description, location) + `aside` (costs, contact placeholder "kolejny
etap"); below 1024 the aside follows the main column, so the cost summary is
**not** near the top on mobile (§30 C-3).

FE-003 composition (S1 §6.2–6.3): the `aside` becomes the **EngagementRail**
≥ 1024 (price summary + shipped actions); below 1024 the **MobileActionDock**
carries the monthly total and the primary action. Where the full mobile cost
summary sits is §28 U-3.

## 7. EngagementRail (≥ 1024)

S1 §6.2: sticky right column (current width 360 px, S5); `complementary`
landmark "Koszty i kontakt"; order price → save → message → viewing → phone;
price summary = FE-002 CostBreakdown values; phone CTA only for
`contact_mode=phone`; existing thread/viewing shown instead of a new start;
actions of unshipped slices absent; summary server-rendered, actions load with
a skeleton, CLS ≤ 0.1. Visual styling: §28 U-1.

## 8. MobileActionDock (< 1024)

S1 §6.3: bottom bar with `monthly_total_estimate` (+ its utilities basis
wording) and one primary action (viewing when FE-003e is shipped, else
message) + save; other actions in a sheet; `region` "Akcje oferty"; respects
`env(safe-area-inset-bottom)`; page bottom padding keeps focused content
visible (WCAG 2.4.11); hidden while the keyboard is open in the composer.
Stacking with the seeker bottom navigation (S2 §2) on the detail page: §28 U-2.

## 9. SaveButton

S3 + S1 §6.1: heart + `aria-label` "Zapisz: {title}"; `aria-pressed`; states
unsaved · saving · saved · error; **non-optimistic** (pressed state changes on
200/201/204 only); on cards it is a separate control **outside** the card link
(S3 ListingCard); anonymous → AuthInterrupt → automatic resume; icon on
cards, labelled in rail/dock.

## 10. Viewing slot presentation

S1 §3.3, §6.4: slots are the **derived** instants from `viewing-slots`, never
computed or extended by the client; a ViewingSlot is a UI representation, not
an entity; grouped by local day in the **API-returned timezone** (BP-2); per
day a `radiogroup` with radios "10:00–10:30"; arrow keys; selection never
colour-only; mobile = day tabs + vertical list, ≥ 1024 = grid; "Pokaż kolejne
dni" up to 31 days. A guest may inspect/select a slot before auth once BP-11
lands; the request itself needs auth. Copy always shows date + time (S2 §7).

## 11. Viewing-state presentation

S1 §3.3 + S4:

| API state | Seeker label | Notes |
|---|---|---|
| REQUESTED | "Prośba wysłana — czeka na potwierdzenie" | cancel only before start |
| CONFIRMED | "Oglądanie potwierdzone" | date/time only — no address (G9) |
| DECLINED | "Właściciel nie przyjął tego terminu" + "Wybierz inny termin" | — |
| CANCELLED | **"Oglądanie odwołane"** — **no actor** | until BP-5/BB-5 (§30 C-1) |
| COMPLETED / NO_SHOW | "Odbyło się" / "Oznaczone jako nieodbyte" | provider-recorded |
| REQUESTED, start passed | display-only "Bez odpowiedzi — termin minął" | stored state unchanged (DEBT-1) |

Status always text + icon; status tokens `--c-requested-*`, `--c-confirmed-*`,
`--c-cancelled-*` (S3) — never a district colour (I-1).

## 12. Conversation hierarchy / composer

S1 §3.2, §6.6–6.7; routes S2 §2: inbox `/wiadomosci` (newest first) → thread
`/wiadomosci/{id}` (listing header, messages oldest → newest, composer); list
→ thread on mobile, split ≥ 1024. A thread starts only with a non-empty first
message (≤ 4000 after trim; counter from 3600). Composer: labelled textarea,
Enter = newline, Ctrl/Cmd+Enter = send, `client_message_id` retries (BP-10).
CLOSED: composer replaced by the notice; REMOVED message "Wiadomość usunięta
przez Homies" (muted, italic — S4); SYSTEM code mapped; "Zgłoś wiadomość" on
the other side's USER messages, no verification wall (D-105).

## 13. Auth interruption UI

S1 §3.7, §6.8; S2 P2 and §2: an in-page dialog (sheet < 1024) with login and
register; fallback pages `/logowanie`, `/rejestracja`; never an auth wall over
readable content (S3 Drawer/Sheet/Modal). E-mail focused on open; paste and
autocomplete allowed (WCAG 3.3.8). Register → **login** → session → the
pending action resumes **per its own rule** (save automatic; message, viewing,
reveal, report need the user's own confirm). Registration never sends `role`.

## 14. Provider ContextSwitch / ProviderViewingRow

S1 §6.9–6.10, S2 §2: the provider context exists only when authority data
proves it (I-13). **Placement conflict (§30 C-2):** S2's IA puts supply in a
"Panel" mode (`/panel/leady`, `/panel/ogladania`, switch "Przełącz na panel");
S1 proposed an in-page switch on `/wiadomosci` and the viewings route. This
handoff recommends the S2 IA and treats ContextSwitch as the Szukam ↔ Panel
mode switch — **pending confirmation**. ProviderViewingRow: date/time,
attendees, `requester_note` as plain text, requester shown as "Imię N." or
"Użytkownik Homies" — never e-mail/phone, never "zweryfikowany" (D-104 OD-3);
action matrix per S1 §6.10.

## 15. CostSignature rules

S1 §3.4, S2 §5.5, S5 `i18n/pl.ts`:

| Row | Field | Rule |
|---|---|---|
| Koszt miesięczny | `monthly_total_estimate` | shown as delivered; "od … + media" / lower-bound note when `utilities_basis=NOT_STATED`; "szacunkowo" when ESTIMATED |
| Najem | `rent_amount` | always |
| Czynsz administracyjny | `admin_fee` | when > 0 |
| Media | `utilities_amount` + `utilities_basis` | INCLUDED "w cenie najmu" · ESTIMATED "ok. X zł (szacunkowo)" · NOT_STATED "nie podano" |
| Parking | `parking_fee` | when > 0; inside the total (§18) |
| Inne koszty | `other_costs` | verbatim, labelled not included in totals; never parsed |

Amounts: tabular numerals, `Intl.NumberFormat('pl-PL', {style:'currency',
currency, useGrouping:'always', minimumFractionDigits:0})` from minor units;
grosze only when non-zero; currency from `currency` (S2 P16).

## 16. Move-in cost / deposit presentation

"Na start" = `move_in_total` as delivered; caption "pierwszy miesiąc +
kaucja" (S2) / runtime note "Na start = koszt pierwszego miesiąca i opłaty
jednorazowe, w tym kaucja." (S5); "Kaucja (zwrotna)" = `deposit_amount` when
> 0, **outside** the monthly total, inside "Na start". LD-6 ("zwrotna")
remains a legal-wording review item (S2 §7).

## 17. D-103 district-colour restrictions

District colour may identify **place** only (area chips, place labels, map
area context). It must not be applied to: prices, totals, freshness, status
chips, viewing/conversation states, refusal states, trust/verification
facts, ranking, "recommended" or sponsored treatments, or anything implying
one area is better, safer or more prestigious. Never the only carrier of
meaning (WCAG 1.4.1). Contrast rules of S3 still apply. Palette and mapping:
FE-VIS-001 (§26), values unrecoverable (§28 U-1).

## 18. G4 / pricing truth

`monthly_total_estimate` includes a stated `parking_fee` (verified in the
FE-003 contract §1.5). The UI never labels parking optional, offers no
"without parking" toggle and never subtracts it; the optional/mandatory input
is a backend modelling gap (BB-4). No heuristic total of any kind.

## 19. G9 privacy boundary

Exact address / meeting point only after CONFIRMED, only to that viewing's
parties, only via a participant-safe surface — **which does not exist**, so
FE-003 shows none of it (04a §24; S1 §3.8). Location copy uses the runtime
string "Lokalizacja przybliżona — dokładny adres zna tylko właściciel." (S5)
without a distance figure (I-7). Nothing private in analytics, URLs, storage,
logs or `aria` text.

## 20. REQUESTED vs CONFIRMED semantics

The result of a request is the **response status**: INSTANT_BOOKING →
CONFIRMED immediately; REQUEST_APPROVAL → REQUESTED until the provider
confirms/declines (S1 §3.3). The UI never predicts the mode (the seeker cannot
read settings) and never shows REQUESTED as booked. Neither state discloses an
address.

## 21. RECONTACT_BLOCKED presentation

Neutral, no reason, no decision, no retry (S1 §3.2, §3.3, §3.5):
conversation "Nie możesz rozpocząć nowej rozmowy o tej ofercie"; viewing
"Nie możesz umówić oglądania tej oferty"; phone "Nie możesz zobaczyć numeru do
tej oferty" (new **and** repeat reveal, D-105). The other engagement CTAs for
that listing are not offered once the code is known.

## 22. Loading / error / empty / 429 / conflict states

From S2 §5.2, S4 errors table and S1:

| State | Rule |
|---|---|
| loading | skeletons (static under reduced motion), container `aria-busy`; actions pending with `aria-busy`, size unchanged |
| empty | EmptyState: title, body, ≤ 2 actions (saved list, inbox, my viewings, provider rows) |
| API error | inline Alert, what still works + one next action; inputs kept |
| 401 | BFF refresh once, then AuthInterrupt with the intent |
| 403 | phone gate → verification step; otherwise "Nie masz dostępu…" |
| 404 | Unavailable / tombstone wording (D-59), never "usunięta"/"wygasła" |
| 409 | per stable code (BP-1), reload/re-read then explain; never raw `detail` |
| 429 | `Retry-After`-aware countdown; reads auto-retry, writes do not |
| 503 / unknown outcome | writes never blind-retried; messages retry with the same `client_message_id` (BP-10) |
| offline | banner; drafts and filters kept in memory |

## 23. Accessibility and keyboard rules

WCAG 2.2 AA (S2 §6, S3): focus visible and not obscured (two-tone ring,
scroll padding for sticky chrome); targets ≥ 24 px, ≥ 44 px primary/touch;
dialogs trap focus, Esc closes, background `inert`; one polite live region for
counts/status; Polish plurals via `Intl.PluralRules('pl')`; contrast ≥ 4.5:1
text, ≥ 3:1 UI; `--c-ink-300` never for meaningful text; `lang="pl"`; codes
never reach the screen unmapped; tabs use roving tabindex; markers are not
individually tabbable ("Pokaż jako listę"); axe on every surface + manual
keyboard/screen-reader pass.

## 24. Focus rules

* The **filter dialog** receives focus on open; focus returns to its opener on
  close. Today filters are a native `<details>` element, not a dialog (§30
  C-4): the rule applies when the filter surface becomes a dialog/sheet.
* Every dialog/sheet returns focus to its opener on close.
* The **auth dialog** focuses the **e-mail** field on open.
* After auth resume or close, focus returns to the **initiating control**; if
  it no longer exists, to the **result status** message.
* After a 409 re-read, focus moves to the status message that explains it.

## 25. Responsive component ownership

| Component | < 1024 | ≥ 1024 | Owner |
|---|---|---|---|
| EngagementRail | — | sticky aside | FE-003 |
| MobileActionDock | bottom bar + sheet | — | FE-003 |
| SaveButton | icon (cards), labelled (dock) | icon (cards), labelled (rail) | FE-003 |
| ViewingSlot picker | sheet, day tabs + list | dialog/side panel, grid (exact container: §28 U-4) | FE-003 |
| Conversation | list → thread navigation | split | FE-003 |
| AuthInterrupt | full-screen sheet | modal | FE-003 |
| ContextSwitch / ProviderViewingRow | segmented control / cards | rows | FE-003 (placement §14) |
| Filters dialog/sheet | full-screen sheet | side panel | **FE-VIS-001** (FE-002 surface; §30 C-4) |
| Results, cards, map, home, header/footer | as §4–§5 | as §4–§5 | FE-002 (exists) / FE-VIS-001 (restyle) |

## 26. FE-003 vs FE-VIS-001 boundary

S1 §7 (D-104 OD-5): **FE-003** builds the engagement components on semantic
tokens; **FE-VIS-001** introduces the 1C token layer (district colour
identity, type, radii, elevation), restyles FE-002 surfaces and converts the
filter surface to the approved dialog/sheet. FE-003 must not ship 1C values;
FE-VIS-001 must not change engagement semantics.

## 27. Current approved typography / tokens status

Production tokens = **Design System v1** (`frontend/design-system/tokens.css`,
S3): brand-600 for primary buttons (AA), `--fs-body` 1rem, price/caption
sizes, tabular numerals, status/map/focus/motion/layer tokens; font = the
system-ui stack at launch (D1-2); light theme only (D1-7); promoted/free
badges deprecated. **No 1C tokens exist in the repository**; none are approved
in a readable form.

## 28. Unresolved visual details (need the approved `.dc.html` or a founder/GPT answer)

| # | Item |
|---|---|
| U-1 | All 1C visual values: district palette and its mapping, typography changes, radii, elevation, iconography, illustration, motion specifics; rail/dock/card styling |
| U-2 | Detail page < 1024: stacking of MobileActionDock with the seeker bottom navigation (S2 §2) — dock replaces, sits above, or hides the nav |
| U-3 | Mobile position of the full CostBreakdown summary (S2 near the top vs runtime after location, §30 C-3) |
| U-4 | Slot picker container ≥ 1024 (modal vs inline panel in the rail) and the confirm-sheet anatomy |
| U-5 | Inbox/thread visual hierarchy details (avatar/initial use, timestamps grouping, closed-state banner styling) |
| U-6 | Final copy for states where S1 and S4 differ in wording (e.g. closed conversation: "Homies zamknął tę rozmowę" vs "Rozmowa została zamknięta przez Homies.") — LD-5/L11 legal review |
| U-7 | Artboard-level assignment FE-003 vs FE-VIS-001 beyond §25 |
| U-8 | Provider surface placement (§14, §30 C-2) |

## 29. Explicit implementation prohibitions

1. No 1C token, colour, layout value or prototype asset in FE-003 code.
2. No district colour on any state, trust, price, quality or ranking element.
3. No client-computed or adjusted totals; no "optional parking" UI.
4. No exact address, coordinate, street, building, meeting point; no
   `floors_total`; no numeric radius in location copy.
5. No viewing ↔ conversation auto-creation.
6. No auto-sent message, auto-requested viewing, auto-reveal or auto-report
   after sign-in; registration never resumes an action by itself.
7. No `role` / `host` as authority; no role choice at registration.
8. No requester e-mail/phone to providers; no "verified" label on projected
   names.
9. No cancellation actor in the UI until BP-5; no invented EXPIRED/DECLINED
   semantics for passed REQUESTED.
10. No parsing of English `detail`; stable codes only (BP-1).
11. No message text, note, phone, `client_message_id` or address in analytics,
    URLs, storage or logs.
12. No verification wall before "Zgłoś wiadomość".
13. No dead buttons; no fake urgency or unsourced counts.

## 30. Conflicts found between repository records

| # | Conflict | Precedence applied |
|---|---|---|
| C-1 | UI-STATE-MAP shows "Odwołane przez Homies"; FE-003 contract §3.10 forbids any cancellation actor until BP-5 | FE-003 contract (later, approved): "Oglądanie odwołane" only. UI-STATE-MAP row is stale |
| C-2 | DESIGN-001 IA: supply in Panel mode (`/panel/leady`, `/panel/ogladania`, "Przełącz na panel"), viewings at `/ogladania`; FE-003 contract proposed in-page ContextSwitch and `/ogledziny` (marked PROPOSED, "handoff decides") | Recommend DESIGN-001 IA (decided, D-100; nav string "Oglądania" already in `pl.ts`) — **needs founder/GPT confirmation** (U-8) |
| C-3 | DESIGN-001 §5.5 puts the cost summary near the top on mobile; FE-002 runtime renders it after the location section | Approved spec = DESIGN-001; runtime deviation recorded; resolution U-3 |
| C-4 | DESIGN-001C focus rule for a "filter dialog"; FE-002 filters are a native `<details>` (not a dialog); FE-003 contract §9.3 says "re-verified in FE-003" | Rule binds when the filter surface becomes a dialog/sheet; recommend FE-VIS-001 owns that conversion; FE-003 E2E asserts it only once it exists |
| C-5 | DESIGN-001 §5.5 location caption includes a distance ("ok. 500 m") and "~550 m cell"; founder P-0 brief: no numeric radius; runtime copy has none | No figure in UI copy; the drawn cell comes from API geometry |
| C-6 | DESIGN-SYSTEM-v1 says breakpoints are mirrored in `frontend/web/src/ui/breakpoints.ts`; the file does not exist (values live in CSS Modules) | Breakpoint values (S3/S5) are correct; the file reference is stale |
| C-7 | DESIGN-001 §7: viewing times "(Europe/Warsaw)"; FE-003 contract BP-2: use the API-returned timezone, no hard-coded zone | Contract wins in code; Polish launch copy still shows local date + time |

---

## IMPLEMENTATION BINDING CHECKLIST (run before every FE-003 frontend slice)

- [ ] Slice entry criteria of FE-003 contract §10.3 met (BPs on `main`); founder authorisation for this slice exists.
- [ ] This handoff's §28/§30 items touching the slice are answered or explicitly out of the slice.
- [ ] Semantic tokens only; no 1C values; no district colour on states, prices, trust or ranking.
- [ ] Totals rendered exactly from `monthly_total_estimate` / `move_in_total`; parity test with a non-additive fixture.
- [ ] Parking shown inside the total when stated; no optional-parking UI.
- [ ] No address, coordinates, meeting point, `floors_total`, numeric radius.
- [ ] Every refusal mapped from a stable code; no `detail` parsing; RECONTACT_BLOCKED neutral.
- [ ] Viewing states from the API; REQUESTED ≠ CONFIRMED; no cancellation actor; passed REQUESTED label display-only.
- [ ] Slots rendered exactly as returned, in the API timezone; no client availability logic.
- [ ] No viewing ↔ conversation auto-creation; first message required to start.
- [ ] Auth: register → login → session → resume per action rule; nothing auto-sent; `role` never sent.
- [ ] Provider surfaces from authority data (VERIFIED, BP-9), never `role`/`host`; requester as "Imię N." only.
- [ ] Focus: dialogs trap and restore; auth dialog → e-mail; after auth → initiator or result status; 409 → status.
- [ ] Rail ≥ 1024 / dock < 1024, never both; dock never covers focused content.
- [ ] A11y: axe clean desktop + mobile; keyboard pass; targets ≥ 44 px primary; not colour-only.
- [ ] Analytics: closed catalogue, consent-gated, no free text/phone/address/ids beyond the contract.
- [ ] BFF allowlist entries match backend auth levels; nothing else proxied.
- [ ] `FE-003 IMPLEMENTATION AUTHORIZED` checked for this slice — never assumed from this document.
