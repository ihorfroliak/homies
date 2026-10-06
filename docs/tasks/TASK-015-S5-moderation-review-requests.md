# TASK-015 Slice 5 — Moderation review requests (owner reconsideration loop)

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, **not merged**; **production NOT READY · NOT DEPLOYED** |
| Disposition (TASK-016, 2026-10-06) | merged into `main` at `1de34bf550e55c0e4e28d78090f0720d6812287e` (merge of candidate `3146fed392d66421cdaad45e72002c2a536c4b63`); still BUILDER VERIFIED · MILESTONE AUDIT DEFERRED (D-88). The status text is kept as written |
| Risk class | **R2** (authorization, moderation workflow, concurrency) |
| S2+S3 integration | exact candidate `7a51236d12630467736d8f607c7e398b1dd3a82a` merged `--no-ff` into `main` `1a65d381` → **`4bf6610849ce42b17480e498d474c9355b0e1887`** (tree equal to the candidate; head `a3c5e7f9b1d4`) |
| Baseline | `main` `4bf6610849ce42b17480e498d474c9355b0e1887` |
| Branch | `claude/TASK-015-s5-review-requests` |
| Contract | [Phase A](TASK-015-reports-moderation-phase-a.md) §6.2, §7.3, §10, §13; 04a §23 (review request seam); [S1](TASK-015-S1-moderation-core.md); [S2+S3](TASK-015-S23-listing-report-moderation-loop.md) |
| Decisions | **D-95** (this slice) |

```text
hold → manager sees it (/me/classifieds, inbox) → POST …/moderation-review
→ target back in the moderator queue → moderator opens it (sees the note)
→ moderator records the NEXT decision (keep the hold, or release)
→ the request is ANSWERED in that decision's transaction → owner sees the result
```

Not a legal appeal, not a case, not a ticket: no new table, no second state
machine, no answer endpoint, no new notice type. Slice 4 is not started.

## API

`POST /v1/classifieds/{listing_id}/moderation-review` body `{note?}` (extra
fields refused) → **201** `{id, listing_id, status: OPEN, created_at}` ·
**401** · **404** listing missing **or** not the caller's to manage (same body)
· **409** not held / hold not reviewable / review of this hold already open /
3 reviews of this hold episode used · **422** note > 500 after normalisation ·
**503** (PR-003, not caught).

The client names only the listing; the hold is the listing's current head,
resolved by the server under the locks. Creating a request changes nothing
about the listing.

## Authorization and manager-access consistency

Caller = any account that can act on the listing's property with
`PUBLISH_LISTING` through the authority chain (personal, organisation
membership, mandate) — never `owner_id`, a token role, a client id or the
listing's creator. Checked before any lock is taken (a stranger never queues
on the property lock) and again under the lock (an authority revoked while
waiting no longer counts).

**Mismatch found on the baseline and repaired:** `GET /v1/me/classifieds`
required the global role `host` before its authority filter, but an
organisation member may be a `guest` account — `authority.holders` (S3)
sends that AGENT the hold notice, yet they could not open the listing page or
reach the review path. Now `/me/classifieds` is decided by property authority
alone (`get_current_user` + the existing `PUBLISH_LISTING` filter); a guest
with no authority still gets `[]`. The review route uses the same rule.
Nothing else was widened: publish/confirm still require `host` (debt below).

## Eligibility

The current head exists, is `CONTENT_EDIT_REQUIRED` or `VISIBILITY_LIMITED`,
and is `appeal_eligible` (every 1A hold is; a non-eligible hold is refused —
tested with a directly written row). One OPEN request per decision (S1
partial UNIQUE; the check runs under the locks, and an `IntegrityError` from a
lockless path maps to the same 409 without carrying the note into a log).

## Continuous hold episode and the cap of 3

