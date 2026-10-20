"""Opt-in synthetic FE-003 fixtures. See docs/engineering/FE-003-E2E-FIXTURES.md.

Run AFTER seed_e2e, with both seed opt-ins and --manifest outside the web tree.
No server settings, migrations or production business logic are changed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.modules.engagement.models import Viewing, ViewingSettings
from app.modules.events.providers import DeliveryResult
from app.modules.geography import service as geography
from app.modules.geography.models import GeoArea, GeoSource
from app.modules.identity.models import User
from app.modules.properties.models import ClassifiedOffer, ContactReveal, PropertyAuthority
from app.scripts import seed_e2e as base

SOURCE = "FE003_E2E"
PASSWORD = "fe003-synthetic-password-not-secret"
PROJECTS = ("desktop", "mobile")
ACCOUNT_KEYS = ("seeker", "phone_seeker", "restricted_seeker", "provider",
                "unverified_provider", "guest_provider", "host_without_authority")
LISTING_KEYS = ("approval", "instant", "phone", "held", "restricted", "closed", "redacted",
                "past_requested", "past_confirmed", "unavailable", "unverified")


def _guard() -> None:
    base._guard()
    if os.environ.get("HOMIES_ALLOW_ENGAGEMENT_E2E_SEED") != "1":
        raise SystemExit("Refusing: set HOMIES_ALLOW_ENGAGEMENT_E2E_SEED=1.")


def _email(project: str, key: str) -> str:
    return f"fe003-{project}-{key.replace('_', '-')}@example.com"


def _areas() -> dict[str, str]:
    with SessionLocal() as db:
        if db.get(GeoSource, SOURCE) is None:
            db.add(GeoSource(code=SOURCE, name="Fictional FE-003 fixtures"))
            db.flush()
        geography.import_areas(db, "PL", SOURCE, [
            geography.AreaRow("F06", None, "PL_VOIVODESHIP", "Lubelskie", "lubelskie"),
            geography.AreaRow("F0663", "F06", "PL_COUNTY", "Lublin", "lublin"),
            geography.AreaRow("F0663011", "F0663", "PL_MUNICIPALITY", "Lublin", "lublin"),
        ])
        geography.import_localities(db, "PL", SOURCE, [
            geography.LocalityRow("F-LUB", SOURCE, "F0663011", "CITY", "Lublin", "96", "lublin"),
        ])
        locality = geography._by_ref(db, SOURCE, "F-LUB", "locality_id")
        area = GeoArea(country_code="PL", locality_id=locality, kind="NEIGHBOURHOOD",
                       name="Fikcyjna dzielnica E2E", slug="fe003")
        db.add(area)
        db.commit()
        return {"F-LUB": locality, "fe003": area.id}


class _CodeSink:
    """In-process delivery capture, never sends SMS or prints codes."""
    code = ""

    def send(self, to, subject, body, idem_key) -> DeliveryResult:
        match = re.search(r"\b(\d{6})\b", body)
        if not match:
            raise RuntimeError("Synthetic verification delivery lacked a code")
        self.code = match.group(1)
        return DeliveryResult(ok=True)


def _phone(api, token, number):
    sink = _CodeSink()
    with patch("app.modules.identity.verification.channel_for", return_value=sink):
        api.call("POST", "/v1/me/verify/phone/start", token, json={"phone": number})
        api.call("POST", "/v1/me/verify/phone/confirm", token, json={"code": sink.code})


def _decision(api, admin, kind, target, action, reason):
    api.call("POST", "/v1/admin/moderation/decisions", admin, json={
        "target_type": kind, "target_id": target, "action": action,
        "reason_code": reason, "expected_head_decision_id": None,
    })


def _schedule(api, provider, listing, instant=False):
    api.call("PUT", f"/v1/classifieds/{listing}/viewing-settings", provider, json={
        "booking_mode": "INSTANT_BOOKING" if instant else "REQUEST_APPROVAL",
        "duration_minutes": 30, "minimum_notice_minutes": 0, "max_concurrent_bookings": 5,
        "timezone": "Europe/Warsaw",
    })
    for weekday in range(7):
        api.call("POST", f"/v1/classifieds/{listing}/viewing-windows", provider, json={
            "window_type": "WEEKLY", "weekday": weekday,
            "local_start_time": "10:00", "local_end_time": "16:00",
        })


def _request(api, seeker, listing):
    day = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    slot = api.call("GET", f"/v1/classifieds/{listing}/viewing-slots",
                    params={"start": day, "days": 1}).json()["slots"][0]
    return api.call("POST", f"/v1/classifieds/{listing}/viewings", seeker, json={
        "starts_at": slot, "note": "Fikcyjna notatka FE003 — nie dane osobowe.",
    }).json()["id"]


def _conversation(api, seeker, provider, listing):
    result = api.call("POST", f"/v1/classifieds/{listing}/conversations", seeker, json={
        "body": "Fikcyjne pytanie FE003 o ofertę.", "client_message_id": str(uuid4()),
    }).json()
    conversation = result["conversation"]["id"]
    message = api.call("POST", f"/v1/conversations/{conversation}/messages", provider, json={
        "body": "Fikcyjna odpowiedź FE003 do zgłoszenia.", "client_message_id": str(uuid4()),
    }).json()["id"]
    return conversation, message


def _project(api, admin, areas, project, index):
    accounts, tokens = {}, {}
    for key in ACCOUNT_KEYS:
        email = _email(project, key)
        role = "host" if key in ("provider", "unverified_provider", "host_without_authority") else "guest"
        api.call("POST", "/v1/auth/register", expect=(201,), json={
            "email": email, "password": PASSWORD, "full_name": f"Anna Testowa {project}", "role": role,
        })
        tokens[key] = api.login(email, PASSWORD)
        accounts[key] = {"email": email, "password": PASSWORD}
        if key in ("provider", "unverified_provider"):
            api.call("PUT", "/v1/me/legal-identity", tokens[key], json={
                "legal_first_name": "Anna", "legal_last_name": "Fikcyjna",
            })
    for offset, key in enumerate(("phone_seeker", "restricted_seeker")):
        _phone(api, tokens[key], f"+48600103{index}{offset}0")
    api.call("POST", "/v1/me/mandates", tokens["provider"], expect=(202,), json={
        "representative_email": accounts["guest_provider"]["email"],
        "scopes": ["MANAGE_MESSAGES", "MANAGE_VIEWINGS"],
    })
    listings, conversations, messages, viewings = {}, {}, {}, {}
    for n, key in enumerate(LISTING_KEYS):
        provider = tokens["unverified_provider" if key == "unverified" else "provider"]
        listing = base._publish(api, provider, admin, areas, n, base.Listing(
            "F-LUB", "fe003", "ul. Fikcyjna FE003", 51.2465, 22.5684,
            f"FE003 {project} {key}", 3000, photo=None,
            contact_mode="phone" if key in ("phone", "restricted") else "message",
            contact_phone=f"+48600903{index}00" if key in ("phone", "restricted") else "",
        ))
        listings[key] = listing

        if key in ("approval", "instant", "held", "restricted", "past_requested", "past_confirmed", "unverified"):
            _schedule(api, provider, listing, instant=key in ("instant", "past_confirmed"))
        if key in ("held", "restricted", "past_requested", "past_confirmed", "unverified"):
            seeker = tokens["restricted_seeker" if key == "restricted" else "seeker"]
            viewings[key] = _request(api, seeker, listing)
        if key in ("approval", "restricted", "closed", "redacted", "unverified"):
            seeker = tokens["restricted_seeker" if key == "restricted" else "seeker"]
            conversations[key], messages[key] = _conversation(api, seeker, provider, listing)
        if key == "restricted":
            api.call("POST", f"/v1/classifieds/{listing}/contact", tokens["restricted_seeker"])
            _decision(api, admin, "CONVERSATION", conversations[key], "FEATURE_RESTRICTED", "HARASSMENT")
        elif key == "closed":
            _decision(api, admin, "CONVERSATION", conversations[key], "FEATURE_RESTRICTED", "HARASSMENT")
        elif key == "redacted":
            _decision(api, admin, "MESSAGE", messages[key], "CONTENT_REMOVED", "HARASSMENT")
        elif key == "held":
            _decision(api, admin, "LISTING", listing, "VISIBILITY_LIMITED", "SAFETY")
        elif key == "unavailable":
            api.call("POST", f"/v1/me/saved-listings/{listing}", tokens["seeker"])
            api.call("POST", f"/v1/classifieds/{listing}/pause", provider)
        elif key in ("past_requested", "past_confirmed"):
            # Fixture-only clock movement; real API created the state and its facts.
            # No endpoint permits moving an existing viewing into history.
            with SessionLocal() as db:
                viewing = db.get(Viewing, viewings[key])
                assert viewing is not None
                delta = viewing.starts_at - (datetime.now(timezone.utc) - timedelta(days=2))
                viewing.starts_at -= delta
                viewing.ends_at -= delta
                viewing.created_at -= delta
                if viewing.responded_at:
                    viewing.responded_at -= delta
                db.commit()
        elif key == "unverified":
            # There is no API to withdraw verification while retaining an active
            # root (revoke is a different state). Required negative BP-9 fixture.
            with SessionLocal() as db:
                offer = db.get(ClassifiedOffer, listing)
                assert offer is not None
                root = db.scalar(select(PropertyAuthority).where(
                    PropertyAuthority.property_id == offer.property_id))
                assert root is not None
                root.verification_state = "UNVERIFIED"
                db.commit()
    messages["reportable"] = messages["approval"]
    for key in ("closed", "restricted"):
        detail = api.call("GET", f"/v1/conversations/{conversations[key]}",
                          tokens["restricted_seeker" if key == "restricted" else "seeker"]).json()
        messages[f"{key}_system"] = next(m["id"] for m in detail["messages"] if m["message_type"] == "SYSTEM")
    return {"accounts": accounts, "listings": listings, "conversations": conversations,
            "messages": messages, "viewings": viewings}


def _require(condition, message):
    if not condition:
        raise SystemExit(f"Incomplete or changed FE-003 fixtures: {message}; recreate the disposable database and manifest.")


def verify(api, manifest):
    """Read real projections; reject partial, consumed or incorrectly scoped fixtures."""
    _require(manifest.get("version") == 1, "manifest version")
    _require(set(manifest.get("projects", {})) == set(PROJECTS), "project inventory")
    for project in PROJECTS:
        data = manifest["projects"][project]
        accounts, listings = data["accounts"], data["listings"]
        _require(set(accounts) == set(ACCOUNT_KEYS), "account inventory")
        _require(set(listings) == set(LISTING_KEYS), "listing inventory")
        _require(set(data["conversations"]) == {"approval", "restricted", "closed", "redacted", "unverified"},
                 "conversation inventory")
        _require(set(data["viewings"]) == {"held", "restricted", "past_requested", "past_confirmed", "unverified"},
                 "viewing inventory")
        _require(set(data["messages"]) == set(data["conversations"]) | {
            "reportable", "closed_system", "restricted_system"}, "message inventory")
        tokens = {}
        for key, account in accounts.items():
            _require(account == {"email": _email(project, key), "password": PASSWORD}, "account identity")
            tokens[key] = api.login(account["email"], account["password"])
            me = api.call("GET", "/v1/me", tokens[key]).json()
            expected_role = "host" if key in (
                "provider", "unverified_provider", "host_without_authority") else "guest"
            _require(me["role"] == expected_role, f"account role: {project}/{key}")
        for key, listing in listings.items():
            with SessionLocal() as db:
                offer = db.get(ClassifiedOffer, listing)
                _require(offer is not None and offer.title == f"FE003 {project} {key}", "listing identity")
            expected = 404 if key in ("held", "unavailable") else 200
            api.call("GET", f"/v1/classifieds/{listing}", expect=(expected,))
        # No settings GET endpoint exists. Inspect persisted configuration without
        # changing it; public slots intentionally do not expose booking mode.
        booking_modes = {
            "approval": "REQUEST_APPROVAL", "instant": "INSTANT_BOOKING",
            "held": "REQUEST_APPROVAL", "restricted": "REQUEST_APPROVAL",
            "past_requested": "REQUEST_APPROVAL", "past_confirmed": "INSTANT_BOOKING",
            "unverified": "REQUEST_APPROVAL",
        }
        with SessionLocal() as db:
            for key, mode in booking_modes.items():
                schedule = db.get(ViewingSettings, listings[key])
                _require(schedule is not None and schedule.booking_mode == mode,
                         f"booking mode: {project}/{key}")
        for key in ("approval", "instant"):
            slots = api.call("GET", f"/v1/classifieds/{listings[key]}/viewing-slots").json()
            _require(slots["timezone"] == "Europe/Warsaw" and slots["slots"], "public offered slots")
        for key in ("seeker", "phone_seeker", "restricted_seeker"):
            me = api.call("GET", "/v1/me", tokens[key]).json()
            _require(bool(me["phone_verified_at"]) == (key != "seeker"), "phone verification")
            _require(me["email_verified_at"] is None, "unverified email")
        for key, conversation in data["conversations"].items():
            seeker = tokens["restricted_seeker" if key == "restricted" else "seeker"]
            detail = api.call("GET", f"/v1/conversations/{conversation}", seeker).json()
            _require(detail["conversation"]["listing_id"] == listings[key], "conversation identity")
            _require(detail["conversation"]["status"] == ("CLOSED" if key in ("closed", "restricted") else "ACTIVE"), "conversation status")
            reply = next((m for m in detail["messages"] if m["id"] == data["messages"][key]), None)
            _require(reply and reply["message_type"] == "USER", "participant USER reply")
            _require((reply["body"] is None) == (key == "redacted"), "message redaction")
            if key in ("closed", "restricted"):
                _require(any(m["id"] == data["messages"][f"{key}_system"] and m["message_type"] == "SYSTEM"
                             for m in detail["messages"]), "closure SYSTEM message")
        _require(data["messages"]["reportable"] == data["messages"]["approval"], "reportable message")
        for actor in ("provider", "guest_provider"):
            api.call("GET", f"/v1/conversations/{data['conversations']['approval']}", tokens[actor])
            api.call("GET", f"/v1/classifieds/{listings['held']}/viewings", tokens[actor])
        for actor in ("unverified_provider", "host_without_authority"):
            api.call("GET", f"/v1/conversations/{data['conversations']['unverified']}", tokens[actor], expect=(404,))
            api.call("GET", f"/v1/classifieds/{listings['unverified']}/viewings", tokens[actor], expect=(404,))
        expected_states = {"held": "REQUESTED", "restricted": "CANCELLED", "past_requested": "REQUESTED",
                           "past_confirmed": "CONFIRMED", "unverified": "REQUESTED"}
        for key, viewing in data["viewings"].items():
            seeker = tokens["restricted_seeker" if key == "restricted" else "seeker"]
            rows = api.call("GET", "/v1/me/viewings", seeker).json()
            row = next((v for v in rows if v["id"] == viewing), None)
            _require(row and row["status"] == expected_states[key] and row["listing_id"] == listings[key], "viewing state")
            start = datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00"))
            _require((start < datetime.now(timezone.utc)) == key.startswith("past_"), "viewing clock")
            if key == "restricted":
                _require(row["cancelled_by"] == "HOMIES", "moderation cancellation source")
        saved = api.call("GET", "/v1/me/saved-listings", tokens["seeker"]).json()["items"]
        tombstones = [x for x in saved if x["listing_id"] == listings["unavailable"]]
        _require(len(tombstones) == 1 and tombstones[0]["listing"] is None
                 and tombstones[0]["availability_status"] == "NO_LONGER_AVAILABLE", "saved tombstone")
        with SessionLocal() as db:
            restricted_user = db.scalar(select(User.id).where(
                User.email == accounts["restricted_seeker"]["email"]))
            _require(db.scalar(select(ContactReveal.id).where(
                ContactReveal.offer_id == listings["restricted"],
                ContactReveal.viewer_id == restricted_user)) is not None, "prior phone reveal")
            unverified = db.get(ClassifiedOffer, listings["unverified"])
            root = db.scalar(select(PropertyAuthority).where(
                PropertyAuthority.property_id == unverified.property_id))
            _require(root is not None and root.status == "ACTIVE"
                     and root.verification_state == "UNVERIFIED", "unverified active root")
        refusal = api.call("POST", f"/v1/classifieds/{listings['restricted']}/contact",
                           tokens["restricted_seeker"], expect=(409,)).json()
        _require(refusal["detail"].startswith("RECONTACT_BLOCKED:"), "repeat contact restriction")


def run(manifest_path: Path) -> None:
    _guard()  # Before database reads, writes, client creation or output-file writes.
    _require(manifest_path.parent.is_dir(), "manifest parent directory does not exist")
    with SessionLocal() as db:
        users = list(db.scalars(select(User.email).where(User.email.like("fe003-%@example.com"))))
        _require(db.scalar(select(User.id).where(User.email == base.ADMIN_EMAIL)) is not None,
                 "run the standard seed_e2e first")
    old_rate_limit = settings.rate_limit_enabled
    settings.rate_limit_enabled = False  # This process's in-process client only.
    api = base._Api()
    try:
        if users:
            _require(set(users) == {_email(p, k) for p in PROJECTS for k in ACCOUNT_KEYS}, "partial account inventory")
            _require(manifest_path.is_file(), "existing fixtures without their completion manifest")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise SystemExit("Unreadable FE-003 manifest; recreate the disposable database and manifest.") from None
        else:
            _require(not manifest_path.exists(), "stale manifest for an empty fixture namespace")
            admin = api.login(base.ADMIN_EMAIL, base.ADMIN_PASSWORD)
            areas = _areas()
            manifest = {"version": 1, "locality_id": areas["F-LUB"], "projects": {
                project: _project(api, admin, areas, project, index)
                for index, project in enumerate(PROJECTS)
            }}
        verify(api, manifest)
        if not users:
            # A completion marker is written only after every real projection passes.
            # Exclusive creation refuses overwriting a manifest owned by another run.
            fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        print("FE-003 synthetic fixtures verified (desktop and mobile); manifest ready.")
    finally:
        api.client.close()
        settings.rate_limit_enabled = old_rate_limit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    run(args.manifest)


if __name__ == "__main__":
    main()
