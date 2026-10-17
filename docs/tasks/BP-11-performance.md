# BP-11 — measured availability evidence

2026-10-16. Baseline production code pinned to 4ed8fe8ab334a8d8e344b80e266da2be3b661aee, measured before optimization. Same ten synthetic fixtures; 3 serial and 4 concurrent HTTP requests each. PostgreSQL16.4/PostGIS3.4, Python3.12 cached test runtime, dedicated disposable tmpfs database. SQL timing includes client round trips and result handling, not just server CPU; EXPLAIN separately records server execution. Wall durations use monotonic perf_counter. Local Docker wall-clock instability is not a certified application defect. These small samples are diagnostic evidence, not a production p95/SLO or maximum throughput claim.

| Fixture | Candidates | Returned | SQL before/after | SQL ms mean before/after | HTTP ms median before/after | HTTP ms max before/after | 4 concurrent SQL total before/after | Concurrent HTTP ms median before/after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small_weekly | 12 | 12 | 20/8 | 19,04/9,54 | 51,44/29,21 | 105,33/75,33 | 80/32 | 268,93/144,69 |
| many_weekly | 2480 | 2480 | 2488/8 | 1 738,13/12,72 | 5 165,97/103,04 | 5 284,41/118,03 | 9952/32 | 21 921,23/703,10 |
| one_off | 12 | 12 | 20/8 | 22,51/11,52 | 63,71/35,37 | 77,61/45,22 | 80/32 | 212,61/126,21 |
| dense | 2480 | 2480 | 2488/8 | 2 066,62/18,35 | 5 192,63/175,80 | 5 230,27/187,17 | 9952/32 | 19 969,70/773,79 |
| blackouts | 12 | 6 | 14/8 | 23,70/14,32 | 72,16/48,77 | 78,95/55,59 | 56/32 | 227,35/156,94 |
| full | 2480 | 0 | 2488/8 | 2 665,16/26,10 | 5 719,86/270,04 | 5 986,73/274,66 | 9952/32 | 22 910,56/1 088,99 |
| maximum_days | 2480 | 2480 | 2488/8 | 2 914,94/12,91 | 7 415,28/126,02 | 8 606,32/130,90 | 9952/32 | 23 681,11/394,31 |
| no_settings | 0 | 0 | 6/5 | 8,79/6,51 | 34,01/25,03 | 36,44/27,83 | 24/20 | 105,08/100,87 |
| spring_dst | 30 | 24 | 32/8 | 31,60/9,19 | 93,21/31,22 | 94,44/32,15 | 128/32 | 338,38/97,18 |
| autumn_dst | 30 | 24 | 32/8 | 30,43/10,46 | 88,49/33,73 | 90,39/36,58 | 128/32 | 346,98/108,09 |

Every full returned slot array is identical before/after (not just counts). No concurrent response differed or failed. Raw results and plans: BP-11-baseline.json and BP-11-optimized.json. Candidate count means attempted wall-clock starts, including invalid DST starts; the original SQL occupancy calls occur only after DST/notice/blackout filtering. HTTP totals include listing/media/price loading, settings and PostgreSQL time; optimized core availability itself uses at most three queries. No settings returns before availability computation.

## Query plan / cache decision

Existing indexes: viewing_windows.listing_id, viewing_blackouts.listing_id, ix_viewings_listing_starts(listing_id, starts_at), ix_viewings_status_starts(status, starts_at). EXPLAIN ANALYZE BUFFERS on the dense 744-booking fixture chooses a sequential scan because all rows belong to the relevant listing/time range (19 shared buffers); the after range projection reports 0.770 ms execution, 0.190 ms planning. This small all-relevant fixture does not justify a new index. Historical and unrelated volume remains subject to existing database deadlines; no unbounded row materialization is allowed.

No cache: after computation is bounded and four simultaneous reads use 32 SQL statements total rather than 9952. A cache would introduce stale public visibility/capacity and invalidation complexity without a measured need. Public reads remain advisory; booking writes independently lock/revalidate current capacity.

## Operational bounds and deployment prerequisites

* Public pages: 1–31 days; start today through +366 days in the schedule zone.
  The new horizon is an operational bound authorized by directive §6.4, not
  a new domain scheduling rule. It allows future paging and both annual DST
  seasons while rejecting arbitrary historical/distant scans. Authenticated
  writes retain existing rules and independently check the stored schedule.
