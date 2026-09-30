# ARCHIVE — TASK-012A Codex independent audit of TASK-012

| Provenance | Value |
|---|---|
| Audit task | TASK-012A — Independent Audit of TASK-012 |
| Auditor | Codex (OpenAI Codex Desktop), independent of the builder |
| Audited SHA | `c4c8bfac7f59a0930d9403d1100f35dccf003ae6` (branch `claude/TASK-012-listing-freshness-availability-quality`) |
| Date | 2026-09-27 (report file written 2026-09-27 22:33 local) |
| Verdict | **TASK_012_REQUIRES_TARGETED_FIXES** — P0 0 / P1 0 / P2 1 (F12A-01, grouped) / P3 0 |
| Source file | `%USERPROFILE%\.codex\visualizations\2026\09\13\01a09879-13f3-7382-bd99-6b9c006a0ff4\TASK-012A\TASK-012A-audit.md` (evidence beside it; working copy in `%TEMP%\homies-task012a-c4c8bfa`) |
| Source SHA-256 | `57fc7cb265a31488b668bc452ab677a74f1fed6f005877fa39ebebaf39961e9f` |
| Codex session | thread `01a09879-13f3-7382-bd99-6b9c006a0ff4` (Codex Desktop) |
| Archived by | Claude Code (builder) at the start of TASK-012R, 2026-09-27 |

Everything below the rule is the auditor's report **byte-for-byte as written**
(not rewritten, sanitised or reconstructed). Links inside it point at the
auditor's worktree and evidence directory on the founder's machine; they are
kept as written. The finding is repaired in TASK-012R.

---

# TASK-012A — Independent Audit of TASK-012

**Verdict: TASK_012_REQUIRES_TARGETED_FIXES**

Audited SHA: **c4c8bfac7f59a0930d9403d1100f35dccf003ae6**  
Accepted parent: ed9cf1b49f70716bd214a3212b2e7497ca5078ec  
Date: 2026-09-27  
Independent auditor: YES. This session did not implement TASK-012.

The required UTC runs, migration checks, authorization/concurrency probes and existing mutations passed. Additional independent probes exposed one P2 time-zone correctness finding with three manifestations: DST changes freshness thresholds, move-in classification uses the session's date, and reminder deduplication changes with the timestamp's offset. This finding blocks acceptance of this SHA. It does not reopen Foundation Baseline 002.

## Gates

| Gate | Verdict | Evidence / qualification |
|---|---|---|
| FRESHNESS | NEEDS_FIX | Correct on UTC; F12A-01 shows wrong elapsed-time thresholds across Warsaw DST. |
| PUBLIC_VISIBILITY | NEEDS_FIX | All seven paths enforce freshness in UTC; wrong threshold still admits stale supply under a non-UTC session. |
| CONCURRENCY | ACCEPTED | Six required races reproduced; actual PostgreSQL blocker/waiter evidence where applicable. |
| MIGRATION | ACCEPTED | Evidence-only backfill, unknown-status refusal/rollback, data preservation, constraint and downgrade tests. |
| AVAILABILITY | NEEDS_FIX | NULL semantics and CAS pass; known-date NOW/FROM_DATE violates the mandated UTC date. |
| QUALITY | ACCEPTED | Derived, deterministic, required/recommended separation, owner-only; no ranking use found. Freshness inputs remain subject to F12A-01. |
| EVENTS_AUTOMATION | NEEDS_FIX | Same-zone sequential/concurrent dedup passes; different session zones emit two reminders for one cycle. |
| PRIVACY_SECURITY | ACCEPTED | Targeted authorization, location/contact privacy and owner/public separation checks pass. |

P0: 0. P1: 0. **P2: 1 grouped finding.** P3: 0.

No Phase-1A acceptance declaration is issued. The accepted parent remains the baseline pending a bounded repair and independent re-audit.

## F12A-01 — P2 MEDIUM: temporal invariants depend on PostgreSQL session time zone

This is one grouped normalization finding, with three separately reproduced effects. Its precondition is a non-UTC PostgreSQL session, or a change of session zone between maintenance runs. Default UTC behavior passed. No claim is made about the time zone of production; production was not accessed.

