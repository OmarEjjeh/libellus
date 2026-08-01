"""Bundling a feast spec into one self-contained file (ADR-0019)."""

import hashlib
import re
from pathlib import Path

import pytest
from conftest import BENEDICT_FEAST, SMOKE_FEAST

from libellus.bundle import BundleError, bundle, bundle_text
from libellus.imagedata import is_inline_image
from libellus.paths import source_of
from libellus.render import render
from libellus.resolve import build_context, load_spec

#: Asset references in the rendered TeX: a score (path without its suffix) and
#: an \includegraphics target.
_SCORE = re.compile(r"\\gregorioscore\{([^}]+)\}")
_GRAPHIC = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?)\{([^}]+)\}")


def _digest(path: Path) -> str:
    """Content hash; a .gabc file's line endings and final newline normalized.

    Two differences are expected and meaningless to gregorio, so neither should
    fail this comparison:

    * `resolve._resolve_gabc` guarantees a final newline on every block it
      materializes, so an inlined chant whose source had none comes out one byte
      longer. That predates bundling and applies to all inline GABC.
    * embedding reads the file as text, so a CRLF source (two of the Benedict
      propers are CRLF) is normalized to LF — a YAML block scalar cannot carry a
      bare CR through a round-trip anyway.

    Images are compared byte-exactly: base64 round-trips exactly, so any
    difference there would be a real defect.
    """
    data = path.read_bytes()
    if path.suffix == ".gabc":
        data = data.replace(b"\r\n", b"\n").rstrip()
    return hashlib.sha256(data).hexdigest()[:16]


def _content_addressed_tex(feast: Path, root: Path) -> str:
    """Rendered TeX with each asset path replaced by a digest of its content.

    A bundled spec resolves its chants to ``chant/inline/…`` and its pictures to
    ``images/inline/…`` instead of their repo locations, so the raw TeX cannot
    match. Comparing by content answers the question that actually matters: does
    the bundle set the same notes, pictures and words?
    """
    spec = load_spec(feast)
    resolved = build_context(spec, root)
    tex = render(spec.rite, resolved.context, root)
    def by_content(path: str) -> str:
        # the preamble defines border macros whose \includegraphics argument
        # holds a TeX parameter (…gilded-edge-top-#3-feather.png), so not every
        # match names a real file; those are identical in both renderings anyway
        target = source_of(Path(path), root)
        return _digest(target) if target.is_file() else path

    tex = _SCORE.sub(lambda m: "\\gregorioscore{" + by_content(m.group(1) + ".gabc") + "}", tex)
    return _GRAPHIC.sub(lambda m: m.group(1) + "{" + by_content(m.group(2)) + "}", tex)


@pytest.mark.parametrize("feast", [SMOKE_FEAST, BENEDICT_FEAST])
def test_a_bundle_sets_exactly_the_same_booklet(
    feast: str, repo_root: Path, tmp_path: Path
) -> None:
    """The guarantee the format rests on. Both reference specs are covered:
    Lambert exercises inline propers + a back-cover photo, Benedict exercises
    path-referenced propers, a filler-page image and a `filler:` list."""
    source = repo_root / feast
    written = bundle(source, repo_root, tmp_path / "bundled.yaml")
    assert _content_addressed_tex(written, repo_root) == _content_addressed_tex(
        source, repo_root
    )


def test_every_reference_is_gone_from_the_bundle(repo_root: Path, tmp_path: Path) -> None:
    """"Self-contained" is the whole point: no `gabc:`/`image:` value may still
    name a file on disk."""
    written = bundle(repo_root / BENEDICT_FEAST, repo_root, tmp_path / "b.yaml")
    dangling = [
        line.strip()
        for line in written.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\s*-?\s*(gabc|image):[ \t]+[^\s|>]", line)
    ]
    assert dangling == []


def test_comments_survive_the_rewrite(repo_root: Path, tmp_path: Path) -> None:
    """Why the transformation is textual rather than a YAML re-dump: the
    reference specs' provenance and „AI draft" markers are load-bearing."""
    source = (repo_root / SMOKE_FEAST).read_text(encoding="utf-8")
    written = bundle(repo_root / SMOKE_FEAST, repo_root, tmp_path / "b.yaml")
    bundled = written.read_text(encoding="utf-8")

    comments = [line for line in source.splitlines() if line.lstrip().startswith("#")]
    assert len(comments) > 10, "precondition: the fixture is heavily commented"
    for comment in comments:
        assert comment in bundled
    assert "AI draft, not yet reviewed" in bundled


def test_bundling_is_idempotent(repo_root: Path, tmp_path: Path) -> None:
    """A bundle is itself a valid spec, so bundling it again must be a no-op —
    values that are already inline are left alone rather than re-wrapped."""
    once = bundle(repo_root / SMOKE_FEAST, repo_root, tmp_path / "once.yaml")
    twice = bundle(once, repo_root, tmp_path / "twice.yaml")
    assert twice.read_text(encoding="utf-8") == once.read_text(encoding="utf-8")


def test_images_become_data_uris(repo_root: Path, tmp_path: Path) -> None:
    written = bundle(repo_root / BENEDICT_FEAST, repo_root, tmp_path / "b.yaml")
    spec = load_spec(written)
    assert is_inline_image(spec.back_cover.image)
    page_images = [p.image for p in spec.filler if getattr(p, "image", None)]
    assert page_images and all(is_inline_image(image) for image in page_images)


def test_a_missing_referenced_file_names_the_line(repo_root: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    text = (repo_root / BENEDICT_FEAST).read_text(encoding="utf-8")
    broken.write_text(
        text.replace(
            "images/02-benedict/medal-print.png", "images/02-benedict/weg.png"
        ),
        encoding="utf-8",
    )
    with pytest.raises(BundleError, match=r"Zeile \d+.*weg\.png"):
        bundle_text(broken, repo_root)


def test_an_already_inline_block_is_left_untouched(repo_root: Path, tmp_path: Path) -> None:
    """A value opening a block scalar is content, not a reference."""
    spec_text = "\n".join(
        ["gabc: |", "  name:Already inline;", "  %%", "  (c4) Test(g) (::)"]
    )
    source = tmp_path / "fragment.yaml"
    source.write_text(spec_text + "\n", encoding="utf-8")
    assert bundle_text(source, repo_root) == spec_text + "\n"


def test_a_quoted_path_is_inlined_too(repo_root: Path, tmp_path: Path) -> None:
    """A path needing quotes (a colon in the filename) must not silently stay a
    dangling reference — YAML unquotes it, then it embeds like any other."""
    source = tmp_path / "fragment.yaml"
    source.write_text(
        'image: "images/02-benedict/medal-print.png"\n', encoding="utf-8"
    )
    result = bundle_text(source, repo_root)
    # |- since encode_inline_image emits no trailing newline
    assert result.startswith("image: |-\n")
    assert "data:image/png;base64," in result
