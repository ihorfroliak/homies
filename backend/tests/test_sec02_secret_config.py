"""SEC-02 — fail-fast secret configuration.

A production-like environment must refuse to start with missing, empty, weak or
known-default cryptographic secrets. Local and test environments keep working
deliberately, so development and deterministic tests are unaffected.
"""

import pytest

from app.core.config import (
    InsecureConfigurationError,
    Settings,
    validate_security_config,
)

STRONG = "S" * 48
STRONG_ALT = "W" * 40


def _cfg(**overrides) -> Settings:
    base = {
        "env": "production",
        "database_url": "postgresql+psycopg://homies_app:x@db.internal:5432/homies",
        "jwt_secret": STRONG,
        "webhook_secret": STRONG_ALT,
        "payment_provider": "simulation",
    }
    base.update(overrides)
    return Settings(**base)


# --- must refuse to start ---------------------------------------------------
def test_empty_jwt_secret_prevents_startup():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(jwt_secret=""))
    assert "JWT_SECRET" in str(e.value)


def test_whitespace_only_secret_prevents_startup():
    with pytest.raises(InsecureConfigurationError):
        validate_security_config(_cfg(jwt_secret="    "))


def test_known_default_secret_prevents_startup():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(
            _cfg(jwt_secret="dev-only-secret-change-me-0123456789abcdef")
        )
    assert "known insecure default" in str(e.value)


def test_short_secret_prevents_startup():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(jwt_secret="short-but-not-a-known-default"))
    assert "shorter than" in str(e.value)


def test_default_webhook_secret_prevents_startup():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(webhook_secret="dev-webhook-secret"))
    assert "WEBHOOK_SECRET" in str(e.value)


@pytest.mark.legacy_runtime
def test_stripe_provider_requires_its_keys():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(
            _cfg(payment_provider="stripe", stripe_api_key="", stripe_webhook_secret="")
        )
    message = str(e.value)
    assert "STRIPE_API_KEY" in message and "STRIPE_WEBHOOK_SECRET" in message


def test_all_problems_are_reported_together():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(jwt_secret="", webhook_secret=""))
    assert "JWT_SECRET" in str(e.value) and "WEBHOOK_SECRET" in str(e.value)


# --- must start -------------------------------------------------------------
def test_strong_production_secrets_allow_startup():
    validate_security_config(_cfg())  # no exception


def test_the_development_database_url_prevents_startup():
    """PR-001: an unset DATABASE_URL must not fall back to the repository's
    local default (and its published password) outside development."""
    from app.core.config import Settings as S

    with pytest.raises(InsecureConfigurationError, match="DATABASE_URL") as caught:
        validate_security_config(_cfg(database_url=S.model_fields["database_url"].default))
    assert "homies:homies" not in str(caught.value)


@pytest.mark.legacy_runtime
def test_stripe_provider_with_real_keys_allows_startup():
    """Production requires LIVE keys — a test-mode key here is refused by the
    payment-environment model (see the FIN-01 section below)."""
    validate_security_config(
        _cfg(payment_provider="stripe", stripe_api_key="sk_live_" + "x" * 24,
             stripe_webhook_secret="whsec_" + "y" * 24)
    )


@pytest.mark.parametrize("env", ["local", "test", "ci", "LOCAL", "Test"])
def test_development_environments_are_intentionally_exempt(env):
    """Defaults must keep working for local dev and deterministic tests."""
    validate_security_config(_cfg(env=env, jwt_secret="dev-webhook-secret", webhook_secret=""))


# --- payment environment model (FIN-01) -------------------------------------
TEST_KEY = "sk_test_" + "a" * 24
LIVE_KEY = "sk_live_" + "a" * 24
WHSEC = "whsec_" + "b" * 32


def _stripe_cfg(**overrides) -> Settings:
    base = {
        "payment_provider": "stripe",
        "stripe_api_key": TEST_KEY,
        "stripe_webhook_secret": WHSEC,
    }
    base.update(overrides)
    return _cfg(**base)


@pytest.mark.legacy_runtime
def test_test_keys_in_production_are_refused():
    """Production must never silently run on fake money."""
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_stripe_cfg(env="production", stripe_api_key=TEST_KEY))
    assert "requires live Stripe keys" in str(e.value)


@pytest.mark.legacy_runtime
@pytest.mark.parametrize("env", ["local", "test", "ci", "staging"])
def test_live_keys_outside_production_are_refused(env):
    """A live key on a laptop or in staging is as dangerous as the reverse —
    and must be caught even though dev environments skip other checks."""
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_stripe_cfg(env=env, stripe_api_key=LIVE_KEY))
    assert "live Stripe keys must never be used" in str(e.value)


@pytest.mark.legacy_runtime
def test_unrecognised_key_shape_is_refused():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_stripe_cfg(env="local", stripe_api_key="totally-not-a-key"))
    assert "not a recognised Stripe secret key" in str(e.value)


@pytest.mark.legacy_runtime
def test_webhook_secret_must_be_a_signing_secret():
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_stripe_cfg(env="local", stripe_webhook_secret="not-a-whsec"))
    assert "not a Stripe signing secret" in str(e.value)


