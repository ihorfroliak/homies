# TASK-015 Slices 2 + 3 — Listing reports, moderator API, owner moderation notices

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, **not merged**; **production NOT READY · NOT DEPLOYED** |
| Disposition (TASK-016, 2026-10-06) | merged into `main` at `4bf6610849ce42b17480e498d474c9355b0e1887` (merge of candidate `7a51236d12630467736d8f607c7e398b1dd3a82a`); still BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (D-88). The status text is kept as written |
| Risk class | **R2** (new public write surface, authorization, privacy of allegations, concurrency) |
| S1 integration | exact candidate `1ccf1a18314cf9020bfd3667ae16b0ba759f862d` merged `--no-ff` into `main` `985db7ae` → **`1a65d3812f5f175e3b27222401685ebf8260b67a`** (tree equal to the candidate; one Alembic head `a3c5e7f9b1d4`) |
| Baseline | `main` `1a65d3812f5f175e3b27222401685ebf8260b67a` |
| Branch | `claude/TASK-015-s2-s3-report-moderation-loop` |
| Contract | [Phase A](TASK-015-reports-moderation-phase-a.md) §5, §6, §8–§13; [Slice 1](TASK-015-S1-moderation-core.md) |
| Decisions | founder D-92 (D-1 … D-9); D-93 (chain/hold); **D-94** (this slice) |

The first complete moderation loop:

```text
verified user → reports a listing → moderator queue → moderator opens the target (IN_REVIEW)
→ moderator decides (S1 service: hold / release / dismissal) → reports RESOLVED
→ owner sees the hold on /me/classifieds → owner gets a TRANSACTIONAL inbox notice
```

**LISTING only.** MESSAGE reports, redaction, conversation close,
`close_engagement`, viewing cancellation and media actions are Slice 4; review
requests are Slice 5. Widening the target enums later is additive.

## API

| Operation | Actor | Answers |
|---|---|---|
| `POST /v1/reports` `{target_type: LISTING, target_id, reason, text?}` | signed-in, verified email or phone | 201 created · 200 already reported (same body, `created: false`) · 401 · 403 not verified · 404 not reportable (= not found) · 409 own listing · 422 · 429 quota / rate limit (`Retry-After`) · 503 (PR-003) |
| `GET /v1/me/reports?limit&offset` | signed-in | own reports: id, target, reason, status `received`/`reviewed`, created_at |
| `GET /v1/admin/moderation/queue?limit&offset` | moderator | targets with live reports (see Queue) |
| `GET /v1/admin/moderation/targets/LISTING/{listing_id}` | moderator | target detail; OPEN → IN_REVIEW |
| `POST /v1/admin/moderation/decisions` | moderator | 201 · 403 not a moderator / conflict of interest · 404 · 409 `STALE_HEAD` · 422 · 503 |
| `GET /v1/me/classifieds` (existing) | listing manager | + `moderation {state NONE|HELD, action, reason_code, since, review NONE}` |
| publish / confirm (existing) | listing manager | 409 `HELD_BY_MODERATION…` now documented |
| `GET /v1/me/inbox` (existing) | user | TRANSACTIONAL moderation notices |

Moderator = `can_moderate(user)` (S1 seam; today the database role `admin`),
router-level dependency. Errors follow the project convention (string
`detail`); moderation conflicts carry a stable leading code (`STALE_HEAD`,
`CONFLICT_OF_INTEREST`, `INVALID_DECISION`, `HELD_BY_MODERATION`). A
machine-readable error-code convention remains debt.

## Report eligibility

1. Authenticated; `email_verified_at` or `phone_verified_at` set (existing
   identity truth) — checked before the target is looked at (no oracle).
2. Reason in the listing subset; text valid.
3. The listing exists — else 404.
4. Not a listing the account may act on (any authority scope through the real
   chain — never `owner_id`) — **409** (they know it exists).
5. The account's own live report on it → 200 with it (even if the listing has
   since gone out of public view).
6. Public now (`freshness.is_public`), **or** the account dealt with it: a
   conversation it started, a viewing it requested, a contact reveal — from the
   domain tables. Otherwise **404**, the same body as "not found".

