---
id: HANDOFF-INDEX
name: Homies handoff index
type: navigation_index
authority: none (navigation only; 00-AUTHORITY decides)
volatile_state: not held here — see docs/PROJECT-STATUS.md
created_by: TASK-016 (D-106)
---

# Handoff index — understanding Homies from the repository alone

For a new CTO, principal or senior engineer with the repository and its Git
history only — no chat transcripts, no agent memory, no design-tool session.
About 30–60 minutes. **This page is navigation, not authority** and holds no
current SHAs, task states or flags: those live in
[PROJECT-STATUS](../PROJECT-STATUS.md).

## Reading path

| # | Read | Time | You learn |
|---|---|---|---|
| 1 | [README](../../README.md) | 2 min | what Homies is, broad scope, NOT READY / NOT DEPLOYED |
| 2 | [00-AUTHORITY](../canonical/00-AUTHORITY.md) | 4 min | which document wins; what is outside the ladder (research, conversations); which canon texts are incomplete |
| 3 | [TRACEABILITY](TRACEABILITY.md) | 5 min | identifiers, status words, the five provenance identities, the self-reference rule, identifier collisions |
| 4 | [PROJECT-STATUS](../PROJECT-STATUS.md) | 4 min | last formal baseline vs latest code-bearing `main` state vs repository HEAD; next task; authorisation flags; everything merged since the baseline |
| 5 | [IBB-001](../baselines/IBB-001.md) | 2 min | what the last formal baseline is and how it was accepted |
| 6 | [AUDIT-HISTORY](../reviews/AUDIT-HISTORY.md) | 4 min | the audit model, risk classes R0–R3, the deferred milestone audit (D-88) |
| 7 | [02 — Business Logic](../canonical/02-BUSINESS-LOGIC.md) | 4 min | product phases and business rules |
| 8 | [07 — Product & Growth Doctrine](../canonical/07-PRODUCT-GROWTH-DOCTRINE.md) | 3 min | how product decisions are judged; independent market evidence |
| 9 | [03 — System Architecture](../canonical/03-SYSTEM-ARCHITECTURE-v1.1.md) | 3 min | stack and architectural boundaries |
| 10 | [04 — Domain Schema](../canonical/04-DOMAIN-SCHEMA-v1.md) + [04a — clarifications](../canonical/04a-DOMAIN-SCHEMA-v1-CLARIFICATIONS.md) | 5 min (skim) | the domain model; founder clarifications §20–§24 |
| 11 | [DESIGN-001](../product/DESIGN-001-product-ui-foundation.md), [FE-001](../frontend/FE-001-foundation.md), [FE-002](../frontend/FE-002-seeker-search-detail.md), [GROWTH-001](../growth/GROWTH-001-marketplace-growth-foundation.md) | 5 min | current product, web and measurement specifications |
| 12 | [06 — Roadmap](../canonical/06-ROADMAP.md) | 2 min | order of phases and beta prerequisites |
| 13 | [FE-003 contract](../tasks/FE-003-save-conversation-viewing-DRAFT.md) §0.2, §10, §13 and the `BP-…` task records in [docs/tasks](../tasks/) | 4 min | the active frontend contract, its backend prerequisites and beta blockers |
| 14 | [DESIGN-001C handoff](../design/DESIGN-001C-HANDOFF.md) §1, §26–§31 | 3 min | the binding design handoff (P-0) and the Home-map amendment (HM-1) |
| 15 | [PRODUCTION-READINESS](../production/PRODUCTION-READINESS.md) §1 | 3 min | what is and is not production-ready, with evidence |
| 16 | [05 — Development Governance](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md) | 3 min | roles, merge flow, CANONICAL DECISION REQUIRED, repository system of record (§14) |
| 17 | [Task template](../tasks/TASK-TEMPLATE.md) | 1 min | what a task contract contains |
| 18 | [DECISIONS](../DECISIONS.md) (newest rows first) | 3 min | how decisions are recorded (D-NNN) |
| 19 | [DEVLOG](../DEVLOG.md) — last entries | 2 min | recent chronology, in Ukrainian |
| 20 | `git log --first-parent --format='%h %ad %s' --date=short origin/main` | 2 min | the actual merge chronology on `main` |
| 21 | `git tag -n9 backend-baseline-001` | 1 min | the baseline tag and its acceptance message |

## The sixteen questions and where they are answered

| Question | Answer lives in |
|---|---|
| What is Homies? | README; 02; 07 §1, §4 |
| Current scope | 02 §1; 06; PROJECT-STATUS "Not now" |
| Authority hierarchy | 00-AUTHORITY |
| Product / business logic | 02; 07; 04a |
| System architecture | 03; ADRs in [docs/adr](../adr/) |
| Domain model | 04; 04a |
| Current implementation | IMPLEMENTATION-CONVERGENCE (newest sections first); the code (`backend/app/composition.py` → `create_phase1_app()`) |
| Recent chronology | PROJECT-STATUS "Integrated on `main` since IBB-001"; DEVLOG; `git log --first-parent` |
| Current `main` | Git (`origin/main`); PROJECT-STATUS for the latest code-bearing state |
| Last formal baseline | PROJECT-STATUS; IBB-001 record; tag |
| Production readiness | PRODUCTION-READINESS; PROJECT-STATUS flags |
| Open risks / debt | PRODUCTION-READINESS gaps; FE-003 §10.2 beta blockers; 06 beta prerequisites; AUDIT-HISTORY deferred scope; TASK-016 §10 |
| Next approved work | PROJECT-STATUS "Next work" |
| How tasks are executed | 05 §6–§7, §11; TASK-TEMPLATE; a recent task record (e.g. BP-12) |
| How decisions are recorded | DECISIONS; 05 §8 (CANONICAL DECISION REQUIRED); 04a for domain clarifications |
| How external knowledge becomes repository knowledge | 05 §14; D-106; [research family](../research/README.md) for market evidence |

## Rules of thumb

* **Durable ≠ authoritative.** Everything committed is durable; 00-AUTHORITY
  decides which document wins.
* **Merged ≠ accepted baseline.** Work merged after IBB-001 is builder
  verified, not independently accepted; items recorded as MILESTONE AUDIT
  DEFERRED wait for the D-88 review, whose scope is still undecided.
* **Status lives in one place.** Other documents link to PROJECT-STATUS;
  task records keep only their own immutable lifecycle facts.
* **Do not edit evidence.** `docs/reviews/*-audit.md`, mutation reports,
  verdict records and `docs/baselines/**` are immutable; historical
  documents carry a banner and are not current scope.
* **A missing source is a gap.** If something binding is not in the
  repository, record the gap; do not reconstruct it.
