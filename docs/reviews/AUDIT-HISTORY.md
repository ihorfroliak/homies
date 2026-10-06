---
id: AUDIT-HISTORY
name: Homies audit history
type: audit_index
status: accepted
as_of: 2026-10-06
current_baseline: IBB-001 (last formal baseline; volatile status in docs/PROJECT-STATUS.md)
current_baseline_sha: 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
---

# Audit history

How Homies evolved, what was checked, what failed, what was repaired, and
which exact state was eventually accepted. This is a **map** over the
immutable reports in this folder; it never replaces them. Reports named
`*-audit.md` are archived byte-for-byte and are never edited. Where this
index and a report disagree, the report wins. Naming and status words:
[TRACEABILITY](../engineering/TRACEABILITY.md).

Where an exact historical SHA or count cannot be established from repository
evidence, this index says **not recorded in this index** rather than guess.
Several early audit reports (TASK-001, -003, -005, -007) were delivered
outside the repository; their outcomes are recorded in
[IMPLEMENTATION-CONVERGENCE](../canonical/IMPLEMENTATION-CONVERGENCE.md) and
[DECISIONS](../DECISIONS.md).

## The audit model

Used for every high-risk cycle up to IBB-001:

```text
Specification (canon + task contract)
→ Implementation (builder, on a task branch)
→ Builder evidence (tests, PostgreSQL/PostGIS, mutation, benchmarks)
→ Independent audit of the exact SHA (Codex or an independent Claude session)
→ Targeted repair of the findings only
→ Narrow re-audit of the repair SHA
→ Accepted SHA (acceptance marker, decision entry, archived report)
```

Severity: **P0 CRITICAL · P1 HIGH · P2 MEDIUM · P3 LOW · NOTE**. "ACCEPTED"
always means accepted for continued development, never production readiness.

### Governance change after IBB-001 — risk-based verification

Independent audits are **not** mandatory for every future task. Verification
is proportionate to risk:

| Class | Scope | Verification |
|---|---|---|
| **R0** | docs, wording, trivial cleanup | builder + lightweight checks |
| **R1** | ordinary low-risk implementation | builder + tests + CI |
| **R2** | database migrations, authorisation, concurrency, privacy, core marketplace invariants | independent review / audit where material |
| **R3** | payments, production data, deployment, security-critical operational changes | independent audit + operational evidence + founder approval |

Future agents: do not recreate the audit-per-task loop that preceded IBB-001.
Classify the task first; audit only what the class requires.

### Addendum 2026-10-01 — milestone audit (D-88, owner directive)

For PR-002 and the following high-risk tasks until the next milestone, the R2
"independent review" is **deferred into a comprehensive milestone /
production-readiness audit** that reviews them together. A task integrates into
`main` for continued development on builder evidence (full suites, real
PostgreSQL scenarios, mutation/fault probes with every load-bearing mutant
killed) plus green CI. Status: **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED**.
This is not independent verification and not production acceptance;
production stays NOT READY / NOT DEPLOYED. R3 is unchanged.

## Summary

| Cycle | Human purpose | Accepted SHA | Final verdict | Report |
|---|---|---|---|---|
| Foundation (TASK-001…009) | C1–C8 Phase-1 foundation | Foundation Baseline 001 `dfa3254c…` → Foundation Baseline 002 `36231840…` | `HOMIES_FOUNDATION_BASELINE_002_ACCEPTED` | [Codex](2026-09-25-task009-codex-final-foundation-audit.md) · [Claude](2026-09-25-task009-claude-final-foundation-audit.md) |
| Geography (TASK-010) | structured geography, address, classification, public location | `ed9cf1b49f70716bd214a3212b2e7497ca5078ec` | `TASK_010_PHASE_1A_SLICE_ACCEPTED` | [TASK-011R](2026-09-27-task011r-codex-task010r-audit.md) |
| Freshness (TASK-012) | listing freshness, availability, quality | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` | `TASK_012_PHASE_1A_SLICE_ACCEPTED` | [TASK-012RA](2026-09-28-task012ra-codex-task012r-audit.md) |
| Search / map (TASK-013) | one search model for list and map | `3f324b6ddff6c7557894eb5f65736729d956f7eb` | `TASK_013_PHASE_1A_SLICE_ACCEPTED` | [TASK-013RA](2026-09-28-task013ra-codex-task013r-audit.md) |
| Saved search / alerts (TASK-014) | saved listings, saved searches, alerts | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` | `TASK_014_PHASE_1A_SLICE_ACCEPTED` | [TASK-014RA](2026-09-29-task014ra-independent-task014r-audit.md) |
| Runtime / CI (PR-001) | Python 3.12, pinned deps, CI, readiness, restore drills | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` | `PR_001_BASELINE_ACCEPTED` | [PR-001RA2](2026-09-29-pr001ra2-independent-pr001r2-audit.md) |
| Convergence (CONV-001) | one history from PRODUCT + INFRA | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` | `INTEGRATED_BASELINE_ACCEPTED` → **IBB-001** | [CONV-001A](2026-09-30-conv001a-independent-integration-audit.md) |