Episode = the head (a hold) and every decision it supersedes, walking
`supersedes_decision_id` back **while each decision is a hold** — one
recursive CTE over the immutable chain, nothing stored. A keep-hold answer
(hold superseding hold) continues the episode; a release (NO_ACTION) ends it;
a later hold starts a new one. Requests counted over all decisions of the
episode; ≥ 3 → 409. Exact under concurrency: the count and the insert run
under the listing row lock that every decision and every request takes.

## Answer semantics

`apply_listing_decision` (S1/S3, unchanged CAS and conflict of interest), after
inserting the decision, applying its effect and resolving reports, marks the
OPEN request on the **superseded** head `ANSWERED` with
`answered_by_decision_id` = the new decision — `FOR UPDATE`, same
transaction. Only a request on the head the decision supersedes can be
answered; the old decision row is never changed. `DecisionOut` carries
`answered_review_request_id`.

* **Keep hold:** a new hold decision superseding the hold; listing stays
  paused; the S3 `MODERATION_LISTING_HELD` notice is sent; same episode.
* **Release:** `NO_ACTION` with `REINSTATED_REMEDIED` /
  `REINSTATED_DECISION_ERROR`; the S3 `MODERATION_LISTING_RELEASED` notice; the
  listing stays paused — the owner republishes through `make_public` (new
  public generation, alerts may fire: D-5).

A conflicted moderator (manages the property, or a live reporter) is still
refused (403) when answering a review.

## Moderator queue and detail

Queue = union of targets with live reports and targets with an OPEN review
request. Review-only rows: `live_reports 0`, `max_severity null`,
`oldest/newest_report_at null` — no invented severity; new fields
`has_open_review_request`, `review_requested_at` (no note). Order: URGENT/HIGH
reports → open reviews → NORMAL-only reports; within a class the oldest
actionable item (report or request), then target id. Once answered with no
live reports the target leaves the queue.

Target detail adds `review_request {id, decision_id, requested_by_user_id,
note, status, created_at}` for the OPEN request on the current hold (no email
or phone). Opening the target does not change the request. The
sensitive-access audit `moderation.target_viewed` now carries
`review_request_id` (ids only).

## Owner projection

`moderation.review`: **OPEN** — the current hold has an OPEN request;
**ANSWERED** — the current hold is the decision that answered a request (the
hold was kept); **NONE** — otherwise. A released listing reads `state NONE`
with every field null, review included — no review history is exposed. One
statement for the page (`reviews.review_states`), next to the one for heads.

## Lock order (final, TASK-015)

| Path | Order |
|---|---|
| decision | property → listing row → head CAS → insert decision → listing pause → reports `FOR UPDATE ORDER BY id` → OPEN review request `FOR UPDATE` → audit → notices → event |
| review request | (authority read) → property → listing row → head → open/episode count → insert request → audit |
| target review | reports `FOR UPDATE ORDER BY id` (OPEN only) |
| report filing | reporter `users` row `FOR NO KEY UPDATE` → reports insert (FK KEY SHARE on the listing) |
| publish / confirm / revoke | property → … (unchanged) |

Review requests are only ever locked or inserted under the listing row lock,
so no new cycle: proven by the parallel stress (deadlock counter unchanged).

## Privacy

The note is moderator-only: never in the owner inbox, a notice, an event,
audit `data`, a metric, logs, the owner/reporter/public APIs. Forbidden-key
and string tests over audit, domain events, notices, `/me/classifieds`,
`/me/inbox`, `/me/reports` and the public listing. Requester id appears only
in the moderator detail.

## Retry semantics (PR-003)

Domain-specific, as Phase A: after an unknown COMMIT of a review request the
retry may answer **409 already open** although the first attempt committed —
a 409 does not mean the request failed. A decision retry after an unknown
COMMIT gets `STALE_HEAD`, and its request is ANSWERED exactly when the
decision committed (proven both branches). No general Idempotency-Key.

## Release policy

