"""TASK-001 media findings, reproduced and closed (TASK-002 R3).

F-02: private metadata survived upload → approval → attach → anonymous GET.
F-05: the upload limit was checked only after the whole body was buffered.
Plus the treatment of files the old C8 walker produced: quarantined, never
served, reprocessed before they can be.

Against the pre-TASK-002 code every test in the first two sections fails.
"""

import asyncio
import io
import zlib

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.modules.identity.models import User
from app.modules.media import storage
from app.modules.media.models import FileObject, MediaAsset
from app.scripts import reprocess_media
from tests import media_corpus as corpus
from tests.conftest import TestingSession, admin_login, auth, register_and_login, verify_ownership

PROPERTY = {"property_type": "apartment", "city": "Rzeszów", "municipality": "Rzeszów",
            "address": "ul. Audytowa 17", "area_m2": 50, "rooms": 2, "capacity": 3}
OFFER = {"title": "Audyt", "rent_amount": 210000, "min_term_months": 12,
         "contact_mode": "message"}
OWNER_EMAIL = "audit-owner@example.com"


@pytest.fixture
def listing(client):
    owner = register_and_login(client, OWNER_EMAIL, "host")
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, prop)
    offer = client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    assert client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner)).status_code == 200
    return owner, prop, offer


def _upload(client, owner, prop, data, content_type="image/jpeg"):
    return client.post(f"/v1/properties/{prop}/media", params={"rights_declared": "true"},
                       content=data, headers={**auth(owner), "Content-Type": content_type})


def _publish_photo(client, owner, prop, offer, data):
    """upload → admin approval → attach → the anonymous public GET."""
    uploaded = _upload(client, owner, prop, data)
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()["id"]
    admin = admin_login(client)
    assert client.post(f"/v1/admin/media/{asset}/approve", headers=auth(admin)).status_code == 200
    attached = client.post(f"/v1/classifieds/{offer}/media",
                           json={"media_asset_id": asset, "is_cover": True}, headers=auth(owner))
    assert attached.status_code == 201, attached.text
    return asset, client.get(f"/v1/media/{asset}")


# --- F-02: nothing private reaches the public ------------------------------------

SECRET = b"GPSLatitude=52.229676;GPSLongitude=21.012229;PrivateAddress=Audit17"


def _real_jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(out, "JPEG", progressive=True)
    return out.getvalue()


def _codex_variant(kind: str) -> bytes:
    """The four JPEGs TASK-001 used, byte for byte in construction."""
    original = _real_jpeg()
    if kind == "APP1_after_scan":
        return (original[:-2] + corpus.seg(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + SECRET)
                + original[-2:])
    if kind in ("APP2", "APP14"):
        return original[:2] + corpus.seg(0xE2 if kind == "APP2" else 0xEE, SECRET) + original[2:]
    return original + b"PK\x03\x04" + SECRET + b"\xff\xd9"


@pytest.mark.parametrize("kind", ["APP1_after_scan", "APP2", "APP14", "after_EOI"])
def test_f02_a_hidden_payload_does_not_survive_to_the_public(client, listing, kind):
    owner, prop, offer = listing
    data = _codex_variant(kind)
    Image.open(io.BytesIO(data)).load()  # a real decoder shows it as a picture
    _, served = _publish_photo(client, owner, prop, offer, data)
    assert served.status_code == 200
    assert SECRET not in served.content
    with Image.open(io.BytesIO(served.content)) as image:
        image.load()
        assert not image.getexif() and "icc_profile" not in image.info


def test_f02_a_png_icc_profile_name_does_not_survive_to_the_public(client, listing):
    owner, prop, offer = listing
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(buffer, "PNG")
    raw = buffer.getvalue()
    icc = zlib.compress(corpus.srgb_icc())
    data = raw[:33] + corpus.chunk(b"iCCP", SECRET[:70] + b"\x00\x00" + icc) + raw[33:]
    Image.open(io.BytesIO(data)).load()
    _, served = _publish_photo(client, owner, prop, offer, data)
    assert served.status_code == 200
    assert SECRET[:40] not in served.content
    assert b"iCCP" not in served.content


def test_f02_exif_gps_does_not_survive_to_the_public(client, listing):
    owner, prop, offer = listing
    data = corpus.jpeg()
    assert Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825)
    _, served = _publish_photo(client, owner, prop, offer, data)
    assert served.status_code == 200
    assert not corpus.leaks(served.content)
    with Image.open(io.BytesIO(served.content)) as image:
        assert not image.getexif().get_ifd(0x8825)


# --- F-05: the body is bounded while it streams ----------------------------------


def _call_upload(prop, receive, headers=()):
    from app.modules.media.router import upload_media

    request = Request({"type": "http", "method": "POST", "path": "/", "headers": list(headers)},
                      receive)
    with TestingSession() as db:
        user = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        return asyncio.run(upload_media(prop, request, media_type="PHOTO", space_id=None,
                                        rights_declared=True, user=user, db=db))