---

## 1. Foundation (2026-09-24 … 2026-09-25)

Context: the C1–C8 port of Schema v1 into the Python stack, committed on
`main` up to `782c833f100f1bf2e86888b664c9b30b27cbc1dd` (C8), was a
**candidate** under the canon adopted in TASK-000.

| ID | Human purpose | Candidate / repair SHA | Result | Verdict / counts | Evidence |
|---|---|---|---|---|---|
| TASK-000 | canonical governance bootstrap; preserve foreign work | `988b31b138436cb69ad20e5cb06e6e3be116fe64` | builder | — | [contract](../tasks/TASK-000-canonical-governance.md) |
| TASK-001 | independent convergence audit (Codex) of `988b31b` | — | audit | `SAFE_TO_CONTINUE_WITH_BLOCKING_FIXES_IN_NAMED_CONTEXTS` · P0 0 / P1 5 / P2 4 (F-01…F-09) | [contract](../tasks/TASK-001-codex-convergence-audit.md); report outside the repository |
| TASK-002 | foundational repair F-01…F-09 | `0d6c55451a6e7e9b0e616957e2384449aa374921` | builder | — | [contract](../tasks/TASK-002-foundational-repair.md) · [mutation](2026-09-24-task002-mutation.md) |
| TASK-003 | re-audit (Codex) of `0d6c554` | — | audit | F-01…F-03, F-05…F-09 CLOSED; **F-04 PARTIALLY_CLOSED (P1)** | report outside the repository |
| TASK-004 | atomic publication authorisation (F-04) | `dfa3254cb8f8d321c278f1d815bbb7e14a514561` | builder | — | [contract](../tasks/TASK-004-atomic-publication-auth.md) · [mutation](2026-09-24-task004-mutation.md) |
| TASK-005 | re-audit of `dfa3254` | — | audit | F-04 CLOSED · `TASK_004_ACCEPTED_WITH_NONBLOCKING_NOTES` · `C1_C8_FOUNDATION_ACCEPTED_FOR_CONTINUED_PHASE_1A_DEVELOPMENT` · new N-01…N-04 (N-02 P2, others P3) | report outside the repository |
| **Foundation Baseline 001** | first accepted foundation | **`dfa3254cb8f8d321c278f1d815bbb7e14a514561`** | ACCEPTED | — | [convergence §000](../canonical/IMPLEMENTATION-CONVERGENCE.md) |
| TASK-006 | authority integrity cleanup N-01…N-04 | `1b2458c0aa2e73d97475733f68e424e62c7ba0e6` | builder | — | [contract](../tasks/TASK-006-authority-integrity-cleanup.md) · [mutation](2026-09-25-task006-mutation.md) |
| TASK-007 | re-audit of `1b2458c` | — | audit | N-02, N-03, N-04 accepted; N-01 PARTIALLY_CLOSED via new N-05 (P3) | report outside the repository |
| TASK-008 | final foundation hardening N-05…N-10 | `36231840ee52d6185e73fda07e54eab33ffe41f3` | builder | — | [contract](../tasks/TASK-008-final-foundation-hardening.md) · [mutation](2026-09-25-task008-mutation.md) |
| TASK-009 | two independent final audits (Codex + Claude) of `3623184` | — | audit | `TASK_008_ACCEPTED_WITH_NONBLOCKING_NOTES` · P0 0 / P1 0 / P2 0 (P3/NOTE only) | [Codex](2026-09-25-task009-codex-final-foundation-audit.md) · [Claude](2026-09-25-task009-claude-final-foundation-audit.md) |
| **Foundation Baseline 002** | accepted foundation for Phase-1A development | **`36231840ee52d6185e73fda07e54eab33ffe41f3`** | ACCEPTED (D-56) | `HOMIES_FOUNDATION_BASELINE_002_ACCEPTED` | [convergence](../canonical/IMPLEMENTATION-CONVERGENCE.md) |

