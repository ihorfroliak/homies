# Product UX — primary journeys

UI-01. The journeys the design system must serve. Backend capability for each
step is noted so design and implementation stay honest about what exists today.

## Roles

Guest · Host · Property manager · Admin · Moderator. One account, multiple
roles (a host is also a guest).

## Renter (guest) journey — Product A

```
search ─▶ browse listings ─▶ property detail ─▶ pick dates ─▶ review price
   ─▶ reserve ─▶ pay (Stripe) ─▶ confirmed ─▶ check-in ─▶ stay ─▶ review
```
- Search / browse / detail: **listings + availability exist** (search is
  minimal today — city + paging; geo/amenity filters are future).
- Price transparency: fee + city tax shown **before** pay (UX principle).
- Reserve → pay → confirmed: **booking + Stripe Connect + ledger exist**;
  a pending booking is held only until its payment deadline (**BK-01**), then
  auto-expired and the dates released.
- Check-in / review: **operational state + double-blind reviews** partially
  exist (reviews are backend-modelled, not yet surfaced).

## Host journey — Product A

```
register ─▶ verify identity (Stripe Connect) ─▶ create listing ─▶ set price
   ─▶ manage calendar ─▶ receive bookings ─▶ get paid out ─▶ see earnings
```
- Onboarding, listing CRUD, calendar blocks, payouts: **exist** (KYC is Stripe
  Connect; real run pending `sk_test_` keys — FIN-01).
- Dashboard (occupancy, earnings, upcoming): **mock in the showcase**; the data
  exists in the ledger/booking modules but no host dashboard endpoint is built.

## Free-listing journey — Product B (not built)

```
owner posts a rental ─▶ verify email + phone ─▶ moderation queue
   ─▶ approved & indexed  |  rejected  ─▶ seeker contacts owner
```
- Strategic purpose: organic SEO traffic + inventory + funnel into Product A.
- **Nothing is built.** The showcase renders it to communicate direction. A new
  `FreeListing` bounded context, moderation, trust signals and anti-abuse are
  required first (and rate limiting, which now exists, is a prerequisite).
- SEO guard rail: unreviewed listings must be `noindex` so the free surface
  cannot poison the domain’s search reputation.

## Moderator journey

```
review queue ─▶ inspect listing / host / report ─▶ approve | reject | suspend
   ─▶ action recorded in audit log
```
- Admin read surfaces + incidents + append-only audit **exist**; a moderation
  queue UI and automated content screening are future.

## Sequencing note

The locked strategy is operator-first (managed hosting before the self-service
marketplace). This UX doc describes the full surface for design direction; it
does **not** change that sequencing. Product B follows Product A hardening and
its own trust-&-safety infrastructure.
