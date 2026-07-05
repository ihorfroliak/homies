# D4 — Перший вертикальний зріз (auth → booking → payment → ledger → payout)

Статус: реалізовано в `backend/`. Це документ-дзеркало коду, не план.

## 1. Архітектура (тільки D4-scope)

Модульний моноліт (ADR-0001), 6 модулів у `backend/app/modules/`:

```
identity   users, host_profiles, refresh_tokens; JWT; RBAC
listings   listings, host_blocks (ручні блокування дат)
booking    bookings; правила доступності; календар-проєкція
payments   payments; PaymentProvider-шов (Stripe Connect симуляція);
           webhook; payout-оркестрація
ledger     рахунки, journal_entries/lines; єдина точка зміни грошей
admin      read-only видимість стану + reconciliation
```

Дозволені залежності (один напрям): booking→listings, booking→payments,
payments→ledger, payments→identity. Решта — заборонена (post-D4 —
через події). Композиція лише в `main.py`.

Потік даних: HTTP → router → (service) → SQLAlchemy → PostgreSQL.
Всі грошові дії пишуть audit_log (append-only).

## 2. Модель даних

| Таблиця | Ключові поля |
|---|---|
| users | id, email(uniq), password_hash(scrypt), role(guest/host/admin) |
| host_profiles | user_id PK, onboarding_state, stripe_account_id(sim), payout_iban_masked |
| refresh_tokens | token_hash(uniq), expires_at, revoked_at (ротація single-use) |
| listings | host_id, title, city, address, capacity, nightly_price_amount(мінорні, ADR-0002), currency, status |
| host_blocks | listing_id, start_date, end_date(exclusive) |
| bookings | listing_id, guest_id, check_in, check_out(excl), status, total_amount, currency, payout_status, uq(guest_id, idempotency_key) |
| payments | booking_id(uniq), provider_intent_id(uniq), status, amount, currency |
| ledger_accounts | code(uniq), kind |
| journal_entries | kind, booking_id, payment_id, currency |
| journal_lines | entry_id, account_id, amount (signed; сума в entry = 0) |
| audit_log | actor, action, entity_type, entity_id, data(json) |

Доступність — **інтервальна** (напрям ADR-0008): бронювання і блокування
= діапазони з exclusive end; перекриття: `a.start < b.end AND b.start < a.end`;
день-календар — лише read-проєкція в API.

## 3. Статусні машини

```
Booking: pending → confirmed → completed
                 ↘ cancelled (з pending або confirmed до check-in)
Payment: requires_payment → succeeded → refunded
                          ↘ voided (скасовано до оплати)
Payout(booking.payout_status): none → paid
Host onboarding: created → payout_ready
```
Переходи виконуються лише кодом відповідних сервісів; кожен — audit.

## 4. API (всі під /v1)

- **Auth:** POST /auth/register (guest|host; admin — лише ops-скрипт),
  /auth/login, /auth/refresh (ротація, повторне використання → 401), GET /me.
- **Host:** POST /hosts/onboarding (симуляція Connect onboarding → acct_sim_*,
  payout_ready), GET /hosts/me.
- **Listings:** POST /listings, PATCH /listings/{id},
  POST /listings/{id}/publish, GET /listings?city=, GET /listings/{id},
  POST /listings/{id}/blocks.
- **Booking:** POST /bookings (заголовок **Idempotency-Key** обов'язковий;
  replay → той самий запис), GET /bookings, GET /bookings/{id},
  POST /bookings/{id}/cancel, POST /bookings/{id}/complete (admin;
  прод: таймер після check-out), GET /listings/{id}/availability?from&to.
- **Payments:** POST /payments/webhook/simulated (стенд-ін Stripe webhook;
  ідемпотентний), POST /hosts/{id}/payouts/run (admin; ідемпотентний).
- **Admin:** GET /admin/{users,bookings,payments,ledger/entries,
  ledger/balances,ledger/reconciliation,audit}.

## 5. Ledger (мінімальний подвійний облік)

Знакова конвенція: дебет > 0, кредит < 0; кожен entry балансується в 0
(перевірка в `post_entry`, ще раз у reconciliation).

Рахунки: `provider_cash` (актив — кошти у Stripe),
`booking_escrow` (зобов'язання перед guest-ами),
`host_payable:{host_id}` (зобов'язання перед host-ом),
`platform_revenue` (дохід, fee 15% bps-конфіг).

| Подія | Проводка |
|---|---|
| payment_captured | Дт provider_cash / Кт booking_escrow (total) |
| refund | Дт booking_escrow / Кт provider_cash (total) |
| payout_allocated | Дт booking_escrow (total) / Кт host_payable (net) / Кт platform_revenue (fee) |
| payout_sent | Дт host_payable (net) / Кт provider_cash (net) |

Reconciliation: кожен entry = 0; сума всіх ліній системи = 0;
`/admin/ledger/reconciliation` повертає ok/unbalanced/balances.
Інваріант закритої системи: provider_cash + escrow + payables + revenue = 0.

## 6. Наскрізні флоу

**Guest booking:** register → login → GET /listings → POST /bookings
(Idempotency-Key; транзакція: lock listing → overlap-чек → ціна =
ночі × nightly) → payment intent (sim) → webhook succeeded →
booking confirmed + ledger capture.
**Host payout:** onboarding(payout_ready) → completed бронювання →
admin запускає payout → allocation + sent проводки → payout_status=paid;
повторний запуск платить 0 (ідемпотентно).
**Refund:** cancel до check-in → якщо оплачено: provider.refund +
зворотна проводка, payment=refunded; якщо ні — voided. Дати миттєво
звільняються. Refund після payout → 409 (clawback свідомо поза D4).

## 7. Порядок реалізації (виконано) і що розблоковано

core(db/security/audit) → identity → listings → booking(availability) →
ledger → payments(provider/service) → admin → тести (10: e2e, refund,
void, RBAC, ротація refresh, перекриття, блокування, валідації).
Розблоковано для Chat 04: реальний Stripe Connect за `PaymentProvider`-швом,
Alembic-міграції, події/outbox, host-кабінет UI.
Свідомо відкладено: RtB, політики скасувань, зміни дат, clawback,
модерація, пошук-двигун, нотифікації.

## 8. Ризики D4 (що зламає систему зараз)

1. **SQLite-тести не перевіряють конкурентність**: `with_for_update` —
   no-op; захист від подвійного бронювання доведений логічно, не
   конкурентним тестом на Postgres. → Chat 04: інтеграційний тест на
   Postgres + exclusion constraint (ADR-0008 повний).
2. **create_all замість Alembic** — ок для sandbox, блокер для спільного
   середовища. → перша міграція до деплою.
3. **Симульований webhook не має підпису** — реальний Stripe-ендпоінт
   зобов'язаний перевіряти Stripe-Signature. Шов готовий, перевірки нема.
4. **complete вручну адміном** — прод: таймер (scheduled event).
5. **Один платіж на бронювання, повний refund only** — часткові
   повернення змінять ledger-проводки (пропорційна структура готова).
6. **JWT-сесії без device-обліку і revocation-list access-токенів** —
   прийнятно 30 хв TTL; ревізит при першому реальному користувачі.
7. **Валюта одна на listing, без FX** — узгоджено зі стратегією (PLN).
