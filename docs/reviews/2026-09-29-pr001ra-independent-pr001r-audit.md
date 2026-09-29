# PR-001RA — Narrow independent re-audit of PR-001R

- **Audited SHA:** `70be78bfd746b63a1444e1dd7eb82023226215d3` (branch `claude/PR-001R-runtime-ci-repair`, identical on `origin`)
- **Repair parent:** `4416e2b14b007ba50aab41cad8e23deea32c4678` — ancestor ✔ (`merge-base --is-ancestor` exit 0)
- **Accepted product ancestor:** `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` — ancestor ✔ (exit 0)
- **Auditor:** independent Claude session (not the PR-001 / PR-001R builder). No source modified, no commit, push, merge, rebase or deploy. No production access, no paid provider, no production data.
- **Worktree:** fresh detached `homies-audit-evidence/PR-001RA/wt`. At start HEAD was exact and `git status --short` was empty (`logs/step0.txt`).
- **Source used for execution:** `PR-001RA/src`, made by `git -c core.autocrlf=false archive 70be78b`. It holds 358 files, byte-identical to the git blobs (LF endings). The Windows checkout uses CRLF and was not used for images.
- **Mutation copies:** `PR-001RA/mut/*`, all outside the frozen worktree.
- **Infrastructure:** disposable Docker, all objects prefixed `cra-`: network `cra-net`, runtime database `cra-db`, suite database `cra-dbs`, mutation database `cra-dbm`. None of it was shared with the concurrently running TASK-014A session or with `homies-postgres`.
- **Evidence:** `PR-001RA/logs/`, probes `PR-001RA/probes/`, checkpoint `PR-001RA/CHECKPOINT.md`.
- **Source material read:** the full archived PR-001A report, the verdict record, the PR-001R diff, the production and CI documentation, and the relevant tests.
  - The archive is byte-exact to the original PR-001A report: sha256 `2cd3dfe5…193d061` for both.

## Evidence environment

| Item | Value |
|---|---|
| SOURCE_SHA | `70be78bfd746b63a1444e1dd7eb82023226215d3` |
| AUDIT_HARNESS | auditor probes in `PR-001RA/probes/` (not in repo; no harness SHA) |
| WORKFLOW_SHA | `.github/workflows/ci.yml` at the source SHA |
| PYTHON_VERSION | 3.12.14 in both images: production `cra-prod:70be78b` (`sha256:fef7982ca50c…`) and test `cra-test:70be78b` (`sha256:e2e9b8e8b852…`). Base `python:3.12-slim@sha256:f77ac9e44ae9…` |
| PG_VERSION / POSTGIS | PostgreSQL 16.4 / PostGIS 3.4.3. Image `postgis/postgis:16-3.4@sha256:44126d87…`, the same digest as the CI service |
| PG_DUMP / PG_RESTORE | 16.15 / 16.15 (test image) |
| CONSTRAINTS_SHA256 | constraints.txt blob at source SHA (LF), unchanged since PR-001 |
| INSTALLED_PACKAGE_SET | test image: 70/70 pinned, `diff` empty (the CI step verbatim). Production image: 37 runtime distributions, all at their pins, no dev tools |
| CLOCK | app↔DB skew **+0.1 ms** (5 samples, 1 ms RTT). Container monotonic equals wall clock over 10 s (Δ 0.0000 s). All timings use `time.monotonic()` |
| CI | GitHub Actions run **36436413217** (push, `claude/PR-001R-runtime-ci-repair`, head `70be78bfd746`): 5/5 jobs and every step `success`, including the pinned audit, the canary, the F8 and F3 image asserts and Test. **Job logs are HTTP 403, so this is metadata only.** Test counts, skip lists and audit output inside CI are **not visible**. I do not report "CI PASSED" on log evidence |
| SKIPS | SQLite run: 298 skips, all "TEST_DATABASE_URL not set / needs PostgreSQL / needs pg_dump" plus 1 Stripe-live. PostgreSQL run: **1 skip — Stripe Test Mode not requested** |