Remaining debt: protected-proof regression tests E01–E03; commit-order test
evidence (P3, partly retired in TASK-010); revoke starvation; error-code
convention; see the Foundation Baseline 002 section of the convergence map.

## 2. Geography (2026-09-25 … 2026-09-27)

| Field | Value |
|---|---|
| ID | TASK-010 — geography, address, property classification |
| Candidate SHA | `e87352a9862408e76e7ebee08b846dab728d4dac` |
| Independent audit | TASK-011 (Codex) — `TASK_010_REQUIRES_TARGETED_FIXES` · P0 0 / P1 0 / P2 3 / P3 0 (GEO-01/02/03) + public EXACT decision — [report](2026-09-26-task011-codex-task010-audit.md) |
| Repair | TASK-010R — [contract](../tasks/TASK-010R-geography-correctness-privacy.md) · [mutation](2026-09-26-task010r-mutation.md); public EXACT prohibited (D-58) |
| Repair SHA | `ed9cf1b49f70716bd214a3212b2e7497ca5078ec` |
| Re-audit | TASK-011R (Codex) — P0–P3 0 · NOTE 2 — [report](2026-09-27-task011r-codex-task010r-audit.md) |
| Final verdict | `TASK_010R_ACCEPTED_WITH_NONBLOCKING_NOTES` → `TASK_010_PHASE_1A_SLICE_ACCEPTED` (D-66) |
| Accepted SHA | **`ed9cf1b49f70716bd214a3212b2e7497ca5078ec`** |
| Evidence | [mutation](2026-09-25-task010-mutation.md) · [location benchmark](2026-09-25-task010-location-benchmark.md) |
| Remaining debt | notes N11R-01/02 fixed in TASK-012; reference data not ingested |

## 3. Freshness / availability (2026-09-27 … 2026-09-28)

| Field | Value |
|---|---|
| ID | TASK-012 — listing freshness, availability, quality |
| Candidate SHA | `c4c8bfac7f59a0930d9403d1100f35dccf003ae6` |
| Independent audit | TASK-012A (Codex) — `TASK_012_REQUIRES_TARGETED_FIXES` · P0 0 / P1 0 / P2 1 / P3 0 (F12A-01 session-time-zone temporal invariants) — [report](2026-09-27-task012a-codex-task012-audit.md) |
| Repair | TASK-012R UTC temporal invariants — [contract](../tasks/TASK-012R-utc-temporal-invariants.md) · [mutation](2026-09-27-task012r-mutation.md) (D-67) |
| Repair SHA | `879bf56cd7bb497fd77d8140fc1443fe9d61c1fe` |
| Re-audit | TASK-012RA (Codex) — P0–P3 0 — [report](2026-09-28-task012ra-codex-task012r-audit.md) |
| Final verdict | `TASK_012R_ACCEPTED_WITH_NONBLOCKING_NOTES` → `TASK_012_PHASE_1A_SLICE_ACCEPTED` (D-75) |
| Accepted SHA | **`879bf56cd7bb497fd77d8140fc1443fe9d61c1fe`** — later the common ancestor of the PRODUCT and INFRA lines |
| Evidence | [mutation](2026-09-27-task012-mutation.md) · [freshness benchmark](2026-09-27-task012-freshness-benchmark.md) |
| Remaining debt | see the TASK-012RA notes in the report |

## 4. Search / map (2026-09-28) — PRODUCT line

| Field | Value |
|---|---|
| ID | TASK-013 — search, map & marketplace discovery |
| Candidate SHA | `56567d24bd764563bc21707c0c027e637a206e16` |
| Independent audit | TASK-013A (Codex) — `TASK_013_REQUIRES_TARGETED_FIXES` · P0 0 / P1 0 / P2 1 / P3 1 + NOTE (F13A-01/02/03) — [report](2026-09-28-task013a-codex-task013-audit.md) |
| Repair | TASK-013R — validate discovery input before SQL; one-statement map partition (D-76) |
| Repair SHA | `3f324b6ddff6c7557894eb5f65736729d956f7eb` |
| Re-audit | TASK-013RA (Codex) — P0–P3 0; notes F13RA-N01, F13RA-N02 — [report](2026-09-28-task013ra-codex-task013r-audit.md) |
| Final verdict | `TASK_013_ACCEPTED_WITH_NONBLOCKING_NOTES` → `TASK_013_PHASE_1A_SLICE_ACCEPTED` (D-77) |
| Accepted SHA | **`3f324b6ddff6c7557894eb5f65736729d956f7eb`** |
| Evidence | [mutation](2026-09-28-task013-mutation.md) · [discovery benchmark](2026-09-28-task013-discovery-benchmark.md) |
| Remaining debt | F13RA-N01 wording/test → MICRO-001; F13RA-N02 local Docker clock (environment) |

