<!-- Archived verbatim from the reviewer's local artifact by the builder, at the reviewer's request.
Reviewed SHA: 77f07ec746ff793132850ed8ee816ab6eefcd323. Verdict: REQUEST_CHANGES. Links point to the
reviewer's machine; that evidence is not in this repository. Disposition:
FE-UX-KRK-002R-verification.md. -->

# FE-UX-KRK-002 + FE-UX-KRK-002R — незалежне фінальне рев’ю
Дата звіту: 2026-11-07. Основні запуски: 2026-11-06; завершальні probes: 2026-11-07.
Роль: незалежний read-only аудитор. Класифікація R1 frontend.

## A. Identity

- Репозиторій: ihorfroliak/homies.
- Accepted main: `d103a4cf5c966320efe2b13a2fae9b73f601d276`.
- PR25 / база combined diff: `6c6bb0237112653b37b71769d0a5fdc0d0f1fcba`.
- Первинний кандидат: `353324acb3d7784a4f798f5eaa400dbef30ea136`.
- Фінальний кандидат: `77f07ec746ff793132850ed8ee816ab6eefcd323`.
- Tree: `e4f064db7fc5c02c8e44377d9a63c0f0945a9ec6`.
- Перевірений combined diff: `6c6bb023..77f07ec`, 54 файли, +2852 / −286.
- Remote SHA, tree та послідовність ancestry підтверджено. Власний worktree pinned до фінального SHA.
- [CI 42204003626](https://github.com/ihorfroliak/homies/actions/runs/42204003626): SUCCESS 6/6 — image, contracts, backend, monitoring, web, secrets. GitHub API підтвердив head_sha фінального кандидата та tree; event=push. Порожня відповідь PR-only workflow connector не означає відсутність CI.
- PR25 і PR26 залишаються відкритими Draft. PR26 досі має head353324a та base6c6bb02; hardening77f07ec у нього ще не включено. Незалежний gate PR25 окремий, OPEN.

## B. Findings

### F-01 — P2 MEDIUM: втрата фокуса після недоступної останньої порції оферт

**Місце:** [map-card.tsx:70](C:/Users/ihorf/.codex/worktrees/fe-ux-krk002r-review/homies/frontend/web/src/app/wynajem/[[...miejsce]]/map-card.tsx:70), також кнопка pagination біля рядка125.

**Відтворення:** відкрити стек з понад10 оферт; перші10 успішні; усі наступні на останній сторінці повертають404 або503; натиснути «Pokaż kolejne». Кнопка зникає, нових посилань немає, фокус опиняється поза карткою: BODY у Chromium, SECTION у WebKit.

**Доказ:** [browser-extra.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/browser-extra.log): 4 відтворення, обидва статуси × два браузери. [extra-unit.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/extra-unit.log): 2 відповідні regression assertions падають.

**Причина:** effect фокусує лише посилання за індексом попередньої кількості оферт, але такого посилання може не бути; focusFrom після цього скидається. Немає запасної цілі.

**Порушення/вплив:** вимога контракту про передбачувану клавіатурну навігацію; користувач втрачає позицію після штатного error/gone стану. Новий дефект combined diff, компонент pagination додано в FE-UX-KRK-002; не приписується PR25.

**Мінімальна корекція:** визначити доступну запасну ціль після завантаження: Retry для failed або кнопка закриття/доступний status для gone. Зберігати зрозумілий фокус і під час очікування.

**Регресія:** остання порція повністю404, повністю503, змішані результати, успішний retry; перевірка activeElement, не лише наявності тексту. CANONICAL DECISION: **не потрібна**.

### F-02 — P2 MEDIUM: UX-R1 не охоплює доступні назви кнопок

**Місце:** [viewings.tsx:120](C:/Users/ihorf/.codex/worktrees/fe-ux-krk002r-review/homies/frontend/web/src/engagement/viewings.tsx:120).

**Відтворення:** майбутній REQUESTED viewing, schedule ще завантажується або повертає503. Видимий текст каже «Wczytujemy godzinę…» / «Nie udało się ustalić godziny», але доступна назва кнопки: «Potwierdź: 1 grudnia 2099 12:00 (UTC)».

**Доказ:** [time-label.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/time-label.log): 2/2 додаткові negative assertions падають, loading і failure. Це перевірка accessible name в DOM, не запуск фізичного скрінрідера.

**Причина:** видимий час переведено на ViewingWhen, але aria-label безпосередньо викликає viewingTime з undefined timezone. Відсутність відповіді помилково перетворюється на UTC.

**Порушення/вплив:** UX-R1 вимагає не повідомляти невідому годину; користувач допоміжних технологій отримує іншу інформацію, ніж зрячий. Це **не нова регресія відносно PR25**: старий прояв залишився в області заявленого виправлення.

**Мінімальна корекція:** формувати доступну назву з того самого стану timezone, що й видимий час; не включати годину до підтвердження зони. FE-003 fallback з явним UTC для справді відсутнього розкладу зберегти.

**Регресія:** accessible names для loading,503,retry success,timezone:null/404; requester/provider дії. CANONICAL DECISION: **не потрібна**.

### F-03 — P3 LOW: C6 помилково оголошено еквівалентним мутантом

**Місце:** [builder receipt:39](C:/Users/ihorf/.codex/worktrees/fe-ux-krk002r-review/homies/docs/reviews/FE-UX-KRK-002R-verification.md:39), [map-card.tsx:48](C:/Users/ihorf/.codex/worktrees/fe-ux-krk002r-review/homies/frontend/web/src/app/wynajem/[[...miejsce]]/map-card.tsx:48), тест closed-card [map-card.test.tsx:59](C:/Users/ihorf/.codex/worktrees/fe-ux-krk002r-review/homies/frontend/web/src/app/wynajem/[[...miejsce]]/map-card.test.tsx:59).

**Відтворення:** почати першу порцію, поки її promises ще не завершено натиснути pagination; новий effect успішно показує11 оферт; завершити старі aborted promises пізніше. Після видалення abort guard старе завершення перезаписує loaded і одинадцята оферта зникає.

**Доказ:** [c6-baseline.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/c6-baseline.log) — original PASS; [c6-mutant.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/c6-mutant.log) — assertion FAIL, не compile failure. Розклад завершень контрольований синтетичним тестом; не заявляю, що цей race спостерігався в реальній мережі.

**Причина:** existing тест перевіряє unmount старої картки, але не superseded effect у тій самій змонтованій картці. Твердження «abort check has no observable effect» хибне.

**Вплив:** прогалина regression coverage та завищений mutation claim. Захист у фінальному коді **присутній і працює**.

**Мінімальна корекція:** додати цей сценарій, повторити C6 і виправити receipt; не видаляти guard. CANONICAL DECISION: **не потрібна**.

P0/P1 у перевіреному diff не виявлено; це не сертифікація всього проєкту.

## C. UX-R1…UX-R6

| Пункт | Статус | Доказ та межа |
|---|---|---|
| UX-R1 timezone | PARTIAL | Видимі loading/failure/retry, no-schedule fallback, DST Warsaw, інша зона, REQUESTED/CONFIRMED і минулі viewing проходять. F-02 лишається в aria-label. |
| UX-R2 return origin | FIX VERIFIED | Listing-bound origin, saved/home/direct fallback, фільтри/сортування, Back/Forward. Додаткові encoded/double-encoded, dot segments, control chars, fragment і prototype-key inputs відхилено; open redirect у перевірених входах не знайдено. |
| UX-R3 selection | PARTIAL | Dissolved group закривається, валідний лишається; privacy stacks/координати не змінюються. Rapid zoom/resize/reopen PASS у Chromium/WebKit. F-01 лишається на error pagination. |
| UX-R4 freshness | FIX VERIFIED | Повторне відкриття читає заново; changed price,404,503,429 unit, abort cleanup перевірено. C6 guard працює, його builder mutation disposition неправильна. Зміни ціни ін’єктовані на BFF, не через зміну реального запису ціни в БД. |
| UX-R5 history/bfcache | PARTIAL | Звичайні Back/Forward, pre-hydration sort, no-JS та synthetic pageshow проходять. Genuine BFCache NOT VERIFIED: persisted=false. |
| UX-R6 recovery | FIX VERIFIED | 18/18 Chromium desktop+mobile recovery tests через proxy до реального API;503,429,timeout, repeated retry, збереження404, захист від error-detail leak. GET-retry не повторює business writes. |

UX-R3 «resize обов’язково закриває картку» — **FINDING REJECTED WITH EVIDENCE**: якщо група збереглась, картка має лишатись. Це окреме твердження, не скасування F-01.

## D. Browser matrix

Playwright1.63.0. Windows: Chromium153.0.8010.12, WebKit26.6. Ізольований Linux: Firefox155.0.

| Набір | Passed | Failed | Skipped | Межа виконання |
|---|---:|---:|---:|---|
| Chromium final, штатна повна desktop+mobile suite | 203 | 0 | 7 | Усі210 запущено;7 skips за viewport/pointer умовами |
| WebKit final,4 проблемні тести | 1 | 3 | 0 | Лише задані4, повний WebKit suite не повторювався |
| WebKit base353324a, ті самі4 | 1 | 3 | 0 | Той самий браузер, production build, API, fixtures; відрізняється локальний порт |
| WebKit локальний HTTPS: session/save/saved return | 1 | 0 | 0 | Синтетичний користувач, self-signed локальний proxy |
| Rapid zoom/resize/reopen + keyboard auth return, Chromium/WebKit | 4 | 0 | 0 | Додаткові незалежні probes |
| HTTP cookie transport, Chromium/WebKit | 2 | 0 | 0 | Діагностичні тести, не загальна browser certification |
| Error pagination focus, Chromium/WebKit | 0 | 4 | 0 | Очікувані падіння F-01 |
| Firefox focused public navigation | 7 | 1 | 0 | Map test не досяг assertions через відсутній WebGL; решта Firefox suite NOT EXECUTED |

### Чотири WebKit failures

1. **foundation — home renders the Polish shell with a working skip link.** Помилка `toBeFocused: Expected focused, Received inactive` для «Przejdź do treści». Однаково final/base. Успадкований збій focus expectation; повна відповідність native Tab/Safari ще не підтверджена. Не нова hardening regression.
2. **navigation — navigation stays usable at narrow widths, closes on Escape and preserves auth return focus.** Та сама помилка для «Zaloguj się» після pointer-open/Escape, final/base. Додатковий сценарій із keyboard activation повертає фокус і проходить. Успадкована проблема pointer/focus interaction; не підстава заявляти повну WebKit accessibility.
3. **recovery — a listing recovers after a timeout.** Builder: `page.goto: Test timeout of30000ms exceeded`, очікування load. Окремо final/base проходить; Chromium desktop/mobile теж проходить. Причина попереднього shared-run timeout **UNRESOLVED / не відтворена**, не оголошена виправленою.
4. **saved list — a listing opened from the saved list returns to the saved list.** `authenticated: Expected true, Received false`, однаково final/base на HTTP. Вимірювання через request.allHeaders: Chromium надсилаєcookie та authenticated=true; WebKit зберігає Secure-cookie, але на HTTP не надсилає, authenticated=false. На HTTPS реєстрація, сесія, save та «Wróć do zapisanych» проходять. Класифікація: **environment/origin limitation**, не регресія повернення.

Діагностика Firefox підтвердила webgl=false, webgl2=false. Map test **NOT VERIFIED**, не product FAIL. OS security controls не змінювались.

Методологічне уточнення: ранній browser-extra probe використовував request.headers(), який не є надійним доказом Cookie header. Його cookie-presence boolean не використано у висновках; правильний повтор з allHeaders збережено в [cookie-transport.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/cookie-transport.log). Focus assertions того раннього probe від цього не залежать.

## E. Test credibility

- **Unit:** незалежно319/319,33 файли. Додатково: path-negative PASS; C6original PASS;2focus та2accessible-name assertions FAIL. Не змішую ці навмисні regression probes зі штатними319.
- **Build:** production build final та353324a успішні на ізольованому Node24.15.0. Окремий локальний lint/typecheck повторно не заявляється; зелений CI підтверджено.
- **E2E:** власна disposable PostgreSQL16/PostGIS3.4 БД, Python3.12 API, existing guarded seeds. Повний Chromium result незалежно відтворює203/7.
- **Mutations:** перевірені33 визначення та builder summary30CAUGHT/3SURVIVED. Повний33-mutant sweep незалежно не повторювався. R1 weakened regex і R3 removed length bound еквівалентні щодо accepted return paths за чинного bounded codec/fixed-point; early length guard має окрему ресурсну користь. C6 **не еквівалентний**, спростовано runtime assertion. Builder runner допускає TypeError/timeout як catch: сама його summary не замінює індивідуальний assertion log. Не зараховую compiler failure як kill.
- **Accessibility:** automated axe у штатному Chromium suite, keyboard/focus додаткові probes. Screen reader і Safari на Apple hardware NOT VERIFIED; дві підтверджені прогалини F-01/F-02.
- **Recovery:** реальний server→proxy→API шлях; ін’єкція помилки не видається за actual backend defect.
- **Genuine BFCache:** не виконано persisted=true. Chromium повідомляє MainResourceHasCacheControlNoStore, JsNetworkRequestReceivedCacheControlNoStoreResource, BrowsingInstanceNotSwapped, BackForwardCacheDisabledForDelegate. no-store явно заданий у backend client та BFF/session і пов’язаний з існуючою freshness/privacy поведінкою; окремого рішення «заборонити BFCache всюди» не встановлено. Політику не змінював.
- **Performance:** grouping O(n²), запускається на zoomend/resize; cleanup listeners/markers/map присутній. Card paging порціями10, кеш лише життя картки, repeat-open читає знову. Rapid cycles проходять; heap/leak soak, великі польові набори та field-performance не сертифіковані.
- **Visual:** viewport/overflow/first-screen CTA перевіряються штатними E2E; зіставлення з001C локальне, не нове погодження всього дизайну. Conversion/retention не оцінювались.
- Додатковий advisory specialist не завершив роботу через runtime usage limit; висновок і наведені відтворення виконані основним незалежним аудитором. Його окремий висновок не зараховано.

## F. Source integrity

- Перевірено combined B+C; diffA(PR25) не приписаний builder і не переаудитований.
- Зміни обмежені frontend/web і документацією. Backend, migrations, API snapshot, package-lock без змін у combined diff.
- Власні pinned worktrees чисті; фінальнийHEAD/tree збігаються.
- Додаткові тести та C6 mutation лише в disposable archive copies поза audited worktree. map-card.tsx після mutation відновлено; SHA256 збігається з pinned source: `cb0dd63882963b66e61eacfa14079383a963006f21f0caea3364beb52a6d0bea`.
- Repository source, protected worktrees, PRs не змінені. Commit/push/merge/deployment не виконувались.
- Міграції лише в tmpfs disposable DB homies_krk002ra_e2e. Власні krk002ra-api та krk002ra-pg після тестів зупинені. Founder containers не запускались. Local media volume та evidence лишені без destructive cleanup. Реальних providers/даних немає.
- Звіт є локальним audit artifact, **ще не repository acceptance record**; його архівування в репозиторії має виконати уповноважений writer.

## G. Remaining blockers

**До merge:** виправити F-01 і F-02, додати focused regressions; виправити F-03 evidence/coverage; отримати CI та вузьку незалежну перевірку нового exactSHA. Окремо потрібне завершення gatePR25; hardening77f07ec ще відсутній у PR26. Поточний зелений CI не покриває майбутні зміни.

**Неблокуючі для цього diff / межі:** успадковані WebKit focus failures; unresolved shared-run timeout; genuineBFCache; Firefoxmap; реальні скрінрідери; field-performance. Не переносити їх у PASS.

**Рішення власника:** фінальне приймання/merge; за потреби прийняття залишкової browser matrix та кольору StareMiasto. Для трьох запропонованих bounded repairs нової бізнес-семантики не потрібно.

**Поза рев’ю:** production readiness, staging launch, PR25 acceptance, backend baseline. Production/deployment цим звітом не дозволені.

## H. Verdict

**REQUEST_CHANGES**

Кандидат має сильну базу: CI6/6, незалежні319unit та203E2E пройдено. Водночас дві відтворені UX/accessibility прогалини та неправильний висновок щодо C6 не дають закрити remediation як повністю прийнятий. Потрібен bounded repair, не новий загальний аудит Homies.

## Evidence index

- [CI identity](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/ci-identity.json)
- [Unit](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/unit.log), [build](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/build.log)
- [Chromium full](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/chromium-full.json)
- [WebKit final](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/webkit-final-four.json), [same base tests](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/webkit-base-four-rerun.json)
- [HTTPS](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/https.log), [cookie transport](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/cookie-transport.log)
- [Firefox suite](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/firefox.log), [WebGL diagnostic](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/firefox-diagnostic.json)
- [Rapid stress](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/rapid-stress.log)
- [Focus repro](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/browser-extra.log), [additional unit probes](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/extra-unit.log)
- [Timezone aria repro](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/time-label.log)
- [C6 original](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/c6-baseline.log), [C6 mutant](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/c6-mutant.log)
- [Checkpoint](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/FE-UX-KRK-002R-AUDIT/CHECKPOINT.md)

