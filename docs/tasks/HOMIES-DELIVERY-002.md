# HOMIES — FULL SOFTWARE DELIVERY PROGRAM

## CODEX ASTRA — EXECUTION DIRECTIVE

**Repository:** `ihorfroliak/homies`
**Date:** 2026-10-16
**Program:** HOMIES-DELIVERY-002
**Agent foundation:** AGENT-001 → AGENT-002
**Execution owner:** Codex Astra
**Objective:** Complete the remaining approved backend prerequisites, establish autonomous backlog orchestration, and deliver the FE-003 user journey as verified software.

---

# 0. PRIMARY MISSION

You are not being asked to conduct another broad architectural audit.

You are being asked to execute the remaining Homies development backlog.

Our previous development process became excessively audit-driven.

We spent too much time:

* reviewing previously reviewed implementations;
* revising prompts;
* repeating completed technical investigations;
* transferring context between agents;
* producing governance documents without corresponding product functionality;
* requiring redundant approvals for already authorized bounded implementation work.

This execution must correct that operating model.

**Primary objective: SHIP VERIFIED SOFTWARE.**

The target workflow is:

Approved Task Contract
→ Implementation
→ Focused Tests
→ Required Independent Review
→ CI
→ Draft PR
→ Founder Merge Decision
→ Next Deliverable

Do not re-plan work whose semantics have already been approved.

Do not manufacture additional approval checkpoints.

Do not reopen completed audits without new material evidence.

Do not replace implementation with recommendations.

Execute each authorized, unblocked phase.

When one phase reaches its legitimate authorization boundary, continue other authorized work that does not depend on crossing that boundary.

Use GitHub as the authoritative repository state.

Historical ChatGPT conversations are context, not current repository authority.

---

# 1. FOUNDER AUTHORIZATION AND GOVERNANCE

The founder authorizes the following bounded execution program:

1. Finalize the already reviewed BP-8 integration, subject to its exact identity and safety gates.
2. Implement AGENT-002.
3. Implement BP-11, including mitigation of public viewing-slots resource exhaustion.
4. Implement BP-9.
5. Implement BP-3.
6. Implement BP-4.
7. Implement FE-003 once its mandatory prerequisites are satisfied.
8. Prepare and, where permissions allow, establish appropriate protection for `main`.
9. Correct necessary project-status, decision and implementation records.
10. Produce tested feature branches and Draft PRs for all completed increments.

This authorization permits implementation of the listed bounded scopes.

It does not authorize arbitrary architecture changes or unrelated backlog work.

It does not authorize production deployment, production-data mutations, paid-provider activation, or FE-VIS-001.

**BP-8 integration:** The founder explicitly requests completion of PR #9. Treat sending this directive as authorization to merge that exact previously reviewed candidate after verifying the stated guards.

**Subsequent PRs:** No blanket merge authorization is granted for newly created BP-11, BP-9, BP-3, BP-4, AGENT-002 or FE-003 pull requests. Deliver those as Draft PRs and obtain the required founder decision before integration.

**FE-003:** The founder authorizes bounded implementation under the already approved FE-003 contract, conditional on its mandatory backend prerequisites. Record this new authorization durably under canonical governance before final acceptance. Do not treat the old `IMPLEMENTATION AUTHORIZED: NO` status as permission to ignore this new founder instruction; reconcile it explicitly.

FE-VIS-001 remains unauthorized.

All existing decisions retain authority unless this directive explicitly changes them.

Read the relevant portions of:

* `AGENTS.md`
* `CLAUDE.md`
* `docs/canonical/00-AUTHORITY.md`
* `docs/canonical/05-DEVELOPMENT-GOVERNANCE-v1.md`
* `docs/DECISIONS.md`
* `docs/PROJECT-STATUS.md`
* `docs/canonical/IMPLEMENTATION-CONVERGENCE.md`
* applicable task contracts
* AGENT-001 engineering documentation.

Read only the relevant canonical sections rather than loading the entire historical repository.

Preserve the accepted Product Constitution, Business Logic, Domain Schema, safety boundaries and founder decisions.

---

# 2. INITIAL REPOSITORY RECONCILIATION

Before executing any Git mutation:

Fetch the current remote state.

Determine:

* actual `origin/main` SHA and tree;
* open pull requests;
* merged pull requests;
* existing candidate branches;
* exact status of BP-8 PR #9;
* GitHub Actions results;
* current Alembic head;
* existing agent definitions;
* available Codex and Claude runtime capabilities;
* available repository administration permissions;
* current working-tree status.

