---
id: TRACEABILITY
name: Traceability convention
type: engineering_convention
status: accepted
adopted_at: 2026-09-30
adopted_by: BASELINE-001
amended_at: 2026-10-06
amended_by: TASK-016 (D-106)
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
| Program | `PROGRAM-NNN` | `PROGRAM-001` | a founder-approved bundle of several workstreams delivered on one program branch and merged as one unit (PROGRAM-001 → `main` at `c32ac63`) |
| Product / UI design | `DESIGN-NNN` (+ letter for a successor round) | `DESIGN-001`, `DESIGN-001B`, `DESIGN-001C` | a product/interface design deliverable; the family is registered in [00](../canonical/00-AUTHORITY.md) (`docs/product/`); letters mark later rounds of the same design line |
| Growth / measurement | `GROWTH-NNN` | `GROWTH-001` | growth and measurement foundation work (`docs/growth/`) |
| Frontend | `FE-NNN` | `FE-001`, `FE-003` | a public-web frontend slice or contract (`docs/frontend/`, `docs/tasks/FE-003…`) |
| Frontend visual | `FE-VIS-NNN` | `FE-VIS-001` | the visual/token rollout separated from functional frontend work (D-104 OD-5); not authorised |
| Context infrastructure | `CTX-NNN` | `CTX-001` | agent context-survival tooling (`.claude/`, DEVLOG 2026-10-01); no product effect |
| Decision | `D-NN` / `D-NNN` | `D-56`, `D-106` | an entry in [DECISIONS](../DECISIONS.md); global, sequential, never reused |
| Booking-era build record | e.g. `MC-01`, `FIN-01`, `BK-01`, `UI-01`, `D4`…`D9` | `UI-01` | historical (2026-07/08) build identifiers in [BUILD_HISTORY](../BUILD_HISTORY.md) and `docs/design/`; not reused |

### Scoped identifiers (meaning only inside their owner)

These are defined by one owner document or decision and mean nothing outside
it. Cite them with the owner ("FE-003 BP-10", "D-104 OD-5").

| Identifier | Owner | Meaning |
|---|---|---|
| `BP-n` | [FE-003 contract §10.1](../tasks/FE-003-save-conversation-viewing-DRAFT.md) | backend prerequisite of FE-003; each is its own bounded task (`docs/tasks/BP-…`) |
| `BB-n` | FE-003 contract §10.2 | beta blocker: must be closed before the named slice reaches external users |
| `BG-n` | [FE-001 §"Backend gaps"](../frontend/FE-001-foundation.md) | backend gap found while building the web foundation |
| `OD-n` | FE-003 contract (first "Open decisions", now §5.1 "Founder decisions") | an FE-003 decision point, decided by D-104 (OD-1…OD-6) and D-105 (OD-7, OD-8) |
| `CF-n` | FE-003 contract §2 | contract review finding |
| `DEBT-n` | FE-003 contract (CF-7), D-104 | recorded debt of the FE-003 line |
| `G-n` (hyphen) | [GROWTH-001](../growth/GROWTH-001-marketplace-growth-foundation.md), D-98 | founder growth decision G-1…G-15 |
| `Gn` (no hyphen) | [DESIGN-001 §9](../product/DESIGN-001-product-ui-foundation.md) | API gap G1…G12 needed by the UI |
| `P-0` | [DESIGN-001C handoff](../design/DESIGN-001C-HANDOFF.md), FE-003 §0.2, D-107 | the repository-readable DESIGN-001C implementation handoff — the prerequisite FE-003 named before implementation. A single scoped identifier; there is **no** general `P-N` family |
| `HM-1` (rules `HM-1.1`…`HM-1.9`) | DESIGN-001C handoff §31, D-107 | the founder's Home-map amendment (2026-10-05), owned by FE-VIS-001. A single scoped identifier; there is **no** general `HM-N` family |
| `C-n`, `U-n`, `I-n` | DESIGN-001C handoff §30, §28, §3 | conflict resolution, visual-detail item, non-negotiable invariant |
| `LD-n`, `L9`, `L11` | DESIGN-001 / TASK-015 | legal-review copy items |
| `S1`…`S5`, `S4a`, `S4b` | TASK-015 | slices of TASK-015 (there is no S6) |
| `D-1`…`D-9` | TASK-015 Phase A | task-local founder decision points, recorded globally as **D-92** |
| `F-01`…, `N-01`…, `GEO-0n`, `F13A-0n`, `RA-n`, `CV-Nn`, `E-Rn`, `M-nn` | the audit or task that raised them | findings, review probes and mutants; local to their report |
| `DQ-n`, `QAL`, `SHO` | `docs/growth/` | data-quality rule, qualified active listing, successful housing outcome |

### Identifiers without an authoritative definition

| Identifier | Where used | Status |
|---|---|---|
| `MICRO-002` | DEVLOG 2026-10-01 and several task notes ("recommendation, outside the repository": JWT leeway / clock-step flake) | **IDENTIFIER DEFINITION REQUIRED** — no task contract exists; do not treat as a task until one is written |

### Known collisions — read with the owner, avoid in new text