@pytest.mark.legacy_runtime
def test_test_mode_in_development_is_allowed():
    validate_security_config(_stripe_cfg(env="local"))  # the point of this cycle


@pytest.mark.legacy_runtime
def test_live_mode_in_production_is_allowed():
    validate_security_config(
        _stripe_cfg(env="production", stripe_api_key=LIVE_KEY, jwt_secret=STRONG,
                    webhook_secret=STRONG_ALT)
    )


def test_simulation_provider_skips_stripe_environment_checks():
    validate_security_config(_cfg(env="local", payment_provider="simulation"))


def test_key_mode_helper_never_returns_the_key():
    from app.core.config import stripe_key_mode

    assert stripe_key_mode(TEST_KEY) == "test"
    assert stripe_key_mode(LIVE_KEY) == "live"
    assert stripe_key_mode("nonsense") == "unknown"


# --- secrets must never leak ------------------------------------------------
def test_error_message_never_contains_the_secret_value():
    secret = "battery-staple-42"  # under the minimum length -> rejected
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(jwt_secret=secret))  # too short -> rejected
    assert secret not in str(e.value)
    assert "JWT_SECRET" in str(e.value)


def test_health_endpoint_does_not_expose_configuration(client):
    body = client.get("/healthz").json()
    assert set(body) == {"status", "env"}
    assert "secret" not in str(body).lower()


# --- PR-001R F4: the repository's development database, however spelled ------
@pytest.mark.parametrize("url", [
    "postgresql+psycopg://homies:homies@localhost:5433/homies",  # the Settings default
    "postgresql+psycopg://homies:homies@db:5432/homies",  # ops/docker-compose.yml
    "postgresql://homies:homies@localhost:5432/homies_ci",  # CI service
    "postgresql+psycopg://homies:hom%69es@prod-db.internal:5432/app",  # percent-encoded
    "postgresql+psycopg://homies:homies@10.0.0.5:6432/homies?sslmode=require",  # query
    "postgresql+psycopg://someone:long-and-random@127.0.0.1:5433/homies",  # dev endpoint
    "postgresql+psycopg://someone:long-and-random@localhost:5433/homies?sslmode=disable",
    "postgresql+psycopg://someone:long-and-random@[::1]:5433/homies",
])
def test_repository_development_databases_are_refused_however_spelled(url):
    with pytest.raises(InsecureConfigurationError) as e:
        validate_security_config(_cfg(database_url=url))
    assert "DATABASE_URL" in str(e.value)
    for secret in ("homies:homies", "hom%69es", "long-and-random"):
        assert secret not in str(e.value)


@pytest.mark.parametrize("url, rule", [
    ("sqlite:///./homies.db", "does not point to PostgreSQL"),
    ("not a url at all", "not a valid database URL"),
])
def test_a_database_url_that_is_not_postgresql_is_refused(url, rule):
    with pytest.raises(InsecureConfigurationError, match=rule):
        validate_security_config(_cfg(database_url=url))


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://homies_app:long-and-random@db.internal:5432/homies",
    # a local sidecar/proxy (e.g. a cloud SQL proxy) on the standard port
    "postgresql+psycopg://homies_app:long-and-random@127.0.0.1:5432/homies",
    "postgresql+psycopg://homies_app:long-and-random@localhost:6432/homies?sslmode=require",
])
def test_ordinary_production_database_urls_pass(url):
    validate_security_config(_cfg(database_url=url))


def test_dev_environments_keep_the_development_database():
    for env in ("local", "test", "ci"):
        validate_security_config(
            _cfg(env=env, database_url="postgresql+psycopg://homies:homies@localhost:5433/homies"))


# --- PR-001R F3: ENV omitted is never silent --------------------------------
def test_an_omitted_env_is_local_but_announced(monkeypatch, caplog):
    monkeypatch.delenv("ENV", raising=False)
    cfg = Settings(database_url="postgresql+psycopg://homies_app:x@db.internal:5432/homies")
    assert cfg.env == "local" and "env" not in cfg.model_fields_set
    with caplog.at_level("WARNING", logger="homies.config"):
        validate_security_config(cfg)
    assert any("ENV is not set" in r.getMessage() for r in caplog.records)


def test_an_explicit_env_is_not_announced(monkeypatch, caplog):
    monkeypatch.setenv("ENV", "local")
    cfg = Settings()
    assert "env" in cfg.model_fields_set
    with caplog.at_level("WARNING", logger="homies.config"):
        validate_security_config(cfg)
    assert not [r for r in caplog.records if "ENV is not set" in r.getMessage()]


def test_the_production_image_defaults_to_production_and_dev_tooling_opts_in():
    """The image cannot run as `local` by omission: its Dockerfile sets
    ENV=production; the compose file for local development says local."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "backend/Dockerfile").read_text(encoding="utf-8")
    assert "\nENV ENV=production\n" in dockerfile
    assert dockerfile.index("ENV ENV=production") < dockerfile.index("CMD ")
    compose = (root / "ops/docker-compose.yml").read_text(encoding="utf-8")
    assert "ENV: local" in compose
