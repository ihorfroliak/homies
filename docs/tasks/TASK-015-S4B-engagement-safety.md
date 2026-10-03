# TASK-015 Slice 4b — Engagement safety: conversations, viewings, photos

| Field | Value |
|---|---|
| Status | **BUILDER VERIFIED · MILESTONE AUDIT DEFERRED** (D-88) — candidate on its branch, integrated into the PROGRAM-001 branch, **not merged to `main`**; **production NOT READY · NOT DEPLOYED** |
| Risk class | **R2** (authorization, concurrency, private engagement, rollback barrier) |
| S4a integration | exact candidate `ff433303948bdf5b5097de757fc5615b3edc56e6` (externally reviewed, CI 37080274514) merged `--no-ff` into `main` `1de34bf5` → **`03268432f664ec6283f427b2f528a8bb6f814065`** (tree equal to the candidate) |
| Baseline | `main` `03268432`, then PROGRAM-001 P0 (`claude/PROGRAM-001-p0-ci-evidence-hygiene`) |
| Branch | `claude/TASK-015-s4b-engagement-safety` |
| Contract | [Phase A](TASK-015-reports-moderation-phase-a.md) §6.2, §11, §14; [S4a](TASK-015-S4A-message-moderation.md); PROGRAM-001 master prompt §11 |
| Decisions | **D-97**; founder **G-14** (re-contact) |
| Legal | **L11** (counterpart/requester notice wording) open — neutral keys only |

## What changes

