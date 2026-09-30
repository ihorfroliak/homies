---
id: TRACEABILITY
name: Traceability convention
type: engineering_convention
status: accepted
adopted_at: 2026-09-30
adopted_by: BASELINE-001
---

# Traceability convention

How humans and AI agents name important Homies project states, so a sentence
tells a person **what** a thing is and tells tooling **exactly which** immutable
state is meant. This page is an index and a convention; it holds no business
rules. Authority is [00-AUTHORITY](../canonical/00-AUTHORITY.md).

## The three identities

Every important state carries up to three identities. They are different
things and are never substituted for one another.

| Identity | Example | Tells you | Stable? |
|---|---|---|---|
| **Human semantic name** | Integrated Backend Baseline 001 | what it is, for navigation and explanation | yes |
| **Stable engineering ID** | `IBB-001` | a short durable handle for docs, tickets and agent context | yes, never reused |
| **Git identity** | `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` (full) · `5abfd7bc` (short) | exactly which repository state | immutable |

**Rule.** Full SHA in formal provenance (baseline records, acceptance markers,
audit scopes, handoffs); short SHA in ordinary engineering prose where the
surrounding text already names the thing; human semantic name for navigation
and explanation. Preferred form for an important milestone:

```text
Integrated Backend Baseline 001 (IBB-001),
Git SHA 5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98
```

Do not write a paragraph whose only identifier for an important milestone is a
short SHA. Do not write "the current one", "the latest thing", "the previous
version", "the accepted commit", "that repair" or "this branch" without an
explicit identifier nearby.

## Kinds of identifier

| Kind | Form | Example | Meaning |
|---|---|---|---|
| Task | `TASK-NNN` | `TASK-014` | a unit of product work with a contract in [docs/tasks](../tasks/) |
| Repair | `<ID>R`, `<ID>R2` | `TASK-014R`, `PR-001R2` | a targeted repair of findings on that task |
| Audit | `<ID>A`, `<ID>RA`, `<ID>RA2` | `TASK-014A`, `TASK-014RA` | an independent audit / narrow re-audit of an exact SHA |
| Infrastructure track | `PR-NNN` | `PR-001` | production-readiness engineering (runtime, CI, release) |
| Convergence | `CONV-NNN` | `CONV-001` | an integration of separately accepted lines |
| Micro cleanup | `MICRO-NNN` | `MICRO-001` | an R0/R1 batch of small documentation/test/evidence fixes |
| Governance | `BASELINE-NNN` | `BASELINE-001` | recording and publishing an accepted baseline |
| Backend baseline | `IBB-NNN` | `IBB-001` | an accepted integrated backend state; successors get new numbers |
| Foundation baseline | "Foundation Baseline NNN" | Foundation Baseline 002 | the earlier accepted C1–C8 foundation states (before IBB) |
| Git tag | `backend-baseline-NNN` | `backend-baseline-001` | annotated, immutable, points at the baseline's exact code SHA |

## Status vocabulary

Use these words, in capitals, where a status is meant:

| Status | Meaning |
|---|---|
| `DRAFT` | being written; not proposed |
| `CANDIDATE` | proposed exact SHA, awaiting verification or acceptance |
| `IN_REVIEW` | under audit or review now |
| `ACCEPTED` | accepted at an exact SHA by the recorded verdict |
| `SUPERSEDED` | replaced by a named successor |
| `DEFERRED` | deliberately postponed, owner or trigger recorded |
| `BLOCKED` | cannot proceed until a named condition is met |
| `NOT_VERIFIED` | claimed but not independently evidenced |
| `NOT_READY` | production readiness not achieved |
| `NOT_DEPLOYED` | not running in any production environment |

Planning words: `NEXT` (the one serialized task to start after the current
one), `PLANNED` (ordered, not started), `DEFERRED` (postponed).

## Distinctions that must not be conflated

```text
baseline != release        IBB-001 is an accepted engineering state, not a shipped version
release  != deployment     a release is a versioned artifact; deployment runs it somewhere
commit   != feature        one feature spans many commits; one commit may touch several
task     != commit         a task ends at an accepted SHA reached through several commits
audit verdict != production readiness
                           "ACCEPTED" means accepted for continued development only
```

`IBB-001` is an engineering baseline. It is **not** a semantic-version release
(`v1.0.0` or any other). No production version number exists yet; one is
introduced only by a future release decision (see PR-002, release and
migration compatibility).

## Where each identity is recorded

| Record | Holds |
|---|---|
| [docs/baselines/](../baselines/) | one file per backend baseline, with YAML front matter (ID, SHA, parents, verdict) |
| [docs/reviews/](../reviews/) `*-audit.md` | independent audit reports, archived **byte-for-byte** (`.gitattributes`: `-text`); never edited |
| [docs/reviews/AUDIT-HISTORY.md](../reviews/AUDIT-HISTORY.md) | the human map over those reports |
| [docs/PROJECT-STATUS.md](../PROJECT-STATUS.md) | current baseline and next serialized work (derived index) |
| [docs/canonical/IMPLEMENTATION-CONVERGENCE.md](../canonical/IMPLEMENTATION-CONVERGENCE.md) | canonical status history, newest first |
| [docs/DEVLOG.md](../DEVLOG.md) | chronological narrative (Ukrainian) |
| Git annotated tags | `backend-baseline-NNN` → exact baseline code SHA; never moved or reused |

## Front matter for durable milestone documents

Compact YAML at the top of baseline and convention documents is an **index**
for tools and agents. It never restates or redefines canonical business
rules. Example: [IBB-001](../baselines/IBB-001.md).

## Precedence for agents

Repository state and canonical documents outrank chat memory and summaries.
When a remembered SHA or status disagrees with the repository, the repository
wins; record the discrepancy instead of acting on memory.
