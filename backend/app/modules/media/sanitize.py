"""Make an uploaded photo safe to publish: prove what it is, strip what it says.

A photo from a phone carries EXIF, and EXIF carries the GPS position where it
was taken — for a listing photo, the flat itself. Publishing it unaltered would
undo everything the approximate map point protects (location.py): anyone
could download the cover photo and read the address out of it. XMP can carry
the same coordinates, and text chunks carry whatever the editing app wrote.

So an image is rebuilt from its own structure with only what is needed to
display it:

* the format is decided by the bytes, never by the client's Content-Type;
* JPEG keeps its image segments and drops APP1 (Exif/XMP), APP12, APP13
  (IPTC/Photoshop) and comments; the entropy-coded data after SOS is copied
  unchanged;
* PNG keeps critical and colour chunks and drops eXIf and all text/time
  chunks; every chunk's CRC is checked.

This is a structure walker, not a decoder: it never interprets pixel data, so
there is nothing to decompress and no bomb to set off. Anything it cannot
account for exactly is refused rather than guessed at.
"""

import struct
import zlib
from dataclasses import dataclass

JPEG = "image/jpeg"
PNG = "image/png"

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_DIMENSION = 16_000

# JPEG markers that carry metadata rather than the image.
_JPEG_DROP = {0xE1, 0xEC, 0xED, 0xFE}  # APP1, APP12, APP13, COM
# Start-of-frame markers (the ones that carry dimensions).
_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
# PNG chunks that describe how to display the image; everything else goes.
_PNG_KEEP = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB",
             b"iCCP", b"sBIT", b"pHYs", b"bKGD"}


class RejectedImage(ValueError):
    """The bytes are not an image this service will publish."""


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    mime_type: str
    width: int
    height: int


def sanitize(data: bytes) -> CleanImage:
    if data.startswith(b"\xff\xd8\xff"):
        return _jpeg(data)
    if data.startswith(_PNG_SIGNATURE):
        return _png(data)
    raise RejectedImage("only JPEG and PNG images are accepted")


def _check_size(width: int, height: int) -> None:
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION):
        raise RejectedImage("image dimensions are out of range")


def _jpeg(data: bytes) -> CleanImage:
    out = bytearray(b"\xff\xd8")
    pos = 2
    size: tuple[int, int] | None = None
    while True:
        if pos + 4 > len(data) or data[pos] != 0xFF:
            raise RejectedImage("malformed JPEG segment")
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte before a marker
            pos += 1
            continue
        if marker == 0xD9:  # EOI with no scan: nothing to show
            raise RejectedImage("JPEG has no image data")
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if length < 2 or pos + 2 + length > len(data):
            raise RejectedImage("JPEG segment runs past the end of the file")
        segment = data[pos:pos + 2 + length]
        if marker in _JPEG_SOF:
            if length < 7:
                raise RejectedImage("malformed JPEG frame header")
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            size = (width, height)
        if marker == 0xDA:  # SOS: the rest is scan data and the trailer
            if size is None:
                raise RejectedImage("JPEG scan before frame header")
            _check_size(*size)
            out += data[pos:]
            if not bytes(out).rstrip(b"\x00").endswith(b"\xff\xd9"):
                raise RejectedImage("JPEG is truncated")
            return CleanImage(bytes(out), JPEG, size[0], size[1])
        if marker not in _JPEG_DROP:
            out += segment
        pos += 2 + length


def _png(data: bytes) -> CleanImage:
    out = bytearray(_PNG_SIGNATURE)
    pos = len(_PNG_SIGNATURE)
    size: tuple[int, int] | None = None
    seen_end = False
    while pos < len(data):
        if pos + 12 > len(data):
            raise RejectedImage("malformed PNG chunk")
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise RejectedImage("PNG chunk runs past the end of the file")
        body = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:end])[0]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise RejectedImage("PNG chunk is corrupt")
        if kind == b"IHDR":
            if length != 13:
                raise RejectedImage("malformed PNG header")
            size = struct.unpack(">II", body[:8])
        if kind in _PNG_KEEP:
            out += data[pos:end]
        pos = end
        if kind == b"IEND":
            seen_end = True
            break
    if size is None or not seen_end:
        raise RejectedImage("PNG is incomplete")
    _check_size(*size)
    return CleanImage(bytes(out), PNG, size[0], size[1])
