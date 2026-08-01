"""Embedded images: the data: URI form of `image:` fields (ADR-0019)."""

import base64
import logging
from pathlib import Path

import pytest
import yaml
from conftest import BENEDICT_FEAST

from libellus.errors import FeastFileError
from libellus.formdata import form_data
from libellus.imagedata import (
    InlineImageError,
    decode_inline_image,
    encode_inline_image,
    image_width,
    is_inline_image,
)
from libellus.resolve import INLINE_IMAGE_DIR, build_context
from libellus.schema import FeastSpec

from helpers import physical

#: Smallest possible real PNG (1×1, fully transparent) — enough for every
#: encode/decode assertion without carrying a fixture file around.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _benedict_data(repo_root: Path) -> dict:
    return yaml.safe_load((repo_root / BENEDICT_FEAST).read_text(encoding="utf-8"))


def test_a_repo_path_is_not_an_inline_image() -> None:
    assert not is_inline_image("images/02-benedict/medal-print.png")


def test_round_trip_preserves_the_bytes() -> None:
    uri = encode_inline_image(TINY_PNG, ".png")
    assert is_inline_image(uri)
    assert decode_inline_image(uri) == (TINY_PNG, ".png")


def test_payload_is_wrapped_so_no_editor_meets_a_megabyte_long_line() -> None:
    uri = encode_inline_image(TINY_PNG * 40, ".png")
    assert max(len(line) for line in uri.splitlines()) <= 76


def test_jpeg_normalizes_to_a_single_suffix() -> None:
    """.jpg and .jpeg share one MIME type, so both come back as .jpg — the
    materialized filename must be predictable."""
    assert decode_inline_image(encode_inline_image(TINY_PNG, ".jpeg"))[1] == ".jpg"
    assert decode_inline_image(encode_inline_image(TINY_PNG, ".jpg"))[1] == ".jpg"


def test_indented_payload_decodes() -> None:
    """A YAML block scalar indents every line; the decoder must not care."""
    uri = encode_inline_image(TINY_PNG, ".png")
    assert decode_inline_image(uri.replace("\n", "\n      ")) == (TINY_PNG, ".png")


def test_an_unsettable_format_is_refused() -> None:
    with pytest.raises(InlineImageError, match="image/webp"):
        decode_inline_image("data:image/webp;base64,AAAA")
    with pytest.raises(InlineImageError, match="webp"):
        encode_inline_image(TINY_PNG, ".webp")


def test_truncated_base64_is_an_error_not_a_half_image() -> None:
    """validate=True in the decoder: a clipped paste must fail loudly rather
    than yield a corrupt file LaTeX then chokes on."""
    with pytest.raises(InlineImageError, match="Base64"):
        decode_inline_image("data:image/png;base64,not valid base64 !!")


def test_empty_payload_is_an_error() -> None:
    with pytest.raises(InlineImageError, match="leer"):
        decode_inline_image("data:image/png;base64,")


def test_a_broken_data_prefix_is_reported_as_such(repo_root: Path) -> None:
    """Without this the value falls through as a "path" and the maintainer
    gets a file-not-found naming a multi-megabyte string."""
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = "data:image/png,oops-no-base64-marker"
    with pytest.raises(ValueError, match="data:"):
        FeastSpec.model_validate(data)


def test_embedded_back_cover_materializes_and_is_staged(repo_root: Path) -> None:
    """The decoded image lands in the gitignored cache and is recorded as an
    asset, so staging copies it exactly like a repo file."""
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = encode_inline_image(TINY_PNG, ".png")
    resolved = build_context(FeastSpec.model_validate(data), repo_root)

    expected = INLINE_IMAGE_DIR / "rueckseite.png"
    assert expected in resolved.assets
    assert physical(expected).read_bytes() == TINY_PNG
    # the template reads the resolved path, never the spec's data URI
    assert resolved.context["back_cover_image"] == expected.as_posix()


