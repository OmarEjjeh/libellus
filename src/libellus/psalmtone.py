"""On-demand psalm/Magnificat GABC generation via the vendored jgabc engine.

``psalm-library/generate.js`` (plain JS, no npm dependencies) points the
accented Clementine psalter to any Liber Usualis tone. It ships inside the
package, because every build of every feast calls it and an installed wheel
without it could not set a single psalm (ADR-0024).

The verses are generated at resolve time into the ``build/.cache/`` copy of
``chant/**/toni/`` — nothing generated is ever stored, in the package or in the
repository.

Requires a JavaScript runtime: ``node`` (preferred) or ``bun``.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from functools import cache
from pathlib import Path
from typing import Any

from libellus.paths import CACHE_PREFIX, bundled

logger = logging.getLogger(__name__)

#: Absolute: the engine ships in the package, so it is found the same way
#: whether libellus runs from a checkout or from site-packages.
GENERATOR = bundled("psalm-library", "generate.js")


class PsalmToneError(Exception):
    """A German, user-facing message about psalm-tone generation."""


def _runtime() -> str:
    for candidate in ("node", "bun"):
        if shutil.which(candidate):
            return candidate
    raise PsalmToneError(
        "Zum Erzeugen der Psalmnoten wird eine JavaScript-Laufzeit gebraucht "
        "(Befehl „node“ oder „bun“), aber keine davon ist installiert. "
        "Node.js gibt es unter https://nodejs.org/."
    )


def _run(*args: str) -> Any:
    command = [_runtime(), str(GENERATOR), *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 2) or not result.stdout.strip():
        raise PsalmToneError(
            f"Der Notengenerator „{GENERATOR}“ ist fehlgeschlagen "
            f"({' '.join(args)}): {result.stderr.strip() or 'keine Ausgabe'}"
        )
    payload = json.loads(result.stdout)
    if result.returncode == 2:
        raise PsalmToneError(_german_error(payload))
    return payload


def _german_error(payload: dict) -> str:
    error: str = payload.get("error", "unbekannter Fehler")
    if error.startswith("unknown tone"):
        return (
            f"Den Ton {error.split('tone ')[1]} gibt es nicht. "
            f"Gültige Töne: {', '.join(payload.get('toni', []))}."
        )
    if error.startswith("unknown psalm"):
        return (
            f"Den Psalm {error.split('psalm ')[1]} gibt es nicht "
            f"(gültig: 1–150 oder „magnificat“)."
        )
    return f"Der Notengenerator meldet: {error}"


def list_toni() -> list[str]:
    """All valid tone labels as the engine prints them (books' spelling).

    :raises PsalmToneError: German message when no JS runtime is installed.
    """
    return _run("list-toni")


@cache
def euouae_per_tonus() -> dict[str, str]:
    """Every tone label mapped to its EUOUAE (termination cue) notes.

    Mode plus differentia fully determine these notes, so they are always
    derived from the engine, never hand-supplied (issue #33). Six
    whitespace-separated neumes each, one per syllable of "E u o u a e".

    Cached: the tone table is a pinned, vendored constant (see
    ``psalm-library/vendor/PROVENANCE.md``), but deriving it runs every tone
    through the engine — far too slow to repeat per antiphon.

    :raises PsalmToneError: German message when no JS runtime is installed.
    """
    return _run("euouae")


def generate_verses(
    psalmus: int | str, tonus: str, open_notes: bool = False
) -> tuple[str, list[str]]:
    """Generate all verses of a psalm (or ``"magnificat"``) in a tone.

    :param psalmus: Psalm number 1–150, or ``"magnificat"``.
    :param tonus: Tone label as the books print it, e.g. ``8G*`` or ``8 G``.
    :param open_notes: Draw every reciting note the verse puts no syllable on
        as a hollow note, as the Liber prints a tone. Only the two-verse
        Magnificat system needs this (ADR-0022); booklet verses are closed.
    :return: ``(folder, verses)`` — the canonical tone folder name (e.g.
        ``8gstar``) and one complete gabc file content per verse.
    :raises PsalmToneError: German message (unknown tone/psalm, no runtime).
    """
    extra = ["--open-notes"] if open_notes else []
    payload = _run("verses", "--psalmus", str(psalmus), "--tonus", tonus, *extra)
    logger.debug(
        "Psalmnoten erzeugt: %s im Ton %s (%d Verse, Ordner %s).",
        psalmus, tonus, len(payload["verses"]), payload["folder"],
    )
    return payload["folder"], payload["verses"]


def write_verse_cache(
    library_dir: Path, folder: str, verses: list[str], content_root: Path
) -> list[Path]:
    """Generate the verses of ``<library_dir>/toni/<folder>/`` into the cache.

    The returned paths are the *logical* ones the rendered TeX will reference
    and a staged folder will reproduce; the bytes are written under
    ``build/.cache/`` instead, because ``library_dir`` names a directory inside
    the installed package, which may be read-only (ADR-0024).

    The folder is wiped first so a rerun can never leave stale verses.

    :return: Logical, staging-relative paths of the written ``vNN.gabc`` files.
    """
    logical_dir = library_dir / "toni" / folder
    tone_dir = content_root / CACHE_PREFIX / logical_dir
    if tone_dir.exists():
        shutil.rmtree(tone_dir)
    tone_dir.mkdir(parents=True)
    written: list[Path] = []
    for index, content in enumerate(verses, start=1):
        (tone_dir / f"v{index:02d}.gabc").write_text(content, encoding="utf-8")
        written.append(logical_dir / f"v{index:02d}.gabc")
    logger.debug("Notencache geschrieben: %s (%d Dateien).", tone_dir, len(written))
    return written
