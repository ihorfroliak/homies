# TASK-009 — Codex final independent foundation audit (archived)

> **Archived verbatim** in TASK-010 (2026-09-25) so the audit outcome does not
> live only in agent session history. Nothing below the provenance block was
> edited, summarised or reconstructed. Links and paths inside the report point
> to the auditor's evidence outside the repository and may not resolve here.

| Field | Value |
|---|---|
| Auditor | Codex (independent, read-only) |
| Audit | TASK-009 — Final Independent Foundation Audit |
| Audited SHA | `36231840ee52d6185e73fda07e54eab33ffe41f3` |
| Verdict | `TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES` · `HOMIES_FOUNDATION_BASELINE_002_ACCEPTED` |
| Section A source | `%USERPROFILE%/.codex/visualizations/2026/09/25/01a0d8bb-87f0-7210-b4d2-f8d718b37da0/TASK-009-final-audit.md` |
| Section A SHA-256 (as archived) | `8224a666b5b146cf87cdb62c0bfb05edeae21cce8ae6a7634c59cb048376de7e` |
| Section B source | last assistant message of the Codex audit session, 2026-09-25T14:05:06Z (Ukrainian; same verdicts as Section A) |
| Section B SHA-256 (as archived) | `d6a58cb3a208334fc421db96f4b7f8220e7ceeae79249dab4b3f95aa45ed0246` |
| Session | `Codex rollout 01a0d8bb-87f0-7210-b4d2-f8d718b37da0` |

Adjudication: the founder, with ChatGPT, accepted Foundation Baseline 002 on
the basis of this report and its independent counterpart — see
[IMPLEMENTATION-CONVERGENCE](../canonical/IMPLEMENTATION-CONVERGENCE.md).

---

## Section A — full report file (verbatim)

# TASK-009 FINAL INDEPENDENT FOUNDATION AUDIT

## EXECUTIVE VERDICT

TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES. HOMIES_FOUNDATION_BASELINE_002_ACCEPTED at 36231840ee52d6185e73fda07e54eab33ffe41f3 for continued Phase 1A development. N-06 is PARTIALLY_CLOSED because two supposedly equivalent restrictions are actually load-bearing; the current code keeps both. Two NEW FINDING P3 items concern regression coverage and timing assertions. Production readiness is not established.

## INDEPENDENCE

Independent new audit context; no participation in TASK-008 implementation. Read-only detached checkout. Probes and mutation copies lived outside it.

## EXACT SHA

git rev-parse HEAD = 36231840ee52d6185e73fda07e54eab33ffe41f3, before and after. git status --short empty; git branch --show-current empty (detached). Parent history: 3623184, 63686b6, 1b2458c, 0f1cb33.

## ENVIRONMENT

Windows host; own disposable Docker PostgreSQL 16/PostGIS 3.4; Python 3.12.14 in an ephemeral test container with read-only checkout mount. No CI run. PostgreSQL tests recreated only task009_disposable.

## COMMANDS ACTUALLY RUN

git rev-parse/status/branch/log/diff; source and canon inspection; targeted PG pytest for TASK-008/006/004/002 and OpenAPI; full SQLite pytest; separate OpenAPI pytest; ruff check app tests; mypy app; TASK-008 D01-D17 mutation runs in /tmp copy; E01-E04 checks; three independent PG probes; pg_dump/pg_restore into own disposable restore DBs; SHA-256 source restoration check.

## N-05 ACTUAL LOCKED-PROOF AUDIT

CLOSED. _lock_proof returns actual FOR SHARE result rows for legal parties, personal/organization links, organizations, memberships, mandates, and authorities; scope pairs are appended only if the lock query returns a row. authorize_for_mutation evaluates within=locked. All five required same-key raw SQL replacement cases returned 409/Retry-After: 0 and left the Listing draft. An unchanged waited-on row returned 200. A fresh attempt read, locked and published through the replacement (200); three repository cases had a separate post-commit thread-order assertion failure. Independent whole-mandate and whole-organization raw SQL replacements returned 409, then 200 on a fresh request.

