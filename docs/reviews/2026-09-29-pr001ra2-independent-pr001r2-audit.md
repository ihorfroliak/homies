# PR-001RA2 — Final Narrow Re-audit of PR-001R2 (Homies)

Independent read-only auditor: Claude Code, fresh session. This session did not build PR-001, PR-001R or PR-001R2.
Nothing was fixed, committed, pushed, merged or deployed.
Date: 2026-09-29 (19:45–20:20Z).

## 0. Exact SHA and independence

| Check | Result |
|---|---|
| Audited HEAD | `5cad442f07264ab25b3024c96fc691ad9c7a75fa`. Fresh detached worktree `homies-audit-evidence/PR-001RA2/wt`; `git status --short` is empty |
| Branch | `origin/claude/PR-001R2-readiness-repair` = `5cad442` (ls-remote) |
| Ancestors | `70be78b` (parent) ✔, `4416e2b` ✔, `879bf56` ✔ |
| Commits over PR-001R | **1** |
| Archived PR-001RA report | `docs/reviews/2026-09-29-pr001ra-independent-pr001r-audit.md`. sha256 `aac50ec0…` is byte-identical to the auditor's original `PR-001RA-FINAL-REPORT.md` |
| Runtime code touched | Only `backend/app/core/health.py`. An AST comparison with docstrings and comments stripped shows exactly one statement added, `PROBE_DRIVER_CLEANUP_S = 10.0`. The probe logic is identical to `70be78b` |
| Not touched | `Dockerfile`, `constraints.txt`, `pyproject.toml`, `ops/`, `composition.py`, `ratelimit.py`, `db.py` |

The diff scope matches the expectation:
- readiness comments, constant, test and docs;
- `scripts/ci/audit_canary.py` and its fixtures and tests;
- the `ci.yml` canary step;
- the archived PR-001RA report;
- README cleanup;
- DEVLOG and CONVERGENCE entries.

There is no domain or product change.

## 1. Environment (actual)

| Item | Value |
|---|---|
| Host | Windows 11 with Docker Desktop 29.2.1. All execution ran in Linux containers |
| Source | LF exact-SHA copy made with `git -c core.autocrlf=false archive 5cad442` (362 files). The Windows worktree differs only by CRLF |
| Images | `cra2-test:5cad442` sha256:`b7e1ecf5…` (`ops/test/Dockerfile.py312`) and `cra2-prod:5cad442` sha256:`af4600dd…` (`backend/Dockerfile`, `ENV=production`) |
| Python | 3.12.14 |
| Key packages | psycopg 3.3.6, pip-audit 2.9.0. Installed set == pinned set, 70/70 |
| Database | PostgreSQL 16.4 / PostGIS 3.4.3 (`postgis/postgis:16-3.4`). Two private servers, one for suites and one for probes, so role toggles cannot collide |
| Client tools | pg_dump / pg_restore 16.15 |
| Clock | `CLOCK_MONOTONIC` (monotonic, not adjustable, 1 ns resolution) |
| CI | GitHub Actions run `36547486045` (push `5cad442`) concluded **success**, all 5 jobs. The canary step "Dependency audit inspects the pins it is given (canary)" succeeded. Logs return 403, so this is **metadata only**. The auditor did not re-run CI |

## 2. Required results

```text
RA1_CONTRACT             = CLOSED
RA1_FREEZE_AFTER_CONNECT = CLOSED
M12                      = KILLED
READINESS_REGRESSION     = ACCEPTED
RA3_DISPOSITION          = CORRECTLY_DEFERRED
RA2_CANARY               = CLOSED
CANARY_MUTATION          = KILLED
CI_DEPENDENCY_AUDIT      = ACCEPTED
README_TRUTH             = ACCEPTED
INFRA_REGRESSION         = ACCEPTED
```

## 3. RA-1 — readiness contract: CLOSED

The claim is now truthful in all four places.