No migration (the S1 table has every column needed). `release.json`:
`NO_SCHEMA_CHANGE`, head = minimum = maximum = `a3c5e7f9b1d4`, previous
`TASK-015-S23`, **`rollback_to_previous = BLOCKED`** — operational: the S2+S3
build would strand OPEN requests (no endpoint, no queue re-entry, no answer).
Forward repair only.

## Measurement impact

No new metric. From the tables (DATA-001 not implemented): review requests
per hold, time hold → request, time request → answer, keep vs release after a
review, repeat-review use per episode, recovered supply after a successful
reconsideration (release → republish → new public generation).

## Concurrency (PostgreSQL)

| | Proven |
|---|---|
| S5-R1 | two simultaneous requests: the second waits on the property lock, then 409; one OPEN row |
| S5-R2/R3 | review committed first → the release / keep-hold decision answers it atomically; decision committed first → release: the request is refused (not held); keep-hold: the request attaches to the new hold, never the superseded one |
| S5-R4 | hold → request → keep → request → keep → request → keep: 3 allowed, the 4th and three concurrent attempts refused |
| S5-R5 | after release no request; a new hold gives a fresh 3 |
| S5-R6 | rolled-back decision: request stays OPEN, no `answered_by_decision_id` |
| S5-R7 | unknown decision COMMIT (PR-003 proxy): committed → request ANSWERED, retry `STALE_HEAD`; rolled back → request OPEN, retry answers it; never an OPEN request on a superseded hold |
| S5-R8 | a target whose reports were resolved re-enters the queue with the request (`live_reports 0`, no severity) and leaves when answered |
| S5-R9 | organisation AGENT with a guest account: notice, `/me/classifieds`, 201 review; a stranger: `[]` and the same 404 as a missing listing |
| stress | 5 × (review ∥ release): no deadlock, no OPEN request left on a released listing |

## Evidence (builder, local Docker; first runs and reruns kept apart)

* S5 SQLite suite 15/15 first run; S5 PostgreSQL suite 11 passed / 2 failed
  first run (test-setup bugs: reporting a paused listing) → 13/13.
* Mutation: baseline 28/28; **13/13 killed**, each by its intended test.
* Full SQLite (candidate tree): 1286 passed / 8 failed / 478 skipped → the 8
  rerun: 7 passed, 1 failed again (401) → passed. All 8 were the local JWT
  clock-step 401 class.
* Full PostgreSQL/PostGIS with mandatory restore drill: 1766 passed / 5 failed
  / 1 skipped → 5/5 passed on rerun; every first failure was a 401 /
  `KeyError` on a refused token.
* ruff, mypy (122 files) clean; Spectral 0 errors (49 pre-existing warnings);
  AsyncAPI valid.
* CI on `556823c9` (run 37048911922) failed in the backend Test step; the same
  step failed on `main` `4bf66108` (run 37047555634), whose tree is identical
  to the S2+S3 candidate that passed CI at 09:25 UTC — a failure that does not
  depend on S5 code. The job log is not readable without GitHub
  authentication; see the final report for the rerun.

## Legal boundary (L1–L13 unresolved)

A technical reconsideration seam only. Not claimed: DSA internal complaint
handling, formal appeal, deadlines/SLA (L3), notice wording (L2), retention.

## Known debt

* Slice 4 (messages, conversations, viewings, media; participant CoI;
  `close_engagement`).
* General Idempotency-Key; D-7 user block; public `/metrics`; JWT clock
  (MICRO-002, Docker VM clock steps backwards); machine-readable error codes.
* 24 h report-window index (S2+S3); queue = three statements (total, page,
  heads): multi-snapshot.
* **New:** publish/confirm still require the global `host` role — a guest-role
  organisation agent can request a review but cannot republish after a
  release (an owner/host member can). A wider authority-over-role review of
  the host endpoints is a separate task.

## Slice 4 boundary

Slice 4 adds MESSAGE targets and engagement effects; review requests stay
LISTING-hold scoped until then.