@pytest.mark.parametrize(("limit", "chunk", "chunks"), [(16, 10, 4), (100_000, 65_536, 200)])
def test_f05_reading_stops_at_the_limit_without_content_length(
    client, listing, monkeypatch, limit, chunk, chunks
):
    """TASK-001 reproduction: 4 × 10 bytes against a 16-byte limit used to be
    read to the end (40 bytes) before the 413. Now reading stops at the first
    chunk that crosses the limit."""
    _, prop, _ = listing
    monkeypatch.setattr(settings, "media_max_bytes", limit)
    consumed: list[int] = []

    async def receive():
        consumed.append(chunk)
        return {"type": "http.request", "body": b"x" * chunk,
                "more_body": len(consumed) < chunks}

    with pytest.raises(HTTPException) as refused:
        _call_upload(prop, receive)
    assert refused.value.status_code == 413
    assert sum(consumed) <= limit + chunk
    assert len(consumed) < chunks


def test_f05_a_false_small_content_length_does_not_lift_the_limit(client, listing, monkeypatch):
    _, prop, _ = listing
    monkeypatch.setattr(settings, "media_max_bytes", 16)
    consumed: list[int] = []

    async def receive():
        consumed.append(10)
        return {"type": "http.request", "body": b"x" * 10, "more_body": len(consumed) < 50}

    with pytest.raises(HTTPException) as refused:
        _call_upload(prop, receive, headers=[(b"content-length", b"5")])
    assert refused.value.status_code == 413
    assert sum(consumed) <= 26


def test_f05_a_chunked_upload_over_the_limit_is_refused_over_http(client, listing, monkeypatch):
    owner, prop, _ = listing
    monkeypatch.setattr(settings, "media_max_bytes", 1_000)

    def body():
        for _ in range(100):
            yield b"x" * 100

    response = client.post(f"/v1/properties/{prop}/media", params={"rights_declared": "true"},
                           content=body(), headers={**auth(owner), "Content-Type": "image/jpeg"})
    assert response.status_code == 413


def test_f05_a_declared_oversize_is_refused_before_reading(client, listing, monkeypatch):
    _, prop, _ = listing
    monkeypatch.setattr(settings, "media_max_bytes", 16)
    consumed: list[int] = []

    async def receive():
        consumed.append(1)
        return {"type": "http.request", "body": b"x", "more_body": False}

    with pytest.raises(HTTPException) as refused:
        _call_upload(prop, receive, headers=[(b"content-length", b"999999")])
    assert refused.value.status_code == 413
    assert consumed == []


# --- files from the old walker ---------------------------------------------------


def _legacy(asset_id, raw: bytes | None = None):
    """Put a file into the state migration c1e3a5b7d9f2 leaves C8 files in —
    optionally with the leaky bytes the old walker would have stored."""
    with TestingSession() as db:
        file = db.get(FileObject, db.get(MediaAsset, asset_id).file_id)
        file.processing_version = None
        file.state = "QUARANTINED"
        file.access_class = "QUARANTINE"
        if raw is not None:
            storage.storage().put(file.storage_key, raw)
        db.commit()


def test_a_quarantined_file_is_not_served_listed_or_attachable(client, listing):
    owner, prop, offer = listing
    asset, served = _publish_photo(client, owner, prop, offer, corpus.jpeg())
    assert served.status_code == 200
    _legacy(asset, raw=corpus.jpeg())

    assert client.get(f"/v1/media/{asset}").status_code == 404
    assert client.get(f"/v1/classifieds/{offer}").json()["media"] == []
    again = client.post(f"/v1/classifieds/{offer}/media",
                        json={"media_asset_id": asset}, headers=auth(owner))
    assert again.status_code == 409


def test_approving_a_quarantined_file_does_not_make_it_public(client, listing):
    owner, prop, offer = listing
    asset, _ = _publish_photo(client, owner, prop, offer, corpus.jpeg())
    _legacy(asset)
    admin = admin_login(client)
    assert client.post(f"/v1/admin/media/{asset}/approve", headers=auth(admin)).status_code == 200
    with TestingSession() as db:
        assert db.get(FileObject, db.get(MediaAsset, asset).file_id).access_class == "QUARANTINE"
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_reprocessing_strips_old_bytes_and_restores_an_approved_photo(client, listing):
    owner, prop, offer = listing
    asset, _ = _publish_photo(client, owner, prop, offer, corpus.jpeg())
    leaky = corpus.jpeg(extra_segments=corpus.seg(0xE2, SECRET))
    _legacy(asset, raw=leaky)

    with TestingSession() as db:
        report = reprocess_media.reprocess(db)
    assert len(report.reprocessed) == 1 and report.rejected == []

    served = client.get(f"/v1/media/{asset}")
    assert served.status_code == 200
    assert SECRET not in served.content and not corpus.leaks(served.content)


def test_a_file_that_no_longer_decodes_is_rejected_by_reprocessing(client, listing):
    owner, prop, offer = listing
    asset, _ = _publish_photo(client, owner, prop, offer, corpus.jpeg())
    _legacy(asset, raw=b"\xff\xd8 not really a jpeg")
    with TestingSession() as db:
        report = reprocess_media.reprocess(db)
    assert report.rejected and not report.reprocessed
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_uploads_beyond_the_processing_budget_wait_then_get_503(client, listing, monkeypatch):
    """Decoding is bounded in concurrency as well as in size: with every slot
    taken, an upload waits the configured time and then answers 503."""
    import threading

    from app.modules.media import router as media_router

    owner, prop, _ = listing
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(media_router, "_processing_slots", slots)
    monkeypatch.setattr(settings, "media_processing_wait_seconds", 0.05)
    response = _upload(client, owner, prop, corpus.jpeg())
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    slots.release()
    assert _upload(client, owner, prop, corpus.jpeg()).status_code == 201
