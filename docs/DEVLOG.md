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

**Далі (Фаза 0 → 1):**
- [ ] Створити GitHub-репозиторій `homies`, запушити, перевірити зелений CI.
- [ ] Chat 03: auth-модуль — схема БД, міграції (Alembic), реєстрація/логін/JWT.
- [ ] GitHub Projects дошка з фазами.
