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

**Урок:** `create_all` не додає колонки до наявних таблиць — жива dev-БД
розійшлась із моделлю (operational_state). Alembic — джерело істини схеми;
dev-БД треба ресетити/мігрувати, не покладатись на create_all для змін.

## 2026-07-09 — OAT-03 Reliable notification delivery (outbox + worker)

**Збудовано:** notifications-таблиця стала **transactional outbox** (пишеться
`status=pending` у тій самій транзакції, що подія+мутація). Delivery винесено
з `emit()` у **background worker** (`events/worker.py`, потік у lifespan,
вимкнений у тестах). State machine: pending→processing→delivered|failed→dead.
Retry: exponential backoff+jitter, `max_attempts` конфіг, permanent→dead.
`claim_batch` — `FOR UPDATE SKIP LOCKED` (дублі-воркери не беруть той самий
рядок). Channel-абстракція: InApp/StubEmail/**SMTP**/StubSms (swap через
`EMAIL_PROVIDER`). Templates (template_id+locale+variables, render не падає).
Prometheus `/metrics` (delivered/failed/dead/retries/latency/queue_depth).
Founder-аудит: `/admin/notifications` (status/attempts/last_error),
`?status=dead` (dead-letter), `/admin/notifications/queue`.

**Доведено:** 7 OAT-03 сценаріїв (timeout→retry→recovery, permanent→dead,
worker-restart-reclaim, dup-event, delivery-fail-не-чіпає-гроші, rollback),
6 acceptance-gate PASS. Live: worker авто-доставляє, черга→0,
**duplicate-worker overlap=0** (SKIP LOCKED), /metrics віддає homies_*.
Warfare без регресій, 41 тест зелений, ruff чистий. Docs:
`docs/design/oat-03-outbox-and-delivery.md`, `docs/reviews/2026-07-09-oat-03-report.md`.
Success-condition виконано: нічого не зникає — delivered АБО observable-as-dead.
Readiness ~56 → ~62.

**Далі (за RELEASE.md):**
- [ ] **Реальний email-провайдер** (`EMAIL_PROVIDER=smtp`+creds / SendGrid) + check-in інструкції (коди/ключі в template payload) — наступний цикл.
- [ ] Auto-void неоплачених (ghost-booking); turnover-задача; auto-complete таймер.
- [ ] Support-модуль (S6), повні disputes (S8), curated attention-в'ю.
- [ ] Без коду: Stripe test-ключі → B1 YES; юр-трек B3; managed Postgres.
- [ ] Gate 2: chargeback/clawback, rate-limit, observability-стек, MFA, GitHub CI.
- [ ] Chat 03: auth-модуль — схема БД, міграції (Alembic), реєстрація/логін/JWT.
- [ ] GitHub Projects дошка з фазами.

## 2026-09-24 — TASK-000: канон, governance, карта конвергенції

**Зроблено:** `docs/canonical/` (00-AUTHORITY … 06-ROADMAP, 04 — дослівна
Domain Schema v1, 04a — уточнення засновника, IMPLEMENTATION-CONVERGENCE);
новий стислий `CLAUDE.md`; `AGENTS.md` для Codex (аудитор, read-only);
`docs/tasks/` (шаблон, TASK-000, чернетка TASK-001). Чужі незакомічені зміни
(159 шляхів) збережено без втрат у локальних гілках
`reference/ts-drizzle-schema-v1`, `preserve/foreign-continuity-2026-09`,
`preserve/worktree-snapshot-2026-09-24` (звірено по blob-хешах). booking,
payments, ledger, listings позначено LEGACY_DORMANT; тест
`test_phase1_boundaries.py` забороняє Phase-1 модулям їх імпортувати.
Старі стратегічні документи — банер HISTORICAL.

**Вивчено:** два агенти в одному брудному checkout → виправлення іншої сесії
потрапило в мій коміт `62a4add` без атрибуції, а мої помилки mypy я тоді
хибно списав на кеш. Звідси правило одного писаря і окремих worktree (05 §3–§4).

**Далі:** TASK-001 — незалежний аудит Codex C1–C8 (C8 — security-фокус).
Два CANONICAL DECISION REQUIRED чекають засновника (мінімальний строк
LONG_TERM; підтип для `aparthotel_unit`).

## 2026-09-24 — TASK-002: ремонт фундаменту після аудиту Codex (F-01…F-09)

