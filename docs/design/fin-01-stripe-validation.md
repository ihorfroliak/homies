# FIN-01 — Stripe financial integrity validation

Micro-cycle 02. Goal: move the Stripe integration from "implemented and locally
tested" to "validated against real Stripe". Design decision:
[ADR-0007](../adr/0007-stripe-connect-destination-charges.md).

## 0. Status — partially validated, FIN-01 stays OPEN

**No Stripe test credentials were available in this environment**, so the parts
that require an account (PaymentIntent creation, test cards, 3DS/SCA, refunds,
transfers, payouts, disputes) **were not executed**. They are written and gated
in `backend/tests/stripe_live/`, ready to run the moment keys exist.

What *was* validated for real: the **webhook trust boundary and event handling,
using the real `stripe` SDK** (signature verification needs only a signing
secret, which is generated locally per test — no account, no network). That
found **two genuine production bugs** that every mocked test had hidden.

| Area | Executed | Evidence |
|---|---|---|
| Webhook signature verification (real SDK) | ✅ | 10 tests |
| At-least-once / duplicate delivery | ✅ | single capture proven |
| Unknown / failed event handling | ✅ | tests |
| Payment-environment model | ✅ | 9 config tests |
| Financial invariants under webhook flow | ✅ | reconciliation `ok=true` |
| PaymentIntent creation, test cards, 3DS/SCA | ❌ **needs keys** | suite written, skipped |
| Refund, transfer, payout, dispute | ❌ **needs keys / not built** | see gaps |

## 1. Architecture discovered

**Stripe Connect, destination charges.** One `PaymentIntent` per booking on the
platform account with `transfer_data.destination = <connected account>` and
`application_fee_amount = commission`. The provider seam
(`StripeConnectProvider` | `StripeSimulationProvider`, selected by
`PAYMENT_PROVIDER`) keeps Stripe types out of the domain — the ledger, booking
engine and modules never import `stripe`.

Payment lifecycle: `requires_payment → succeeded → refunded | voided | failed`.
Webhook lifecycle: verify signature → persist raw event → dedupe by
`stripe_event_id` → dispatch → mark processed, all in one DB transaction.

## 2. Bugs found by testing against the real SDK

Both were invisible to the mocked B1 tests and would have hit production.

### BUG-1 — every post-verification failure was reported as "Invalid signature"

The handler caught `Exception` broadly and mapped everything to **400**. Stripe
treats 400 as "do not retry". So a *validly signed* event that we failed to
process would be silently dropped by Stripe while the operator saw a misleading
"invalid signature".

**Fix:** the provider raises `WebhookVerificationError` **only** for an
untrusted sender (bad/missing signature, stale timestamp, unparseable body).
Anything else propagates as 5xx, so Stripe retries and the real cause stays
visible. Trust failure and processing failure are no longer conflated.

### BUG-2 — persisting a real event crashed

`stripe.Webhook.construct_event` returns a `StripeObject`, not a mapping; the
handler did `dict(event)` for the audit record, which raises `KeyError` on a
genuine event. The mock returned a plain dict, so tests passed.

**Fix:** after verification the provider returns `json.loads(payload)` — the
*exact verified bytes* as a plain dict. Better audit fidelity (we store what
Stripe actually sent) and no SDK coupling.

## 3. Payment environment model (new)

Previously nothing stopped `sk_live_` keys on a laptop or `sk_test_` keys in
production. Now `validate_security_config` enforces agreement between the
deployment environment and the key mode, **in every environment** (the dev
exemption must not hide a live key):

| Environment | Required Stripe mode |
|---|---|
| `production` | **live** — a test key is refused ("would run production on fake money") |
| `local`, `test`, `ci`, `staging`, anything else | **test** — a live key is refused |

Also enforced: the key must look like a Stripe secret key (`sk_test_`/`sk_live_`
/`rk_*`), and `STRIPE_WEBHOOK_SECRET` must be a `whsec_...` signing secret.
Key **mode** is derived from the prefix and is the only thing ever logged —
never the key.

## 4. Idempotency results (executed)

The same signed event delivered five times produced **exactly one**
`payment_captured` ledger entry; `/admin/payments/reconciliation` reported
`ok=true`, `double_capture=[]`. Deduplication is by Stripe `event.id` in
`webhook_events`, with the payment row locked `FOR UPDATE` during capture (the
race fixed in OAT-02). At-least-once delivery is assumed, never exactly-once.

