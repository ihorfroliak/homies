# Bounded Context Map

11 contexts across three subdomain categories (Chat 01 outcome). All live
as modules inside the modular monolith (ADR-0001), except Notifications
and ML-serving which run as separate processes.

## Core subdomains (competitive differentiation)

| Context | Responsibility | Key events published |
|---|---|---|
| **Identity** | Users, roles (client/worker/manager/admin), auth tokens | UserRegistered, UserVerified |
| **Listings** | Property catalog, geo-data (PostGIS), publication lifecycle | ListingPublished, ListingUpdated, ListingArchived |
| **Search** | Read-optimized listing index (Meilisearch projection) | — (consumer only) |
| **Booking** | Availability calendars, booking lifecycle, idempotent creation | BookingRequested/Confirmed/Cancelled/Completed |
| **Pricing** | Price rules; later ML-backed dynamic pricing | — (serves quotes) |
| **Payments** | Charges, refunds, landlord payouts (Stripe) | PaymentAuthorized/Captured/Failed, PayoutSent |

## Supporting subdomains

| Context | Responsibility | Key events |
|---|---|---|
| **Reviews** | Ratings and reviews after completed stays | ReviewSubmitted |
| **CRM** | Leads, customer profiles, communication history | — |
| **Operations (ERP)** | Field tasks: cleaning, maintenance, inspections, check-ins | TaskCreated, TaskCompleted |
| **Marketing** | Google Ads + GA4 ingestion, attribution | — |

## Generic subdomains

| Context | Responsibility | Deployment |
|---|---|---|
| **Notifications** | Email/SMS/push fan-out from domain events | **Separate process** |

## Integration rules

1. Modules never import each other; integration is events (ADR-0004) or
   explicit application-service interfaces.
2. Search, Notifications, Operations, Reviews are primarily **consumers**
   reacting to core-domain events (e.g. `BookingCompleted` fan-out).
3. Each context owns its own PostgreSQL schema (ADR-0003).
