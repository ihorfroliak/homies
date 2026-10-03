# METRICS-v1 — marketplace metric dictionary

Part of [GROWTH-001](GROWTH-001-marketplace-growth-foundation.md). A metric
without every field below is not accepted. Status labels: **MEASURABLE NOW**
(exact from existing tables) · **PROXY** (a stand-in, always shown with its
label) · **NOT MEASURABLE YET** (needs a named seam). Versions: `name-vN`;
any predicate change bumps N; reports show the version.

## 0. Shared conventions

* **Time.** Days, weeks (Mon–Sun), months in Europe/Warsaw civil time:
  `(ts AT TIME ZONE 'Europe/Warsaw')::date`; windows half-open `[start,
  end)`. Durations are elapsed seconds between UTC instants. Use database
  instants stored on rows or in fact payloads — never `domain_events.occurred_at`
  (application clock).
* **Excluded accounts (EXCL).** `users.role = 'admin'` (moderators/admins)
  plus `analytics_account_exclusions` (**seam**: `user_id`, `reason_code ∈
  {INTERNAL, TEST, SEED, FRAUD, PARTNER_DEMO}`, `since`, `created_by`;
  admin-written, audited — not a column on `users`). A listing is excluded
  when its owner or the user behind its ACTIVE authority holder is excluded;
  a conversation or viewing when its requester or listing is.
* **Cell `CELL(KRK, WHOLE_APT, LONG_TERM)`.** The property's address resolves
  inside the Kraków area (the same descendant resolution search uses) ∧
  `spaces.space_type = 'WHOLE_PROPERTY'` ∧ `properties.category =
  'APARTMENT'`; LONG_TERM is implicit (no rental-mode column yet — add the
  predicate when one exists). NULL category falls outside the cell: report
  its count as a data-quality figure.
* **Public now** = `freshness.public_clause` (`active` ∧ confirmed within 21
  days); a moderation hold is always `paused`, hence never public.
* **Public episode** = `listing_public_generations(listing_id,
  public_generation)`, start `became_public_at`; its end = the next
  `ListingStatusChanged` leaving `active` for that generation (fact built in
  GROWTH-001) — before that fact existed, unknown.
* **Messages.** Provider-side = USER message whose sender ≠ requester;
  tenant = sender = requester; redacted = `redacted_at IS NOT NULL`; closed
  by Homies = SYSTEM message `system.conversation_closed_by_homies`.
* **Viewing cancelled by Homies** = `ViewingCancelled.cancelled_by = 'HOMIES'`
  (or, for rows before the fact: `cancelled_at` = the `effective_from` of a
  close-engagement decision on the listing — `effects.cancelled_by_homies`).
* **Right-censoring.** A cohort member enters a k-window rate only when
  `cohort_instant + k ≤ cutoff`; immature members are reported as a count.
  Percentiles: Kaplan–Meier, unconverted members censored at
  `min(cutoff, episode end)`; n < 20 → counts only; a curve never reaching
  0.9 → p90 reported as "> k". Never averages alone.

## 1. QAL-v1 — Qualified Active Listing

| Field | Definition |
|---|---|
| Business question | How much trustworthy, decision-ready inventory can a Kraków whole-apartment seeker find right now? |
| Numerator | listings L at instant T with **all**: (1) public at T; (2) in CELL; (3) not EXCL; (4) `quality.assess(...).missing_required = []`; (5) rent > 0 and a computable monthly total (`monthly_total_estimate` not null); (6) ≥ 3 APPROVED, servable, PUBLIC photos; (7) description ≥ 200 characters; (8) structured address resolution; (9) `available_from` set; (10) no URGENT live LISTING report |
| Denominator | none (a count); companion ratio QAL ÷ public listings in CELL |
| Cohort / period | point in time; daily series at 23:59:59 Warsaw |
| Eligibility | listings in CELL |
| Exclusions | EXCL; NULL category |
| Window | instantaneous |
| Grain | district, provider type (PERSON / ORGANIZATION holder), rent band |
| Dedup | one per listing id (several listings on one space count separately → DQ-11) |
| Source | `classified_offers`, `spaces`, `properties`, `addresses`, listing media, `reports`, `quality.assess` recomputed |
| Known bias | (5)–(9) read the *current* row: history cannot be recomputed. Favours complete listings; does not measure attractiveness. **Derived, never a persisted flag** |
| Version · Status | v1 · MEASURABLE NOW (current value); history NOT MEASURABLE YET (needs `metric_snapshots`) |

## 2. Qualified inquiry v1 — PROXY, REQUIRES BETA CALIBRATION