**Зроблено** (гілка `claude/TASK-002-foundational-repair`, чотири цикли):
- **R1** — `app/composition.py`: `create_phase1_app()` більше не маршрутизує
  short-stay/booking/payments/host-payouts/legacy-admin і не запускає
  booking-expiry worker. Legacy-тести йдуть через `tests/legacy_runtime.py`
  (маркер `legacy_runtime`). Runtime-тести на справжньому app + ширший AST-тест.
  Знайдено: тест «кожен маршрут задокументований» був порожнім на FastAPI 0.139
  (`_IncludedRouter`); NaN у тілі давав 500 замість 422.
- **R2** — публікація, revoke і архівування простору серіалізовані на рядку
  Property; умовний UPDATE статусу. Координати: API + CHECK у БД, міграція
  відмовляє, а не «вгадує». Рішення засновника: LONG_TERM без 6-місячної межі;
  aparthotel_unit — підтип APARTMENT, публікація fail-closed.
- **R3** — Pillow замість власного парсера: decode → бюджет пікселів →
  орієнтація → sRGB → нове зображення з пікселів → re-encode → повторний decode.
  Потокове читання тіла з межею; старі файли C8 у карантині до `reprocess_media`.
- **R4** — квота розкриттів контактів, створення розмов — під блокуванням рядка
  users; переходи стану перегляду умовні під блокуванням рядка; DST: лише
  однозначний локальний час; partial UNIQUE для активної розмови.
- Виправлено хибнопозитивний тест від'ємної ціни.

**Вивчено:** «dormant» як мітка нічого не гарантує — перевіряти треба
скомпонований застосунок. Мутаційні тести повинні включати і міграції (CHECK),
і локи, інакше тест може бути зеленим з будь-якою реалізацією.

**Далі:** цільовий повторний аудит Codex точного SHA. Потім — вузька міграція
типу/підтипу нерухомості (пропозиція, чекає затвердження).

## 2026-09-24 — TASK-004: атомарна авторизація публікації (F-04)

**Контекст:** TASK-003 (Codex) прийняв вісім закриттів TASK-002, але F-04
лишився частково відкритим: відкликання членства чи мандата, призупинення
організації, архівування юридичної особи або закінчення мандата могли
статися між останньою перевіркою і записом `active`.

**Зроблено:** `authority.authorize_for_mutation` — під блокуванням Property
блокує FOR SHARE усі рядки кожного чинного ланцюжка й повторно оцінює їх за
годинником БД, у тій самій транзакції, що й умовний UPDATE статусу. Шляхи
відкликання блокують свій рядок перед читанням; додано сервісні примітиви
статусу організації та юридичної особи (без нових endpoint). 27 PG-тестів:
кожна втрата в обох серійних порядках, очікування блокувань через
`pg_blocking_pids`, прострочення, вцілілий ланцюжок, відсутність розширення
scope; 9 мутантів.

**Вивчено:** блокування «координаційного рядка» захищає лише від змін, які
теж беруть цей рядок. Для ланцюжка з кількох таблиць треба захищати сам доказ.

**Далі:** TASK-005 — цільовий повторний аудит Codex точного SHA.

## 2026-09-25 — TASK-006: цілісність повноважень, борг аудиту TASK-005

**Контекст:** TASK-005 (незалежний аудит `dfa3254`) закрив F-04 і прийняв
фундамент C1–C8 (`dfa3254` = HOMIES FOUNDATION BASELINE 001), але знайшов
чотири нові пункти N-01…N-04.

**Зроблено:**
- N-02 (P2): `accept_invitation` блокує рядок членства FOR UPDATE до читання й
  приймає лише рядок, що досі INVITED — застаріле прийняття більше не
  перезаписує відкликання.
- N-01 (P3): захищене рішення оцінює ланцюжки лише через заблоковані рядки
  доказу; ланцюжок, що з'явився під час очікування блокувань, дає 409, а
  наступна спроба його використовує. Один прохід, без циклу, без глобального
  блокування.
- N-03 (P3): тести обох порядків для `person_legal_parties`,
  `organization_legal_parties`, `representation_mandate_scopes`,
  `property_authority_scopes`; очікування прив'язане до pid публікації;
  мутанти B01–B07.
- N-04 (P3): `tests/conftest.authorization_date()` (UTC) замість локального
  `date.today()` там, де дата означає дату авторизації. Продуктове правило
  (UTC) не змінене; питання польської цивільної дати — окреме рішення.

