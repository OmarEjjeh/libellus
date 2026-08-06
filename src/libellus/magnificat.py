"""Two verses of the Magnificat on one system (ADR-0022).

The Magnificat's first verse is a single word — „Magníficat" — which cannot
carry the tone's mediant cadence, so jgabc shortens the formula for it. A
booklet that notates verse 1 alone therefore never shows the cadence the other
eleven verses use, and no amount of competence can supply an unseen cadence.

The Liber Usualis prints both verses under one system instead: the notes of the
complete verse, verse 1's syllables where they fall, verse 2's beneath them, and
the notes verse 1 has no words for simply standing there. This module builds
that system, once per tone, into files committed under
``chant/magnificat/kurzfassung/`` — the text of those two verses never varies,
so the placement is decided once and can be read off the page rather than
recomputed per build (the reasoning of ADR-0010's incipit table).

The second text line is gabc's translation slot, which gregorio sets under the
lyrics; ``\\grechangestyle{translation}{}`` keeps it upright, since it is sung
Latin and not a translation.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from libellus.paths import source_of
from libellus.psalmtone import generate_verses, list_toni, mediationes_per_tonus

logger = logging.getLogger(__name__)

#: Where the committed systems live. Not under ``toni/``: that is the
#: gitignored per-tone generation cache.
SYSTEM_DIR = Path("chant/magnificat/kurzfassung")

#: The mediant divider jgabc writes between the two half-verses.
_MEDIANT = " *(:) "

#: One ``syllable(notes)`` pair. The syllable may carry ``<b>``/``<i>``
#: pointing or be empty (a note group of its own).
_SLOT = re.compile(r"(?P<text>[^()]*)\((?P<notes>[^)]*)\)")

#: A note's gregorio annotation, e.g. the brace jgabc draws over a reciting
#: note that covers several syllables (``gr[ocba:1;6mm]``). Kept in the output,
#: ignored when comparing one verse's notes with the other's.
_ANNOTATION = re.compile(r"\[[^\]]*\]")

#: A note group ending in an open reciting note jgabc appended to the previous
#: syllable, e.g. ``me(g hr)``. The Liber gives that note its own place in the
#: system, because the other verse may well have a syllable for it.
_TRAILING_OPEN = re.compile(
    r"^(?P<notes>.*?)\s+(?P<open>[a-mA-M][^\s]*r[.]?(?:\[[^\]]*\])?)$"
)


class MagnificatSystemError(Exception):
    """A German, user-facing message about building a two-verse system."""


def _halves(gabc: str) -> tuple[str, str]:
    """The two half-verses of a generated verse, notation included."""
    body = gabc.split("%%", 1)[-1]
    body = body.replace("(::)", "").strip()
    if _MEDIANT not in body:
        raise MagnificatSystemError(
            f"Der Vers hat keine Versmitte („{_MEDIANT.strip()}“): {body}"
        )
    first, second = body.split(_MEDIANT, 1)
    # the clef opens the verse and belongs to the system, not to a syllable
    first = re.sub(r"^\((?:c|f)b?\d\)\s*", "", first.strip())
    # jgabc numbers each verse; the system carries its own numbers instead
    first = re.sub(r"^\d+\.\s*", "", first)
    return first, second.strip()


def _slots(half: str) -> list[tuple[str, str]]:
    """``(syllable, notes)`` pairs of one half-verse.

    A trailing open reciting note is split into a slot of its own, so the
    other verse can put a syllable on it.
    """
    slots: list[tuple[str, str]] = []
    for match in _SLOT.finditer(half):
        text, notes = match.group("text"), match.group("notes")
        trailing = _TRAILING_OPEN.match(notes)
        if trailing:
            slots.append((text, trailing.group("notes")))
            slots.append(("", trailing.group("open")))
        else:
            slots.append((text, notes))
    return slots


def _pitch(notes: str) -> str:
    """A note group reduced to what identifies it across two realizations.

    The open-note marker goes: whether jgabc drew a reciting note hollow
    depends on whether *that* verse had a syllable for it, which is exactly
    what differs between the two verses being merged. Annotations go too.
    """
    return re.sub(r"r(?=[.]?$)", "", _ANNOTATION.sub("", notes).strip())


def _plan(
    first: list[tuple[str, str]], second: list[tuple[str, str]]
) -> list[tuple[int | None, int | None]]:
    """The merged order of both verses' slots, as ``(verse 1, verse 2)`` indices.

    A longest common subsequence over the note pitches recovers where verse 1's
    syllables belong, ties resolving towards the earlier slot so they sit at the
    head of a reciting run, as the Liber prints them. Both verses realize the
    same formula, so most of verse 1's notes are also the complete verse's; a
    note only one of them sings gets a slot to itself, carrying that verse's
    syllable alone — the device the system already uses for the notes verse 1
    has no words for, read the other way round.

    **Verse-1-only notes are accepted only as a contiguous tail.** Six tones
    end their shortened mediant a step off the complete verse's („cat" on
    ``i.`` where verse 2 has ``j.``): those two notes stand side by side at the
    end of the line, each under its own verse's last syllable. Where instead
    the divergence runs through the intonation — 8G's ``g hg gj`` against
    ``g h j`` — a merged line would alternate between the verses note by note
    and read as neither, so this refuses and the booklet notates both verses.

    :raises MagnificatSystemError: when the two verses' notes interleave.
    """
    keys_first = [_pitch(notes) for _, notes in first]
    keys_second = [_pitch(notes) for _, notes in second]
    rows, columns = len(keys_first), len(keys_second)
    # lengths[i][j] = LCS length of keys_first[i:] and keys_second[j:]
    lengths = [[0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(columns - 1, -1, -1):
            if keys_first[i] == keys_second[j]:
                lengths[i][j] = 1 + lengths[i + 1][j + 1]
            else:
                lengths[i][j] = max(lengths[i + 1][j], lengths[i][j + 1])

    steps: list[tuple[int | None, int | None]] = []
    i = j = 0
    while i < rows and j < columns:
        if keys_first[i] == keys_second[j] and lengths[i][j] == 1 + lengths[i + 1][j + 1]:
            steps.append((i, j))
            i, j = i + 1, j + 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            steps.append((i, None))
            i += 1
        else:
            steps.append((None, j))
            j += 1
    steps += [(index, None) for index in range(i, rows)]
    steps += [(None, index) for index in range(j, columns)]

    shared = [position for position, (a, b) in enumerate(steps) if a is not None and b is not None]
    last_shared = shared[-1] if shared else -1
    interleaved = [
        first[a][0].strip() or "(ohne Text)"
        for position, (a, b) in enumerate(steps)
        if b is None and a is not None and position < last_shared
    ]
    if interleaved:
        raise MagnificatSystemError(
            "Der 1. Vers singt hier Noten, die der 2. nicht hat, und zwar "
            "mitten in der Formel (bei: " + ", ".join(interleaved) + ") — die "
            "beiden Verse lassen sich nicht in ein System legen."
        )

    # The divergent tail is a cadence ending: it belongs beside the complete
    # verse's own last note, not before the reciting notes leading up to it.
    head, tail = steps[: last_shared + 1], steps[last_shared + 1 :]
    only_first = [step for step in tail if step[1] is None]
    only_second = [step for step in tail if step[1] is not None]
    if not only_first:
        return steps
    return head + only_second[:-1] + only_first + only_second[-1:]


def _hyphenate(texts: list[str]) -> list[str]:
    """Mark syllable continuation in the second text line.

    Gregorio hyphenates the lyric line itself but not the translation, so the
    hyphens of „sul-tá-vit" have to be written out. A syllable continues the
    word before it when jgabc did not put a space in front of it — which is
    also why the original spacing is preserved everywhere else here: it is
    what tells gregorio where a word ends. Slots this verse has no syllable for
    are skipped: what follows „tus" is „me", not the gap between them.
    """
    out: list[str] = []
    for index, text in enumerate(texts):
        following = next((t for t in texts[index + 1:] if t.strip()), "")
        continues = bool(following.strip()) and not following.startswith(" ")
        out.append(f"{text}-" if text.strip() and continues else text)
    return out


def _close_words(lyrics: list[str]) -> list[str]:
    """Space the slots verse 1 has no syllable for, where its word has ended.

    Gregorio draws a continuation hyphen across every gap it takes to be inside
    a word, which is what „Magní-fi- - - -cat" wants. But after „á-ni-ma" the
    word is finished, and an unspaced gap would hyphenate it into the void. A
    gap closes the word when the next syllable verse 1 does have starts a new
    one — or when it has none left.
    """
    spaced = list(lyrics)
    for index, text in enumerate(lyrics):
        if text.strip():
            continue
        following = next((t for t in lyrics[index + 1:] if t.strip()), None)
        if following is None or following.startswith(" "):
            spaced[index] = " "
    return spaced


def _merge(first: list[tuple[str, str]], second: list[tuple[str, str]]) -> str:
    """One half-verse of the system: verse 1 as lyrics, verse 2 beneath it."""
    plan = _plan(first, second)
    # The COMPLETE verse takes the lyric line, the short one the slot beneath.
    # Gregorio sizes a syllable by its lyric alone and lays a word's second-line
    # syllables as a run nothing on the lyric side can widen — so with verse 1
    # above, „sul-" and „tá-" of verse 2 printed on top of each other in every
    # tone. With the longer verse governing the spacing, the shorter one beneath
    # always fits. The cost is that verse 2 stands above verse 1; both lines
    # carry their number, so which is which stays plain.
    lyrics = _close_words(["" if a is None else first[a][0] for a, _ in plan])
    beneath = _hyphenate(["" if b is None else second[b][0] for _, b in plan])
    notation: list[str] = []
    for a, b in plan:
        # a slot only verse 1 sings keeps its own note; everywhere else the
        # complete verse's is authoritative, since that is the one carrying
        # jgabc's hollow marker for a reciting note
        if b is not None:
            notation.append(second[b][1])
        else:
            assert a is not None  # every slot names at least one of the verses
            notation.append(first[a][1])

    pieces: list[str] = []
    for index, notes in enumerate(notation):
        lyric, under = lyrics[index], beneath[index]
        if lyric.strip() or under.strip():
            # Word spacing is per line, and the two verses do not break their
            # words in the same places („á-ni-ma" against „in De-o"): a space
            # OUTSIDE the syllable is what gregorio reads to end a word in the
            # lyric line, while the line beneath is typeset from the bracket, so
            # its own space belongs inside it. The widths take care of
            # themselves — see the \GreWriteTranslation patch in the preamble.
            space = " " if lyric.startswith(" ") else ""
            pieces.append(f"{space}{lyric.strip()}[{under}]({notes})")
        elif pieces:
            # a note neither verse sings: jgabc wrote it inside the previous
            # syllable's group (`me(g hr)`) and it goes back there, so nothing
            # breaks the word the two syllables around it belong to
            pieces[-1] = re.sub(r"\)$", f" {notes})", pieces[-1])
        else:
            pieces.append(f"({notes})")
    # joined without separators: the syllables carry their own spacing
    return "".join(pieces)


def _plain(text: str) -> str:
    """Text without pointing markup — what a phantom has to be as wide as."""
    return re.sub(r"</?[bi]>", "", text)


def system_gabc(verse_one: str, verse_two: str) -> str:
    """The complete gabc file for one tone's two-verse Magnificat system.

    The mode and differentia headers are copied from the generated verse rather
    than rebuilt from the tone label: only the engine knows how a tone with a
    single termination is spelled, and it already wrote it down.

    :param verse_one: Generated verse 1, open notes on.
    :param verse_two: Generated verse 2, open notes on.
    :raises MagnificatSystemError: when the two verses cannot be merged.
    """
    first_one, second_one = _halves(verse_one)
    first_two, second_two = _halves(verse_two)
    header = [
        line if not line.startswith("name:") else "name: Magnificat, Kurzfassung (Vers 1 und 2);"
        for line in verse_two.split("%%", 1)[0].strip().splitlines()
    ]
    clef = re.match(r"\((?:c|f)b?\d\)", verse_two.split("%%", 1)[-1].strip())
    # The verse numbers ride on the first syllable, the way jgabc numbers an
    # ordinary verse — a slot of their own has no notes, hence no width, and
    # the syllable after it would print on top of them.
    mediant = _numbered(_merge(_slots(first_one), _slots(first_two)))
    body = (
        f"{clef.group() if clef else '(c4)'} {mediant} *[*](:) "
        f"{_merge(_slots(second_one), _slots(second_two))} (::)"
    )
    return "\n".join(header) + "\n%%\n" + body + "\n"


def _numbered(half: str) -> str:
    """Number both text lines. The lyric line is verse 2 (see :func:`_merge`)."""
    half = re.sub(r"^(\s*)", r"\g<1>1.~", half, count=1)
    return re.sub(r"\[", "[2.~", half, count=1)


def build_systems() -> dict[str, str]:
    """Every tone's two-verse system, keyed by the tone's cache folder name.

    Runs each tone through the engine with open notes on, so a reciting note
    the verse puts no syllable on arrives already hollow.

    **Not every tone gets one.** Where the tone table holds a ``solemn`` form,
    jgabc sings the Magnificat's first verse to *that* rather than to a
    shortened ferial mediant — tone 8G's „Ma(g)gní(hg)fi(gj jr)cat(j.)"
    against „Et(g) ex(h)sul(j)…". The two verses then have different melodies
    for the first half, which no single system can carry and which it would be
    wrong to force. Those tones are skipped here and the booklet notates both
    verses separately instead; the absence of the file is that decision.

    **Some tones get more than one.** Where the books print two mediations
    under one label (``6F``, ADR-0043), each is a melody of its own and gets
    its own system. Keying by cache folder rather than by label is what keeps
    them apart — ``6f`` and ``6f-ut-in-tono-i``.
    """
    systems: dict[str, str] = {}
    skipped: list[str] = []
    mediationes = mediationes_per_tonus()
    for label in list_toni():
        # The first mediation listed is the tone's default, and is generated
        # under no name at all — naming it would only produce the same file.
        for mediatio in [None, *mediationes.get(label, [])[1:]]:
            named = f"{label} ({mediatio})" if mediatio else label
            folder, verses = generate_verses(
                "magnificat", label, open_notes=True, mediatio=mediatio
            )
            if len(verses) < 2:
                raise MagnificatSystemError(
                    f"Ton „{named}“: der Generator liefert nur {len(verses)} Vers(e)."
                )
            try:
                systems[folder] = system_gabc(verses[0], verses[1])
            except MagnificatSystemError:
                skipped.append(named)
                continue
            logger.debug("Kurzfassungs-System für Ton %s erzeugt (%s).", named, folder)
    logger.info(
        "Magnificat-Systeme erzeugt: %d von %d Tönen. Eigene Melodie im 1. Vers "
        "(zwei Systeme statt einem): %s",
        len(systems), len(systems) + len(skipped), ", ".join(skipped) or "keine",
    )
    return systems


def write_systems(root: Path) -> list[Path]:
    """Write every tone's system into ``chant/magnificat/kurzfassung/``.

    :return: Root-relative paths of the files whose content changed.
    """
    target = source_of(SYSTEM_DIR, root)
    target.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []
    for folder, content in build_systems().items():
        path = target / f"{folder}.gabc"
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            changed.append(path.relative_to(root))
    return changed


def stale_systems(root: Path) -> list[str]:
    """Tone folders whose committed system is missing or out of date."""
    stale: list[str] = []
    for folder, content in build_systems().items():
        path = source_of(SYSTEM_DIR / f"{folder}.gabc", root)
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            stale.append(folder)
    return stale
