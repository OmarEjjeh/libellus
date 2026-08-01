"""The form's data island: variable vocabularies as deterministic JSON.

The static HTML form cannot read the repo from the browser, so
``libellus export-form-data`` rewrites a marked JSON block inside the
form's HTML with everything that varies (ADR-0004): valid tone labels and
their EUOUAE cues, ordinarium chant names, psalms with German verses,
rite → antiphon count, rank vocabulary (ADR-0015), existing chant and
image paths. Output
ordering is stable so freshness is plain string comparison —
regenerating on an unchanged repo is a no-op.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from libellus.paths import source_of
from libellus.psalmtone import euouae_per_tonus, list_toni
from libellus.resolve import (
    BORDERS_DIR,
    CHANT_DIR,
    DROLLERY_DIR,
    IMAGE_SUFFIXES,
    ORDINARIUM_DIR,
    PSALTER_DIR,
)
from libellus.schema import ANTIPHONAE_PER_RITE, RANK_CODEX_1960, RANK_PRE_1955

logger = logging.getLogger(__name__)

#: Not offerable as a chant path: the transient per-build caches (``toni``,
#: ``inline``), and ``kurzfassung`` — the committed two-verse Magnificat systems
#: (ADR-0022), which the compact booklet picks by tone on its own. Nobody
#: authors a feast against one, and offering them would suggest otherwise.
_CHANT_CACHE_DIRS = {"toni", "inline", "kurzfassung"}

#: Image trees the form offers, each scanned where it actually lives: the
#: working directory's per-feast pictures, plus the ornament tiles the package
#: ships. Listed separately because ``images/`` spans both providers.
_IMAGE_DIRS = (Path("images"), BORDERS_DIR, DROLLERY_DIR)


def _logical(physical: Path, base: Path, root: Path) -> str:
    """A found file's logical asset path, whichever provider it came from."""
    return (base / physical.relative_to(source_of(base, root))).as_posix()


#: Ditto under images/: the decoded data: URI cache (ADR-0019). A bundled spec
#: carries its pictures inside itself, and the copies it leaves in the cache are
#: per-build artifacts — offering them would let a maintainer point a new feast
#: at a file the next build overwrites.
#: (images/borders/ is *not* excluded here, so the picker still lists 101 gilded
#: ornament tiles nobody would choose as a back cover — pre-existing, unrelated.)
_IMAGE_CACHE_DIRS = {"inline"}


def form_data(root: Path) -> dict[str, Any]:
    """Collect the data island's vocabularies from the repo state.

    The vocabularies come from two places, because the form offers both what
    the tool ships and what this working directory adds: the chant library and
    the ornament tiles are read out of the installed package, per-feast
    pictures and the Psalter out of ``root`` (ADR-0024).

    :param root: The working directory.
    :return: JSON-ready dict; all lists sorted (toni keep the engine's
        mode order, which is itself deterministic).
    """
    ordinarium = sorted(
        p.stem for p in source_of(ORDINARIUM_DIR, root).glob("*.gabc")
    )
    psalmi_cum_de = sorted(
        {
            int(psalm.stem)
            for psalm in (root / PSALTER_DIR).glob("*/*.yaml")
            if psalm.stem.isdigit()
        }
    )
    chant_paths = sorted(
        _logical(p, CHANT_DIR, root)
        for p in source_of(CHANT_DIR, root).rglob("*.gabc")
        if not _CHANT_CACHE_DIRS & set(p.parts)
    )
    image_paths = sorted(
        _logical(p, base, root)
        for base in _IMAGE_DIRS
        for p in source_of(base, root).rglob("*")
        if p.is_file()
        and p.suffix.lower() in IMAGE_SUFFIXES
        and not _IMAGE_CACHE_DIRS & set(p.parts)
    )
    island = {
        "toni": list_toni(),
        # mode + differentia fully determine an ending's EUOUAE, so the form
        # shows it read-only for the chosen tone instead of asking (issue #33)
        "euouae_per_tonus": euouae_per_tonus(),
        "ordinarium": ordinarium,
        "psalmi_cum_de": psalmi_cum_de,
        "antiphonae_per_rite": dict(sorted(ANTIPHONAE_PER_RITE.items())),
        "rank_pre_1955": list(RANK_PRE_1955),
        "rank_codex_1960": list(RANK_CODEX_1960),
        "chant_paths": chant_paths,
        "image_paths": image_paths,
    }
    logger.info(
        "Datenblock: %d Töne, %d Ordinariumsgesänge, %d Psalmen mit Deutsch, "
        "%d Noten- und %d Bilddateien.",
        len(island["toni"]), len(ordinarium), len(psalmi_cum_de),
        len(chant_paths), len(image_paths),
    )
    return island


def form_data_json(root: Path) -> str:
    """The data island as pretty-printed, deterministic JSON."""
    return json.dumps(form_data(root), ensure_ascii=False, indent=2)


#: The form file whose marked island block ``export-form-data`` rewrites.
FORM_FILE = Path("form/formular.html")

#: The marked block: everything between the opening tag's line and the
#: closing ``</script>`` line is machine-written JSON.
_ISLAND_RE = re.compile(
    r'(?<=<script type="application/json" id="datenblock">\n)'
    r".*?"
    r"(?=\n</script>)",
    re.DOTALL,
)


class FormDataError(Exception):
    """A German, user-facing message about the form's data island."""


def _island_match(html: str) -> re.Match[str]:
    match = _ISLAND_RE.search(html)
    if match is None:
        raise FormDataError(
            f"In „{FORM_FILE}“ fehlt der markierte Datenblock "
            "(<script type=\"application/json\" id=\"datenblock\">…</script>) — "
            "er darf nicht von Hand entfernt werden."
        )
    return match


def embedded_island(html: str) -> str:
    """The island JSON currently embedded in the form's HTML.

    :raises FormDataError: German message when the marked block is missing.
    """
    return _island_match(html).group(0)


def _form_html(root: Path) -> str:
    form_file = root / FORM_FILE
    if not form_file.is_file():
        raise FormDataError(f"Die Formulardatei „{FORM_FILE}“ wurde nicht gefunden.")
    return form_file.read_text(encoding="utf-8")


def island_is_current(root: Path) -> bool:
    """Whether the island embedded in the form matches the repo state.

    :raises FormDataError: German message when the form file or its marked
        block is missing.
    """
    return embedded_island(_form_html(root)) == form_data_json(root)


def rewrite_island(root: Path) -> bool:
    """Rewrite the marked island block in the form; the rest stays untouched.

    :return: True if the file changed, False if the island was already
        current (byte-identical no-op).
    :raises FormDataError: German message when the form file or its marked
        block is missing.
    """
    html = _form_html(root)
    match = _island_match(html)
    fresh = form_data_json(root)
    if match.group(0) == fresh:
        logger.debug("Datenblock in %s ist aktuell — nichts geschrieben.", FORM_FILE)
        return False
    (root / FORM_FILE).write_text(
        html[: match.start()] + fresh + html[match.end() :], encoding="utf-8"
    )
    logger.info("Datenblock in %s neu geschrieben.", FORM_FILE)
    return True
