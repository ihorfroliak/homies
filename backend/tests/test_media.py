"""Property photos through the API (Domain Schema v1 §36–§38, §48, §121).

A phone photo carries the GPS position where it was taken — for a listing,
the flat — and publishing it unaltered would hand out the address the
approximate map point hides. Every image here is a real, decodable picture
(tests/media_corpus.py) with that metadata planted in it, and the tests look
for it in what is stored and what is served. The decoder-level corpus is in
test_media_pipeline.py; TASK-001's reproductions are in
test_media_regressions.py.
"""

import io

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import settings
from app.modules.media import storage
from app.modules.media.models import FileObject, ListingMedia, MediaAsset
from tests.conftest import (
    TestingSession,
    admin_login,
    auth,
    register_and_login,
    verify_ownership,
)
from tests.media_corpus import jpeg, leaks, png


def _leaks(data: bytes) -> bool:
    return leaks(data)


def test_storage_keys_cannot_climb_out_of_the_store(tmp_path):
    store = storage.LocalStorage(str(tmp_path))
    for key in ("../escape", "a/../../escape", "/abs/path", "UPPER"):
        with pytest.raises(ValueError):
            store.put(key, b"x")


# --- the API ------------------------------------------------------------------

PROPERTY = {"property_type": "apartment", "city": "Rzeszów", "municipality": "Rzeszów",
            "address": "ul. Zdjęciowa 1", "area_m2": 50, "rooms": 2, "capacity": 3}
OFFER = {"title": "Ze zdjęciami", "rent_amount": 210000, "min_term_months": 12,
         "contact_mode": "message"}


@pytest.fixture
def owner(client):
    return register_and_login(client, "photo-owner@example.com", "host")


@pytest.fixture
def listing(client, owner):
    prop = client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()
    verify_ownership(client, owner, prop["id"])
    offer = client.post(f"/v1/properties/{prop['id']}/classifieds", json=OFFER,
                        headers=auth(owner)).json()["id"]
    client.post(f"/v1/classifieds/{offer}/publish", headers=auth(owner))
    return {"property": prop["id"], "offer": offer}


def _upload(client, token, property_id, data=None, content_type="image/jpeg", rights=True):
    return client.post(
        f"/v1/properties/{property_id}/media",
        params={"rights_declared": "true" if rights else "false"},
        content=jpeg() if data is None else data,
        headers={**auth(token), "Content-Type": content_type},
    )


def _approved(client, token, property_id, data=None):
    asset = _upload(client, token, property_id, data)
    assert asset.status_code == 201, asset.text
    admin = admin_login(client)
    assert client.post(f"/v1/admin/media/{asset.json()['id']}/approve",
                       headers=auth(admin)).status_code == 200
    return asset.json()["id"]


def _attach(client, token, offer, asset, cover=False, order=0):
    return client.post(f"/v1/classifieds/{offer}/media",
                       json={"media_asset_id": asset, "is_cover": cover, "sort_order": order},
                       headers=auth(token))


def test_what_is_stored_carries_no_location(client, owner, listing):
    asset = _upload(client, owner, listing["property"])
    assert asset.status_code == 201, asset.text
    with TestingSession() as db:
        file = db.get(FileObject, db.get(MediaAsset, asset.json()["id"]).file_id)
        stored = storage.storage().get(file.storage_key)
    assert not _leaks(stored)
    assert asset.json()["width_px"] == 64
    with Image.open(io.BytesIO(stored)) as image:
        assert not image.getexif() and "icc_profile" not in image.info


def test_what_is_served_carries_no_location(client, owner, listing):
    asset = _approved(client, owner, listing["property"])
    _attach(client, owner, listing["offer"], asset, cover=True)
    served = client.get(f"/v1/media/{asset}")
    assert served.status_code == 200
    assert not _leaks(served.content)
    assert served.headers["x-content-type-options"] == "nosniff"


def test_the_type_is_decided_by_the_bytes_not_the_header(client, owner, listing):
    """A PNG labelled image/jpeg is served as what it is."""
    asset = _approved(client, owner, listing["property"], data=png())
    _attach(client, owner, listing["offer"], asset)
    assert client.get(f"/v1/media/{asset}").headers["content-type"] == "image/png"


def test_a_non_image_is_refused_and_nothing_is_stored(client, owner, listing):
    resp = _upload(client, owner, listing["property"], data=b"<script>x</script>")
    assert resp.status_code == 422
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(FileObject)) == 0


def test_the_right_to_publish_must_be_declared(client, owner, listing):
    assert _upload(client, owner, listing["property"], rights=False).status_code == 422


def test_an_oversized_upload_is_refused(client, owner, listing):
    original = settings.media_max_bytes
    settings.media_max_bytes = 100
    try:
        assert _upload(client, owner, listing["property"]).status_code == 413
    finally:
        settings.media_max_bytes = original