Do not assume the historical state is still current.

Previously verified checkpoint:

```text
main:
64a9cebd763d74d2ea6fb718734fa486750e0c55

BP-8 PR:
#9

BP-8 candidate:
24a47e81cfd31948e4de642ff7c2cb2fbe5bf521

BP-8 tree:
b29e0ceac644c026ecaa3d3e5dd01cc625b27f27

BP-8 CI:
38548793363 — SUCCESS 6/6

BP-8 independent review:
PASS

Last formal backend baseline:
IBB-001
```

Treat these values as verification anchors, not instructions to reset newer valid work.

If tasks are already completed, verify their exact identities and skip them.

Do not duplicate branches or work.

Never overwrite unrelated user changes.

Never force-push or rewrite audited candidate history.

---

# 3. PHASE A — COMPLETE BP-8

## Goal

Integrate the already verified G-14 contact-reveal restriction.

PR #9 implements:

* restriction on new phone reveals;
* restriction on repeat phone reveals;
* neutral `409 RECONTACT_BLOCKED`;
* publication-generation awareness;
* PostgreSQL serialization with moderation changes;
* authorization revalidation following rollback;
* preservation of existing quotas and disclosure semantics.

The independent review already returned PASS.

Required candidate CI is green.

### Execution

Verify the exact candidate SHA and tree.

Verify PR mergeability.

Verify no substantive changes were introduced after the completed review.

Verify required CI results.

Do not initiate another general audit.

Do not rewrite the candidate.

Use the normal GitHub merge mechanism, preserving the reviewed implementation and commit ancestry.

Do not bypass existing branch protections.

If the exact candidate differs materially, or required checks fail, stop the merge and report the precise changed evidence.

Otherwise, merge PR #9 under the founder authorization in this directive.

Record:

* actual merge SHA;
* final main SHA;
* accepted candidate ancestry;
* merge tree;
* post-merge CI result;
* remaining debt.

Archive the independent BP-8 review into repository-readable records where required by §14 without modifying or retroactively re-identifying the audited candidate.

If a separate documentation-only PR is needed, keep it minimal.

Do not repeat BP-8 tests solely to reproduce previously verified evidence.

Proceed directly to the next authorized implementation phase.

---

# 4. PHASE B — IMPLEMENT AGENT-002

## Goal

Transform the existing AGENT-001 foundation from a review-oriented configuration into a delivery-oriented agent operating system.

Create exactly one additional primary role:

# IMPLEMENTATION ORCHESTRATOR

Do not create six more review agents.

Preserve the existing six specialist roles.

## 4.1 Core responsibilities

The Implementation Orchestrator must:

1. Read the current approved backlog.
2. Resolve the next authorized and unblocked task.
3. Read its approved Task Contract.
4. Identify the required baseline SHA.
5. Determine the risk classification.
6. Select exactly one primary writer for the bounded context.
7. Create or select the appropriate isolated worktree.
8. Dispatch the implementation task.
9. Select only relevant technical specialists.
10. Collect focused test evidence.
11. Collect required independent review evidence.
12. Collect CI results.
13. Prepare a Draft PR.
14. Persist an implementation checkpoint.
15. Update delivery status.
16. Select the next authorized and unblocked task.

Do not repeatedly ask for confirmation of an already approved implementation scope.

Do not silently expand task scope.

Do not automatically merge or deploy.

## 4.2 Cross-vendor integration

Integrate the operating model with:

**Claude Code**

Create a project-scoped orchestrator definition under:

`.claude/agents/implementation-orchestrator.md`

Use valid Claude Code agent metadata.

Preserve existing specialist agents.

**Codex**

Create the corresponding compatible definition under:

`.codex/agents/`

Update `.codex/config.toml` only where required.

Determine the exact manifest format supported by the installed Codex runtime.

Do not assume unsupported multi-agent APIs.

**ChatGPT**

Update the repository-readable interoperability contract.

ChatGPT remains responsible for:

* architecture;
* product decisions;
* contract refinement;
* founder-facing assessment;
* independent strategic synthesis.

ChatGPT is not a hidden background worker or automatically shared-memory agent.

**GitHub Copilot**

Update the existing Copilot instructions so Copilot follows the same Task Contract, ownership and review rules.

Do not grant Copilot independent authority to merge, deploy or redefine canonical product semantics.

## 4.3 Runtime reality

An agent definition is persistent configuration, not necessarily a continuously running process.

Do not claim continuous autonomous execution where no runtime scheduler exists.

Do not assume a Claude subagent can spawn additional subagents.

