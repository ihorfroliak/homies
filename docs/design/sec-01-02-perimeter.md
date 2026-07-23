# SEC-01 / SEC-02 — Security perimeter

Micro-cycle 01. Closes the two P0 findings from the
[full system audit](../reviews/2026-07-23-full-system-audit.md): no rate
limiting anywhere, and cryptographic secrets that fail open.

## SEC-01 — Rate limiting

### Storage decision (evidence-based)

| Option | Verdict |
|---|---|
| PostgreSQL | ❌ a DB write per request; the audit explicitly rules this out |
| Redis | ❌ **not operational** (container stopped) and referenced by zero lines of code — introducing it would create a new production dependency for theoretical scalability |
| **In-process token buckets behind `RateLimitStore`** | ✅ chosen — no new dependency, no added latency, correct for the current topology |

Topology check that decided it: the container runs a **single** uvicorn process
(`CMD uvicorn app.main:app`, no `--workers`), and nothing is deployed anywhere yet.

> ⚠️ **Limitation, stated loudly:** counters are per-process. Running more than
> one worker or replica multiplies every limit by the number of instances.
> Before scaling out, implement a shared backend behind `RateLimitStore` — the
> protocol exists precisely so that is a drop-in change. Recorded as D-14.

### Algorithm

Token bucket: `capacity` = burst, `refill_per_second` = sustained rate. Chosen
over fixed windows (no double-burst at window edges) and over sliding-window
logs (memory). It refills **continuously**, which is what makes the
account-lockout DoS below impossible.

### Policy table

Policies are central (`app/core/ratelimit.py`), never ad-hoc counters in handlers.

| Policy | Burst | Sustained | Store failure |
|---|---:|---:|---|
| `auth_login_ip` | 10 | 0.1/s | **closed** |
| `auth_login_account` | 8 | 0.05/s | **closed** |
| `auth_register` | 5 | 0.02/s | **closed** |
| `auth_refresh` | 30 | 0.5/s | **closed** |
| `booking_create` | 10 | 0.2/s | open |
| `booking_mutate` | 20 | 0.5/s | open |
| `listing_write` | 20 | 0.5/s | open |
| `admin` | 120 | 5/s | open |
| `public_read` | 120 | 10/s | open |

**Exempt (never throttled):** `/v1/payments/webhook/*`, `/healthz`, `/metrics`,
API docs. Payment webhooks are exempt because the provider retries
aggressively; throttling them would create inconsistent financial state. The
handler is already signature-verified and idempotent, so the exemption costs
nothing.

**Future Product B categories** (documented, deliberately not wired — the routes
do not exist): `free_listing_create`, `free_listing_edit`, `free_listing_delete`,
`image_upload`, `search`, `contact_request`, `messaging`, `report`,
`moderation_action`.

### Keying strategy

- **Per IP** for every limited route, applied in middleware before routing.
- **Per account** additionally on login, spent **only by failed attempts**.

That layering is deliberate. A pure account limit is an account-lockout DoS: an
attacker floods failures and locks the victim out. Here:

- successful logins never spend account tokens, so a busy legitimate user cannot
  throttle themselves out;
- the account bucket refills continuously, so an attacker can add friction but
  **can never permanently lock anyone out**;
- the bucket is keyed by the submitted address whether or not the account
  exists, and the 429 body is generic — so it cannot be used to enumerate accounts.

### Proxy trust

`X-Forwarded-For` is **never** trusted by default. `TRUST_PROXY_HOPS` (default
`0`) declares how many trusted proxies sit in front; with `0` the socket peer is
used, so a spoofed header cannot be used to evade limits or frame another
client. With `N > 0` the N-th entry **from the right** is taken — the left edge
is attacker-controlled and is ignored.

### Failure semantics

Per policy, not mechanical:

| Category | On limiter failure | Why |
|---|---|---|
| Authentication | **fail-closed** | an unavailable limiter must not open the door to credential stuffing |
| Booking / listing mutations | fail-open | availability matters and the **database** remains the authoritative defence (exclusion constraint still makes double booking impossible) |
| Public reads | fail-open | availability |
| Payments | **exempt** | the limiter is never in the money path |

The limiter is never the source of truth for authorization, booking state,
payment state or financial state.

### Observability

`homies_rate_limit_hits_total{policy, outcome}` where outcome is
`allowed | rejected | error`. Deliberately **no IP label** — raw addresses are
high-cardinality and personal data. Policy + outcome is enough to spot
credential stuffing, client bugs and legitimate spikes.

### Performance

No I/O and no allocation beyond two floats per active key; a full bucket is
evicted, so idle keys cost nothing. Measured impact on the suite: 53 → 84 tests
with no change in wall-clock profile. There is no new bottleneck because there
is no new network hop or query.

## SEC-02 — Fail-fast secret configuration

Single source of truth: `validate_security_config()` in `app/core/config.py`,
called once at startup. No `os.environ.get(..., "default")` scattered anywhere.

- **Production-like environments** (anything except `local`, `test`, `ci`) must
  supply `JWT_SECRET` (≥32 chars) and `WEBHOOK_SECRET` (≥16); with
  `PAYMENT_PROVIDER=stripe`, also `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET`.
- Startup **refuses** on: empty/whitespace values, values shorter than the
  minimum, and any value in the known-insecure set (the defaults shipped in this
  repo, plus `changeme`, `secret`, `password`, …).
- All problems are reported together, so a deploy is fixed in one pass.
- Dev/test environments are exempt **on purpose**, so local development and
  deterministic tests are untouched.
- Error messages name the **field only, never the value** — a crash log cannot
  leak a secret. `/healthz` exposes only `status` and `env`.

Verified end-to-end:

```
$ ENV=production python -c "validate_security_config(Settings())"
REFUSED: Refusing to start in env='production': JWT_SECRET uses a known
insecure default; WEBHOOK_SECRET uses a known insecure default
```

## Tests (31 added)

`tests/test_sec01_ratelimit.py` (15) — bucket burst/refill via an **injectable
clock** (no sleeps), peek does not consume, key isolation, per-policy store
failure semantics, forwarded-header trust in both modes, policy resolution
including webhook exemption, login burst → 429 with `Retry-After`, recovery
after refill, account bucket spent only by failures, identical treatment of
existing vs non-existing accounts, booking burst → 429 while legitimate booking
succeeds, webhooks never throttled, limiter never grants access, health stays up
under load.

`tests/test_sec02_secret_config.py` (16) — empty/whitespace/short/known-default
secrets refuse startup, Stripe keys required when that provider is selected, all
problems reported together, strong secrets start, dev environments exempt,
secret values never appear in error messages, health endpoint exposes no config.

## Known limitations

1. **Per-process counters** (see D-14) — multi-instance deployment weakens limits.
2. Adversarial harnesses (`scripts/warfare/`) generate deliberately abusive
   traffic from one address and will now receive 429s. Run them with
   `RATE_LIMIT_ENABLED=false`; they test booking concurrency, not the perimeter.
3. No CAPTCHA/proof-of-work — appropriate for Product B later, not needed now.
4. Registration is throttled but email is still unverified (SEC-03, open).
