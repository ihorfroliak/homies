# D9 — Business Continuity & Disaster Recovery (executed drill + evidence)

> Мандат: бекап, який не відновлювали, **не існує**. Тому нижче — не
> архітектура, а **виконаний drill** з реальними числами. Скрипти:
> `backend/scripts/backup/`. Дата: 2026-07-05. Стан коду: post-7a3fc50.

## 0. Executed evidence (не припущення)

Drill `dr_drill.sh` проти живого docker+Postgres:
```
source: bookings=77, journal_lines=48
[1] BACKUP  -> homies_homies_20260705T171920Z.dump.gz.enc (90 416 B, AES-256, sha256 fixed)
[2] DRILL A clean restore: RTO = 4s
    counts match source (bookings=77, journal_lines=48, audit_log=364)
    grand_total=0 escrow=0 unbalanced_entries=0 paid_without_payout=0
    FINANCIAL RECOVERY: PASS
[3] triggers=3, excl_booking_overlap present  (guards survived restore)
[4] DRILL B accidental DROP TABLE journal_lines -> restore -> re-verify
    FINANCIAL RECOVERY: PASS  (data fully returned)
```
Шифрування підтверджено: артефакт починається з `Salted__` (openssl
AES-256-CBC/pbkdf2), не plaintext `PGDMP`. Checksum:
`8413efe0...beefc213`.

## 1. Failure Catalogue

| Disaster | Ймов. | Бізнес-вплив | Складність відновл. | Max downtime | Max data loss | Покрито drill-ом? |
|---|---|---|---|---|---|---|
| Accidental DROP TABLE / DELETE | середня | H | низька | хвилини | до останнього бекапу | ✅ **DRILL B** |
| Postgres корупція тому | низька | C | середня | хвилини-години | до бекапу | 🟡 restore-процедура доведена, реальну корупцію не інсценовано |
| Крах диска БД | низька | C | середня | години | **весь том, якщо бекап локальний** | 🟡 restore ✅; **offsite-копії немає** |
| Broken migration | середня | H | низька | хвилини | 0 (Alembic downgrade / restore) | 🟡 downgrade доведено (D8); restore-шлях є |
| Region outage | низька | C | висока | години-доба | залежить від offsite | ❌ **не покрито** (одна нода) |
| Operator mistake (drop DB) | середня | C | низька | хвилини | до бекапу | ✅ restore.sh перестворює БД |
| Credential/secrets leak | середня | C | — | — | — | ❌ секрети — dev-дефолти (B8) |
| Deploy failure | середня | M | низька | хвилини | 0 | 🟡 rollback-процедура є, не автоматизована |
| Stripe outage | середня | H | — | — | 0 | 🟡 провайдер симуляція; degraded-mode описано |
| Lost object storage (бекапи) | низька | C | — | — | всі бекапи | ❌ **immutable/offsite сховище відсутнє** |
| Deleted k8s cluster | низька | C | висока | години | 0 (stateless) | ❌ інфра-як-код не застосована |

## 2. Recovery Objectives (виміряні / цільові)

| Метрика | Ціль Gate 1 | Доведено drill-ом |
|---|---|---|
| **RTO** (відновлення БД) | ≤ 30 хв | **4 c** на пілотному обсязі (77 бронювань); лінійно росте з даними |
| **RPO** | ≤ 1 год | = інтервал бекапу; **зараз ручний → RPO = «від останнього ручного бекапу»** (розрив) |
| Max financial exposure | 0 корупції | **0** (звірка PASS після restore і після DROP) |
| Max booking loss | 0 у межах RPO | 0 (counts збіглись) |
| Max audit loss | 0 у межах RPO | 0 (audit_log=364 відновлено) |

## 3. Backup Strategy (реалізовано / відкрито)

**Реалізовано (`backup.sh`):** custom-format `pg_dump` → gzip →
**AES-256 шифрування** (openssl, pbkdf2) → **sha256 checksum** →
timestamped артефакт; тримається лише зашифрована копія.
**Відкрито (P1, до реального проду):** автоматичне розкладом (cron/
systemd-timer/managed) — зараз **ручний запуск = головний розрив RPO**;
offsite/geo-redundant immutable сховище (S3 Object-Lock); WAL-archiving
для PITR (RPO→хвилини); ротація ключів шифрування.

## 4. Restore Validation Report

| Drill | Виконано | Результат |
|---|---|---|
| Clean restore у свіжу БД | ✅ | RTO 4s, counts збіглись, фінансова звірка PASS |
| Restore після accidental DROP TABLE | ✅ | дані повернулись, звірка PASS |
| Guards survive restore | ✅ | 3 append-only тригери + exclusion constraint відновлені |
| Checksum-verify перед restore | ✅ | `sha256sum -c` у restore.sh |
| Restore to timestamp T (PITR) | ❌ | потребує WAL-archiving — managed-Postgres шлях |
| Restore after real page corruption | 🟡 | процедура та сама; реальну корупцію не інсценовано |