## N-06 RESTRICTED-PROOF AUDIT

PARTIALLY_CLOSED. Load-bearing filters: personal link, organization link, membership, organization id, mandate id and (mandate, scope) pair, authority id and (authority, scope) pair. The code retains them. Same-principal second mandate and same-holder second authority gains returned 409, with no holder/scope pooling. E01 and E02 are not equivalent under the current schema: deleting and reinserting a mandate with its cascaded scope, or an organization after deleting its membership/link, under the same ids makes the new child rows lockable after the parent FOR SHARE query returned none. Independent probes passed with current code and failed as assertions when the respective id filter was removed. E03 and E04 survived seven stable tests each; current authority-to-holder RESTRICT FK and Property FOR UPDATE/FK lock support their present redundancy. A future schema change can invalidate that reasoning. The current organization/legal-party model is one-to-one, already recorded as canonical debt, so a single organization with multiple legal parties could not be exercised.

## N-07 ACCEPT LOCK-STRENGTH AUDIT

CLOSED. accept_invitation uses FOR UPDATE before reading status. Two accepts for both AGENT and ADMIN serialized: one 200, other 404, one join audit, no deadlock. Accept/revoke tests covered both orders. D13 FOR SHARE mutant failed a behavioral assertion after a green baseline.

## N-08 AUTHORIZATION OUTCOME AUDIT

CLOSED. Real publish API interleavings reached 403 (verification lost after precheck), 404 (relationship removed), 409 (unlocked valid replacement), 200 (cosmetic update). Listing status and Retry-After were checked. The final 403 was not mocked.

## N-09 INVITATION LIFECYCLE AUDIT

CLOSED. Row lock precedes decision. No row creates INVITED; explicit manager re-invite moves REVOKED to INVITED; INVITED and ACTIVE are unchanged. Invite-vs-accept race finished ACTIVE. D14-D16 failed behavioral tests.

## N-10 CONCURRENT FIRST-INVITE AUDIT

CLOSED. API/API returned 202/202, one membership, winning role; API/raw uncommitted INSERT with COMMIT and ROLLBACK returned controlled 202 and one row. Savepoint recovered the unique violation without poisoning the outer transaction. D17 failed behaviorally.

## N-01 REGRESSION

NONE. Independent compound probe: locked valid personal chain A survived organizational chain Y's revoke while new mandate B appeared; publish returned 200 through A. Existing chain-gain race: Y invalid, B unprotected produced 409/draft, then fresh 200 through B. No global mutex or scope pooling observed.

## N-02 REGRESSION

NONE. AGENT and ADMIN accept-vs-revoke tests passed in both orders; no stale ACTIVE after successful revoke.

## F-04 REGRESSION

NONE observed. PG tests exercised membership and mandate revoke, organization suspension, LegalParty archive, relationship/scope removal, mandate expiry, surviving independent chains, authority revoke and Space archive. Direct SQL replacement samples supported atomic refusal. Four F-04 tests failed only their HTTP-thread completion-order assertion after observing the DB blocker and publish 200; see NEW FINDING.

## 409 API CONTRACT

Only the protected authority-change conflict returns HTTP 409, Retry-After: 0 and stable detail authority.AUTHORITY_CHANGED. Other publish 409 paths inspected have no retry header; archived-listing case verified via API. OpenAPI drift passed and the spec is generated from route metadata. The header is distinguishable for an HTTP client; no current frontend publish retry handler was found. Retrying this 409 starts a fresh, side-effect-free decision. The precheck prevents a cross-property authority oracle; no identity or chain details are disclosed. A client with unbounded automatic retries could loop under continual authority churn.

## DEADLOCK / LOCK ORDER

Publication locks Property first, then proof tables in documented order. Authority revoke and Space archive also take Property first. Accept/invite/revoke take their membership row; mandate revoke takes its mandate row. No feasible new cycle identified. Continuous publications may delay revoke; this is starvation risk, not deadlock.

## RAW-SQL GUARANTEE

