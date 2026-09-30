"""The media trust boundary, decoder level (TASK-002 R3).

Every accepted image is decoded, bounded, re-encoded from its pixels, and the
output decoded again. These tests check the output with a decoder, not by
looking for marker bytes alone: an image is safe to publish when what a
browser would read from it is the picture and nothing else.
"""

import io
import random

import pytest
from PIL import Image

from app.modules.media import sanitize
from tests import media_corpus as corpus


def _decoded(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def _assert_clean(clean: sanitize.CleanImage) -> Image.Image:
    assert not corpus.leaks(clean.data)
    image = _decoded(clean.data)
    assert (image.width, image.height) == (clean.width, clean.height)
    assert not image.getexif(), "EXIF survived"
    assert "icc_profile" not in image.info, "ICC profile bytes survived"
    assert "exif" not in image.info and "xmp" not in image.info
    if clean.mime_type == sanitize.JPEG:
        # APP0 (JFIF), DQT, SOF, DHT, SOS — no APP1..APP15, no COM.
        markers = corpus.jpeg_segments(clean.data)
        assert not [m for m in markers if 0xE1 <= m <= 0xEF or m == 0xFE], markers
        # Nothing after the end of the image.
        assert clean.data.endswith(b"\xff\xd9")
    else:
        assert set(corpus.png_chunks(clean.data)) <= {b"IHDR", b"PLTE", b"tRNS", b"IDAT",
                                                       b"IEND"}
        assert not {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"iCCP"} & set(
            corpus.png_chunks(clean.data))
    return image


# --- valid inputs, stripped -----------------------------------------------------


@pytest.mark.parametrize("progressive", [False, True])
def test_a_jpeg_with_gps_exif_xmp_iptc_and_a_comment_is_rebuilt_clean(progressive):
    source = corpus.jpeg(progressive=progressive)
    assert corpus.leaks(source)
    assert _decoded(source).getexif().get_ifd(0x8825), "fixture must carry a GPS IFD"
    clean = sanitize.sanitize(source)
    assert clean.mime_type == sanitize.JPEG
    _assert_clean(clean)


def test_a_png_with_text_ztxt_itxt_and_exif_chunks_is_rebuilt_clean():
    source = corpus.png()
    assert corpus.leaks(source)
    clean = sanitize.sanitize(source)
    assert clean.mime_type == sanitize.PNG
    _assert_clean(clean)


def test_a_png_icc_profile_name_does_not_survive():
    """TASK-001: the iCCP chunk's profile name is free text — it carried GPS."""
    source = corpus.png(icc_name=corpus.GPS_TEXT)
    assert "icc_profile" in _decoded(source).info
    _assert_clean(sanitize.sanitize(source))


def test_a_jpeg_icc_profile_is_used_then_dropped():
    source = corpus.jpeg(icc=corpus.srgb_icc(corpus.SECRET))
    assert "icc_profile" in _decoded(source).info
    _assert_clean(sanitize.sanitize(source))


def test_an_unusable_icc_profile_is_dropped_not_fatal():
    source = corpus.jpeg(icc=b"not a profile at all " + corpus.SECRET)
    _assert_clean(sanitize.sanitize(source))


def test_exif_orientation_is_applied_to_the_pixels():
    source = corpus.jpeg(size=(40, 20), orientation=6)  # rotate 90° clockwise
    clean = sanitize.sanitize(source)
    assert (clean.width, clean.height) == (20, 40)
    _assert_clean(clean)


@pytest.mark.parametrize(
    ("maker", "mode", "expected_mime"),
    [
        (corpus.jpeg, "CMYK", sanitize.JPEG),
        (corpus.jpeg, "L", sanitize.JPEG),
        (corpus.png, "P", sanitize.PNG),
        (corpus.png, "LA", sanitize.PNG),
        (corpus.png, "RGBA", sanitize.PNG),
        (corpus.png, "I;16", sanitize.PNG),
    ],
)
def test_colour_modes_are_normalised(maker, mode, expected_mime):
    clean = sanitize.sanitize(maker(mode=mode))
    assert clean.mime_type == expected_mime
    _assert_clean(clean)


def test_only_the_first_frame_of_an_animated_png_is_kept():
    clean = sanitize.sanitize(corpus.apng(frames=3))
    image = _assert_clean(clean)
    assert getattr(image, "n_frames", 1) == 1


def test_data_after_the_end_of_a_jpeg_is_not_carried_over():
    """A JPEG with a ZIP behind it is a polyglot. The picture is kept; the
    passenger is not — the output is re-encoded from pixels."""
    source = corpus.jpeg(trailer=b"PK\x03\x04" + corpus.SECRET + b"\xff\xd9")
    clean = sanitize.sanitize(source)
    assert b"PK\x03\x04" not in clean.data
    _assert_clean(clean)


@pytest.mark.parametrize("marker", [0xE1, 0xE2, 0xEE, 0xEC, 0xED, 0xFE])
def test_metadata_segments_anywhere_before_the_scan_are_dropped(marker):
    source = corpus.jpeg(extra_segments=corpus.seg(marker, corpus.GPS_TEXT))
    _assert_clean(sanitize.sanitize(source))


# --- refused inputs -------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["GIF", "WEBP", "BMP", "TIFF"])
def test_other_real_image_formats_are_refused(fmt):
    with pytest.raises(sanitize.RejectedImage, match="JPEG and PNG"):
        sanitize.sanitize(corpus.other_format(fmt))


@pytest.mark.parametrize("data", [
    b"",
    b"not an image at all",
    b"%PDF-1.7 pretending",
    b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
    b"\xff\xd8\xff",
    b"\x89PNG\r\n\x1a\n",
])
def test_non_images_are_refused(data):
    with pytest.raises(sanitize.RejectedImage):
        sanitize.sanitize(data)


def test_a_truncated_jpeg_is_refused():
    source = corpus.jpeg(size=(96, 96))
    with pytest.raises(sanitize.RejectedImage, match="corrupt"):
        sanitize.sanitize(source[: len(source) * 2 // 3])


def test_a_png_truncated_into_its_pixels_is_refused():
    source = corpus.png(size=(96, 96))
    with pytest.raises(sanitize.RejectedImage):
        sanitize.sanitize(source[: len(source) * 2 // 3])


def test_a_png_missing_only_its_trailer_is_rebuilt_from_complete_pixels():
    """Pillow does not verify IDAT/IEND CRCs. When every pixel decodes, the
    output is a fresh encoding of those pixels — the damaged trailer is not
    carried over, so accepting it is safe. Recorded so the behaviour is a
    decision, not an accident."""
    source = corpus.png(size=(96, 96))
    _assert_clean(sanitize.sanitize(source[: len(source) - 12]))


@pytest.mark.parametrize("case", ["no_idat", "bad_zlib", "duplicate_ihdr"])
def test_pngs_the_old_walker_accepted_but_no_decoder_shows_are_refused(case):
    """TASK-001 parser differentials: the walker accepted these, a decoder
    does not. Now the decoder decides."""
    ihdr = corpus.chunk(b"IHDR", bytes.fromhex("0000000a0000000a0802000000"))
    sig = b"\x89PNG\r\n\x1a\n"
    data = {
        "no_idat": sig + ihdr + corpus.chunk(b"IEND", b""),
        "bad_zlib": sig + ihdr + corpus.chunk(b"IDAT", b"not-zlib") + corpus.chunk(b"IEND", b""),
        "duplicate_ihdr": sig + ihdr + ihdr + corpus.chunk(b"IEND", b""),
    }[case]
    with pytest.raises(sanitize.RejectedImage):
        sanitize.sanitize(data)


@pytest.mark.parametrize(
    ("width", "height", "reason"),
    [
        (16_000, 16_000, "larger than|more than"),  # Pillow's own guard may fire first
        (10_001, 10, "larger than"),
        (10, 10_001, "larger than"),
        (9_000, 9_000, "more than"),            # each axis fine, 81 MP total
        (10_000, 4_001, "more than"),
    ],
)
def test_the_pixel_budget_is_enforced_before_decoding(width, height, reason):
    with pytest.raises(sanitize.RejectedImage, match=reason):
        sanitize.sanitize(corpus.png_header_only(width, height))


def test_pillows_global_guard_matches_the_budget():
    """Defence in depth: any other Image.open in the process is bounded by
    the same budget, not Pillow's 89 MP default."""
    assert Image.MAX_IMAGE_PIXELS == sanitize.MAX_PIXELS


def test_the_budget_edge_is_accepted_in_principle():
    """40 MP exactly is within budget: the refusal above is the budget, not
    a blanket size refusal (header-only, so it then fails as corrupt data)."""
    with pytest.raises(sanitize.RejectedImage, match="corrupt"):
        sanitize.sanitize(corpus.png_header_only(8_000, 5_000))


def test_decoding_errors_are_refusals_never_crashes():
    """Deterministic mutation fuzzing of real images: every outcome is either
    a clean image or RejectedImage — never another exception (a 500)."""
    rng = random.Random(20260924)
    seeds = [corpus.jpeg(), corpus.jpeg(progressive=True), corpus.png(), corpus.apng()]
    outcomes = {"accepted": 0, "refused": 0}
    for _ in range(400):
        data = bytearray(rng.choice(seeds))
        for _ in range(rng.randint(1, 8)):
            op = rng.random()
            pos = rng.randrange(len(data))
            if op < 0.5:
                data[pos] = rng.randrange(256)
            elif op < 0.75:
                del data[pos:pos + rng.randint(1, 32)]
            else:
                data[pos:pos] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 32)))
        try:
            clean = sanitize.sanitize(bytes(data))
        except sanitize.RejectedImage:
            outcomes["refused"] += 1
            continue
        outcomes["accepted"] += 1
        _assert_clean(clean)
    assert outcomes["accepted"] and outcomes["refused"], outcomes
