---
name: security-probe
description: Write and run executable security probes for Homies — object-level authorization (IDOR), role boundaries, auth bypass, trust boundaries. Use whenever an endpoint is added or an authorization rule changes.
---

# Security probe

Security claims in this repo are **executable**, never assertions from code
review. Every "can user A touch user B's data?" question is a test in
`backend/tests/test_security_authz.py`.

## Rule

Adding any endpoint that reads or mutates user-owned data requires a probe in
the same cycle. An endpoint without a probe is treated as unverified.

## Probe checklist per new endpoint

1. **IDOR** — a second user of the same role gets `404` (not `403`; do not leak existence).
2. **Role boundary** — every other role is refused.
3. **Anonymous** — no token ⇒ `401`; malformed token ⇒ `401`.
4. **Forged token** — signed with a wrong secret ⇒ `401`.
5. **Token confusion** — a refresh token must not work as an access token.
6. **Scoping** — list endpoints return only the caller's rows.
7. **Side-effect check** — after a denied attempt, assert the target object is unchanged.

## Pattern

```python
def test_x_cannot_touch_y(client):
    owner = register_and_login(client, "owner@example.com", "host")
    other = register_and_login(client, "other@example.com", "host")
    obj = create_something(client, owner)
    assert client.patch(f"/v1/things/{obj}", json={...}, headers=auth(other)).status_code == 404
    assert client.get(f"/v1/things/{obj}").json()["field"] == original  # unchanged
```

## Run

```bash
cd backend && ./.venv/Scripts/python -m pytest tests/test_security_authz.py -v
```

## Verified sound as of 2026-07-23 (12/12)

Guest↔guest booking isolation · host↔host listing isolation · payout is
admin-only · notification privacy · admin surface denied to guest/host ·
role escalation via registration blocked · missing/malformed/forged tokens
rejected · refresh-token-as-access rejected · webhook without secret cannot
confirm a booking.

## Perimeter status

**Closed (MC-01):** rate limiting (central token-bucket policies, per-IP plus
per-account on login failures, proxy-trust aware, webhooks exempt) and
fail-fast secret validation (production refuses to start on default/weak
secrets). Design: `docs/design/sec-01-02-perimeter.md`.

When adding a route, add its policy to `app/core/ratelimit.py` — never write an
ad-hoc counter in a handler.

**Still open:** no MFA · no email verification · no account lockout policy ·
rate-limit counters are per-process (breaks if >1 instance). Treat every new
public surface as amplifying these.
