# TASK-016 — Source-of-truth documentation reconciliation

| Field | Value |
|---|---|
| Status | **PHASE B — BUILDER CANDIDATE** (documentation and governance only). Phase C: two independent read-only audits. `MERGE AUTHORIZED: NO` |
| Authorisation | founder/GPT: Phase A read-only audit (2026-10-06) → adjudicated → "TASK-016 PHASE B AUTHORIZED — final founder/GPT contract v2" |
| Risk | R0 (documentation, governance, agent instructions). Canon changes (00, 05, 06, 07, IMPLEMENTATION-CONVERGENCE, DECISIONS) explicitly approved for this task |
| Baseline | `main` = `a7756e16c5ae2888776bf02a022b44b0221c0f7a` (BP-12 merge; parents `6adca78c9ae6342438f08b8b7c8cfd1b88be714a` + `0d45583a14abbf5d4ce5eced0a5c270382aa44b5`), tree `f6363155f86a65b603772c65303a2fe6b36e4a9a`, main CI `37417946174` completed / success — backend, web, image, contracts, monitoring, secrets all success |
| Branch | `claude/TASK-016-source-of-truth-docs-reconciliation` |
| Decisions | **D-106** (repository system of record and independent research governance), **D-107** (provenance index for P-0 and HM-1 — no new semantics) |
| Candidate | this file does not name the commit that contains it (see [TRACEABILITY — self-reference](../engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit)); the candidate SHA, its CI run and any merge SHA are in Git and in the final report |

## 1. Purpose

Make the Homies repository a durable, self-contained system of record for
accepted project knowledge, so that an engineer with only the repository and
Git history (no chat, no agent memory, no design-tool session) can tell what
Homies is, what is accepted, what is on `main`, what is next and what is
authorised.

**Repository durability ≠ document authority.** Committed history, with the
accepted state on `main`, is the durable record; which document wins is still
decided by [00-AUTHORITY](../canonical/00-AUTHORITY.md). Branches are
candidates, historical files stay historical, research stays non-normative.

## 2. Phase A evidence (read-only audit of `6adca78`, 2026-10-06)

Two independent read-only passes (status/chronology; knowledge-loss and
research/IP) plus a builder identifier audit, adjudicated by the builder.
Phase A ran on `6adca78`; the only later change on `main` is the BP-12 merge
`a7756e1` (BP-12 code, its task record, OpenAPI description, DEVLOG).

**Inventory (160 Markdown documents classified):** CANONICAL 11 · CURRENT
INDEX 5 · ACTIVE SPECIFICATION 29 · TASK CONTRACT 24 · BASELINE RECORD 1 ·
AUDIT EVIDENCE 27 · HISTORICAL 31 · SNAPSHOT 1 · SUPERSEDED 26 · RESEARCH 3 ·
DERIVED 2.

**Stale current-facing claims (repaired here):**

| Severity | Where | Finding |
|---|---|---|
| BLOCKER | `README.md` | "Next engineering work … none is implemented yet" listed MICRO-001, PR-002, PR-003, TASK-015 — all on `main` |
| BLOCKER | `docs/PROJECT-STATUS.md` | `next_task: PROGRAM-001 … founder merge decision` after PROGRAM-001 and six further merges; AGENTS.md / CLAUDE.md route agents there |
| MATERIAL | `PROJECT-STATUS.md` | two different "as of" dates; chain ended at FE-002; "later commits change no code" while `main` carries builder-verified code after IBB-001 |
| MATERIAL | `06-ROADMAP.md`, `IMPLEMENTATION-CONVERGENCE.md` | P-0, HM-1, BP-1, BP-2/BP-7 absent; convergence intro "as of TASK-000, candidate" |
| MATERIAL | `PRODUCTION-READINESS.md` | header "PR-001 is not accepted"; PR-002 / PR-003 "candidate" |
| MATERIAL | `docs/runbooks/dr-database-recovery.md` | `alembic downgrade -1` contradicts the accepted rollback policy (D-84, RELEASE-AND-MIGRATION) while linked as current |
| MATERIAL | BP-1, BP-2/BP-7, TASK-015 S1/S2+3/S4a/S4b/S5/Phase A, MICRO-001, FE-001, FE-002, GROWTH-001 | "not merged" / "candidate" after merge |
| MATERIAL | FE-003 §10.1 / §13 | no prerequisite status; "Next: the P-0 handoff" after P-0 merged |
| MATERIAL | `CLAUDE.md` | reference oracle branch `reference/ts-drizzle-schema-v1` is not on `origin` |
| NONBLOCKING | DECISIONS D-76/78/79/80/82; TASK-000…014 headers; AUDIT-HISTORY as-of; 00 "files at this level carry a banner" | stale status words / missing banners |
| NONBLOCKING (found in Phase B verification) | DECISIONS D-99/D-100, IMPLEMENTATION-CONVERGENCE | short SHA `c32ac63a` does not resolve; the PROGRAM-001 merge is `c32ac63f…` — corrected |
| NONBLOCKING (found in Phase B verification, not changed) | DEVLOG 2026-10-01 entry | link anchor `PR-002-release-migration-compatibility.md#evidence` does not exist; earlier DEVLOG entries are not edited |

