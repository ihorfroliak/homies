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
- **B6 закрито:** Alembic-міграції — `upgrade head`/`downgrade base`/повтор
  зелені на чистій docker-БД; схема (з exclusion constraint) керована.
- **B5 закрито owner-proof:** DB-тригери append-only на journal_entries/
  journal_lines/audit_log — прямий `UPDATE`/`DELETE` через psql (в обхід
  застосунку) відбито `ERROR: append-only table ...: UPDATE is not permitted`.

### 2. Що ще блокує наступний реліз (Gate 1)?
- **B1** реальний Stripe Connect (зараз симуляція) — критичний шлях.
- **B2** PITR/бекапи + виконаний restore-тест.
- **B3** agency-договір + T&C + KYC через Stripe (юр-трек, паралельно).
- (Gate 2, не блокує #1: auto-void, rate-limit, observability, MFA, chargeback.)

### 3. Одна наступна задача з найбільшим наближенням до prod?
→ **Бекап + restore-тест (B2)** — найдешевший, закриває нескінченний
cost-of-delay (втрата грошей при краху диска). Далі — StripeConnectProvider (B1).

---

## Історія гейтів
- 2026-07-05: D7 board → **NO-GO** (симуляція платежів, нема бекапів/комплаєнсу/observability).
- 2026-07-05: W1 — Alembic-міграції (B6 закрито) + DB append-only тригери (B5 закрито, owner-proof). Readiness 22 → ~32.
