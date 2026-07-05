# D5 — Race Condition & Fraud Hardening (аудит реального D4-коду)

Статус: аудит проведено по коду `backend/app/`; P0-фікси **реалізовані**
в цьому ж коміті (позначені ✅), решта — беклог із пріоритетами.
Формат кожного кейсу: сценарій → наслідок → вразливість → фікс → інваріант.

## 1. Race Condition Register

### RC-1. Подвійне бронювання (два guest-и, ті самі дати) — P0 ✅
- **Сценарій:** два конкурентні POST /bookings на однакові дати.
- **Наслідок:** два pending-бронювання → обидва можуть оплатитись.
- **Вразливість D4:** overlap-чек у транзакції з `SELECT ... FOR UPDATE`
  на listing — коректно на Postgres, але **не перевірено конкурентним
  тестом**, і жодного захисту на рівні БД (application-only).
- **Фікс ✅:** Postgres **exclusion constraint** (btree_gist):
  `EXCLUDE USING gist (listing_id WITH =, daterange(check_in, check_out) WITH &&)
  WHERE (status IN ('pending','confirmed'))` — БД фізично не приймає
  перетин; IntegrityError → 409. FOR UPDATE лишається (зменшує конфлікти),
  constraint — остання лінія оборони.
- **Інваріант:** у БД не можуть існувати два бронювання одного listing
  зі статусом pending/confirmed і перетином дат. Enforcement: БД.

### RC-2. Скасування ↔ пізній webhook оплати — P0 ✅
- **Сценарій:** guest скасовує pending-бронювання; webhook `succeeded`
  приходить після скасування (Stripe вже списав гроші).
- **Наслідок D4:** webhook отримував 409 → payment лишався
  `requires_payment`, а в реальності гроші списані → **гроші-привид**:
  ledger не знає про капчер, guest без коштів і без бронювання.
- **Фікс ✅:** late-success flow: якщо booking `cancelled`, а intent
  succeeded → зафіксувати capture у ledger І негайно повний refund
  (обидві проводки, payment → `refunded`). Гроші повертаються, ledger
  повний, система детермінована.
- **Інваріант:** скасоване бронювання ніколи не тримає escrow > 0.
  Enforcement: payments.service.

### RC-3. Дубльовані/повторні webhook-и — P0 (було ✅ в D4)
- Stripe ретраїть до успіху; події можуть дублюватися.
- Захист: обробка за `provider_intent_id`, стан `succeeded` → no-op replay.
- **Інваріант:** одна capture-проводка на payment. Тест повторного
  webhook-а існує (test_e2e_flow: подвійний виклик).

### RC-4. Повторний payout (retry/подвійний клік адміна) — було ✅
- Вибірка `payout_status='none'` + `FOR UPDATE` + фліп у тій самій
  транзакції; повторний запуск платить 0 (тест є).
- **Інваріант:** на бронювання ≤ 1 пара проводок allocation+sent.

### RC-5. Payout ↔ refund колізія — P0 ✅ (частково D4)
- **Сценарій:** refund і payout по тому самому бронюванню конкурентно.
- **D4:** refund після payout → 409 (clawback поза scope) — правильно;
  але навпаки (payout під час refund) захищений лише статусами.
- **Фікс ✅:** інваріантна перевірка після payout-циклу: баланс
  `booking_escrow` не може стати від'ємним → інакше rollback усього
  запуску. Плюс fee=0 більше не ламає проводку (лінія з нулем
  не додається).
- **Інваріант:** escrow-баланс ≥ 0 завжди.

### RC-6. Crash між payment.status і ledger-проводкою — було ✅
- Обидва в одній DB-транзакції (один commit у webhook-роутері);
  crash до commit → відкат обох, Stripe ретраїть webhook → повтор.
- **Інваріант:** payment `succeeded` ⇔ існує capture-проводка.
  (Перевіряється reconciliation-ом; P1 — автоматичний нічний чек.)

### RC-7. Ротація refresh-токена конкурентно — P2
- Два одночасні refresh з одним токеном: обидва прочитають
  `revoked_at IS NULL` до commit → два нові токени.
- Ризик низький (потрібен вкрадений токен + гонка); фікс P2 —
  `UPDATE ... WHERE revoked_at IS NULL` з перевіркою rowcount.
- **Інваріант:** refresh-токен використовується рівно один раз.