**Knowledge gaps (class B — binding semantics outside the repository):**
full original Constitution v2, Business Logic and System Architecture v1.1
(01/02/03 are incomplete derived representations); the founder-decision
precedence without a required written form; the DESIGN-001C `.dc.html` as the
source of concrete 1C visual values (blocks only a future FE-VIS-001
contract). External GPT review texts, the PROGRAM-001 master prompt and the
2026-10-05 founder resolutions are class A (semantics captured in D-102…D-105,
04a §24, the FE-003 contract and the DESIGN-001C handoff).

**Research / IP:** no research family existed; canon 07 §5 named a standing
commercial benchmark set; three dated benchmark reviews named commercial
platforms; historical strategy/business documents contain named comparisons.

**Identifiers:** families used without a definition (PROGRAM, DESIGN, GROWTH,
FE, FE-VIS, BP, BB, BG, OD, CTX, P-0, HM-1, MICRO-002) and known collisions
(G-n vs Gn, F6, task-local D-1…D-9, repair R vs R0–R3, P0 vs P-0, Phase 1A vs
Phase A/B/C).

## 3. Founder/GPT adjudication of Phase A (applied)

1. D-106 approved (repository system of record + research governance).
2. D-107 approved (provenance index for P-0 and HM-1; no new semantics).
3. 05 §14 appended; 05 §7 extended (no renumbering).
4. 00: founder precedence stays #1, clarified as binding at once and durable
   once represented under 05 §14; `docs/research/**` registered as
   NON-NORMATIVE EVIDENCE; the 01/02/03 source-status truth preserved.
5. 07 §5 named-benchmark doctrine superseded by an independent market
   evidence doctrine (canonical change approved).
6. Research family charter only; **MARKET-001 deferred** to a separate task.
7. PROJECT-STATUS is the single semantic owner of volatile status and does
   not embed its own commit SHA.
8. D-88 milestone stays undefined here — **CANONICAL DECISION REQUIRED**; the
   already deferred scope may be listed.
9. Historical documents get banners; editable benchmark files are sanitised
   mechanically where meaning survives; anything else is reported for review.
10. Baseline for Phase B = the BP-12 merge `a7756e1`; next engineering task
    after TASK-016 = BP-10 (not started).

## 4. Policies introduced

