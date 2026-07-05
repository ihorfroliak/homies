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
    access_token_ttl_seconds: int = 1800
    refresh_token_ttl_days: int = 30

    # Money (ADR-0002: integer minor units)
    platform_fee_bps: int = 1500  # 15% managed fee placeholder until pricing is approved
    default_currency: str = "PLN"


settings = Settings()
