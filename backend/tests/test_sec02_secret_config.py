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


def test_stripe_provider_with_real_keys_allows_startup():
    validate_security_config(
        _cfg(payment_provider="stripe", stripe_api_key="sk_test_" + "x" * 24,
             stripe_webhook_secret="whsec_" + "y" * 24)
    )


@pytest.mark.parametrize("env", ["local", "test", "ci", "LOCAL", "Test"])
def test_development_environments_are_intentionally_exempt(env):
    """Defaults must keep working for local dev and deterministic tests."""
    validate_security_config(_cfg(env=env, jwt_secret="dev-webhook-secret", webhook_secret=""))


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
