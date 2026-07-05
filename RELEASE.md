# RELEASE — живий трекер гейтів (Build → Verify → Gate)

> Оновлюється після кожної значної зміни. Відповідає на 3 питання, щоб
> команда завжди бачила найкоротший шлях до реального бізнесу.
> План: [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md). Останній gate-огляд:
> [D7 board](docs/reviews/2026-07-05-d7-production-readiness-board.md).

## Поточний гейт: **NO-GO** → ціль **Gate 1 (GO WITH RESTRICTIONS)**

### 1. Що тепер можна довести фактами?
- Booking-engine + ledger warfare-доведені (D6): 60 конкурентних→1, 200
  webhook→1 capture, 10 payout→1, крах БД→ACID recovery, refund-loop→0.
- 12 pytest зелені, ruff чистий, живий смоук на docker+Postgres.
- Ledger append-only, escrow≥0, reconciliation=0 під хаосом.
- **B6 закрито:** Alembic-міграції зелені (upgrade/downgrade/повтор).
- **B5 закрито owner-proof:** DB append-only тригери — прямий psql UPDATE/DELETE відбито.
- **B2 restore ДОВЕДЕНО (D9):** виконаний drill — backup (AES-256+checksum)
  → restore RTO 4s → фінансова звірка PASS; **accidental DROP TABLE →
  restore → дані повернулись, звірка PASS**; guards переживають restore.

### 2. Що ще блокує наступний реліз (Gate 1)?
- **B1** реальний Stripe Connect (зараз симуляція) — критичний шлях, гроші.
- **B2-решта** автоматичний розклад бекапів + offsite/PITR — закривається
  **managed Postgres** (RDS/Supabase/Neon дають з коробки), не eng-код.
- **B3** agency-договір + T&C + KYC через Stripe (юр-трек, паралельно).
- (Gate 2, не блокує #1: auto-void, rate-limit, observability, MFA, chargeback.)

### 3. Одна наступна задача з найбільшим наближенням до prod?
→ **B1 — реальний StripeConnectProvider** за наявним `PaymentProvider`-швом
+ webhook-підпис. Це єдине, що лишилось на критичному шляху як **код**
(B2-решта = вибір managed-хостингу, B3 = юр-трек паралельно). Без реального
Stripe немає жодного реального бронювання.

---

## Історія гейтів
- 2026-07-05: D7 board → **NO-GO** (симуляція платежів, нема бекапів/комплаєнсу/observability).
- 2026-07-05: W1 — Alembic-міграції (B6 закрито) + DB append-only тригери (B5 закрито, owner-proof). Readiness 22 → ~32.
- 2026-07-05: D9 — виконаний DR-drill (backup+restore+фінансова звірка PASS двічі). B2-restore доведено; авто-розклад+offsite → managed Postgres. Answer: PARTIALLY. Readiness ~32 → ~40.

## Робочий режим (постійний, без нових D-етапів)
Build → Verify → Release Gate → Repeat. Кожен цикл: одна задача критичного
шляху → доказ (тести/інваріанти/drill) → оновити цей файл і перевірити, чи
змінився шлях. Наступний цикл: **B1 реальний StripeConnectProvider**.