All five row classes required by N-05 were directly deleted/reinserted during a real PostgreSQL lock wait. Independent probes additionally replaced whole mandate and organization rows under identical ids. Correct behavior depends on actual returned locks and retained id filters, not API refusal of DELETE.

## MUTATION REVIEW

In an external /tmp copy, D01-D17 each had a green baseline and were killed by pytest assertion failure, not syntax, collection or setup errors. The original E01/E04 harness baseline was intermittently red because of a thread-order assertion. New stable raw SQL probes killed E01 and E02: the published “expected equivalent” classification for these is false. E03/E04 survived seven stable tests each and have current-schema FK/lock reasoning. TASK-006, TASK-004 and TASK-002 harnesses were inspected; their historical counts were not rerun. Mutation source bytes in /tmp were restored and matched checkout SHA-256.

## TEST QUALITY

Blocking PID, HTTP status, Listing state, membership row and audit count are meaningful checks. The list-order assertions at test_publication_proof_replacement_pg.py:222 and test_publication_authority_race_pg.py:252 equate HTTP response completion order with database commit order. A loss can commit after publication but return before publish response serialization finishes; seven failures showed this while blocking and publication outcomes held. One failing case reproduced in isolation.

## TEST RESULTS

Targeted PG + OpenAPI: 77 passed, 7 failed (all two timing assertions), 1 warning. Separate OpenAPI: 5 passed. Full SQLite: 705 passed, 188 skipped, 52 warnings. Three independent PG probes passed. Ruff: pass. Mypy: pass, 77 source files. TASK-008 mutation: 17/17 D killed with valid green baselines; E01/E02 killed by independent probes; E03/E04 survived stable tests. Full PG suite and CI were not run.

## PYTHON 3.12 STATUS

Python 3.12.14 targeted runtime VERIFIED; 7 targeted timing assertions failed. This was not an unverified-runtime case.

## DR RESTORE STATUS

Local disposable pg_dump/pg_restore succeeded. Restored database had 46 public tables, Alembic head d3f5b7a9c1e4, PostGIS, and matching synthetic counts (users 2, classified_offers 1, audit_log 6). Production DR procedure was not assessed.

## NEW FINDINGS

- NEW FINDING P3 — E01/E02 false equivalence and missing regression cases. authority.py:151,159; task008_mutants.py E01/E02; 2026-09-25-task008-mutation.md. Invariant: only parent rows actually locked may carry authority. Raw SQL delete/reinsert under identical parent id plus children: current code 409, each corresponding mutant 200/assertion failure. Expected: these filters treated as load-bearing and regression tests pin parent replacement. Suggested repair: add these two tests and correct mutation review. CANONICAL DECISION REQUIRED: NO. This is a test/evidence defect; current production code is safe in the reproduced cases.
- NEW FINDING P3 — thread completion is used as transaction-order evidence. test_publication_proof_replacement_pg.py:222 and test_publication_authority_race_pg.py:252. Seven targeted cases failed after confirmed blocking and publish 200 because a later DB commit's HTTP response completed first. Expected: prove lock wait, committed state and transaction ordering without relying on response scheduling. Suggested repair: replace list-order assertions with DB-level or gate evidence. CANONICAL DECISION REQUIRED: NO.

Canonical violations: none newly demonstrated. Optional/test improvements: two P3 findings above.

## NONBLOCKING DEBT

Possible revoke starvation; no project-wide machine-readable error-code convention; manager revoked mid-invite; legal-name update vs admin verification; current one-to-one organization/legal-party model; production DR drill and production-readiness work remain. Automatic retries need a client-side cap.

## FINAL VERDICTS

N-05 = CLOSED
N-06 = PARTIALLY_CLOSED
N-07 = CLOSED
N-08 = CLOSED
N-09 = CLOSED
N-10 = CLOSED
N-01 REGRESSION = NONE
N-02 REGRESSION = NONE
F-04 REGRESSION = NONE
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES

## FOUNDATION BASELINE 002

HOMIES_FOUNDATION_BASELINE_002_ACCEPTED
SHA: 36231840ee52d6185e73fda07e54eab33ffe41f3
Accepted for continued Phase 1A development.

