# TASK-015 Slice 4a — Message reports, moderator evidence, message redaction

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, **not merged**; **production NOT READY · NOT DEPLOYED** |
| Disposition (TASK-016, 2026-10-06) | merged into `main` at `03268432f664ec6283f427b2f528a8bb6f814065` (merge of candidate `ff433303948bdf5b5097de757fc5615b3edc56e6`, externally reviewed); still BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (D-88). The status text is kept as written |
| Risk class | **R2** (private messages, authorization, privacy, rollback barrier) |
| S5 integration | exact candidate `3146fed392d66421cdaad45e72002c2a536c4b63` merged `--no-ff` into `main` `4bf66108` → **`1de34bf550e55c0e4e28d78090f0720d6812287e`** (tree equal to the candidate; head `a3c5e7f9b1d4`) |
| Baseline | `main` `1de34bf550e55c0e4e28d78090f0720d6812287e` |
| Branch | `claude/TASK-015-s4a-message-moderation` |
| Contract | [Phase A](TASK-015-reports-moderation-phase-a.md) §5, §6.2, §9; [S1](TASK-015-S1-moderation-core.md); [S2+S3](TASK-015-S23-listing-report-moderation-loop.md); [S5](TASK-015-S5-moderation-review-requests.md) |
| Decisions | PD-1 … PD-9 (this task's authorization); **D-96** |
| Legal | **L9: TECHNICALLY IMPLEMENTED — LAUNCH LEGAL/PRIVACY VALIDATION REQUIRED** |

```text
conversation participant → reports another participant's message (POST /v1/reports, MESSAGE)
→ moderator queue (ids only) → GET …/targets/MESSAGE/{id}: audited, bounded evidence
→ POST …/decisions: CONTENT_REMOVED (redaction) or NO_ACTION
→ participants see "Removed by Homies"; the original stays moderator-only evidence
```

## Product decisions (PD-1 … PD-9, authorized by this task)

PD-1 MESSAGE is the second user-facing report target (LISTING unchanged) ·
PD-2 only an authenticated participant reports, never their own USER message
nor a SYSTEM message · PD-3 reportability follows participation, not listing
publicity or conversation status · PD-4 evidence = the message ± 2 messages of
the same conversation · PD-5 CONTENT_REMOVED keeps the body · PD-6
participant-facing "Removed by Homies" through the client's strings · PD-7
MESSAGE actions: NO_ACTION, CONTENT_REMOVED · PD-8 no conversation, viewing,
account or listing effect · PD-9 no private content in any domain event.

## Message reports

`POST /v1/reports` body is a discriminated union on `target_type`:
`ListingReportIn` (S2, unchanged) or **`MessageReportIn`** `{target_type:
MESSAGE, target_id, reason, text?}` with reason ∈ HARASSMENT, SCAM,
DISCRIMINATION, SAFETY (**HIGH**), SPAM, OTHER (**NORMAL**); listing and
moderator-only reasons → 422; extra fields (severity, …) → 422.

Eligibility (`reports.file_message_report`):

1. verified email or phone (as for listings) — before any lookup;
2. the message and its conversation exist **and** the reporter is a current
   side of the conversation — `engagement.access.side`, the conversation
   routes' own rule (the tenant who started it, or whoever holds
   MANAGE_MESSAGES on the listing's property now; never copied participant
   rows) — else **404**, the same body as a missing message;
3. a SYSTEM message → **409**; the reporter's own message
   (`Message.sender_user_id`, never a side or an organisation) → **409** —
   409 because the reporter can see the message; nothing is leaked;
4. access re-read after the reporter lock is granted: a right revoked by
   then no longer counts (M-R2).

