"""On-demand psalm/Magnificat GABC generation via the vendored jgabc engine.

``psalm-library/generate.js`` (plain JS, no npm dependencies) points the
accented Clementine psalter to any Liber Usualis tone. It ships inside the
package, because every build of every feast calls it and an installed wheel
without it could not set a single psalm (ADR-0024).

The verses are generated at resolve time into the ``build/.cache/`` copy of
``chant/**/toni/`` — nothing generated is ever stored, in the package or in the
repository.

Requires a JavaScript runtime. By default that is an installed ``node``
(preferred) or ``bun``, reached through a subprocess; a host that is itself a
JavaScript runtime supplies its own via :func:`set_engine`.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from libellus.paths import CACHE_PREFIX, bundled

logger = logging.getLogger(__name__)

#: Absolute: the engine ships in the package, so it is found the same way
#: whether libellus runs from a checkout or from site-packages.
GENERATOR = bundled("psalm-library", "generate.js")

#: Run ``generate.js`` with these arguments; return ``(exit code, stdout,
#: stderr)`` exactly as a process would. Everything the caller does with that —
#: which exit codes are legitimate, the JSON, the German messages — stays on
#: this side, so a host only has to know how to run the engine.
#:
#: The engine is already JavaScript, and ``generate.js`` needs no npm packages.
#: A host that *is* a JavaScript runtime calls it directly and deletes the
#: subprocess rather than emulating one (ADR-0027); the default below is the
#: subprocess, for the CLI against an installed node or bun.
Engine = Callable[[Sequence[str]], tuple[int, str, str]]


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


def subprocess_engine(args: Sequence[str]) -> tuple[int, str, str]:
    """Run the generator under an installed ``node`` or ``bun``. The default."""
    command = [_runtime(), str(GENERATOR), *args]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, result.stderr


_engine: Engine = subprocess_engine


def set_engine(engine: Engine) -> None:
    """Point psalm-tone generation at another JavaScript runtime.

    The browser application runs the engine in the page rather than in a
    process, because Pyodide has no ``subprocess`` and the engine is JavaScript
    already (ADR-0027). Pass :func:`subprocess_engine` to restore the default.
    """
    global _engine  # noqa: PLW0603 — one process-wide toolchain, chosen by the host
    logger.debug("Psalmnoten-Laufzeit gewechselt: %s.", getattr(engine, "__name__", engine))
    _engine = engine
    euouae_per_tonus.cache_clear()
    mediationes_per_tonus.cache_clear()


def _run(*args: str) -> Any:
    returncode, stdout, stderr = _engine(args)
    if returncode not in (0, 2) or not stdout.strip():
        raise PsalmToneError(
            f"Der Notengenerator „{GENERATOR}“ ist fehlgeschlagen "
            f"({' '.join(args)}): {stderr.strip() or 'keine Ausgabe'}"
        )
    payload = json.loads(stdout)
    if returncode == 2:
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
    if error.startswith("unknown mediatio"):
        return (
            f"Die Mediatio {error.split('mediatio ')[1]} gibt es nicht. "
            f"Möglich sind: {', '.join(payload.get('mediationes', []))}."
        )
    if error.startswith("no mediationes"):
        return (
            f"Der Ton {error.split('tone ')[1]} hat nur eine Mediatio, "
            f"also ist „mediatio:“ hier gegenstandslos — bitte das Feld "
            f"weglassen."
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


@cache
def mediationes_per_tonus() -> dict[str, list[str]]:
    """Tone label → the mediations it may be sung from, **first one the default**.

    Only the tones whose mediation the books leave open appear — today that is
    ``6F`` alone, where the Liber Usualis p. 117 prints two under one label
    (ADR-0043). A tone with a single mediation is absent rather than listed
    with one entry, so "is there a choice here" is one membership test.

    Derived from the engine for the same reason the EUOUAE table is: the tone
    table is the engine's, and a second copy on this side would be a second
    thing to keep true.

    :raises PsalmToneError: German message when no JS runtime is installed.
    """
    return _run("list-mediationes")


def generate_verses(
    psalmus: int | str,
    tonus: str,
    open_notes: bool = False,
    mediatio: str | None = None,
) -> tuple[str, list[str]]:
    """Generate all verses of a psalm (or ``"magnificat"``) in a tone.

    :param psalmus: Psalm number 1–150, or ``"magnificat"``.
    :param tonus: Tone label as the books print it, e.g. ``8G*`` or ``8 G``.
    :param open_notes: Draw every reciting note the verse puts no syllable on
        as a hollow note, as the Liber prints a tone. Only the two-verse
        Magnificat system needs this (ADR-0022); booklet verses are closed.
    :param mediatio: Which mediation to sing, where the tone offers a choice —
        see :func:`mediationes_per_tonus`. ``None`` takes the tone's default.
        Naming one on a tone that has none is an error, not a no-op.
    :return: ``(folder, verses)`` — the canonical tone folder name (e.g.
        ``8gstar``, or ``6f-ut-in-tono-i`` for a non-default mediation) and
        one complete gabc file content per verse.
    :raises PsalmToneError: German message (unknown tone/psalm/mediatio, no
        runtime).
    """
    extra = ["--open-notes"] if open_notes else []
    if mediatio:
        extra += ["--mediatio", mediatio]
    payload = _run("verses", "--psalmus", str(psalmus), "--tonus", tonus, *extra)
    logger.debug(
        "Psalmnoten erzeugt: %s im Ton %s%s (%d Verse, Ordner %s).",
        psalmus, tonus, f" (Mediatio {mediatio})" if mediatio else "",
        len(payload["verses"]), payload["folder"],
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