**Locations**

- [freshness.py:63](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/modules/properties/freshness.py:63): _aware preserves an existing non-UTC tzinfo; db_now returns it.
- [freshness.py:85](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/modules/properties/freshness.py:85): PostgreSQL cutoff subtracts a day-bearing interval from timestamptz.
- [freshness.py:97](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/modules/properties/freshness.py:97): Python age uses those datetimes; reconfirm_at/stale_at likewise add days without canonicalizing instants.
- [freshness.py:158](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/modules/properties/freshness.py:158): dedup key serializes the unnormalized timestamp with isoformat().
- [router.py:157](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/modules/properties/router.py:157): move_in compares available_from with now.date().
- [db.py:24](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/backend/app/core/db.py:24): connections have a timeout but no enforced UTC session setting.

**Violated requirements:** TASK-012A exact 14/21-day boundaries, consistent public visibility, UTC move-in classification and event deduplication; D-59/D-60/D-64/D-65; [04a §18–§19](C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies/docs/canonical/04a-DOMAIN-SCHEMA-v1-CLARIFICATIONS.md:148).

### A. Freshness thresholds shift across Europe/Warsaw DST

On a real disposable PostgreSQL database, set the transaction's TimeZone to Europe/Warsaw. Pin only the decision instant, retaining the session's ZoneInfo representation for the Python clock and running the actual SQL predicate and HTTP handlers.

| Decision instant UTC | Confirmation UTC | Actual elapsed age | Required | Observed list / detail |
|---|---|---|---|---|
| 2026-11-01 12:00 | 2026-10-11 12:00 | Exactly 21 days | Hidden / 404 | Included / 200 |
| 2026-04-01 12:00 | 2026-03-11 12:30 | 20 days 23h 30m | Visible / 200 | Excluded / 404 |

A PostgreSQL interval carrying calendar days crosses a DST boundary differently from a fixed elapsed duration. Python subtraction of datetimes sharing the same ZoneInfo similarly uses wall-time arithmetic. The data did not change, but the session zone changed the outcome. The same cutoff helper is used by maintenance; the reproduced HTTP failures are sufficient to establish the defect without claiming an additional executed sweep/DST test.

Evidence: [dst_session_probe.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst_session_probe.py), [dst-session.xml](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst-session.xml). Both boundary assertions failed, with no setup errors.

An earlier diagnostic used the same pinned UTC instant in Python and exposed list/detail disagreement while the SQL session was Warsaw: [dst_probe.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst_probe.py), [dst.xml](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst.xml). Those two failures isolate SQL calendar arithmetic. The final session-clock reproduction above is the faithful model of the existing db_now representation; the diagnostic is not presented as an additional production interleaving.

### B. Move-in NOW/FROM_DATE uses the wrong date

This probe used the actual database clock without mocking it. At 2026-09-27 20:25:21 UTC, a +14:00 database session returned 2026-09-28 10:25:21+14:00. An offer with available_from = 2026-09-28 was returned as NOW by both list and detail. D-64 requires FROM_DATE until the database UTC date reaches September 28.

Evidence: [timezone_probe.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/timezone_probe.py), [timezone.xml](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/timezone.xml), one assertion failure. The +14 zone makes the boundary reproducible at the audit's execution time; the same code also uses Warsaw's date rather than UTC near midnight.

### C. Same confirmation cycle emits a second reminder after a session-zone change

Set a single active listing's confirmation to 2026-09-11 12:00:00Z, and run the real sweep at 2026-09-27 12:00:00Z, committing once in UTC and once in Europe/Warsaw. Both runs report that listing as reminded. Two ListingReconfirmationDue rows are stored.

The keys differ only in the representation of the same instant:

    ListingReconfirmationDue:<same-listing>:2026-09-11T12:00:00+00:00
    ListingReconfirmationDue:<same-listing>:2026-09-11T14:00:00+02:00

Expected: one event and an empty reminded list on the second pass. The unique constraint cannot detect equivalent instants encoded as different strings. No actual email/SMS/push delivery occurred; transport is intentionally not routed yet.

