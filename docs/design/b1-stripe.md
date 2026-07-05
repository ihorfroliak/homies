# B1 — Production Stripe Connect Integration (evidence + honest limits)

Build cycle B1. Real Stripe Connect adapter behind the existing
`PaymentProvider` seam. Decision: [ADR-0007](../adr/0007-stripe-connect-destination-charges.md).

## 0. Honest scope boundary (read first)

**No real Stripe account/keys exist in this environment.** Therefore:
- Adapter logic, the trust boundary (signature verification), idempotency,
  replay safety, dispatch and ledger translation are **proven
  deterministically against a FakeStripe** (`tests/test_b1_stripe.py`).
- Real **sandbox** behaviour — live 3DS/SCA, real signatures, transfers to
  connected accounts, partial capture, disputes, payout events — is
  **UNVERIFIED, pending test keys**. The mandate forbids trusting docs over
  observed behaviour, so these are listed as pending, not passed.

## 1. Architecture (no domain change)

```
Booking -> PaymentProvider.create_payment_intent()   [seam, unchanged]
             ├─ simulation (default)
             └─ StripeConnectProvider (destination charge + application_fee)
Guest pays at Stripe (SCA/3DS/BLIK/Apple/Google Pay)
Stripe -> POST /v1/payments/webhook/stripe
             1. construct_event(payload, sig)   -> verify signature (trust boundary)
             2. persist raw webhook_events        -> audit
             3. dedupe by stripe_event_id         -> idempotency
             4. dispatch by type -> service -> ledger.post_entry (immutable)
```
Provider chosen by `settings.payment_provider`. Ledger stays authoritative;
Stripe never writes balances.

## 2. Payment flow (destination charge)

`PaymentIntent(amount, application_fee_amount=fee, transfer_data.destination=host_acct)`
→ guest confirms → `payment_intent.succeeded` webhook →
ledger `payment_captured` (Дт provider_cash / Кт booking_escrow) →
booking `confirmed`. Payout allocation/settlement on completion, exactly
as D4 (Stripe moves the host share; our ledger mirrors the split).

## 3. Webhook subsystem (implemented)

- **Signature verification enforced**: `stripe.Webhook.construct_event`;
  bad/missing/tampered signature → **400** (proven: `test_webhook_rejects_bad_signature`).
- **Raw persistence**: every event stored in `webhook_events` (audit).
- **Idempotency**: unique `stripe_event_id`; a duplicate delivery returns
  `{duplicate:true}` and does **not** re-run money effects (proven:
  `test_webhook_confirms_and_is_idempotent` — single capture entry).
- **Out-of-order / failed**: `payment_intent.payment_failed` frees dates,
  never touches ledger (proven: `test_webhook_replay_out_of_order_and_failed`).
- **Unknown event types**: stored + acknowledged, never acted on.
- **Provider guard**: the endpoint returns **503** when the stripe provider
  is not configured (proven live + test) — no accidental processing in
  simulation mode.

## 4. Reconciliation engine (implemented)

`/v1/admin/payments/reconciliation`:
- **payment↔ledger consistency** (no external calls, fully tested): every
  succeeded/refunded payment has a capture entry; every refund has a
  reversal; no double capture; no orphan payments; ledger balances to zero.
- **Stripe-balance cross-check**: compares ledger `provider_cash` to Stripe
  balance transactions — runs only with real keys; otherwise honestly
  reports `available:false` (never a false pass).

## 5. Failure Simulation Report

| Scenario | Observed | Evidence |
|---|---|---|
| Duplicate webhook delivery | no double money; `duplicate:true` | ✅ mock test |
| Tampered / missing signature | rejected 400 | ✅ mock test |
| payment_failed event | booking → payment_failed, ledger untouched | ✅ mock test |
| Endpoint without stripe provider | 503 | ✅ live + test |
| Out-of-order (failed before succeeded) | idempotent, safe | ✅ mock test |
| Real 3DS/SCA challenge | — | ❌ pending keys |
| Partial capture / partial refund | — | ❌ pending keys (structure ready) |
| Transfer / payout failure events | — | ❌ pending keys |
| Chargeback / dispute.created | — | ❌ pending keys (P1 handler) |
| Network timeout / Stripe retry | idempotency-key on create + event dedupe | 🟡 logic present, real retry pending keys |

## 6. Security Review

- **API key / webhook secret**: from env/settings only; **never hard-coded**;
  simulation defaults are empty for Stripe fields. Secrets manager wiring =
  P1 (B8).
- **Trust boundary**: no webhook is trusted without signature verification.
- **Idempotency keys** on `PaymentIntent.create` and `Refund.create`.
- **PCI scope**: card data never touches our servers (Stripe-hosted
  confirmation via client_secret) — PCI SAQ-A scope.
- **No weakening of D5–D9**: append-only ledger/audit, exclusion constraint,
  RBAC all intact (warfare regression clean, 16 tests green).
- **Open**: key rotation, environment separation (test vs live keys),
  webhook endpoint rate-limiting → P1.

## 7. Release Gate (B1 criteria)

| Criterion | Status |
|---|---|
| Simulation replaceable by Stripe without domain change | ✅ config toggle, warfare unaffected |
| Sandbox payments complete | ❌ pending keys |
| Webhook verification enforced | ✅ (adapter + 400 on bad sig) |
| Financial reconciliation passes | ✅ payment↔ledger; 🟡 Stripe-balance pending keys |
| Ledger invariants intact | ✅ warfare no regression |
| Replay attacks fail | ✅ dup event id + bad sig rejected |
| Duplicate webhooks don't duplicate money | ✅ single capture proven |
| All failure scenarios documented + tested | 🟡 mock-tested; real Stripe pending keys |
| No D5–D9 regression | ✅ 16 tests, warfare clean |

## 8. Remaining Production Blockers (post-B1)

1. **Real test keys** → observe sandbox: 3DS, transfers, partial capture,
   disputes, payout events (turns the 🟡/❌ above into ✅).
2. Chargeback / `charge.dispute.*` handler + clawback for refund-after-payout.
3. Daily reconciliation as a scheduled job + alert on divergence.
4. Secrets manager + key rotation + test/live separation.
5. Webhook endpoint rate-limiting.

## 9. Final Executive Answer

**"Can Homies safely accept its first real payment through Stripe Connect
while preserving financial integrity, auditability and operational
control?"**

# 🟡 PARTIALLY

**Evidence for:** the adapter is production-shaped and drops into the proven
seam with **zero regression** (16 tests green, warfare clean); the trust
boundary (signature → 400), idempotency (duplicate → single capture),
replay safety and ledger translation are **proven by execution** against a
deterministic Stripe mock; the ledger stays authoritative and
reconciliation passes; PCI scope is SAQ-A.

**Evidence against (why not YES):** **no real Stripe sandbox call has been
observed** — 3DS/SCA, real signatures, transfers to connected accounts,
partial capture, disputes and payout events are unverified pending test
keys. Per the mandate ("do not assume Stripe docs correct without observing
sandbox behaviour"), this cannot be YES yet.

**Path to YES (small):** provide Stripe **test** keys → run the sandbox
validation checklist (§5 ❌ rows) → observe + record → flip to YES. No
further architecture needed.