When a runtime cannot delegate recursively, the top-level Codex/Claude session must perform orchestration directly and invoke available specialists.

If Claude CLI integration is available and permitted, Claude may remain the primary code writer.

If unavailable, Codex Astra may act as the explicitly authorized writer for this program.

A writer must never certify its own mandatory independent audit.

Where Codex is the writer, use a genuinely separate read-only Codex review session or equivalent canon-compliant independent execution context.

Do not call an in-process self-review independent.

## 4.4 Automatic agent selection

Implement a small, explicit and testable dispatch policy.

Suggested mapping:

| Change type                           | Specialist        |
| ------------------------------------- | ----------------- |
| FastAPI / business logic              | backend-reviewer  |
| PostgreSQL / migrations / locking     | postgres-auditor  |
| Authorization / privacy / identity    | security-auditor  |
| React / Next.js / accessibility       | frontend-reviewer |
| Test methodology / regression quality | test-engineer     |
| CI / infrastructure / recovery        | devops-reviewer   |

Risk policy:

```text
R0 → 0 specialists
R1 → 0–1 specialists
R2 → 1–2 relevant specialists by default
R3 → required independent reviews and operational gates
```

Mandatory independent reviews remain additional requirements.

Do not spawn all specialists by default.

Use a deterministic lightweight task-to-specialist selection mechanism where practical.

The mechanism should be inspectable and testable rather than relying exclusively on vague natural-language descriptions.

Avoid introducing a heavy orchestration platform or distributed infrastructure merely to select agents.

## 4.5 Backlog execution

The orchestrator must distinguish:

```text
PLANNED
AUTHORIZED
READY
IN_PROGRESS
BUILDER_VERIFIED
REVIEW_REQUIRED
REVIEWED
CI_GREEN
DRAFT_PR_READY
MERGE_AUTHORIZED
INTEGRATED
BLOCKED
```

Do not confuse implementation completion with integration or production readiness.

Selection priority:

1. authorized;
2. prerequisites satisfied;
3. not already implemented;
4. no existing active writer;
5. highest-priority task in the approved dependency order.

Support sequential execution of the backlog.

Support dependency-aware stacked Draft PRs where an earlier task is complete but awaiting founder merge authorization.

Never silently include unrelated changes from one feature branch in another.

Preserve accurate base/head relationships.

## 4.6 Failure and recovery

On interrupted sessions:

Recover from:

* repository state;
* exact Git SHA;
* Task Contract;
* durable checkpoint;
* CI and review evidence.

Do not rely on private model memory.

The system must safely resume without:

* duplicating implementation;
* rewriting accepted commits;
* reopening completed audits;
* selecting a second writer;
* losing unresolved blockers.

## 4.7 Cache and context efficiency

Preserve AGENT-001's existing protections:

* no default full transcript copying;
* bounded opt-in transcript archives;
* no raw hook-event persistence;
* task-isolated checkpoints;
* no claim of shared Claude/OpenAI provider caches.

Audit the existing cache implementation only for material problems affecting delivery.

Do not redesign provider caching without measurements.

Collect available metrics:

* context-compaction overhead;
* checkpoint recovery success;
* duplicate context loading;
* agent calls per completed task;
* measured token consumption where exposed;
* total task cycle time.

Optimize repository context loading through small, stable, task-specific handoffs.

Do not indiscriminately clear caches.

## 4.8 Acceptance

AGENT-002 is complete when:

* its configuration loads in supported runtimes;
* deterministic routing tests pass;
* a task can be resumed from checkpoint;
* one-writer ownership is enforced by the process;
* the orchestrator can prepare a Draft PR;
* it cannot bypass merge authorization;
* mandatory independent-review gates remain intact;
* no material regression is introduced into AGENT-001.

Run bounded synthetic smoke tests.

Do not spend another extended audit cycle on the agent framework.

Deliver AGENT-002 through its own branch and Draft PR.

**AGENT-002 must not become a blocker for BP-11 if its runtime integration remains incomplete.**

---

# 5. PHASE C — BP-11 PUBLIC VIEWING SLOTS

## Goal

Enable unauthenticated visitors to inspect derived available viewing slots for PUBLIC residential listings.

Current backend:

`backend/app/modules/engagement/viewings.py`

Endpoint:

`GET /v1/classifieds/{listing_id}/viewing-slots`

Current authentication dependency:

`get_current_user`

Current frontend BFF contract already identifies the endpoint as optional authentication.

Implement the approved OD-6 behavior.

## 5.1 Preserve domain semantics