Evidence: test_reminder_cycle_deduplicates_across_session_timezones in [dst_session_probe.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst_session_probe.py), [dst-session.xml](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/dst-session.xml). The assertion observed 2 events rather than 1.

**Suggested bounded repair:** normalize database instants to UTC before Python subtraction/addition, date extraction and cycle-key serialization; make PostgreSQL cutoff arithmetic use the same elapsed-time basis independent of TimeZone. Enforcing UTC on every API/worker/CLI session can support that invariant, but merely normalizing db_now in Python leaves the SQL interval issue. Add regressions for both DST directions, UTC date boundaries and equivalent-instant event retries. Preserve all current authorization and lock ordering.

**Expected behavior:** the same stored instants and decision instant produce the same state, public visibility and cycle key in every session zone; move_in uses the database UTC date.

**CANONICAL DECISION REQUIRED: NO.** The existing requirements already determine the expected behavior. No source repair was made in this audit.

## Independent concurrency evidence

The independent harness uses real API calls, separate PostgreSQL transactions and pg_blocking_pids assertions for specific waiter/blocker pairs. Temporary gates are in-memory test instrumentation; source files are unchanged.

| Scenario | Database evidence | Result |
|---|---|---|
| Confirmation in progress vs sweep | Confirmation PID 171 held its real update transaction open; sweep completed while that lock remained held. | SKIP LOCKED omitted the row; confirmation 200, final active. |
| Sweep first vs confirm | Confirm PID 171 blocked on sweep PID 176. | Sweep committed, confirmation resumed with 200, final active. |
| Archive vs confirm | Confirm PID 171 blocked on archive PID 177. | After archive commit, confirmation 409; archived remained terminal. Pause/publish/confirm also refused revival. |
| Revoke before protected decision | Request gated after preliminary authority check; revocation committed before protected authorization resumed. | Reactivation denied with 403/404, final stale, public detail 404. No blocking claim is needed for this ordered case. |
| Revoke during reactivation | Revoke PID 171 was verified blocked by protected confirmation PID 177. | Confirmation and subsequent revoke both 200; final paused, public detail 404. |
| Space archive during reactivation | Space archive PID 177 was verified blocked by protected confirmation PID 171. | Confirmation and archive both 200; final paused, public detail 404. |
| Two availability updates | Competing CAS updates waited behind a held row lock and used the same expected_version. | One 200 and one 409; version advanced once; confirmation and publication timestamps unchanged. |
| Duplicate event in one zone | Competing INSERT waited on the first uncommitted identical event. | Exactly one event; loser returned False; its savepoint contained the conflict and the transaction remained usable. |

Evidence: [probes.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/probes.py), [probes.log](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/probes.log), [probes.xml](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/probes.xml). All 15 cases passed. These establish locking behavior; they do not override the separate time-zone failures.

## Other verified requirements

- **Authoritative clock:** publication and confirmation used actual PostgreSQL time when the Python clocks were deliberately moved to year 2001. Initial published_at equaled last_confirmed_available_at.
- **All seven paths:** at 14d minus 1 microsecond, exactly 14d, and 21d minus 1 microsecond, list/detail/contact/conversation/slots/request/media remained available as appropriate. At exactly 21d, list excluded the listing and the other six returned 404, without any sweep and while the stored status remained active. These were pinned UTC decision-time tests on PostgreSQL.
- **Migration b8d0f2a4c6e8:** tested upgrade/backfill and downgrade regressions. Independently compared complete JSON snapshots of Properties, Addresses, Spaces, Listings, PropertyAuthorities and price components. An unknown status caused refusal before the column was installed; the Alembic revision and all six tables remained unchanged. After explicitly correcting the synthetic invalid fixture, upgrade preserved existing data and set confirmation exactly to published_at, including NULL. No invented confirmation or upgrade lifecycle change. A NULL-evidence active listing was identified by preflight.
- **Availability:** unknown stays NULL/UNKNOWN and remains eligible for general search when otherwise valid; explicit available_by excludes it. Input validation and stale-version rejection passed. Updating availability does not renew freshness. UTC date classification remains blocked by F12A-01.
- **Quality:** repeated owner responses matched; required blockers and recommendations were distinct, percentage matched checks, strangers did not receive another owner's listings, and public list/detail exposed neither quality nor freshness_detail. Source inspection found no ranking use.
- **Trust/privacy:** the new API fields describe currentness, not identity/property verification. Exact street, building, unit, postcode, raw private address, exact coordinates and contact sentinels did not leak through the checked public JSON surfaces. Contact disclosure to an authorized viewer was tested separately as an intended path. Existing media/location/privacy regressions passed. This is an API audit, not a claim that a future frontend was reviewed.
- **Events:** payload keys were limited to listing/property identifiers, confirmation timestamp and policy durations. No private address/coordinate/contact payload. Same-zone event retries passed; cross-zone cycle dedup failed as above. Repeating the confirm API is a new confirmation cycle; this report does not claim HTTP exactly-once semantics. Publication stamps confirmation, whereas the current DomainEvent seam is exercised by confirm/sweep; delivery is out of scope.

