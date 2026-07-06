# Dev Log

Short entries: what was done / what was learned / what's next.
(Working language: Ukrainian — це внутрішній журнал.)

## 2026-07-05 — Репозиторій створено, Chat 01 закрито, старт Фази 0

**Зроблено:**
- Імпортовано майстер-план із проєкту Homies (Claude): `docs/PROJECT_CHARTER.md` (v1.0).
- Створено monorepo `homies/` за структурою charter §7, адаптованою під рішення про **модульний моноліт** (`backend/` замість `services/*`).
- **Закрито Chat 01 (System Design & Contracts):** написано 6 ADR (`docs/adr/`) — модульний моноліт, гроші в мінорних одиницях, PostgreSQL+PostGIS, подієва інтеграція, contract-first API + Spectral, monorepo/trunk-based.
- Відтворено контракти: OpenAPI 3.1 (auth, listings, booking) + AsyncAPI 3.0 (16 подій, 5 каналів) + `.spectral.yaml` з документованою політикою.
- Walking skeleton: FastAPI-моноліт із `/healthz`, тест, Dockerfile, `docker-compose` (Postgres+PostGIS, Redis, Meilisearch, NATS), `Makefile` (`make up`), CI (GitHub Actions: lint+test+валідація контрактів).

**Вивчено/зафіксовано:**
- Bounded contexts ≠ одиниці деплою — мікросервісність відкладена свідомо (ADR-0001).
- Split "policy vs facts" для календаря доступності (як графік роботи vs журнал бронювань).

**Верифікація стека:**
- [x] `make up` end-to-end: усі 5 контейнерів піднялись, `GET /healthz` → 200 `{"status":"ok","env":"local"}`.
- ⚠️ На машині лишився старий контейнер `homies-postgres` (створений раніше, тримає порт 5432 хоста) — новий `db` працює у внутрішній мережі compose, але з хоста на 5432 відповідає старий. Вирішити: або видалити старий контейнер, або змінити мапінг порту в `ops/docker-compose.yml`.

## 2026-07-05 (пізніше) — Пакет бізнес-архітектури (Chat 13/01-розширення)

**Зроблено:** повний пакет бізнес-архітектури в `docs/business/` (00–07):
бізнес-модель і актори, процеси і флоу (Guest/Host/Admin), автоматизація
(automation-first), модулі й дані (карта розширена 11→17 контекстів:
+Ledger, Messaging, Disputes, Trust&Safety, Support, Loyalty), бізнес-правила
і статусні машини всіх сутностей, 4-рівнева модель суперечок зі SLA,
прогалини та пріоритизація MVP→V3.

**Ключове:** гроші тільки через Ledger (подвійний облік); адмінка = черги
винятків + real-time, не CRUD; статусні машини — джерело істини.

**Чекає на затвердження** (крок 13): після нього — монетизація, ціноутворення,
UI/UX; технічно — ADR для Ledger + оновлення контрактів новими подіями/статусами.

## 2026-07-05 (вечір) — Стратегічна трансформація: Homies = бізнес

**Рішення засновника (docs/strategy/00-DECISIONS.md):** D1 бізнес, не
портфоліо; D2 Stripe Connect; D3 диференціація managed hosting +
HeyHomie-вертикаль; D4 далі Chat 03.