## 5. Financial invariants (executed)

I1–I9 from the `money-invariants` skill all hold under the real-signature
webhook flow. Specifically re-verified this cycle: money is neither created nor
destroyed (`ledger_grand_total = 0`), commission posted once, a failed payment
event never confirms a booking, and an unknown event type changes nothing.

**No new invariant was required** — the two bugs were transport/serialisation
issues, not accounting errors.

## 6. Gaps confirmed (not fixed here — scope discipline)

| ID | Gap | Status |
|---|---|---|
| **FIN-01** | Real Stripe Test Mode run (PaymentIntent, test cards, 3DS/SCA) | **still open — needs `sk_test_` keys**; suite ready |
| **FIN-02** | Partial refunds; only full refunds exist | open |
| **FIN-03** | Chargebacks/disputes: no `charge.dispute.*` handling, and the ledger has no representation for dispute-opened / won / lost / funds-withdrawn | open |
| FIN-04 | Refund after payout returns 409 — no clawback | open |
| **BK-01** | Ghost booking — an unpaid `pending` booking blocks inventory indefinitely. **Re-confirmed this cycle**: a `payment_intent.payment_failed` event correctly frees the dates, but an *abandoned* intent (no event at all) leaves the booking `pending` forever | open |
| REC-01 | Reconciliation is internal only (payments ↔ ledger). There is no Stripe-side comparison: no detection of orphaned Stripe payments, missing webhooks, or payout mismatch. `stripe_ledger_reconciliation()` exists but reports `available: false` without keys | open |

## 7. Ghost booking — expected state machine (for the next cycle)

Evidence: a booking that never receives any webhook stays `pending`, and
`pending` is in `BLOCKING_STATUSES`, so the calendar stays blocked at zero cost
to an attacker.

Recommended target state machine:

```
pending --(payment succeeded)--> confirmed
        --(payment failed)-----> payment_failed      [dates freed]
        --(TTL expires, no terminal event)--> expired [dates freed]
```

TTL should be short (15–30 min, the lifetime of a checkout session), enforced by
a scheduled sweep, and must be idempotent and safe against a late-arriving
success (the existing late-success auto-refund path already handles that case).

## 8. Test evidence

**Added:** `tests/test_fin01_stripe_signature.py` (10, real SDK) — valid
signature accepted and booking confirmed; missing signature rejected; signature
from a different secret rejected; tampered payload rejected; stale timestamp
(replay) rejected; malformed header rejected; malformed JSON fails safely;
duplicate signed delivery captures once; unknown event type recorded but inert;
failed-payment event does not confirm a booking.

`tests/test_sec02_secret_config.py` (+9) — payment environment model.

`tests/stripe_live/test_stripe_live.py` (6, **gated**) — credentials/test-mode
guard, PaymentIntent shape with `application_fee_amount`, successful card,
declined card, 3DS/SCA `requires_action`, refund idempotency.

Gating verified by execution:

| Condition | Behaviour |
|---|---|
| not requested | skipped, ordinary CI unaffected |
| `STRIPE_LIVE_TESTS=1`, no key | **fails loudly** (never silently green) |
| live key supplied | **refuses to run** |

Run with: `STRIPE_LIVE_TESTS=1 STRIPE_API_KEY=sk_test_... STRIPE_TEST_CONNECTED_ACCOUNT=acct_... make test-stripe`

## 9. Observability

Payment operations are traceable by internal payment id, booking id, Stripe
payment-intent id and Stripe event id — all safe identifiers, all already
persisted (`webhook_events` keeps the full raw event). Duplicate deliveries are
diagnosable from `webhook_events` alone. No card data, keys or signing secrets
are ever logged; the config validator names fields, never values.

## 10. To close FIN-01

1. Create a Stripe **test-mode** account and a test connected account.
2. Export `STRIPE_API_KEY=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...`,
   `STRIPE_TEST_CONNECTED_ACCOUNT=acct_...`.
3. `make test-stripe` — records the remaining evidence rows in §0.
4. Run one end-to-end booking against test mode with the Stripe CLI forwarding
   webhooks, and confirm reconciliation stays `ok=true`.