## Reason taxonomy (founder D-3)

| UI label | Stored code | Severity |
|---|---|---|
| scam | `SCAM` | HIGH |
| not real / lister not entitled | `FAKE` | HIGH |
| price or key details misleading | `MISLEADING_PRICE` | NORMAL |
| discriminatory | `DISCRIMINATION` | HIGH |
| unsafe property | `SAFETY` | HIGH |
| photos stolen / not this place | `STOLEN_MEDIA` | NORMAL |
| duplicate or spam | `DUPLICATE` | NORMAL |
| other (text ≥ 20) | `OTHER` | NORMAL |

The API takes the stored code. `ILLEGAL_CONTENT`, `IMPERSONATION`, `SPAM` and
`HARASSMENT` are not offered for listings (moderator reclassification only).
Severity is derived on the server and only orders the queue.

Text: optional, ≤ 1000 characters after normalisation (NFC; CR/CRLF → LF;
tab → space; every other control or format character — zero-width, bidi
overrides — removed; trimmed). Never interpreted. Stored for moderators only.

## Snapshot (Phase A §5.4)

An explicit allowlist over the public projection (`ClassifiedOut`, itself built
field by field without street, unit, postcode, exact point, owner or contact):
`title, description, status, space_type, city, district, place,
public_location (the public point and its precision), rent_amount, currency,
admin_fee, utilities_amount, utilities_included, utilities_basis, parking_fee,
deposit_amount, other_costs, monthly_total_estimate, move_in_total` +
`cover_media_id` + `public_generation`. A forbidden-key test pins it.

## Idempotency (Phase A §13, C)

One live report per (reporter, target) — the S1 partial UNIQUE. A repeat, or a
retry after an unknown COMMIT whose first attempt committed, answers **200 with
the live report**; if the first attempt did not commit, the retry creates it.
A duplicate never consumes quota. After resolution a new report is allowed.
The insert runs in a savepoint: should a path ever skip the reporter lock, the
UNIQUE decides and the loser is answered with the live report — and the
constraint error (whose parameters carry the text) never reaches a traceback.

## Quota and rate limit (founder D-4)

* Per account: ≤ 10 new reports in a rolling 24 h of **database time**, ≤ 20
  live. Exact under concurrency: the reporter's `users` row `FOR NO KEY UPDATE`
  (the contact-reveal pattern; compatible with the FK `KEY SHARE` of decision
  and notice inserts), the window read after the lock is granted. Order:
  duplicate → daily → live → insert.
* `REPORT_CREATE` IP policy: burst **5** (D-4); sustained **0.05/s**, inherited
  from the stranger-facing writes (`CONTACT_REVEAL`, `CONVERSATION_START`) —
  D-4 sets none. Moderator routes ride the existing `ADMIN` policy.
* Lock order: users row → reports insert (KEY SHARE on the listing). This path
  locks no property, listing or report row first, so it closes no cycle with a
  decision (property → listing → reports in id order).

## Moderator queue

Live reports grouped by target (no case entity): `target_type, target_id,
listing_id, live_reports, max_severity, oldest_report_at, newest_report_at,
distinct_reporters, phone_verified_reporters, head_decision_id, head_action,
held`. Order: severity rank (URGENT > HIGH > NORMAL, by `CASE`, never text) →
oldest outstanding report → target id. `limit/offset` + `total` (the inbox
convention). Two statements for the page plus one batched head lookup. No
text, reporter contact, address or snapshot. Nothing in the queue acts.

## Target review

`GET …/targets/LISTING/{id}` locks the target's OPEN reports **in id order**
(the order a decision locks them — no deadlock), moves them to IN_REVIEW with
`first_reviewed_at = COALESCE(first_reviewed_at, db now)` (set once; a second
moderator waits, then moves nothing; a report a decision resolved meanwhile
never regresses), and returns: the listing (status, public, generation, current
allowlisted snapshot), the decision head, and each live report with reporter
internal id, email/phone verification flags, reason, severity, text, times and
report-time snapshot. Never the reporter's email or phone, the exact address or
authority documents. Audited `moderation.target_viewed` with `{target_type,
report_ids}` — ids only.