**Пакет docs/strategy/ (00–07):** життєздатність (чистий маркетплейс
відхилено; вертикально інтегрований оператор → managed marketplace →
Hospitality OS), позиціювання «Managed Stays / здай ключі — отримуй
дохід», потоки доходу ранжовані (managed fee + клінінг + B2B — ядро),
аудит функцій (Operations+channel manager у ядро MVP; Search/CRM/
Marketing/повні Disputes — вниз/у V1), AI-first оргдизайн (<1 чол/1000
об'єктів), фінархітектура на Connect (ліцензія не потрібна), регуляторний
реєстр PL, growth flywheel на чужому OTA-трафіку, KPI-фреймворк,
80 ранжованих покращень. MVP переозначено: «петля виручки оператора»
з 10 об'єктами.

## 2026-07-05 (ніч) — D4 вертикальний зріз + D5 hardening (КОД)

**D4 (backend/app):** модульний моноліт FastAPI+SQLAlchemy, 6 модулів —
identity (register/login scrypt, JWT+refresh-ротація, RBAC guest/host/admin,
host onboarding = симуляція Stripe Connect), listings (CRUD+publish+блокування),
booking (Idempotency-Key, інтервальна доступність, ціна=ночі×ставка, cancel/
complete, календар-проєкція), payments (PaymentProvider-шов Stripe Connect,
webhook, refund, payout-оркестрація), ledger (подвійний облік, єдина точка
руху грошей, reconciliation), admin (read-only видимість + audit). Гроші —
цілі мінорні одиниці (ADR-0002), audit_log append-only. Документ:
`docs/design/d4-vertical-slice.md`.

**D5 hardening (реальні P0-фікси, не лише аудит):** (1) Postgres exclusion
constraint проти подвійного бронювання (btree_gist, daterange &&), IntegrityError→409;
(2) late-success auto-refund (webhook succeeds після cancel → capture+refund,
escrow не зависає); (3) секрет на webhook (трастовий кордон; прод — Stripe-Signature);
(4) ORM-guard append-only на ledger+audit; (5) escrow≥0 інваріант у payout +
fix проводки з fee=0. Документ: `docs/design/d5-hardening.md` (9 deliverables:
race register, fraud map, ledger spec, concurrency model, Stripe edge cases,
інваріанти I1-I10, distributed failure, risk heatmap, P0 backlog).

**Верифікація:** 12 pytest зелені (e2e booking→payment→payout→ledger, refund,
void, RBAC, refresh-ротація, overlap, блокування, валідації, D5: webhook-401,
late-refund, ledger immutability), ruff чистий. Живий смоук на docker+Postgres:
подвійне бронювання→409, webhook-wrong-secret→401, повний цикл, recon ok=True,
platform_revenue=15750 (15% з 105000), escrow=0.

## 2026-07-05 (ніч-2) — D7 board (NO-GO) + D8 release-loop + W1 execution

**D7 Production Readiness Board:** evidence-only Go/No-Go → **NO-GO**
(`docs/reviews/2026-07-05-d7-production-readiness-board.md`). Докази командами:
провайдер = симуляція, нема бекапів/міграцій/observability/MFA/rate-limit,
комплаєнс не збудований. Launch readiness 22/100.

**D8 release optimizer + процес:** `docs/RELEASE_PLAN.md` (критичний шлях до
першого безпечного бронювання; managed-модель коротшає шлях — контрольовані
сторони; 3 гейти; топ-задачі за ROET). Впроваджено цикл **Build→Verify→Gate**:
живий трекер `RELEASE.md` (3 питання) + правило в CLAUDE.md.

**W1 виконано (код, не план):**
- **B6 закрито:** Alembic (`backend/alembic/`) + перша міграція (вся схема +
  exclusion constraint). Верифіковано: upgrade/downgrade/повтор зелені.
- **B5 закрито owner-proof:** DB-тригери append-only на ledger+audit.
  Доведено: прямий UPDATE/DELETE через psql відбито на рівні БД (не лише ORM).
- Startup-guard і міграція узгоджені; 12 pytest зелені, warfare без регресій,
  живий смоук чистий. Readiness 22 → ~32.

## 2026-07-05 (ніч-3) — D9 Disaster Recovery (виконаний drill)

**B2-restore закрито доказом.** Скрипти `backend/scripts/backup/`
(backup.sh: pg_dump→gzip→AES-256→sha256; restore.sh: checksum-verify→
decrypt→pg_restore; verify_restore.py: фінансова звірка; dr_drill.sh).
Виконаний drill проти живого Postgres: backup (90 КБ, шифрований) →
restore **RTO 4s** → фінансова звірка PASS (grand_total=0, escrow=0,
paid_without_payout=0, counts збіглись) → **accidental DROP TABLE
journal_lines → restore → дані повернулись, звірка PASS**. Append-only
тригери + exclusion constraint переживають restore. Runbook:
`docs/runbooks/dr-database-recovery.md`. Звіт+оцінки:
`docs/design/d9-disaster-recovery.md`. Answer: **PARTIALLY** (локальна
катастрофа — виживає; тотальна втрата хоста — ні, offsite/авто-розклад
відкриті → managed Postgres). Readiness ~32 → ~40.

## 2026-07-05 (ніч-4) — B1 Stripe Connect адаптер

**Збудовано за наявним `PaymentProvider`-швом (0 змін домену/ledger):**
`StripeConnectProvider` (destination charges + application_fee, ADR-0007),
config-селектор (`payment_provider=simulation|stripe`, default simulation),
Stripe-webhook `/v1/payments/webhook/stripe` (перевірка підпису→400, сира
персистенція `webhook_events`, ідемпотентність за stripe_event_id, диспетч
succeeded/failed/refunded у ledger), обробники process_intent_failed/
process_charge_refunded, reconciliation-engine (payment↔ledger + Stripe-
balance cross-check), admin `/payments/reconciliation`. Міграція оновлена
(webhook_events). Stripe SDK 15.3.

**Доведено (проти FakeStripe, без мережі):** bad-sig→400, дублікат event→
1 capture (no double money), out-of-order/failed безпечно, 503 без stripe-
провайдера. **16 pytest зелені, ruff чистий, warfare без регресій, live
503 у simulation.** Звіт: `docs/design/b1-stripe.md`, ADR-0007.

**Чесна межа:** реальних Stripe-ключів нема → sandbox (3DS/SCA, transfers,
partial capture, disputes, payout) **не спостережено**. Answer: **PARTIALLY**.
Шлях до YES: дати test-ключі + прогнати sandbox-checklist (b1-stripe §5), без
нового коду. Readiness ~40 → ~50.

## 2026-07-06 — OAT-01 Operational Acceptance Testing

10 бізнес-сценаріїв з порожньої системи (`tests/test_oat_business.py`, всі
відпрацювали). **Хребет** (S1 onboarding→bookable, S2 booking→confirmed+
reconciled, S5 cancel→refund+availability, S9 financial closing) **PASS без
ручного ремонту даних**; S4 фін-частина (complete→payout→recon=0) PASS.
**Dead-end (404, доведена відсутність):** S3 check-in/ops, S6 support,
S7 incident, S8 dispute; S10 founder ops-view. Money-visibility ✅.
Answer: **PARTIALLY** — платформа тримає гроші/бронювання безпечно;
check-in/клінінг/support/dispute/нотифікації в платформі **не існують** →
на пілоті операції ручні off-platform (HeyHomie+засновник), як у D8-плані.
Звіт: `docs/reviews/2026-07-06-oat-01-report.md` (матриця, gap-и, risk-
register, Top-20 ROI). 26 тестів зелені.

## 2026-07-06 — OAT-02 Operational Notification Layer

**Збудовано (модуль `events/`, brutally-minimal, без event-bus):**
`domain_events` (append-only DB-тригер, ідемпотентний за dedup_key,
correlation_id=booking_id), `notifications` (routing guest/host/founder ×
email/sms/in_app, log-based канали, best-effort), `incidents` (мін-хук S7/S8).
7 подій (Created/Confirmed/CheckInAvailable/CheckInCompleted/Cancellation/
Payout/IncidentOpened) emit-яться в тій самій транзакції, що й зміна стану.
Нові ендпоінти: `POST /bookings/{id}/checkin`, `GET /bookings/{id}/state`
(lifecycle+financial+operational+timeline), `GET /me/notifications`,
`POST/GET /admin/incidents`, `GET /admin/founder-feed`,
`GET /admin/notifications?status=failed` (dead-letter). `operational_state`
на booking (none→checkin_available→checked_in→checked_out). Міграція+guard
оновлені (domain_events у append-only список).

**Доведено:** 8 OAT-02 сценаріїв (подія→нотифікація→стан), 4 acceptance-gate
PASS (0 orphan, event-state consistency, S1/S2/S5 notif-paths, timeline
reconstruction). **Warfare спіймав latent double-capture race** під 200
concurrent webhook — виправлено root cause (`SELECT FOR UPDATE` на payment);
тепер детерміновано 1 capture. 34 тести зелені, ruff чистий, reconciliation
ok=True double_capture=[]. Docs: `docs/design/oat-02-architecture.md`,
`docs/reviews/2026-07-06-oat-02-report.md`. Founder ops-visibility ❌→✅.

**Далі (за RELEASE.md):**
- [ ] **Реальна email-доставка** нотифікацій (провайдер за channel-абстракцією) + check-in інструкції (коди/ключі в payload) — наступний цикл.
- [ ] Auto-void неоплачених (ghost-booking); turnover-задача; auto-complete таймер.
- [ ] Support-модуль (S6), повні disputes (S8), curated attention-в'ю.
- [ ] Без коду: Stripe test-ключі → B1 YES; юр-трек B3; managed Postgres.
- [ ] Gate 2: chargeback/clawback, rate-limit, observability, MFA, GitHub CI.

**Урок:** `create_all` не додає колонки до наявних таблиць — жива dev-БД
розійшлась із моделлю (operational_state). Alembic — джерело істини схеми;
dev-БД треба ресетити/мігрувати, не покладатись на create_all для змін.
- [ ] Chat 03: auth-модуль — схема БД, міграції (Alembic), реєстрація/логін/JWT.
- [ ] GitHub Projects дошка з фазами.