**Supported runtime evidence:** stable Linux containers, Python 3.12.14, real PG 16 / PostGIS 3.4, exact SHA, stable clocks. No host Python 3.14 evidence was used for any verdict.

## Tests actually run

| Gate | Result |
|---|---|
| CI-equivalent gates (`logs/suites/gates.log`) | Python 3.12 assertion ✔; installed == pinned 70/70 ✔; `alembic heads` = 1 ✔; ruff 0.15.22 "All checks passed" ✔; mypy "no issues in 88 files" ✔ |
| OpenAPI drift (`export_openapi --check`) | "up to date" ✔ |
| `pip-audit -r constraints.txt --no-deps --disable-pip` | "No known vulnerabilities found", exit 0 |
| Canary `urllib3==1.26.4` | 9 PYSEC advisories, exit 1 (a real detection) |
| Full SQLite suite | **824 passed, 298 skipped**, exit 0 (518 s) |
| Migrate base→head + PG16/PostGIS assertions | exit 0 |
| Full PostgreSQL/PostGIS suite, CI-equivalent (coverage, `HOMIES_REQUIRE_RESTORE_DRILL=1`, dedicated DB server) | **1121 passed, 1 skipped (Stripe live)**, exit 0 (1636 s). Branch coverage **91.5 %** (threshold 80) |
| promtool check config / rules (13) / test rules; amtool (v2.55.1 / v0.27.0) | all SUCCESS |
| Auditor promtool semantics (`probes/promtool/f6_extra.test.yml`) | SUCCESS |
| Production-image startup matrix, 9 cases + F5 cases | see F3–F5 |
| Request-id direct-ASGI matrix (24 header cases + 3 unhandled paths) | 0 failures |
| Real-uvicorn request-id matrix (13 raw cases) + 500 mixed concurrent requests + log correlation | 0 mismatches |
| Real 429 and database-down 500 on the production app | see N7, F1 |
| F11 fault matrix | see F11. Methods: real `docker pause` / `stop`, the auditor's freeze proxy, a DNS fault, a business-traffic interaction |
| F7 prerequisite-failure matrix (7 cases) | see F7 |
| Mutation matrix, 15 mutations, each with a green baseline | 15/15 killed; 1 killed only by an auditor probe (m12) |

## Closure table

```text
F1_REQUEST_ID_500        = CLOSED
F2_DEPENDENCY_AUDIT      = CLOSED        (canary self-check residual: RA-2, P3)
F3_ENV_FAIL_CLOSED       = CLOSED
F4_DEV_DB_GUARD          = CLOSED
F5_ALEMBIC_LOGGING       = CLOSED
F6_BACKLOG_MONITORING    = CLOSED
F7_RESTORE_DRILLS        = CLOSED        (CI-side skip list not readable: logs 403)
F8_PYTHON_RUNTIME_GUARD  = CLOSED
F8_REPRODUCIBILITY_RESIDUE = PRESENT
F9_CANONICAL_HISTORY     = CLOSED
F10_CI_CONCURRENCY       = CLOSED        (static YAML inspection only for main)
F11_BOUNDED_READINESS    = PARTIAL       (RA-1, P2)
N1_REQUEST_ID_FULLMATCH  = CLOSED
N5_README_STACK          = CLOSED        (residual stale README lines: NOTE)
N7_REAL_429              = CLOSED
DOMAIN_REGRESSION        = ACCEPTED
SUPPORTED_RUNTIME_EVIDENCE = ACCEPTED
```

## Per-item verification

**F1 — CLOSED.**
- **Direct ASGI:** unhandled sync `RuntimeError`, unhandled async `ValueError`, and an invalid caller id each gave a 500 with body `{"detail":"Internal Server Error"}` and exactly one `X-Request-ID`. Nothing propagated to the server. Exactly **one** `homies.http` record with `exc_info` was written under the same id, and the contextvar was `None` afterwards.
- **Real uvicorn, production image, `ENV=production`, JSON logs** (`logs/f1-http-*`): 500 concurrent requests, mixed 200 / handled 409 / unhandled 500, caller-supplied and generated ids.
  - 0 header mismatches.
  - 200/200 unhandled requests had exactly one exception record under their own id, all from `homies.http`.
  - 0 cross-request leaks over 600 probe log lines.
  - 0 plain `Exception in ASGI application` tracebacks. The exception text and `SECRET-DETAIL` stayed in the server-side JSON only, never in the response.