## 5. Saved search / alerts (2026-09-28 … 2026-09-29) — PRODUCT line

| Field | Value |
|---|---|
| ID | TASK-014 — Saved Listings, Saved Search & Alerts |
| Candidate SHA | `196c88796cf34a6b19860259cc6ff81c94dbe8d2` |
| Independent audit | TASK-014A (independent Claude) — `TASK_014_REQUIRES_TARGETED_FIXES` · P0–P2 0 / P3 6 / NOTE 8; evidence NOT_VERIFIED — [report](2026-09-29-task014a-independent-task014-audit.md) |
| Repair | TASK-014R — durable single-use unsubscribe capabilities, stored-query integrity, migration re-upgrade, PATCH 409, SMTP classification — [mutation](2026-09-29-task014r-mutation.md) |
| Repair SHA | `7ffb4f51dd315363362df1a5f8fc5c19a57767dc` (first freeze `39f158e` failed the stable evidence run; test-only fixture fix) |
| Re-audit | TASK-014RA (independent Claude) — P0–P3 0 · NOTE 5 — [report](2026-09-29-task014ra-independent-task014r-audit.md) |
| Final verdict | `TASK_014_ACCEPTED_WITH_NONBLOCKING_NOTES` → `TASK_014_PHASE_1A_SLICE_ACCEPTED` |
| Accepted SHA | **`7ffb4f51dd315363362df1a5f8fc5c19a57767dc`** — PRODUCT parent of IBB-001 |
| Evidence | [TASK-014 mutation](2026-09-28-task014-mutation.md); stable run `36595074447` (harness `3d37a7e8e29b71a6c57b7b3884d9632eef6c8fc9`) |
| Remaining debt | N-2 poison work-item cap; RA-N1 delivery-side unknown-exception retry; RA-N2 token wording / D-81 → MICRO-001; RA-N5 backfill trust; X04 CAS note |

## 6. Runtime / CI / readiness (2026-09-28 … 2026-09-29) — INFRA line

| Field | Value |
|---|---|
| ID | PR-001 — Runtime / CI / Readiness Baseline (built on `879bf56`, no TASK-013/014 code) |
| Candidate SHA | `4416e2b14b007ba50aab41cad8e23deea32c4678` |
| Independent audit | PR-001A (Codex) — `PR_001_REQUIRES_TARGETED_FIXES` · P0 0 / P1 0 / P2 4 / P3 7 — [report](2026-09-28-pr001a-codex-pr001-audit.md) · [verdict record](2026-09-28-pr001a-verdict-record.md) |
| Repair | PR-001R — request id on 500, pinned audit, fail-closed ENV, bounded readiness (`e6059d9ae9a6c115612baf282904334a245c9780`; archive commit on top) |
| Repair SHA | `70be78bfd746b63a1444e1dd7eb82023226215d3` |
| Re-audit | PR-001RA (independent Claude) — `PR_001_REQUIRES_TARGETED_FIXES` · P2 1 / P3 2 (RA-1, RA-2, RA-3) — [report](2026-09-29-pr001ra-independent-pr001r-audit.md) |
| Second repair | PR-001R2 — honest readiness contract, freeze-after-connect regression, strict audit canary; RA-3 deferred to PR-003 |
| Second repair SHA | `5cad442f07264ab25b3024c96fc691ad9c7a75fa` |
| Second re-audit | PR-001RA2 (independent Claude) — P0–P3 0 · NOTE 6 — [report](2026-09-29-pr001ra2-independent-pr001r2-audit.md) |
| Final verdict | `PR_001_ACCEPTED_WITH_NONBLOCKING_NOTES` → `PR_001_BASELINE_ACCEPTED` |
| Accepted SHA | **`5cad442f07264ab25b3024c96fc691ad9c7a75fa`** — INFRA parent of IBB-001 |
| Remaining debt | RA-3 health isolation + DB client deadlines → PR-003; RA2-N1 decision-budget value test → MICRO-001; notes N-A, N-C, N-D, N-E, N-F |

## 7. Convergence (2026-09-30) — one line again