Public users may receive:

* available start instants;
* duration;
* timezone.

They may not receive:

* private settings;
* provider availability configuration;
* blackout records or reasons;
* booking capacity;
* individual booking information;
* requester information;
* private addresses;
* internal scheduling rules.

Nonpublic listings must retain the existing visibility refusal behavior.

Creating or changing a viewing remains authenticated and subject to existing authorization.

Do not invent a Slot database entity.

Do not introduce a new availability architecture without demonstrated necessity.

---

# 6. BP-11 — MANDATORY PERFORMANCE AND RESOURCE-EXHAUSTION REPAIR

## Critical technical finding

Current slot generation calls:

`_held_overlapping(...)`

from inside the candidate-slot loop.

This can result in one PostgreSQL occupancy query per candidate slot.

The endpoint is currently authentication-gated.

Making it public without first addressing this query pattern creates a resource-exhaustion risk.

This must be resolved as part of BP-11, not deferred until after public exposure.

## 6.1 Measure baseline behavior

Before optimizing, construct representative synthetic fixtures.

Include:

* one listing with a small weekly schedule;
* one with many recurring windows;
* one with one-off windows;
* dense existing bookings;
* blackouts;
* fully booked windows;
* maximum permitted days;
* empty settings;
* DST boundaries.

Measure:

* generated candidate count;
* returned slot count;
* executed SQL statements;
* SQL execution time;
* endpoint wall time;
* query plan and index usage;
* database work under concurrent requests.

Use disposable PostgreSQL/PostGIS.

Never run destructive performance tests against production or a shared development database.

## 6.2 Remove per-candidate PostgreSQL round trips

Investigate a bounded occupancy-query strategy.

Prefer:

1. Generate eligible candidate intervals using existing semantics.
2. Determine the minimal relevant time range.
3. Load relevant confirmed bookings using bounded, indexed database access.
4. Compute overlap counts efficiently without one SQL query per candidate.
5. Return the same derived availability semantics.

Select the simplest correct algorithm supported by measurements.

Potential implementations include interval sweeping, sorted interval structures or bounded batched SQL aggregation.

Do not select an algorithm merely because it is theoretically sophisticated.

**Acceptance invariant: PostgreSQL query count must not grow linearly with the number of candidate slots.**

Preserve:

* booking-capacity semantics;
* before/after buffers;
* minimum notice;
* DST handling;
* confirmed-booking overlap behavior;
* existing public-listing rules;
* existing availability output contract.

The booking-write path must continue independently revalidating capacity and availability.

Public slot reads are not reservations.

## 6.3 Database performance

Inspect existing PostgreSQL indexes.

Use `EXPLAIN (ANALYZE, BUFFERS)` on synthetic data when appropriate.

If a missing index is proven necessary, create the smallest justified migration and follow all migration-safety requirements.

Do not introduce speculative indexes.

Keep resource usage bounded by validated request parameters.

If existing stored windows or booking volumes can create unbounded work, establish justified limits or bounded query behavior without silently changing accepted domain rules.

## 6.4 Abuse protection

Implement public endpoint rate limiting using the existing infrastructure where possible.

Verify client-IP attribution through trusted proxy configuration.

Prevent bypass through forged forwarding headers.

Provide appropriate HTTP 429 behavior and `Retry-After` where supported by the existing API contract.

Limit costly request dimensions.

Prevent arbitrary historical or excessively distant date queries from creating expensive scans, while preserving approved use cases.

Investigate whether a short-lived cache provides measurable value.

Do not add Redis, distributed caching, or another service unless the existing architecture demonstrates a need.

If caching is used, its keys and invalidation must preserve public visibility and avoid disclosing stale private information.

Prefer correct bounded computation over an unsafe cache.

## 6.5 Performance acceptance

Compare the optimized implementation against the measured baseline using identical fixtures.

Provide a before/after table containing:

```text
Fixture
Candidate count
Returned slots
SQL statements
DB execution time
Endpoint wall time
Concurrent-request behavior
```

Verify that SQL round trips are bounded independently of candidate count.

Record the observed latency distribution and whether the change creates unacceptable database load.

Do not invent performance numbers.

Document any unresolved operational limits.

## 6.6 Functional and security testing

Required coverage:

* anonymous PUBLIC listing;
* authenticated PUBLIC listing;
* private listing;
* paused listing;
* held listing;
* missing listing;
* no settings;
* disabled settings;
* existing bookings;
* maximum capacity;
* buffer overlap;
* minimum notice;
* blackout exclusion;
* DST spring transition;
* DST autumn transition;
* date boundaries;
* rate limiting;
* information disclosure;
* booking-request authentication;
* public-read/booking-write concurrency.

