# 00 — Authority

Which document wins when two disagree. Established 2026-09-24 by founder
instruction (TASK-000).

## Precedence

1. Founder explicit current decision
2. Homies Product & Engineering Constitution v2 — [01](01-CONSTITUTION-v2.md)
3. Canonical Business Logic — [02](02-BUSINESS-LOGIC.md)
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
  override anything above it. Files at this level carry a banner saying so.

## Known supersessions

| Where | Statement | Superseded by |
|---|---|---|
| 04 header, §1, §88–§90 | Drizzle ORM, node-postgres, Fastify, PostgreSQL 18 / PostGIS 3.6 as the implementation | 03 §2: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL + PostGIS. **The domain in 04 is unchanged; only the technology is.** |
| 04 header | "Target: Codex" | 05: Claude Code is primary builder; Codex is independent auditor |
| `docs/PROJECT_CHARTER.md`, `docs/strategy/*`, `docs/business/*`, `docs/PRODUCT_MODEL.md`, `docs/RELEASE_PLAN.md`, `RELEASE.md` | Managed hospitality / "give us the keys" / operator revenue loop as the current strategy; commission-bearing short and monthly stays as Phase 1 | 01, 02: long-term marketplace first; MONTHLY is Phase 2, SHORT_STAY Phase 3 |
| `docs/DECISIONS.md` product entries before 2026-09-24 (incl. D-07, D-44 wording) | Product sequencing and scope | 02. Engineering decisions in that log (money, ledger, append-only, DB roles, CI) remain in force unless contradicted by 03 |

## Source status of levels 2–4

The founder's Constitution v2, Business Logic and System Architecture v1.1 were
authored outside this repository. Files 01–03 record **only** what the founder
stated in the TASK-000 instruction of 2026-09-24; they do not invent missing
text. Where a full founder/ChatGPT-authored text exists, it should be committed
over the corresponding file, with this table updated.

| File | Content source | Complete? |
|---|---|---|
| 01 | Founder instruction 2026-09-24 | **No** — full Constitution v2 text not yet committed |
| 02 | Founder instruction 2026-09-24 | **No** — derived summary |
| 03 | Founder instruction 2026-09-24 | **No** — derived summary |
| 04 | Founder-supplied Domain Schema v1, byte-for-byte, SHA-256 `fd9c1fe707e84cd4c5e15f06127f4f4fbd64a1fad126e3c3153f8c744a0eb990` | Yes (spec text) |
| 04a | Founder instruction 2026-09-24 §20–§21 | Yes, for what it covers |
| 05 | Founder instruction 2026-09-24 | Yes |