- **Code** (`health.py:66-93, 138-143, 163-166`):
  - `PROBE_DEADLINE_S` is labelled the "DEPENDENCY DECISION BUDGET … not the time the HTTP response takes".
  - Completion is described as the decision plus driver clean-up, with measured cases for before-handshake, after-connect (7–13 s) and DNS (3.8–4.0 s / ~10 s, OS resolver).
  - The comment says: "There is no universal end-to-end wall-clock guarantee, and none is claimed". It also names RA-3.
  - The misleading old comment ("does not wait for a frozen server") was removed.
- **Production readiness** (`PRODUCTION-READINESS.md` row 6):
  - The row is downgraded from READY to **PARTIAL**.
  - It states the decision budget of 3 s, the measured envelope, "Always 503", and the RA-3 gap.
  - §6b records the repair.
  - The PR-001R `docker stop` line is annotated with the PR-001RA 3.8–4.0 s figure.
- **Runbook** (`INCIDENT-RUNBOOK.md:10-13`): "a hung query can hold a probe for up to ~13 s … probes queue behind hung business requests (PR-003 debt) — set orchestrator probe timeouts accordingly."
- **Tests:** the new test bounds completion at decision + clean-up + slack, and does not require completion under 3 s.

Repository-wide search (`end to end|wall-clock|within 3|bounded|PROBE_DEADLINE|readyz`, excluding `docs/reviews` and `docs/tasks`):
- No remaining statement claims that `/readyz` completes end-to-end within 3 s.
- Historical entries are dated history and remain true: CONVERGENCE F11 row "under a wall-clock deadline", and DEVLOG 2026-09-28 "дедлайн 3 с".

## 4. Freeze-after-connect on real PostgreSQL: CLOSED

The sequence was: connect succeeds → `SELECT 1` in flight → server and cancel channel stop making progress → decision budget expires → fail closed → driver clean-up → 503.

**A. Candidate regression test** (`test_readiness_faults_pg.py::test_a_freeze_after_the_connection_is_established_is_a_finite_503`):
- Setup: real PG16/PostGIS behind the test's own protocol-triggered proxy. It freezes on the first client bytes after `ReadyForQuery`, and the cancel connection is frozen too.
- Guards: the `app_pool_untouched` fixture makes any use of the application engine fail.
- Asserts: freeze happened mid-query; finished; 503 with `TimeoutError`; `elapsed >= 3.0`; `elapsed < 16.0`; no DSN, user or port in the body.
- Result: 3 runs gave **13029 / 13012 / 13012 ms**, 20/20 passed each time.

**B. Auditor HTTP probe:**
- Setup: production image, real uvicorn, restricted `homies_app` role, `ENV=production`. The auditor's own proxy (`freeze_on_query`) sits in front of real PG16.
- The application pool was warmed first (5 idle).
- Three runs returned `/readyz` **503 in 13.023 / 13.020 / 13.028 s** (`latency_ms` ≈ 13005, `TimeoutError`).
- `/healthz` returned 200 in 15–17 ms during the freeze.
- The application pool was still 5 idle after every probe (`pg_stat_activity`). No readiness connection lingered.
- Recovery returned 200 (2×).
- There were 0 secret, DSN or password matches in the body or the application logs.
- The logs show psycopg's own `query cancellation failed: cancellation timeout expired`, then `query not terminated after cancellation: closing connection` 5.0 s later.

**C. Timing decomposition:**
- Method: real `health.check_database` of the exact SHA. The only instrumentation was a timing wrapper around psycopg `AsyncConnection._try_cancel`.
- psycopg 3.3.6 source: `wait()` runs `_try_cancel(timeout=5.0)`, then drains with `wait_async(timeout=5.0)`.

| Measurement | Value |
|---|---|
| Decision budget (declared) | 3.0 s |
| Decision observed (cancel begins) | 3.001–3.002 s |
| Driver clean-up: cancel attempt | 5.002–5.003 s |
| Driver clean-up: drain / close | 5.003–5.004 s |
| Driver clean-up total | **10.004–10.006 s** (declared `PROBE_DRIVER_CLEANUP_S` 10.0) |
| Total wall-clock | **13.005–13.008 s** (documented "~7–13 s", 13.05 s with cancel frozen; test bound 16 s) |