Use relevant existing PostgreSQL tests.

Run Ruff, Mypy, OpenAPI drift checks, generated frontend API checks and required CI.

BP-11 is high-risk enough to require a genuinely independent, bounded exact-SHA security/availability review under existing governance.

Do not commission another whole-repository audit.

## 6.7 Delivery

Implement BP-11 completely.

Produce:

* production code;
* tests;
* API documentation;
* generated types where necessary;
* benchmark evidence;
* task record;
* Draft PR.

Do not automatically merge.

Proceed to the next authorized work item.

---

# 7. PHASE D — BP-9 VERIFIED PROPERTY AUTHORITY

## Goal

Enforce the already accepted D-105 PropertyAuthority rule for private provider interactions.

Canonical requirement:

**Private engagement access requires a VERIFIED PropertyAuthority root and a currently valid authority/representation chain granting the relevant scope.**

Do not silently redefine the User, LegalParty, PropertyAuthority or RepresentationMandate model.

## Scope

Inspect and repair provider authorization for:

* conversation and message access;
* private requester identity and notes;
* viewing management;
* provider viewing operations;
* private engagement mutations;
* provider notification recipients introduced by BP-6;
* other directly related provider engagement paths identified by the approved BP-9 contract.

Use the relevant `MANAGE_MESSAGES` and `MANAGE_VIEWINGS` scopes.

Unverified authority must not grant access to private engagement data.

Expired, revoked or otherwise invalid mandates must not remain effective.

Preserve authorized requester access to their own conversations and viewings.

Do not broaden the change into unrelated property-management permissions without canonical justification.

## Security acceptance

Test:

* verified owner;
* verified authorized representative;
* unverified root;
* expired mandate;
* revoked mandate;
* missing required scope;
* unauthorized unrelated user;
* ownership changes;
* provider notification recipient filtering;
* private data non-disclosure;
* existing legitimate participant access.

Where authorization is time-sensitive, verify that cached or preloaded authority state cannot improperly grant access.

Preserve existing refusal and privacy semantics.

Apply targeted security and PostgreSQL tests.

Independent exact-SHA authorization review is mandatory.

Deliver the implementation as a Draft PR.

**BP-9/BB-10 remains an external-provider-beta gate until integrated and verified.**

---

# 8. PHASE E — BP-3 PROVIDER LISTING ENUMERATION

## Goal

Provide the approved provider-facing listing discovery capability required by FE-003.

Existing enumeration is too narrowly associated with the publication scope.

Implement the behavior required by the approved FE-003 contract and authority model.

## Requirements

A provider should be able to discover only listings for which their valid authority chain grants the relevant provider capabilities.

Preserve distinctions between:

* listing publication rights;
* message-management rights;
* viewing-management rights.

Do not grant broader permissions merely because a provider can enumerate a listing.

Use VERIFIED-root rules for private engagement projections.

Ensure cross-property isolation.

Avoid leaking private listing, requester or authority information through the returned DTO.

Prefer an existing endpoint extension where the approved contract permits it.

Preserve backward compatibility.

Add focused access-control tests.

Deliver a separate Draft PR.

---

# 9. PHASE F — BP-4 REQUESTER DISPLAY-NAME PROJECTION

## Goal

Provide the minimum requester identity projection needed by provider-facing engagement UI.

Implement approved OD-3 semantics.

The provider receives:

**First name + surname initial.**

Do not expose:

* requester e-mail;
* requester phone;
* full legal identity;
* sensitive verification metadata;
* unrelated account fields.

Do not label the projected name as identity-verified without an independent verified-identity fact.

Use server-side projection.

Do not construct sensitive identity projections from unrestricted client-side user objects.

Preserve authorization and data minimization.

Handle unusual names, empty names, Unicode and whitespace according to approved rules.

If previously accepted rules do not resolve a material ambiguity, record a bounded canonical question instead of inventing business semantics.

Test unauthorized access, data leakage and serialization.

Deliver a separate Draft PR.

---

# 10. PHASE G — FE-003 PRODUCT IMPLEMENTATION

## Goal

Deliver a coherent frontend implementation of:

**Discovery → Save → Conversation → Viewing**

Use the already approved contract:

`docs/tasks/FE-003-save-conversation-viewing-DRAFT.md`

Read the approved DESIGN-001C repository handoff.

Do not require the inaccessible original design artifact if the repository handoff is sufficient under its approved P-0 rule.

