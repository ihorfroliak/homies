"""Proving an email address and a phone number belong to the account.

The number matters more than the address. It is what the free board checks
before it hands somebody's personal phone to a stranger, so the tests here are
mostly about what it costs to defeat: how many guesses a code survives, how
many codes can be alive at once, how many messages one number can be made to
receive, and how many accounts one SIM can stand behind.

A six-digit code is 10^6 candidates. Nothing about the hash protects it — the
controls are the attempt cap, the expiry, the single-outstanding rule and the
send budget, and each of them is asserted below rather than assumed.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.identity import verification
from app.modules.identity.models import User, VerificationCode
from tests.conftest import (
    SENT_MESSAGES,
    TestingSession,
    auth,
    last_code,
    register_and_login,
    verify_phone,
)

PHONE = "+48501234567"


@pytest.fixture
def user_token(client):
    return register_and_login(client, "verify-me@example.com", "guest")


def _start_phone(client, token, phone=PHONE):
    return client.post("/v1/me/verify/phone/start", json={"phone": phone}, headers=auth(token))


def _confirm(client, token, code, channel="phone"):
    return client.post(
        f"/v1/me/verify/{channel}/confirm", json={"code": code}, headers=auth(token)
    )


# --- the happy path -----------------------------------------------------------


def test_a_fresh_account_is_verified_in_neither_channel(client, user_token):
    state = client.get("/v1/me/verification", headers=auth(user_token)).json()
    assert state == {"email_verified": False, "phone_verified": False, "phone": None}


def test_the_code_travels_to_the_number_not_to_the_response(client, user_token):
    """If the code appeared in the HTTP response, anyone able to name a phone
    number could verify it without ever holding the SIM."""
    resp = _start_phone(client, user_token)

    assert resp.status_code == 200, resp.text
    assert SENT_MESSAGES[-1]["to"] == PHONE
    code = last_code()
    assert code not in resp.text
    assert resp.json()["destination_masked"] != PHONE


def test_a_correct_code_verifies_the_number(client, user_token):
    _start_phone(client, user_token)
    resp = _confirm(client, user_token, last_code())

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"email_verified": False, "phone_verified": True, "phone": PHONE}


def test_email_verification_uses_the_registered_address(client, user_token):
    resp = client.post("/v1/me/verify/email/start", headers=auth(user_token))
    assert resp.status_code == 200, resp.text
    assert SENT_MESSAGES[-1]["to"] == "verify-me@example.com"

    confirmed = _confirm(client, user_token, last_code(), channel="email")
    assert confirmed.status_code == 200
    assert confirmed.json()["email_verified"] is True
    assert confirmed.json()["phone_verified"] is False


def test_the_two_channels_are_independent(client, user_token):
    """A code sent by SMS must not unlock the email flag, or one channel's
    weakness becomes both channels' weakness."""
    _start_phone(client, user_token)
    sms_code = last_code()

    assert _confirm(client, user_token, sms_code, channel="email").status_code == 400
    assert client.get("/v1/me/verification", headers=auth(user_token)).json()[
        "email_verified"
    ] is False


def test_an_unknown_channel_is_not_a_channel(client, user_token):
    assert _confirm(client, user_token, "123456", channel="fax").status_code == 404


def test_anonymous_callers_cannot_start_a_send(client):
    """Otherwise the SMS bill is open to the whole internet."""
    assert client.post("/v1/me/verify/phone/start", json={"phone": PHONE}).status_code == 401


# --- the number is never stored before it is proven ---------------------------


def test_an_unconfirmed_number_never_lands_on_the_account(client, user_token):
    """A pending number sitting in `users.phone` would read as verified to
    every query that checks the column instead of the timestamp."""
    _start_phone(client, user_token)

    with TestingSession() as db:
        user = db.scalar(select(User).where(User.email == "verify-me@example.com"))
    assert user.phone is None
    assert user.phone_verified_at is None


def test_the_plain_code_is_not_in_the_database(client, user_token):
    _start_phone(client, user_token)
    code = last_code()

    with TestingSession() as db:
        rows = list(db.scalars(select(VerificationCode)))
    assert len(rows) == 1
    assert code not in rows[0].code_hash
    assert rows[0].code_hash == verification.hash_code(code)


def test_the_hash_is_keyed_to_the_application_secret(client):
    """A bare digest of six digits is reversible by anyone with the table. An
    HMAC is not, because the key is not in the table."""
    from app.core.config import settings

    original = settings.jwt_secret
    first = verification.hash_code("123456")
    settings.jwt_secret = "a-different-secret-value-0123456789"
    try:
        assert verification.hash_code("123456") != first
    finally:
        settings.jwt_secret = original


# --- what it costs to guess ---------------------------------------------------


def test_a_wrong_code_is_rejected(client, user_token):
    _start_phone(client, user_token)
    resp = _confirm(client, user_token, "000000" if last_code() != "000000" else "111111")

    assert resp.status_code == 400
    assert client.get("/v1/me/verification", headers=auth(user_token)).json()[
        "phone_verified"
    ] is False


