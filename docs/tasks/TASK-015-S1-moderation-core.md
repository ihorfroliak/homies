# TASK-015 Slice 1 — Moderation domain core + publication hold

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, **not merged**; **production NOT READY · NOT DEPLOYED** |
| Risk class | **R2** (publication gating, migration, authorization seam, immutable history) |
| Baseline | `main` `985db7ae116aca5e37984b8e46556e0859792313` = `451b7e56` (PR-003) + TASK-015 Phase A `2d4064b0` (merged `--no-ff` by this task's entry gate; documentation-only delta, tree equal to the candidate) |
| Branch | `claude/TASK-015-s1-moderation-core` |
| Contract | [Phase A](TASK-015-reports-moderation-phase-a.md) §6–§7, §14–§16 |
| Decisions | founder D-1 … D-9 recorded as **D-92**; slice design **D-93**; canon refinement **04a §23** |

## Founder decisions (approved with this task, recorded D-92)

D-1 contract (LISTING + MESSAGE targets; no case entity; moderation state from
the immutable decision chain; no hold table) · D-2 04a §23 · D-3
`MISLEADING_PRICE` covers "price or key details misleading"; no PRIVACY ·
D-4 Slice 2 limits (10/24 h, ≤ 20 live, IP burst 5) · D-5 republish after a
release opens a new public generation and may alert · D-6 no account status ·
D-7 user block is a pre-launch decision · D-8 no property-level hold · D-9
inbox-only notices, category TRANSACTIONAL.

## Scope delivered (Slice 1 only)

| Part | Where |
|---|---|
| canonical clarification | `docs/canonical/04a-…` §23 |
| migration `a3c5e7f9b1d4` (parent `0c4e6a8b2d91`; EXPAND, rollback BLOCKED) | `backend/alembic/versions/a3c5e7f9b1d4_moderation_core.py` |
| models: `Report`, `ModerationDecision` (immutable), `ModerationReviewRequest` | `app/modules/trust/models.py` |
| chain head / hold derivation (fails closed on a fork) | `app/modules/trust/hold.py` |
| decision application service `apply_listing_decision` | `app/modules/trust/decisions.py` |
| moderator seam `can_moderate` (DB role `admin`) | `app/core/security.py` |
| hold check in the single public-transition seam; `make_public` writes `active` itself | `app/modules/properties/publicity.py` |
| publish/confirm → 409 `HELD_BY_MODERATION`; **confirm `.applied` bug fixed** | `app/modules/properties/router.py` |
| lock order level 5 (`reports`) | `app/modules/properties/coordination.py` |
| inbox category seam (TRANSACTIONAL) | `app/modules/alerts/models.py` + migration |
| release manifest | `app/release.json` (head = minimum = `a3c5e7f9b1d4`, previous PR-003) |

**Not in S1** (by design): reports API, moderator HTTP API, review-request
API, message reports, redaction, conversation close, `close_engagement`,
viewing cancellation, media RESTRICTED action, notices, email, user block,
account status, property hold, Idempotency-Key, DATA-001, frontend. OpenAPI is
unchanged (no new routes; the 409 description is extended in Slice 3 with the
moderator API).

## Migration

* `reports` (04 §64 + 04a §23 columns), CHECKs on target type, category,
  severity, status; MESSAGE ⇒ `conversation_id`; partial UNIQUE
  `uq_reports_live_per_reporter_target` (OPEN/IN_REVIEW); queue and
  live-target indexes.
* `moderation_decisions` (04 §65 + refinements): CHECKs (target type, action,
  reason code, reclassified category, not self); **`uq_moderation_decisions_supersedes`**
  (a decision is superseded at most once); **`uq_moderation_decisions_first_per_target`**
  (partial UNIQUE where `supersedes_decision_id IS NULL`); **composite FK
  `fk_moderation_decisions_supersedes_same_target`** over `(supersedes_decision_id,
  target_type, target_id)` → `(id, target_type, target_id)`; trigger
  **`moderation_decisions_append_only`** (`forbid_mutation()`), created_at /
  effective_from = DB `now()`.
* `moderation_review_requests`: one OPEN per decision (partial UNIQUE).
* `user_notifications.category IN ('PRODUCT','TRANSACTIONAL')`.
* **Privileges:** the trigger name makes `app_grants.sql` withhold UPDATE and
  DELETE (TRUNCATE is withheld from every table); the migration job's
  post-verify and the startup check (`verify_ledger_privileges`) cover it —
  proven by `test_db_privileges_pg.py` (tables derived from the triggers).
* **Release:** EXPAND (new tables, widened CHECK) / BLOCKED (the previous
  release's publication ignores holds; against this schema it is refused as
  TOO_NEW). `minimum_schema` = head: this build reads the decisions on every
  publication, so migration first.

## Decision-chain invariants

1. **One line per target** — at most one first decision, each decision
   superseded at most once, only by a decision on the same target (database).
2. **One head** — the decision nobody supersedes; `hold.head()` raises
   `ForkedChain` rather than pick one if that were ever violated.
3. **No silent overwrite** — `apply_listing_decision(…, expected_head_decision_id)`
   compares under the listing row lock; mismatch → `StaleHead(current_head_id)`.
4. **Retry after `commit_unknown`** — the committed first attempt moved the
   head, so the retry gets `StaleHead`; if it did not commit, the retry
   succeeds; never two branches (proven through the PR-003 fault proxy, both
   branches).
5. **Immutable** — ORM guard, append-only trigger (any role), no UPDATE/DELETE
   privilege for the application role.

Lock order: property coordination lock → listing row (`FOR UPDATE`) → head
read (separate statement, after the lock is granted) → insert → effect →
reports (`FOR UPDATE`, level 5) → audit → event. The caller commits.

## Hold, release, publication

* **Held** ⇔ head ∈ {CONTENT_EDIT_REQUIRED, VISIBILITY_LIMITED}. Applying a
  hold moves `draft/active/stale/paused` to `paused` (archived stays archived;
  the hold still stands). The public-visibility rule is unchanged.
* **`make_public`** — the only code that writes `active` (AST sentinel with a
  self-test) — reads the head after its row lock and returns
  `Transition(applied=False, held=True)` before writing: no status, no
  generation, no `ListingBecamePublic`, no work item.
* **Publish and confirm** answer `409` with detail
  `HELD_BY_MODERATION: this listing is on hold by Homies moderation` (stable
  leading code; the project has no coded-error convention yet). A structural
  test requires every `make_public` caller to use `.applied` and `.held`.
* **Confirm bug (pre-existing, fixed):** confirm ignored `make_public`'s result
  — a refusal returned 200, wrote `classified.confirmed` and a freshness event.
  Now: rollback + 409. Proven in the N−1 skew state (held but `active`/`stale`).
* **Release** = `NO_ACTION` superseding the hold with `REINSTATED_REMEDIED` or
  `REINSTATED_DECISION_ERROR`; it never touches the listing row (row `xmin`
  unchanged). The owner republishes → new public generation, alerts may fire
  (D-5).
* Reason rules: holds need a report category; NO_ACTION on a non-held listing
  is `NOT_A_VIOLATION`; ACCOUNT_* and media/message actions are refused in S1.

## Authorization

`can_moderate(user)` = database role `admin` (never a token claim). Conflict
of interest in S1: a moderator holding any authority scope on the listing's
property, or deciding on their own report → `ConflictOfInterest`.
**Boundary:** participant conflicts (conversation/message targets) belong to
Slice 4, where those targets exist.

## Privacy, audit, event, metric

* Audit `moderation.<action>` on the listing: `decision_id, reason_code,
  supersedes_decision_id, status_before, status_after` — ids and codes only.
* Event **`ModerationDecisionRecorded`**, dedup `ModerationDecisionRecorded:{id}`,
  payload exactly `decision_id, target_type, target_id, listing_id, action,
  reason_code, supersedes_decision_id, effective_from`; forbidden-key test (no
  reporter, text, explanation, actor, address, coordinates, body, contact,
  snapshot); **not** in `events.ROUTING`.
* Metric `homies_moderation_decisions_total{target_type,action}` (bounded),
  counted after commit only; a rolled-back savepoint drops only its own
  decisions.

## Measurement impact

S1 makes moderation decisions, hold application and release, and decision
counts by action measurable (decisions + reports tables, generation at
decision, reversal reason codes). It does **not** measure reporting behaviour —
`homies_reports_created_total` arrives with Slice 2.

## Concurrency (PostgreSQL, `pg_blocking_pids` evidence)

| | Proven |
|---|---|
| C1 | publish waiting behind a hold → 409, status `paused`, generation unchanged (prior active and paused); hold waiting behind a publication → listing taken down; head read after the row lock (row-lock-only writer) |
| C2 | confirm waiting behind a hold → 409; confirm and publish in the N−1 skew state (active/stale) → 409, no side effects |
| C3 | two moderators on one head → one wins, the other `StaleHead` (initial and from a hold); direct fork refused by `uq_moderation_decisions_supersedes` (and allowed when the first writer rolls back); second first decision and cross-target supersede refused |
| C4 | release under the lock then republish → generation + 1, one event, one work item; release writes nothing to the listing; publish holding the lock while held → 409, then the release, then a successful publish |
| C5 | retry with the old head after a committed decision → `StaleHead`; real unknown COMMIT through the PR-003 proxy: committed branch → retry stale; rolled-back branch (backend terminated) → retry succeeds; exactly one successor of the old head |
| C6 | hold vs authority revoke in both orders (moderator holds nothing below the property lock while waiting; no deadlock counter change); hold vs owner pause; archived stays archived |

## Tests and evidence

See the final report for exact counts (SQLite, PostgreSQL/PostGIS, restore
drills, mutation, CI). Mutation classes: hold check removed, confirm ignores
`.applied`, fork uniqueness removed, CAS removed, decisions mutable, private
data in the event, event routed through ROUTING, release reactivates.

## Known debt

* Slices 2–6 (reports API with D-4 limits, moderator API + notices, messages/
  conversations/viewings/media, review requests, hardening).
* General Idempotency-Key before the browser launch (property, classified,
  message creates).
* User block before public launch (D-7); account status revisited (D-6).
* Legal L1/L2/L3/L8 (and the rest of L1–L13) — launch blockers, not S1.
* Public `/metrics` (category counts become world-readable until ingress
  restriction).
* JWT clock flake (MICRO-002 recommendation).
* No machine-readable error-code convention (HELD_BY_MODERATION is a stable
  detail prefix).
* The 409 description in OpenAPI is updated with the moderator API (Slice 3).

## Slice 2 boundary

Slice 2 adds `POST /v1/reports` and `GET /v1/me/reports` (D-4 limits, snapshot,
derived severity, `homies_reports_created_total`). Report creation must never
lock `reports` and then a listing, property or user row (lock level 5).