The observed behaviour matches the documented envelope. A real `docker pause` race after connect (7.25–7.28 s in PR-001RA) was not repeated, because the code path is unchanged (AST).

## 5. m12 — deadline mutation: KILLED

Each mutation was applied to a fresh `git archive` copy (`mut/<name>`). Before mutating, the copy's hash was checked equal to the git blob (`058f6b80…`). `wt/` and `src2/` were never modified, and their blob hashes were re-verified at the end.

| Mutant | Change | Result |
|---|---|---|
| Baseline | none | 20 passed (×3) |
| **m12** | `await asyncio.wait_for(probe(), PROBE_DEADLINE_S)` → `await probe()` | **KILLED.** The new test fails with the message "/readyz did not answer within 21 s of a freeze after connect — the decision deadline is missing". 1 failed / 19 passed |
| m12b (auditor extra) | `PROBE_DEADLINE_S = 3.0` → `60.0` | **Survived.** 503 in 70019 ms; test passed. See NOTE RA2-N1 |

## 6. Ordinary readiness regression: ACCEPTED

Production image, direct to real PG16/PostGIS, application pool warm (10 idle):

| Case | Result |
|---|---|
| Healthy | `/readyz` 200 in 14–43 ms. `/healthz` 200 |
| `docker pause` (frozen before handshake, warm pool) | 503 `ConnectionTimeout` in 2.006–2.025 s. 20 concurrent: max 2.29 s. `/healthz` 200 in 14 ms. The business request still hangs (PR-003 debt, not reopened) |
| Recovery | 200. Pool 10 idle, unchanged |
| `docker stop` | 503 `TimeoutError` in 3.857–3.997 s (Docker DNS, documented). `/healthz` 200 |
| Recovery after restart | `/readyz` 200. `/v1/classifieds` 200 |
| Candidate tests | stopped 1–3 ms, frozen cold 2002 ms, warm pool ×6 max 2021 ms, recovered 200, pool-exhaustion test and `test_obs01_*`: all pass |
| Privacy | 0 DSN or password leaks |

The dedicated readiness path still does not use the application pool:
- fixture `app_pool_untouched`;
- `pg_stat_activity` before and after;
- probe logic unchanged (AST).

## 7. RA-3: CORRECTLY_DEFERRED

- The code states that health endpoints share the application thread pool and that this is "PR-003 debt" (`health.py:91-92`).
- The docs agree:
  - PRODUCTION-READINESS row 6 "Gap (PR-003)", §6b "not fixed here";
  - RUNBOOK;
  - CONVERGENCE "DEFERRED — PR-003 debt";
  - DEVLOG "Не зроблено навмисно".
- No document claims RA-3 is fixed.
- Regression is impossible from this diff: `composition.py`, `ratelimit.py`, `db.py` and the endpoint sync/async shape are unchanged, and `health.py` adds only one constant.

## 8. RA-2 — dependency canary: CLOSED

Source: `backend/scripts/ci/audit_canary.py`.
- It runs `pip_audit … -f json` and parses **stdout only**. stderr is printed, never parsed.
- It succeeds only if a `dependencies[]` entry has `name` (case-insensitive) == `urllib3`, `version == "1.26.4"`, and a vuln id matching `^(PYSEC|GHSA|CVE)-`.

**Matrix.** The real CI entry point was used. Synthetic cases replay recorded or crafted output through a `python -m pip_audit` stub. All 14 matched expectation (`logs/ra2-canary-matrix.txt`):