## Tests actually run

Runtime: Python **3.12.14**, PostgreSQL **16.4**, PostGIS **3.4.3**. Package details: [environment.json](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/environment.json).

| Check | Actual result |
|---|---|
| Targeted regression run with disposable PG | **132 passed**, no failures/skips |
| Included TASK-012 files | 36 SQLite freshness cases + 11 PostgreSQL freshness cases |
| Included additional regressions | 23 location + 10 PG location + 27 geography repair + 14 classifieds search + 6 publication races + 5 OpenAPI drift |
| Full SQLite suite | **780 passed / 245 skipped** |
| Independent primary PG probes | **15 passed** |
| Additional UTC-date regression | **1 failed**, expected-contract assertion |
| Additional DST diagnostic | **2 failed**, expected-contract assertions |
| Final session-clock DST and reminder regressions | **3 failed**, expected-contract assertions |
| Ruff | Clean |
| Mypy | Clean, **86 source files**; existing untyped-function notes |
| F01–F16 mutations | **16/16 killed**, every green baseline rerun first |
| Full PostgreSQL suite | **NOT RUN**; targeted PG, migration and independent probes were run |
| CI | **NOT RUN** |

The 6 additional failing case executions are not six separate findings: two are diagnostics, and four reproduce the three manifestations of F12A-01. None is a collection/setup failure or model safeguard limitation. The builder's older 779 SQLite count is not substituted for the 780 actually observed here. The builder's full-PG result is not claimed as an independent run.

Commands were executed in containers against a read-only mount of the exact worktree. [run.py](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/run.py) records the test lists, pytest arguments and static-check commands. New probe commands used:

    python -m pytest -p tests.conftest /audit/probes.py -q -s
    python -m pytest -p tests.conftest /audit/timezone_probe.py -q -s
    python -m pytest -p tests.conftest /audit/dst_probe.py -q -s
    python -m pytest -p tests.conftest /audit/dst_session_probe.py -q -s

All PostgreSQL URLs referred only to audit-owned local disposable databases. Logs/XML are preserved beside this report.

## Mutation assessment

[mutations.json](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/mutations.json) and mutation-01 through mutation-32 logs/XML record all baseline/mutant runs. Every mutated run had a test failure, zero pytest errors, and a passing baseline.

| Mutation | Observed kill |
|---|---|
| F01 / F02 | Stale listing appeared in list / detail returned 200 instead of 404 |
| F03 / F04 | Exactly-21d inclusion / exactly-14d classified FRESH |
| F05 | Sweep waited on a confirmation row instead of skipping it |
| F06 / F07 / F08 | Unauthorized confirmation / archived confirmation / invalid-space reactivation succeeded |
| F09 | Sweep changed non-active lifecycle rows |
| F10 | Repeat sweep reported another reminder |
| F11 | Publication left confirmation NULL |
| F12 | NULL availability matched explicit date filter |
| F13 | Removed API validation reached the real minimum-term DB CHECK and raised IntegrityError |
| F14 | Photo recommendation became a required blocker |
| F15 / F16 | Backfill invented current time / migration changed status |