Do not implement FE-VIS-001.

Use the existing semantic-token design system.

## 10.1 Prerequisites

Before FE-003 implementation, confirm that required backend behavior is available in the verified dependency chain.

Relevant components include:

* BP-1;
* BP-2;
* BP-5;
* BP-6;
* BP-7;
* BP-8;
* BP-9;
* BP-10;
* BP-11;
* BP-12;
* BP-3;
* BP-4.

Do not confuse an implemented Draft PR with an integrated dependency.

If founder merge decisions for intermediate backend PRs remain pending, FE-003 implementation may proceed on a clearly identified stacked dependency branch where technically safe, but must not be represented as independently mergeable against an unprepared `main`.

Do not bypass dependent integration gates.

## 10.2 Functional scope

Implement the approved FE-003 slices.

### Authentication interruptions

Users must be able to begin supported actions as guests, authenticate when required and resume the intended action.

Preserve session and authentication security.

### Saved listings

Implement save/unsave behavior.

Handle tombstones for no-longer-available listings.

Preserve idempotent backend semantics.

### Saved searches

Implement approved saved-search interaction and error states.

Do not invent new notification capabilities.

### Conversations

Implement:

* conversation start;
* existing-thread continuation;
* message composer;
* message history;
* inbox;
* conversation states;
* redacted messages;
* idempotent message retries.

Preserve BP-10 `client_message_id` behavior.

Do not create duplicate messages following uncertain network outcomes.

### Reporting

Implement the approved in-context message-report interaction.

Preserve OD-7:

An authenticated current participant may report another participant's USER message without an additional verified-contact requirement.

Do not weaken LISTING report verification requirements.

### Contact reveal

Implement the approved contact-reveal UX.

Preserve BP-8 `RECONTACT_BLOCKED` behavior.

Never display a phone returned from stale application state after an authorization refusal.

Respect verified-phone requirements and reveal quotas.

### Viewing flow

Allow guests to inspect and select derived offered slots.

Require authentication before creating a viewing request.

Implement existing request, confirmation, cancellation and viewing-state semantics.

Preserve timezones and DST behavior.

Do not invent an independent frontend booking authority.

### Provider interactions

Use the completed BP-3, BP-4 and BP-9 contracts.

Do not expose private requester information to unverified or unauthorized provider representatives.

## 10.3 UX and quality

Honor the approved FE-003 contract for:

* responsive behavior;
* mobile action dock;
* desktop engagement rail;
* accessibility;
* keyboard navigation;
* focus management;
* loading states;
* empty states;
* API refusal messages;
* internationalization;
* analytics consent.

Do not introduce speculative redesigns.

Use the existing frontend architecture and BFF allowlist.

Do not bypass the BFF by making unsupported direct browser-to-backend calls.

## 10.4 End-to-end tests

Required user journeys include:

```text
Guest → Listing → Save → Login → Saved

Guest → Listing → Select Slot → Login → Request Viewing

Authenticated user → Start Conversation → Send Message

Message send → Network uncertainty → Idempotent retry

Requester → Report another participant's USER message

Restricted requester → Contact reveal → RECONTACT_BLOCKED

Verified provider → View engagement

Unverified provider → Private engagement denied

Requester → Viewing request → Provider decision

Requester → Viewing cancellation
```

Implement the exact approved lifecycle and edge cases rather than simplifying them for the test.

Include negative authorization, privacy and accessibility checks.

Run relevant unit, component, integration and Playwright E2E tests.

Run frontend and backend CI.

Deliver the full approved FE-003 scope through bounded implementation slices.

Use separate Draft PRs for independently reviewable slices where that improves integration safety.

Do not stop after implementing only a visual mockup.

The final deliverable must contain working frontend/backend integration, not placeholder buttons.

---

# 11. PARALLEL SECURITY WORK — GITHUB RULESET

## Observed repository risk

The previously inspected repository reported:

```text
visibility: public
main protected: false
active rulesets: none returned
```

Reconfirm the current state.

Do not change repository visibility without explicit authorization.

## Required protection

Prepare and, if supported by available permissions and policy, configure an active main-branch ruleset with:

* pull requests required;
* relevant CI checks required;
* force pushes blocked;
* deletion of main blocked;
* normal merge workflow preserved.

Verify exact GitHub Actions check names before making them required.

Avoid requiring a formal GitHub approval from a nonexistent reviewer, thereby deadlocking the sole-contributor development workflow.

Preserve the founder's ability to merge approved, green pull requests through the normal GitHub interface.

