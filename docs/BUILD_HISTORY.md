# BUILD HISTORY

One entry per completed micro-cycle. Newest last. Status legend: ✅ shipped ·
⚠️ shipped with known gap · ⛔ blocked.

| # | Date | Scope | Tests | Security / verification | Commit | CI | Deploy |
|---|---|---|---|---|---|---|---|
| 01 | 2026-07-05 | Phase 0: monorepo skeleton, FastAPI walking skeleton, compose stack, CI | 1 | — | `7ec222f` | n/a | — |
| 02 | 2026-07-05 | Chat 01 closed: 6 ADRs, OpenAPI+AsyncAPI contracts, bounded-context map | — | Spectral 0 errors | `a675c7b` | n/a | — |
| 03 | 2026-07-05 | Business architecture package (17 bounded contexts, lifecycles, disputes) | — | — | `97c73f8` | n/a | — |
| 04 | 2026-07-05 | Hostile EA review: 15 perspectives, 100-item red team, gap analysis | — | — | `cd5f5bc` | n/a | — |
| 05 | 2026-07-05 | Strategy: operator-first model, Stripe Connect, KPI framework | — | — | `c4d1652` | n/a | — |
| 06 | 2026-07-05 | Founder Mode constitution + repo CLAUDE.md | — | — | `4742ff8` | n/a | — |
| 07 | 2026-07-05 | **D4 vertical slice + D5 hardening**: auth, listings, booking, payments (sim), ledger, admin | 12 | exclusion constraint, late-success refund, webhook secret, append-only guards | `4b5852f` | n/a | — |
| 08 | 2026-07-05 | **D6 warfare**: real adversarial runs on live Postgres | 12 | 60→1 booking, 200→1 capture, 10→1 payout, DB crash ACID | `dd3b88c` | n/a | — |
| 09 | 2026-07-05 | D7 production readiness board — evidence-based **NO-GO** (22/100) | — | evidence-only audit | `f032815` | n/a | — |
| 10 | 2026-07-05 | **D8**: release loop, Alembic migrations, DB append-only triggers | 12 | direct-SQL ledger tamper blocked (owner-proof) | `7a3fc50` | n/a | — |
| 11 | 2026-07-05 | **D9 disaster recovery**: encrypted backup, restore drill | 12 | restore RTO 4s, financial reconciliation PASS ×2 | `4989b50` | n/a | — |
| 12 | 2026-07-05 | **B1 Stripe Connect** adapter, webhook subsystem, reconciliation engine | 16 | signature→400, dup event→1 capture; ⚠️ sandbox unverified | `c883348` | n/a | — |
| 13 | 2026-07-06 | **OAT-01** operational acceptance: 10 whole-business scenarios | 26 | money spine passes; ops layer dead-ends documented | `3bd0ba7` | n/a | — |
| 14 | 2026-07-06 | **OAT-02** notification layer: domain events, routing, booking state, incidents | 34 | found + fixed latent double-capture race (FOR UPDATE) | `d66d0af` | n/a | — |
| 15 | 2026-07-09 | **OAT-03** transactional outbox, worker, retry state machine, metrics | 41 | duplicate-worker SKIP LOCKED overlap=0; queue drains to zero | `b7ce97d` | n/a | — |
| 16 | 2026-07-23 | Repo published to GitHub; salvaged early-draft ADRs preserved | 41 | — | `acba734` | ❌ then ✅ | — |
| 17 | 2026-07-23 | **CI fix**: setuptools package discovery (`Multiple top-level packages`) | 41 | clean-venv CI chain reproduced before push | `ea35259` | ✅ | — |
| 18 | 2026-07-23 | **AUDIT-01**: full system audit + project tracking docs + security probes | 53 | **12/12 IDOR/authz probes pass** | `638d06b` | ✅ | — |
| 19 | 2026-07-23 | **MC-01 / SEC-01+SEC-02**: perimeter rate limiting (token bucket, central policies, proxy trust, per-policy failure semantics, metrics) + fail-fast secret validation | 84 | 31 new security tests; 12/12 probes still pass; production+default secrets refuse to start (verified e2e) | `ad93424` | ✅ | — |
| 20 | 2026-07-23 | **MC-02 / FIN-01**: real-SDK webhook validation, payment-environment model, gated Stripe Test Mode suite. **Two production bugs found and fixed** (trust-vs-processing failure conflation; `dict(event)` crash on genuine Stripe events) | **105** (+1 skipped) | 10 real-signature tests, 9 environment tests; replay/tamper/stale rejected; duplicate delivery → single capture; reconciliation ok | _this cycle_ | — | — |

## Notes

- Entries 01–15 predate GitHub publication, so CI status is `n/a` (the workflow
  existed but had never run).
- Build 16 is the first CI execution — it failed, exposing a packaging defect
  that had been latent since build 10 (Alembic added a second top-level package).
  Root cause and fix in build 17.
- No entry has a deployment: the platform has never been deployed to any
  environment.