| Pattern | Example | Rule for new documentation |
|---|---|---|
| hyphenated founder/product id vs unhyphenated gap label | `G-4` (0 PLN listing policy, D-98) vs `G4` (parking API gap, DESIGN-001; used so in D-102) | write "growth decision G-4" or "API gap G4"; prefer a distinct prefix for new gap lists |
| `F6` reused | PR-001R finding F6 (notification backlog alert) vs `F6` re-contact viewing bar (D-102, 04a §24) | always qualify: "PR-001R F6", "D-102 F6" |
| task-local `D-1`…`D-9` vs global `D-NN` | TASK-015 D-1…D-9 (= D-92) vs D-01…D-09 (2026-07) | global decisions only as `D-NN`/`D-NNN`; new task-local decision points use another prefix (e.g. `OD-n`) |
| repair suffix `R` vs risk class `R0`–`R3` | `TASK-014R`, `PR-001R2` vs `R2` | a suffix is attached to an id; a risk class stands alone ("risk R2") |
| severity `P0` vs `P-0` | `P0 CRITICAL` vs the P-0 handoff | see the distinctions below |
| historical `D1`…`D4`, `D4`…`D9` | `docs/strategy/00-DECISIONS.md`, booking-era build steps | historical only; never reused |

Historical identifiers are not rewritten; new documentation avoids ambiguous
reuse.

## Classifications

| Class | Values | Meaning | Defined in |
|---|---|---|---|
| Risk / verification class | `R0` · `R1` · `R2` · `R3` | how much verification a task needs (docs → ordinary → migrations/authorisation/concurrency/privacy → payments/production/deployment) | [AUDIT-HISTORY](../reviews/AUDIT-HISTORY.md#governance-change-after-ibb-001--risk-based-verification); D-88 defers R2 independent review into a milestone audit |
| Audit finding severity | `P0 CRITICAL` · `P1 HIGH` · `P2 MEDIUM` · `P3 LOW` · `NOTE` | severity of an independent-audit finding | [05 §10](../canonical/05-DEVELOPMENT-GOVERNANCE-v1.md), AUDIT-HISTORY |
| Review finding class | `BLOCKER` · `MATERIAL` · `NONBLOCKING` · `NONE` | founder/GPT review and hostile-review classes (BP tasks, TASK-016): blocks acceptance / must be fixed in scope / recorded only / nothing found | task contracts (e.g. BP-12 §6, TASK-016 §9) |

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
| `BUILDER VERIFIED · MILESTONE AUDIT DEFERRED` | merged to `main` on builder evidence and green CI; independent review deferred into the milestone audit (D-88); **not** accepted in the baseline sense |

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
merged to main != accepted baseline
                           a builder-verified merge after IBB-001 is not a new baseline
P0 severity != P-0         P0 is an audit-finding severity; P-0 is the scoped
                           DESIGN-001C handoff identifier
Phase 1A product phase != Phase A/B/C task execution phases
                           06/02 phases (1A, 1B, 1.5, 2, 3) are product scope;
                           a task's Phase A/B/C is audit → implementation → review
durability != authority    everything committed is durable; 00-AUTHORITY decides
                           which document wins
```

## Provenance identities of a change

A reviewed change has up to five Git-related identities. Name the one meant.

| # | Identity | Example (BP-12) | Recorded in |
|---|---|---|---|
| 1 | implementation SHA | `434c0956022d10f7bdaa4f1391674d490521561c` | task contract, report |
| 2 | reviewed candidate SHA (the frozen branch HEAD that was reviewed) | `0d45583a14abbf5d4ce5eced0a5c270382aa44b5` | report, review verdict |
| 3 | CI run bound to the candidate SHA | `37413458869` | report |
| 4 | merge SHA (final integration identity on `main`) | `a7756e16c5ae2888776bf02a022b44b0221c0f7a` | Git; later status and provenance records |
| 5 | formal baseline SHA | IBB-001 `5abfd7bc6f6b5aa085c8e439ba8fe67c458d1f98` (unchanged by BP-12) | [docs/baselines/](../baselines/), tag |

## Self-reference: a file cannot name its own commit

A committed file cannot reliably contain the SHA of the commit that creates
that file content: writing the SHA into the file changes the commit and
therefore the SHA. Consequently:

* a task document does **not** carry its own candidate HEAD; the candidate
  SHA, its CI run and the merge SHA live in Git, the builder's report and the
  reviewer's verdict;
* no follow-up commit is made merely so a document can contain its own
  candidate HEAD;
* [PROJECT-STATUS](../PROJECT-STATUS.md) does not embed the SHA of the commit
  or merge that contains it; the exact current repository HEAD is read from
  Git (`git rev-parse origin/main`);
* a later record (a status update, an acceptance or baseline record, an audit
  report) may name earlier immutable candidate, merge or baseline SHAs.

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
| [docs/PROJECT-STATUS.md](../PROJECT-STATUS.md) | the single semantic owner of volatile status: last formal baseline, latest code-bearing `main` state, candidates, next work, authorisation flags, production state (D-106) |
| [docs/DECISIONS.md](../DECISIONS.md) | global decisions `D-NN`/`D-NNN`, newest first |
| [docs/engineering/HANDOFF-INDEX.md](HANDOFF-INDEX.md) | reading path for a new engineer (navigation only) |
| [docs/research/](../research/README.md) | non-normative research (D-106) |
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