- **Real unhandled path in the production app** (database stopped, `GET /v1/classifieds`): 500 with the caller id `dbdown-req-000001`, and 500 with a generated 32-hex id. One `homies.http` record for each, with no password.
- **Metrics:** 5xx is still counted (`http_metrics` counts on exception).
- **Scope check:** the app has no BackgroundTasks or streaming responses, so there is no post-start exception path.

**F2 — CLOSED.**
- CI installs `-c constraints.txt`. The new step proves installed == pinned; I reproduced it with an empty diff over 70 packages.
- The audit reads `constraints.txt` with `--no-deps --disable-pip`, which inspects each pin as written and resolves nothing. No `--ignore-vuln` exclusions are present.
- The production image's 37 runtime distributions all equal their pins, and they are a subset of the audited set.
- The canary is flagged for real (9 advisories).
- Mutation m03 (`pip_audit .`) is killed by `test_ci_contract`.
- Residual: RA-2.

**F3 — CLOSED.** The production image has `ENV=production` by default. Startup matrix (`logs/f3-startup-matrix.txt`), with every refusal naming the rule and never the value, and no password, DSN or secret in any log:

| Case | Outcome |
|---|---|
| no `ENV`, nothing set | exit 3; JWT, WEBHOOK and both DATABASE_URL rules named |
| dev URL spelled `127.0.0.1…?connect_timeout` | exit 3 |
| weak JWT | exit 3 |
| default JWT | exit 3 |
| owner role | exit 3 `LedgerPrivilegeError` (**B5 active**) |
| empty DB, no `ENV` | exit 3 `SchemaNotMigratedError`; DB still has **0 tables** (no self-migration) |
| `ENV=''` | strict |
| `ENV=staging` with dev credentials on a remote host | refused |
| explicit production with a restricted role | started |

- A developer shell (`unset ENV`) stays `local` and logs a WARNING. This is documented.
- The CI image step catches mutation m04 (Dockerfile `ENV` removed): exit 1.

**F4 — CLOSED.** 27 URL variants were checked (`logs/f4-urls.txt`), all per the documented bounded guarantee. None of the messages leaks a password.
- **Refused:** `localhost`, `127.0.0.1`, `[::1]`, `LOCALHOST`, query parameters, a trailing `?`, a %-encoded user or password, compose `db`, the CI URL, dev credentials on any host, the loopback dev endpoint with other credentials, sqlite, mysql, malformed input, an empty value.
- **Accepted:** synthetic non-development URLs.
- Mutation m05 (literal compare) is killed by 9 `test_sec02` cases. Residual: NOTE N-C.

**F5 — CLOSED.**
- `ENV=local` self-migrated an empty DB (24 upgrades). After migration the JSON handler survived, the root level stayed INFO, `homies.*`, `uvicorn.*` and `alembic` were not disabled, and logs continued ("notification worker started", access log).
- Startup failures stay visible (≈173-line tracebacks, exit 3).
- `%`-encoded passwords were never printed, whether through the app or CLI Alembic.
- CLI `alembic upgrade head` works with normal logging.
- Mutations m06 and m06b are killed.

**F6 — CLOSED.** The expression is `sum(max by (status)(…pending|failed)) > 100`, `for: 15m`.
- The candidate promtool tests pass.
- Auditor tests also pass:
  - split statuses across replicas: 60+41 fires exactly at 15 m, not at 14 m;
  - 3×40 real rows never fires;
  - an absent series never fires;
  - a stale series resolves;
  - a frozen high gauge from a dead worker dominates `max` (documented heartbeat debt).