Do not create broad administrator bypasses merely for convenience.

Do not disable CI requirements to accelerate delivery.

If the current repository plan, connector permissions or GitHub API prevents applying the ruleset:

1. Do not claim it was configured.
2. Preserve completed product implementation work.
3. Produce the exact proposed configuration.
4. Record the minimum required founder action.
5. Continue unrelated authorized development.

Do not deploy.

---

# 12. CROSS-PR EXECUTION STRATEGY

Avoid a giant unreviewable branch.

Use bounded branches.

Suggested sequencing:

```text
BP-8 integration
        |
        +--> AGENT-002
        |
        +--> BP-11
                 |
                 +--> BP-9
                          |
                          +--> BP-3
                                   |
                                   +--> BP-4
                                            |
                                            +--> FE-003
```

AGENT-002 and GitHub protection do not belong in the product dependency chain.

One active writer per bounded context.

Where a predecessor is integrated:

Branch from current integrated main.

Where a predecessor awaits founder merge:

Use an explicitly documented stacked PR dependency if appropriate.

Never pretend that an unmerged dependency exists on main.

Do not squash, rebase or rewrite an already frozen reviewed candidate without identifying the resulting review implications.

Avoid duplicating backend changes across feature branches.

Prefer one coherent implementation and review cycle per bounded task.

Do not batch unrelated feature changes into the AGENT-002 PR.

---

# 13. REVIEW AND VERIFICATION POLICY

The objective is delivery with risk-appropriate verification.

Not the maximum possible number of audits.

## Risk levels

R0:

Documentation and trivial mechanical changes.

R1:

Ordinary bounded changes.

R2:

Authorization, privacy, availability, concurrency, migrations and other sensitive backend changes.

R3:

Production, payments, irreversible data operations and similarly critical changes.

Follow existing canonical §9 requirements.

Use independent exact-SHA review when mandatory.

Existing completed audits remain valid for their unchanged audited candidates.

Do not repeat:

* BP-10 independent audit;
* BP-5/BP-6 completed reviews;
* BP-8 completed independent review;
* AGENT-001 foundation audit;

unless material new evidence invalidates a previous conclusion.

A material finding requires a targeted repair.

Do not generate a new broad review program for every repair.

The independent reviewer must operate on the exact candidate SHA in an isolated read-only context and must not be the implementation writer.

A required review is not satisfied by renaming the writer's self-review as independent.

---

# 14. CONTINUOUS DELIVERY METRICS

Stop treating audit count as a success metric.

Track:

### Product delivery

* completed approved backlog items;
* number of tested feature slices;
* number of Draft PRs ready for founder review;
* number of accepted integrations;
* number of completed end-to-end user journeys.

### Engineering efficiency

* cycle time per task;
* implementation-to-review duration;
* first-pass CI success;
* number of material review findings;
* number of repeated review loops;
* escaped material defects;
* time lost to context recovery;
* number of agent handoffs.

### Quality

* relevant test pass rates;
* regression failures;
* security findings;
* production-impacting incidents;
* measured API performance.

### Agent efficiency

* specialist invocations per task;
* unnecessary specialist invocations;
* token consumption where available;
* compaction/recovery failures;
* completed tasks per authorized execution cycle.

Only report actually measured values.

Do not invent productivity improvements.

Do not optimize toward artificially high test counts or superficial code coverage.

---

# 15. DELIVERY CHECKPOINTS AND RESUMABILITY

After each meaningful implementation milestone, persist:

```text
TASK
STATUS
BASE SHA
BRANCH
CANDIDATE SHA
TREE SHA
CHANGED FILES
TEST RESULTS
REVIEW STATUS
CI STATUS
PR URL
OPEN BLOCKERS
NEXT UNBLOCKED ACTION
```

Use an appropriate repository-readable checkpoint or existing project mechanism.

Do not duplicate current volatile status across multiple conflicting files.

Keep `docs/PROJECT-STATUS.md` as the canonical volatile status owner.

Update accepted decisions and implementation convergence where required.

Checkpoint data must allow another authorized Codex or Claude session to resume without redoing the completed work.

Do not preserve unnecessary full transcripts or sensitive model/tool output.

---

# 16. HARD CONSTRAINTS

Never:

* deploy to production;
* mutate production data;
* activate paid providers;
* bypass authentication;
* bypass GitHub branch protection;
* change canonical business rules without authorization;
* expose private identity or address data;
* silently expand scope;
* perform destructive repository cleanup;
* delete historical implementation evidence;
* falsify test results;
* treat stale chat memory as repository truth;
* automatically merge newly created PRs without founder authorization.