def test_guesses_are_capped_and_the_cap_survives_a_correct_guess(client, user_token):
    """Without a cap, 10^6 candidates fall in minutes over HTTP. With one, an
    attacker gets five tries and then needs a new code — which costs an SMS and
    spends the send budget."""
    _start_phone(client, user_token)
    code = last_code()
    wrong = "999999" if code != "999999" else "888888"

    for _ in range(verification.MAX_ATTEMPTS):
        assert _confirm(client, user_token, wrong).status_code == 400

    resp = _confirm(client, user_token, code)
    assert resp.status_code == 400, "the real code still worked after the cap"
    assert "attempts" in resp.text.lower()


def test_a_spent_attempt_is_not_rolled_back_by_the_rejection(client, user_token):
    """The counter is the control. If the failing response rolled the increment
    back, the cap would never be reached."""
    _start_phone(client, user_token)
    _confirm(client, user_token, "000001")

    with TestingSession() as db:
        row = db.scalar(select(VerificationCode))
    assert row.attempts == 1


def test_an_expired_code_is_dead(client, user_token):
    _start_phone(client, user_token)
    code = last_code()

    with TestingSession() as db:
        row = db.scalar(select(VerificationCode))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    resp = _confirm(client, user_token, code)
    assert resp.status_code == 400
    assert "expired" in resp.text.lower()


def test_asking_again_kills_the_previous_code(client, user_token):
    """Ten requests must not leave ten live codes: that would multiply the
    guessing budget tenfold while each per-code cap still looked intact.

    Asserted on the table, not only through the API. Confirm reads the newest
    live code, so an old row left behind is invisible from outside — and stays
    invisible right up until someone changes that query.
    """
    _start_phone(client, user_token)
    first = last_code()
    _start_phone(client, user_token)
    second = last_code()
    assert first != second

    with TestingSession() as db:
        live = list(
            db.scalars(select(VerificationCode).where(VerificationCode.consumed_at.is_(None)))
        )
    assert len(live) == 1, "a superseded code was left alive"

    assert _confirm(client, user_token, first).status_code == 400
    assert _confirm(client, user_token, second).status_code == 200


def test_a_used_code_cannot_be_used_twice(client, user_token):
    _start_phone(client, user_token)
    code = last_code()
    assert _confirm(client, user_token, code).status_code == 200
    assert _confirm(client, user_token, code).status_code == 400


def test_confirming_without_a_code_is_refused(client, user_token):
    assert _confirm(client, user_token, "123456").status_code == 400


def test_one_account_cannot_confirm_another_accounts_code(client, user_token):
    """Codes are scoped to the user, not global — otherwise a code sent to one
    person verifies anybody who guesses it first."""
    _start_phone(client, user_token)
    code = last_code()
    stranger = register_and_login(client, "stranger@example.com", "guest")

    assert _confirm(client, stranger, code).status_code == 400


# --- one number, one account --------------------------------------------------


def test_a_number_cannot_back_two_accounts(client, user_token):
    """The whole economic argument: verification only raises the cost of an
    account if a SIM cannot be reused across them."""
    verify_phone(client, user_token, PHONE)
    second = register_and_login(client, "second@example.com", "guest")

    _start_phone(client, second, PHONE)
    resp = _confirm(client, second, last_code())

    assert resp.status_code == 409, resp.text
    assert client.get("/v1/me/verification", headers=auth(second)).json()["phone"] is None


def test_the_collision_is_only_revealed_to_whoever_holds_the_sim(client, user_token):
    """Refusing at START would answer "is this number registered with Homies?"
    for any number typed in. The refusal waits until the caller has proved they
    control the number, when it tells them nothing new."""
    verify_phone(client, user_token, PHONE)
    second = register_and_login(client, "nosy@example.com", "guest")

    started = _start_phone(client, second, PHONE)
    assert started.status_code == 200, "start leaked whether the number is known"


def test_a_verified_number_can_be_replaced(client, user_token):
    verify_phone(client, user_token, PHONE)
    verify_phone(client, user_token, "+48509999999")

    assert client.get("/v1/me/verification", headers=auth(user_token)).json()[
        "phone"
    ] == "+48509999999"


def test_reverifying_the_same_number_is_refused_rather_than_resent(client, user_token):
    """No point paying for an SMS to tell someone what they already have."""
    verify_phone(client, user_token, PHONE)
    assert _start_phone(client, user_token, PHONE).status_code == 409


def test_reverifying_a_confirmed_email_is_refused(client, user_token):
    client.post("/v1/me/verify/email/start", headers=auth(user_token))
    _confirm(client, user_token, last_code(), channel="email")

    assert client.post("/v1/me/verify/email/start", headers=auth(user_token)).status_code == 409


# --- input shape --------------------------------------------------------------


@pytest.mark.parametrize(
    "phone", ["500123456", "+48 501 234 567", "0048501234567", "+0501234567", "not-a-phone"]
)
def test_only_e164_numbers_are_accepted(client, user_token, phone):
    """Free-text numbers cannot be compared, and without comparison the
    one-number-one-account rule silently stops holding."""
    assert _start_phone(client, user_token, phone).status_code == 422


