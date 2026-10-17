# BP-4 — Minimal requester display name

Authorized by HOMIES-DELIVERY-002 and founder clarification2026-10-16 (D-113,
documentation DraftPR10). R2 private identity projection; independent exact-SHA
review required. Baseline fb5b3e57a6e4881ab14ad378a15e15f49475e682 (BP-9 DraftPR13,
NOT integrated). Branch codex/BP-4-requester-display-name, sole writer parentCodex.
Canon00,04a section24 OD-3,D-104/D-105; FE-003 sections3.9/6.10; governance05.

## Scope
Add requester_display_name to provider conversation and viewing DTOs only,
computed on server from User.full_name after existing BP-9 authorization.
First whitespace-separated word plus last word initial and period; one word
alone stays unchanged; excess whitespace removed; Unicode preserved. Empty
names use Użytkownik Homies. Combining marks belonging to the initial are
retained; do not transliterate or normalize the name into a legal identity.
Never read legal identity for this projection or expose email/phone/full_name,
identity verification metadata or a verified label. The name is unverified
user-provided display text; callers must render it as plain text.
Bulk provider lists use one scalar name query, not a per-row user-object load.
Requester projections remain unchanged. No stored name field or migration.

## Verification
Projection examples: empty/whitespace, single word, multipart, hyphenated,
Unicode/combining marks, markup treated as data. HTTP provider inbox/thread,
stage/assignment and viewing list; requester/stranger/unverified root and
revocation; exact serialized private field exclusions. Existing conversations,
viewings and BP-9 authorization regressions; Ruff/mypy/API generated drift,
required CI and separate review. Draft PR base is BP-9 branch, not main.
No merge/deployment/paid providers; IBB001 and all existing debt remain.

## Builder verification — 2026-10-17

Python3.12 Docker selection:126passed,2 setup errors in147.42s across BP4,
conversations,viewings,BP9. The initial error detail was truncated; no clock
causality is asserted. The failed selection reran unchanged:4passed8.20s.
Source-pinned host environment (import path asserted to this worktree): BP4
18cases plus OpenAPI6checks,24passed20.70s. Ruff clean; mypy127files clean;
generated API comparison and TypeScript check passed. HostNode24.14 reports
existing transitive engine warnings; required LinuxCI remains distinct.
No migration or new PG lock protocol. Inherited BP9 CI38941516780 SUCCESS;
its mandatory independent review and this candidate's separate review remain
acceptance prerequisites. Draft stacked on BP9, not independently mergeable
against unprepared main. No deployment or production certification.
