# D6 — Production Warfare Report (реальні атаки на живий стек)

> **Це не аналіз — це виконані атаки.** Харнеси (`scripts/` scratchpad)
> били по запущеному `homies-api-1` + `homies-db-1` (Postgres 16, docker),
> паралельними потоками (httpx + ThreadPoolExecutor). Усі числа нижче —
> фактичний вивід, не припущення. Дата: 2026-07-05.

## 0. Чесні межі цього прогону

- **Масштаб**: реально запущено 60–200 конкурентних запитів, не літеральні
  10 000. DB-рівнева гарантія (exclusion constraint, row-locks) **однакова
  при будь-якому N** — раса тригериться вже при десятках. Не претендую на
  навантажувальний тест пропускної здатності.
- **Один uvicorn-воркер**: FastAPI виконує sync-ендпоінти в threadpool
  (до 40) → **реальна конкурентність на БД відбулася**; але не
  мультипроцес/мультинод.
- **Провайдер платежів — симуляція.** Partial capture, chargeback,
  payout reversal, out-of-order Stripe-події **не тестовані, бо не
  побудовані** (P1). Не можна атакувати те, чого нема. Чесно.
- **Розподілені збої** (replica lag, черги, network partition між
  сервісами) **структурно відсутні** — моноліт з одною БД (ADR-0001).
  Це не «пройдено», це «не існує на цій стадії».

## 1. System Stress Test Report (виконані сценарії)

| # | Сценарій | Параметри | Фактичний результат | Вердикт |
|---|---|---|---|---|
| 1 | Booking storm, **ті самі** дати | 60 конкурентних guest-ів | `{409: 59, 201: 1}` — рівно 1 бронювання | **PASS** |
| 2 | Booking storm, **різні** дати | 30 конкурентних | `{201: 30}` — усі успішні, без корупції | **PASS** |
| 3 | Retry storm (той самий guest+ключ) | 20 конкурентних | `{201: 20}`, але **distinct booking_ids = 1** | **PASS** (money-safe) |
| 4 | Webhook replay storm | той самий intent ×200 конкурентно | `{200: 200}`, **capture-проводок = 1**, escrow-delta рівно −90000 | **PASS** |
| 5 | Double payout | 10 конкурентних payout-run | сумарно оплачено бронювань = **1** | **PASS** |
| 6 | Ghost booking (неоплачений блокує) | 2-й guest на ті самі дати | got **409** (заблоковано неоплаченим pending) | **CONFIRMED GAP** |
| 7 | Reconciliation після всього хаосу | — | `ok=True, grand_total=0`, escrow=0, всі host_payable=0 | **PASS** |
| 8 | **Крах БД посеред навантаження** | `docker stop` db + booking + restart | під час простою → **conn_error** (не фантом); після — `ok=True, total=0` | **PASS** |
| 9 | Refund-abuse / cancel-rebook loop | pay→cancel→refund ×5 на тих самих датах | щоцикл escrow −120000→0, дати звільнено, 5 refunded, recon=0 | **PASS** |
| 10 | Boundary: zero-night booking | check_in==check_out | **422** відхилено | **PASS** |
| 11 | Webhook signature bypass | невірний X-Webhook-Secret | **401** (сценарій 4 харнесу) | **PASS** |

## 2. Breakdown Analysis (що знайдено)

### F-1. Ghost booking — inventory DoS (CONFIRMED, P1)
- **Клас:** відсутність TTL на неоплачені pending.
- **Атака:** зловмисник створює N неоплачених бронювань → `BLOCKING_STATUSES`
  включає `pending` → календар host-а заблокований безстроково без єдиної
  копійки.
- **Підсистема:** booking + availability.
- **Серйозність:** операційна/довіра (не пряма фін. втрата) — але вбиває
  supply, головний актив операторської моделі.
- **Відтворюваність:** 100% (сценарій 6).
- **Фікс (P1):** auto-void неоплачених через 15–30 хв (scheduled event) +
  ліміт активних неоплачених на guest + rate limiting. **Не побудовано.**

### F-2. Idempotency-key не повністю атомарний (LATENT, P2)
- **Клас:** TOCTOU між перевіркою `existing` та insert.
- **Спостереження:** у сценарії 3 всі 20 повторів повернули той самий
  booking (timing рознесло їх) — але при точному збігу вікна другий потік
  може отримати 409 «Dates not available» замість оригінального
  бронювання.
- **Серйозність:** довіра/UX. **Money-safe** — подвійного бронювання чи
  списання не буде (unique-constraint + exclusion-constraint ловлять).
- **Фікс (P2):** `INSERT ... ON CONFLICT (guest_id, idempotency_key) DO
  NOTHING RETURNING` + повторне читання при конфлікті → детермінований
  idempotent-replay.

### Що НЕ зламалося (доведено, не заявлено)
- Подвійне бронювання — **фізично неможливе** (exclusion constraint,
  59/60 відбито БД).
- Подвійний capture під штормом 200× — **1 проводка**.
- Подвійна виплата під 10 конкурентними run — **1 оплата**.
- Ledger після всього хаосу + краху БД — **зводиться в нуль**.
- Крах БД посеред транзакції — **без часткової корупції** (ACID/WAL).

