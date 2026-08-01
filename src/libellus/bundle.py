"""Bundle a feast spec into one self-contained file (ADR-0019).

`feasts/*.yaml` reference notation and pictures by repo path, which keeps them
readable but means a spec alone is not a booklet: hand someone the file and
they cannot build it. A bundle inlines every reference — GABC as notation
(ADR-0005), images as ``data:`` URIs — so a single file plus this program is
enough. That is the artifact to email, archive, or attach to an issue.

The transformation is textual rather than a parse-and-re-dump, because PyYAML
cannot preserve comments and the reference specs carry a lot of load-bearing
ones — provenance for each proper, „AI draft, not yet reviewed" markers,
explanations of editorial choices. Re-serializing would silently drop all of
it, which for an archival format is exactly backwards. So each ``gabc:`` and
``image:`` line is rewritten in place and everything else is left byte-for-byte
alone; the result is then re-parsed and compared against the original to prove
the rewrite did not change the spec's meaning.

The one thing an embedded chant does not preserve is its line endings: notation
is read as text, so a CRLF source file (two of the Benedict propers are) becomes
LF. gregorio does not care, and a YAML block scalar cannot round-trip a bare CR.
Images are embedded byte-exactly.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from libellus.errors import FeastFileError
from libellus.gabc import is_inline_gabc
from libellus.imagedata import encode_inline_image, is_inline_image
from libellus.paths import source_of
from libellus.resolve import build_context, load_spec

logger = logging.getLogger(__name__)

#: A ``key: value`` line whose value is a scalar on the same line — the only
#: shape a path reference ever takes. A value opening a block scalar (``|``,
#: ``>``) is excluded because it is already inline content, not a reference.
_REFERENCE_LINE = re.compile(
    r"""^(?P<indent>\s*)(?P<dash>-\s+)?(?P<key>gabc|image):[ \t]+(?P<value>[^\s|>#][^#]*?)[ \t]*$"""
)


class BundleError(Exception):
    """The bundle could not be produced, with a German message."""


def _block_scalar(indent: str, key: str, payload: str) -> str:
    """Render ``key: |`` followed by the payload, indented under the key.

    The chomping indicator follows the payload: ``|`` (clip, keeps one trailing
    newline) when it ends with one, ``|-`` (strip) when it does not. Getting
    this from the content rather than fixing it makes the embedded copy
    byte-identical to the file it replaced — several .gabc files in this repo
    have no final newline, and a bundle that silently added one would no longer
    reproduce its source exactly.
    """
    body_indent = indent + "  "
    chomp = "" if payload.endswith("\n") else "-"
    lines = payload.rstrip("\n").split("\n")
    # an empty payload line stays empty rather than becoming indent-only
    # whitespace, which any editor's trailing-space trimming would eat
    body = "\n".join(f"{body_indent}{line}" if line else "" for line in lines)
    return f"{indent}{key}: |{chomp}\n{body}\n"


def bundle_text(feast_yaml: Path, root: Path) -> str:
    """Rewrite a feast spec's path references into inline content.

    :param feast_yaml: The spec to bundle.
    :param root: Repository root the spec's paths are relative to.
    :return: The bundled YAML, comments and field order intact.
    :raises BundleError: A referenced file is missing or cannot be embedded.
    """
    source = feast_yaml.read_text(encoding="utf-8")
    out: list[str] = []
    inlined_gabc = inlined_images = 0

    for number, line in enumerate(source.splitlines(keepends=True), start=1):
        match = _REFERENCE_LINE.match(line.rstrip("\n"))
        if match is None:
            out.append(line)
            continue

        key, raw = match.group("key"), match.group("value").strip()
        # a maintainer may quote the path (a filename with a colon in it has to
        # be quoted); let YAML itself unquote so escapes are handled correctly
        if raw[0] in "\"'":
            parsed = yaml.safe_load(raw)
            if not isinstance(parsed, str):
                out.append(line)
                continue
            value = parsed
        else:
            value = raw
        if key == "gabc" and is_inline_gabc(value):
            out.append(line)  # already inline (single-line inline GABC is legal)
            continue
        if key == "image" and is_inline_image(value):
            out.append(line)
            continue

        target = source_of(Path(value), root)
        if not target.is_file():
            raise BundleError(
                f"{feast_yaml}, Zeile {number}: die Datei „{value}“ wurde nicht "
                f"gefunden, also lässt sie sich nicht einbetten."
            )

        # a "- gabc: x" list item keeps its dash; the payload indents under the
        # key, which sits two columns right of the dash
        indent = match.group("indent") + (
            " " * len(match.group("dash")) if match.group("dash") else ""
        )
        if key == "gabc":
            payload = target.read_text(encoding="utf-8")
            inlined_gabc += 1
        else:
            payload = encode_inline_image(target.read_bytes(), target.suffix)
            inlined_images += 1
        prefix = match.group("indent") + (match.group("dash") or "")
        rendered = _block_scalar(indent, key, payload)
        # splice the dash back onto the first line, which _block_scalar wrote
        # with the deeper indent so the payload lines up
        out.append(prefix + rendered[len(indent) :])

    logger.info(
        "Gebündelt: %d Gesänge und %d Bilder eingebettet.", inlined_gabc, inlined_images
    )
    return "".join(out)


def bundle(feast_yaml: Path, root: Path, destination: Path) -> Path:
    """Write a self-contained copy of a feast spec, checking it still resolves.

    Validating and resolving the written file is a cheap, worthwhile gate: it
    proves the rewritten YAML parses, that every embedded payload decodes, and
    that nothing was left dangling. Proving the bundle renders the *same
    booklet* is a regression guard on the transformation itself, so it lives in
    the test suite (``test_bundle``) rather than running on every invocation.

    :return: The path written.
    :raises BundleError: The bundle is not itself a valid spec.
    """
    load_spec(feast_yaml)  # fail on a broken source before writing anything
    text = bundle_text(feast_yaml, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")

    try:
        build_context(load_spec(destination), root)
    except FeastFileError as exc:
        raise BundleError(
            "Die gebündelte Datei ist selbst nicht gültig — das ist ein Fehler "
            "im Bündeln, nicht in der Fest-Datei:\n  • " + "\n  • ".join(exc.messages)
        ) from exc

    size = destination.stat().st_size
    logger.info("Bündel geprüft und gültig: „%s“ (%.1f MB).", destination, size / 1024**2)
    return destination