### RC-8. Stale availability read (кеш/репліка) — P2 (архітектурний)
- D4 читає доступність з primary в транзакції бронювання — stale
  неможливий. Правило на майбутнє: календар-проєкції та пошук — лише
  для відображення; **істина завжди перевіряється в Booking при create**.

## 2. Fraud Vector Map

| Вектор | Стимул | Сигнали | Захист зараз | Залишковий ризик |
|---|---|---|---|---|
| Крадена карта → бронювання → chargeback | відмив/безплатне проживання | нова карта + високий чек + velocity | Stripe Radar (прод), затримка виплат (check-in+24h→payout після completed) | середній до Radar-правил (P1) |
| Refund-абьюз (бронюй→скасовуй циклічно) | блокування supply конкуренту / фарм | частота cancel per guest | повний refund тільки до check-in; аудит | середній — rate-limit скасувань P1 |
| Ghost-бронювання (pending без оплати блокує дати) | блокування supply | pending без capture > TTL | **дірка D4**: pending блокує календар безстроково → **P1: авто-void неоплачених через 30 хв** (потрібен scheduler) | високий до фіксу |
| Webhook-спуфінг (підтвердити броню без оплати) | безплатне проживання | — | **P0 ✅**: секрет на simulated-webhook; прод — перевірка Stripe-Signature обов'язкова в адаптері | закрито для sandbox |
| Idempotency-key повтор чужим guest-ом | перехоплення брoні | — | ключ унікальний **per guest** (uq guest_id+key) — чужий ключ не колізить | закрито |
| Фейковий listing (фантом) | збір передоплат | новий host + миттєві бронювання | managed-модель: фізична інспекція до активації (процес); Listed-шар — верифікація P1 | низький для managed |
| Off-platform coercion | уникнення комісії | контакти в чаті | Messaging поза D4; правило в T&C | п. V1 |
| Booking-спам API | DoS/блокування дат | rps per user/IP | **P1: rate limiting** (немає в D4) | високий до фіксу |
|账 фарм на промо | купони | device/IP кластери | промо нема в D4 | n/a |
| Admin-інсайдер | крадіжка виплат | аудит дій | append-only audit ✅, maker-checker P1 (зараз один admin) | прийнятний на стадії |

## 3. Ledger Hardening Spec

**Інваріанти (порушення = інцидент P0):**
1. Кожен journal entry балансується в 0 — enforcement: `post_entry`
  (перевірка до запису) + reconciliation (перевірка після).
2. Сума всіх ліній системи = 0 — reconciliation.
3. Append-only: entries/lines ніколи не змінюються — **P0 ✅**:
  ORM-guard (before_update/before_delete → виняток) на JournalEntry,
  JournalLine, AuditLog; DB-рівень (REVOKE UPDATE/DELETE) — P1 з міграціями.
4. `booking_escrow` ≥ 0 — **P0 ✅** пост-чек у payout.
5. payment `succeeded` ⇔ capture-проводка існує — reconciliation P1
  (звірка payments ↔ entries).
6. Recovery після порушення: ledger не «виправляється» update-ом —
  лише компенсаційна проводка (correction entry) з посиланням на
  інцидент. Правило зафіксоване.
7. Replay-безпека: всі фінансові операції ідемпотентні за природним
  ключем (intent_id, payout_status, booking idempotency key).
8. Ordering: проводки не залежать від порядку подій між бронюваннями;
  в межах одного бронювання порядок примушується статусними машинами
  (не можна payout до completed, refund після payout → 409).

**Виживання при відключенні живлення в мить транзакції:** атомарність
= Postgres WAL; проводка або повністю є, або її нема; парна зміна
статусу в тій самій транзакції. Незакомічений capture повторить webhook.

## 4. Booking Concurrency Model

- Стратегія: **песимістична** (`FOR UPDATE` на listing) +
  **constraint-based** (exclusion як гарантія БД) — подвійний захист.
- Атомарний create: lock → validate (active, capacity, dates) →
  overlap-чек → insert booking + payment intent → commit. Будь-яка
  помилка → повний rollback (жодних часткових станів).
- Conflict resolution: перший commit виграє; другий отримує 409 з
  чистим повідомленням; клієнт пропонує інші дати.
- Rollback-стратегія: скасування будь-якого етапу до commit — безслідне;
  після commit — тільки через статусні переходи (cancel → refund-флоу).

## 5. Stripe Connect Edge Case Spec