## 3. System Weakness Map

| Кластер | Стан | Деталі |
|---|---|---|
| **Concurrency** | 🟢 сильний | double-book, webhook, payout — усі ідемпотентні під штормом; латентний idempotency-TOCTOU (F-2, money-safe) |
| **Payments** | 🟡 частковий | ідемпотентність доведена; але провайдер — симуляція, chargeback/reversal/partial-capture не існують (P1) |
| **Ledger** | 🟢 сильний | append-only, зводиться в нуль після хаосу і краху БД, escrow≥0 |
| **Booking** | 🟡 частковий | конкурентність надійна; **ghost-booking DoS (F-1, P1)** |
| **Identity** | 🟡 частковий | RBAC/refresh-ротація/webhook-secret ок; MFA, device-mgmt, rate-limit відсутні |
| **Infrastructure** | 🔴 слабкий | ACID-recovery ок, але **нема PITR-бекапів, DR, failover**; одна БД = SPOF |
| **Fraud** | 🔴 слабкий | нема rate-limiting, auto-void, risk-scoring; провайдер-sim = нема Radar |

## 4. Production Survivability Score (за фактом прогону)

| Вимір | /100 | Обґрунтування (на доказах) |
|---|---|---|
| **Financial Integrity** | **78** | double-entry витримав 200× webhook-шторм, 10× payout, крах БД — reconciliation=0. Мінус: chargeback/clawback/daily-recon не існують |
| **Concurrency Safety** | **82** | double-book фізично неможливе (доведено N=60); webhook/payout ідемпотентні. Мінус: idempotency-TOCTOU (F-2), лише single-node |
| **Fraud Resistance** | **30** | ghost-booking DoS підтверджено; нема rate-limit/auto-void/risk/Radar |
| **Failure Recovery** | **45** | ACID-crash recovery доведено наживо; але нема PITR/DR/failover, SPOF, нуль runbook-ів виконано |
| **Trust Safety** | **60** | webhook-secret, RBAC-межі, append-only ledger/audit доведені; нема MFA/device-mgmt; провайдер-sim |
| **OVERALL PRODUCTION SURVIVAL** | **58** | **фінансово-конкурентне ядро вистояло весь хаос; система вмирає на fraud/DoS і не має DR.** Не production-ready, але ядро грошей — здорове |

## 5. P0 Kill List (що дало б реальну втрату/колапс довіри в проді)

**Строго за серйозністю. P0 = фінансова втрата або колапс довіри.**

Після реального прогону — **жодного P0-дефекту у фінансовому ядрі не
знайдено**: подвійне бронювання, подвійний capture, подвійна виплата,
корупція ledger при краху БД — усі спроби відбиті. Це головний результат
D6.

**Проте система НЕ production-ready через P0-**відсутності** (не баги, а
незбудоване, що обов'язкове до реальних грошей):**

| Ранг | P0-відсутність | Чому kill | Стан |
|---|---|---|---|
| 1 | **Реальний Stripe Connect** (зараз симуляція) | нема справжнього руху грошей, SCA/3DS, chargeback | не збудовано |
| 2 | **PITR-бекапи + тест відновлення** | крах диска БД = безповоротна втрата всіх грошей-фактів; ACID не рятує від втрати тому | не збудовано |
| 3 | **Ghost-booking auto-void + rate limiting** (F-1) | inventory-DoS вбиває supply з першого дня | не збудовано |
| 4 | **Chargeback/clawback-флоу** | refund після виплати → негативний баланс без стягнення | не збудовано |
| 5 | **MFA + захист зміни IBAN** | крадіжка виплат через ATO | не збудовано |

## 6. Incident Recovery (доведене наживо)

| Інцидент | Detection | TTD | TTR | Recovery доведено? |
|---|---|---|---|---|
| Крах БД посеред транзакції | healthz/conn-error | миттєво | ручний restart ~15 c | ✅ **так** (сценарій 8: recon=0 після) |
| Webhook-шторм | — (ідемпотентність поглинає) | n/a | авто | ✅ так (1 проводка з 200) |
| Ghost-booking DoS | **немає сигналу** (F-1) | ∞ | нема авто | ❌ ні — P1 |
| Розсинхрон ledger | reconciliation-ендпоінт | ручний виклик | нема авто-job | 🟡 частково (є чек, нема алерту) |

## 7. Вердикт ради

**Система пережила реальний фінансово-конкурентний хаос без корупції.**
Це доведено виконанням, не обіцяно: 60 конкурентних бронювань → 1;
200 webhook-повторів → 1 capture; 10 payout-run → 1 виплата; крах БД →
ACID вистояв, ledger зводиться в нуль. Ядро грошей — здорове.

**Але це не production-ready.** Реальний Stripe, бекапи, auto-void +
rate-limit, chargeback-флоу, MFA — **не збудовані**. Overall survival
**58/100**: ядро тримає удар, периметр (fraud/DoS/DR) відкритий.
Пріоритет — P0-відсутності з §5, у тому порядку.