**Вивчено:** блокувати доказ недостатньо, якщо рішення може спертися на
рядок поза доказом — рішення має читати лише те, що заблоковано.

**Далі:** незалежний огляд N-01/N-02; потім — вертикальний зріз географії/адреси
для всієї Польщі з архітектурою, готовою до Європи.

## 2026-09-25 — TASK-008: фінальне укріплення фундаменту (TASK-007 N-05…N-10)

**Контекст:** TASK-007 прийняв N-02…N-04, але N-01 лишився частково відкритим
через N-05: рядок доказу, видалений і вставлений знову з тим самим ключем, поки
публікація чекала на блокування, проходив без блокування. Baseline 002 —
кандидат, ще не прийнятий.

**Зроблено:**
- N-05: `_lock_proof` повертає рядки, які FOR SHARE справді повернув; рішення
  оцінюється лише через них (плюс обмеження на пари (authority, scope) і id
  мандата). Замінений рядок → 409 з `Retry-After: 0`, нова спроба блокує його й
  публікує.
- N-06: поведінкові тести для кожного суттєвого обмеження `within`; ті, що
  випливають зі схеми, — еквівалентні мутанти.
- N-07: accept-vs-accept — другий чекає ще до читання рядка; без deadlock.
- N-08: одна послідовність — чотири результати 403/404/409/200.
- N-09: запрошення блокує рядок і змінює лише REVOKED → INVITED.
- N-10: одночасні перші запрошення — savepoint, переможець вирішує, обидва 202.
- 409 публікації задокументовано в OpenAPI; коментар про чергу блокувань виправлено.

**Вивчено:** «заблоковано» — це те, що повернув оператор блокування, а не
ключ, прочитаний до нього. Нове повноваження під час очікування взагалі не може
з'явитися: його INSERT чекає на FOR UPDATE рядка Property.

**Далі:** незалежний фінальний аудит фундаменту (не сесія-будівельник).


## 2026-09-25 — TASK-010: географія, адреса, класифікація + доктрина продукту

**Контекст:** Foundation Baseline 002 (`3623184`) прийнято після двох
незалежних аудитів TASK-009 (Codex і Claude Code); обидва звіти збережено
дослівно в `docs/reviews/2026-09-25-task009-*`.

**Зроблено:** `07-PRODUCT-GROWTH-DOCTRINE` (десять питань A1–A10, принципи,
позиціонування, North Star). Модуль `geography`: Country (ISO) →
AdministrativeArea (будь-яка глибина, `kind_code` країни, тригер проти циклів)
→ Locality; GeoArea для районів пошуку; GeoSource/GeoExternalRef для TERYT/PRG
— ідентифікатори поза ключами. Структурована адреса (рівень будинку, квартира
на Property, точна точка без змін), публічне `place` лише з довідкових
сутностей. Класифікація: category APARTMENT|HOUSE + subtype; ROOM відхилено;
aparthotel і далі fail-closed. Міграція додавальна: наявні Property отримали
UNSTRUCTURED-адресу з текстом як є, без вгадування. `municipality` —
необов'язкова.

**Вивчено:** два «загублені» фонові прогони PG-тестів одночасно в одній БД
блокують один одного — перед повторним прогоном перевіряти живі процеси.
`lazy="joined"` на Property ламає `FOR UPDATE` координаційного замка в
PostgreSQL (outer join) — лише `lazy="select"`. Три гоночні тести фундаменту
доводили порядок комітів порядком HTTP-відповідей (борг P3 TASK-009) і
почали «мигати»; тепер вони доводять порядок з БД: `backend_xid` паузованої
публікації на захищеному бар'єрі та перевірка, що ця транзакція вже не
виконується, коли конкурент комітить. Перевіряти саме xid, а не стан
бекенду: після коміту той самий бекенд уже виконує наступну транзакцію.

**Перевірено:** SQLite 740 passed / 207 skipped; PostgreSQL/PostGIS 946
passed / 1 skipped; ruff, mypy, OpenAPI drift чисто; мутації TASK-010 10/10
вбито; регресія TASK-004/006/008 без змін (E01–E04 виживають, як і раніше, —
у коді залишені).

**Далі:** адюдикація TASK-010; наступний вертикальний зріз обирає засновник.
