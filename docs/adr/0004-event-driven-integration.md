# ADR-0004: Event-driven integration between bounded contexts

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context chat:** 01 — System Design & Contracts

## Context

Contexts must react to each other's state changes (e.g., a completed booking triggers a guest notification, an operations cleaning task, and a review invitation) without direct coupling. The data platform also needs a reliable feed of business events for the lake/DWH.

## Decision

Cross-context integration uses **domain events** published to an event bus. The catalog is contract-first in **AsyncAPI 3.0** (`docs/api/events.asyncapi.yaml`): 16 events across 5 channels (identity, listings, bookings, payments, operations).

Key pattern — **fan-out decoupling**: `BookingCompleted` is consumed independently by Notifications, Operations, and Reviews; the Booking module does not know who listens.

Transport:
- **Local dev:** NATS JetStream (single lightweight container in docker-compose).
- **Production:** Kafka (MSK) when the data-platform phase needs durable replayable streams; the publishing interface is transport-agnostic so the swap is a config change, not a rewrite.

Events are named in past tense (`ListingPublished`, `PaymentCaptured`), carry an `event_id` (UUIDv7), `occurred_at`, and a versioned payload schema.

## Consequences

- **Positive:** contexts stay independent; the same event stream powers product features and the analytics pipeline.
- **Negative:** eventual consistency between contexts; consumers must be idempotent (`event_id` deduplication).