| Case | Exit |
|---|---|
| Recorded vulnerable JSON / GHSA-only / CVE-only | 0 |
| Network failure: empty stdout plus traceback on stderr | 1 |
| Network-failure traceback on stdout | 1 |
| Vulnerable JSON only on stderr | 1 |
| Truncated JSON | 1 |
| Plain text naming `urllib3 1.26.4` with ids | 1 |
| Correct package and version, `vulns: []` | 1 |
| Wrong version 1.26.5 (vulnerable) | 1 |
| Unrelated vulnerable `requests` with urllib3 skipped | 1 |
| Non-advisory or lowercase ids | 1 |
| Empty output with rc 0 or rc 1 | 1 |
| Bad usage | 2 |

**Real pip-audit runs:**
- `--network none` gives **exit 1**. stdout is empty; stderr mentions urllib3 14 times (the old grep's false success).
- With network, `urllib3==1.26.4` gives exit 0 (9 PYSEC).
- With network, `1.26.5`, `requests==2.19.0` and `urllib3==2.5.0` each give exit 1, although pip-audit found vulnerabilities in every one.
- The recorded fixture's advisory ids are identical to the live run's (9/9).

## 9. Canary mutation: KILLED

The baseline `test_ci_contract.py` gave 18 passed. Each mutant used a fresh archive copy with its hash verified:

| Mutant | Result |
|---|---|
| **c1** — package-name occurrence means success (the original weak semantics) | **KILLED**, 4 failed (`test_an_advisory_lookup_failure_is_a_canary_failure`, 3 parametrised cases) |
| c2 — `urllib3` in stderr counts as detection | KILLED (`…fails_closed_when_pip_audit_fails`: `assert 0 == 1`) |
| c3 — non-zero pip-audit exit counts as detection | KILLED (same test) |
| c4 — any advisory id accepted | KILLED (report3) |
| c5 — version not checked | KILLED (report1) |

## 10. CI dependency audit: ACCEPTED

- The main step `python -m pip_audit -r constraints.txt --no-deps --disable-pip --progress-spinner off` is unchanged. It is clean with network (exit 0) and fails closed offline (exit 1).
- The canary is a separate, later step that is supplementary. There is no `continue-on-error` and no `if:` anywhere in `ci.yml`. A canary lookup failure makes the job red; it cannot make it green.
- The pins are unchanged (`constraints.txt` is not in the diff), and installed == pinned (70/70).
- There is no resolver-to-latest regression (`--no-deps --disable-pip` kept).
- The contract test pins the new command and forbids the grep.

## 11. README truth: ACCEPTED

- "Phase 0 — Walking Skeleton" is replaced by "Phase 1A … in development; not deployed".
- "ML-serving separately deployed" is replaced by "One deployable application process; background workers (notifications, listing freshness) run in-process. No ML serving exists". This is confirmed by the `composition.py:95-110` in-process workers.
- The layout now lists only tracked top-level dirs (`backend/ frontend/ ops/ docs/`); `apps/`, `data/` and `infra/` are gone.
- No new false architecture claim was found.

## 12. Infra regression: ACCEPTED

All gates ran on the exact SHA, Python 3.12.14, in containers:

| Gate | Result |
|---|---|
| installed == pinned | 70/70, diff exit 0 |
| Alembic heads | 1. Migrate empty → head on PG16.4 / PostGIS 3.4.3: exit 0 |
| ruff 0.15.22 | All checks passed |
| mypy | exit 0 |
| OpenAPI drift (`test_tst01_openapi_contract.py`) | 5 passed |
| promtool `check config` / `check rules` (13 rules) / `test rules` | SUCCESS |
| amtool | SUCCESS |
| CI contract tests | 18 passed |
| Readiness targeted tests | 20 passed ×3 |
| Canary tests / matrix | see §8–9 |
| **Full SQLite suite** | **833 passed / 299 skipped, exit 0** (PR-001RA: 824 / 298) |
| **Full PostgreSQL / PostGIS suite** | CI-equivalent: `coverage run`, `HOMIES_REQUIRE_RESTORE_DRILL=1`. **1131 passed / 1 skipped** (Stripe live, not requested), exit 0. Branch coverage **91.5%** (PR-001RA: 1121 / 1) |

The previously CLOSED items F1–F10 (F2 main logic), N1, N5 and N7 were not re-audited. Their code is untouched by this diff, and their tests are inside the green full suites.

## 13. Findings

No new P0, P1, P2 or P3.

### RA2-N1 — NOTE — the decision-budget value is not pinned by any test

| Field | Detail |
|---|---|
| File | `backend/tests/test_readiness_faults_pg.py:36` (`AFTER_CONNECT_BOUND_S = health.PROBE_DEADLINE_S + health.PROBE_DRIVER_CLEANUP_S + 3.0`) and `backend/app/core/health.py:90` |
| Reproduction | Change `PROBE_DEADLINE_S = 3.0` to `60.0` (mutant m12b). Run `tests/test_readiness_faults_pg.py tests/test_obs01_health_readiness.py` on PG |
| Expected | Some test fails, because the documented contract is a 3 s decision and a ~13 s worst case |
| Actual | 20 passed. `/readyz` answered 503 in **70.0 s**. Every bound derives from the constant under test, and the other fault cases are decided by the 2 s `connect_timeout` |
| Impact | Low. Removing the deadline is caught (m12 killed). Only an explicit, visible edit to a documented constant would pass, and orchestrator probe timeouts would still fail closed |
| Bounded repair (optional, e.g. with PR-003) | Assert the documented numbers absolutely: `PROBE_DEADLINE_S == 3.0`, or an absolute upper bound of about 16 s in the after-connect test |
| Canonical decision required | NO |

### Carried forward, unchanged, nonblocking

- N-A: failed-probe `CLOSE_WAIT` until GC.
- N-C: loopback set.
- N-D: `"1"`-only drill flag.
- N-E: F8 reproducibility residue.
- N-F: CI evidence is metadata only. It is still true: run `36547486045` logs return 403.
- N-B is resolved by this commit (§11).

### Carried as assigned debt, not counted

RA-3 (P3) is assigned to PR-003 and has not been claimed as fixed.

## 14. Known debt preserved (not reopened)

The following remain production-readiness debt:
- RA-3 / business-request DB hang → PR-003;
- no worker heartbeat;
- public `/metrics`;
- no staging;
- no alert destination;
- no PITR;
- base-image digest / reproducibility residue;
- root container;
- uvicorn / logging residue;
- PG client minor pinning;
- build tooling reproducibility;
- failed-probe CLOSE_WAIT / GC.

PR-001R2 regressed none of them.

## 15. Verdict

```text
P0:   0
P1:   0
P2:   0
P3:   0   (RA-3 P3 remains assigned PR-003 debt; not counted, not claimed fixed)
NOTE: 6   (new RA2-N1; carried N-A, N-C, N-D, N-E, N-F)

PR_001_ACCEPTED_WITH_NONBLOCKING_NOTES
```

All acceptance conditions are met:
- RA-1 CLOSED;
- m12 KILLED;
- RA-2 CLOSED;
- canary mutation KILLED;
- no new P0, P1 or P2;
- no regression.

```text
PR_001_BASELINE_ACCEPTED

SHA:
5cad442f07264ab25b3024c96fc691ad9c7a75fa
```

This means the PR-001 infrastructure/runtime baseline is accepted. It does **not** mean Homies is production ready.

```text
PRODUCTION READINESS:
NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

## 16. Evidence

Everything is under `C:\Users\ihorf\Projects\homies-audit-evidence\PR-001RA2\`: `CHECKPOINT.md`, `logs/`, `probes/` and `mut/`.

| File | Contents |
|---|---|
| `logs/step0.txt` | SHA and ancestry |
| `logs/diff.txt` | full repair diff |
| `logs/gates.log` | CI-equivalent gates |
| `logs/gates-monitoring-openapi.txt` | promtool, amtool, OpenAPI drift |
| `logs/suites/suite-sqlite.log`, `suite-pg.log`, `coverage.log`, `pg-migrate.log` | full suites |
| `logs/ra1-http-freeze-after-connect.txt` | §4 B |
| `logs/ra1-decomposition.txt` | §4 C |
| `logs/ra1-readiness-tests-and-m12.txt` | §4 A, §5 |
| `logs/readiness-regression-http.txt` | §6 |
| `logs/health-ast-diff.txt` | AST comparison, integrity hashes |
| `logs/ra2-canary-matrix.txt`, `logs/ra2-main-audit-offline-and-fixture.txt` | §8, §10 |
| `logs/mut-apply.txt`, `logs/mut-canary.txt` | mutation hashes, canary mutants |
| `logs/gha-runs.json`, `logs/gha-jobs.json` | CI metadata |

---

```text
CHATGPT HANDOFF

Project:
Homies

Task:
PR-001RA2 — Final Narrow Re-audit of PR-001R2

Audited SHA:
5cad442f07264ab25b3024c96fc691ad9c7a75fa

Parent:
70be78bfd746b63a1444e1dd7eb82023226215d3

Independent auditor session:
YES

RA-1 contract:
CLOSED — 3 s is documented as the dependency decision budget; completion = decision + finite driver/DNS clean-up; no universal end-to-end 3 s claim remains (code, PRODUCTION-READINESS row 6 → PARTIAL, runbook, tests)

Freeze-after-connect:
CLOSED — real PG16/PostGIS, server + cancel frozen mid-query: /readyz 503 TimeoutError in 13.01–13.03 s (decision 3.00 s + cancel 5.00 s + drain 5.00 s), app pool untouched, /healthz 200, no leaks, recovery 200; matches documented ~7–13 s envelope

m12:
KILLED — removing wait_for makes the new PG regression fail ("did not answer within 21 s … decision deadline is missing"); NOTE RA2-N1: raising the budget value (3→60 s) is not detected

RA-2 canary:
CLOSED — structured JSON proof only (urllib3==1.26.4 + PYSEC/GHSA/CVE on stdout); offline, malformed, no-vuln, wrong-version, unrelated-package, stderr-only and text cases all exit 1 (14/14 + real offline/online runs)

Canary mutation:
KILLED — name-occurrence (4 failures), stderr-name, nonzero-exit, any-id, no-version: all killed

RA-3:
PR-003 DEBT — NOT CLAIMED FIXED

Regression:
ACCEPTED — ruff, mypy, heads=1, OpenAPI drift, promtool/amtool, CI contract, pinned==installed; SQLite 833 passed/299 skipped; PG 1131 passed/1 skipped, coverage 91.5%; health.py runtime change = one constant

Environment:
Windows 11 host, Docker 29.2.1 Linux containers; Python 3.12.14; psycopg 3.3.6; pip-audit 2.9.0; PostgreSQL 16.4 / PostGIS 3.4.3; pg_dump 16.15; CLOCK_MONOTONIC; exact-SHA LF archive; images cra2-test b7e1ecf5…, cra2-prod af4600dd…; GHA run 36547486045 success (metadata only, logs 403; not re-run)

Tests independently run:
gates; full SQLite + full PostgreSQL/PostGIS suites (CI-equivalent, restore drill required); readiness tests ×3; production-image HTTP freeze-after-connect ×3, pause/stop/recovery matrix; timing decomposition; canary matrix (14 stub + 5 real); mutations m12, m12b, c1–c5; promtool/amtool; OpenAPI drift

P0:
0

P1:
0

P2:
0

P3:
0

NOTE:
6

Overall verdict:
PR_001_ACCEPTED_WITH_NONBLOCKING_NOTES

PR-001 baseline accepted:
YES

Accepted infra SHA:
5cad442f07264ab25b3024c96fc691ad9c7a75fa

Production:
NOT READY

Deployment:
NOT DEPLOYED

May participate in CONV-001:
YES

REQUEST TO CHATGPT:
Adjudicate PR-001RA2. If accepted, synchronize accepted product SHA
7ffb4f51dd315363362df1a5f8fc5c19a57767dc
with accepted infra SHA
5cad442f07264ab25b3024c96fc691ad9c7a75fa
and authorize the next controlled convergence step.
```