- The rule comment, runbook and readiness matrix no longer claim worker-death detection.
- Mutation m07 (plain `sum`) is killed ("180 notifications").

**F7 — CLOSED.** With `HOMIES_REQUIRE_RESTORE_DRILL=1`:

| Missing | Result |
|---|---|
| pg_dump + pg_restore | collection ERROR, exit 2 |
| only pg_restore | exit 2 |
| only pg_dump | exit 2 |
| `TEST_DATABASE_URL` | exit 2 |
| DB unreachable | 10 errors, exit 1 |

- Without the flag, a developer machine still skips with the reason shown.
- Both drills **executed** in my PostgreSQL run: only the Stripe skip was reported.
- CI has `-rs` and installs the PG client or fails.
- Mutation m08 is killed. Residual: NOTE N-D.
- A local synthetic restore does **not** prove production backup readiness.

**F8 — CLOSED.**
- The image is 3.12.14. The CI image-job assert exits 1 on `python:3.14-slim` and `python:3.13-slim` and 0 on `python:3.12.13-slim`, so patch upgrades are allowed.
- The CI backend job asserts `(3, 12)`.
- Dependabot ignores `python` semver-major and semver-minor updates.
- The remote branch `dependabot/docker/backend/python-3.14-slim` still exists unmerged. It would now fail the image job.
- Mutation m09 is killed.
- **F8_REPRODUCIBILITY_RESIDUE = PRESENT:** base images by tag, unconstrained build-isolation `pip`/`setuptools`, unpinned `postgresql-client-16` minor, no SBOM, image runs as root with `build/` and `*.egg-info` leftovers.

**F9 — CLOSED.**
- Since `879bf56`, the only modified canonical or review file is `IMPLEMENTATION-CONVERGENCE.md`.
- All 17 `879bf56` headings are present in their original order. The only additions are the two PR-001 sections placed above them, and the only removals are PR-001's Redis/Meilisearch/NATS rows.
- The archived PR-001A report is byte-exact and marked `-text` in `.gitattributes`.
- The PR-001 separation ("NOT accepted", "pending PR-001RA") is recorded.

**F10 — CLOSED (static YAML inspection only for `main`).** The concurrency block is `group: ci-${{ ref==main && sha || ref }}`, `cancel-in-progress: ${{ ref != main }}`.

| Branch type | Behaviour |
|---|---|
| `main` | a per-commit group, never cancelled |
| task branch | per-ref group, superseded runs cancel |
| PR merge refs and other branches | separate groups |

- Observed: two PR-001R branch runs (`e6059d9`, `70be78b`), both success, pushed 19 minutes apart.
- No `main` run exists under the new workflow, and I pushed nothing.
- Mutation m10 is killed.

**F11 — PARTIAL (RA-1).** See the matrix below. The original defect is closed: the warm-pool hang is gone and the pool is never touched. The declared ~3 s end-to-end bound does **not** hold.

**N1 — CLOSED.**
- Direct ASGI: the exact bounds 8 and 64 are kept. These are all replaced by a generated 32-hex id: 7, 65, trailing LF, trailing CRLF, embedded LF, CRLF injection, CR, NUL, TAB, DEL, ESC, VT, latin-1, UTF-8, space, `/`, `:`, quote, `%0a`, empty, leading space.
- Real parser: bare LF, CR, NUL, ESC and obs-fold are rejected with 400.
- Mutation m13 (`$`) is killed.

**N5 — CLOSED.**
- The README separates the runtime stack today from deferred items and says there is no Redis, Meilisearch or NATS.
- No runtime code, config, compose, Makefile, Dockerfile or CI references them, only comments.
- Residual: NOTE N-B.

**N7 — CLOSED.** A real limiter on the production app with `ENV=production`: `POST /v1/auth/login` returned requests 0–9 as 422 and requests 10–15 as **429** with `Retry-After: 8`, and the caller's `X-Request-ID` was echoed on every one. Mutation m14 (id middleware inside the limiter) is killed by the new real-429 test.

