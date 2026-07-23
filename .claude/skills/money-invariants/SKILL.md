---
name: money-invariants
description: The financial invariants of the Homies ledger and how to verify them. Use before or after any change touching payments, bookings, refunds, payouts, commission or the ledger.
---

# Money invariants

The ledger is the accounting truth; Stripe is an external processor. Every
money movement is a balanced double-entry posting. Violating any invariant
below is a P0 incident, not a bug.

| ID | Invariant | Enforced by |
|---|---|---|
| I1 | No two active (`pending`/`confirmed`) bookings overlap on a listing | Postgres exclusion constraint `excl_booking_overlap` |
| I2 | Every journal entry sums to exactly zero | `ledger.post_entry` + reconciliation |
| I3 | The whole system sums to zero | reconciliation |
| I4 | `journal_entries`, `journal_lines`, `audit_log`, `domain_events` are append-only | **DB triggers** (owner-proof, survive direct SQL) |
| I5 | `booking_escrow` is never positive (liability, credit-normal) | post-payout check, aborts the run |
| I6 | A cancelled booking holds no escrow | late-success auto-refund path |
| I7 | Payout only for `completed` bookings with a `succeeded` payment | payout query |
| I8 | `confirmed` booking ⇒ payment `succeeded` | webhook handler |
| I9 | Duplicate webhook delivery never doubles money | payment row locked `FOR UPDATE` + status guard |

## Accounts

`provider_cash` (asset, funds at Stripe) · `booking_escrow` (liability to guests)
· `host_payable:{host_id}` (liability to a host) · `platform_revenue` (income).
Amounts are **signed integers in minor units**: debit > 0, credit < 0.

## Verify

```bash
# live stack
curl -s localhost:8000/v1/admin/payments/reconciliation -H "Authorization: Bearer $ADMIN"
# expect: ok=true, grand_total=0, double_capture=[], succeeded_without_capture=[]
cd backend && ./.venv/Scripts/python scripts/warfare/warfare.py   # all VERDICT lines PASS
```

## Rules when changing money code

- Never write balances directly — only `ledger.post_entry`.
- Never mutate a posted entry; correct with a **compensating entry**.
- Any concurrent path that reads-then-writes a payment or booking must lock the
  row (`with_for_update()`); a check-then-act gap has already produced a real
  double-capture race here.
- Notification/delivery failure must never roll back or block a money
  transaction.

## Known open gaps (do not assume these work)

Refund after payout returns 409 — **no clawback flow**. No chargeback handling.
Only full refunds. Ledger accounts are **not currency-scoped**. Commission is a
single global bps value with integer floor rounding.
