#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Allioli-Arndt (1914) German psalter: fetch, align to the sung Vulgate verse
boundaries, and write a review draft (issue #1).

Fetches all 150 psalms plus the Magnificat (Lk 1,46-55) from k-bibel.de's
JSON/XML data API (the same data its own bible-reader page renders from —
``BibleAppXmlData/Arndt_1914/Ps<n>.xml``), which conveniently pairs each
German verse with Allioli's own Latin, verse-numbered.

Allioli's own verse numbering is a *print-Bible* convention and does not
always match the *sung* Vulgate/Clementine verse division the vendored
psalm-tone engine points (``psalm-library/vendor/psalms/``) — sometimes
Allioli splits what the sung psalter merges, sometimes the reverse. This
script realigns by normalized Latin word sequence: where the word content is
identical (just cut differently), it regroups German text onto the sung
verse boundaries automatically and flags the regrouping for review. Where
the underlying Latin text itself differs, no automatic recut is attempted —
the psalm is flagged whole and left for manual alignment.

**Copyright status of this specific digitization has not been verified.**
This script produces working/review material only (``psalter/allioli-arndt/``
is not wired into ``PSALTER_DE_PREFERENCE`` and is not credited in
CREDITS.md) — see issue #1's ready-for-human copyright judgement.

Rerunnable and resumable: fetched pages are cached in ``cache/`` (delete to
re-fetch); output YAML files are always regenerated from the cache.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import logging
import re
import sys
import time
import unicodedata
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CACHE_DIR = SCRIPT_DIR / "cache" / "allioli-arndt"
CLEMENTINE_DIR = REPO_ROOT / "src" / "libellus" / "psalm-library" / "vendor" / "psalms"
OUTPUT_DIR = REPO_ROOT / "psalter" / "allioli-arndt"
EU1980_DIR = REPO_ROOT / "psalter" / "eu1980"
REVIEW_FILE = REPO_ROOT / "allioli-arndt-review.html"
UNRESOLVED_FILE = SCRIPT_DIR / "allioli-arndt-unresolved.yaml"
WORK_ITEMS_FILE = SCRIPT_DIR / "allioli-arndt-work-items.json"

BASE_URL = "https://k-bibel.de/BibleAppXmlData/Arndt_1914"
PSALM_URL = BASE_URL + "/Ps{n}.xml"
LUKE_URL = BASE_URL + "/Lk1.xml"

GLORIA_PATRI = (
    "Ehre sei dem Vater und dem Sohn und dem Heiligen Geist.",
    "Wie im Anfang, so auch jetzt und allezeit und in Ewigkeit. Amen.",
)

YAML_HEADER_TEMPLATE = """\
# Allioli-Arndt 1914, aus k-bibel.de's Bibel-App-Datenquelle bezogen und auf
# die Versgrenzen des gesungenen Psalters ausgerichtet (Issue #1). Diese
# Ausrichtung ist {alignment_note}.
# UNGEPRUEFT: Der Urheberrechtsstatus dieser konkreten Digitalisierung ist
# noch nicht bestaetigt (siehe Issue #1) - nicht als Standard-Psalter
# einbinden, bevor das geklaert ist.
"""

_VERSE_RE = re.compile(
    r'<VERS vnumber="(\d+)" Language="(German|Latin)" class="BibleVerse"[^>]*>(.*?)</VERS>',
    re.S,
)


def clean_verse_html(body: str) -> str:
    """Strip footnote markers and tags from one <VERS> body; unescape entities."""
    body = re.sub(r"<sup>\d+</sup>", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html_module.unescape(body)
    return re.sub(r"\s+", " ", body).strip()


def clean_german_verse(text: str) -> str:
    """Drop k-bibel's inline cross-reference markers, e.g. ``[Mal 1,11]``.

    These are the digitizer's own study aid, not part of Allioli's
    translation, and have no counterpart in the sung Latin to align against.
    """
    text = re.sub(r"\s*\[[^\]]*\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_chapter(xml_text: str) -> tuple[dict[int, str], dict[int, str]]:
    """Return ``({verse_number: german}, {verse_number: latin})`` for one chapter."""
    german: dict[int, str] = {}
    latin: dict[int, str] = {}
    for match in _VERSE_RE.finditer(xml_text):
        number, language, body = int(match.group(1)), match.group(2), match.group(3)
        text = clean_verse_html(body)
        if language == "German":
            german[number] = clean_german_verse(text)
        else:
            latin[number] = text
    return german, latin


def fetch(url: str, cache_name: str) -> str:
    """Fetch through the on-disk cache (resumable, deterministic)."""
    cached = CACHE_DIR / cache_name
    if cached.is_file():
        return cached.read_text(encoding="utf-8")
    logger.info("Lade %s ...", url)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(page, encoding="utf-8")
    time.sleep(0.2)  # be polite to the server
    return page


def clementine_lines(psalmus: int) -> list[str]:
    """Sung Vulgate verses (one line each) from the vendored Clementine file."""
    text = (CLEMENTINE_DIR / f"{psalmus:03d}.txt").read_text(encoding="utf-8-sig")
    return [line.strip() for line in text.splitlines() if line.strip()]


_LIGATURES = str.maketrans({"æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ſ": "s"})


def normalize_latin_words(text: str) -> list[str]:
    """Latin text -> lowercase, unaccented, punctuation-free word list.

    Vendored and k-bibel Latin differ only in orthography (accents, ligatures,
    pointing marks) when they render the same underlying words - normalizing
    both to this form is what makes a content-identity check meaningful.
    """
    text = text.translate(_LIGATURES)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return words


def cumulative_boundaries(word_lists: list[list[str]]) -> list[int]:
    """Cumulative word-count checkpoint after each unit, e.g. [3, 7, 10, ...]."""
    boundaries = []
    total = 0
    for words in word_lists:
        total += len(words)
        boundaries.append(total)
    return boundaries


#: Below this SequenceMatcher ratio, treat the two Latin texts as genuinely
#: different (not just re-cut the same words) - refuse to auto-align.
MIN_TEXT_SIMILARITY = 0.90
#: How many sung-side words a mapped Allioli boundary may land from an actual
#: sung boundary and still count as "the same checkpoint" (spelling-variant
#: noise shifts the mapping by a word or two without meaning a real recut).
BOUNDARY_TOLERANCE = 2


def map_boundary(kb_index: int, matcher: SequenceMatcher, sung_len: int) -> int:
    """Where does word ``kb_index`` of the Allioli text land in the sung text?

    Interpolates across non-matching (substituted/inserted/deleted) stretches
    using the surrounding matching blocks, so a handful of spelling variants
    elsewhere in the psalm don't derail the boundary this checkpoint needs.
    """
    blocks = matcher.get_matching_blocks()
    prev_a, prev_b = 0, 0
    for block in blocks:
        if kb_index <= block.a:
            gap_a = block.a - prev_a
            gap_b = block.b - prev_b
            if gap_a == 0:
                return prev_b
            fraction = (kb_index - prev_a) / gap_a
            return round(prev_b + fraction * gap_b)
        if kb_index <= block.a + block.size:
            return block.b + (kb_index - block.a)
        prev_a, prev_b = block.a + block.size, block.b + block.size
    return sung_len


def strip_trailing_colophon(
    psalmus: int | str, kb_numbers: list[int], kb_words: list[list[str]], sung_flat: list[str]
) -> tuple[list[int], list[list[str]], list[str]]:
    """Drop trailing Allioli verses with no counterpart in the sung text.

    Some psalms (e.g. Ps 71's "Defecerunt laudes David filii Jesse") end with
    a book-division colophon that Allioli's print Bible numbers as its own
    verse but the sung Vulgate simply does not carry. Detected only when the
    sung side is already fully matched before the gap starts - a genuine
    trailing textual difference (sung side also has unmatched tail content)
    is left alone for manual review instead.
    """
    kb_flat = [w for words in kb_words for w in words]
    if not kb_flat or not sung_flat:
        return kb_numbers, kb_words, []
    matcher = SequenceMatcher(None, kb_flat, sung_flat, autojunk=False)
    real_blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]
    if not real_blocks:
        return kb_numbers, kb_words, []
    last_block = real_blocks[-1]
    tail_start = last_block.a + last_block.size
    if tail_start >= len(kb_flat):
        return kb_numbers, kb_words, []  # no trailing gap
    if last_block.b + last_block.size < len(sung_flat) - BOUNDARY_TOLERANCE:
        return kb_numbers, kb_words, []  # sung side has unmatched tail too - real difference

    boundary = 0
    keep_numbers, keep_words, notes = [], [], []
    for num, words in zip(kb_numbers, kb_words):
        start = boundary
        boundary += len(words)
        if start >= tail_start - BOUNDARY_TOLERANCE:
            latin_preview = " ".join(words)
            notes.append(
                f"Ps {psalmus} Allioli-Vers {num} (\"{latin_preview}\") ist ein "
                "Kolophon ohne Entsprechung im gesungenen Text - nicht uebernommen."
            )
        else:
            keep_numbers.append(num)
            keep_words.append(words)
    return keep_numbers, keep_words, notes


def strip_leading_superscription_verses(
    psalmus: int | str, kb_numbers: list[int], kb_words: list[list[str]], sung_flat: list[str]
) -> tuple[list[int], list[list[str]], list[str]]:
    """Drop leading Allioli verses that are *entirely* superscription.

    Some psalms give the print-Bible title its own verse number (e.g. Ps 4:
    v1 = "In finem in carminibus, Psalmus David" in full, with the actual
    first sung verse only starting at v2) rather than fusing it onto the
    front of the first real verse (as in Ps 3, where v1 is title *and*
    content together). Only a verse with **zero** overlapping content is
    dropped here - a fused verse keeps its real content and is instead
    reported as a "starts with a superscription" note further down, since
    trimming it would lose translated text.
    """
    kb_flat = [w for words in kb_words for w in words]
    if not kb_flat or not sung_flat:
        return kb_numbers, kb_words, []
    matcher = SequenceMatcher(None, kb_flat, sung_flat, autojunk=False)
    real_blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]
    if not real_blocks:
        return kb_numbers, kb_words, []
    first_block = real_blocks[0]
    if first_block.a == 0 or first_block.b != 0:
        return kb_numbers, kb_words, []  # no leading gap, or sung side has one too

    gap_end = first_block.a
    boundary = 0
    drop_count = 0
    for words in kb_words:
        verse_end = boundary + len(words)
        if verse_end <= gap_end + BOUNDARY_TOLERANCE:
            drop_count += 1
            boundary = verse_end
        else:
            break
    if drop_count == 0:
        return kb_numbers, kb_words, []

    notes = [
        f"Ps {psalmus} Allioli-Vers {kb_numbers[i]} (\"{' '.join(kb_words[i])}\") ist "
        "eine Ueberschrift ohne Entsprechung im gesungenen Text - nicht uebernommen."
        for i in range(drop_count)
    ]
    return kb_numbers[drop_count:], kb_words[drop_count:], notes


def align_psalm(
    psalmus: int | str, kb_german: dict[int, str], kb_latin: dict[int, str], sung_lines: list[str]
) -> dict[str, Any]:
    """Regroup Allioli's German onto the sung verse boundaries.

    Latin word sequences are compared with :class:`difflib.SequenceMatcher`
    rather than exact equality: two independent Vulgate witnesses carry
    ordinary spelling-variant noise (a stray "consilio" for "concilio")
    without that being a substantively different text. Below
    ``MIN_TEXT_SIMILARITY`` the texts are treated as genuinely different and
    left for manual alignment rather than guessed at.

    :return: ``{"status": "clean" | "regrouped" | "text-differs", "verses":
        {sung_verse_number: german_text}, "notes": [str, ...]}``. On
        ``"text-differs"`` ``verses`` is empty - the psalm is left unresolved.
    """
    kb_numbers = sorted(kb_latin)
    kb_words = [normalize_latin_words(kb_latin[n]) for n in kb_numbers]
    sung_words_preview = [normalize_latin_words(line) for line in sung_lines]
    sung_flat_preview = [w for words in sung_words_preview for w in words]
    kb_numbers, kb_words, colophon_notes = strip_trailing_colophon(
        psalmus, kb_numbers, kb_words, sung_flat_preview
    )
    kb_numbers, kb_words, superscription_verse_notes = strip_leading_superscription_verses(
        psalmus, kb_numbers, kb_words, sung_flat_preview
    )
    sung_words = sung_words_preview
    kb_flat = [w for words in kb_words for w in words]
    sung_flat = sung_flat_preview

    matcher = SequenceMatcher(None, kb_flat, sung_flat, autojunk=False)
    ratio = matcher.ratio()

    # A print-Bible superscription (title, historical note) fused into verse
    # 1's Latin has no counterpart in the sung text at all - it drags down
    # the whole-psalm similarity ratio without the psalm *body* actually
    # differing. Detect it and judge similarity on the body alone.
    leading_note = colophon_notes + superscription_verse_notes
    first_block = matcher.get_matching_blocks()[0]
    body_ratio = ratio
    if first_block.a > 0 and first_block.b == 0:
        superscription = " ".join(kb_flat[: first_block.a])
        leading_note.append(
            f"Ps {psalmus} Vers {kb_numbers[0]}: lateinischer Text beginnt mit einer "
            f"Ueberschrift, die im gesungenen Text fehlt (\"{superscription}\") - "
            "im Deutschen ggf. entsprechend kuerzen."
        )
        body_ratio = SequenceMatcher(
            None, kb_flat[first_block.a :], sung_flat, autojunk=False
        ).ratio()

    if body_ratio < MIN_TEXT_SIMILARITY:
        return {
            "status": "text-differs",
            "verses": {},
            "notes": leading_note + [
                f"Ps {psalmus}: lateinischer Wortlaut weicht zu stark ab "
                f"(Aehnlichkeit {body_ratio:.0%}) - keine automatische Ausrichtung."
            ],
            "work_items": [],
        }

    kb_boundaries = cumulative_boundaries(kb_words)
    sung_boundaries = cumulative_boundaries(sung_words)

    if kb_boundaries == sung_boundaries and ratio == 1.0:
        verses = {i + 1: kb_german[num] for i, num in enumerate(kb_numbers)}
        return {"status": "clean", "verses": verses, "notes": [], "work_items": []}

    kb_words_by_num = dict(zip(kb_numbers, kb_words))
    superscription_text = None
    if first_block.a > 0 and first_block.b == 0:
        superscription_text = " ".join(kb_flat[: first_block.a])

    mapped = [map_boundary(b, matcher, len(sung_flat)) for b in kb_boundaries]
    mapped[-1] = len(sung_flat)  # anchor the final checkpoint exactly

    def find_sung_boundary(value: int, start_idx: int) -> int | None:
        """First sung boundary at/after ``start_idx`` within tolerance of ``value``."""
        for idx in range(start_idx, len(sung_boundaries)):
            if abs(sung_boundaries[idx] - value) <= BOUNDARY_TOLERANCE:
                return idx
        return None

    def sung_verse_entries(numbers: list[int]) -> list[dict[str, Any]]:
        return [{"number": n, "latin": sung_lines[n - 1]} for n in numbers]

    def allioli_verse_entries(numbers: list[int]) -> list[dict[str, Any]]:
        return [
            {"number": n, "latin": " ".join(kb_words_by_num[n]), "german": kb_german[n]}
            for n in numbers
        ]

    verses: dict[int, str] = {}
    notes: list[str] = []
    work_items: list[dict[str, Any]] = []
    kb_ptr = 0
    sung_ptr = 0
    is_first_group = True
    while kb_ptr < len(kb_numbers):
        kb_group_start = kb_ptr
        sung_end_idx = None
        # Grow the Allioli-verse group one verse at a time until its mapped
        # boundary lands on a real sung boundary - handles both a merge
        # (several Allioli verses -> one sung verse) and a clean 1:1 step.
        while kb_ptr < len(kb_numbers):
            kb_ptr += 1
            sung_end_idx = find_sung_boundary(mapped[kb_ptr - 1], sung_ptr)
            if sung_end_idx is not None:
                break
        if sung_end_idx is None:
            return {
                "status": "text-differs",
                "verses": {},
                "notes": [
                    f"Ps {psalmus}: kein passender gesungener Versgrenze ab "
                    f"Allioli-Vers {kb_numbers[kb_group_start]} gefunden - von Hand ausrichten."
                ],
                "work_items": [],
            }
        kb_group = kb_numbers[kb_group_start:kb_ptr]
        sung_group = list(range(sung_ptr + 1, sung_end_idx + 2))
        sung_ptr = sung_end_idx + 1
        group_superscription = superscription_text if is_first_group else None
        is_first_group = False

        if len(kb_group) == 1 and len(sung_group) == 1:
            verses[sung_group[0]] = kb_german[kb_group[0]]
            if group_superscription:
                work_items.append(
                    {
                        "psalm": psalmus,
                        "type": "trim",
                        "sung_verses": sung_verse_entries(sung_group),
                        "allioli_verses": allioli_verse_entries(kb_group),
                        "superscription_latin": group_superscription,
                    }
                )
        elif len(sung_group) == 1:
            verses[sung_group[0]] = " ".join(kb_german[n] for n in kb_group)
            notes.append(
                f"Ps {psalmus} Vers {sung_group[0]}: aus Allioli-Versen "
                f"{'/'.join(str(n) for n in kb_group)} zusammengezogen."
            )
            if group_superscription:
                work_items.append(
                    {
                        "psalm": psalmus,
                        "type": "trim",
                        "sung_verses": sung_verse_entries(sung_group),
                        "allioli_verses": allioli_verse_entries(kb_group),
                        "superscription_latin": group_superscription,
                    }
                )
        elif len(kb_group) == 1:
            verses[sung_group[0]] = kb_german[kb_group[0]]
            for extra in sung_group[1:]:
                verses[extra] = ""
            notes.append(
                f"Ps {psalmus} Verse {'/'.join(str(n) for n in sung_group)}: "
                f"Allioli-Vers {kb_group[0]} muss von Hand aufgeteilt werden - "
                f"vollstaendiger Text steht bei Vers {sung_group[0]}, "
                f"{len(sung_group) - 1} weitere(r) Vers(e) leer gelassen."
            )
            work_items.append(
                {
                    "psalm": psalmus,
                    "type": "split",
                    "sung_verses": sung_verse_entries(sung_group),
                    "allioli_verses": allioli_verse_entries(kb_group),
                    "superscription_latin": group_superscription,
                }
            )
        else:
            # Both sides span more than one verse - a merge and a split
            # meet here, so no automatic split point can be trusted. Every
            # word of Allioli's translation is kept (concatenated onto the
            # first sung verse of the group) rather than risk losing any of
            # it; the rest of the group is left empty for a human to
            # redistribute.
            verses[sung_group[0]] = " ".join(kb_german[n] for n in kb_group)
            for extra in sung_group[1:]:
                verses[extra] = ""
            notes.append(
                f"Ps {psalmus} Verse {'/'.join(str(n) for n in sung_group)}: "
                f"Allioli-Verse {'/'.join(str(n) for n in kb_group)} treffen hier "
                "auf mehrere gesungene Verse - muss von Hand aufgeteilt werden, "
                f"vollstaendiger (zusammengezogener) Text steht bei Vers {sung_group[0]}, "
                f"{len(sung_group) - 1} weitere(r) Vers(e) leer gelassen."
            )
            work_items.append(
                {
                    "psalm": psalmus,
                    "type": "tangled",
                    "sung_verses": sung_verse_entries(sung_group),
                    "allioli_verses": allioli_verse_entries(kb_group),
                    "superscription_latin": group_superscription,
                }
            )

    # Any sung verses left over after the last mapped Allioli verse (can
    # happen if the last boundary's tolerance match wasn't the true last
    # sung line) get the remaining Allioli verses, if any, else stay empty.
    while sung_ptr < len(sung_boundaries):
        sung_ptr += 1
        verses.setdefault(sung_ptr, "")
        notes.append(f"Ps {psalmus} Vers {sung_ptr}: kein zugeordneter Allioli-Vers gefunden - von Hand pruefen.")

    return {"status": "regrouped", "verses": verses, "notes": leading_note + notes, "work_items": work_items}


def emit_yaml(psalmus: int, verses: dict[int, str], alignment_note: str) -> str:
    numbered = dict(verses)
    n = len(verses)
    numbered[n + 1] = GLORIA_PATRI[0]
    numbered[n + 2] = GLORIA_PATRI[1]
    header = YAML_HEADER_TEMPLATE.format(alignment_note=alignment_note)
    body = yaml.safe_dump(
        {"psalmus": psalmus, "verses": numbered},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return header + body


def load_eu1980(psalmus: int) -> dict[int, str]:
    path = EU1980_DIR / f"{psalmus}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in data.get("verses", {}).items()}


def build_review_html(results: list[dict[str, Any]]) -> str:
    template = (SCRIPT_DIR / "allioli-arndt-review-template.html").read_text(encoding="utf-8")
    # work_items is intermediate material for the hand-split pass, not part
    # of what the priest's review page needs to carry.
    trimmed = [{k: v for k, v in r.items() if k != "work_items"} for r in results]
    psalms_json = json.dumps(trimmed, ensure_ascii=False)
    return template.replace("__PSALMS_JSON__", psalms_json)


def process_psalm(psalmus: int) -> dict[str, Any]:
    xml_text = fetch(PSALM_URL.format(n=psalmus), f"Ps{psalmus}.xml")
    kb_german, kb_latin = parse_chapter(xml_text)
    sung_lines = clementine_lines(psalmus)
    result = align_psalm(psalmus, kb_german, kb_latin, sung_lines)
    eu1980 = load_eu1980(psalmus)

    if result["status"] != "text-differs":
        alignment_note = {
            "clean": "direkt (Wortfolge identisch, Verszahl stimmt ueberein)",
            "regrouped": "automatisch neu gruppiert (Wortfolge identisch, "
            "Verszahl urspruenglich verschieden) - siehe Anmerkungen",
        }[result["status"]]
        yaml_text = emit_yaml(psalmus, result["verses"], alignment_note)
        target = OUTPUT_DIR / f"{psalmus}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml_text, encoding="utf-8")

    rows = []
    for i in range(len(sung_lines)):
        label = str(i + 1)
        rows.append(
            {
                "label": label,
                "latin": sung_lines[i],
                "allioli": result["verses"].get(i + 1, ""),
                "eu1980": eu1980.get(i + 1, ""),
                "needs_review": result["status"] != "clean"
                or not result["verses"].get(i + 1, "").strip(),
            }
        )

    return {
        "number": psalmus,
        "status": result["status"],
        "notes": result["notes"],
        "rows": rows,
        "work_items": result["work_items"],
    }


def process_magnificat() -> dict[str, Any]:
    xml_text = fetch(LUKE_URL, "Lk1.xml")
    kb_german, kb_latin = parse_chapter(xml_text)
    kb_german = {n: kb_german[n] for n in range(46, 56) if n in kb_german}
    kb_latin = {n: kb_latin[n] for n in range(46, 56) if n in kb_latin}
    sung_lines = clementine_lines_magnificat()
    result = align_psalm("Magnificat", kb_german, kb_latin, sung_lines)
    eu1980 = load_eu1980_magnificat()

    if result["status"] != "text-differs":
        alignment_note = {
            "clean": "direkt (Wortfolge identisch, Verszahl stimmt ueberein)",
            "regrouped": "automatisch neu gruppiert - siehe Anmerkungen",
        }[result["status"]]
        yaml_text = emit_yaml(0, result["verses"], alignment_note).replace(
            "psalmus: 0", "canticum: magnificat"
        )
        target = OUTPUT_DIR / "magnificat.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml_text, encoding="utf-8")

    rows = []
    for i in range(len(sung_lines)):
        rows.append(
            {
                "label": str(i + 1),
                "latin": sung_lines[i],
                "allioli": result["verses"].get(i + 1, ""),
                "eu1980": eu1980.get(i + 1, ""),
                "needs_review": result["status"] != "clean"
                or not result["verses"].get(i + 1, "").strip(),
            }
        )
    return {
        "number": "Magnificat",
        "status": result["status"],
        "notes": result["notes"],
        "rows": rows,
        "work_items": result["work_items"],
    }


def clementine_lines_magnificat() -> list[str]:
    text = (CLEMENTINE_DIR / "Magnificat.txt").read_text(encoding="utf-8-sig")
    return [line.strip() for line in text.splitlines() if line.strip()]


def load_eu1980_magnificat() -> dict[int, str]:
    path = EU1980_DIR / "magnificat.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in data.get("verses", {}).items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--psalm", type=int, action="append", help="nur diese Psalmen (wiederholbar)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    targets = sorted(set(args.psalm)) if args.psalm else list(range(1, 151))

    results = []
    for psalmus in targets:
        try:
            results.append(process_psalm(psalmus))
        except Exception as exc:  # noqa: BLE001 - one bad psalm shouldn't kill the run
            logger.error("Psalm %d: %s", psalmus, exc)
            raise

    if not args.psalm:
        results.append(process_magnificat())

    clean = sum(1 for r in results if r["status"] == "clean")
    regrouped = sum(1 for r in results if r["status"] == "regrouped")
    unresolved = sum(1 for r in results if r["status"] == "text-differs")
    logger.info(
        "Fertig: %d sauber, %d neu gruppiert, %d ungeloest (von %d).",
        clean, regrouped, unresolved, len(results),
    )

    if not args.psalm:
        REVIEW_FILE.write_text(build_review_html(results), encoding="utf-8")
        logger.info("Review-Seite -> %s", REVIEW_FILE.relative_to(REPO_ROOT))
        all_work_items = [item for r in results for item in r["work_items"]]
        WORK_ITEMS_FILE.write_text(
            json.dumps(all_work_items, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "Arbeitsauftraege fuer Handausrichtung: %d -> %s",
            len(all_work_items), WORK_ITEMS_FILE.name,
        )
        unresolved_psalms = [r for r in results if r["status"] == "text-differs"]
        if unresolved_psalms:
            UNRESOLVED_FILE.write_text(
                yaml.safe_dump(
                    {"unresolved": [{"number": r["number"], "notes": r["notes"]} for r in unresolved_psalms]},
                    allow_unicode=True, sort_keys=False,
                ),
                encoding="utf-8",
            )
            logger.info("Ungeloeste Psalmen -> %s", UNRESOLVED_FILE.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