| Policy | Where it lives |
|---|---|
| Repository system of record | [05 §14](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md), D-106, [00](../canonical/00-AUTHORITY.md) |
| Merge flow ends with current-index reconciliation | [05 §7](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md) |
| Independent market evidence doctrine | [07 §5](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md) |
| Research family (non-normative), sources, independent synthesis | [docs/research/README.md](../research/README.md) |
| History preservation (keep / banner / disposition / never rewrite evidence) | §6 below; [TRACEABILITY](../engineering/TRACEABILITY.md) |
| Self-reference rule (a file cannot name its own commit) | [TRACEABILITY](../engineering/TRACEABILITY.md#self-reference-a-file-cannot-name-its-own-commit) |
| Volatile status owner | [PROJECT-STATUS](../PROJECT-STATUS.md) |

## 5. Current-state model

| Concept | Value | Owner |
|---|---|---|
| Last formal backend baseline | IBB-001, `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98`, ACCEPTED (CONV-001A), tag `backend-baseline-001`. No IBB-002 | [IBB-001](../baselines/IBB-001.md) |
| Latest code-bearing `main` state | `a7756e16c5ae2888776bf02a022b44b0221c0f7a` (BP-12 merge, main CI `37417946174` success) — IBB-001 plus builder-verified increments, none independently accepted; PR-002, PR-003 and TASK-015 S1–S4b are recorded as MILESTONE AUDIT DEFERRED (D-88) | PROJECT-STATUS |
| Repository HEAD | resolved from Git (`origin/main`); never embedded in a file that the same commit changes | Git |
| Next engineering task | BP-10 — NOT STARTED | PROJECT-STATUS |
| Authorisation | FE-003 implementation NO · FE-VIS-001 implementation NO | PROJECT-STATUS, FE-003 contract, DESIGN-001C handoff |
| Production | NOT READY · NOT DEPLOYED | PROJECT-STATUS, PRODUCTION-READINESS |

Provenance model (BP-12 as the worked example): implementation commit
`434c0956022d10f7bdaa4f1391674d490521561c`; independently reviewed candidate
`0d45583a14abbf5d4ce5eced0a5c270382aa44b5`; CI `37413458869` bound to that
candidate; merge `a7756e16c5ae2888776bf02a022b44b0221c0f7a` = final
integration identity; formal baseline unchanged (IBB-001).

## 6. History-preservation rules applied

| Kind | Rule |
|---|---|
| Correctly pinned history (baselines, input baselines in contracts and handoffs, "as of" sections) | keep |
| Immutable evidence (`docs/reviews/*-audit.md`, mutation reports, verdict records, 2026-07 review reports) | keep byte-for-byte |
| A statement that was true when written (DEVLOG entries, convergence history) | keep |
| Current-facing stale statement | update |
| Task document still saying "not merged" | add a dated **Disposition** row/line; the original narrative stays |
| Historical document without a banner | add a one-line banner; body unchanged |
| Editable benchmark file naming commercial platforms | mechanical sanitisation with a banner saying so; the original stays recoverable from Git history |

## 7. File allowlist

**Create:** this file · `docs/engineering/HANDOFF-INDEX.md` ·
`docs/research/README.md`.

**Modify:** `README.md` · `AGENTS.md` · `CLAUDE.md` ·
`docs/PROJECT-STATUS.md` · `docs/canonical/00-AUTHORITY.md` ·
`docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md` ·
`docs/canonical/06-ROADMAP.md` · `docs/canonical/07-PRODUCT-GROWTH-DOCTRINE.md` ·
`docs/canonical/IMPLEMENTATION-CONVERGENCE.md` · `docs/DECISIONS.md` ·
`docs/engineering/TRACEABILITY.md` · `docs/reviews/AUDIT-HISTORY.md` ·
`docs/DEVLOG.md` · `docs/production/PRODUCTION-READINESS.md` ·
`docs/production/INCIDENT-RUNBOOK.md` · `docs/runbooks/dr-database-recovery.md` ·
task contracts in `docs/tasks/` (disposition only) · `docs/frontend/FE-001-foundation.md` ·
`docs/frontend/FE-002-seeker-search-detail.md` ·
`docs/growth/GROWTH-001-marketplace-growth-foundation.md` · historical files
(banner only): `docs/strategy/01…07`, `docs/business/01…07`, eleven
booking-era build records in `docs/design/`, `docs/diagrams/bounded-contexts.md`,
`docs/BUILD_HISTORY.md` · benchmark reviews (sanitised):
`docs/reviews/2026-09-25-task010-location-benchmark.md`,
`docs/reviews/2026-09-27-task012-freshness-benchmark.md`,
`docs/reviews/2026-09-28-task013-discovery-benchmark.md`.

**Forbidden:** `backend/**`, runtime `frontend/**`, `ops/**`, `.github/**`,
migrations, dependencies, generated API artifacts (`docs/api/openapi.json`,
AsyncAPI), `backend/app/release.json`, Makefiles, `.claude/**`,
`docs/reviews/*-audit.md`, mutation and verdict evidence, `docs/baselines/**`,
canonical 04 and 04a, the substance of 01/02/03,
`docs/design/DESIGN-001C-HANDOFF.md`, earlier DEVLOG entries, the historical
body of IMPLEMENTATION-CONVERGENCE.

## 8. Acceptance criteria

1. Every changed path is on the allowlist; no runtime, generated or evidence
   file changed (`git diff --stat` against the baseline).
2. README, AGENTS.md and CLAUDE.md point to PROJECT-STATUS for volatile state
   and contain no stale "next work".
3. PROJECT-STATUS separates last formal baseline, latest code-bearing `main`
   state and repository HEAD; contains no self-referential SHA; every SHA and
   CI id in it is verified against Git / GitHub.
4. D-106 and D-107 are the next free decision ids; D-107 adds no semantics.
5. 05 §14 exists; §1–§13 keep their numbers; §7 ends with index
   reconciliation.
6. 00 keeps the founder at #1; research is outside the ladder; 01/02/03 stay
   marked incomplete; nothing is reconstructed.
7. 07 names no commercial platform and forbids imitation as a rationale.
8. `docs/research/README.md` is non-normative, has the evidence classes, the
   citation fields, HYPOTHESIS labelling, the decision path and the
   independent-synthesis rules; no MARKET-001 content exists.
9. TRACEABILITY defines every used family or flags it
   `IDENTIFIER DEFINITION REQUIRED`; P0 ≠ P-0; Phase 1A ≠ Phase A/B/C; the
   self-reference rule is stated.
10. No named commercial competing platform or competitor domain remains in
    current editable product doctrine, active research, new governance or
    current task reasoning; exceptions are counted and categorised.
11. Immutable evidence is byte-identical to the baseline.
12. `PRODUCTION READY: NO`, `DEPLOYMENT: NO` everywhere they are stated.
13. Relative links in changed files resolve; front matter parses.
14. Branch CI green.

## 9. Phase C

Two independent read-only reviewers on the frozen candidate, neither seeing
the other's report until both are complete:

* **C1 governance / chronology / traceability:** current-state accuracy, Git
  chronology, baseline vs `main` separation, PROJECT-STATUS self-reference, D
  numbering, authority hierarchy, system-of-record semantics, knowledge-gap
  preservation, identifiers, historical provenance, production truth,
  unauthorised roadmap change, task/commit/baseline/release/deployment
  conflation.
* **C2 IP / research / history preservation:** remaining commercial names or
  domains where prohibited, branded terminology introduced, research as
  authority, unsupported originality/IP claims, citation policy loopholes,
  immutable evidence modified, history silently rewritten, sanitised files
  claiming original wording, technical dependencies anonymised, 07 still
  permitting imitation, MARKET-001 leakage.

Findings are BLOCKER / MATERIAL / NONBLOCKING / NONE; the builder adjudicates
each and fixes only in-scope BLOCKER / MATERIAL. `MERGE AUTHORIZED: NO` until
founder/GPT external review.

## 10. Recorded, not resolved here

| Item | Status |
|---|---|
| 01/02/03 originals | KNOWLEDGE GAP — founder supplies originals or declares the repository versions complete |
| D-88 milestone (trigger, scope, threshold, IBB-002) | **CANONICAL DECISION REQUIRED** |
| DESIGN-001C `.dc.html` visual values (U-1) | KNOWLEDGE GAP for a future FE-VIS-001 contract |
| External review texts (GPT-5.6 Sol verdicts) not archived | audit-trail gap; semantics captured |
| Historical strategy/business/charter/product-model documents naming commercial platforms (`docs/strategy/01, 02, 05, 07, 08`, `docs/business/00, 01, 02, 04, 06, 07`, `docs/PROJECT_CHARTER.md`, `docs/PRODUCT_MODEL.md`) | **SANITISATION REQUIRES FOUNDER/GPT REVIEW** (names are woven into superseded reasoning, distribution-channel plans and data-vendor evaluation; banner-marked, bodies unchanged) |
| Pre-canon decision records D-42 (third-party terms cited as the legal basis for the no-scraping rule; data-vendor evaluation) and D-44 (a fraud pattern described by platform type) | kept as recorded decisions; **FOUNDER/GPT REVIEW** if their wording should be neutralised |
| `frontend/design-system/index.html` shows a proprietary programme name as a demo badge; backend comments name an amenity-vocabulary vendor | outside the allowlist — separate task |
| `backend/app/release.json` release label names a task (`TASK-015 Slice 4b`) | outside the allowlist — separate task (baseline ≠ release ≠ task) |
| `reference/ts-drizzle-schema-v1` exists only in the founder's local clone | founder decision whether to publish |
| `.claude/skills/micro-cycle` points at historical `PROJECT_STATE.md` / `BUILD_HISTORY.md` | outside the allowlist — separate task |
| MARKET-001 | separate future research task |