## 5. Infrastructure Recovery (чесний стан)

| Компонент | Recovery | Доведено? |
|---|---|---|
| Database | restore.sh перестворює+відновлює БД | ✅ |
| Application | stateless, `docker compose up`/образ | 🟡 (образ є, IaC нема) |
| Secrets | **dev-дефолти в config** | ❌ (B8) |
| Config | env/pydantic-settings | 🟡 |
| Storage (бекапи) | локальна папка | ❌ offsite нема |
| Networking/DNS/TLS | — | ❌ поза scope пілота |
| Scheduled jobs | **нема планувальника** | ❌ |
| Admin access | ops-скрипт create_admin | 🟡 |

## 6. Financial Recovery Validation ✅

Доведено `verify_restore.py` після кожного restore: кожен journal-entry
= 0; сума системи = 0; escrow ≤ 0 (liability, без дрейфу); **жодного
paid-бронювання без payout_sent-проводки**; counts збіглися з джерелом.
Подвійних/зниклих виплат немає. **Фінансова цілісність переживає
відновлення — доведено виконанням, двічі.**

## 7. Disaster Runbooks

Створено `docs/runbooks/dr-database-recovery.md` (виконувані кроки:
backup, restore, drill, broken-migration, accidental-delete) +
короткі процедури: payment-provider outage (degraded-mode), manual
booking/payout continuation, incident escalation. Кожен крок = реальна
команда з `backend/scripts/backup/`.

## 8. Recovery Metrics (з drill-у)

RTO = **4 c** (пілотний обсяг), operator effort = 1 команда
(`dr_drill.sh`), manual intervention = запуск скрипта, unexpected
failures = 0. Data loss у drill = 0 (у межах бекапу).

## 9. Monitoring Recovery Readiness (відкрито, P1)

Немає: детекції відсутніх/зламаних бекапів, alerting на fail, перевірки
retention, авто-verify. Зараз readiness перевіряється лише ручним
запуском drill-у. **P1: nightly backup + auto-verify + alert.**

## 10. Release Gate Status (D9-критерії)

| Критерій GO | Стан |
|---|---|
| Backups automatic | ❌ (скрипт є, розкладу нема) |
| Backups encrypted | ✅ AES-256 |
| Restores verified | ✅ виконано двічі |
| Recovery documented | ✅ runbooks |
| Recovery rehearsed | ✅ drill виконано |
| Financial reconciliation after restore | ✅ PASS |
| Evidence exists | ✅ (цей звіт + артефакт + checksum) |

**6 із 7 виконано; єдиний розрив — автоматизація розкладу + offsite.**

## 11. Remaining Recovery Risks

1. **Ручний бекап** → RPO = «від останнього запуску» (P1: розклад).
2. **Локальне сховище** → крах хоста втрачає і БД, і бекапи (P1: offsite S3 Object-Lock).
3. Немає PITR (RPO→хвилини) — managed-Postgres закриває.
4. Секрети — dev-дефолти (B8).
5. Немає моніторингу здоров'я бекапів.

## 12–13. Оцінки

| Метрика | /100 | Обґрунтування (докази) |
|---|---|---|
| **Recovery Readiness** | **55** | restore+фінансова звірка доведені виконанням (RTO 4s, 2 drill-и); мінус автоматизація/offsite/PITR/моніторинг |
| **Production Survival** | **48** | локальна катастрофа з недавнім бекапом — виживає (доведено); тотальна втрата хоста/регіону — **ні** (offsite нема) |

## 14. Executive Recommendation

**Рекомендація:** для пілота — **managed Postgres** (RDS/Supabase/Neon):
дає автоматичні бекапи + PITR + offsite «з коробки», закриваючи 3 з 5
залишкових ризиків нулем інженерних годин. Наш внесок — **доведена
процедура restore + фінансова верифікація** (цей drill), яку запускаємо
проти managed-снапшотів як регулярну репетицію. Не будувати власний
WAL-archiving на цій стадії (низький ROET).

## 15. Final Executive Answer

**«Якщо прод сьогодні повністю зникне — чи відновить Homies безпечну
роботу в межах RTO/RPO без фінансової корупції?»**

# 🟡 PARTIALLY

**Докази за:** відновлення БД + повна фінансова звірка **виконані двічі**
(clean restore і після accidental DROP), RTO 4s, guards переживають
restore, corruption=0. Від **локальної** катастрофи з недавнім бекапом
Homies відновлюється безпечно — доведено.

**Докази проти (чому не YES):** бекап **ручний** (RPO = від останнього
запуску, не гарантований), сховище **локальне** (крах хоста втрачає і
дані, і бекапи — offsite-копії немає), **PITR немає**. Від тотальної
втрати хоста/регіону відновлення **не доведене**.

**Шлях до YES (дешевий):** managed Postgres (авто-бекап+PITR+offsite) +
розклад цього ж backup.sh на offsite. Тоді всі 7 gate-критеріїв
зелені.