def test_a_stranger_cannot_upload_to_your_property(client, listing):
    stranger = register_and_login(client, "photo-thief@example.com", "host")
    assert _upload(client, stranger, listing["property"]).status_code == 404


# --- moderation and what the public sees ---------------------------------------


def test_a_pending_photo_cannot_go_on_a_listing(client, owner, listing):
    asset = _upload(client, owner, listing["property"]).json()["id"]
    assert _attach(client, owner, listing["offer"], asset).status_code == 409


def test_a_pending_photo_is_never_served(client, owner, listing):
    asset = _upload(client, owner, listing["property"]).json()["id"]
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_an_approved_photo_off_every_listing_is_not_served(client, owner, listing):
    """Knowing an id is not access."""
    asset = _approved(client, owner, listing["property"])
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_a_paused_listing_stops_serving_its_photos(client, owner, listing):
    asset = _approved(client, owner, listing["property"])
    _attach(client, owner, listing["offer"], asset)
    assert client.get(f"/v1/media/{asset}").status_code == 200
    client.post(f"/v1/classifieds/{listing['offer']}/pause", headers=auth(owner))
    assert client.get(f"/v1/media/{asset}").status_code == 404


def test_a_rejected_photo_comes_off_the_listing(client, owner, listing):
    asset = _approved(client, owner, listing["property"])
    _attach(client, owner, listing["offer"], asset, cover=True)
    admin = admin_login(client)
    client.post(f"/v1/admin/media/{asset}/reject", headers=auth(admin))

    assert client.get(f"/v1/media/{asset}").status_code == 404
    public = client.get(f"/v1/classifieds/{listing['offer']}").json()
    assert public["media"] == []
    # Taken off, not merely hidden: if it were approved again later it must
    # not reappear on the listing without the owner putting it back.
    with TestingSession() as db:
        assert db.scalar(select(func.count()).select_from(ListingMedia).where(
            ListingMedia.media_asset_id == asset)) == 0


def test_a_photo_restricted_after_attaching_is_not_shown(client, owner, listing):
    """Defence in depth for moderation states that do not detach: whatever
    is on the listing, the public sees only what is APPROVED right now."""
    asset = _approved(client, owner, listing["property"])
    _attach(client, owner, listing["offer"], asset, cover=True)
    with TestingSession() as db:
        db.get(MediaAsset, asset).moderation_state = "RESTRICTED"
        db.commit()
    assert client.get(f"/v1/classifieds/{listing['offer']}").json()["media"] == []


def test_the_public_listing_shows_approved_photos_cover_first(client, owner, listing):
    first = _approved(client, owner, listing["property"])
    cover = _approved(client, owner, listing["property"], data=png())
    _attach(client, owner, listing["offer"], first, order=0)
    _attach(client, owner, listing["offer"], cover, cover=True, order=5)

    media = client.get(f"/v1/classifieds/{listing['offer']}").json()["media"]
    assert [m["id"] for m in media] == [cover, first]
    assert media[0]["is_cover"] is True
    assert media[0]["url"] == f"/v1/media/{cover}"


def test_a_new_cover_replaces_the_old_one(client, owner, listing):
    a = _approved(client, owner, listing["property"])
    b = _approved(client, owner, listing["property"], data=png())
    _attach(client, owner, listing["offer"], a, cover=True)
    _attach(client, owner, listing["offer"], b, cover=True)
    covers = [m["id"] for m in client.get(f"/v1/classifieds/{listing['offer']}").json()["media"]
              if m["is_cover"]]
    assert covers == [b]


def test_the_database_holds_one_cover(client, owner, listing):
    a = _approved(client, owner, listing["property"])
    b = _approved(client, owner, listing["property"], data=png())
    _attach(client, owner, listing["offer"], a, cover=True)
    with TestingSession() as db:
        db.add(ListingMedia(listing_id=listing["offer"], media_asset_id=b, is_cover=True))
        with pytest.raises(Exception):  # noqa: B017 — unique violation
            db.commit()


def test_another_propertys_photo_cannot_be_borrowed(client, owner, listing):
    other = client.post("/v1/properties", json={**PROPERTY, "address": "ul. Inna 9"},
                        headers=auth(owner)).json()["id"]
    verify_ownership(client, owner, other)
    foreign = _approved(client, owner, other)
    assert _attach(client, owner, listing["offer"], foreign).status_code == 404


def test_only_admins_moderate(client, owner, listing):
    asset = _upload(client, owner, listing["property"]).json()["id"]
    assert client.post(f"/v1/admin/media/{asset}/approve",
                       headers=auth(owner)).status_code == 403


def test_photo_writes_are_throttled(client):
    from app.core import ratelimit as rl

    assert rl.resolve_policy("POST", "/v1/properties/x/media") is rl.PROPERTY_WRITE
    assert rl.resolve_policy("POST", "/v1/classifieds/x/media") is rl.PROPERTY_WRITE