Stored: target MESSAGE, `conversation_id`, `listing_id` (the conversation's),
category, text, derived severity — **no snapshot**: messages have no edit
path (`edited_at` is never written), so the message row is the evidence; no
context is copied into the report. S2 idempotency (one live report per
reporter and target, 200 on repeat/retry) and the **shared** account quota
(10/24 h, ≤ 20 live, `REPORT_CREATE`) apply unchanged.

## Moderator queue

Grouped by `(target_type, target_id)`; MESSAGE rows carry `conversation_id`
and `listing_id` — ids, counts, severity, times, head — never a body, the
conversation or report text. Ordering unchanged (URGENT/HIGH, open listing
reviews, NORMAL). Review requests stay LISTING-only.

## Moderator evidence (PD-4) and its audit

`GET /v1/admin/moderation/targets/MESSAGE/{message_id}` (moderator only):

* OPEN reports → IN_REVIEW, `first_reviewed_at` once (same id-ordered lock as
  listings);
* evidence = the target fixed by id plus **at most 2 messages before and 2
  after it in the same conversation**, ordered by `(created_at, id)` — two
  statements with `LIMIT 2` on a `(created_at, id)` row comparison; the
  conversation is never read whole; fewer at the edges;
* per message: id, `is_target`, sender user id, sender organisation id, type,
  **stored body** (also for a removed message), created/redacted time, reason
  code; the conversation's id, listing id, status; the decision head; the
  live reports (reporter id, verification flags, reason, severity, text).
  Never an email, phone, address, profile, or another conversation;
* every access writes `moderation.message_evidence_viewed` with `{message_id,
  conversation_id, evidence_message_ids, report_ids}` — ids only.

Original-body access is isolated in `trust.moderation.review_message`; the
participant API has no parameter that reaches it.

## Decisions on messages

`POST /v1/admin/moderation/decisions` with `target_type: MESSAGE` →
`decisions.apply_message_decision` (same chain invariants: one first decision,
one successor, same-target FK, expected head → 409 `STALE_HEAD`, never
re-aimed):

* **CONTENT_REMOVED** (reason: a report category) — insert the decision, set
  `redacted_at` (= the decision's DB instant) and `redaction_reason_code`
  (only where not yet redacted), resolve the live reports, audit
  `moderation.message_content_removed` (ids and codes), emit
  `ModerationDecisionRecorded` (ids and codes), count — one transaction. The
  body is **not** changed.
* **NO_ACTION** (`NOT_A_VIOLATION`) — dismissal; resolves reports; the message
  is untouched.
* **Removal is not reversed in S4a.** Canon defines no message restoration, so
  once removed, NO_ACTION, REINSTATED_* and a second CONTENT_REMOVED are 422.
  Restoration, if ever wanted, is a product decision and a new slice.
* No conversation closure, listing hold, viewing, account or notice effect.

### Conflict of interest (403)

A moderator may not decide on a message when they are a **current side of the
conversation** (tenant, or current MANAGE_MESSAGES holder — dynamic, the
`engagement.access` rule), hold **any authority over the listing's property**,
**wrote the message**, or have a **live report** on it (re-checked under the
report row locks). A former provider with no current right is not conflicted
by history alone (tested: an agent removed from the organisation may decide
on the tenant's message but not on their own). There is no caller-selected
report (`report_id` is refused).

## Redaction projection (participants)

`MessageOut` gains `moderation_state: NONE | REMOVED`; for a redacted row it
returns `body: null, moderation_state: REMOVED` — enforced in the model's own
validator for ORM rows and dicts alike, so `GET /v1/conversations/{id}`, the
send response and any future route cannot serialise a removed body. The
policy reason is **not** exposed to participants. The client renders
"Removed by Homies" (no localisation is implemented server-side).

## Lock order (final, S4a)

| Path | Order |
|---|---|
| message decision | conversation row → message row → head CAS → insert → redaction → reports `FOR UPDATE ORDER BY id` → audit → event |
| message review | reports `FOR UPDATE ORDER BY id` (OPEN only) |
| message report | reporter `users` row `FOR NO KEY UPDATE` → reports insert |
| listing decision (S1–S5) | property → listing row → … (unchanged) |

A message decision never locks a property or listing row, so it closes no
cycle with listing decisions. **S4b boundary:** `send_message` still checks
`status` without a row lock (known); S4b's conversation locking should take
the conversation row first — the same first lock as here.

## Concurrency (PostgreSQL)

| | Proven |
|---|---|
| M-R1 | two simultaneous reports by one participant → one 201 + one 200, same id, one live row |
| M-R2 | the provider's report waits on its reporter lock while an admin revokes the provider's authority → the re-check refuses (404); no report |
| M-R3 | two moderators: the second waits on the conversation row, then `STALE_HEAD` naming the first; one decision |
| M-R4 | a read during the uncommitted decision returns the committed (original) state — read committed, documented; after commit no read returns the body; the stored body is unchanged |
| M-R5 | rolled-back decision: no decision, not redacted, report OPEN, no audit, no event |
| M-R6 | unknown decision COMMIT (PR-003 proxy): committed → redacted once, retry `STALE_HEAD`; rolled back → original, retry removes |
| M-R7 | a participant (reporting tenant) moderator: 403 through the handler; `report_id` refused |
| M-R8 | evidence fixed by id; concurrent writes and another conversation with identical timestamps never enter it |
| stress | 4 × (review ∥ decision): deadlock counter unchanged |

## Privacy

Message bodies and report text never reach audit `data`, logs, metrics,
domain events, notices, the reporter's API or public listing APIs — canary
tests over each surface (and a log capture). `ModerationDecisionRecorded`
payload unchanged (ids and codes).

## Release policy — security/privacy rollback barrier

No migration (`messages.redacted_at/redaction_reason_code`,
`reports.conversation_id`, MESSAGE decision targets exist since S1).
`release.json`: `NO_SCHEMA_CHANGE`, head = minimum = maximum = `a3c5e7f9b1d4`,
previous `TASK-015-S5`, **`rollback_to_previous = BLOCKED` — SECURITY/PRIVACY
BARRIER**: the S5 build serialises `messages.body` without reading
`redacted_at`, so rolling back would show every removed message to its
participants again. Never restart an older image once a redaction exists;
forward repair only. A test pins the barrier and its note.

## Evidence (builder, local Docker; first runs and reruns kept apart)

* S4a SQLite suite (+ affected S1/S2/S3/S5, release, conversations): 190
  passed / 1 failed first run — the failure a refused-token `KeyError` in an
  S1 setup (local clock class).
* S4a PostgreSQL M-R1…M-R8 + stress: 10/10 on first execution.
* Mutation: baseline 85/85; **14/14 killed**, each by its intended test (M13
  for the right reason: the side transaction's redaction survives the
  rollback).
* Full PostgreSQL/PostGIS with mandatory restore drill: 1800 passed / 2
  failed / 1 skipped. Both are pre-existing timing assertions on a slow host
  (45-minute run): PR-003 `/healthz` under a full thread pool (1.27 s vs
  < 1 s) — passed on rerun; PR-002
  `test_a_second_runner_waits_at_most_the_lock_timeout` (12.6 s vs < 12 s) —
  fails on every local rerun, because the bound includes the runner's
  pre-lock setup (~2.5 s here); it fails the same way on the S1 baseline.
* Full SQLite: 1314 passed / 488 skipped / 1 error (refused token) → passed on
  rerun. (A first attempt was invalid: run with the restore-drill flag and
  no database, which aborts collection.)
* ruff, mypy (123 files) clean; Spectral 0 errors (49 pre-existing warnings);
  AsyncAPI valid.
* CI on `2f0af3d2` (run 37071488807) failed in the backend Test step, as did
  37047555634 (`main` 4bf66108) and 37048911922 (S5) on code that passed on
  rerun. The job log is not readable without GitHub authentication; the
  timing tests above are the suspected class (debt).

## Legal boundary

**L9 — moderator access to private messages: TECHNICALLY IMPLEMENTED —
LAUNCH LEGAL/PRIVACY VALIDATION REQUIRED.** Not claimed: GDPR/DSA compliance,
retention periods, final wording. Visibility is limited to PD-4.

## Known debt

* **S4b:** conversation restriction (FEATURE_RESTRICTED / CLOSED + SYSTEM
  line), `close_engagement`, cancelling future viewings, refusing viewing
  confirmation under a hold, media RESTRICTED, and locking `send_message`.
* Message removal is irreversible (no restoration flow).
* General Idempotency-Key; D-7 user block; public `/metrics`; JWT clock
  (MICRO-002); machine-readable error codes; 24 h report-window index;
  queue multi-snapshot; host-only publish/confirm (S5).
