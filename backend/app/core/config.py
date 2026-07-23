from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql+psycopg://homies:homies@localhost:5433/homies"
    redis_url: str = "redis://localhost:6379/0"
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = "dev-master-key"
    nats_url: str = "nats://localhost:4222"

    # Auth
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"  # >=32 bytes for HS256
    # Simulated-webhook shared secret. The real Stripe adapter MUST verify
    # the Stripe-Signature header instead — never trust an unsigned webhook.
    webhook_secret: str = "dev-webhook-secret"

    # Payments (B1). "simulation" keeps the deterministic in-process provider
    # (default so tests and local dev need no Stripe account). "stripe" wires
    # the real Stripe Connect adapter — requires the keys below (never
    # hard-code real keys; set via env/secrets manager).
    payment_provider: str = "simulation"  # simulation | stripe
    stripe_api_key: str = ""  # sk_test_... / sk_live_...
    stripe_webhook_secret: str = ""  # whsec_...

    # Perimeter rate limiting (SEC-01)
    rate_limit_enabled: bool = True
    # How many reverse proxies sit in front of the app. 0 => X-Forwarded-For is
    # NOT trusted and the socket peer is used. Only raise this when the
    # deployment actually terminates through that many trusted proxies.
    trust_proxy_hops: int = 0

    # Notification delivery (OAT-03: transactional outbox + worker)
    notification_max_attempts: int = 5
    notification_backoff_base_seconds: float = 2.0  # base * 2**attempt + jitter
    notification_worker_interval_seconds: float = 1.0
    notification_worker_batch: int = 20
    notification_stale_processing_seconds: int = 60  # reclaim stuck PROCESSING
    notification_worker_enabled: bool = True  # disabled in tests (deterministic)
    email_provider: str = "stub"  # stub | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@homies.example"
    access_token_ttl_seconds: int = 1800
    refresh_token_ttl_days: int = 30

    # Money (ADR-0002: integer minor units)
    platform_fee_bps: int = 1500  # 15% managed fee placeholder until pricing is approved
    default_currency: str = "PLN"


settings = Settings()


# --- SEC-02: fail-fast secret validation ------------------------------------
# Environments where insecure defaults are acceptable *on purpose*. Anything
# else is production-like and must supply real secrets.
DEV_ENVIRONMENTS = frozenset({"local", "test", "ci"})

# Values shipped in this repository or commonly pasted in. Any of these in a
# production-like environment is a hard startup failure.
KNOWN_INSECURE_VALUES = frozenset({
    "dev-only-secret-change-me-0123456789abcdef",
    "dev-webhook-secret",
    "dev-backup-key-change-me",
    "change-me-in-any-shared-environment",
    "changeme", "change-me", "secret", "password", "test", "dev", "",
})

MIN_SECRET_LENGTH = 32


# Only this environment may talk to Stripe with live credentials. Everything
# else must use test mode — this is what stops live keys leaking into a laptop
# and test keys silently running a "production" deployment on fake money.
LIVE_PAYMENT_ENVIRONMENTS = frozenset({"production"})


def stripe_key_mode(api_key: str) -> str:
    """'test' | 'live' | 'unknown' — derived from the key prefix, never logged."""
    if api_key.startswith("sk_test_") or api_key.startswith("rk_test_"):
        return "test"
    if api_key.startswith("sk_live_") or api_key.startswith("rk_live_"):
        return "live"
    return "unknown"


def stripe_environment_problems(cfg: "Settings") -> list[str]:
    """Explicit payment-environment model (FIN-01). Ambiguity is rejected:
    the deployment environment and the Stripe key mode must agree."""
    problems: list[str] = []
    mode = stripe_key_mode(cfg.stripe_api_key)
    env = cfg.env.lower()

    if mode == "unknown":
        problems.append("STRIPE_API_KEY is not a recognised Stripe secret key (sk_test_/sk_live_)")
    elif env in LIVE_PAYMENT_ENVIRONMENTS and mode != "live":
        problems.append(f"env='{cfg.env}' requires live Stripe keys but a {mode}-mode key is set")
    elif env not in LIVE_PAYMENT_ENVIRONMENTS and mode == "live":
        problems.append(f"live Stripe keys must never be used in env='{cfg.env}'")

    if cfg.stripe_webhook_secret and not cfg.stripe_webhook_secret.startswith("whsec_"):
        problems.append("STRIPE_WEBHOOK_SECRET is not a Stripe signing secret (whsec_...)")
    return problems


class InsecureConfigurationError(RuntimeError):
    """Raised at startup when a production-like environment has weak secrets.

    Messages name the offending FIELD only — never the value — so a crash log
    can never leak a secret.
    """


def validate_security_config(cfg: "Settings | None" = None) -> None:
    """Single source of truth for security-critical configuration.

    Called at startup. In dev/test environments it is a deliberate no-op so
    local development and deterministic tests keep working.
    """
    cfg = cfg or settings
    problems: list[str] = []

    # Payment-environment agreement is checked in EVERY environment: a live
    # Stripe key on a developer laptop is as dangerous as a test key in
    # production, and the dev exemption below must not hide it.
    if cfg.payment_provider == "stripe":
        problems.extend(stripe_environment_problems(cfg))

    if cfg.env.lower() in DEV_ENVIRONMENTS:
        if problems:
            raise InsecureConfigurationError(
                f"Refusing to start in env='{cfg.env}': " + "; ".join(problems)
            )
        return

    def _check(field: str, value: str, *, min_length: int = MIN_SECRET_LENGTH) -> None:
        if not value or not value.strip():
            problems.append(f"{field} is empty")
            return
        if value.strip().lower() in KNOWN_INSECURE_VALUES:
            problems.append(f"{field} uses a known insecure default")
            return
        if len(value) < min_length:
            problems.append(f"{field} is shorter than {min_length} characters")

    _check("JWT_SECRET", cfg.jwt_secret)
    _check("WEBHOOK_SECRET", cfg.webhook_secret, min_length=16)

    if cfg.payment_provider == "stripe":
        _check("STRIPE_API_KEY", cfg.stripe_api_key, min_length=16)
        _check("STRIPE_WEBHOOK_SECRET", cfg.stripe_webhook_secret, min_length=16)

    if problems:
        raise InsecureConfigurationError(
            f"Refusing to start in env='{cfg.env}': " + "; ".join(problems)
        )