| Field | Definition |
|---|---|
| Business question | How many seeker contacts are serious enough that a provider wants them? |
| Numerator | conversations c with: listing in CELL; requester not EXCL and email- or phone-verified; first tenant message not redacted and ≥ 40 characters (to calibrate — length computed server-side, the body never leaves the database); c not targeted by a CONVERSATION decision; no SCAM/FAKE close-engagement decision on the listing |
| Denominator | used as a numerator below; own quality ratio = qualified ÷ all conversations |
| Cohort / period | by `conversations.created_at` (Warsaw date) |
| Eligibility | conversations with a listing |
| Exclusions | EXCL (self-contact is refused in code) |
| Window | weekly / 28-day |
| Grain | district, provider type, rent band, local hour of the first message |
| Dedup | one per (requester, listing, public generation) |
| Source | `conversations`, `messages`, `users`, `moderation_decisions`, `listing_public_generations` |
| Known bias | phone-mode listings produce contact reveals, not conversations — report `contact_reveals` (unique per offer × viewer) separately as **contact intent**. The thresholds are arbitrary until fitted against viewing/outcome rungs in beta (→ v2) |
| Version · Status | v1 · PROXY — REQUIRES BETA CALIBRATION |

## 3. Successful Housing Outcome (North Star, G-7)

| Field | Definition |
|---|---|
| Business question | Did Homies help a home get let to a seeker? |
| Numerator (target) | public episodes closed with the provider answering RENTED_VIA_HOMIES (`ListingOutcomeReported`, owner-flow slice), once per episode; "confirmed" when matched to a tenant conversation or viewing in that episode |
| Denominator | episodes closed in the period (outcome rate); none for the count |
| Cohort / period | outcome report instant; secondary cohort `became_public_at` |
| Eligibility / exclusions | CELL; EXCL; listings with SCAM/FAKE decisions |
| Window / grain | weekly, monthly · district, provider type, channel of provider and of matched seeker |
| Dedup | `ListingOutcomeReported:{listing}:{generation}` |
| Source | `ListingOutcomeReported` — **does not exist yet** |
| Known bias | self-report, non-response: RENTED_ELSEWHERE and "no answer" are reported, never imputed. **Never inferred from a listing disappearing, pausing or going stale** |
| Version · Status | v1 · **NOT MEASURABLE YET** |

**Proxy ladder** (every number carries its rung label):

| Rung | Fact | Source | Status |
|---|---|---|---|
| L0 | contact intent (reveal, conversation or viewing request) | `contact_reveals`, `conversations`, `viewings` | MEASURABLE NOW |
| L1 | qualified inquiry | §2 | PROXY |
| L2 | provider responded (first valid provider-side message) | `messages` | MEASURABLE NOW |
| L3 | viewing confirmed | `ViewingResponded(CONFIRMED)` / `viewings.responded_at` | MEASURABLE NOW |
| **L4** | **viewing completed** (provider records COMPLETED after the time) | `ViewingOutcomeRecorded` / `viewings.completed_at` | MEASURABLE NOW — **strongest current proxy** |
| L5 | provider stage ACCEPTED | `ConversationStageChanged` | PROXY |
| L6 | owner reports RENTED_VIA_HOMIES | future | NOT MEASURABLE YET |
| L7 | tenant confirms move-in | future | NOT MEASURABLE YET |

## 4. Search coverage(N) and zero-result rate

| Field | coverage(N)-v1 | zero-result-rate-v1 |
|---|---|---|
| Question | does an in-cell search show a real choice (≥ N results)? | how often does a seeker hit an empty board? |
| Numerator | distinct `search_id` with `result_count ≥ N` (N ∈ {1, 5, 10}) | distinct `search_id` with `result_count = 0` |
| Denominator | distinct `search_id` | same |
| Cohort / window | `search_performed` date; weekly | same |
| Eligibility | normalized filters resolve to the Kraków area, whole-property (or none), apartment (or none) | same |
| Exclusions | EXCL (server join), bot-flagged sessions (DQ-9); 422/429 never emit | same |
| Grain | surface (list/map), filter-dimension signature, price band | same |
| Dedup | `search_id` per distinct canonical query per session; paging and list↔map reuse it | same |
| Source | client `search_performed.result_count` = API `total` | same; reconcile with Prometheus `homies_search_requests_total{results="0"}` |
| Bias | consent-limited | same |
| Status | v1 · NOT MEASURABLE YET (needs ingestion); Prometheus buckets = operational PROXY now | same |

## 5. Liquidity family

Shared: eligibility CELL; exclusions EXCL + listings with a SCAM/FAKE
close-engagement decision; grain district, provider type, rent band,
`contact_mode`; censoring per §0.

