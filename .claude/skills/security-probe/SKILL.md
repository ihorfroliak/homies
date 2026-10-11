---
name: security-probe
description: Use for Homies endpoint changes, replay/idempotency, authorization rules, PII access, or trust-boundary changes; require executable negative-case evidence.
---
# Homies scoped security probes

Security claims should be falsifiable, not review-only assurances. Only an authorized writer adds or changes probes; read-only specialists identify missing evidence and request a bounded test from that writer.

## Minimal matrix per affected endpoint
- Anonymous/malformed/forged/refresh-token misuse => refusal with no side effects.
- Same-role different user/IDOR => masked existence where contract requires it (usually 404).
- Wrong role/expired/revoked authority => current authorization; repeat after relevant lock waits if the contract requires it.
- List/read scoping and cross-target or replay-key confusion => no cross-user leakage.
- Denials/replays => assert Message, parent rows, audit and events remain unchanged except expressly permitted counters.
- Inspect errors, logs, request-validation echo, metrics labels and redaction projection.

Put probes in **test files authorized by the active task contract**. `backend/tests/test_security_authz.py` is an optional existing example, not an unconditional write destination. If a new file is required outside the allowlist, stop for scope authorization.

Run the smallest relevant test first, then required regression. PostgreSQL concurrency is proven with real disposable PostgreSQL/PostGIS, not SQLite. Verify baseline versus candidate when classifying pre-existing debt. Do not modify legacy-dormant payments for unrelated tasks. Report exact evidence and remaining unknowns.
