# 05 — Бізнес-правила і життєві цикли сутностей

**Принцип:** статусна машина — джерело істини. Перехід можливий лише з
таблиці переходів; кожен перехід — подія + запис аудиту (хто/що/підстава).
«Хто» ∈ {guest, host, system, support, moderator, t&s, dispute_resolver,
finance, admin}.

## 1. User (акаунт)

`pending_verification → active → restricted → suspended → banned`
плюс `deleted (анонімізовано)`.

| Перехід | Хто | Умова/пояснення |
|---|---|---|
| pending → active | system | підтверджений email/телефон |
| active → restricted | system, t&s | ризик-сигнал: обмежені дії (не може бронювати/публікувати), може оскаржити |
| restricted → active | t&s | рев'ю пройдено |
| active/restricted → suspended | t&s | серйозна підозра; вхід заблоковано |
| suspended → banned | t&s | підтверджене порушення; PII зберігаються для запобігання повторній реєстрації (легітимний інтерес) |
| any → deleted | user, system | GDPR-запит; блокується за наявності активних бронювань/боргів |

## 2. Host-профіль (KYC)

`not_started → docs_submitted → in_review → verified | rejected (→ resubmission)`
Правила: виплати лише з `verified`; оголошення можна створювати з
`docs_submitted`; `rejected` тричі → ескалація t&s.

## 3. Listing

`draft → in_moderation → active ⇄ paused → delisted → archived`
(+ `rejected` з модерації, з причинами).

| Перехід | Хто | Умова |
|---|---|---|
| draft → in_moderation | host | мінімальна повнота (фото ≥ N, адреса, ціна, політика скасування) |
| in_moderation → active | system (автопрохід) або moderator | перевірки пройдені |
| in_moderation → rejected | system/moderator | причини типізовані; host виправляє → знову модерація |
| active → paused | host | ручна пауза (не штрафується, дати блокуються) |
| active → delisted | system (quality score), t&s | якість/порушення; план відновлення |
| delisted → in_moderation | host | після виправлень |
| any → archived | host | назавжди; історія бронювань зберігається |

Зміна **критичних полів** (адреса, тип житла) на `active` → повторна
модерація без зняття з публікації.

## 4. Booking — центральна машина

```
draft → pending_payment → pending_host (лише Request to Book)
      → confirmed → checked_in → completed → reviewed/closed
Термінальні гілки: cancelled_by_guest | cancelled_by_host |
declined | expired | payment_failed | no_show
```

| Перехід | Хто | Умова/таймер |
|---|---|---|
| draft → pending_payment | guest | Idempotency-Key; календар м'яко утримується 15 хв |
| pending_payment → confirmed | system | Instant Book: оплата ok |
| pending_payment → pending_host | system | Request-режим: авторизаційний hold ok |
| pending_host → confirmed | host, system (auto-accept правило) | ≤ 24 год |
| pending_host → declined | host | причина типізована |
| pending_host → expired | system | таймер 24 год; hold звільнено |
| pending_payment → payment_failed | system | ретрай 30 хв не вдався |
| confirmed → cancelled_by_guest | guest | повернення за політикою (авто) |
| confirmed → cancelled_by_host | host | 100% повернення + штраф + ризик-сигнал |
| confirmed → checked_in | system (дата) + guest-підтвердження або відсутність скарги 24h | вікно «проблема при заселенні» |
| confirmed → no_show | system + host-заява | guest не з'явився; кошти за політикою |
| checked_in → completed | system | check-out + N год; блокується відкритою суперечкою |
| completed → closed | system | 14 днів: відгуки опубліковані/вікно закрите, claim-вікно host-а (72 год) минуло |

Зміна дат/гостей = BookingChange з власним міні-циклом
(`proposed → accepted/declined/expired`), перерахунок ціни обов'язковий.

## 5. Payment

`initiated → authorized → captured → (partially_)refunded | failed | voided`
+ `chargeback_opened → chargeback_won/lost`.
Правила: capture у Instant Book — одразу; у Request — після підтвердження
host-а. Chargeback → авто-заморозка пов'язаної виплати + кейс у T&S.

## 6. Payout (виплата host-у)

`scheduled → processing → paid | failed (→ retry ×3 → manual_review) | frozen`
Правила: створюється лише з ledger-балансу; `frozen` — відкрита
суперечка/фрод-рев'ю; розморозка — рішенням кейса.

## 7. Refund

`calculated → approved (system за політикою | support понад політику в межах ліміту) → processing → completed | failed`
Правило: будь-який refund поза політикою вимагає підстави (тікет/суперечка).

## 8. Dispute — див. документ 06 (власна машина зі SLA).

## 9. Review

`invited → submitted → published | hidden (модерація) | expired (14 днів)`
Double-blind: `submitted` не видно другій стороні до публікації обох або
дедлайну.

## 10. Support Ticket

`new → triaged → in_progress → waiting_user → resolved → closed`
(+ `reopened ≤ 7 днів`). SLA: P1 ≤ 15 хв, P2 ≤ 2 год, P3 ≤ 24 год першої
реакції; таймери → авто-ескалація L1→L2.

## 11. Penalty (штраф host-а)

`assessed → acknowledged | appealed → upheld/waived → settled (утримано з виплат)`
Правило: оскарження заморожує утримання, але не скасовує його.

## 12. Наскрізні бізнес-правила (вибірка нормативу)

**Можна / не можна:**
1. Guest не може забронювати об'єкт із перекриттям власного бронювання
   тих самих дат (анти-спекуляція) — м'яке попередження, ліміт активних
   бронювань конфігурований.
2. Host не може контактувати guest-а поза платформою до `confirmed`
   (маскування контактів у Messaging).
3. Host не може змінити ціну підтвердженого бронювання. Ніколи.
4. Знижки/акції не можуть підняти повну ціну вище показаної у видачі
   (анти-drip-pricing, вимога ЄС).
5. Відгук — тільки після `completed` (verified stay), 14 днів.
6. Виплата — тільки після check-in + 24h і лише на верифікований IBAN.
7. Скасування host-ом ближче ніж за 48 год до заїзду → підвищений штраф
   + пропозиція guest-у альтернатив коштом платформи (компенсується з host-а).
8. Один об'єкт = одне активне оголошення (дедуплікація по гео+адресі).
9. Ціни та податки: показана guest-у сума фінальна; податкові збори
   (міський податок) — окремим рядком, конфігурація ринку.
10. Будь-який ручний рух грошей > ліміту ролі → maker-checker.

**Головні винятки:**
- Extenuating circumstances (форс-мажор, підтверджений документально) →
  повне повернення незалежно від політики, без штрафу host-у, рішення
  support/t&s за списком підстав.
- B2B-бронювання: інвойс замість миттєвої оплати можливий лише для
  верифікованих компаній з кредитним лімітом (V2+).
