"""Load a feast YAML, run all checks, and build the template context.

Cross-file checks (things Pydantic cannot express) also produce German
messages: referenced gabc files exist, (psalmus, tonus) can be generated
and has German verse translations, the ordinarium has the referenced
chants and their German texts.

Every file the rendered TeX will read at compile time (gabc scores,
images, filler pages) is recorded as an asset while it is resolved, so the
staging step can copy exactly those files into the build folder.
"""

from __future__ import annotations

import logging
import random
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from libellus.errors import FeastFileError, german_messages
from libellus.gabc import (
    CANONICAL_CLEF,
    build_euouae_gabc,
    chant_name,
    find_clef,
    find_euouae,
    first_stanza_gabc,
    hymn_incipit,
    hymn_stanzas,
    incipit,
    is_inline_gabc,
    pointed_halves,
)
from libellus.imagedata import (
    HUGE_ABOVE,
    TOO_NARROW_BELOW,
    decode_inline_image,
    image_width,
    is_inline_image,
)
from libellus.latin import latin_date, latin_day_month, roman
from libellus.magnificat import SYSTEM_DIR
from libellus.paths import source_of
from libellus.psalmtone import (
    PsalmToneError,
    euouae_per_tonus,
    generate_verses,
    write_verse_cache,
)
from libellus.schema import FeastSpec
from libellus.tonus import (
    Provenance,
    disagrees,
    labels_with,
    resolve_tonus,
    tonus_message,
)

logger = logging.getLogger(__name__)

CHANT_DIR = Path("chant")
PSALMI_DIR = CHANT_DIR / "psalmi"
MAGNIFICAT_DIR = CHANT_DIR / "magnificat"
ORDINARIUM_DIR = CHANT_DIR / "ordinarium"
INLINE_DIR = CHANT_DIR / "inline"  # gitignored cache for inline GABC blocks
INLINE_IMAGE_DIR = Path("images/inline")  # ditto for embedded data: URIs
DROLLERY_DIR = Path("images/drollery")
BORDERS_DIR = Path("images/borders")
#: Fixed corner + edge-segment tiles for the "gilded" back-cover border
#: (ADR-0014) — 4 corners, each cropped from its own real
#: position (no mirroring: a mirrored tile visibly mismatches the photo's
#: directional gloss highlight), plus each edge sliced into several
#: consecutive real segments (13 top/bottom, 11 left/right) so the natural
#: photographed gradient carries through instead of one tile repeating and
#: hard-cutting against each corner.
#: Each segment also has a "-feather" variant (alpha-faded tiling-direction
#: margins) used for whichever segment ends up an interior tile — which
#: physical segment plays "first"/"last"/"interior" depends on how many
#: display tiles a given feast's image needs, so every segment needs both
#: forms available.
GILDED_EDGE_COUNTS = {"top": 13, "bottom": 13, "left": 11, "right": 11}
GILDED_BORDER_ASSETS = tuple(
    BORDERS_DIR / f"gilded-corner-{name}.png"
    for name in ("nw", "ne", "sw", "se")
) + tuple(
    BORDERS_DIR / f"gilded-edge-{side}-{i}{suffix}.png"
    for side, count in GILDED_EDGE_COUNTS.items()
    for i in range(count)
    for suffix in ("", "-feather")
)

#: The only image formats LuaLaTeX's \includegraphics can set.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".pdf")

#: Where Psalters live: one directory per translation, ``psalter/<versio>/``,
#: holding ``<psalm number>.yaml`` and ``magnificat.yaml`` (ADR-0024). Outside
#: the package on purpose — no German translation is redistributable yet, so
#: none ships, and a fresh install has no Psalter at all.
PSALTER_DIR = Path("psalter")

#: German psalter translations tried in this order when the feast spec
#: does not choose one via ``psalter_de``. Allioli-Arndt 1914 comes first
#: because it is the only one a fresh install may legally have (ADR-0041):
#: the Einheitsübersetzung translations behind it are not redistributable,
#: so a default naming one was a default nobody outside Bremen could use.
#: eu1980 = the Stundenbuch psalter (ADR-0007); eu2016 = the hand-made
#: re-cuts the Benedict booklet was printed with. Both stay reachable, and
#: both feasts in ``feasts/`` name one explicitly rather than inherit this.
PSALTER_DE_PREFERENCE = ("allioli-arndt", "eu1980", "eu2016")

#: Ordinarium chants every skeleton needs (chant name → German required?).
ORDINARIUM_ALWAYS: dict[str, bool] = {
    "incipit": True,
    "versicle-domine-exaudi": True,
    "benedicamus-domino": True,
    "deo-gratias": True,
    "fidelium-animae": True,
    "amen": False,
}
#: Additional chants for rites that sing Preces + Pater noster.
ORDINARIUM_CUM_PRECIBUS: dict[str, bool] = {
    "te-rogamus": True,
    "kyrie-eleison": False,
    "paternoster": True,
}