| Field | Value |
|---|---|
| ID | CONV-001 — Product / Infrastructure Baseline Convergence |
| Candidate SHA | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` — one merge commit, parents `7ffb4f51…` (PRODUCT) and `5cad442f…` (INFRA), merge base `879bf56c…` |
| Builder result | PASS: 3 git conflicts (docs, `.gitattributes`), 1 semantic test interaction resolved in the merge; CI run `36644550108` all green; evidence run `36644558783` |
| Independent audit | CONV-001A (independent Claude) — 21 integration gates ACCEPTED · P0–P3 0 · NOTE 3 — [report](2026-09-30-conv001a-independent-integration-audit.md) |
| Repair / re-audit | none required |
| Final verdict | `CONV_001_ACCEPTED_WITH_NONBLOCKING_NOTES` → `INTEGRATED_BASELINE_ACCEPTED` |
| Accepted SHA | **`5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98`** |
| Baseline | **Integrated Backend Baseline 001 (IBB-001)** — [record](../baselines/IBB-001.md); tag `backend-baseline-001` |
| Remaining debt | CV-N1 harness drill count, CV-N2 restore drill omits TASK-014 tables, CV-N3 `assert_unhandled_500` request-id assertion → MICRO-001 |

## 8. After IBB-001 — integrated without independent acceptance (D-88)

*Added 2026-10-06 (TASK-016). A map only; no new verdict.*

No independent acceptance has been recorded after IBB-001, and no successor
baseline exists. Work since then reached `main` under the risk-based policy
on builder evidence and green CI.

**Recorded by their own task records as BUILDER VERIFIED · MILESTONE AUDIT
DEFERRED (D-88)** (merge on `main`, candidate in brackets):

| Item | Class | `main` merge (candidate) |
|---|---|---|
| PR-002 release and migration compatibility | R2 | `13a92ef77b66096021d3927fdb255b546a4ecc63` (`be26fcb8`) |
| PR-003 database deadlines and failure containment | R2 | `451b7e566a1958097b2df2266e2bb7cc41314621` (`e54b3eec`) |
| TASK-015 S1 moderation core, publication hold | R2 | `1a65d3812f5f175e3b27222401685ebf8260b67a` (`1ccf1a18`) |
| TASK-015 S2+S3 listing reports, moderator loop | R2 | `4bf6610849ce42b17480e498d474c9355b0e1887` (`7a51236d`) |
| TASK-015 S5 review requests | R2 | `1de34bf550e55c0e4e28d78090f0720d6812287e` (`3146fed3`) |
| TASK-015 S4a message moderation | R2 | `03268432f664ec6283f427b2f528a8bb6f814065` (`ff433303`) |
| TASK-015 S4b engagement safety (via PROGRAM-001) | R2 | `c32ac63f9a4c08366369a2088709b658754373e6` (`779b30fe`) |

**Merged builder verified, without an independent audit and without a
recorded D-88 deferral** — whether any of them joins the milestone review is
part of the open decision below: FE-001 and FE-002 (R2 by their own records),
GROWTH-001 measurement facts (R1/R2), the TASK-015 closure and the
PROGRAM-001 security repairs — all via PROGRAM-001 `c32ac63f…`, externally
reviewed by GPT-5.6 Sol; F6 enforcement via `995b05fe72bc15a86141e214bf1c4fc63b8bc570`
(`cde91fa9`, class not recorded).

**R1, founder/GPT reviewed (not independent audits):** BP-1 `6be148b6…`
(`fa5612e6`), BP-2 + BP-7 `6adca78c…` (`caf38383`), BP-12 `a7756e16…`
(`0d45583a`). **R0/R1 cleanup:** MICRO-001 `dacbe9e3` (evidence, docs,
tests). **Documentation-only:** TASK-015 Phase A `985db7ae`, FE-003 contract
`c87616ad`, P-0 `673b61e0`, HM-1 `dc74da3f`.

External reviews by GPT-5.6 Sol (S4a, PROGRAM-001 "accepted for merge with
conditions", FE-003 r1/r2, P-0) are recorded through their outcomes in
DECISIONS D-102…D-107, canon 04a §24, the FE-003 contract and the DESIGN-001C
handoff; their review texts are not archived in this folder, and the
conditions attached to PROGRAM-001's acceptance are not listed as such
(recorded audit-trail gap).

**CANONICAL DECISION REQUIRED:** D-88 defers the independent review "until
the next milestone" but no repository record defines that milestone's
trigger, scope, acceptance threshold or whether it produces a successor
baseline. This section lists scope only; it defines none of those.

---

## Before the canon (historical)

Reports dated 2026-07 (enterprise-architecture review, OAT reports,
full-system and technical audits) predate the canonical documents and
TASK-000. They describe the earlier booking-era system and are historical
context only; they are not part of any acceptance above.
