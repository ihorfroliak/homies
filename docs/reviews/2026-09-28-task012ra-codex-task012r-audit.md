# ARCHIVE — TASK-012RA Codex narrow independent re-audit of TASK-012R

| Provenance | Value |
|---|---|
| Audit task | TASK-012RA — Narrow Independent Re-audit of TASK-012R |
| Auditor | Codex (OpenAI Codex Desktop), independent of the builder |
| Audited SHA | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` (branch `claude/TASK-012R-utc-temporal-invariants`) |
| Date | 2026-09-28 (report file written 2026-09-28 00:48 local) |
| Verdict | **TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES**; F12A-01 CLOSED; P0–P3 0; **TASK_012_PHASE_1A_SLICE_ACCEPTED** at `879bf56` |
| Source file | `%USERPROFILE%\.codex\visualizations\2026\09\27\01a0e4e7-39b8-73e2-a57d-c5e5b202fd92\TASK-012RA\TASK-012RA-audit.md` (evidence beside it) |
| Source SHA-256 | `e336e1b5330089edf436e243c7c5dae163bf865ec95a94f6faa48ee86bcb872d` |
| Codex session | thread `01a0e4e7-39b8-73e2-a57d-c5e5b202fd92` (Codex Desktop) |
| Archived by | Claude Code (builder) at the start of TASK-013, 2026-09-28 |

Everything below the rule is the auditor's report **byte-for-byte as written**
(not rewritten, sanitised or reconstructed). Links inside it point at the
auditor's worktree and evidence directory on the founder's machine; they are
kept as written.

---

# TASK-012RA FINAL NARROW INDEPENDENT RE-AUDIT

## EXECUTIVE VERDICT

F12A-01 is CLOSED. Every required gate is ACCEPTED. No new P0/P1/P2/P3 findings. TASK-012 is accepted for continued Phase-1A development, subject to founder/ChatGPT adjudication; this is not production readiness.

## INDEPENDENCE

Independent auditor: YES. No repair implementation, source edits, commits, pushes, PRs or deployment. Exact detached worktree mounted read-only at /repo in test containers. Mutation changes existed only in process memory. New probes, logs and this report are outside the repository. Reviewed authority/governance, archived TASK-012A audit, TASK-012 and TASK-012R contracts, D-67, 04a sections 18–20, convergence dispositions and the exact repair diff. Earlier accepted architecture was not reopened.

## EXACT SHA

879bf56cd7bb497fd77d8140fc1443fe9d61c1fe

Initial shared checkout: exact SHA; clean status; expected branch claude/TASK-012R-utc-temporal-invariants. Audit worktree: C:/Users/ihorf/.codex/worktrees/task012ra-audit/homies; detached at the same SHA, clean after testing. Repair parent c4c8bfac7f59a0930d9403d1100f35dccf003ae6; accepted parent ed9cf1b49f70716bd214a3212b2e7497ca5078ec verified as ancestor. Evidence: final-integrity.json.

## ENVIRONMENT

Python 3.12.14; PostgreSQL 16.4; PostGIS 3.4.3. SQLAlchemy 2.0.52, psycopg 3.3.4, pytest 9.1.1, ruff 0.15.22, mypy 2.3.0. Disposable, audit-owned PostgreSQL container on an internal Docker network, no published port; separate synthetic databases for regressions, probes and mutations. Container identity and audit label verified before removal with its volumes; isolated network removed. Production was not accessed. Details: environment.json; commands: launch.ps1 and run.py.

## F12A-01

CLOSED: A freshness/DST, B UTC move-in date and C canonical event-cycle instant independently reproduced successfully on the repaired SHA. No canonical decision required.

## FRESHNESS / DST

UTC, Europe/Warsaw and Pacific/Kiritimati were deliberately selected after connection/at transaction begin. Original autumn case (2026-11-01T12:00Z vs 2026-10-11T12:00Z) is STALE, excluded from list and detail 404. Original spring case (2026-04-01T12:00Z vs 2026-03-11T12:30Z) is RECONFIRM_DUE and visible. Independent probes covered both DST directions in all three zones: 14×24h−1µs FRESH; 14×24h RECONFIRM_DUE; 21×24h−1µs RECONFIRM_DUE; 21×24h STALE. Evidence: probes.log, probes.xml, targeted.xml.

## SQL ELAPSED-TIME SEMANTICS

freshness.py:108–113 subtracts make_interval(0,0,0,0,0,0,delta.total_seconds()). Actual production helper executed against PostgreSQL: identical instant cutoffs, inclusion/exclusion and sweep outcomes across zones. Runtime checks of the cutoff covered both DST directions; restoring a day-bearing interval (Z01) admitted the autumn stale listing. This conclusion does not rest on connection UTC configuration.

## PYTHON UTC NORMALISATION

freshness.py:74–140 normalizes aware instants to UTC before age arithmetic and reconfirm_at/stale_at addition; pinned as_of is normalized as well. Equivalent UTC/+02 representations retain the same state, cutoff and event identity. Independent probes checked derived UTC instants and owner freshness serialization; confirmed_on also stayed the UTC date.

## PUBLIC VISIBILITY

Independent successful-response checks, in all three zones and without sweep:

| Path | Exactly 21×24h | 20d 23h 30m |
|---|---|---|
| List | 200; listing excluded | 200; listing included |
| Detail | 404 | 200 |
| Contact reveal | 404 | 200 |
| Conversation start | 404 | 201 |
| Viewing slots | 404 | 200 |
| Viewing request | 404 | 201 |
| Public media | 404 | 200 |

Stored status remained active. The positive viewing case used a real configured slot. These checks strengthen the committed test's non-404 assertion. Evidence: independent.py and probes.log.

## SWEEP CONSISTENCY

For active confirmed fixtures, request-time stale exclusion exactly matched sweep staling; RECONFIRM_DUE exactly matched first-cycle reminder eligibility. All four microsecond thresholds, both DST directions and all three zones passed. Previously emitted reminders correctly deduplicate rather than re-emitting. No sweep redesign or lock-order change in the diff.

## MOVE-IN UTC DATE

available_from=2026-09-28 returned FROM_DATE at 2026-09-27T20:25:21Z, and NOW at 2026-09-28T00:00:00Z, in list and detail under UTC/Warsaw/Kiritimati. Committed regressions also cover the last microsecond before UTC midnight. NULL remained UNKNOWN and was excluded by available_by. Evidence: independent and committed timezone tests.

## EVENT DEDUP

Confirmation 2026-09-11T12:00:00Z; committed sweep runs in UTC→Warsaw, Warsaw→UTC and Kiritimati→Warsaw each produced [[listing_id], []], with exactly one stored reminder. Actual keys and payloads were inspected and asserted. Canonical timestamp: 2026-09-11T12:00:00.000000Z. Payload contained only listing/property identifiers, canonical confirmation time and policy durations. Evidence: probes.log.

## DB CLOCK AUTHORITY

PostgreSQL db_now derives from statement_timestamp() and normalizes its representation. The real-clock timezone checks passed. With Python clocks forced to 2001, publication and confirmation still used the actual 2026 database instant. Existing SQLite/test-only and detached-object fallbacks are not a new PostgreSQL decision-clock source.

## CONNECTION UTC DEFENSE-IN-DEPTH

Application connection arguments start sessions in UTC; real SHOW TimeZone check passed. Deliberate post-connect/transaction zone changes in temporal probes still passed all business invariants.

## CONCURRENCY REGRESSION

The 11-test PostgreSQL freshness suite passed, including confirm-first vs sweep, sweep-first vs confirm, archive-first vs confirm, revoke-before decision, revoke-during reactivation and Space archive interaction. Production diff leaves locking and transition structure unchanged. This is a bounded regression gate, not a new broad concurrency audit.

## MIGRATION REGRESSION

No migration added or changed. Entire backend/alembic Git tree is e643f9f086dcdd3b930059ee3853148c9ce4ef83 at both repair parent and audited SHA; b8d0f2a4c6e8 is unchanged. Upgrade/backfill, row preservation, downgrade/re-upgrade, status constraint and unknown-status refusal regressions passed.

## PRIVACY / SECURITY

Exact-address, coordinate and contact sentinels stayed out of checked public responses, except authorized contact disclosure. Actual event payloads matched the exact permitted field set. Location/media privacy regressions passed. No new public or event data fields introduced by this repair.

## MUTATION REVIEW

All six mutations independently exercised in memory, with green baselines and behavioral assertion failures:

| Mutant | Observed kill |
|---|---|
| Z01 day-based SQL interval | Autumn exact-21-day listing still listed |
| Z02 Python age without UTC normalization | Autumn 14-day boundary FRESH instead of RECONFIRM_DUE |
| Z03 session-local move-in date | Kiritimati returned NOW instead of FROM_DATE |
| Z04 offset-dependent dedup key | Second sweep reminded the same cycle again |
| Z05 db_now left in session zone | Returned +7200-second offset instead of UTC |
| Z06 canonical instant retains offset | Warsaw→UTC emitted a second reminder |

6/6 killed; zero errors in counted runs. An initial Z03 instrumentation attempt re-executed module-level metric registration and failed before tests; excluded, corrected to replace only the function in memory, and rerun to a real assertion failure. F01–F16 were not independently rerun. Evidence: mutations.json, individual Z01–Z06 logs/XML, mutate_in_memory.py.

## TEST RESULTS

| Check actually run | Result |
|---|---|
| Targeted regression run | 161 passed, no skips/failures/errors |
| Included timezone/DST PG | 46 passed |
| Included freshness PG / unit | 11 / 36 passed |
| Included availability/search | 14 passed |
| Included location / location PG / media regressions | 23 / 10 / 16 passed |
| Included OpenAPI drift/contract | 5 passed |
| Independent probes, including original reproductions | 43 passed, no skips/failures/errors |
| Full SQLite | 780 passed, 291 skipped |
| Z01–Z06 mutations | 6/6 behavioral kills with green baselines |
| Ruff | Clean |
| Mypy | Clean, 86 source files; existing untyped-function notes |
| Full PostgreSQL suite | NOT RUN |
| CI | NOT RUN |

Two preliminary test launches were blocked by incomplete local runtime dependencies (pytest installation not finished, then missing Pillow); resolved before the counted runs. No setup failure is counted as a passed test or a mutation kill. Logs/XML and runner scripts retained beside this report.

## NEW FINDINGS

None. P0: 0; P1: 0; P2: 0; P3: 0. No new canonical violation or blocking correctness/security evidence. No additional canonical decision required.

## NONBLOCKING DEBT

Existing unbounded due-reminder scan; public-place N+1; owner-view query amplification; reminder delivery/scheduling infrastructure; deferred SEO/listing fields. CI and production readiness remain unassessed. Python 3.12 was available and used in this audit. Existing debt was not converted into a new blocker.

## FINAL VERDICTS

F12A-01 = CLOSED
FRESHNESS_TIMEZONE_INVARIANCE = ACCEPTED
PUBLIC_VISIBILITY = ACCEPTED
SWEEP_CONSISTENCY = ACCEPTED
MOVE_IN_UTC_DATE = ACCEPTED
EVENT_DEDUP = ACCEPTED
DB_CLOCK_AUTHORITY = ACCEPTED
CONCURRENCY_REGRESSION = ACCEPTED
MIGRATION_REGRESSION = ACCEPTED
PRIVACY_SECURITY = ACCEPTED

TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES

## TASK-012 FINAL ACCEPTANCE

TASK_012_PHASE_1A_SLICE_ACCEPTED

SHA:
879bf56cd7bb497fd77d8140fc1443fe9d61c1fe

Accepts the TASK-012 Phase-1A slice: Listing freshness, availability semantics, marketplace quality/completeness, centralized public visibility, reconfirmation/stale lifecycle, related automation/event seams and UTC temporal invariants. Prior accepted areas are carried forward from TASK-012A; this was a narrow temporal repair audit. Not production readiness.

## PRODUCTION READINESS

PRODUCTION READINESS:
NOT ASSESSED / NOT READY

## DEPLOYMENT

DEPLOYMENT:
NOT DEPLOYED

## CHATGPT HANDOFF

CHATGPT HANDOFF

Project: Homies

Task:
TASK-012RA — Narrow Independent Re-audit of TASK-012R

Audited SHA:
879bf56cd7bb497fd77d8140fc1443fe9d61c1fe

Independent auditor:
YES

F12A-01:
CLOSED

Freshness timezone invariance:
ACCEPTED

Public visibility:
ACCEPTED

Sweep consistency:
ACCEPTED

Move-in UTC date:
ACCEPTED

Event dedup:
ACCEPTED

DB clock authority:
ACCEPTED

Concurrency regression:
ACCEPTED

Migration regression:
ACCEPTED

Privacy/security:
ACCEPTED

TASK-012R:
TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES

TASK-012:
ACCEPTED

P0: 0
P1: 0
P2: 0
P3: 0

New findings:
None.

Tests actually run:
Python 3.12.14; targeted 161 passed (including 46 timezone PG and 5 OpenAPI); independent probes 43 passed; full SQLite 780 passed / 291 skipped; Z01–Z06 6/6 behavioral kills with green baselines; ruff clean; mypy clean, 86 files. Full PG, F01–F16 rerun and CI not run. Setup/instrumentation errors excluded from passing evidence.

Known debt:
Unbounded due-reminder scan; public-place N+1; owner-view query amplification; reminder delivery/scheduling; deferred SEO/listing fields; CI/production validation outstanding.

Production readiness:
NOT ASSESSED / NOT READY

Deployment:
NOT DEPLOYED

REQUEST TO CHATGPT:
Adjudicate TASK-012RA.

If TASK-012 is accepted, formally establish
879bf56cd7bb497fd77d8140fc1443fe9d61c1fe
as the accepted TASK-012 Phase-1A slice and proceed to TASK-013
Search, Map & Marketplace Discovery.
