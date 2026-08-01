"""Inline images in a feast spec: an RFC 2397 ``data:`` URI instead of a path.

The counterpart to inline GABC (ADR-0005) for pictures, and what makes a
bundled spec (ADR-0019) buildable rather than merely readable: one file with
no outside references.

A data URI is used rather than bare base64 because it carries its own MIME
type, and the MIME type is what gives the materialized file its suffix —
LuaLaTeX picks its graphics driver by extension, so ``\\includegraphics`` on a
suffixless file fails. Guessing the format from magic bytes would work too,
but then a hand-edited spec has no way to say what it pasted.
"""

from __future__ import annotations

import base64
import binascii
import re

#: The formats LuaLaTeX can set, as MIME type ↔ suffix. Kept in step with
#: ``resolve.IMAGE_SUFFIXES``; ``.jpeg`` normalizes to ``.jpg`` on the way in.
MIME_TO_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/pdf": ".pdf",
}
SUFFIX_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}

#: Only the prefix is matched — the payload may be wrapped over many lines by
#: the YAML block scalar it usually arrives in.
_PREFIX = re.compile(r"\s*data:([\w.+-]+/[\w.+-]+);base64,", re.IGNORECASE)

#: Bundles wrap the payload at this width so the YAML stays diffable-ish and
#: no editor has to render a single multi-megabyte line.
WRAP_COLUMNS = 76


#: Print-size thresholds, mirroring `RIESIG_AB` / `ZU_SCHMAL_UNTER` in
#: form/formular.html. An A5 page is ~10 cm of image width, so 300 dpi wants
#: ~1200 px and 3000 px is already generous. **Keep both in step with the
#: form's constants** — the build only warns, the form actually acts on them.
HUGE_ABOVE = 3000
TOO_NARROW_BELOW = 1200


class InlineImageError(ValueError):
    """A ``data:`` URI that cannot be decoded, with a German message."""


def image_width(data: bytes) -> int | None:
    """Pixel width of a PNG or JPEG, without decoding the pixels.

    Enough to reproduce the form's two size checks at build time, for pictures
    that never went through the form. Deliberately header-only: pulling in
    Pillow to read two integers would be a dependency for a warning.

    :return: The width, or ``None`` for a format not covered (PDF, or a JPEG
        whose marker chain does not parse) — callers must treat that as
        "cannot tell", never as a problem.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        # IHDR is always the first chunk: 8 signature + 4 length + 4 type
        return int.from_bytes(data[16:20], "big")
    if not data.startswith(b"\xff\xd8"):
        return None
    # walk the JPEG marker chain to the frame header, which carries the size
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        # SOF0..SOF15 hold the dimensions; DHT/JPG/DAC share the range but not
        # the payload, and are skipped like any other segment
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[offset + 7 : offset + 9], "big")
        segment = int.from_bytes(data[offset + 2 : offset + 4], "big")
        if segment < 2:
            return None
        offset += 2 + segment
    return None


def is_inline_image(value: str) -> bool:
    """Whether a spec's ``image:`` value is a data URI rather than a repo path."""
    return _PREFIX.match(value) is not None


def decode_inline_image(value: str) -> tuple[bytes, str]:
    """Decode a data URI into its bytes and the file suffix to store it under.

    :param value: The full ``data:<mime>;base64,<payload>`` string; the
        payload may contain arbitrary whitespace and line breaks.
    :return: ``(payload_bytes, suffix)``, suffix including the leading dot.
    :raises InlineImageError: Unsupported MIME type or undecodable base64.
    """
    match = _PREFIX.match(value)
    if match is None:  # pragma: no cover - callers gate on is_inline_image
        raise InlineImageError("Der Wert ist keine „data:“-URI.")
    mime = match.group(1).lower()
    suffix = MIME_TO_SUFFIX.get(mime)
    if suffix is None:
        raise InlineImageError(
            f"Das eingebettete Bild hat den Typ „{mime}“, den LaTeX nicht "
            f"setzen kann (erlaubt: {', '.join(sorted(MIME_TO_SUFFIX))})."
        )
    payload = "".join(value[match.end() :].split())
    try:
        # validate=True so a stray character is an error rather than silently
        # dropped — a truncated paste must not yield a half-decoded image
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InlineImageError(
            f"Das eingebettete Bild ist kein gültiges Base64: {exc}"
        ) from exc
    if not data:
        raise InlineImageError("Das eingebettete Bild ist leer.")
    return data, suffix


def encode_inline_image(data: bytes, suffix: str) -> str:
    """Build the data URI for an image file's bytes.

    :param suffix: The source file's suffix, e.g. ``.png`` (case-insensitive).
    :return: ``data:<mime>;base64,`` followed by the payload, wrapped at
        :data:`WRAP_COLUMNS` and newline-separated (no trailing newline).
    :raises InlineImageError: The suffix is not a settable image format.
    """
    mime = SUFFIX_TO_MIME.get(suffix.lower())
    if mime is None:
        raise InlineImageError(
            f"Ein Bild mit der Endung „{suffix}“ kann nicht eingebettet werden "
            f"(erlaubt: {', '.join(sorted(SUFFIX_TO_MIME))})."
        )
    payload = base64.b64encode(data).decode("ascii")
    lines = [
        payload[i : i + WRAP_COLUMNS] for i in range(0, len(payload), WRAP_COLUMNS)
    ]
    return "\n".join([f"data:{mime};base64,", *lines])