## PRODUCTION READINESS

PRODUCTION READINESS:
NOT ASSESSED / NOT READY

## DEPLOYMENT STATUS

DEPLOYMENT STATUS:
NOT DEPLOYED

## CHATGPT HANDOFF

CHATGPT HANDOFF

Project: Homies
Task: TASK-009 — Final Independent Foundation Audit

Audited SHA:
36231840ee52d6185e73fda07e54eab33ffe41f3

Independent auditor:
YES

N-05:
CLOSED

N-06:
PARTIALLY_CLOSED

N-07:
CLOSED

N-08:
CLOSED

N-09:
CLOSED

N-10:
CLOSED

N-01 regression:
NONE

N-02 regression:
NONE

F-04 regression:
NONE

TASK-008:
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES

Foundation Baseline 002:
ACCEPTED

P0:
0
P1:
0
P2:
0
P3:
2

New findings:
P3 E01/E02 are load-bearing, not equivalent; P3 thread-completion assertions misstate database order.

Tests actually run:
Targeted PG/OpenAPI 77 passed, 7 failed; full SQLite 705 passed, 188 skipped; OpenAPI 5 passed; 3 independent PG probes passed; ruff and mypy passed; D01-D17 17/17 killed with green baselines; E01/E02 killed by new probes; E03/E04 survived stable tests.

Python 3.12:
3.12.14 TARGETED RUNTIME VERIFIED; seven timing assertions failed.

DR restore:
Local synthetic PostgreSQL/PostGIS pg_dump/pg_restore verified; production DR not assessed.

Remaining debt:
Two P3 test/evidence fixes; possible revoke starvation; machine-readable error-code convention; manager-revoked-mid-invite and legal-name/admin-verification races; organization/legal-party cardinality; capped automatic retry; production DR/readiness.

Production readiness:
NOT ASSESSED / NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-009.

If HOMIES_FOUNDATION_BASELINE_002_ACCEPTED, formally freeze SHA
36231840ee52d6185e73fda07e54eab33ffe41f3
as Foundation Baseline 002 and generate the first new Poland-wide,
Europe-ready Phase-1A product vertical slice, including the canonical
Homies Product & Growth Doctrine.

---

## Section B — final message delivered in the audit session (verbatim)

# TASK-009 FINAL INDEPENDENT FOUNDATION AUDIT

## EXECUTIVE VERDICT

**TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES.** На SHA `36231840ee52d6185e73fda07e54eab33ffe41f3` виконані задані умови прийняття Foundation Baseline 002. Це прийняття **для продовження розробки Phase 1A**. Виявлено два нові P3 зауваження до тестового покриття; N-06 має вердикт `PARTIALLY_CLOSED`.

Повний [звіт збережено поза репозиторієм](C:/Users/ihorf/.codex/visualizations/2026/09/25/01a0d8bb-87f0-7210-b4d2-f8d718b37da0/TASK-009-final-audit.md).

## INDEPENDENCE

Аудит виконано в новому контексті без участі в реалізації TASK-008. Код, коміти й PR не змінювалися. Probes і mutation copies розміщувалися поза аудиторським checkout.

## EXACT SHA

`git rev-parse HEAD` до й після аудиту: `36231840ee52d6185e73fda07e54eab33ffe41f3`. `git status --short` порожній; HEAD від’єднаний. Перевірено diff від `1b2458c0aa2e73d97475733f68e424e62c7ba0e6`.

## ENVIRONMENT

Окремі одноразові PostgreSQL 16/PostGIS 3.4 та Python 3.12.14 контейнери; checkout змонтовано лише для читання. Усі використані БД були власними синтетичними БД TASK-009. Контейнери після аудиту зупинено й автоматично видалено. CI не запускався.

## COMMANDS ACTUALLY RUN

Перевірки Git SHA/status/log/diff; цільовий PG pytest для TASK-008/006/004/002; повний SQLite pytest; окремий OpenAPI drift pytest; `ruff check app tests`; `mypy app`; D01–D17 і E01–E04 mutation checks у тимчасовій копії; три незалежні PG probes; локальні `pg_dump` і `pg_restore`. Точні результати наведено нижче.