| Кейс | Поведінка системи |
|---|---|
| Webhook із затримкою годин | стан не залежить від часу: pending-бронювання чекає; **після P1 auto-void** — late success на voided → capture+refund (як RC-2) |
| Дубль callback-ів | ідемпотентна обробка (RC-3) |
| Out-of-order події | обробляємо лише термінальні `succeeded`/`failed`; проміжні ігноруються; неможливі переходи → 409 + лог |
| Chargeback після виплати | P1-флоу: dispute-event → заморозка майбутніх виплат host-а + компенсаційна проводка з негативним балансом host_payable; стягнення з наступних виплат |
| Reversed transfer | дзеркальна компенсаційна проводка payout_sent⁻¹; ніколи не update |
| Partial capture failure | D4: один інтент на повну суму; часткові — поза scope, статуси не допускають |
| Затримка settlement | ledger рахує наш стан; звірка з реальним Stripe Balance — щоденний reconciliation P1 |

## 6. System Invariants Document (зведення)

| # | Інваріант | Enforcement | Відновлення |
|---|---|---|---|
| I1 | Нема перетину активних бронювань | DB exclusion ✅ | неможливе порушення |
| I2 | Entry-баланс = 0 | post_entry ✅ + recon | correction entry |
| I3 | Система сумується в 0 | reconciliation | інцидент + correction |
| I4 | Ledger append-only | ORM-guard ✅ (DB P1) | відновлення з WAL/бекапу |
| I5 | Escrow ≥ 0 | payout post-check ✅ | rollback запуску |
| I6 | Cancelled ⇒ escrow(booking)=0 | late-success refund ✅ | авто |
| I7 | Payout лише для completed+succeeded | вибірка payout ✅ | — |
| I8 | Confirmed ⇒ payment succeeded | webhook-флоу ✅ | recon-звірка P1 |
| I9 | Refresh-токен одноразовий | ротація ✅ (гонка P2) | ревокація сесій |
| I10 | Admin створюється лише ops-скриптом | schema Literal ✅ + тест | аудит |

## 7. Distributed Failure Analysis

D4 — моноліт з одною БД: класи розподілених збоїв (partition між
сервісами, черги, реплики) **структурно відсутні** — це свідома
перевага ADR-0001 на цій стадії. Реальні залишкові збої: crash процесу
(покрито транзакційністю), недоступність Stripe (create intent
падає → бронювання не створюється, чисто), недоступність БД (повна
відмова, відновлення = PITR-бекап — **P1: бекапи не налаштовані**).
Правило на майбутнє (events/outbox): консюмери ідемпотентні, порядок
не припускається.

## 8. Production Risk Heatmap

| Ризик | Фін. | Корупція даних | Фрод | Довіра | Разом |
|---|---|---|---|---|---|
| Webhook без підпису (прод) | C | H | C | C | **P0 ✅ (sandbox), адаптер-вимога** |
| Подвійне бронювання | M | H | L | C | **P0 ✅** |
| Late-success після cancel | H | H | M | H | **P0 ✅** |
| Ghost pending блокує дати | M | L | H | H | **P1** (scheduler) |
| Нема rate limiting | M | L | H | M | **P1** |
| Нема PITR-бекапів | C | C | L | C | **P1** |
| Chargeback-флоу відсутній | H | M | H | M | **P1** |
| Refresh-гонка | L | L | L | L | P2 |
| DB-рівень immutability | L | M | L | L | P1 (з Alembic) |

## 9. P0/P1 Hardening Backlog

**P0 — зроблено в цьому коміті ✅:**
1. Exclusion constraint проти подвійного бронювання (Postgres) + 409-мапінг.
2. Late-success auto-refund для скасованих бронювань.
3. Секрет на simulated webhook (прод-адаптер зобов'язаний перевіряти Stripe-Signature).
4. ORM-guard append-only для ledger і audit.
5. Escrow ≥ 0 пост-чек у payout + fix проводки з fee=0.

**P1 — наступний спринт:** auto-void неоплачених бронювань (30 хв TTL,
перший scheduled-механізм), rate limiting, PITR-бекапи + тест
відновлення, chargeback/clawback-флоу, щоденна звірка payments↔ledger↔
Stripe Balance, DB-рівень REVOKE на ledger-таблицях (Alembic),
конкурентний тест бронювання на Postgres у CI.

**P2:** refresh-гонка (rowcount-check), verified-listing для Listed-шару,
maker-checker на ручні фінансові дії.
