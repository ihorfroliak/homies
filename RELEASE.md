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

- **Технічний аудит коду (2026-07-28)** — доказовий, read-only: 4 High / 9
  Medium / 9 Low. **Закрито всі 4 High:**
  - **H1** — валюта. Ledger сумує баланси по всіх валютах без scoping, тому
    non-PLN лістинг тихо ламав escrow-математику й знецінював інваріант I5.
    Тепер приймається лише `settings.default_currency`.
  - **H2** — webhook. Сира Stripe-подія комітиться **до** диспетчу, тож збій
    хендлера більше не стирає audit-запис. Дефект спершу **відтворено**
    (unknown intent → 404, нуль рядків), потім доведено закриття тим самим
    скриптом. `processed_at IS NULL` = dead-letter маркер.
  - **H3** — ідемпотентність Stripe. Ключ інтенту містив `uuid4()`, попри
    коментар про booking-derived: retry після невдалої транзакції створював
    другий інтент на ту саму бронь — подвійне списання. Тепер ключ = id броні.
  - **H4** — транзакційні межі. Виклик Stripe стояв між `SELECT listing FOR
    UPDATE` і `commit()`, тож усі конкурентні броні того самого об'єкта
    шикувались за одним мережевим викликом. Тепер провайдер викликається після
    коміту. Доведено **фальсифікованим** тестом: проти старого коду він падає
    («row lock is still held across provider I/O»), проти нового — проходить.
  - Доказ: **171 тест зелений на реальному Postgres** (+8-тредовий race-тест
    на унікальність event id), warfare + refund_warfare + live_smoke PASS,
    `recon ok=true`, `grand_total=0`.

### 2. Що ще блокує наступний реліз (Gate 1)?
- **B1-решта:** реальні Stripe **test-ключі** → спостерегти sandbox (3DS/SCA,
  transfers, partial capture, disputes, payout events). Адаптер готовий; це
  крок «дати ключі + прогнати checklist», не код.
- **B2-решта:** авто-розклад бекапів + offsite/PITR → managed Postgres.
- **B3** agency-договір + T&C + KYC через Stripe (юр-трек, паралельно).
- (Gate 2: auto-void, rate-limit, observability, MFA, chargeback/clawback.)

### 3. Одна наступна задача з найбільшим наближенням до prod?
**Усі 4 High-знахідки аудиту закрито.** Далі — Medium, і найбільший ROI дає
**M9 — quality gates у CI**: зараз CI не має ні typecheck, ні coverage, ні
сканування залежностей/секретів, ні `docker build`. Тобто зламаний Dockerfile
або вразлива залежність проходять повз зелений білд. Це дешево, не чіпає
грошову логіку й підвищує довіру до кожного наступного циклу.
Далі: **OBS-1** (справжній health-check + метрики) → **M4** (пінування залежностей).

<details><summary>Попередній запис (нотифікації)</summary>

Доставка нотифікацій тепер durable+retryable+observable (OAT-03), але
email-канал = stub (SMTP-адаптер є, без реальних creds). Наступний ROI:
- **Реальний email-провайдер** (`EMAIL_PROVIDER=smtp` + creds, або SendGrid-
  адаптер) — swap за абстракцією, не редизайн + **check-in інструкції** (коди/
  ключі в template payload).
- Потім: **auto-void неоплачених** (закрити ghost-booking DoS).
- Без коду паралельно: Stripe test-ключі (B1→YES) + юр-трек (B3).

</details>

---

## Історія гейтів
- 2026-07-05: D7 board → **NO-GO** (симуляція платежів, нема бекапів/комплаєнсу/observability).
- 2026-07-05: W1 — Alembic-міграції (B6 закрито) + DB append-only тригери (B5 закрито, owner-proof). Readiness 22 → ~32.
- 2026-07-05: D9 — виконаний DR-drill (backup+restore+фінансова звірка PASS двічі). B2-restore доведено; авто-розклад+offsite → managed Postgres. Answer: PARTIALLY. Readiness ~32 → ~40.
- 2026-07-05: B1 — Stripe Connect адаптер (destination charges) + webhook (підпис/ідемпотентність/dispatch) + reconciliation. Доведено проти mock; sandbox pending keys. Answer: PARTIALLY. Readiness ~40 → ~50.
- 2026-07-06: OAT-01 — 10 бізнес-сценаріїв з порожньої системи. Хребет (onboard→book→pay→cancel/refund→complete→payout→reconcile) PASS без ручного ремонту; операційний шар (check-in/клінінг/support/incident/dispute/нотифікації) = dead-end (404). Answer: PARTIALLY — платформа тримає гроші/бронювання, операції ручні off-platform. 26 тестів зелені.
- 2026-07-06: OAT-02 — Operational Notification Layer (domain_events append-only + notification routing + `/bookings/{id}/state` + founder-feed + incidents). 7 подій, guest/host/founder нотифікації (log-based канали), operational_state, timeline reconstruction. 4 acceptance-gate PASS. Warfare спіймав і виправлено latent double-capture race (FOR UPDATE на payment). 34 тести зелені. Founder ops-visibility ❌→✅. Readiness ~50 → ~56.
- 2026-07-09: OAT-03 — Reliable delivery: transactional outbox (notifications) + background worker + retry state machine (pending→processing→delivered|failed→dead) + exponential backoff/jitter + channel abstraction (in_app/email-stub/SMTP/sms) + templates + Prometheus /metrics. 6 acceptance-gate PASS. Live: worker auto-delivers, queue→0, duplicate-worker SKIP LOCKED overlap=0. Warfare без регресій. 41 тест зелений. Readiness ~56 → ~62.

- 2026-08-03: Технічний аудит коду (read-only, доказовий) → 4 High/9 Medium/9 Low. Закрито **H1** (єдина підтримувана валюта — ledger не має currency-scoping) і **H2** (сира webhook-подія комітиться до диспетчу; дефект відтворено й доведено закритим). 158 тестів на реальному Postgres, warfare/refund/live_smoke PASS, recon ok=true. Закрито також **H3** (ключ = id броні) і **H4** (виклик провайдера після коміту, доведено фальсифікованим тестом). **Усі 4 High закрито.** Наступне: M9 (quality gates у CI).

## Робочий режим (постійний, без нових D-етапів)
Build → Verify → Release Gate → Repeat. Кожен цикл: одна задача критичного
шляху → доказ (тести/інваріанти/drill) → оновити цей файл і перевірити, чи
змінився шлях. Наступний цикл: **B1 реальний StripeConnectProvider**.