| Target / path | Action | Effect |
|---|---|---|
| LISTING | `VISIBILITY_LIMITED` + `close_engagement: true` — **only** with reason SCAM, FAKE or SAFETY | the hold (unchanged) **plus**: every ACTIVE conversation of the listing → CLOSED with a neutral SYSTEM line; every REQUESTED/CONFIRMED viewing starting after the decision → CANCELLED (`cancelled_at` = the decision's instant); a TRANSACTIONAL notice to each affected viewing requester |
| LISTING | `CONTENT_EDIT_REQUIRED`, `VISIBILITY_LIMITED` without the flag | unchanged (S1): engagement is untouched — a correctable hold never destroys it. `close_engagement` with any other action or reason → **422** |
| viewing confirm | — | refused while the listing is held: **409 `LISTING_HELD`** (decline and cancel stay possible) |
| viewing request, new conversation | — | unchanged rule (a held listing is paused, so not public → 404), now read under the listing lock |
| CONVERSATION | `FEATURE_RESTRICTED` (reason: a report category) | CLOSED + neutral SYSTEM line; **terminal** (canon defines no reopening): any successor → 422. The requester cannot open a new conversation on the listing for the same public generation (**G-14**, 409 `RECONTACT_BLOCKED`); a republish (new generation) lifts it |
| CONVERSATION | `NO_ACTION` (`NOT_A_VIOLATION`) | dismissal, only before a restriction |
| MEDIA | `CONTENT_REMOVED` (reason: a report category) | `moderation_state = RESTRICTED`; **non-destructive** — FileObject, MediaAsset, every ListingMedia link and the bytes stay; the public serve and the public projection (APPROVED only) drop it; attach/cover/reorder of it → 409; managers get a TRANSACTIONAL notice; terminal in this slice |
| MEDIA | `NO_ACTION` (`NOT_A_VIOLATION`) | dismissal, only before a restriction |
| send message | — | the conversation row is locked first and its status read under the lock: **409 `CONVERSATION_CLOSED`** after any committed closure |

`DecisionIn` gains `target_type` CONVERSATION and MEDIA, `close_engagement`
(LISTING only) and `listing_id` (MEDIA only: the listing the photo was seen
on, which must show it). `DecisionOut` gains `closed_conversations` and
`cancelled_viewings`. `ViewingOut` gains `cancelled_by_homies`. The LISTING
target view lists every linked photo with its state; new moderator routes:
`GET /v1/admin/moderation/targets/MEDIA/{id}` (state, listings, head) and
`GET /v1/admin/moderation/media/{id}/content` (the sanitised bytes,
`Cache-Control: private, no-store`, every access audited) — without them a
moderator could not see a held listing's photos, because the public serve
refuses anything not public.

The SYSTEM line body is the stable key `system.conversation_closed_by_homies`;
the client renders it ("Zamknięte przez Homies"). It never carries a reporter,
an allegation, a reason or a moderator's words.

## Why no schema change

Every column already exists since S1 (`moderation_decisions` CONVERSATION and
MEDIA targets, `close_engagement`, `listing_public_generation_at_decision`;
`media_assets.moderation_state` RESTRICTED). "Cancelled by Homies" is derived
exactly, not stored: such a viewing's `cancelled_at` equals the
`effective_from` of a close-engagement decision on its listing, and a user's
cancellation cannot carry that instant (both are written under the viewing's
row lock). G-14 uses the decision's recorded public generation.

## Lock order (final for TASK-015)

| Path | Order |
|---|---|
| listing decision (incl. close_engagement) | property → listing `FOR UPDATE` → conversations `FOR UPDATE ORDER BY id` → viewings `FOR UPDATE ORDER BY id` → reports(id) → review request |
| conversation decision | listing `FOR KEY SHARE` → conversation `FOR UPDATE` → head CAS → effects → reports(id) |
| message decision (S4a, reordered in S4b) | listing `FOR KEY SHARE` → conversation → message → head → reports(id) |
| message report | reporter users row → listing `FOR KEY SHARE` → insert (FK checks) |
| media decision | media asset `FOR UPDATE` → head CAS → state → reports(id) |
| send message | conversation `FOR UPDATE` |
| start conversation | listing `FOR SHARE` → reporter users row (`FOR NO KEY UPDATE`) → the continued thread `FOR UPDATE` |
| request viewing | listing `FOR SHARE` → viewing settings `FOR UPDATE` |
| confirm viewing | listing `FOR SHARE` (hold read under it) → viewing settings `FOR UPDATE` → viewing `FOR UPDATE` |
| decline / cancel / outcome | viewing `FOR UPDATE` only |
| attach photo | media asset `FOR SHARE` |

Every path that also takes the listing takes it first — including the
implicit `FOR KEY SHARE` a foreign-key check takes when a row referencing the
listing is inserted; paths that lock only their own row never wait on a
listing while holding it (stress test and E-R11/E-R12: deadlock counter
unchanged).

**Defect found by the PostgreSQL suite and fixed** (`core.db.lock_row`):
`SELECT … FOR SHARE` on an entity with a joined eager relationship fails in
PostgreSQL ("FOR SHARE cannot be applied to the nullable side of an outer
join") — SQLite ignores row locks and hid it. Row locks are now taken on the
bare id, then the entity is re-read under the lock.

**Ordering defect found and fixed:** the closure line was stamped with the
decision's instant (its transaction's start), which can precede a message
that committed while the decision waited for the row; it is now stamped no
earlier than 1 µs after the latest message, read under the conversation lock.

## Adversarial review (specialist agent, read-only) and repairs

| # | Finding | Severity | Repair |
|---|---|---|---|
| F1 | upload review (`/admin/media/{id}/approve|reject`) could re-approve or reject a RESTRICTED photo — serving it again on every listing, or deleting its links; a concurrent approve could overwrite RESTRICTED | P1 | the asset row is locked; RESTRICTED → **409 `MEDIA_RESTRICTED`** (only its decision chain changes it) |
| F2 | a conversation/message decision held its conversation and then inserted a decision referencing the listing (FK check = `FOR KEY SHARE`), while close_engagement held the listing and waited for the conversation → deadlock (40P01 → 500) | P2 | listing `FOR KEY SHARE` first in conversation and message decisions and in message-report filing; E-R11/E-R12. (A first attempt — the listing decision taking `FOR NO KEY UPDATE` — broke S3 invariant R6, a moderator's own concurrent report being caught, and was reverted.) |
| F3 | FEATURE_RESTRICTED on an already closed conversation recorded the listing's *current* generation for G-14 | P3 | only an ACTIVE conversation can be restricted (422) |
| F4 | lead assign/stage incremented the version unlocked (could overwrite a closure's version bump) | P3 | the conversation row is locked first |
| F5 | (hypothesis) FK trigger order after a restore could invert report locks | P3 | covered by F2's explicit listing lock in report filing |
| F6 | a restricted requester may still request a viewing on the same publication (G-14 covers conversations) | — | **PROPOSED FOUNDER DECISION** — not changed |

## Invariants and their proof (PostgreSQL, `tests/test_engagement_safety_pg.py`)

| | Race / case | Proven |
|---|---|---|
| E-R1a | closure first, send waits | send blocked on the conversation row, then 409; no message after the closure |
| E-R1b | send first (held at COMMIT), closure waits | the message stands, the closure follows; the SYSTEM line is last |
| E-R1c | continuing a thread vs its restriction | start blocked on the thread, then 409 RECONTACT_BLOCKED; no message |
| E-R2 | two moderators restrict | one decision; the second `STALE_HEAD` naming the first; one SYSTEM line |
| E-R3a/b | close_engagement vs send (both orders) | as E-R1 |
| E-R4a | decision first, confirm waits | confirm blocked on the listing, then 409 LISTING_HELD; viewing CANCELLED |
| E-R4b | confirm first (held at COMMIT), decision waits | the decision then cancels the confirmed viewing |
| E-R5 | decision first; new request and new conversation wait | both 404 after it; nothing ACTIVE or held remains |
| E-R5b | new conversation first (held at COMMIT) | the decision that waited closes it too |
| E-R6 | requester's cancel first | stays their own (`cancelled_by_homies: false`); the decision cancels nothing |
| E-R7 | photo restriction vs public serve | served until the commit (read committed), never after; the link stays |
| E-R8 | photo restriction vs attach | attach blocked on the asset row, then 409; no link |
| E-R9 | rolled-back close_engagement | no status change, SYSTEM line, cancellation, decision, audit, notice or event |
| E-R10 | decision COMMIT outcome unknown (PR-003 proxy) | committed → retry STALE_HEAD; rolled back → retry applies; exactly one SYSTEM line |
| stress | 4 × (close_engagement ∥ restriction ∥ send ∥ confirm) | deadlock counter unchanged; final state consistent |
| order | closure line vs a later-stamped message | the SYSTEM line is last; cancellations carry the decision's instant |
| E-R11 | conversation decision vs close_engagement | close_engagement waits at the listing; no deadlock |
| E-R12 | message decision vs close_engagement | the message decision waits at the listing; no deadlock |

SQLite behaviour suite: `tests/test_engagement_safety.py` (validation
matrix, effects, history untouched, hold vs confirm, G-14 incl. republish,
terminality, conflict of interest, photo non-destructiveness and moderator
endpoints, privacy canaries over SYSTEM lines, notices, events and audit,
rollback of a refused decision).

## Release policy — safety rollback barrier

`release.json`: `NO_SCHEMA_CHANGE`, head = minimum = maximum = `a3c5e7f9b1d4`,
previous `TASK-015-S4a`, **`rollback_to_previous = BLOCKED` — SAFETY
BARRIER**: the S4a build confirms viewings on a held listing, lets a
closed-out requester open a new conversation on the same publication (G-14)
and checks a conversation's status without locking it. The S4a privacy
barrier still stands behind it. Forward repair only.

## Known debt (classified)

* **Upload rejection is destructive** (`media.router._moderate` deletes
  listing links for REJECTED) — by design for a photo that never passed
  review; trust moderation does not use it. NORMAL DEBT.
* **Photo cache window:** `/v1/media/{id}` sends `max-age=300`, so a client
  that already fetched a photo may keep it ≤ 5 minutes after restriction.
  Documented exposure window; no CDN exists. NORMAL DEBT.
* Conversation restriction, message removal and photo restriction are
  terminal (no restoration flow). PRODUCT DECISION LATER.
* A photo restriction does not unpublish a listing that falls below a photo
  minimum (none is enforced today). IMPLEMENTATION DEFAULT.
* L11 wording of the closure line and of the viewing-cancellation notice.
  BETA BLOCKER (legal).
* General Idempotency-Key (a send retried after an unknown COMMIT can
  duplicate): BETA BLOCKER for the messaging UI.