## N-05 ACTUAL LOCKED-PROOF AUDIT

**CLOSED.** `_lock_proof` формує захищений набір із рядків, фактично повернутих `FOR SHARE`, включно з `(mandate, scope)` і `(authority, scope)`. Фінальне рішення використовує `within=locked`.

Прямі SQL `DELETE`/`INSERT` під тим самим ключем для `person_legal_parties`, `organization_legal_parties`, `organization_memberships` і двох таблиць scope дали **409**, `Retry-After: 0` та draft. Незмінений рядок після очікування дозволив **200**. Наступний запит зміг використати замінений рядок. Окремі [незалежні probes](C:/Users/ihorf/.codex/visualizations/2026/09/25/01a0d8bb-87f0-7210-b4d2-f8d718b37da0/task009_independent_probes.py) підтвердили 409, а потім 200 для заміни цілого мандата й організації.

## N-06 RESTRICTED-PROOF AUDIT

**PARTIALLY_CLOSED.** Поточний код зберігає потрібні обмеження для links, membership, organization id, mandate id і scope pair, authority id і scope pair. Перевірені сценарії з другим мандатом того самого principal і другим authority того самого holder не дали запозичення ланцюга чи об’єднання scopes.

**E01 та E02 не є еквівалентними мутантами в поточній схемі.** Після SQL заміни parent і child рядків нові child рядки можуть бути заблоковані, коли parent lock query не повернув жодного рядка. Чинні фільтри в [authority.py](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/app/modules/properties/authority.py:151) правильно дають 409; видалення кожного фільтра в тимчасовій копії дало **200 через незаблокований parent**. E03/E04 витримали сім стабільних тестів кожен; їхня нинішня надлишковість спирається на FK та Property lock і потребуватиме перегляду при зміні схеми. Поточна модель одного LegalParty на Organization не дозволяє перевірити кілька таких зв’язків усередині однієї організації; це вже задокументоване відхилення.

## N-07 ACCEPT LOCK-STRENGTH AUDIT

**CLOSED.** `accept_invitation` бере `FOR UPDATE` перед читанням. Для AGENT і ADMIN два accept серіалізувалися: один 200, другий 404, один join audit, без deadlock. Мутант D13 (`FOR SHARE`) убитий поведінковим assertion.

## N-08 AUTHORIZATION OUTCOME AUDIT

**CLOSED.** Реальний publish API після зміни proof під час очікування повернув усі чотири результати: **403** після втрати verification, **404** після видалення зв’язку, **409** після заміни proof, **200** після косметичного update. Фінальний 403 не мокався.

## N-09 INVITATION LIFECYCLE AUDIT

**CLOSED.** Перевірено переходи: відсутній рядок → `INVITED`; `REVOKED` → `INVITED` лише через явне повторне запрошення; повторне запрошення `INVITED` або `ACTIVE` не змінює рядок. Invite-vs-accept завершився `ACTIVE`. D14–D16 убиті.

## N-10 CONCURRENT FIRST-INVITE AUDIT

**CLOSED.** API-vs-API дав 202/202 і один membership. API-vs-uncommitted raw `INSERT` при `COMMIT` та `ROLLBACK` дав контрольовані 202 і один рядок. Savepoint не зіпсував зовнішню транзакцію. D17 убитий.

## N-01 REGRESSION

**NONE.** Незалежний складений probe: чинний заблокований ланцюг A залишився придатним, з’явився B, publish пройшов через A з 200. Якщо початковий ланцюг втрачено, а B не захищено, поточна спроба дала 409; нова спроба змогла використати B.

## N-02 REGRESSION

**NONE.** Accept-vs-revoke для AGENT і ADMIN перевірено в обох порядках. Застарілий accept не відновив `ACTIVE` після успішного revoke.

## F-04 REGRESSION

