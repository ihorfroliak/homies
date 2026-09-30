"""Make an uploaded photo safe to publish: decode it, bound it, re-encode it.

A photo from a phone carries EXIF, and EXIF carries the GPS position where it
was taken — for a listing photo, the flat itself. XMP can carry the same
coordinates, text chunks and comments whatever the editing app wrote, and an
ICC profile's name is free text too. Publishing any of it would undo what the
approximate map point protects (properties/location.py).

Until TASK-002 this module walked the JPEG/PNG structure and copied the
segments it trusted. TASK-001 showed why that is not a trust boundary: after
the first scan everything was copied verbatim (APP1 after SOS, APP2, APP14,
bytes after a false EOI), a PNG iCCP name survived, and PNGs the walker
accepted were not decodable at all. The parser and the browser disagreed.

So now the image is **decoded by a maintained library (Pillow) and rebuilt
from its pixels**:

1. the format is decided by the decoder from the bytes — JPEG or PNG only,
   whatever the client's Content-Type says;
2. dimensions are checked against an explicit budget *before* pixels are
   decoded (width, height and total pixels — 16 000 × 16 000 passes each
   axis limit and is still refused);
3. the pixels are fully decoded; truncated or corrupt data is a refusal;
4. EXIF orientation is applied to the pixels, so the photo is upright
   without keeping the EXIF that said how to rotate it;
5. colour is normalised: an embedded ICC profile is used once to convert the
   pixels to sRGB and is then discarded — the profile's bytes are never
   copied (a profile we cannot use is simply dropped);
6. a new image is built from the pixel data alone — no `info`, no EXIF, no
   XMP, no text, no ICC — and encoded as JPEG or PNG;
7. the output is decoded again as a check before it is accepted.

Only the first frame of an animated PNG or a multi-picture JPEG is kept.
Nothing uploaded is ever stored as it arrived.
"""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageFile, ImageOps, UnidentifiedImageError

JPEG = "image/jpeg"
PNG = "image/png"

# Recorded on every file this pipeline produces (FileObject.processing_version).
# 1 was never recorded: bytes from the C8 walker carry NULL and are quarantined.
PIPELINE_VERSION = 2

# The processing budget (TASK-002 §29). A 12 MP phone photo is ~4000×3000;
# 50 MP sensors reach ~8200×6200. The total-pixel cap is what bounds memory:
# 40 MP of RGBA is ~160 MB while decoding.
MAX_WIDTH = 10_000
MAX_HEIGHT = 10_000
MAX_PIXELS = 40_000_000
JPEG_QUALITY = 88

# Decoder names Pillow reports for what we accept. MPO is a JPEG with extra
# pictures appended (some cameras); only its first picture is kept.
_ACCEPTED = {"JPEG": JPEG, "MPO": JPEG, "PNG": PNG}
_OUTPUT_FORMAT = {JPEG: "JPEG", PNG: "PNG"}
_SRGB = ImageCms.createProfile("sRGB")

# A truncated file must be refused, never padded with grey. This is Pillow's
# default; set explicitly so no other import can quietly flip it.
ImageFile.LOAD_TRUNCATED_IMAGES = False
# Pillow's own decompression-bomb guard (warning above, error at twice this),
# aligned with our budget so no other Image.open in the process is looser.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class RejectedImage(ValueError):
    """The upload is not an image this service will publish."""


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    mime_type: str
    width: int
    height: int


def _check_budget(width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise RejectedImage("the image has no pixels")
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        raise RejectedImage(f"the image is larger than {MAX_WIDTH}×{MAX_HEIGHT} pixels")
    if width * height > MAX_PIXELS:
        raise RejectedImage(f"the image has more than {MAX_PIXELS:,} pixels")


def _to_srgb(image: Image.Image, icc: bytes | None) -> Image.Image:
    """Pixels expressed in sRGB. The profile is read, never copied."""
    if not icc or image.mode not in ("RGB", "RGBA"):
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        converted = ImageCms.profileToProfile(image, source, _SRGB, outputMode=image.mode)
    except (ImageCms.PyCMSError, OSError, ValueError, TypeError):
        # A profile that cannot be used is dropped; the pixels stay as they are.
        return image
    return converted if converted is not None else image


def _normalised_mode(image: Image.Image, mime: str) -> Image.Image:
    if mime == JPEG:
        if image.mode in ("L", "RGB"):
            return image
        return image.convert("RGB")
    if image.mode in ("L", "LA", "RGB", "RGBA"):
        return image
    # Palette, 16-bit, CMYK and the rest: RGBA keeps any transparency.
    return image.convert("RGBA")


def _decode(data: bytes) -> tuple[Image.Image, str]:
    with warnings.catch_warnings():
        # Pillow warns before it errors on huge images; treat both as refusal.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        opened = Image.open(io.BytesIO(data), formats=["JPEG", "PNG"])
        with opened:
            mime = _ACCEPTED.get(opened.format or "")
            if mime is None:
                raise RejectedImage("only JPEG and PNG images are accepted")
            _check_budget(*opened.size)
            icc = opened.info.get("icc_profile")
            opened.seek(0)
            opened.load()
            upright = ImageOps.exif_transpose(opened)
            _check_budget(*upright.size)
            pixels = _normalised_mode(_to_srgb(upright, icc), mime)
            # A brand-new image from raw pixel bytes: nothing of the source's
            # `info` (EXIF, XMP, ICC, text, comments) can ride along.
            fresh = Image.frombytes(pixels.mode, pixels.size, pixels.tobytes())
    return fresh, mime


def _encode(image: Image.Image, mime: str) -> bytes:
    out = io.BytesIO()
    if mime == JPEG:
        image.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    else:
        image.save(out, "PNG", optimize=False)
    return out.getvalue()


def _verify(data: bytes, mime: str, size: tuple[int, int]) -> None:
    with Image.open(io.BytesIO(data), formats=[_OUTPUT_FORMAT[mime]]) as check:
        check.load()
        if check.size != size:
            raise RejectedImage("the image could not be re-encoded faithfully")


def sanitize(data: bytes) -> CleanImage:
    """A publishable image rebuilt from `data`, or RejectedImage.

    Every decoder failure is a refusal, never a 500 and never a partial file.
    """
    if not data:
        raise RejectedImage("the upload is empty")
    try:
        image, mime = _decode(data)
        encoded = _encode(image, mime)
        _verify(encoded, mime, image.size)
    except RejectedImage:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise RejectedImage(f"the image has more than {MAX_PIXELS:,} pixels") from None
    except UnidentifiedImageError:
        raise RejectedImage("only JPEG and PNG images are accepted") from None
    except (OSError, SyntaxError, ValueError, EOFError, IndexError, KeyError, TypeError):
        # Truncated, corrupt or internally inconsistent image data.
        raise RejectedImage("the image data is corrupt or incomplete") from None
    return CleanImage(data=encoded, mime_type=mime, width=image.width, height=image.height)
