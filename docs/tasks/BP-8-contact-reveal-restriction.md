# BP-8 — G-14 contact reveal restriction

Status: IMPLEMENTATION AUTHORIZED by founder 2026-10-14, D-111; candidate until reviewed/accepted.
Base implementation: PR7 merge38db9c100eae331fbe978432c9197d5ceb893121,
tree225cc074f8358b521bbf79f033b57313ebe7821e. Documentation receipt follows on its own branch.
Sole bounded writer: Codex. Canon: 00, 02 safety/privacy, 04a24, 05 sections9/14,
D-104 OD-2 / D-105 OD-8, FE-003 section3.5. No new Phase A decision required.

## Goal and scope
Prevent G-14 restricted requesters from retrieving a phone via new or repeat
contact reveal for the same listing/publication generation. Relevant doctrine
07 A2/A3: automatically enforce safety decisions across the phone channel;
A1: stable neutral refusal without exposing private moderation reasons.
Only properties contact endpoint, focused tests, API documentation/generated
types, and necessary status/evidence records. No migration or release-policy
change. No FE UI, BP9, BP10, moderation semantics, quotas or paid services work.

## Invariants / acceptance
- Authenticated verified phone and existing public/contact-mode gates remain.
- Current-generation G-14 returns409 RECONTACT_BLOCKED before repeat fast path;
  no old/current phone, private allegation, quota use or disclosure audit.
- Later legitimate publication generation uses existing access/quota rules.
- Other requesters/listings remain unaffected. Unrestricted repeats cost no
  quota and add neither reveal row nor disclosure audit, even at full quota.
- Listing FOR SHARE before existing viewer NO KEY UPDATE lock orders reads
  against FEATURE_RESTRICTED and republish. Refresh preloaded identity state.
  Refusal after committed restriction; reveal ordered first may finish before
  restriction. No claim to undo an already disclosed number.
- The integrity-conflict repeat fallback must reacquire/revalidate after rollback.
- Preserve existing audit payloads; do not put phone/reason in logs or metrics.

## Verification and risk
R2: actual authorization/private contact/row-lock change, despite preliminary
FE-003 R1 estimate. Governance9 requires genuinely separate exact-SHA review.
HTTP negative cases: new/repeat, updated phone, private reason canary, repeat
at full quota, isolation, republish, verification/public/message-only gates,
no side effects. Real disposable PostgreSQL tests observe pg_blocking_pids
for restriction vs new/repeat reveal, both orders, and unchanged deadlocks.
Run relevant reveal quota/auth/regression tests, Ruff/mypy, OpenAPI drift and
generated type checks; required exact-head CI includes full PG/restore/web.
No paid/live Stripe, development or production database. Local Docker clock
limitations remain explicit; stable Linux CI provides full certification.

## Delivery
Feature branch codex/BP-8-contact-restriction, coherent commit, push, Draft PR,
separate independent exact-SHA review. Do not merge BP8 without later founder
authorization. IBB001 unchanged; production NOT READY/NOT DEPLOYED.

## Builder evidence (2026-10-14)
Python3.12.15 / disposable PostgreSQL16.4/PostGIS3.4.3: combined HTTP BP8,
BP8 PG and existing SQLite/PG quota suites **31 passed in78.29s**. Includes
4 observed pg_blocking_pids schedules (restriction/reveal both orders, new
and repeat), no deadlock increase; stale preloaded generation after real
republish; rollback-conflict fallback revalidation; neutral refusal and no
quota/audit side effects; unrelated listing/requester isolation and new
generation access with normal quota. Initial PG run correctly caught an
unscoped FOR SHARE against joined nullable relations (6failed/1passed);
fixed to OF ClassifiedOffer, subsequent7passed then combined31passed.
Initial HTTP test used wrong AuditLog.payload attribute (2failed/20passed);
fixed to data, HTTP3passed then combined31passed. No failed run called green.
Ruff clean; mypy126 source files clean; OpenAPI drift6passed; generated
frontend API check and typecheck passed. HostNode24.14 reports transitive
engine warnings; required Linux CI remains the full web/backend gate.
Existing F03 concurrent quota regression runs separately before commit.
Required CI and genuinely separate independent exact-SHA review pending.
No mutation success/full local suite claimed. No schema migration.

Existing F03 concurrent quota/repeat regression: 2 passed, 5 deselected,15.50s; final changed-file Ruff clean.
