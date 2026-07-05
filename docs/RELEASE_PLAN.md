# Release Plan — найкоротший шлях NO-GO → GO (D8)

> Оптимізуємо **послідовність**, не код. Мета — не ідеальна платформа, а
> **перше безпечне реальне бронювання** з найменшим інженерним зусиллям.
> База — блокери D7 (`docs/reviews/2026-07-05-d7-production-readiness-board.md`).

## 1. Ключовий інсайт скорочення шляху

Managed-модель **сама коротшає критичний шлях**: платформа оперує
об'єктом, тому «перший host / перша квартира / перший гість» — **відомі,
контрольовані сторони** (host з HeyHomie-бази, квартира фізично
інспектована, гість — реальний, але керований). Це прибирає з шляху до
бронювання #1 усе, що потрібне лише для *публічного масштабу*:
fraud-скоринг, rate-limit, auto-void, повна observability, MFA-периметр —
**переносяться в Gate 2**, бо на одному контрольованому бронюванні їх
ризик ≈ 0.

## 2. Критичний шлях (послідовні блокери) до бронювання #1

```
[Legal: agency contract + T&C + Stripe MoR]  ── parallel, founder+юрист
                                                 │
[Real Stripe Connect за PaymentProvider-швом] ──┤ CRITICAL, eng
  + webhook signature verification              │
                                                 ▼
[PITR/pg_dump бекапи + виконаний restore-тест] ─ CRITICAL, eng (S)
                                                 ▼
[Alembic + перша міграція (freeze схеми)] ─────  CRITICAL, eng (S-M)
                                                 ▼
[1 реальний host + 1 інспектована квартира] ───  parallel, ops/founder
                                                 ▼
              ⇒ ПЕРШЕ БЕЗПЕЧНЕ БРОНЮВАННЯ (Gate 1)
```

Все інше з D7 (auto-void, rate-limit, observability, MFA, disputes,
chargeback, повний комплаєнс) — **НЕ на критичному шляху до #1**.

## 3. Три гейти

| Гейт | Умова | Що потрібно (тільки це) |
|---|---|---|
| **Gate 1 — GO WITH RESTRICTIONS** | 1 host, 1 квартира, 1 гість, 1 платіж, 1 виплата | реальний Stripe Connect + webhook-підпис; бекапи+restore-тест; Alembic; agency-договір+T&C; фізична інспекція об'єкта. Ручні операції засновника. |
| **Gate 2 — LIMITED PRODUCTION** | 100 listings, 1000 bookings | auto-void+rate-limit; observability (метрики/алерти/синтетик); support+incident runbook-и; MFA+secrets-mgmt; chargeback/clawback; щоденна авто-звірка; базовий GDPR/KYC/VAT |
| **Gate 3 — GA** | публічний запуск | disputes-модуль, fraud-скоринг, DR-навчання (region), verified-listing, DAC7, maker-checker, масштаб-операції |

## 4. Паралельні дороги (ніхто не простоює)

| Команда | Gate 1 робота |
|---|---|
| **Engineering** | Stripe Connect адаптер → бекапи → Alembic → DB-REVOKE (ledger) |
| **Legal** | agency-договір Homies↔host, T&C/regulamin, підтвердити Stripe як MoR, GDPR consent-текст |
| **Founder** | оферта + дзвінки host-ам з HeyHomie-бази (net-payout калькулятор) |
| **Operations** | стандарт-чекліст об'єкта, інспекція першої квартири, клінінг-SLA |
| **Finance** | Stripe-акаунт компанії, sp. z o.o., бухсервіс з KSeF |
| **Design/Marketing/AI** | **навмисно idle до Gate 1** (не на критичному шляху — не витрачаємо годин) |

## 5. Топ-задачі за ROET (Return on Engineering Time)

ROET = (business value + risk reduction) ÷ effort. Тільки Gate 1.

| # | Задача | Ефорт | Закриває | ROET |
|---|---|---|---|---|
| 1 | **Alembic + перша міграція** (freeze схеми, exclusion constraint у міграцію) | S-M | B6 | **дуже високий** — розблоковує безпечний прод-деплой, дешево |
| 2 | **pg_dump/PITR бекап + restore-тест** | S | B2 | **дуже високий** — без цього гроші втрачаються, зусилля мінімальне |
| 3 | **DB-REVOKE ledger + окрема app-роль** | S | B5 | високий — закриває tamper, дешево |
| 4 | **StripeConnectProvider адаптер** (шов існує) + webhook-підпис | M | B1 | високий — критичний шлях, але більший ефорт |
| 5 | Config: prod-секрети через env, прибрати dev-дефолти | S | B8(частк.) | середній |
| — | auto-void, rate-limit, observability, MFA-повний | — | Gate 2 | **виключено з шляху до #1** |

## 6. Тижневий план (відносний, без календаря)

| Тиждень | Ціль | Deliverable | Верифікація | Δ readiness |
|---|---|---|---|---|
| **W1** | схема+дані безпечні | Alembic-міграції, бекап+restore-тест, DB-REVOKE | `alembic upgrade head` на docker; restore піднімає копію; прямий UPDATE ledger від app-ролі → відмова | 22 → ~40 |
| **W2** | реальні гроші | StripeConnectProvider + webhook-підпис (test-mode) | e2e бронювання в Stripe **test-mode**: intent→capture→payout у Connect; ledger звіряється зі Stripe Balance | 40 → ~58 |
| **W3** | Gate 1 юр+ops | agency-договір+T&C підписані; 1 квартира інспектована; Stripe live-keys | юрист-sign-off; чекліст об'єкта пройдено; live-mode тестова копійка | 58 → ~68 |
| **W4** | **перше реальне бронювання** | контрольований гість бронює реальну ніч | гроші пройшли Stripe live; виплата host-у; ledger=Stripe; recon=0 | Gate 1 ✅ |

## 7. Cost of Delay (чому саме цей порядок)

- Затримка **бекапів** (B2): очікувана втрата = усі гроші-факти при
  першому краху диска → нескінченна. Тому W1, попри малий «прогрес».
- Затримка **Stripe** (B1): нуль реальної виручки, весь бізнес стоїть →
  найбільша opportunity cost, але потребує W1 (безпечна схема) під собою.
- Затримка **auto-void/observability**: на одному контрольованому
  бронюванні бізнес-вплив ≈ 0 → свідомо в Gate 2 (не платимо зараз).

## 8. Найраніша безпечна прод-дата

**Відносно:** ~**4 build-цикли** (W1–W4 вище) до першого реального
бронювання за умови, що юр-трек іде паралельно з W1–W2. Критичний шлях —
не код Stripe, а **бекапи+схема (W1) → Stripe (W2) → юр+ops-готовність
(W3)**. Найдовший паралельний елемент — юридичний (договір+T&C), тому
він стартує **негайно**, у W1.

## 9. Виконавче рішення

**Наступне для команди:** W1 — Alembic + бекапи + DB-REVOKE (eng,
найвищий ROET, розблоковує все), і **паралельно негайно** — юрист на
agency-договір. Це найкоротший, найнижчий за ризиком шлях до Gate 1.
Design/marketing/AI — не чіпати до Gate 1.
