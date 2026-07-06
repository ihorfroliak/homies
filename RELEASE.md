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
- **B2 restore ДОВЕДЕНО (D9):** backup (AES-256+checksum) → restore RTO 4s
  → фінансова звірка PASS; accidental DROP TABLE → restore → дані повернулись.
- **B1 адаптер ЗБУДОВАНО:** `StripeConnectProvider` (destination charges) за
  наявним швом + Stripe-webhook (підпис→400, сира персистенція, ідемпотентність
  за event id, диспетч у ledger) + reconciliation-engine. Доведено проти
  mock-Stripe: підпис, дублікат→1 capture, replay, ledger-звірка; **16 тестів
  зелені, warfare без регресій, live 503 у simulation-режимі**.

### 2. Що ще блокує наступний реліз (Gate 1)?
- **B1-решта:** реальні Stripe **test-ключі** → спостерегти sandbox (3DS/SCA,
  transfers, partial capture, disputes, payout events). Адаптер готовий; це
  крок «дати ключі + прогнати checklist», не код.
- **B2-решта:** авто-розклад бекапів + offsite/PITR → managed Postgres.
- **B3** agency-договір + T&C + KYC через Stripe (юр-трек, паралельно).
- (Gate 2: auto-void, rate-limit, observability, MFA, chargeback/clawback.)

### 3. Одна наступна задача з найбільшим наближенням до prod?
Нотифікації збудовано (OAT-02), але канали **log-based** — гість/хост не
отримують реального email/SMS. Наступний ROI:
- **Реальна доставка нотифікацій** (email через провайдера за наявною
  channel-абстракцією) + **check-in інструкції** (коди/ключі в payload).
- Потім: **auto-void неоплачених** (закрити ghost-booking DoS).
- Без коду паралельно: Stripe test-ключі (B1→YES) + юр-трек (B3).
→ Рекомендація наступного циклу: **реальна email-доставка + check-in контент**.

---

## Історія гейтів
- 2026-07-05: D7 board → **NO-GO** (симуляція платежів, нема бекапів/комплаєнсу/observability).
- 2026-07-05: W1 — Alembic-міграції (B6 закрито) + DB append-only тригери (B5 закрито, owner-proof). Readiness 22 → ~32.
- 2026-07-05: D9 — виконаний DR-drill (backup+restore+фінансова звірка PASS двічі). B2-restore доведено; авто-розклад+offsite → managed Postgres. Answer: PARTIALLY. Readiness ~32 → ~40.
- 2026-07-05: B1 — Stripe Connect адаптер (destination charges) + webhook (підпис/ідемпотентність/dispatch) + reconciliation. Доведено проти mock; sandbox pending keys. Answer: PARTIALLY. Readiness ~40 → ~50.
- 2026-07-06: OAT-01 — 10 бізнес-сценаріїв з порожньої системи. Хребет (onboard→book→pay→cancel/refund→complete→payout→reconcile) PASS без ручного ремонту; операційний шар (check-in/клінінг/support/incident/dispute/нотифікації) = dead-end (404). Answer: PARTIALLY — платформа тримає гроші/бронювання, операції ручні off-platform. 26 тестів зелені.
- 2026-07-06: OAT-02 — Operational Notification Layer (domain_events append-only + notification routing + `/bookings/{id}/state` + founder-feed + incidents). 7 подій, guest/host/founder нотифікації (log-based канали), operational_state, timeline reconstruction. 4 acceptance-gate PASS. Warfare спіймав і виправлено latent double-capture race (FOR UPDATE на payment). 34 тести зелені. Founder ops-visibility ❌→✅. Readiness ~50 → ~56.

## Робочий режим (постійний, без нових D-етапів)
Build → Verify → Release Gate → Repeat. Кожен цикл: одна задача критичного
шляху → доказ (тести/інваріанти/drill) → оновити цей файл і перевірити, чи
змінився шлях. Наступний цикл: **B1 реальний StripeConnectProvider**.