**NONE observed.** Цільові PG тести покрили втрату membership, mandate, organization status, LegalParty status, зв’язків і scopes, expiry, незалежні ланцюги, authority revoke та Space archive. Чотири тести впали лише на перевірці порядку завершення HTTP потоків після підтвердженого DB blocking і publish 200; це описано як P3 нижче.

## 409 API CONTRACT

Authority-change conflict має HTTP **409**, `Retry-After: 0` і стабільний `authority.AUTHORITY_CHANGED`. Інші перевірені publish 409 не отримують цей header; OpenAPI drift пройшов. Для HTTP клієнта сигнал розрізнюваний; frontend обробника автоматичного retry не знайдено. Повторення саме цього 409 починає нове рішення без ефекту невдалої спроби. Precheck не відкриває існування чужого property, а відповідь не містить ідентичностей proof. Без обмеження кількості автоматичних спроб клієнт може повторювати запит нескінченно за постійних змін authority.

## DEADLOCK / LOCK ORDER

Публікація бере Property lock перед proof rows; authority revoke та Space archive також починають із Property. Accept/invite/revoke серіалізуються на membership, mandate revoke — на mandate. Конкретного нового циклу не знайдено. Можлива затримка revoke за безперервних публікацій є starvation risk, а не deadlock.

## RAW-SQL GUARANTEE

П’ять необхідних класів proof rows перевірено прямою SQL заміною під час PostgreSQL lock wait. Два додаткові незалежні probes замінили цілі mandate та organization разом із залежними рядками. Гарантія не спирається на заборону DELETE в API.

## MUTATION REVIEW

У зовнішній копії **D01–D17: 17/17 убиті**, кожен після зеленого baseline і через pytest assertion failure. Нові probes вбили E01/E02; отже builder classification «expected equivalent» для них хибна. E03/E04 пережили стабільні тести. Початкові E01/E04 прогони через builder harness мали незелений baseline через assertion порядку потоків і не були зараховані як mutation evidence. TASK-006/004/002 harnesses переглянуто, їхні історичні кількості не перезапускалися. [Результати мутацій](C:/Users/ihorf/.codex/visualizations/2026/09/25/01a0d8bb-87f0-7210-b4d2-f8d718b37da0/task009_mutation_evidence.json) збережені поза repo.

## TEST QUALITY

Перевірки blocker PID, стану Listing, HTTP результату, membership і audit count є змістовними. Assertions у [replacement test](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/tests/test_publication_proof_replacement_pg.py:222) та [publication race test](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/tests/test_publication_authority_race_pg.py:252) прирівнюють порядок завершення HTTP відповідей до порядку DB commit. Пізніший commit може повернути HTTP відповідь раніше після серіалізації publish response. Один такий провал повторено ізольовано.

## TEST RESULTS

- Цільовий PG + OpenAPI: **77 passed, 7 failed** — усі сім на двох assertions порядку потоків.
- Повний SQLite: **705 passed, 188 skipped**.
- Окремий OpenAPI drift: **5 passed**.
- Незалежні PG probes: **3 passed**.
- Ruff: passed. Mypy: passed, 77 source files.
- D01–D17: **17/17 killed** після зелених baselines; E01/E02 killed новими probes; E03/E04 survived стабільний набір.
- Повний PG набір і CI не запускалися.

## PYTHON 3.12 STATUS

Python **3.12.14 TARGETED RUNTIME VERIFIED**. Сім timing assertions не пройшли; це не статус «runtime unverified».

## DR RESTORE STATUS

Локальний `pg_dump`/`pg_restore` синтетичної БД пройшов: 46 public tables, Alembic head `d3f5b7a9c1e4`, PostGIS та однакові підрахунки синтетичних users/classified offers/audit rows. Production DR не оцінювався.

## NEW FINDINGS