F05 is a compound mutant. Its actual kill was the unwanted wait, not a separately observed newer-confirmation overwrite; do not treat it as independent coverage of each removed guard. F13's DB exception is a meaningful validation regression, not a setup failure. F06 contains two selected cases, but -x stopped after the first unauthorized behavior failed.

All 212 copied backend files matched their original SHA-256 after mutation restoration: [mutation-restoration.json](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/mutation-restoration.json). Mutations ran only in an external disposable copy; the audited worktree was never mutated. This set covers its advertised default-zone behavior but misses the now-reproduced time-zone cases.

## Performance and remaining scope

Observed public list SELECT counts for limits 1/5/10: **6/10/15**. Each request performed **one** scalar database-clock read. Source inspection and tracing found no new freshness query per listing. The parent benchmark was not independently rerun; its recorded 5/9/14 is builder evidence only.

Existing public-place N+1 and owner-view query amplification remain debt. The stale transition batch is bounded, but the due-reminder scan is not; this is a scalability note, not an independently demonstrated pathological failure. Reminder delivery, worker scheduling, future SEO handling, expires_at/available_until/maximum_lease_months, and existing lowercase status vocabulary remain documented scope/debt. No transport or paid provider was activated.

Full PG/CI/DR/production validation is not inferred from these runs. Python 3.12 was verified for the checks actually run.

## Isolation and completion

Detached worktree: C:/Users/ihorf/.codex/worktrees/homies-task012a-audit/homies

HEAD and clean tracked/untracked status were verified after testing: [final-integrity.json](C:/Users/ihorf/.codex/visualizations/2026/09/13/01a09879-13f3-7382-bd99-6b9c006a0ff4/TASK-012A/final-integrity.json). No source changes, commits, pushes, PRs or deployments were made. No production or external target was accessed. The only databases used contained synthetic fixtures.

The audit-owned PostgreSQL container, verified by full ID and TASK-012A label, was removed with its anonymous volumes after the test runners exited. The worktree and external evidence remain available for review.

PRODUCTION READINESS: **NOT ASSESSED / NOT READY**  
DEPLOYMENT: **NOT DEPLOYED**

## CHATGPT HANDOFF

Project: Homies  
Task: TASK-012A — Independent Audit of TASK-012

Audited SHA:  
c4c8bfac7f59a0930d9403d1100f35dccf003ae6

Independent auditor: YES

Freshness: NEEDS_FIX  
Public visibility: NEEDS_FIX  
Concurrency: ACCEPTED  
Migration: ACCEPTED  
Availability: NEEDS_FIX  
Quality: ACCEPTED  
Events/automation: NEEDS_FIX  
Privacy/security: ACCEPTED

TASK-012: TASK_012_REQUIRES_TARGETED_FIXES

P0: 0  
P1: 0  
P2: 1  
P3: 0

New findings: F12A-01 — session-time-zone-dependent freshness thresholds, move-in date classification and event cycle deduplication.

Tests actually run: Python 3.12.14; targeted 132 passed; full SQLite 780 passed / 245 skipped; independent primary PG probes 15 passed; additional time-zone cases 6 assertion failures (2 diagnostic + 4 final reproductions); F01–F16 16/16 killed with green baselines and restoration verified; ruff clean; mypy 86 files clean; OpenAPI 5 passed. Full PG and CI not run.

Known debt: public-place N+1; owner-view query amplification; unbounded due-reminder scan; reminder transport/scheduling; documented deferred listing fields and SEO; full PG/CI/DR/production not independently assessed here.

Production readiness:  
NOT ASSESSED / NOT READY

Deployment:  
NOT DEPLOYED

REQUEST TO CHATGPT:  
Adjudicate TASK-012A. Request a bounded builder repair for F12A-01 and an independent re-audit before accepting TASK-012. Do not establish this SHA as accepted or begin TASK-013 on this result. If TASK-012 is subsequently accepted, formally establish the accepted repaired SHA as the TASK-012 Phase-1A slice and proceed with TASK-013 Search, Map & Marketplace Discovery.

