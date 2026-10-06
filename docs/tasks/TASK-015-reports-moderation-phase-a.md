# TASK-015 — Reports & Moderation Basics · Phase A (delta review and implementation contract)

| Field | Value |
|---|---|
| Status | **TASK-015 COMPLETE FOR PHASE 1A** (PROGRAM-001, 2026-10-03): S1, S2+S3, S5, S4a merged to `main`; S4b and the closure (restore-drill coverage) are PROGRAM-001 candidates, **not merged to `main`**. The S6 hardening slice was absorbed into S4b and the closure — **there is no S6**. Production NOT READY, NOT DEPLOYED. *(Phase A contract text below is kept as written.)* |
| Disposition (TASK-016, 2026-10-06) | contract on `main` at `985db7ae116aca5e37984b8e46556e0859792313` (merge of `2d4064b01c2a68d5e0f62e30fffc303a41ca9ad2`); S4b and the closure (`50f2f521abe3a245442d93f4da8088a0cf44ed7e`) reached `main` with PROGRAM-001 at `c32ac63f9a4c08366369a2088709b658754373e6`, so every TASK-015 slice is on `main`. The status text is kept as written |
| Risk class (implementation) | **R2** (authorization, publication gating, privacy, migration) |
| Roadmap | 06 Phase 1A item 6 — "Reports and moderation basics; incidents" (incidents: see §3, non-goal for this slice) |
| Baseline | `main` `451b7e566a1958097b2df2266e2bb7cc41314621` = IBB-001 + MICRO-001 + PR-002 + PR-003 (PR-003 merged by this task's entry gate: parents `13a92ef7` + `e54b3eec`) |
| Branch | `claude/TASK-015-phase-a-reports-moderation` (documentation only; not merged) |
| Canon | 04 §64 `trust.reports`, §65 `trust.moderation_decisions`, §66 `trust.incidents`, §68 audit, §70–71 notification categories, §50 publication validator, invariants 21 and 23; 04a §5 (actor), §22 (no account status in 1A); 07 doctrine |
| Evidence (outside the repository) | `homies-audit-evidence/TASK-015-phase-a/`: `PHASE-A-REPORT.md`, `subagents/DOMAIN-AUTHZ-DELTA.md` (A), `TRUST-SAFETY-DELTA.md` (B), `TASK015-MEASUREMENT-DELTA.md` (C) |
| Prior input | Phase A draft of 2026-09-29 at `196c887` — used only as a list of claims; superseded by this contract where they differ (§2.9) |

---

## 1. What this contract answers

The minimum correct Phase-1A reports/moderation slice for the system **as it is
at `451b7e5`**: which objects can be reported, the smallest moderator workflow,
how moderation reaches public visibility without a second state machine, what
happens to dependent objects, who may do what, what stays private, how retries
behave after PR-003's "outcome unknown", what to measure, what legal questions
remain open, and the exact slices to build.

## 2. Current-state findings (evidence; file:line in subagent A's report)

### 2.1 Visibility: one rule, one entry
* **One public-visibility rule:** `freshness.public_clause` / `is_public` =
  `status='active'` and confirmed within 21 days. It is used by search, map,
  detail, contact reveal, conversation start, viewing slots/request, media
  serving, saved listings, alert matching, alert reconciliation and send-time
  revalidation. A listing that is not `active` disappears from **every** public
  path at once.
* **One entry into `active`:** `publicity.make_public` (row `FOR UPDATE`, CAS on
  status + `public_generation`, opens an alert episode). Its only callers are
  publish (`properties/router.py:530`) and confirm (`:684`). No other Phase-1
  code writes `active` — but **no test enforces that**.
* `confirm_classified` **ignores `make_public(...).applied`**: a refusal would
  be returned as 200 with the old state. Must be fixed with the hook.
* Listing statuses in code: `draft, active, paused, stale, archived`. **Nothing
  writes `archived`** (no listing-archive path). Owner pause writes no audit row.
  Canon statuses `PENDING_REVIEW`, `status_reason_code` and status history are
  not implemented.

### 2.2 Moderation that already exists
* **Media:** `moderation_state` PENDING / APPROVED / REJECTED / RESTRICTED;
  `POST /v1/admin/media/{id}/approve|reject`. No transition guard, no lock, no
  reason; **reject deletes the asset's listing links and re-approve does not
  restore them**; nothing writes RESTRICTED although the serve filter already
  hides any non-APPROVED asset.
* **Authority revoke** (admin): pauses the property's `active` listings only
  when no other VERIFIED publishing authority remains; blocks new publication.
* **No listing moderation of any kind** — admins have no listing endpoint.
* **No reports, decisions, holds, account status, user block.**

### 2.3 Identity and authorization
* `users.role` ∈ guest | host | admin (no CHECK); `admin` only via the ops
  script; no role-change endpoint. `require_role` reads the role **from the
  database on every request** (the JWT claim is never trusted). No moderator
  role in code or canon.
* No `users.status`; 04a §22: "Phase 1A has no account deletion/status model …
  no parallel account lifecycle".

### 2.4 Audit and events
* `audit_log`: untyped `actor` (user id or `"system"`), app-clock `created_at`,
  append-only in three layers (ORM guard, `*_append_only` trigger, grants
  revoked for every table with such a trigger — new immutable tables are covered
  by naming alone). `GET /v1/admin/audit` returns `data` verbatim → ids and
  codes only. Roadmap item 1 (actor type) is still open.
* `domain_events`: PascalCase fact names, ids-only payloads, `dedup_key`
  `Type:id[:n]`, append-only, **no `event_version`**. `ROUTING` resolves
  recipients through **legacy booking/listings imports** — never route a
  moderation event through it. `IncidentOpened` is a taken legacy name.

### 2.5 Dependent objects when a listing stops being public
| Object | Today |
|---|---|
| saved listing | tombstone `NO_LONGER_AVAILABLE`, no reason leaked |
| saved-search alerts | queued deliveries suppressed `listing_not_public`; new episode → `not_public` |
| contact reveal | new and repeat reveals 404; past disclosures irrevocable |
| new conversation / viewing request | 404 |
| **existing conversation** | **both sides can still read and send** (send checks only `conversation.status`) |
| **pending viewing** | **provider can still confirm**; confirmed viewings survive |
| owner view `/me/classifieds` | shows `paused` with **no reason** |

So **hide ≠ freeze**: hiding protects new seekers, not those already in contact.

### 2.6 Conversations, messages, notifications
* `conversations.status` ACTIVE / ARCHIVED / CLOSED — nothing sets CLOSED;
  `send_message` reads status without a lock. Messages: `redacted_at`,
  `redaction_reason_code` exist but **the read path still returns the body**;
  `message_type SYSTEM` exists (system messages need no sender).
* Notification categories in code: PRODUCT only (CHECK on three TASK-014
  tables). Canon §70 already defines TRANSACTIONAL / SUPPORT / SECURITY …;
  `user_notifications.delivery_id` is nullable — an inbox row without an alert
  delivery is possible.

### 2.7 Rate limiting
Per-IP, per-process token buckets; an unregistered route falls back to the
PUBLIC_READ budget (120 burst, 10/s). Per-account volume is bounded only by DB
quotas (contact reveal, conversation start) — the pattern a report quota must
follow.

### 2.8 Legacy
`Incident` model (booking-keyed), `/admin/incidents` (`admin/legacy.py`),
`INCIDENT_OPENED` routing, disputes/chargebacks — **DORMANT, not reused** (§4).

### 2.9 Prior draft (`196c887`) — what changed
| Prior claim | Now |
|---|---|
| owners can archive listings | **false** — no archive path |
| a hold inherits everything automatically | **false** — conversations and pending viewings keep working |
| notification category needs a canon decision | **false** — canon §70 has it; an implementation choice + CHECK widening |
| Alembic head `f3b5d7e9a1c2` | **changed** — `0c4e6a8b2d91`; migrations declare `schema_transition` / `rollback_to_previous` (PR-002) |
| F13RA-N01 cleanup belongs in TASK-015 | **obsolete** — closed by MICRO-001 |
| ModerationCase entity + RECEIVED/LINKED report states | **not adopted** (§6.3) — no canon change needed |
| `listing_moderation_holds` table | **not adopted** — the hold is derived from the canonical decision chain (§6.4) |

---

## 3. Scope

**In (Phase-1A slice):**
1. Signed-in users report a **listing** or a **message** (§5.1).
2. Moderators (today: `admin`) see a **queue grouped by target**, open the
   context, and record **immutable decisions** (canon §65).
3. Listing actions through the **existing lifecycle** (`paused`) plus a
   **publication hold derived from the decision chain**, enforced in
   `make_public`.
4. Message redaction, conversation close, non-destructive media restriction,
   refusal of new viewing confirmations on a held listing, and — only for
   upheld scam/safety — closing that listing's conversations and cancelling its
   future viewings.
5. Owner-visible moderation status of their own listing, a transactional inbox
   notice with a policy reason, and one **review request** per hold.
6. Reporter-visible status of their own reports.
7. Audit rows, one domain event per decision, two bounded counters.

**Non-goals (explicitly rejected for this slice):** support CRM / ticketing;
law-enforcement portal; payment, booking or deposit disputes; short-stay safety
operations; **trust.incidents** (canon §66 — property-safety incidents belong
with roadmap item 7, safety foundation; the legacy booking `Incident` stays
dormant); fraud ML, keyword/image detection, AI moderation; trust or reputation
scores; public "reported" badges; automatic takedown on report count;
automated bans; **account status / suspension** (04a §22; §17 D-6); user block
(deferred, §17 D-7); evidence uploads; anonymous / non-registered notices
(legal question L1); reporting PROPERTY, USER or MEDIA directly (§5.1);
pre-publication text review; four-eyes review; reporter reliability scoring;
DATA-001 envelope/versioning; general Idempotency-Key.

## 4. Reuse classification

| Component | Class | Use |
|---|---|---|
| `freshness.public_clause` / `is_public` | **REUSE unchanged** | hiding = `paused`; every public path follows |
| `publicity.make_public` | **REUSE + hook** | hold check under its row lock |
| owner-pause conditional UPDATE | **ADAPT** | moderation pause with property lock + row lock + audit |
| `coordination.lock_property` and lock order (properties → spaces → authorities → offers) | **REUSE** | every moderation write |
| `authority.revoke` | **REUSE as separate lever** | authority fraud |
| `require_role("admin")` | **ADAPT** | behind a new `can_moderate(user)` seam |
| media `_moderate` | **ADAPT** | RESTRICTED writer, transition rules, row lock, reason; reject stays as is |
| `MediaAsset.moderation_state` RESTRICTED | **REUSE** | serve filter already hides it |
| `Message.redacted_at` / `redaction_reason_code` | **ADAPT** | read path must blank the body |
| `Conversation.status` CLOSED + send guard | **ADAPT** | writer + lock on send |
| `message_type SYSTEM` | **REUSE** | neutral "closed by Homies" line |
| viewing statuses (CANCELLED) | **ADAPT** | moderation cancel; confirm refused under hold |
| `audit_log` / `audit()` | **REUSE (secondary trail)** | ids and codes only |
| `*_append_only` trigger + `app_grants.sql` | **REUSE** | decisions table covered by naming |
| `domain_events` / `events.emit` | **ADAPT** | direct emit in a savepoint, unique dedup key, **never `ROUTING`** |
| `UserNotification` (nullable `delivery_id`) | **ADAPT** | TRANSACTIONAL notices; widen that table's CHECK only |
| rate limiter `Policy` | **REUSE** | new `REPORT_CREATE` policy; moderation under `/v1/admin` → ADMIN |
| `alert_deliveries` / alerts worker | **DO NOT REUSE** | listing-episode specific |
| `notifications` outbox (OAT-03) | **DO NOT REUSE** | booking/role recipient model |
| `Incident`, `/admin/incidents`, `INCIDENT_OPENED` | **DORMANT** | booking-keyed; canon §66 is a different aggregate |
| `payments/disputes.py` | **DORMANT** | money domain |
| `set_organization_status` / `set_legal_party_status` | **DO NOT REUSE (v1)** | block only future publication; no takedown |
| `FILE_PURPOSES` `REPORT_EVIDENCE` | **RESERVED** | no uploads in v1 |

## 5. Product scope

### 5.1 Report targets (Q1)

| Target | Phase 1A | Why |
|---|---|---|
| **LISTING** | **yes** | the public surface; scams, fakes, misleading and discriminatory listings live here |
| **MESSAGE** | **yes** | harassment and scams after first contact live here; the conversation gives the moderator context |
| MEDIA | **not user-facing** | users report the listing ("photos are stolen / not this flat" = `STOLEN_MEDIA`); moderators act on media inside the listing context |
| USER | deferred | without account status there is no proportionate user-level action; message and listing reports cover the evidence |
| PROPERTY | deferred | a property is private; its public face is the listing |
| VIEWING | deferred | viewing misconduct is reported through the conversation's messages; no separate surface |

### 5.2 Who may report
* Signed-in users only; **no anonymous reports** (Q9).
* A verified **email or phone** is required (email keeps victims without SMS
  able to report).
* LISTING: any such user, the listing must currently be public **or** the
  reporter must have a conversation, viewing or contact reveal on it (a hidden
  listing remains reportable by those who dealt with it).
* MESSAGE: only a **participant** of the conversation, and not about their own
  message.
* Nobody may report their own listing (authority chain) — 409.

### 5.3 Reason taxonomy (Q2)
Stored as canon §64 codes; the UI offers a smaller set; moderators may
reclassify (a reclassification is part of the decision record).

| Surface | User-facing reasons → stored canon code |
|---|---|
| LISTING (8) | scam → `SCAM`; not real / lister not entitled → `FAKE`; price or key details misleading → `MISLEADING_PRICE`; discriminatory → `DISCRIMINATION`; unsafe property → `SAFETY`; photos not of this place / stolen → `STOLEN_MEDIA`; duplicate or spam → `DUPLICATE`; other → `OTHER` |
| MESSAGE (6) | harassment → `HARASSMENT`; scam or impersonation → `SCAM`; discriminatory → `DISCRIMINATION`; threat or safety → `SAFETY`; spam → `SPAM`; other → `OTHER` |
| moderator-only | `ILLEGAL_CONTENT`, `IMPERSONATION`, `SPAM` on listings |

* Free text: optional, ≤ 1 000 characters, required (≥ 20) only for OTHER;
  plain text, control characters stripped; rendered as plain text (no links)
  to moderators; never echoed to the target, never in logs/metrics/events.
* Severity is **derived** (server-side, never client-provided): `SAFETY` →
  HIGH, `SCAM`/`FAKE`/`DISCRIMINATION`/`HARASSMENT` → HIGH, else NORMAL.
  `URGENT` is unused (not an emergency channel): SAFETY reasons show static
  "in danger, call 112" guidance.
* Using `MISLEADING_PRICE` for "key details" is a label widening, recorded as a
  04a clarification candidate (§17 D-3), not a blocker.

### 5.4 Evidence
No uploads. LISTING: the server stores a **snapshot** of the public fields at
report time (title, description, price components, public location precision,
cover media id, `public_generation`) — future edit endpoints cannot rewrite the
evidence. MESSAGE: a reference (messages are immutable; the moderator reads the
original body even after redaction).

### 5.5 Duplicates (Q11 detail)
At most **one live report per (reporter, target)** — DB partial UNIQUE over
`status IN ('OPEN','IN_REVIEW')`. Creating it again returns **200 with the
existing report** (`created: false`), same shape as 201. After resolution a new
report is allowed (new conduct). Many reporters on one target are **grouped in
the queue**, not merged.

### 5.6 Response semantics (reporter)
`201` created / `200` already reported (same body) / `404` target not
reportable for this user (indistinguishable from not found) / `409` own listing
or own message / `422` invalid reason or text / `429` quota or rate limit / `503`
per PR-003. The reporter later sees only `received` or `reviewed` — never the
action taken (L13).

## 6. Moderator workflow, actions and state ownership

### 6.1 Minimum workflow (Q3)
```text
report OPEN ─(moderator opens target)→ IN_REVIEW ─(decision on target)→ RESOLVED
                         └────────────(decision on target)────────────→ RESOLVED
```
* `TRIAGED` and `CLOSED` (canon) are not used in 1A: severity is derived at
  creation (no separate triage team), and RESOLVED is terminal. Not using two
  canonical values is not a contradiction.
* `IN_REVIEW` is set (and `first_reviewed_at` set once) when a moderator opens
  the target's detail — the measurement anchor for time-to-first-review.
* One decision resolves **all** live reports on its target in the same
  transaction (`resolution_decision_id`).
* Moderators may also decide **without** a report (own initiative) — so a
  decision never proves that a report exists (reporter protection).

### 6.2 Actions (Q4) — canon §65 names, Phase-1A subset

| Action | Target | Effect (existing lifecycle) | Owner/counterpart effect |
|---|---|---|---|
| `NO_ACTION` | any | resolves reports; **also used to release a hold** (`supersedes` the hold, reason `REINSTATED_REMEDIED` or `REINSTATED_DECISION_ERROR`) | release: owner notified "you may republish" |
| `CONTENT_EDIT_REQUIRED` | LISTING | moderation pause (`paused`) + hold | correctable: conversations and viewings untouched; owner notice + review request |
| `VISIBILITY_LIMITED` | LISTING | moderation pause + hold; option `close_engagement` (only with reason SCAM, FAKE or SAFETY): close the listing's ACTIVE conversations (SYSTEM line) and cancel its future REQUESTED/CONFIRMED viewings | owner notice; counterparts get a neutral "closed by Homies" line, no allegation (L11) |
| `CONTENT_REMOVED` | MEDIA | `RESTRICTED` (non-destructive; links kept) | owner notice |
| `CONTENT_REMOVED` | MESSAGE | redaction (`redacted_at`, reason) — participants see "removed by Homies" | — |
| `FEATURE_RESTRICTED` | CONVERSATION | `CLOSED` + SYSTEM line | both participants see "closed by Homies" |
| (existing) authority revoke | PropertyAuthority | unchanged admin endpoint; the decision records the reason | — |

Not in 1A: `WARNING` (no channel beyond the notice itself), `ACCOUNT_LIMITED`,
`ACCOUNT_SUSPENDED`, `ACCOUNT_TERMINATED` (no account status — §17 D-6),
escalation (single moderator; severity orders the queue).

### 6.3 Why no ModerationCase entity
Canon has reports + decisions only. Everything a case would own is derivable:
the queue groups live reports by `(target_type, target_id)`; the current state
of a target is the head of its decision chain (§6.4); concurrency is a CAS on
that head. A case table would be a new aggregate (a canon change) for no
Phase-1A invariant. If volume later needs assignment/SLA, a case table can be
added additively over the same reports.

### 6.4 State model (relationship of lifecycles)
Three orthogonal things, no combined enum:

| Concern | Owner | States |
|---|---|---|
| listing lifecycle | `classified_offers.status` (existing) | draft / active / paused / stale / archived |
| public visibility | `freshness.public_clause` (existing, **unchanged**) | derived: active ∧ fresh |
| moderation of a target | **decision chain** in `moderation_decisions` (new, immutable) | head action ∈ {none, NO_ACTION, CONTENT_EDIT_REQUIRED, VISIBILITY_LIMITED, …} |
| report handling | `reports.status` (new) | OPEN / IN_REVIEW / RESOLVED |

* **Hold** = the listing's chain head is `CONTENT_EDIT_REQUIRED` or
  `VISIBILITY_LIMITED` (no `effective_until` in 1A). Derived, not stored twice.
* **Moderation action on a listing** = in one transaction: property lock →
  offer row lock → `status IN (draft, active, stale, paused) → paused` → insert
  decision → resolve reports → audit → event → notice.
* **Publication** = `make_public` reads the chain head **under its row lock**
  and refuses while held (`HeldByModeration`), mapped to 409 with a stable code
  in publish **and** confirm (fix the ignored `.applied`).
* **Release** = a `NO_ACTION` decision superseding the hold. It does **not**
  set `active`: the owner republishes through `make_public` (freshness is the
  owner's attestation; a moderator cannot confirm availability for them).
* Why `paused` (and not a new status or a visibility column): every public path
  already treats `paused` as hidden; old releases (N−1) do too — a new column in
  the public rule would be ignored by an N−1 reader and show held listings
  during a rolling deploy or rollback. The remaining N−1 gap (old `make_public`
  ignores holds) is why the migration is `rollback_to_previous = BLOCKED`.
* Property persists; only the listing's publication is moderated.

### 6.5 Concurrency of decisions
Every decision request carries `expected_head_decision_id` (null when none).
Under the target's row lock the server compares it with the chain head: equal →
insert (the new row's `supersedes_decision_id` = the old head); different → 409
with the current head. `UNIQUE(supersedes_decision_id)` makes a fork
impossible even without the lock.

## 7. Domain model (proposal for Slice 1)

### 7.1 `reports` (canon §64 + refinements)
| Column | Notes |
|---|---|
| canon: `id`, `reporter_user_id` (FK users; nullable per canon, API requires it), `target_type` (LISTING, MESSAGE in 1A; CHECK lists canon five), `target_id`, `category` (CHECK canon 12), `description`, `severity` (derived), `status` (CHECK OPEN/TRIAGED/IN_REVIEW/RESOLVED/CLOSED), `external_ticket_id` (unused), `created_at` (DB `now()`), `updated_at`, `resolved_at`, `version` | |
| `listing_id` | context: the listing, or the message's conversation listing (queue grouping, owner scope) |
| `conversation_id` | MESSAGE reports only |
| `snapshot` JSONB | LISTING: public fields at report time (§5.4); ids and public values only |
| `listing_public_generation_at_report` | measurement (exposure) |
| `first_reviewed_at` | set once |
| `resolution_decision_id` | FK decisions |

* Invariants: partial UNIQUE `(reporter_user_id, target_type, target_id) WHERE
  status IN ('OPEN','IN_REVIEW')`; CHECK MESSAGE ⇒ `conversation_id` not null;
  queue index `(status, severity, created_at)`; target index `(target_type,
  target_id) WHERE status IN ('OPEN','IN_REVIEW')`.
* Persists beyond the listing (history). Privacy: **moderator-only** except the
  reporter's own status view. Retention: L8.

### 7.2 `moderation_decisions` (canon §65 + refinements) — immutable
| Column | Notes |
|---|---|
| canon: `id`, `report_id` (the report under review, nullable), `target_type`, `target_id`, `action` (CHECK canon 9), `reason_code` (CHECK, closed list), `explanation` (moderator-internal), `decided_by_user_id` NOT NULL, `effective_from` DB `now()`, `effective_until` (null in 1A), `appeal_eligible`, `created_at` DB `now()` | |
| `supersedes_decision_id` | UNIQUE — the chain (§6.5) |
| `listing_id` | context for LISTING/MEDIA/MESSAGE/CONVERSATION targets |
| `reclassified_category` | when the moderator changes the report category |
| `close_engagement` | boolean (VISIBILITY_LIMITED only) |
| `listing_public_generation_at_decision` | measurement |

* Trigger `moderation_decisions_append_only` (→ grants revoked automatically,
  startup check covers it). `actor_kind` is not added: 1A decisions are always
  USER (canon NOT NULL `decided_by_user_id`); the typed actor arrives with
  roadmap item 1.
* `reason_code` closed list: the 12 canon categories plus
  `REINSTATED_REMEDIED`, `REINSTATED_DECISION_ERROR`, `NOT_A_VIOLATION`.
* Persists (canon §75 keeps moderation decisions). Privacy: moderator-only;
  the owner sees action + reason code + date only.

### 7.3 `moderation_review_requests` (minimal)
`id`, `decision_id` (the hold), `requested_by_user_id`, `note` (≤ 500, plain),
`status` OPEN/ANSWERED, `answered_by_decision_id`, `created_at`. Partial UNIQUE
one OPEN per decision; per-hold cap (3). Why a table: the reconsideration seam
the canon `appeal_eligible` flag implies, without an appeal state machine.

### 7.4 Changes to existing tables
* `user_notifications.category` CHECK widened to `('PRODUCT','TRANSACTIONAL')`
  (only this table; preferences stay PRODUCT-only, so TRANSACTIONAL cannot be
  switched off — canon §71).
* None to `classified_offers`, `users`, the public clause.

### 7.5 Migration
One Alembic migration on head `0c4e6a8b2d91`: `schema_transition = "EXPAND"`,
`rollback_to_previous = "BLOCKED"` (an N−1 `make_public` ignores holds).
Covered by the startup privilege check (append-only trigger) and the PR-002
lineage recorder. No data backfill.

## 8. Authorization (server-authoritative)

| Who | May |
|---|---|
| signed-in, verified email/phone | create reports (§5.2); list **own** reports (status only) |
| listing manager (existing authority chain: PERSON / membership / mandate with MANAGE_* on the property) | see the moderation status of **their** listings; file a review request; never see reports |
| conversation participant | see "removed by Homies"/"closed by Homies" lines |
| moderator = `can_moderate(user)` (today `role == "admin"`, read from the DB per request) | queue, report detail incl. reporter identity, context, decisions, review answers |
| anyone else | nothing |

* No role is accepted from the client; moderation state is never client input.
* **Conflict of interest:** a moderator cannot decide on a target where they are
  the reporter, a conversation participant, or hold authority over the listing's
  property → 403.
* Role escalation: unchanged (no role endpoint; admin only via ops script);
  `can_moderate` is the single seam for a later moderator role.
* Moderation routes live under `/v1/admin/moderation/*` (ADMIN rate limit,
  router-level `require_role`).

## 9. Privacy classes (Q8)

| Data | Public | Subject (owner / reported sender) | Reporter | Moderator | Audit-only |
|---|---|---|---|---|---|
| report existence, count, category | **never** | **never** | own report | yes | — |
| reporter identity | never | **never** | self | yes | decision/audit rows reference ids only |
| report free text | never | never | own | yes (plain text) | never in audit `data` |
| listing snapshot | — | — | — | yes | — |
| decision action + reason code + date | no ("no longer available") | yes (own listing / own message) | no (L13) | yes | yes |
| moderator explanation | never | never | never | yes | — |
| redacted message body | never | replaced by "removed by Homies" | — | yes | — |

* Nothing is sent to the owner while a report is pending; `NO_ACTION` is not
  notified; notices carry a template key + reason code, never the allegation.
* No reporter id in events, notifications, metrics, logs or audit `data`.
* Collection minimum: no uploads, no documents, bounded free text.

## 10. API proposal (OpenAPI-generated; names final in Slice 2/3)

| Method & path | Actor | Notes |
|---|---|---|
| `POST /v1/reports` | user | body `{target_type, target_id, reason, text?}` → 201/200 `ReportOut {id, target_type, target_id, reason, status: received|reviewed, created_at, created}` |
| `GET /v1/me/reports` | user | own reports, status only, paged |
| `GET /v1/admin/moderation/queue` | moderator | grouped by target: target type/id, listing id, open count, max severity, oldest/newest, distinct reporters (phone-verified count) |
| `GET /v1/admin/moderation/targets/{type}/{id}` | moderator | reports (with reporter id, text), snapshot, current listing/message/conversation state, decision chain, open review request; sets IN_REVIEW + `first_reviewed_at` |
| `POST /v1/admin/moderation/decisions` | moderator | `{target_type, target_id, action, reason_code, explanation?, expected_head_decision_id, close_engagement?, reclassified_category?}` → 201; 409 stale head / invalid transition; 403 conflict of interest |
| `GET /v1/me/classifieds` (existing) | owner | adds `moderation: {state: NONE|HELD, action, reason_code, since, review: NONE|OPEN|ANSWERED}` |
| `POST /v1/classifieds/{id}/moderation-review` | owner | review request; 409 if not held / already open |
| publish / confirm (existing) | owner | new 409 `HELD_BY_MODERATION` |
| `GET /v1/me/inbox` (existing) | user | TRANSACTIONAL moderation notices |

Future UI states (no frontend work here): report action on listing detail and
on each message; "received" confirmation (also on 200 duplicate); owner banner
"on hold by Homies — reason — request review"; moderator queue empty state,
target detail, decision form with stale-head conflict handling.

## 11. Cross-domain effects (Q5–Q7)

| Domain | On hold (CONTENT_EDIT_REQUIRED / VISIBILITY_LIMITED) | On release |
|---|---|---|
| search / map / detail / media serve | gone (paused) | back only after owner republish |
| contact reveal | 404 (existing) | after republish |
| saved listings (Q6) | tombstone "no longer available" (no reason) | tombstone clears after republish |
| saved-search alerts (Q6) | queued deliveries suppressed `listing_not_public` (existing) | republish = new `public_generation` → alerts may fire (**§17 D-5**, recommended allow) |
| new conversation / viewing request | 404 (existing) | after republish |
| existing conversations (Q7) | untouched; with `close_engagement` (SCAM/FAKE/SAFETY): CLOSED + neutral SYSTEM line | not reopened (a new thread is allowed after republish) |
| pending viewings (Q7) | **confirm refused** (new); with `close_engagement`: future REQUESTED/CONFIRMED → CANCELLED (system) | — |
| media | unchanged (served only via public listings) | — |
| authority | unchanged; revoke stays a separate lever | — |

Residual risk (recorded): an owner can create a **new listing** on the same
property while one is held; the moderator answers with another hold or the
authority revoke. A property-level hold is deferred (§17 D-8).

## 12. Events and measurement (DATA-001 not implemented)

* **One event:** `ModerationDecisionRecorded`, one per decision row, dedup
  `ModerationDecisionRecorded:{decision_id}`, emitted in a savepoint in the
  decision's transaction, **not routed**. Payload: `decision_id, target_type,
  target_id, listing_id?, action, reason_code, supersedes_decision_id?,
  effective_from` — ids, closed enums, DB instant. A test pins the exact keys
  and a forbidden-key list (no reporter id, text, explanation, address).
* **No `ReportSubmitted` event:** nothing consumes it and it would write an
  allegation (possibly about a person) into a log that cannot be erased.
* **Versioning (Q12): not now** — a later DATA-001 concern. Every consumer
  selects exact event types; a new unrouted type breaks none; canon §69 gives
  `event_version` a default of 1, so existing rows become version 1 when the
  column arrives. Rule for this slice: payloads only gain optional keys; a
  breaking change gets a new event name. No `schema_version` inside the payload.
* **Prometheus (bounded labels):** `homies_reports_created_total{target_type,
  category}` (≤ 2×12 series), `homies_moderation_decisions_total{target_type,
  action}`; both after commit. Open-queue gauge/alert: deferred (no destination
  exists).
* **Offline KPIs (later, SQL over the tables — columns persisted now):**
  reports per active listing, unique reported listings, duplicate-report rate,
  time to first review, time to decision, action rate by category, reversal
  rate (`REINSTATED_DECISION_ERROR` = over-removal, `REINSTATED_REMEDIED` =
  recovered supply), exposure before intervention (generation at report vs
  decision), repeat-target signal per listing/property (moderator view only;
  never a public or ranking score; never guilt from count).
* Never in metrics/analytics: free text, reporter identity, listing/user ids as
  labels, snapshot content, message bodies. `/metrics` is still public (PR-001
  gap) — category counts are world-readable until ingress restriction.

## 13. Idempotency decision (Q11) — **C for TASK-015; B for the platform**

| Operation | Retry after `commit_unknown` | Mechanism |
|---|---|---|
| create report | returns the existing live report (200) | DB partial UNIQUE per (reporter, target) — natural key |
| repeated / malicious reports | bounded | per-account DB quota (e.g. 10/24 h, ≤ 20 live) + `REPORT_CREATE` IP policy; numbers = product decision |
| moderator decision | 409 with current head (the first attempt applied) — never a duplicate decision | CAS `expected_head_decision_id` + `UNIQUE(supersedes_decision_id)` |
| review request | 409 already open | partial UNIQUE one OPEN per hold |
| set IN_REVIEW | idempotent | conditional UPDATE, `first_reviewed_at` set once |

**C:** the slice has safe domain-specific idempotency; a general
`Idempotency-Key` is **not** a prerequisite for TASK-015.
**B (platform):** property, classified and message creates remain duplicable
after an unknown COMMIT (PR-003 debt). That must be solved **before the public
browser vertical slice / launch**, in parallel with or after TASK-015 — it does
not touch the moderation tables.

## 14. Concurrency / failure matrix (to be proven in Phase B)

| Race | Invariant | Mechanism |
|---|---|---|
| two users report one listing at once | both stored, one queue group | independent rows; queue grouping |
| one user reports twice concurrently / retries after `commit_unknown` | one live report | partial UNIQUE; `IntegrityError` → return existing |
| report quota under concurrent creates | quota exact | per-reporter users-row lock (pattern of conversation start) + count |
| two moderators decide the same target | one decision per head | target row lock + CAS head + UNIQUE(supersedes) |
| owner publishes / confirms while moderator holds | never active while held | both take property lock → offer `FOR UPDATE`; `make_public` reads the head under the lock |
| moderator releases while owner pauses / owner republishes during release | consistent | same lock order; release never writes `active` |
| alert episode opening vs hold | no episode while held | hold refusal precedes `opening` in `make_public` |
| public search racing a hold | at most one stale read, never after commit | single statement snapshot; status change commits atomically |
| message sent while conversation is being closed | no message after CLOSED commits | `send_message` locks the conversation row (or conditional INSERT on status) |
| conversation/viewing created just before hold | allowed (was public); covered by `close_engagement` when upheld | start paths re-check `is_public` under their existing locks |
| viewing confirm vs hold | refused under hold | `_respond` checks the head under the listing row lock |
| decision vs report creation | new report after decision stays OPEN for the next review | `resolution_decision_id` set only on reports live at decision time |
| abandoned COMMIT of a decision | outcome unknown → retry gets 409 + head | CAS |
| deadlock | none | fixed order properties → spaces → authorities → offers → conversations → viewings |

## 15. Acceptance criteria and required tests (Phase B)

* Structural: `make_public` is the **sole writer of `active`** (AST/grep test);
  confirm and publish map a hold to 409 (`.applied` checked).
* Hold: a held listing cannot become public by publish, confirm or any API;
  release + republish works; generation behaviour per §17 D-5.
* Reports: authz matrix (§8), own-listing/own-message refusal, participant-only
  message reports, hidden-listing report by prior counterpart, duplicate → 200
  same body, quota and rate limit, text bounds, derived severity, snapshot
  integrity.
* Privacy: reporter id/text never in owner API, inbox, events, metrics, logs,
  audit `data`; NO_ACTION not notified; 404 indistinguishable for
  non-reportable targets; forbidden-key test on the event payload.
* Decisions: append-only (ORM, trigger, grants, startup check); CAS 409; fork
  impossible (UNIQUE); conflict-of-interest 403; reclassification recorded.
* Cross-domain: every row of §11 on PostgreSQL; redacted body blanked for
  participants and kept for moderators; conversation close blocks send;
  viewing confirm refused; `close_engagement` cancels future viewings only.
* Concurrency: every row of §14 on PostgreSQL with row-lock evidence
  (`pg_blocking_pids`), not sleeps.
* Migration: EXPAND/BLOCKED lineage; single head; up/down on a disposable DB;
  restore drill includes the new tables.
* Mutation (load-bearing): remove the hold check; drop the partial UNIQUE;
  drop the CAS; accept client severity; leak reporter id into the owner view;
  skip `close_engagement` cancellation; allow a moderator conflict of interest;
  route the event through `ROUTING`.
* Gates: ruff, mypy, OpenAPI drift (regenerated), Spectral, full SQLite, full
  PostgreSQL/PostGIS, promtool (if a rule is added), CI.

## 16. Implementation slices (Q15)

| Slice | Content | Size |
|---|---|---|
| **S1 — domain core + hold enforcement** | migration (§7, EXPAND/BLOCKED); models; decision-chain service (`apply_decision` with locks, CAS, audit, event); `make_public` hold check; confirm/publish 409 mapping; sole-writer structural test; append-only + startup checks; unit + PG concurrency tests for hold vs publish/confirm and decision CAS. **No public API.** | medium |
| S2 — reports API | `POST /v1/reports`, `GET /v1/me/reports`; quota + `REPORT_CREATE`; snapshot; derived severity; counter metric | small |
| S3 — moderator API (listings) | queue, target detail (IN_REVIEW), decisions for LISTING (NO_ACTION, CONTENT_EDIT_REQUIRED, VISIBILITY_LIMITED incl. release), CoI, owner TRANSACTIONAL notice, owner `moderation` field, decision counter | medium |
| S4 — messages, conversations, viewings, media | MESSAGE reports; redaction read path; conversation close (locked send); `close_engagement`; viewing confirm refusal and cancel; media RESTRICTED writer | medium |
| S5 — review requests | owner review request + moderator answer | small |
| ~~S6 — hardening~~ | **absorbed** (PROGRAM-001): adversarial review, PG race suite and mutation testing in S4b; restore-drill coverage of conversations, messages (redacted), viewings and media in the TASK-015 closure | — |

S1 first: it is the invariant every later slice relies on and is reviewable on
its own. S2+S3 together make the first usable listing-report loop.

## 17. Decisions required (founder) — none blocks S1

| # | Decision | Class | Recommendation |
|---|---|---|---|
| D-1 | Approve this contract (targets LISTING + MESSAGE; no case entity; decision-chain hold) | PRODUCT | approve |
| D-2 | Record in 04a the refinements of §64/§65 (extra columns §7.1–7.3, unused TRIAGED/CLOSED in 1A, review request seam) | CANONICAL CLARIFICATION (refinement, not contradiction) | approve as 04a entry with S1 |
| D-3 | `MISLEADING_PRICE` labelled "price or key details misleading"; no new PRIVACY category | PRODUCT / 04a | approve |
| D-4 | quota and rate numbers (10/24 h, 20 live, IP 5 burst) | PRODUCT | approve as starting values |
| D-5 | republish after a released hold opens a new episode and may fire saved-search alerts | PRODUCT | allow (genuine return to market; consistent with D-80) |
| D-6 | account status / suspension stays out of 1A (04a §22) | CANONICAL (already decided) | keep deferred; revisit before public launch |
| D-7 | user block (self-protection after reporter inference) | PRODUCT | schedule before public launch |
| D-8 | property-level hold against relist evasion | PRODUCT | defer; use repeat hold or authority revoke |
| D-9 | notice channel: inbox only in 1A, email later | PRODUCT / LEGAL (L2) | inbox now |

No **CANONICAL DECISION REQUIRED** contradiction remains in this design: the
case entity, the hold table and new categories from the prior draft were
dropped in favour of canon-native constructs.

## 18. Legal / regulatory dependencies (Q14)

Nothing here is a statement of current law; counsel must verify.

| # | Question | Class | Blocks |
|---|---|---|---|
| L1 | notice intake for non-registered persons (DSA notice-and-action), receipt confirmation, notifier outcome | EXTERNAL LEGAL VERIFICATION REQUIRED | public launch, not S1–S6 |
| L2 | statement of reasons to affected users: content, language (PL), whether a hold is a "restriction", P2B for agencies | EXTERNAL LEGAL VERIFICATION REQUIRED | notice wording (S3), not the mechanism |
| L3 | internal complaint / appeal requirement and timelines | EXTERNAL LEGAL VERIFICATION REQUIRED | launch; S5 is the seam |
| L4 | measures against manifestly unfounded notifiers | EXTERNAL LEGAL VERIFICATION REQUIRED | later |
| L5 | duty to inform authorities of threats to life/safety | EXTERNAL LEGAL VERIFICATION REQUIRED | launch ops; not code |
| L6 | transparency reporting | EXTERNAL LEGAL VERIFICATION REQUIRED | data already retained by §7 |
| L7 | trusted flaggers / authority orders | EXTERNAL LEGAL VERIFICATION REQUIRED | later |
| L8 | GDPR basis, retention per artefact, access request by the reported person vs reporter confidentiality, erasure | EXTERNAL LEGAL VERIFICATION REQUIRED | production data, not the build |
| L9 | moderator access to private messages | EXTERNAL LEGAL VERIFICATION REQUIRED | launch (privacy notice) |
| L10 | housing anti-discrimination content policy | EXTERNAL LEGAL VERIFICATION REQUIRED | policy text; taxonomy already has DISCRIMINATION |
| L11 | wording of counterpart notices (personal rights) | PRODUCT + legal review | S4 wording |
| L12 | preservation for investigations | EXTERNAL LEGAL VERIFICATION REQUIRED | retention policy |
| L13 | outcome disclosure to reporters | EXTERNAL LEGAL VERIFICATION REQUIRED | default: not disclosed |
| — | "no account status in 1A" | ALREADY CANONICALLY DECIDED (04a §22) | — |
| — | decisions immutable; reports do not mutate targets | ALREADY CANONICALLY DECIDED (04 §65, inv. 23) | — |

**Implementable independently of legal verification:** the whole mechanism
(S1–S6). Legal answers change notice texts, intake channels, retention jobs and
launch readiness — not the data model.

## 19. Rollout

Backend only; no frontend. `can_moderate` = founder admin account(s). No
production data, no deployment. Before public launch: L1/L2/L3/L8 answered,
D-7 decided, `/metrics` restricted, Idempotency-Key (B) done.

## 20. Product & Growth Doctrine impact

| Dim. | Effect |
|---|---|
| A2 Trust & Safety | first report → decision → effect loop; scams can be taken down and contact frozen |
| A3 Automation | none automated on purpose (no auto-takedown); queue grouping and derived severity reduce manual work |
| A4 Efficiency | reuses the lifecycle, the public rule and the inbox; 3 small tables |
| A5 Liquidity | proportionate actions (edit-required keeps threads), owner notice + review request, clean restore, reversal measured — legitimate supply is not destroyed by allegations |
| A6 Competitive advantage | "trust-first" becomes operable, not a slogan |
| A8 Growth | no engagement optimisation; trust outcomes outrank CTR |
| A10 Necessity | listing + message only; everything else deferred with a reason |

Signals to separate later: fraud removal (upheld SCAM/FAKE), false reporting
(`NOT_A_VIOLATION` share per reporter cohort — moderator-only), over-removal
(`REINSTATED_DECISION_ERROR`), recovered supply (`REINSTATED_REMEDIED` →
republish).