class ResolvedFeast(BaseModel):
    """Everything a staged build folder needs.

    :param context: The full Jinja2 template context.
    :param assets: Root-relative files the rendered TeX reads at compile
        time (gabc scores, images, filler pages).
    """

    context: dict[str, Any]
    assets: list[Path]


def load_spec(feast_yaml: Path) -> FeastSpec:
    """Parse + validate the feast YAML; raise FeastFileError with German messages."""
    logger.debug("Lese Fest-Datei „%s“.", feast_yaml)
    try:
        raw = yaml.safe_load(feast_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FeastFileError(
            [f"Die Datei „{feast_yaml}“ ist kein gültiges YAML: {exc}"]
        ) from exc
    if not isinstance(raw, dict):
        raise FeastFileError([f"Die Datei „{feast_yaml}“ enthält keine Felder."])
    try:
        spec = FeastSpec.model_validate(raw)
    except ValidationError as exc:
        raise FeastFileError(german_messages(exc)) from exc
    logger.info(
        "Fest geladen: %s — %s, Vesperae %s, Ritus „%s“.",
        spec.title, spec.date, spec.vesperae, spec.rite,
    )
    return spec


def _stem(gabc_path: Path) -> str:
    """Path as \\gregorioscore wants it: relative, without the .gabc suffix."""
    return gabc_path.with_suffix("").as_posix()


def _check_gabc(
    path: Path, what: str, problems: list[str], root: Path, assets: set[Path]
) -> None:
    if not source_of(path, root).is_file():
        problems.append(f"{what}: Die Notendatei „{path}“ wurde nicht gefunden.")
        return
    logger.debug("%s: Notendatei „%s“ gefunden.", what, path)
    assets.add(path)


def _resolve_gabc(
    source: str, slug: str, what: str, problems: list[str], root: Path, assets: set[Path]
) -> Path:
    """Root-relative .gabc path for a chant element's ``gabc:`` value.

    Inline notation (ADR-0005) is first written into the gitignored
    ``chant/inline/`` cache, so incipit derivation and staging read it
    exactly like a repo file.
    """
    if is_inline_gabc(source):
        path = INLINE_DIR / f"{slug}.gabc"
        target = source_of(path, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            source if source.endswith("\n") else source + "\n", encoding="utf-8"
        )
        logger.debug("%s: eingebettete GABC-Notation nach „%s“ geschrieben.", what, path)
        assets.add(path)
        return path
    path = Path(source)
    _check_gabc(path, what, problems, root, assets)
    return path


def _resolve_image(
    source: str,
    slug: str,
    subject: str,
    problems: list[str],
    root: Path,
    assets: set[Path],
) -> Path | None:
    """Root-relative path for an ``image:`` value, or None if it is unusable.

    An embedded data URI (ADR-0019) is decoded into the gitignored
    ``images/inline/`` cache first, so staging copies it like any repo file —
    the same trick ``_resolve_gabc`` plays with pasted notation.

    :param slug: Filename stem for the cache copy; the suffix comes from the
        URI's MIME type, since LuaLaTeX picks its graphics driver by extension.
    :param subject: How to name this slot in an error message, e.g.
        ``"Das Rückseitenbild"``.
    :return: ``None`` when a problem was recorded, so the caller can carry on
        collecting the rest rather than aborting on the first bad field.
    """
    if is_inline_image(source):
        # cannot fail: schema._validate_image_source already decoded this value
        data, suffix = decode_inline_image(source)
        path = INLINE_IMAGE_DIR / f"{slug}{suffix}"
        target = source_of(path, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.debug(
            "%s: eingebettetes Bild nach „%s“ geschrieben (%d Bytes).",
            subject, path, len(data),
        )
        assets.add(path)
        _warn_about_print_size(data, subject, path)
        return path

    path = Path(source)
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        hint = (
            " — bitte zuerst nach PNG umwandeln (die Bildwahl im Formular "
            "macht das automatisch)"
            if path.suffix.lower() == ".webp"
            else ""
        )
        # wrong format is the one clear error — existence is not also checked
        problems.append(
            f"{subject} „{path}“ hat ein Format, das LaTeX nicht setzen kann "
            f"(erlaubt: {', '.join(IMAGE_SUFFIXES)}){hint}."
        )
        return None
    if not source_of(path, root).is_file():
        problems.append(f"{subject} „{path}“ wurde nicht gefunden.")
        return None
    assets.add(path)
    _warn_about_print_size(source_of(path, root).read_bytes(), subject, path)
    return path


def _warn_about_print_size(data: bytes, subject: str, path: Path) -> None:
    """Warn — never fail — when a picture's pixel width is wrong for print.

    The form applies these thresholds when a picture is chosen through it
    (`verarbeiteBild`), but a file added by hand bypasses that entirely, and
    until now nothing said so. Hence a build-time echo of the same two checks:
    it stays a warning because both cases still print, just not well.
    """
    width = image_width(data)
    if width is None:  # PDF, or an unparsable marker chain — cannot tell
        return
    if width > HUGE_ABOVE:
        logger.warning(
            "%s „%s“ ist %d px breit — für den Druck genügen %d px. Über die "
            "Bildwahl im Formular wird es automatisch verkleinert.",
            subject, path, width, HUGE_ABOVE,
        )
    elif width < TOO_NARROW_BELOW:
        logger.warning(
            "%s „%s“ ist nur %d px breit — für den Druck sind mindestens %d px "
            "ratsam, sonst wird es sichtbar grob. Es wird trotzdem gesetzt.",
            subject, path, width, TOO_NARROW_BELOW,
        )


def _verify_tonus(
    gabc: str,
    euouae: str,
    clef: str,
    source: str,
    tonus: str,
    what: str,
    problems: list[str],
) -> None:
    """Check a EUOUAE against ``tonus:`` — they must name the same ending.

    Every ending's EUOUAE is distinct, so an exact match settles the label
    (issue #33). Real transcriptions embellish the final neume, so a
    non-exact EUOUAE is accepted when the leading neumes still admit the
    stated tone. Anything else is a German error: a EUOUAE and a tone that
    disagree mean the printed cue and the sung psalm ending would diverge.

    The matching itself is :func:`~libellus.tonus.resolve_tonus`, shared with
    the suggestion the editor offers (issue #46) — this is the assertion end
    of the same operation, and two implementations would drift. Only the
    *measured* candidates decide anything here: the connection rule the
    resolver also applies is a convention, and three antiphons of the two
    shipped booklets legitimately depart from it, so it cannot fail a build.

    :param gabc: The antiphon's whole score — what the resolver reads.
    :param euouae: The EUOUAE being checked: the antiphon's own, or the feast
        spec's ``euouae:`` assertion, which is why it is passed rather than
        re-read from ``gabc``.
    :param clef: The clef ``euouae`` is written under — without it the pitch
        letters mean nothing, since they are staff positions (issue #45).
    """
    try:
        table = euouae_per_tonus()
    except PsalmToneError as exc:
        problems.append(f"{what}: {exc}")
        return
    if tonus not in table:
        return  # an unknown tone is reported once, by verse generation
    candidates = resolve_tonus(gabc, table, euouae=euouae, clef=clef)
    if disagrees(candidates):
        logger.debug("%s: %s", what, tonus_message(candidates))
    exact = labels_with(candidates, Provenance.EUOUAE)
    leading = labels_with(candidates, Provenance.EUOUAE_LEADING)
    # `exact` holds at most one label, since no two endings' EUOUAEs normalize
    # alike (`test_every_endings_euouae_is_unique`) — hence `exact[0]` below.
    if tonus in exact or (not exact and tonus in leading):
        return
    if exact:
        problems.append(
            f"{what}: {source} gehört zum Ton „{exact[0]}“, nicht zum "
            f"angegebenen „{tonus}“ — bitte den Psalmton berichtigen."
        )
    elif leading:
        problems.append(
            f"{what}: {source} passt zu keinem Ton genau; nach den ersten "
            f"Neumen käme {', '.join(f'„{label}“' for label in leading)} in "
            f"Frage, angegeben ist aber „{tonus}“."
        )
    else:
        problems.append(
            f"{what}: {source} passt zu keinem bekannten Psalmton "
            f"(angegeben: „{tonus}“) — bitte die Noten prüfen."
        )


def _antiphon_clef(content: str, gabc_path: Path) -> str:
    """The clef the antiphon is notated in — the frame its EUOUAE is spelled
    in, and the frame a feast spec's ``euouae:`` assertion is spelled in too,
    since that records what the antiphon's own printed source shows.

    A score naming no clef cannot be typeset by gregorio either, so stopping
    the build here would only add a second, worse-worded complaint about it:
    the canonical clef is assumed instead, and said out loud (issue #45).
    """
    clef = find_clef(content)
    if clef is None:
        if content:  # empty means the file is missing, already reported as such
            logger.warning(
                "„%s“ hat keinen Notenschlüssel — zum Prüfen der Schlussformel "
                "wird „%s“ angenommen.", gabc_path, CANONICAL_CLEF,
            )
        return CANONICAL_CLEF
    return clef


def _resolve_euouae(
    gabc_path: Path,
    euouae_field: str | None,
    tonus: str,
    slug: str,
    what: str,
    problems: list[str],
    root: Path,
    assets: set[Path],
) -> Path:
    """The antiphon's gabc path, with its EUOUAE appended if it had none.

    The schola whistles the EUOUAE after the antiphon to pitch the psalm,
    so every antiphon should print one. When the antiphon's own GABC has no
    EUOUAE, the ending's canonical notes (derived from ``tonus:`` — mode
    plus differentia fully determine them) are appended onto a
    *materialized copy*: the antiphon's own source is never mutated
    (ADR-0017), and it is dropped from ``assets`` in favour of the copy so
    the superseded original isn't staged as a dead extra file.

    A EUOUAE that is already present, or supplied as the ``euouae:``
    assertion, is checked against ``tonus:`` (issue #33).
    """
    full_path = source_of(gabc_path, root)
    content = full_path.read_text(encoding="utf-8") if full_path.is_file() else ""
    own = find_euouae(content)
    if own is not None:
        _verify_tonus(
            content, own, _antiphon_clef(content, gabc_path),
            "Die Schlussformel der Antiphon", tonus, what, problems,
        )
        return gabc_path
    if euouae_field is not None:
        _verify_tonus(
            content, euouae_field, _antiphon_clef(content, gabc_path),
            "Das Feld „euouae“", tonus, what, problems,
        )
    try:
        table = euouae_per_tonus()
    except PsalmToneError as exc:
        problems.append(f"{what}: {exc}")
        return gabc_path
    if tonus not in table:
        return gabc_path  # unknown tone: already reported by verse generation
    euouae_gabc = build_euouae_gabc(table[tonus])
    if euouae_gabc is None:
        return gabc_path
    appended = content.rstrip("\n") + f" <eu>{euouae_gabc}</eu>(::)\n"
    target = INLINE_DIR / f"{slug}.gabc"
    source_of(target, root).parent.mkdir(parents=True, exist_ok=True)
    source_of(target, root).write_text(appended, encoding="utf-8")
    logger.debug(
        "%s: Schlussformel des Tons %s an materialisierte Kopie „%s“ angehängt.",
        slug, tonus, target,
    )
    assets.discard(gabc_path)
    assets.add(target)
    return target


def _psalter_name(library_dir: Path) -> str:
    """What a Psalter calls this verse library: a psalm number, or the canticle.

    ``chant/psalmi/109`` → ``"109"``, ``chant/magnificat`` → ``"magnificat"``.
    """
    return "magnificat" if library_dir == MAGNIFICAT_DIR else library_dir.name


def _select_de_file(
    library_dir: Path,
    psalter_de: str | list[str] | None,
    what: str,
    problems: list[str],
    root: Path,
) -> Path | None:
    """Pick this psalm's German out of a **Psalter** — ``psalter/<versio>/``.


    A Psalter is one translator's complete German, one directory per
    translation, kept beside the working directory rather than inside the
    package: no translation ships with libellus, because the one Bremen prints
    is not redistributable and no public-domain German psalter exists yet
    (ADR-0024). A stranger supplies their own directory, or sets
    ``latin_only``.

    ``psalter_de`` may name **one** translation or an ordered list of them,
    and a list is the whole point (ADR-0041): a translation can be incomplete.
    Bremen's eu1980 has all 150 psalms and no Magnificat, so the St. Lambert
    booklet takes its psalms from eu1980 and its Magnificat from eu2016 — which
    it now says outright, ``psalter_de: [eu1980, eu2016]``, instead of getting
    it by naming nothing and inheriting whatever ``PSALTER_DE_PREFERENCE``
    happened to hold. A feast that names translations gets those and no others:
    falling through to the global default instead would mean that changing the
    default silently retranslates part of a booklet that had already chosen,
    which is exactly the accident ADR-0041 was avoiding.

    Resolution is per item, so a feast may legitimately mix translations. That
    is why each psalm logs the translation it resolved to.
    """
    name = _psalter_name(library_dir)
    psalter_root = root / PSALTER_DIR
    available = sorted(
        folder.name
        for folder in psalter_root.glob("*")
        if folder.is_dir() and (folder / f"{name}.yaml").is_file()
    )
    if psalter_de is not None:
        chosen = [psalter_de] if isinstance(psalter_de, str) else list(psalter_de)
        for versio in chosen:
            candidate = psalter_root / versio / f"{name}.yaml"
            if candidate.is_file():
                return candidate
        named = ", ".join(f"„{versio}“" for versio in chosen)
        problems.append(
            f"{what}: Keine der im Fest genannten Übersetzungen ({named}) hat "
            f"„{name}“ — vorhanden: {', '.join(available) if available else 'keine'}."
        )
        return None
    for versio in PSALTER_DE_PREFERENCE:
        candidate = psalter_root / versio / f"{name}.yaml"
        if candidate.is_file():
            return candidate
    if len(available) == 1:
        return psalter_root / available[0] / f"{name}.yaml"
    if available:
        problems.append(
            f"{what}: Mehrere Übersetzungen vorhanden ({', '.join(available)}) — "
            f"bitte im Fest mit „psalter_de:“ eine auswählen."
        )
        return None
    problems.append(
        f"{what}: Für „{name}“ fehlt die deutsche Übersetzung. Erwartet wird "
        f"„{PSALTER_DIR}/<Übersetzung>/{name}.yaml“ — es gibt hier noch keinen "
        f"Psalter. Ohne deutschen Psalter lässt sich das Heft nur mit "
        f"„latin_only: true“ setzen."
    )
    return None


#: ADR-0010's table, the single source of truth for naming a psalm.
PSALM_INCIPITS_FILE = PSALMI_DIR / "incipits.yaml"


def psalm_incipits(root: Path) -> dict[int, str]:
    """Vulgate psalm number → canonical accented Latin incipit (ADR-0010).

    Read from a table rather than derived from the psalm's verse gabc: the
    verses live in the per-tone cache, so a derived label would depend on
    whichever ``tonus:`` the author happened to pick, and the incipit
    cutter's punctuation rule truncated Ps. cxii to "Laudáte" instead of
    "Laudáte, púeri" (ADR-0020).

    :param root: Repository root.
    :raises FeastFileError: German message when the table is missing.
    """
    table = source_of(PSALM_INCIPITS_FILE, root)
    if not table.is_file():
        raise FeastFileError(
            [f"Die Psalmen-Incipit-Tabelle „{PSALM_INCIPITS_FILE}“ fehlt im Repository."]
        )
    raw = yaml.safe_load(table.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("incipits"), dict):
        raise FeastFileError(
            [f"Die Psalmen-Incipit-Tabelle „{PSALM_INCIPITS_FILE}“ hat kein Feld „incipits“."]
        )
    incipits = {int(number): text for number, text in raw["incipits"].items()}
    # The table is meant to be hand-corrected, so a gap in it is a plausible
    # editing slip, not an impossible state.
    missing = [number for number in range(1, 151) if number not in incipits]
    if missing:
        shown = ", ".join(str(number) for number in missing[:10])
        ellipsis = " …" if len(missing) > 10 else ""
        message = (
            f"In der Psalmen-Incipit-Tabelle „{PSALM_INCIPITS_FILE}“ fehlen "
            f"{len(missing)} Psalmen: {shown}{ellipsis}."
        )
        raise FeastFileError([message])
    return incipits


def _load_verse_library(
    library_dir: Path,
    tonus: str,
    what: str,
    problems: list[str],
    root: Path,
    assets: set[Path],
    psalter_de: str | list[str] | None = None,
    latin_only: bool = False,
    mediatio: str | None = None,
) -> list[dict[str, Any]]:
    """Generate the per-verse gabc on demand and pair it with the German.

    The verses come from the vendored jgabc engine (any psalm, any LU tone —
    see ``psalm-library/``) and are written into the ``build/.cache/`` copy of
    ``chant/**/toni/``. The German comes from a **Psalter**: one directory per
    translation, supplied alongside the working directory rather than bundled,
    and selected via the feast spec's ``psalter_de`` (ADR-0024).

    A ``latin_only`` feast needs no Psalter at all (ADR-0025) — every verse
    still gets its notation, and its German is simply absent. This is what
    makes a fresh ``pip install`` able to set a booklet, since no Psalter
    ships with libellus.

    :param mediatio: Which of the tone's mediations to sing, where it offers a
        choice (ADR-0043). Only the Magnificat passes one.
    """
    psalmus = _psalter_name(library_dir)
    try:
        folder, contents = generate_verses(psalmus, tonus, mediatio=mediatio)
    except PsalmToneError as exc:
        problems.append(f"{what}: {exc}")
        return []
    # Logical paths throughout: these are what the TeX references and what
    # staging reproduces. Reading their bytes goes through source_of.
    verse_files = write_verse_cache(library_dir, folder, contents, root)
    translations: dict[int, str] = {}
    de_name: Path | str = "—"
    if not latin_only:
        de_file = _select_de_file(library_dir, psalter_de, what, problems, root)
        if de_file is None:
            return []
        de_name = de_file.relative_to(root) if de_file.is_relative_to(root) else de_file
        de_data = yaml.safe_load(de_file.read_text(encoding="utf-8"))
        translations = {int(k): v for k, v in de_data.get("verses", {}).items()}
    logger.debug(
        "%s: %d Verse erzeugt (Ton %s → %s), %d Übersetzungen in „%s“.",
        what, len(verse_files), tonus, folder, len(translations), de_name,
    )
    verses: list[dict[str, Any]] = []
    for verse_file in verse_files:
        number = int(verse_file.stem.lstrip("v"))
        if not latin_only and number not in translations:
            problems.append(
                f"{what}: In „{de_name}“ fehlt die Übersetzung "
                f"für Vers {number}."
            )
            continue
        assets.add(verse_file)
        verses.append(
            {
                "gabc": _stem(verse_file),
                "de": translations.get(number, ""),
                "number": number,
                # what a Kurzfassung prints instead of the score (ADR-0022);
                # derived for every build, since the tone engine writes the
                # pointing into the verse either way
                "halves": pointed_halves(source_of(verse_file, root)),
            }
        )
    logger.info("%s: %d Verse aufgelöst (Ton %s).", what, len(verses), tonus)
    return verses


def _compact_hymnus(
    gabc_path: Path,
    german: list[str] | None,
    problems: list[str],
    root: Path,
    assets: set[Path],
) -> tuple[Path, list[list[str]]]:
    """One notated stanza plus the rest as text, for a Kurzfassung (ADR-0022).

    The score is truncated onto a *materialized copy* — the hymn's own source
    is never mutated, the same way an appended EUOUAE is handled (ADR-0017) —
    and the original is dropped from the assets in favour of it.

    A Latin stanza count that disagrees with ``hymnus.de`` is a hard error,
    never a silent fall back to the fully notated hymn: that would hand back a
    Kurzfassung which isn't one. It also means the German stanza numbering is
    already wrong in the ordinary booklet.

    :return: The score to set, and the Latin of every stanza after the first.
    """
    stanzas = hymn_stanzas(source_of(gabc_path, root))
    truncated = first_stanza_gabc(source_of(gabc_path, root))
    if not stanzas or truncated is None:
        problems.append(
            f"Hymnus: Die Kurzfassung braucht Strophen, die in den Noten durch "
            f"„(::)“ getrennt sind — in „{gabc_path.as_posix()}“ steht kein "
            f"einziger solcher Strophenschluss."
        )
        return gabc_path, []
    # A Latin-only Kurzfassung has no stanza translations to count against.
    if german is not None and len(stanzas) != len(german):
        problems.append(
            f"Hymnus: Die Noten haben {len(stanzas)} Strophe(n) (getrennt durch "
            f"„(::)“), das Feld „de“ hat {len(german)} — für die Kurzfassung "
            f"braucht jede Strophe ihren deutschen Text. Stimmt die Zahl nicht, "
            f"ist auch die Strophenzählung im gewöhnlichen Heft falsch."
        )
        return gabc_path, []
    target = INLINE_DIR / "hymnus-kurzfassung.gabc"
    source_of(target, root).parent.mkdir(parents=True, exist_ok=True)
    source_of(target, root).write_text(truncated, encoding="utf-8")
    logger.info(
        "Kurzfassung: Hymnus auf die erste von %d Strophen gekürzt („%s“).",
        len(stanzas), target,
    )
    assets.discard(gabc_path)
    assets.add(target)
    return target, stanzas[1:]


def _load_ordinarium(
    needed: dict[str, bool], problems: list[str], root: Path, assets: set[Path]
) -> dict[str, dict[str, Any]]:
    de_file = source_of(ORDINARIUM_DIR / "de.yaml", root)
    de_data: dict[str, str] = {}
    if de_file.is_file():
        de_data = yaml.safe_load(de_file.read_text(encoding="utf-8")) or {}
    else:
        problems.append(f"Die Datei „{ORDINARIUM_DIR / 'de.yaml'}“ fehlt.")
    chants: dict[str, dict[str, Any]] = {}
    for name, needs_german in needed.items():
        gabc_path = ORDINARIUM_DIR / f"{name}.gabc"
        if not source_of(gabc_path, root).is_file():
            problems.append(f"Ordinarium: Die Notendatei „{gabc_path}“ fehlt.")
            continue
        if needs_german and name not in de_data:
            problems.append(
                f"Ordinarium: In „{ORDINARIUM_DIR / 'de.yaml'}“ fehlt die "
                f"Übersetzung für „{name}“."
            )
        logger.debug("Ordinarium: „%s“ aufgelöst.", name)
        assets.add(gabc_path)
        chants[name] = {"gabc": _stem(gabc_path), "de": de_data.get(name, "")}
    logger.info("Ordinarium: %d von %d Gesängen aufgelöst.", len(chants), len(needed))
    return chants


def _resolve_filler(
    spec: FeastSpec, problems: list[str], root: Path, assets: set[Path]
) -> list[dict[str, Any]]:
    """Filler pages, normalized to dicts the partial can render without isinstance.

    Two shapes, discriminated by ``kind``: a structured ``FillerPage``
    (``kind: "page"``, whose ``image`` IS recorded as an asset) and the
    ADR-0001/0002 escape hatch of a hand-authored .tex file (``kind: "tex"``,
    copied verbatim — files it references are deliberately not discovered,
    so such a page has to be self-contained).
    """
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(spec.filler, start=1):
        if isinstance(page, Path):
            if not source_of(page, root).is_file():
                problems.append(f"Die Zusatzseite „{page}“ wurde nicht gefunden.")
                continue
            logger.debug("Zusatzseite „%s“ gefunden (eigenes .tex).", page)
            assets.add(page)
            pages.append({"kind": "tex", "path": page.as_posix()})
            continue

        image = (
            None
            if page.image is None
            else _resolve_image(
                page.image,
                f"zusatzseite-{index:02d}",
                f"Das Bild der {index}. Zusatzseite",
                problems,
                root,
                assets,
            )
        )
        pages.append(
            {
                "kind": "page",
                "title": page.title,
                "subtitle": page.subtitle,
                "blocks": [{"heading": b.heading, "text": b.text} for b in page.blocks],
                "citation": page.citation,
                "image": image.as_posix() if image is not None else None,
                "image_width": page.image_width,
                "caption": page.caption,
            }
        )
    if pages:
        logger.info("Zusatzseiten: %d aufgelöst.", len(pages))
    return pages


def _resolve_drollery(
    spec: FeastSpec, problems: list[str], root: Path, assets: set[Path]
) -> str | None:
    if spec.drollery == "none":
        logger.debug("Drolerie: per Fest-Datei abgeschaltet („none“).")
        return None
    drollery_dir = source_of(DROLLERY_DIR, root)
    if spec.drollery == "auto":
        if not drollery_dir.is_dir():
            logger.debug("Drolerie: kein Ordner „%s“ — übersprungen.", DROLLERY_DIR)
            return None
        candidates = sorted(
            p for p in drollery_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        if not candidates:
            logger.debug("Drolerie: Ordner „%s“ ist leer — übersprungen.", DROLLERY_DIR)
            return None
        # Seeded by the celebration date so rebuilds are reproducible.
        chosen = random.Random(str(spec.date)).choice(candidates)
        logger.info(
            "Drolerie: „%s“ gewählt (aus %d Kandidaten, Saat „%s“).",
            chosen.name, len(candidates), spec.date,
        )
        assets.add(chosen.relative_to(root))
        return chosen.relative_to(root).as_posix()
    if not (drollery_dir / spec.drollery).is_file():
        problems.append(
            f"Das Feld „drollery“ nennt „{spec.drollery}“, aber die Datei liegt "
            f"nicht in „{DROLLERY_DIR}/“."
        )
        return None
    logger.debug("Drolerie: „%s“ (fest vorgegeben).", spec.drollery)
    assets.add(DROLLERY_DIR / spec.drollery)
    return (DROLLERY_DIR / spec.drollery).as_posix()


def build_context(
    spec: FeastSpec, root: Path, draft_stamp: str | None = None, compact: bool = False
) -> ResolvedFeast:
    """Cross-file checks + the full Jinja2 context + asset list. Raises FeastFileError.

    :param draft_stamp: The dated draft line (libellus.latin.draft_stamp), or
        None for a final booklet. Its presence *is* the draft flag in the
        template — the caller has already OR-ed the spec field with ``--draft``.
    :param compact: Build a Kurzfassung (ADR-0022). The caller has already
        settled the spec field against ``--compact``/``--no-compact``.
    """
    problems: list[str] = []
    assets: set[Path] = set()

    # Never leave inline chants from a previously built feast behind.
    if source_of(INLINE_DIR, root).exists():
        shutil.rmtree(source_of(INLINE_DIR, root))

    incipits = psalm_incipits(root)
    psalmi: list[dict[str, Any]] = []
    for index, ant in enumerate(spec.antiphonae, start=1):
        what = f"Antiphon {index}"
        ant_gabc = _resolve_gabc(
            ant.gabc, f"antiphona-{index}", what, problems, root, assets
        )
        ant_gabc = _resolve_euouae(
            ant_gabc, ant.euouae, ant.tonus, f"antiphona-{index}",
            what, problems, root, assets,
        )
        verses = _load_verse_library(
            PSALMI_DIR / str(ant.psalmus), ant.tonus, f"Psalm {ant.psalmus}",
            problems, root, assets, spec.psalter_de, spec.latin_only,
        )
        ant_file = source_of(ant_gabc, root)
        ant_incipit = incipit(ant_file, 4) if ant_file.is_file() else ""
        psalmi.append(
            {
                "index_roman": roman(index),
                "number_roman": roman(ant.psalmus),
                "antiphona": {
                    "gabc": _stem(ant_gabc),
                    "de": ant.de,
                    "repetitio": ant.repetitio or ant_incipit,
                    "incipit": ant.incipit or (
                        incipit(source_of(ant_gabc, root), 3)
                        if source_of(ant_gabc, root).is_file()
                        else ""
                    ),
                    "note": ant.note,
                },
                "verses": verses,
                "incipit": incipits[ant.psalmus],
            }
        )

    responsorium_gabc = None
    if spec.responsorium is not None:
        responsorium_gabc = _resolve_gabc(
            spec.responsorium.gabc, "responsorium", "Responsorium", problems, root, assets
        )
    hymnus_gabc = _resolve_gabc(
        spec.hymnus.gabc, "hymnus", "Hymnus", problems, root, assets
    )
    # The truncated copy still opens with the first stanza, so the Ordo row's
    # incipit below reads the same first metrical line either way.
    hymnus_latin: list[list[str]] = []
    if compact and source_of(hymnus_gabc, root).is_file():
        hymnus_gabc, hymnus_latin = _compact_hymnus(
            hymnus_gabc, spec.hymnus.de, problems, root, assets
        )
    versiculus_gabc = _resolve_gabc(
        spec.versiculus.gabc, "versiculus", "Versiculus", problems, root, assets
    )
    magnificat_ant_gabc = _resolve_gabc(
        spec.magnificat.antiphona.gabc, "antiphona-ad-magnificat",
        "Antiphona ad Magnificat", problems, root, assets,
    )
    magnificat_ant_gabc = _resolve_euouae(
        magnificat_ant_gabc, spec.magnificat.antiphona.euouae, spec.magnificat.tonus,
        "antiphona-ad-magnificat", "Antiphona ad Magnificat", problems, root, assets,
    )

    magnificat_verses = _load_verse_library(
        MAGNIFICAT_DIR, spec.magnificat.tonus, "Magnificat", problems, root, assets,
        psalter_de=spec.psalter_de, latin_only=spec.latin_only,
        mediatio=spec.magnificat.mediatio,
    )

    # A Kurzfassung puts the Magnificat's first two verses under one system
    # (ADR-0022): „Magníficat" alone cannot carry the mediant cadence, so a
    # notated verse 1 would show a melody no other verse follows. Where the
    # tone sings its first verse to its own solemn formula there is no such
    # system — the absence of the file says so — and both verses are notated.
    magnificat_system: str | None = None
    if compact and magnificat_verses:
        # the verse paths carry the tone's cache folder, e.g. …/toni/6f/v01
        folder = Path(magnificat_verses[0]["gabc"]).parent.name
        system = SYSTEM_DIR / f"{folder}.gabc"
        if source_of(system, root).is_file():
            assets.add(system)
            magnificat_system = _stem(system)
        else:
            logger.info(
                "Kurzfassung: Ton %s hat kein Zwei-Vers-System (eigene Melodie im "
                "1. Vers) — Vers 1 und 2 werden einzeln notiert.", folder,
            )

    needed_ordinarium = dict(ORDINARIUM_ALWAYS)
    if spec.cum_precibus:
        needed_ordinarium |= ORDINARIUM_CUM_PRECIBUS
    needed_ordinarium[spec.antiphona_bmv] = True
    ordinarium = _load_ordinarium(needed_ordinarium, problems, root, assets)

    filler = _resolve_filler(spec, problems, root, assets)
    back_cover_image = _resolve_image(
        spec.back_cover.image, "rueckseite", "Das Rückseitenbild", problems, root, assets
    )

    drollery = _resolve_drollery(spec, problems, root, assets)

    if spec.back_cover.border == "gilded":
        assets.update(GILDED_BORDER_ASSETS)

    if problems:
        logger.error("Auflösung fehlgeschlagen: %d Problem(e) in der Fest-Datei.", len(problems))
        raise FeastFileError(problems)

    bmv = dict(ordinarium[spec.antiphona_bmv])
    bmv["name"] = chant_name(
        source_of(ORDINARIUM_DIR / f"{spec.antiphona_bmv}.gabc", root)
    )
    mag_gabc = source_of(magnificat_ant_gabc, root)

    logger.info("Auflösung fertig: %d Dateien werden als Anlagen gebraucht.", len(assets))
    context = {
        "feast": spec,
        "draft_stamp": draft_stamp,
        "compact": compact,
        # The preamble turns this into a LaTeX switch; \pstrans, \transblock and
        # \textstanza then suppress every translation themselves (ADR-0025).
        "latin_only": spec.latin_only,
        "date_latin": latin_date(spec.date),
        "translata_note": (
            f"translata ex die {latin_day_month(spec.liturgical_date)}"
            if spec.liturgical_date
            else None
        ),
        "vesperae_label": (
            None if spec.vesperae is None else ("Primæ" if spec.vesperae == "I" else "Secundæ")
        ),
        "psalmi": psalmi,
        "responsorium": (
            {"gabc": _stem(responsorium_gabc), "de": spec.responsorium.de,
             "incipit": spec.responsorium.incipit or incipit(source_of(responsorium_gabc, root), 4),
             "note": spec.responsorium.note}
            if spec.responsorium is not None and responsorium_gabc is not None
            else None
        ),
        # stanzas: [] rather than None for a latin_only feast, so the partial
        # iterates over nothing instead of having to test for absence
        "hymnus": {"gabc": _stem(hymnus_gabc), "stanzas": spec.hymnus.de or [],
                   "incipit": spec.hymnus.incipit or hymn_incipit(source_of(hymnus_gabc, root)),
                   "note": spec.hymnus.note,
                   # Kurzfassung only: the Latin of stanzas 2..n as metrical
                   # lines, paired with `stanzas[1:]` in the partial
                   "latin": hymnus_latin},
        "versiculus": {"gabc": _stem(versiculus_gabc), "de": spec.versiculus.de,
                       "incipit": spec.versiculus.incipit
                       or incipit(source_of(versiculus_gabc, root), 3),
                       "note": spec.versiculus.note},
        "magnificat": {
            "antiphona": {
                "gabc": _stem(magnificat_ant_gabc),
                "de": spec.magnificat.antiphona.de,
                "repetitio": spec.magnificat.antiphona.repetitio or incipit(mag_gabc, 4),
                "incipit": spec.magnificat.antiphona.incipit or incipit(mag_gabc, 3),
                "note": spec.magnificat.antiphona.note,
            },
            "verses": magnificat_verses,
            # Kurzfassung only: the two-verse system replacing verses 1-2
            "system": magnificat_system,
        },
        "oratio_incipit": " ".join(spec.oratio.text.split()[:3]).rstrip(",;:."),
        "ordinarium": ordinarium,
        "bmv": bmv,
        "filler": filler,
        "drollery": drollery,
        # resolved separately from `feast.back_cover.image`, which may be an
        # embedded data URI rather than a path the template could set
        "back_cover_image": None if back_cover_image is None else back_cover_image.as_posix(),
    }
    return ResolvedFeast(context=context, assets=sorted(assets))