**DOMAIN_REGRESSION — ACCEPTED.**
- No file under `app/modules/**` changed.
- Test edits in h2/h4 swap `pytest.raises` for the same data invariants plus a 500 assertion.
- The full SQLite and PostgreSQL suites are green.

### F11 matrix (production image, private PostgreSQL, monotonic timings)

| Case | Result |
|---|---|
| Healthy | 200 (0.03–0.1 s) |
| DB stopped (`docker stop`) | 503 in **3.82–3.97 s**. Docker DNS takes 3.85 s to NXDOMAIN a stopped container; `wait_for` fires at 3.0 s, but `asyncio.run` then joins the default-executor `getaddrinfo` thread |
| Frozen (`docker pause`), cold | 503 in 2.01–2.06 s (`ConnectionTimeout`) |
| **Warm pool (5 idle `homies_app`), then `docker pause`** — the original reproduction | `/readyz` 503 in **2.01–2.06 s** ×9 sequential. 30/20/20/20 concurrent: max 2.52 s. A business request on the warm pool **still hangs** (PR-003 debt, expected). `/healthz` 200 in 0.03 s |
| 40–45 concurrent while frozen | max 4.06 s = probe ≤2.09 s + 2.05 s anyio thread-limiter queue |
| Repeated failures (≈200 probes) | pool untouched; threads return to baseline 7. Failed-probe sockets linger in CLOSE_WAIT until cyclic GC; `gc.collect()` frees all. Bounded (NOTE N-A) |
| Recovery | 200 in 0.03–0.06 s every time |
| Privacy | bodies carry the class name only. 0 occurrences of password/DSN in app logs |
| **Freeze after connect, query in flight** (auditor proxy; the cancel request answered) | 503 in **8.02–8.21 s** (×3 seq, ×10 concurrent) |
| **Same, cancel request also frozen** (a truly frozen server) | 503 in **13.05 s** ×3 = 3 s `wait_for` + psycopg 3.3.6 `AsyncConnection.wait` cancel (5 s) + drain (5 s) |
| **Same on real `docker pause`** (30-thread probe storm, pause mid-flight) | **7.25 s, 7.26 s, 7.27 s, 7.28 s** in 2 of 3 tries; cut short by the unpause after 6 s |
| Unreachable DNS resolver | **10.0 s** ×2 (glibc 5 s × 2) |
| Frozen DB + 60 looping business clients | `/readyz` **5.5–10.7 s** (probe 2.0 s, the rest thread-pool queueing). `/healthz` **6.6 s** (RA-3) |

## Findings

### RA-1 — P2 — F11 residual: the declared 3 s end-to-end readiness deadline is not end-to-end, and the deadline itself is untested

- **Location:**
  - `backend/app/core/health.py:64` ("the deadline holds whatever the server does"), `:119` (`asyncio.run`), `:137` (`asyncio.wait_for(probe(), PROBE_DEADLINE_S)`);
  - `docs/production/PRODUCTION-READINESS.md:21` (row 6 **READY**: "bounded end to end by a 3 s wall-clock deadline") and `:147` ("`docker stop`: 503 in ~2.3–2.8 s");
  - `backend/tests/test_readiness_faults_pg.py` (every fault freezes before the handshake, so only `connect_timeout` is exercised).
- **Original rule / finding:** PR-001A F11 (P2), and the PR-001RA requirement "approximately the declared ~3-second bound plus only a small explicitly measured scheduling allowance".
- **Independent reproduction:** see the F11 matrix.
  1. The server freezes after the probe's connection is established: 8.0 s with a cooperative cancel, **13.05 s** with a frozen cancel. On real `docker pause`: 7.25–7.28 s.
     - Cause: `asyncio.wait_for` cancels the task, and then **waits** while psycopg 3.3.6's `AsyncConnection.wait` handles `CancelledError`. It runs `_try_cancel(timeout=5)` and then drains for up to 5 more seconds.
  2. DNS resolution runs in the default executor, and `asyncio.run` joins that thread after the timeout: 3.8–3.97 s with a stopped Docker container (reproduced on the production image), 10.0 s with an unreachable resolver.
  3. Mutation m12 removes `wait_for` entirely. **All 19 candidate readiness tests still pass.** Only the auditor's freeze-on-query probe kills it: it hangs past 40 s, against the 13.0 s baseline.
