# ADR-0007: Stripe Connect via destination charges; ledger stays authoritative

- **Status:** Accepted
- **Date:** 2026-07-05
- **Context:** B1 — transition from simulated to real regulated money

## Context

Homies must accept real guest money and pay hosts without becoming a
licensed payment institution (strategy D2). The domain already has a
ledger, booking engine and a `PaymentProvider` seam with a simulation
implementation proven under warfare (D5–D9). We must wire real Stripe
Connect without weakening any proven invariant.

## Decision

1. **Regulated partner = Stripe Connect.** Stripe holds funds and is the
   money merchant of record; Homies never custodies funds → no KNF payment
   licence needed.
2. **Charge model = destination charges.** One `PaymentIntent` on the
   platform with `transfer_data.destination = host connected account` and
   `application_fee_amount = platform fee`.
   - *Why over separate charges-and-transfers:* the managed-operator model
     already makes Homies the guest-facing merchant; destination charges
     keep one atomic object per booking, let Stripe move the host's share
     automatically, and expose the fee explicitly — a clean 1:1 with our
     ledger split (`escrow → host_payable + platform_revenue`).
3. **Ledger stays the accounting truth.** Stripe is an external processor.
   Every Stripe event is translated into **immutable** ledger entries;
   nothing bypasses `post_entry`. If Stripe and the ledger disagree, the
   reconciliation engine flags it — Stripe never silently overrides us.
4. **Webhooks are the only state source.** State changes arrive as
   signature-verified webhooks (`stripe.Webhook.construct_event`), are
   persisted raw (`webhook_events`, audit), deduped by Stripe event id
   (idempotency), and dispatched to ledger handlers.
5. **Provider is config-selected** (`payment_provider=simulation|stripe`).
   Simulation stays the default so tests and local dev need no Stripe
   account and D5–D9 stay hermetic.

## Consequences

- **Positive:** legal money model; no domain/ledger redesign; the seam
  swap is a config change (proven — warfare unaffected by the new adapter).
- **Positive:** SCA/3DS, BLIK, Apple/Google Pay come via
  `automatic_payment_methods`; refunds/transfers/payouts are Stripe-native.
- **Negative / open:** real sandbox behaviour (3DS, partial capture,
  transfer failure, disputes) must be **observed with test keys** before
  GO — not assumed from docs. Post-payout refund needs a clawback flow
  (P1). Chargeback handling is P1.