- **NEW FINDING P3 — E01/E02 хибно названі еквівалентними.** [authority.py](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/app/modules/properties/authority.py:151), mutation harness і TASK-008 mutation review. Інваріант: parent proof має бути фактично заблокований. Raw SQL заміна під тим самим id дала 409 з чинним кодом, а кожен відповідний мутант — 200 через незаблокований parent. **Очікувано:** ці фільтри є обов’язковими. **Ремонт:** додати обидва probes до репозиторних тестів і виправити mutation review. **CANONICAL DECISION REQUIRED: NO.** Поточний код у відтворених випадках безпечний.
- **NEW FINDING P3 — порядок HTTP потоків помилково використаний як доказ порядку транзакцій.** [replacement test](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/tests/test_publication_proof_replacement_pg.py:222), [race test](C:/Users/ihorf/.codex/worktrees/b65c/homies/backend/tests/test_publication_authority_race_pg.py:252). Сім провалів настали після підтвердженого блокування й publish 200. **Очікувано:** перевіряти DB wait, committed state та порядок транзакцій без залежності від завершення HTTP serialization. **Ремонт:** замінити ці list-order assertions. **CANONICAL DECISION REQUIRED: NO.**

Нових доведених canonical violations немає; обидва findings стосуються тестів та доказів.

## NONBLOCKING DEBT

Можливе revoke starvation; відсутній загальний машинозчитуваний error code; manager-revoked-mid-invite і legal-name/admin-verification races; поточна кардинальність Organization–LegalParty; ліміт автоматичних retry; production DR та інша робота з production readiness.

## FINAL VERDICTS

```text
N-05 = CLOSED
N-06 = PARTIALLY_CLOSED
N-07 = CLOSED
N-08 = CLOSED
N-09 = CLOSED
N-10 = CLOSED
N-01 REGRESSION = NONE
N-02 REGRESSION = NONE
F-04 REGRESSION = NONE
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES
```

## FOUNDATION BASELINE 002

**HOMIES_FOUNDATION_BASELINE_002_ACCEPTED**

SHA: `36231840ee52d6185e73fda07e54eab33ffe41f3` — accepted for continued Phase 1A development.

## PRODUCTION READINESS

```text
PRODUCTION READINESS:
NOT ASSESSED / NOT READY
```

## DEPLOYMENT STATUS

```text
DEPLOYMENT STATUS:
NOT DEPLOYED
```

## CHATGPT HANDOFF

```text
CHATGPT HANDOFF

Project: Homies
Task: TASK-009 — Final Independent Foundation Audit

Audited SHA:
36231840ee52d6185e73fda07e54eab33ffe41f3

Independent auditor:
YES

N-05:
CLOSED

N-06:
PARTIALLY_CLOSED

N-07:
CLOSED

N-08:
CLOSED

N-09:
CLOSED

N-10:
CLOSED

N-01 regression:
NONE

N-02 regression:
NONE

F-04 regression:
NONE

TASK-008:
TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES

Foundation Baseline 002:
ACCEPTED

P0:
0
P1:
0
P2:
0
P3:
2

New findings:
P3 E01/E02 are load-bearing, not equivalent.
P3 HTTP completion-order assertions do not prove database commit order.

Tests actually run:
Targeted PG/OpenAPI 77 passed, 7 failed; full SQLite 705 passed,
188 skipped; OpenAPI 5 passed; 3 independent PG probes passed;
ruff and mypy passed; D01-D17 17/17 killed with green baselines;
E01/E02 killed by new probes; E03/E04 survived stable tests.

Python 3.12:
3.12.14 TARGETED RUNTIME VERIFIED; seven timing assertions failed.

DR restore:
Local synthetic PostgreSQL/PostGIS pg_dump/pg_restore verified;
production DR not assessed.

Remaining debt:
Two P3 test/evidence fixes; possible revoke starvation;
machine-readable error-code convention; manager-revoked-mid-invite
and legal-name/admin-verification races; Organization–LegalParty
cardinality; capped automatic retry; production DR/readiness.

Production readiness:
NOT ASSESSED / NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-009.

If HOMIES_FOUNDATION_BASELINE_002_ACCEPTED, formally freeze SHA
36231840ee52d6185e73fda07e54eab33ffe41f3
as Foundation Baseline 002 and generate the first new Poland-wide,
Europe-ready Phase-1A product vertical slice, including the canonical
Homies Product & Growth Doctrine.
```