def test_embedded_filler_image_materializes_per_page(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["filler"][1]["image"] = encode_inline_image(TINY_PNG, ".png")
    resolved = build_context(FeastSpec.model_validate(data), repo_root)

    expected = INLINE_IMAGE_DIR / "zusatzseite-02.png"
    assert expected in resolved.assets
    assert physical(expected).read_bytes() == TINY_PNG
    assert resolved.context["filler"][1]["image"] == expected.as_posix()


def test_an_unsettable_embedded_format_is_caught_at_validation(repo_root: Path) -> None:
    """The schema decodes every data URI, so a bad one is a validation error —
    the maintainer hears about it before any file is written, and `resolve`
    can decode without a failure branch."""
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = "data:image/gif;base64,R0lGODlhAQABAAAAACw="
    with pytest.raises(ValueError, match="image/gif"):
        FeastSpec.model_validate(data)


def test_a_missing_image_file_still_reports_per_slot(repo_root: Path) -> None:
    """Path values keep their old per-slot German errors after the refactor."""
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = "images/02-benedict/does-not-exist.png"
    data["filler"][1]["image"] = "images/02-benedict/nor-this.png"
    with pytest.raises(FeastFileError) as excinfo:
        build_context(FeastSpec.model_validate(data), repo_root)
    messages = excinfo.value.messages
    assert any("Rückseitenbild" in m and "nicht gefunden" in m for m in messages)
    assert any("2. Zusatzseite" in m and "nicht gefunden" in m for m in messages)


def test_the_decoded_cache_is_kept_out_of_the_form_island(repo_root: Path) -> None:
    """Regression: the island scans all of images/, so materializing an
    embedded image made the picker offer a per-build artifact — and left the
    committed island permanently "veraltet" after any build."""
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = encode_inline_image(TINY_PNG, ".png")
    build_context(FeastSpec.model_validate(data), repo_root)

    cached = INLINE_IMAGE_DIR / "rueckseite.png"
    assert physical(cached).is_file(), "precondition: the cache copy exists"
    assert cached.as_posix() not in form_data(repo_root)["image_paths"]


def test_image_width_reads_png_and_jpeg_headers(repo_root: Path) -> None:
    """Header-only parsing, checked against `magick identify` values."""
    png = repo_root / "images/02-benedict/medal-print.png"
    jpeg = repo_root / "images/03-lambert/St-Lambert-Liège.jpg"
    assert image_width(png.read_bytes()) == 764
    assert image_width(jpeg.read_bytes()) == 1280
    assert image_width(TINY_PNG) == 1


def test_image_width_gives_up_rather_than_guessing() -> None:
    """A format the parser does not cover must read as "cannot tell", never as
    a width — callers warn on the answer."""
    assert image_width(b"%PDF-1.7\nnot really a pdf") is None
    assert image_width(b"\xff\xd8totally truncated") is None
    assert image_width(b"") is None


def test_a_narrow_image_warns_but_still_builds(
    repo_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The form applies these thresholds; a hand-added file bypasses it, so the
    build echoes the same check. Both current Benedict pictures are under it."""
    with caplog.at_level(logging.WARNING, logger="libellus.resolve"):
        build_context(FeastSpec.model_validate(_benedict_data(repo_root)), repo_root)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Rückseitenbild" in m and "1018 px" in m and "1200" in m for m in warnings)


def test_an_oversized_image_names_the_form_as_the_fix(
    repo_root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Above the upper threshold the form would have downscaled it, so the
    warning points there rather than just stating a number."""
    wide = tmp_path / "wide.png"
    # a real PNG header is all image_width reads; the pixels are irrelevant
    wide.write_bytes(
        b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
        + (4000).to_bytes(4, "big") + (100).to_bytes(4, "big") + TINY_PNG[24:]
    )
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = str(wide.relative_to(repo_root, walk_up=True))
    with caplog.at_level(logging.WARNING, logger="libellus.resolve"):
        build_context(FeastSpec.model_validate(data), repo_root)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("4000 px" in m and "Formular" in m for m in warnings)


def test_a_webp_path_still_gets_the_conversion_hint(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["back_cover"]["image"] = "images/02-benedict/some-picture.webp"
    with pytest.raises(FeastFileError) as excinfo:
        build_context(FeastSpec.model_validate(data), repo_root)
    assert any("PNG umwandeln" in m for m in excinfo.value.messages)