* Each computation materializes at most 2,001 relevant windows, 2,001 relevant
  blackouts, or 10,001 relevant confirmed booking intervals. The extra row
  detects overflow: ceilings are 2,000/2,000/10,000 respectively. Candidate
  expansion stops after 100,000 attempted wall starts. These are safety
  budgets, not deletion/normalization of stored records; exceeded budgets
  return a neutral 503 with Retry-After: 1, never partial availability.
  The measured high schedule has 112 windows / 2,480 attempted starts;
  the full fixture has 1,488 confirmed bookings. Budgets leave substantial
  room above these fixtures while bounding Python memory and CPU. Existing
  5-second PostgreSQL statement and client deadlines bound scans/waits when
  historical volume or a bad plan is costly. Larger real workloads need
  measured operational tuning, not a speculative index in this task.
* Dedicated per-IP token bucket: burst20, refill0.2/s (12/min), fail-closed,
  all listing ids/dates/authentication states share the same bucket. Rejection
  is HTTP429 with Retry-After through existing middleware, before DB work.
  The existing store is per process: horizontal scaling multiplies budgets;
  a shared limiter remains an operational prerequisite before scaling out.
* Forwarded headers require BOTH TRUST_PROXY_HOPS and TRUSTED_PROXY_CIDRS
  (JSON list of actual proxy networks; default empty). The socket peer and
  every intermediary in the selected suffix must be trusted. Untrusted peer,
  missing/invalid chain or invalid client address falls back to socket peer.
  Never configure an all-address CIDR to trust arbitrary callers. Existing
  deployments using hop count alone must set their actual networks before
  rollout; otherwise they safely share the proxy's IP bucket.
* Uvicorn must retain the socket peer: the shipped Docker CMD now explicitly
  uses --no-proxy-headers. Custom launchers must preserve that setting.
  Synthetic real TCP/Uvicorn tests verify ignored untrusted headers and
  explicitly trusted forwarding, in addition to ASGI limiter evasion tests.
  No external deployment topology or production configuration was changed
  or certified. A future deployment must verify its actual proxy boundary.

## Verification history (actual runs)

Python3.12 test image `bp10c-test:c385136`, PostgreSQL16.4/PostGIS3.4.3,
dedicated container `homies-bp11-builder-20261016`; unrelated databases untouched.

* Baseline benchmark: 1 passed, 174.49s. After benchmark: 1 passed, 18.70s.
  Fixture source: `backend/tests/test_bp11_benchmark_pg.py`; opt-in
  BP11_BENCHMARK_OUTPUT plus disposable TEST_DATABASE_URL. Outputs preserve
  full slot arrays and query plans for reproducible comparison.
* First functional run: 92 passed / 2 failed, 101.84s. Both new-test defects
  repaired: nonexistent synthetic moderation attribute replaced by actual
  moderation API, total-query expectation corrected for existing loaded
  listing relationships. No production workaround for either test.
* Follow-up command used a misspelled DST file; collected no tests. Corrected
  focused suite (BP-11 HTTP/PG, existing viewings/PG/DST and rate limits):
  122 passed / 1 failed, 146.69s. Unexpected401 instead of404 on the second
  action of existing `test_a_stranger_can_touch_nothing`; isolated rerun plus
  six OpenAPI checks: 7 passed, 7.32s, without authentication changes.
  Local cause is not certified; stable CI is required rather than assuming
  clock instability proves an application pass or defect.
* Additional maximum-capacity and out-of-horizon authenticated booking tests:
  2 passed, 6.68s.
* New PG race observes pg_blocking_pids: public read sees committed free
  capacity during an uncommitted confirmation; a subsequent booking waits
  for the settings lock, then refuses the occupied slot. Next public read
  is empty, one confirmed booking, no increase in deadlocks.
* Ruff clean (initial fixture-import F811 errors corrected using explicit
  shared fixture registration); Mypy clean, 126 files. OpenAPI6 passed;
  generated web API consistency and TypeScript typecheck passed.
* npm installed481 pinned packages. HostNode24.14 generated transitive
  engine-version warnings; the CI web runtime remains authoritative.
* Two interruptions exhausted automatic approval review usage; rejected
  commands were not executed. Checkpoint recovery reused completed baseline,
  implementation and measurements. No full-suite/mutation/CI result is
  inferred from these targeted runs.

Independent review and required exact-candidate GitHub CI: PENDING at builder
freeze. Parent orchestration owns those remaining gates. No merge/deployment.