| Metric | Question | Numerator ÷ denominator | Cohort · window | Dedup | Source | Bias | Status |
|---|---|---|---|---|---|---|---|
| listing-liquidity-7d-v1 | does new inventory find demand quickly? | mature episodes with ≥ 1 qualified inquiry within 7×24 h of `became_public_at` ÷ mature episodes started in period | episode start week | (listing, generation) | `listing_public_generations`, §2 | phone-mode understated (variant with L0 incl. reveals); episode ends before 7 d (pause/hold) reported alongside | MEASURABLE NOW / PROXY |
| response-liquidity-{1h,6h,24h}-v1 | do providers answer fast enough? | qualified inquiries whose first valid provider message ≤ h after the first tenant message ÷ mature qualified inquiries | first tenant message week | conversation | `messages` | closed-by-Homies before h removed; redacted replies do not count; segment by local hour | MEASURABLE NOW |
| viewing-liquidity-v1 | do conversations become visits? | (a) requested within 14 d (b) confirmed (L3) (c) completed (L4) ÷ mature qualified inquiries | inquiry week · 14 d | inquiry, earliest viewing | `viewings` ⋈ `conversations`, viewing facts | Homies-cancelled removed from (b)(c); NO_SHOW = non-completion; viewing-only demand reported apart; unrecorded outcomes = DQ-7 | MEASURABLE NOW |
| match-liquidity-30d-v1 | does supply reach a likely match? | mature episodes with ≥ 1 L4 within 30 d ÷ mature episodes | 30 d | episode | `viewings`, generations | L4 is not a let | PROXY |

## 6. Speed (p50 / p90, Kaplan–Meier)

| Metric | Start → event | Unit | Censor | Status |
|---|---|---|---|---|
| TTFI | `became_public_at` → first qualified inquiry | episode | min(cutoff, episode end) | PROXY |
| TTFR | first tenant message → first valid provider message | qualified inquiry | cutoff or closure by Homies | MEASURABLE NOW |
| TTV | inquiry → viewing request; → confirmation | qualified inquiry | cutoff | MEASURABLE NOW |
| TTM | `became_public_at` → first L4 | episode | as TTFI | PROXY |

## 7. Supply funnel (unit: provider account; 30-day step windows, to calibrate)

owner_reached → owner_interested (concierge log — NOT MEASURABLE YET) →
signed_up (`users.created_at`) → property_created → authority_submitted →
authority_verified (audit) → listing_created → **activated** (first
generation-1 episode) → first QAL (snapshot — NOT YET) → first qualified
inquiry (PROXY) → first L4 → outcome (NOT YET) → relist/retained. Also
QAL per acquired owner, time-to-publish, inquiries/QAL, provider response
rate and time.

**supply-retention-v1:** activated owners (monthly cohort) with ≥ 1 freshness
action in month k (`ListingConfirmed`, `ListingStatusChanged` to `active`) ÷
cohort; k = 1…6 · MEASURABLE NOW. **relist-rate-v1:** listings with a
generation g ≥ 2 starting ≥ 14 d after g−1 (to calibrate), plus spaces with a
newer listing ÷ listings/spaces with a closed earlier episode · PROXY (a relist
after a let and after a failure are indistinguishable until
`ListingOutcomeReported`).

## 8. Demand funnel (unit: anonymous_id before signup, user after)

landing_viewed → search_performed → listing_viewed (client — NOT YET) →
signed_up → L0 → L1 → L3 → L4 → outcome; repeat/referral later. Segmented by
first, last and last-non-direct touch and platform.

**active-seekers-28d-v1:** distinct non-EXCL users with ≥ 1 seeker action
(conversation start, tenant message, viewing request, contact reveal,
surviving saved listing, saved-search creation) in [D−27, D] on CELL listings
or cell-resolving saved searches · MEASURABLE NOW (logged-in only; anonymous
browsers invisible; unsaves erase saves). **qualified-seeker-v1:** active
seeker with ≥ 1 qualified inquiry in the window · PROXY — REQUIRES BETA
CALIBRATION.

## 9. Side-specific CAC (UNIT-ECONOMICS-v1)

Numerator: attributed cost (minor units) for the side, **including concierge
labour and incentives** — a 0 PLN listing is not 0 CAC. Shared costs are
reported apart, never silently allocated.

| Side | Metric | Denominator | Status |
|---|---|---|---|
| supply | CAC / activated owner · / QAL (average QAL) · / outcome | §7, §1, §3 | NOT MEASURABLE YET (cost CSV, concierge log) |
| demand | CAC / qualified seeker · / qualified inquiry · / outcome | §8, §2, §3 | NOT MEASURABLE YET |

Monthly, 30-day conversion lag reported as immature; blended CAC shown next to
channel CAC, never instead of it; platform-reported conversions never a
denominator; every figure labelled with its causality class (ATTRIBUTION-v1).
