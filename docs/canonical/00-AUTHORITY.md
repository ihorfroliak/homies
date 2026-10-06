# 00 — Authority

Which document wins when two disagree. Established 2026-09-24 by founder
instruction (TASK-000).

## Precedence

1. Founder explicit current decision — binding for direction immediately;
   it becomes durable project knowledge once represented in the repository
   under [05 §14](05-DEVELOPMENT-GOVERNANCE-v1.md) (D-106)
2. Homies Product & Engineering Constitution v2 — [01](01-CONSTITUTION-v2.md)
3. Canonical Business Logic — [02](02-BUSINESS-LOGIC.md), with the Product &
   Growth Doctrine — [07](07-PRODUCT-GROWTH-DOCTRINE.md) (added 2026-09-25,
   TASK-010: how material product decisions are judged; refines, never
   contradicts, 02)
4. System Architecture v1.1 — [03](03-SYSTEM-ARCHITECTURE-v1.1.md)
5. Domain Schema v1 + approved clarifications — [04](04-DOMAIN-SCHEMA-v1.md), [04a](04a-DOMAIN-SCHEMA-v1-CLARIFICATIONS.md)
6. Development Governance — [05](05-DEVELOPMENT-GOVERNANCE-v1.md)
7. Approved Task Contract — [`docs/tasks/`](../tasks/)
8. ADRs — [`docs/adr/`](../adr/)
9. Existing implementation
10. Historical/legacy documentation

When implementation conflicts with a higher source, the higher source wins
unless the founder explicitly changes it. A conflict that cannot be resolved
from these documents is recorded as **CANONICAL DECISION REQUIRED** (format in
[05 §8](05-DEVELOPMENT-GOVERNANCE-v1.md)) and taken to the founder; it is never
decided silently in code.

## What each level may and may not do

* A lower source may **refine** a higher one (add detail it leaves open).
  It may not **contradict** it.
* Implementation (9) is evidence of what exists, not of what is right. A
  committed commit is a candidate until accepted under 05.
* Historical documentation (10) is kept for context and must not be used to
  override anything above it. Files at this level carry a banner saying so
  (banners completed for the files known on 2026-10-06 by TASK-016; a
  historical file found without one is still level 10).

## Outside the ladder

| Material | Status | May | May not |
|---|---|---|---|
| [`docs/research/**`](../research/README.md) | **NON-NORMATIVE EVIDENCE** (D-106) | inform a hypothesis or a founder/product decision | override, refine or stand in for canon, a D-decision or an approved Task Contract; authorise implementation |
| Conversations, agent memory, design-tool state, external artifacts | inputs, not durable authority ([05 §14](05-DEVELOPMENT-GOVERNANCE-v1.md)) | direct work through a founder decision | bind implementation until represented in the repository |

Research reaches implementation only as: research / evidence → Homies
hypothesis → founder/product decision → D-xxx / canonical update / approved
Task Contract → implementation.

## Known supersessions

| Where | Statement | Superseded by |
|---|---|---|
| 04 header, §1, §88–§90 | Drizzle ORM, node-postgres, Fastify, PostgreSQL 18 / PostGIS 3.6 as the implementation | 03 §2: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL + PostGIS. **The domain in 04 is unchanged; only the technology is.** |
| 04 header | "Target: Codex" | 05: Claude Code is primary builder; Codex is independent auditor |
| `docs/PROJECT_CHARTER.md`, `docs/strategy/*`, `docs/business/*`, `docs/PRODUCT_MODEL.md`, `docs/RELEASE_PLAN.md`, `RELEASE.md` | Managed hospitality / "give us the keys" / operator revenue loop as the current strategy; commission-bearing short and monthly stays as Phase 1 | 01, 02: long-term marketplace first; MONTHLY is Phase 2, SHORT_STAY Phase 3 |
| `docs/DECISIONS.md` product entries before 2026-09-24 (incl. D-07, D-44 wording) | Product sequencing and scope | 02. Engineering decisions in that log (money, ledger, append-only, DB roles, CI) remain in force unless contradicted by 03 |

## Registered document families (PROGRAM-001, 2026-10-03)

Founder-approved for the PROGRAM-001 candidate. These families **refine** 02,
03 and 07 for product, interface and growth work; they sit at level 7 (the
specification of an approved task) and never contradict a higher level. A
conflict found while writing them is recorded as CANONICAL DECISION REQUIRED,
not resolved in the family. They are current since PROGRAM-001 was merged to
`main` with founder approval (`c32ac63`, 2026-10-04).

| Family | Path | Owns | Entry document |
|---|---|---|---|
| Product & interface | [`docs/product/`](../product/) | information architecture, journeys, UI states, Design System v1, copy rules, URL design | [DESIGN-001](../product/DESIGN-001-product-ui-foundation.md) |
| Frontend engineering | [`docs/frontend/`](../frontend/) | the public web app: BFF/session, security headers, API client, i18n, measurement seams, slices | [FE-001](../frontend/FE-001-foundation.md), [FE-002](../frontend/FE-002-seeker-search-detail.md) |
| Growth & measurement | [`docs/growth/`](../growth/) | metric, event, attribution, experiment, data-quality, unit-economics and consent definitions | [GROWTH-001](../growth/GROWTH-001-marketplace-growth-foundation.md) |

Superseded by these families (historical, banner-marked):
`docs/design/PRODUCT_UX.md`, `docs/design/DESIGN_SYSTEM.md` (UI-01 drafts) and
`docs/design/ANALYTICS_EVENTS.md` (booking era).

## Source status of levels 2–4

The founder's Constitution v2, Business Logic and System Architecture v1.1 were
authored outside this repository. Files 01–03 record **only** what the founder
stated in the TASK-000 instruction of 2026-09-24; they do not invent missing
text. Where a full founder/ChatGPT-authored text exists, it should be committed
over the corresponding file, with this table updated.

Under [05 §14](05-DEVELOPMENT-GOVERNANCE-v1.md) the "No" rows below are
recorded **knowledge gaps**: they stay open until the founder either supplies
the authoritative original or explicitly declares the repository version
complete. They are never filled from model memory, likely intent, adjacent
documents or the implementation. (TASK-016 did neither; status unchanged.)

| File | Content source | Complete? |
|---|---|---|
| 01 | Founder instruction 2026-09-24 | **No** — full Constitution v2 text not yet committed |
| 02 | Founder instruction 2026-09-24 | **No** — derived summary |
| 03 | Founder instruction 2026-09-24 | **No** — derived summary |
| 04 | Founder-supplied Domain Schema v1, byte-for-byte, SHA-256 `fd9c1fe707e84cd4c5e15f06127f4f4fbd64a1fad126e3c3153f8c744a0eb990` | Yes (spec text) |
| 04a | Founder instruction 2026-09-24 §20–§21; later founder decisions recorded as §22 (TASK-014), §23 (TASK-015 D-1…D-9) and §24 (PROGRAM-001 adjudication D-102 and FE-003 contract reviews D-104/D-105, with GPT-5.6 Sol) | Yes, for what it covers |
| 05 | Founder instruction 2026-09-24 | Yes |
| 07 | Founder instruction 2026-09-25 (TASK-010 Part A) | Yes, for what it covers |