## Decision API

`POST /v1/admin/moderation/decisions` → `apply_listing_decision` (S1): actions
`NO_ACTION`, `CONTENT_EDIT_REQUIRED`, `VISIBILITY_LIMITED`;
`expected_head_decision_id` required (null for none). Extra fields
(`close_engagement`, `report_id`, …) are 422.

* **Stale head → 409 `STALE_HEAD`** naming the current head; never re-aimed.
* **Conflict of interest → 403**: authority over the property (S1), or **any
  live report of the moderator on the target** (S3 — not a caller-selected
  report), re-checked under the report row locks so a report the moderator
  files while the decision is in flight is caught (its insert holds the
  listing's KEY SHARE; the decision waits, then sees it).
* Invalid action/reason for the state → 422; unknown listing → 404.
* Every live report on the target is resolved in the decision's transaction.
  The reporter sees `reviewed` only (L13).

## Owner moderation status

`/me/classifieds` items gain `moderation`. Only a hold is shown (`HELD`,
action, reason code, since); a dismissal or release head reads `NONE` with
nulls — otherwise a dismissal would reveal that someone reported the listing.
`review` is `NONE` (Slice 5). Heads for the whole page come from **one**
statement (`hold.heads`); a test counts statements on `moderation_decisions`.

## Transactional inbox notices (founder D-9)

* Inbox only (`user_notifications`, category TRANSACTIONAL): no email, no
  outbox, no provider, no preference, not `alert_deliveries`.
* Hold (new or changed) → `MODERATION_LISTING_HELD`; release →
  `MODERATION_LISTING_RELEASED` ("may republish"; never republished for the
  owner); dismissal of a listing that was not held → **nothing**.
* Recipients: `authority.holders(property, PUBLISH_LISTING)` — the three
  authority chains read from the property end in one statement; the same
  audience as `/me/classifieds`; distinct.
* Data exactly `listing_id, decision_id, action, reason_code, effective_from`;
  title/body are localisation keys. Never reporter, count, text, explanation
  or address (forbidden-key tests). Legal wording (L2) is template work.
* Written in the decision's transaction (rollback → no notice). Exactly once
  per (decision, manager) without a new key: the decision row is created once
  (head CAS + UNIQUE supersedes; a retry after an unknown COMMIT gets 409), and
  only the inserting call writes its notices.

## Failure semantics (PR-003)

No new engine or unbounded path. Database errors are not caught: 503 by the
PR-003 handlers. Only the narrowed domain refusals and the savepoint
`IntegrityError` are handled. Retry safety: report create (domain key) and
decision (head CAS) are safe to retry; review is idempotent.

## Privacy invariants

Moderator-only: reporter identity, report text, live count, per-reporter
categories, snapshots. Never on the owner API, owner inbox, public listing or
search, metric labels, logs, audit `data`, or `ModerationDecisionRecorded`.
Tests: forbidden keys on owner state, notice data, queue, own reports;
string checks for reporter id / text / explanation in owner views, audit,
events and notices.

## No automatic action

Reports never mutate a target; no count or severity hides, pauses, ranks or
sanctions anything (04 invariant 23). Test: six SAFETY reports leave the
listing active and public with no decision.

## Release policy

No migration: the Slice 1 schema `a3c5e7f9b1d4` carries reports, decisions and
TRANSACTIONAL notices. `release.json`: `NO_SCHEMA_CHANGE`, head = minimum =
maximum = `a3c5e7f9b1d4`, previous release `TASK-015-S1` (same head),
**`rollback_to_previous = BLOCKED`** — operational: rolling back to the S1
build removes report intake and the moderator HTTP operations while their
data stays. Forward repair only. Known gap: no index serves the 24 h window
count `(reporter_user_id, created_at)` — a per-reporter scan bounded by the
statement timeout; an index is a later EXPAND migration if measurement asks.

## Measurement

New: `homies_reports_created_total{target_type,category}` (new committed
reports only — not duplicates, refusals or rollbacks; savepoint-aware via the
shared commit-only counter). Existing: `homies_moderation_decisions_total`.
Offline KPIs available from the tables (DATA-001 not implemented): reports per
active listing, duplicate rate (200s are not stored — derivable only from
request logs; the table gives repeat-after-resolution), time to first review
(`first_reviewed_at − created_at`), time to decision (`resolved_at −
created_at`), action rate, reversal rate (`REINSTATED_DECISION_ERROR` vs
`REINSTATED_REMEDIED`), recovered supply (republish after release: new public
generation). No public trust score; no allegation counts exposed.

## Concurrency (PostgreSQL; `pg_blocking_pids`)

| | Proven |
|---|---|
| R1 | two simultaneous reports by one reporter → one 201 + one 200 with the same id; the partial UNIQUE refuses a direct second live row; the savepoint backstop answers a lockless loser with the existing report |
| R2 | daily and live caps exact under 3 concurrent filers; database-time aging frees a slot; duplicates free at quota |
| R3 | report retry after a real unknown COMMIT (PR-003 proxy): committed → 200 same id; rolled back → 201; one live row |
| R4 | two reviews: the second waits on the first's report locks, moves nothing; `first_reviewed_at` set once; a review after a decision never reopens resolved reports |
| R5 | two decisions through the HTTP handler: one 201, the other 409 `STALE_HEAD`; one decision |
| R6 | moderator among several reporters → 403, nothing written; the moderator's own report racing the decision → decision waits on the listing, then 403; no deadlock |
| R7 | rolled-back decision leaves no notice; committed → one per manager; release notified; dismissal silent; both report lockers lock `ORDER BY reports.id` (structural); 5 parallel review/decision pairs, no deadlock |
| R8 | decision + notice after a real unknown COMMIT: committed → retry 409, one notice; rolled back → retry creates, the lost attempt left no notice; one decision |
| R9 | owner sees before or after an uncommitted decision, never between; reporter never visible; queue order URGENT > HIGH > NORMAL |

## Tests and evidence

Counts (first runs and reruns separately), mutation results and CI: see the
final report and `homies-audit-evidence/TASK-015-S23/`. Mutation classes:
duplicate idempotency bypass, quota lock removed, client severity accepted,
hidden listing without interaction, reporter in the owner notice, report text
/ explanation in audit, report count auto-hold, CoI via one selected report,
stale head re-aimed, notice outside the transaction, dismissal notice,
per-row head query, unordered review locks, quota off-by-one, dismissal shown
to the owner.

## Legal boundary (L1–L13 unresolved; not blocking this build, blocking launch)

Registered users only; inbox notices only; no external notifier; no email; no
formal appeal; no reporter outcome disclosure (L13). Not claimed: DSA
compliance, statement-of-reasons compliance (L2), retention periods (L8),
private-message access policy.

## Known debt

* Slice 4 (message/conversation/viewing/media moderation, participant CoI,
  `close_engagement`); Slice 5 (review requests).
* General Idempotency-Key before the browser launch.
* User block before public launch (D-7); account status revisited (D-6).
* Public `/metrics` (category counts world-readable until ingress restriction).
* JWT clock debt: the local Docker VM wall clock steps backwards (measured up
  to 1.9 s, ~4×/min), so a fresh token's `iat` is "in the future" and is
  refused 401 — the local flake class (MICRO-002). Not fixed here (no JWT
  leeway without a decision).
* Machine-readable error-code convention.
* 24 h window index (above).
* A guest-role agency member who manages a listing receives its notice but
  `/me/classifieds` requires the host role.
* Queue page, total and heads are three statements (three snapshots): a
  decision committing in between can show a group next to its new head.

## Slice 4/5 boundary

Slice 4 adds MESSAGE to `ReportIn.target_type` and the decision target types,
participant conflicts, redaction and engagement effects. Slice 5 adds
`POST /v1/classifieds/{id}/moderation-review` and fills `moderation.review`.