def test_a_non_numeric_code_is_rejected_before_it_costs_an_attempt(client, user_token):
    _start_phone(client, user_token)
    assert _confirm(client, user_token, "abcdef").status_code == 422

    with TestingSession() as db:
        assert db.scalar(select(VerificationCode)).attempts == 0


def test_codes_are_six_digits_and_drawn_from_the_whole_space(client):
    """Zero-padding matters: dropping it would leak that a code starting with a
    zero is shorter, and shrink the space for anyone who noticed."""
    codes = {verification.new_code() for _ in range(300)}
    assert all(len(c) == verification.CODE_DIGITS and c.isdigit() for c in codes)
    assert len(codes) > 250, "codes repeat far more than chance allows"


# --- rate limiting ------------------------------------------------------------


def test_sending_is_throttled_per_account_and_per_destination(client):
    """SMS costs real money, which makes this the one route where abuse has a
    direct bill attached (SMS pumping). Both keys are needed: per-account stops
    one user cycling numbers, per-destination stops many accounts pointing at
    one victim's phone."""
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/me/verify/phone/start") is rl.VERIFY_SEND
    assert rl.resolve_policy("POST", "/v1/me/verify/email/start") is rl.VERIFY_SEND
    assert rl.resolve_policy("POST", "/v1/me/verify/phone/confirm") is rl.VERIFY_CONFIRM
    assert rl.VERIFY_SEND.capacity < rl.VERIFY_CONFIRM.capacity
    # An unavailable limiter must not open the tap: the failure mode of "cannot
    # send" is an annoyed user, the failure mode of "send without a ceiling" is
    # an invoice.
    assert rl.VERIFY_SEND.on_store_failure == "closed"


def test_the_send_budget_is_actually_spent(client, user_token):
    from app.core.config import settings
    from app.core.ratelimit import VERIFY_SEND, limiter

    limiter.reset()
    settings.rate_limit_enabled = True
    limiter.enabled = True
    try:
        codes = [_start_phone(client, user_token).status_code for _ in range(VERIFY_SEND.capacity)]
        assert codes == [200] * VERIFY_SEND.capacity
        blocked = _start_phone(client, user_token)
        assert blocked.status_code == 429, blocked.text
        assert "Retry-After" in blocked.headers
    finally:
        settings.rate_limit_enabled = False
        limiter.enabled = False
        limiter.reset()


@pytest.fixture
def live_limiter():
    """Rate limiting on, with every bucket empty.

    The buckets are drained through the limiter directly rather than by making
    requests: a request spends the per-IP bucket too, and TestClient gives every
    caller the same address, so an HTTP-driven test cannot tell which key did
    the rejecting. Draining one key by hand makes the assertion specific.
    """
    from app.core.config import settings
    from app.core.ratelimit import limiter

    limiter.reset()
    settings.rate_limit_enabled = True
    limiter.enabled = True
    yield limiter
    settings.rate_limit_enabled = False
    limiter.enabled = False
    limiter.reset()


def test_the_destination_has_its_own_budget(client, user_token, live_limiter):
    """The victim's phone is the thing being spammed, and each attacker account
    is free — so the ceiling has to attach to the number, not to the account."""
    from app.core.ratelimit import VERIFY_SEND

    key = f"{VERIFY_SEND.name}:dest:{PHONE}"
    for _ in range(VERIFY_SEND.capacity):
        live_limiter.check(key, VERIFY_SEND)

    # This account has sent nothing and made no request: only the number's
    # budget is gone.
    blocked = _start_phone(client, user_token, PHONE)
    assert blocked.status_code == 429, blocked.text
    assert "Retry-After" in blocked.headers


def test_the_account_has_its_own_budget(client, user_token, live_limiter):
    """And the account's ceiling has to hold while it cycles through numbers,
    or one account sends unlimited SMS by changing the digits each time."""
    from app.core.ratelimit import VERIFY_SEND

    user_id = client.get("/v1/me", headers=auth(user_token)).json()["id"]
    key = f"{VERIFY_SEND.name}:user:{user_id}:phone"
    for _ in range(VERIFY_SEND.capacity):
        live_limiter.check(key, VERIFY_SEND)

    assert _start_phone(client, user_token, "+48511111111").status_code == 429


# --- delivery failures --------------------------------------------------------


def test_a_code_that_could_not_be_sent_is_not_left_pending(client, user_token, monkeypatch):
    """Committing a code nobody received leaves the user staring at a field
    they can never fill, and burns their send budget doing it."""
    from app.modules.events.providers import DeliveryResult

    class _Broken:
        def send(self, to, subject, body, idem_key):
            return DeliveryResult(ok=False, transient=True, error="carrier down")

    monkeypatch.setattr(
        "app.modules.identity.verification.channel_for", lambda name: _Broken()
    )
    resp = _start_phone(client, user_token)

    assert resp.status_code == 502, resp.text
    with TestingSession() as db:
        assert db.scalar(select(VerificationCode)) is None