- **Expected:** `/readyz` answers within ≈3 s plus a small measured allowance whatever the server does, as the code comment and row 6 state. Or the documented bound equals the measured worst case, and a test proves the deadline.
- **Actual:** the probe is bounded, but the bound is up to ~13 s from the server and resolver-bound from DNS. The deadline mechanism has no test.
- **Impact:** The dangerous part of the original F11 is gone: no unbounded hang and no application-pool use. Still:
  - The central guarantee of the repair and the READY claim are false by 2.5–4×, reproducibly, including on real `docker pause`.
  - A regression that removes the deadline would ship green.
  - The outcome always fails closed (503), and a probe holds one thread for at most ~13 s.
- **Bounded repair direction:** choose one.
  - (a) On deadline, close the socket directly (`conn.pgconn.finish()`, or abandon the task and finish the pgconn) instead of letting psycopg cancel and drain. Resolve the host outside the executor join or with a bounded lookup (for example `hostaddr`, or avoid joining the executor). Add a freeze-after-handshake test that fails if the deadline is removed.
  - (b) Document the true worst case (≈13 s, or the resolver's timeout) in `health.py`, row 6 and §6a, correct the "~2.3–2.8 s" figure, and add the same test.
- **Canonical decision required:** NO. Choosing between (a) and (b) is the builder's call.

### RA-2 — P3 — The CI audit canary step goes green when the advisory lookup fails

- **Location:** `.github/workflows/ci.yml:133-138` (`if pip_audit …; then fail; fi … grep -qi "urllib3" /tmp/canary.txt`).
- **Original rule:** PR-001RA F2 — "Do not count network failure / missing advisory service … as a successful vulnerability detection."
- **Independent reproduction** (`logs/f2-canary-semantics.txt`, step body verbatim): with `--network none` the step exits **0**. pip-audit fails, and `grep urllib3` matches urllib3 frames in the connection-error traceback.
- **Expected:** the canary passes only when the canary pin is reported vulnerable.
- **Actual:** it passes on any pip-audit error whose output mentions urllib3.
- **Impact:** low. The preceding main audit step fails red on the same network failure, so CI as a whole fails closed. The canary's self-assurance is still weaker than claimed, for example when only the canary call fails transiently.
- **Bounded repair direction:** require the vulnerability row, for example `grep -Eq '^urllib3 +1\.26\.4 +(PYSEC|GHSA)-'`, or require the "Found N known vulnerabilities" line.
- **Canonical decision required:** NO.

### RA-3 — P3 — Readiness and liveness share the application threadpool, so hung business requests starve them

- **Location:** `backend/app/composition.py:218-233` (sync `def healthz` and `def readyz`). Pre-existing: `composition.py` is unchanged since `4416e2b`. Coupled to PR-003 debt.
- **Original rule:** F11 "liveness remains lightweight/independent"; repeated probes must not hang.
- **Independent reproduction** (`logs/f11-business-starvation.txt`): warm pool, `docker pause`, then 60 clients looping `GET /v1/classifieds`.
  - `/readyz` takes 5.5–10.7 s, although the probe itself measured 2.0 s.
  - `/healthz` takes 6.6 s.
  - Both recover on unpause.
  - Without business traffic, 45 concurrent probes already queue for about 2 s on anyio's 40-token limiter.
- **Expected:** health endpoints are not blocked by business requests.
- **Actual:** they queue behind business threads that hang (up to 15 pooled connections) or wait on `pool_timeout` (30 s).
- **Impact:** during a database freeze under traffic, liveness can time out, which invites restart storms, and readiness exceeds any 3 s bound. Nothing is deployed yet.
- **Bounded repair direction:** make both endpoints `async def` (readiness awaits the async probe directly) or give them a dedicated limiter. Track with PR-003.
- **Canonical decision required:** YES — whether health endpoints must be isolated from the application threadpool (PR-003 scope).

### NOTE

- **N-A:** A failed probe's libpq socket is freed only by cyclic GC, because the reference cycle runs through the exception traceback. It shows as CLOSE_WAIT; `gc.collect()` frees all of them, and growth plateaued (10 → 5 → 10). Not a runaway leak.
- **N-B:** `README.md:9`, `:13` and `:33-35` still claim "Phase 0 — Walking Skeleton" and "Notifications and ML-serving are the only separately deployed processes" (the worker runs in-process and ML serving does not exist). The layout lists `apps/`, `data/` and `infra/`, none of which is tracked; `frontend/` is.
- **N-C:** `config.py:203`: loopback is `{localhost, 127.0.0.1, ::1}` only. `127.0.0.2:5433/homies` with non-development credentials would pass. This is within the documented guarantee.
- **N-D:** `test_dr_restore_pg.py:49` treats only `"1"` as required (`true` leaves the drill optional). CI sets `"1"`, and a contract test pins it.
- **N-E:** F8 reproducibility residue is present (see F8).
- **N-F:** CI evidence is metadata only (logs 403).

## Mutation matrix (every mutation on an external copy; baselines green: rid 23 passed, ci 9, sec 45, td01 15, ready 19)

| Mutation | Killed by |
|---|---|
| m01 no unhandled catch | `test_an_unhandled_exception_is_a_generic_500_with_the_request_id` |
| m02 no exception log | same test |
| m03 `pip_audit .` | `test_the_dependency_audit_targets_the_pinned_set_without_resolution` |
| m04 no `ENV=production` | CI image step (exit 1). The pytest suite does not catch it |
| m05 literal URL compare | 9 × `test_sec02` |
| m06 / m06b Alembic wipes logging | `test_local_self_migration_keeps_the_application_logging` (+ percent test) |
| m07 plain `sum()` | promtool "counts once across replicas" |
| m08 drill guard removed | `test_a_required_restore_drill_without_its_tools_fails_instead_of_skipping` |
| m09 no runtime assert | `test_the_production_image_is_python_312_and_ci_asserts_it` |
| m10 cancel on main | `test_superseded_runs_are_cancelled_on_branches_but_never_on_main` |
| m11 readiness uses the pool | 7 readiness tests |
| **m12 no wall-clock deadline** | **survives all candidate tests.** Killed only by the auditor freeze-on-query probe (RA-1) |
| m13 `re.match` + `$` | `test_the_middleware_replaces_an_id_with_a_trailing_newline` |
| m14 id middleware inside the limiter | `test_a_rate_limited_response_carries_the_callers_id` |

## Known debt (not reopened, not blockers)

- A warm-pool business request hangs on a frozen DB (**PR-003 DEBT — not claimed fixed**; reproduced, still hangs).
- No worker heartbeat.
- `/metrics` is public.
- No alert destination, no staging, no PITR.
- Base images by tag; the image runs as root.
- uvicorn lines are plain text; LOG_LEVEL validation residue.
- PG client minor is unpinned; build-tooling reproducibility residue.

## Final verdict

```text
P0: 0
P1: 0
P2: 1   (RA-1 — F11 residual)
P3: 2   (RA-2, RA-3)
NOTE: 6
```

**PR_001_REQUIRES_TARGETED_FIXES**

**Why this is not acceptance.** F11 is the highest-priority runtime gate. It is only PARTIAL: the warm-pool hang and the pool exhaustion are closed and independently verified. The repair's own declared bound fails, though: "3 s end-to-end, whatever the server does" measured 8–13 s after a mid-query freeze (7.3 s on real `docker pause`) and 3.8–10 s through DNS. No test protects the deadline.

**The fix is narrow:** either (a) or (b) from RA-1, plus a freeze-after-handshake test. Everything else re-audited is CLOSED:
- F1–F10, N1, N5, N7;
- domain regression ACCEPTED;
- Python 3.12 runtime evidence ACCEPTED.

A follow-up re-audit can be limited to RA-1, plus RA-2 if the builder takes it.

The PR-001_BASELINE_ACCEPTED marker is **not** emitted.

```text
PRODUCTION READINESS:
NOT READY

DEPLOYMENT:
NOT DEPLOYED
```

CHATGPT HANDOFF

Project:
Homies

Task:
PR-001RA — Narrow Independent Re-audit of PR-001R

Audited SHA:
70be78bfd746b63a1444e1dd7eb82023226215d3

Repair parent:
4416e2b14b007ba50aab41cad8e23deea32c4678

Accepted product ancestor:
879bf56cd7bb497fd77d8140fc1443fe9d61c1fe

Independent auditor session:
YES

F1:
CLOSED

F2:
CLOSED (canary residual RA-2, P3)

F3:
CLOSED

F4:
CLOSED

F5:
CLOSED

F6:
CLOSED

F7:
CLOSED

F8:
CLOSED (F8_REPRODUCIBILITY_RESIDUE = PRESENT)

F9:
CLOSED

F10:
CLOSED (static YAML inspection for main; branch runs observed)

F11:
PARTIAL — warm-pool hang and pool exhaustion CLOSED (503 in 2.01–2.52 s on real docker pause); declared 3 s end-to-end bound NOT met: 8.0–13.05 s freeze-after-connect (7.25–7.28 s on real docker pause), 3.8–10.0 s via DNS; deadline untested (mutation m12 survives) — RA-1 P2

N1:
CLOSED

N5:
CLOSED

N7:
CLOSED

Domain regression:
ACCEPTED

Supported Python 3.12 evidence:
ACCEPTED

Python:
3.12.14 (production image cra-prod:70be78b sha256:fef7982ca50c…, test image sha256:e2e9b8e8b852…, base python:3.12-slim@sha256:f77ac9e44ae9…)

PostgreSQL/PostGIS:
PostgreSQL 16.4 / PostGIS 3.4.3 (postgis/postgis:16-3.4@sha256:44126d87…, same digest as CI); pg_dump/pg_restore 16.15

Production image:
built --no-cache --pull from the exact-SHA LF export; ENV=production by default; 37 runtime distributions exactly at constraints.txt pins, no dev tools; runs as root (known debt)

Clock evidence:
app↔DB skew +0.1 ms (5 samples, RTT ≈1 ms); container monotonic == wall over 10 s; all timings monotonic

Tests actually run:
gates: Python 3.12 assert, installed==pinned 70/70, alembic heads=1, ruff OK, mypy OK (88 files), OpenAPI drift up to date, pip-audit pinned set clean, canary flagged (9 advisories); SQLite 824 passed / 298 skipped (all PG-only or Stripe-live); PostgreSQL/PostGIS 1121 passed / 1 skipped (Stripe live not requested), branch coverage 91.5 %, restore drills executed; promtool/amtool SUCCESS + auditor semantics SUCCESS; production-image startup matrix (9 + F5 cases); request-id ASGI (28 checks, 0 fail) and real HTTP (500 mixed concurrent, 0 mismatches, 200/200 single exception records); real 429 ×6; F11 fault matrix (docker pause/stop, freeze proxy, DNS, business-traffic interaction); F7 prerequisite matrix (7 cases); mutations 15/15 killed (m12 only by auditor probe)

CI:
GitHub Actions run 36436413217 (push, exact SHA 70be78b): all 5 jobs and all steps success — metadata only, job logs HTTP 403 (test counts/skips not visible)

P0:
0

P1:
0

P2:
1

P3:
2

NOTE:
6

Overall verdict:
PR_001_REQUIRES_TARGETED_FIXES

PR-001 baseline accepted:
NO

Repair required:
YES

General warm-pool business-request hang:
PR-003 DEBT — NOT CLAIMED FIXED

Production readiness:
NOT READY

Deployment:
NOT DEPLOYED

May participate in CONV-001:
NO

REQUEST TO CHATGPT:
Adjudicate PR-001RA and synchronize it with the independent TASK-014A result before authorizing any mutation-bearing next task.
