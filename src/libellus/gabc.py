"""Minimal GABC reading: headers and lyric incipits (for the Ordo table
and antiphon repeat lines)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def is_inline_gabc(source: str) -> bool:
    """Whether a feast-spec ``gabc:`` value is notation itself, not a repo path.

    Inline GABC (ADR-0005) is recognized by the mandatory ``%%`` header/body
    separator line plus at least one ``(...)`` note group.
    """
    return bool(re.search(r"^\s*%%\s*$", source, flags=re.MULTILINE)) and "(" in source


def read_headers(path: Path) -> dict[str, str]:
    """Parse the ``key: value;`` headers before the ``%%`` separator."""
    headers: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "%%":
            break
        match = re.match(r"([\w-]+)\s*:\s*(.*?);?\s*$", line)
        if match:
            headers[match.group(1)] = match.group(2)
    return headers


def chant_name(path: Path) -> str:
    """The ``name:`` header without transcriber parentheticals like ``(simple tone)``."""
    name = read_headers(path).get("name")
    if name is None:
        name = path.stem.replace("-", " ").title()
        logger.debug(
            "„%s“ hat keinen name:-Header — Rückfall auf Dateinamen „%s“.", path.name, name
        )
    return re.sub(r"\s*\([^)]*\)\s*$", "", name)


def lyrics(path: Path) -> str:
    """Extract the plain sung text from a gabc file.

    Strips the note groups ``(...)``, markup tags like ``<b>``/``<i>``, the
    euouae block, a leading verse number such as ``1.``, and ℣./℟. rubric
    markers (the newer Unicode-character convention — equivalent to the
    legacy ``<sp>V/</sp>``/``<sp>R/</sp>`` tags, which the ``<sp>`` strip
    below already removes). The mid-verse markers ``*`` and ``†`` are kept
    (incipit uses them as cut points).
    """
    return _plain_text(_body(path))


def _body(path: Path) -> str:
    """Everything after the ``%%`` header separator — notation included."""
    return path.read_text(encoding="utf-8").split("%%", 1)[-1]


def _plain_text(body: str) -> str:
    """Strip notation and markup from a gabc body; see :func:`lyrics`."""
    body = re.sub(r"<eu>.*?</eu>", "", body, flags=re.DOTALL)
    body = re.sub(r"<sp>\s*([*†])\s*</sp>", r" \1 ", body)
    body = re.sub(r"<sp>.*?</sp>", "", body, flags=re.DOTALL)
    body = re.sub(r"[℣℟]\.", "", body)
    body = re.sub(r"\([^)]*\)", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"^\s*\d+\.\s*", "", body.strip())
    return re.sub(r"\s+", " ", body).strip()


#: GABC's ``<sp>`` special characters, spelled out as the glyph each stands
#: for. Only what the chants a Kurzfassung touches actually contain — psalm
#: verses and hymn stanzas. Anything else falls back to its own inner text
#: rather than vanishing, which is what ``_plain_text`` does and why
#: "sæculórum" came out of it as "s{}culórum".
_SPECIALS = {"'ae": "ǽ", "ae": "æ", "'oe": "œ́", "oe": "œ", "+": "†", "*": "*"}

#: Where a stanza ends: the divisio finalis. Metrical lines inside it end at
#: the divisio minor or maior — the same unit :func:`hymn_incipit` cuts on.
_DIVISIO_FINALIS = re.compile(r"\(::\)")
_DIVISIO_LINE = re.compile(r"\([;:]\)")

#: The hymn's closing Amen, which every transcription writes after the last
#: divisio finalis and so looks like a stanza of its own. It is sung with the
#: doxology, not as a seventh stanza, and there is no German for it.
_AMEN = re.compile(r"(?i)^amen\.?$")


def _pointed_text(body: str) -> str:
    """A gabc body as printable text, pointing kept (ADR-0022).

    Unlike :func:`_plain_text`, which reduces a chant to bare words for an
    incipit, this keeps everything a singer needs when the neumes are gone:
    the ``<b>`` accent and ``<i>`` preparation marks the tone engine writes,
    and the mid-verse ``*``/``†``. Notation-only spellings are resolved to
    their glyphs — ``<sp>`` specials, the ``<e>`` elision tag, and the braces
    that group a syllable containing markup (``s{<sp>'ae</sp>}cula``).
    """
    body = re.sub(
        r"<sp>\s*(.*?)\s*</sp>",
        lambda m: _SPECIALS.get(m.group(1), m.group(1)),
        body,
        flags=re.DOTALL,
    )
    body = re.sub(r"<e>(.*?)</e>", r"\1", body, flags=re.DOTALL)
    body = re.sub(r"\([^)]*\)", "", body)
    body = body.replace("{", "").replace("}", "")
    # Note groups split a word into syllables, so adjacent runs of the same
    # tag are one bold or italic passage: \textit{dex}\textit{tris} would set
    # identically but reads as two.
    body = re.sub(r"</([bi])><\1>", "", body)
    body = re.sub(r"^\s*\d+\.\s*", "", body.strip())
    return re.sub(r"\s+", " ", body).strip()


def pointed_halves(path: Path) -> list[str]:
    """A psalm or canticle verse as half-verses of pointed text (ADR-0022).

    The flex ``†`` and the mediant ``*`` each end the half-verse they belong
    to, so a text verse presents the same landmarks in the same places as the
    notated verse it replaces.
    """
    halves: list[str] = []
    for chunk in re.split(r"\s*([*†])\s*", _pointed_text(_body(path))):
        if chunk in {"*", "†"} and halves:
            halves[-1] = f"{halves[-1]} {chunk}"
        elif chunk.strip():
            halves.append(chunk.strip())
    return halves


def hymn_stanzas(path: Path) -> list[list[str]]:
    """Each stanza of a hymn as its metrical lines of text (ADR-0022).

    Stanzas end at the divisio finalis ``(::)``, metrical lines at the
    divisio minor or maior — cutting a line mid-metre reads as a mistake
    (ADR-0020). A closing Amen stands after its own divisio finalis but is
    not a stanza, so it joins the one before it. Empty when the notation
    marks no stanza end at all, which the caller must report rather than
    guess around.
    """
    body = _body(path)
    if not _DIVISIO_FINALIS.search(body):
        logger.debug("„%s“ hat keine Divisio finalis — keine Strophen erkennbar.", path.name)
        return []
    stanzas: list[list[str]] = []
    for chunk in _DIVISIO_FINALIS.split(body):
        if not chunk.strip():
            continue
        lines = [_pointed_text(line) for line in _DIVISIO_LINE.split(chunk)]
        stanzas.append([line for line in lines if line])
    # only the first stanza carries the all-caps syllable of the drop-cap
    # initial, so only there is there anything to undo
    if stanzas and stanzas[0]:
        stanzas[0][0] = _normalize_first_word(stanzas[0][0])
    if len(stanzas) > 1 and len(stanzas[-1]) == 1 and _AMEN.match(stanzas[-1][0]):
        stanzas[-2].append(stanzas.pop()[0])
    return stanzas


def first_stanza_gabc(path: Path) -> str | None:
    """The hymn file with all but its first stanza cut away, or None.

    A compact booklet prints one notated stanza, and ``\\gregorioscore`` sets
    a whole file — so the truncated score has to exist as a file of its own
    (ADR-0022). None when the notation has no ``(::)`` to cut at.
    """
    text = path.read_text(encoding="utf-8")
    headers, separator, body = text.partition("%%")
    if not separator or not _DIVISIO_FINALIS.search(body):
        return None
    first = _DIVISIO_FINALIS.split(body, maxsplit=1)[0]
    # The space before the divisio matters: written straight onto the last note
    # group, gregorio reads it as that syllable continuing and draws a hyphen
    # after "óptimum." — the divisio has to stand on its own.
    return f"{headers}%%{first.rstrip()} (::)\n"


#: A EUOUAE cue: six syllables spelling the vowels of "saeculOrUm. Amen",
#: each with its own note group — matched whether wrapped in a `<eu>` tag
#: (some GregoBase transcribers) or written bare with no tag at all
#: (others, e.g. Solesmes 1934 "Ab Oriente", transcriber Benjamin
#: Bloomfield) — see issue #33. Tagged forms vary in where the closing
#: `</eu>` sits relative to the last note group — some place it after
#: (`e.(ghg) </eu>`), others before (`e.</eu>(g.)`, e.g. St. Lambert's
#: "Omnes sancti quanta passi") — the optional tag below tolerates both.
_EUOUAE = re.compile(
    r"(?i)\bE(\([^()]*\))\s*u(\([^()]*\))\s*o(\([^()]*\))"
    r"\s*u(\([^()]*\))\s*a(\([^()]*\))\s*e\.?(?:</eu>)?\s*(\([^()]*\))"
)


def find_euouae(text: str) -> str | None:
    """The antiphon's own termination notes, if its GABC has a EUOUAE cue.

    Returns the six note groups space-joined (e.g. ``"j j i j h ghg"``) —
    the same format the psalm-tone engine's termination table uses — or
    ``None`` if the antiphon has no EUOUAE at all (issue #33).
    """
    match = _EUOUAE.search(text)
    if match is None:
        return None
    return " ".join(group.strip("()") for group in match.groups())


#: The six syllables of "sæculOrUm. Amen" as printed at a psalm/canticle
#: ending — always the same text; only the notes vary per termination
#: (issue #33).
_EUOUAE_SYLLABLES = ("E", "u", "o", "u", "a", "e.")

#: How many of a EUOUAE's six neumes are compared when no ending matches
#: exactly: real-world transcriptions embellish and omit morae almost only
#: on the *final* neume (``e.(ghg)`` where the books print ``e.(g.)``), so
#: the leading five still identify the ending's neighbourhood (issue #33).
_EUOUAE_LEADING = 5


def build_euouae_gabc(neumes: str) -> str | None:
    """Splice an ending's termination neumes onto the fixed EUOUAE syllables.

    The neumes come from the psalm-tone engine (``euouae_per_tonus``) —
    mode plus differentia fully determine them, so they are never
    hand-supplied (issue #33). The syllable text never varies.

    :param neumes: Six whitespace-separated neume tokens, e.g.
        ``"j j i j h g."``.
    :return: The full ``E(...) u(...) o(...) u(...) a(...) e.(...)`` GABC
        text, or ``None`` if ``neumes`` isn't exactly six tokens.
    """
    tokens = neumes.split()
    if len(tokens) != 6:
        return None
    return " ".join(
        f"{syllable}({token})" for syllable, token in zip(_EUOUAE_SYLLABLES, tokens)
    )


def normalize_euouae(euouae: str) -> str:
    """A EUOUAE reduced to what is reliably comparable: its pitches.

    Mora dots are dropped. They carry no differentia information but are
    spelled inconsistently in the wild: jgabc writes two moraed notes as
    ``gf..`` where hand transcriptions write ``g.f.``, and transcribers
    routinely omit the final mora altogether (issue #33).
    """
    return " ".join(token.replace(".", "") for token in euouae.split())


def differentia_candidates(
    euouae: str, euouae_per_tonus: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Which endings a EUOUAE could belong to.

    Since every ending's EUOUAE is distinct, an exact match identifies the
    ending uniquely (issue #33).

    :param euouae: The EUOUAE to identify (an antiphon's own, or a feast
        spec's ``euouae:`` assertion).
    :param euouae_per_tonus: Tone label → canonical EUOUAE, from
        ``psalmtone.euouae_per_tonus``.
    :return: ``(exact, leading)`` — labels matching completely, and labels
        agreeing on the leading neumes only (a superset used to accept
        ornamented final neumes).
    """
    wanted = normalize_euouae(euouae)
    head = " ".join(wanted.split()[:_EUOUAE_LEADING])
    exact = [
        label for label, other in euouae_per_tonus.items()
        if normalize_euouae(other) == wanted
    ]
    leading = [
        label for label, other in euouae_per_tonus.items()
        if " ".join(normalize_euouae(other).split()[:_EUOUAE_LEADING]) == head
    ]
    return exact, leading


def _normalize_first_word(text: str) -> str:
    """Undo the all-caps first syllable GregoBase writes for the drop-cap
    initial: ``BEátus vir`` → ``Beátus vir``, ``VIR Dómini`` → ``Vir Dómini``."""
    words = text.split(maxsplit=1)
    if not words:
        return text
    first = words[0]
    if len(first) > 1 and any(c.isupper() for c in first[1:]):
        first = first[0] + first[1:].lower()
    return first if len(words) == 1 else f"{first} {words[1]}"


#: Closed-class Latin words that demand a complement to their right, so an
#: incipit may not end on one — prepositions, conjunctions and
#: subordinators, relatives and correlatives (ADR-0020). The class is
#: closed: this list is complete, not a growing pile of special cases.
_GOVERNING = frozenset(
    # prepositions
    "a ab abs ad adversus ante apud circa circum cis citra contra coram cum "
    "de e ex erga extra in infra inter intra juxta iuxta ob penes per post "
    "prae praeter pro prope propter secundum sine sub subter super supra "
    "trans ultra "
    # conjunctions, subordinators, negation
    "et ac atque aut vel sed nec neque sive seu nam ut ne si nisi quia quod "
    "quoniam dum donec quamvis licet etsi non "
    # relatives and correlatives
    "quam quantus quanta quantum quanti quantae quot qui quae quem quos quas "
    "cujus cuius cui quo qua quibus quorum quarum".split()
)

#: Forms of *esse*. Never stranded: when one sits immediately after the cut
#: it is absorbed, which is what carries ``Omnes Sancti quanta passi`` to
#: ``… sunt`` (ADR-0020). A one-word lookahead, not a classification of the
#: word being kept — suffix-based participle detection would misfire on
#: ``Sancti``, ``Benedíctus`` and ``justi``.
_ESSE = frozenset(
    "sum es est sumus estis sunt eram eras erat eramus eratis erant ero eris "
    "erit erimus eritis erunt sim sis sit simus sitis sint esse esset essent "
    "fui fuisti fuit fuimus fuistis fuerunt fuere fuerat fuerant".split()
)

#: How far the governing-word rule may reach. A bound, not a tuning knob:
#: without it a pathological text could pull a whole line into the Ordo.
_MAX_EXTENSION = 3

#: Accents and ligatures folded away before a stoplist lookup, so `quæ`
#: matches `quae` and an accented preposition still matches.
_FOLD = {
    ord("á"): "a", ord("é"): "e", ord("í"): "i", ord("ó"): "o", ord("ú"): "u",
    ord("ý"): "y", ord("æ"): "ae", ord("ǽ"): "ae", ord("œ"): "oe",
}

_PUNCTUATION = ",;:.!?"


def _fold(word: str) -> str:
    """A word reduced to what the stoplists are keyed on: unaccented lowercase."""
    return word.lower().strip(_PUNCTUATION).translate(_FOLD)


def incipit(path: Path, words: int = 3) -> str:
    """First few words of the sung text, for Ordo-table rows and \\antrepeat.

    Ends at the first punctuation, at the mid-verse marker */† once it
    carries at least 3 words (in antiphons the asterisk may sit after only
    two intonation words — ``Fuit vir * vitæ venerábilis`` reads past it,
    ``Sancte Pater Benedícte * …`` stops at it), or after ``words`` words.

    That cut is then extended so it never dangles (ADR-0020): while the
    last word governs something to its right it absorbs one more word, and
    a form of *esse* immediately after the cut is absorbed rather than
    stranded. Neither fires on an incipit that already reads as a phrase.
    """
    tokens = _normalize_first_word(lyrics(path)).split()
    out: list[str] = []
    cut_at_punctuation = False
    index = -1
    for index, token in enumerate(tokens):
        if token in {"*", "†"}:
            if len(out) >= 3:
                break
            continue
        stripped = token.rstrip(_PUNCTUATION)
        out.append(stripped)
        if stripped != token:
            cut_at_punctuation = True
            break
        if len(out) == words:
            break
    rest = tokens[index + 1:]

    # Extending past punctuation would undo the cut the punctuation made,
    # so a dangling word right before a comma is left alone (it does not
    # occur in practice — Latin does not punctuate after a preposition).
    extension = 0
    while (
        not cut_at_punctuation
        and out
        and rest
        and extension < _MAX_EXTENSION
        and _fold(out[-1]) in _GOVERNING
    ):
        token = rest.pop(0)
        if token in {"*", "†"}:
            continue
        out.append(token.rstrip(_PUNCTUATION))
        extension += 1
        if token != token.rstrip(_PUNCTUATION):
            break

    # Bound by the same barrier as the extension above: a cut the text's own
    # punctuation made is a sense break, and nothing may be pulled across it.
    if not cut_at_punctuation and rest and _fold(rest[0]) in _ESSE:
        out.append(rest[0].rstrip(_PUNCTUATION))
    return " ".join(out)


#: A hymn's first metrical line ends at the divisio minor, so that — not a
#: word count — is where its incipit ends (ADR-0020).
_DIVISIO_MINOR = re.compile(r"\(;\)")


def hymn_incipit(path: Path, words: int = 5) -> str:
    """A hymn's first metrical line, for its Ordo row.

    Hymns are strophic: the first line is a metrical unit the singers know
    by heart, and cutting mid-line reads as a mistake — "Sanctórum méritis
    ínclyta gaúdia" is a sapphic hendecasyllable, "…gaúdia Pangámus" is
    nothing (ADR-0020). Gabc marks the line end with the divisio minor,
    which no punctuation necessarily accompanies.

    :param path: The hymn's gabc file.
    :param words: Fallback word count for a hymn whose notation has no
        divisio minor at all.
    """
    body = _body(path)
    if not _DIVISIO_MINOR.search(body):
        logger.debug(
            "„%s“ hat keine Divisio minor — Rückfall auf %d Wörter.", path.name, words
        )
        return incipit(path, words)
    first_line = _plain_text(_DIVISIO_MINOR.split(body, maxsplit=1)[0])
    # _plain_text keeps */† for incipit()'s sake; a metrical line ends where
    # the divisio does, so a stray marker inside it is not part of the text.
    without_markers = " ".join(t for t in first_line.split() if t not in {"*", "†"})
    return _normalize_first_word(without_markers).rstrip(_PUNCTUATION)