Use disposable databases for destructive tests.

Maintain existing migration barriers and rollout restrictions.

Preserve:

```text
IBB-001:
Last formal backend baseline.

BP-5 migration:
BARRIER / rollback_to_previous BLOCKED.

BP-10:
Existing EXPAND and BB-11 rollout restrictions.

FE-VIS-001:
NOT AUTHORIZED.

PRODUCTION:
NOT READY / NOT DEPLOYED.
```

New integrations do not automatically establish IBB-002.

Do not create a new formal baseline merely to mark progress.

---

# 17. WHEN TO STOP OR CONTINUE

Do not stop for:

* already approved implementation semantics;
* completed audit findings with accepted dispositions;
* redundant prompt refinements;
* documentation polish unrelated to correctness;
* optional architecture improvements;
* an unavailable specialist when that specialist is not mandatory.

Stop only the affected operation for:

* missing founder merge authorization;
* genuine canonical contradiction;
* material unresolved security finding;
* failed mandatory CI;
* missing required independent review;
* unsafe Git state;
* unavailable permissions for an otherwise mandatory mutation;
* a destructive operation outside this authorization.

When one path is blocked, continue another authorized and independent task.

Do not claim dependent work is integrated when its prerequisite remains only a Draft PR.

If all currently executable work is complete, return the exact remaining founder decisions and their corresponding PRs.

Do not pretend to continue running outside the active session.

---

# 18. FINAL EXPECTED DELIVERABLE

Do not return only a plan.

Do not return only an audit.

Do not return only architecture recommendations.

Execute the authorized implementation work.

The final report must contain:

## Integration

* BP-8 final integration status;
* actual merge SHA if merged;
* resulting main SHA;
* relevant post-merge CI.

## AGENT-002

* orchestrator implementation;
* Claude/Codex integration;
* routing tests;
* checkpoint recovery evidence;
* Draft PR;
* remaining runtime limitations.

## BP-11

* public viewing-slot implementation;
* resource-exhaustion mitigation;
* before/after SQL measurements;
* rate-limit verification;
* tests;
* independent review;
* Draft PR.

## BP-9

* VERIFIED-root authorization enforcement;
* provider notification protection;
* negative authorization tests;
* independent review;
* Draft PR.

## BP-3

* provider enumeration implementation;
* authorization evidence;
* Draft PR.

## BP-4

* requester display-name projection;
* privacy evidence;
* Draft PR.

## FE-003

* implemented frontend slices;
* backend integration;
* tested user journeys;
* E2E results;
* independent reviews where required;
* Draft PRs.

## Infrastructure

* GitHub main protection status;
* configuration applied or exact permission blocker;
* repository visibility left unchanged unless separately authorized.

## Engineering results

* completed tasks;
* open blockers;
* actual CI results;
* material findings;
* measurable performance results;
* final repository state;
* exact next founder decisions.

Use this final summary structure:

| Task           | Implementation | Tests | Review | CI | PR | Merge |
| -------------- | -------------- | ----- | ------ | -- | -- | ----- |
| BP-8           |                |       |        |    |    |       |
| AGENT-002      |                |       |        |    |    |       |
| BP-11          |                |       |        |    |    |       |
| BP-9           |                |       |        |    |    |       |
| BP-3           |                |       |        |    |    |       |
| BP-4           |                |       |        |    |    |       |
| FE-003         |                |       |        |    |    |       |
| GitHub Ruleset |                |       |        |    |    |       |

Every status must represent actual completed work.

Distinguish:

```text
IMPLEMENTED
TESTED
INDEPENDENTLY REVIEWED
CI GREEN
DRAFT PR
MERGED
ACCEPTED
PRODUCTION READY
DEPLOYED
```

These terms are not interchangeable.

---

# 19. EXECUTION PRIORITY

Prioritize actual product implementation.

The orchestrator exists to accelerate delivery, not to become another development bottleneck.

The public viewing-slots performance issue is a mandatory BP-11 acceptance criterion.

BP-9 remains a hard private-engagement security prerequisite.

BP-3 and BP-4 must supply real provider-facing capabilities.

FE-003 must connect the completed backend capabilities into a functioning user journey.

Do not postpone product implementation to perfect the agent framework.

**Success means completed, tested, independently verified where necessary, and reviewable Homies functionality.**

Not another collection of audit reports.

Begin with current GitHub verification, then execute Phase A.

Continue through every authorized and unblocked phase.

**EXECUTE.**
