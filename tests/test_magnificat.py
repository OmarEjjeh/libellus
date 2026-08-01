"""The Kurzfassung's two-verse Magnificat system (ADR-0022)."""

from pathlib import Path

import pytest

from libellus.magnificat import (
    SYSTEM_DIR,
    MagnificatSystemError,
    system_gabc,
)
from libellus.psalmtone import generate_verses

from helpers import physical


@pytest.fixture
def verses_6f(repo_root: Path) -> list[str]:
    """Magnificat verses in tone 6F with open (hollow) reciting notes."""
    return generate_verses("magnificat", "6F", open_notes=True)[1]


def test_open_notes_are_off_by_default(repo_root: Path) -> None:
    """Booklet verses are generated closed: hollow notes belong to a printed
    tone, not to a verse somebody sings."""
    _, closed = generate_verses("magnificat", "6F")
    _, open_ = generate_verses("magnificat", "6F", open_notes=True)

    assert "(hr)" not in closed[1] and "(fr)" not in closed[0]
    assert "(hr)" in open_[1]


def test_system_carries_both_verses_under_one_line_of_notes(
    verses_6f: list[str],
) -> None:
    """Verse 1 in the lyric line, verse 2 in gabc's translation slot beneath
    it, the notes those of the complete verse — so the cadence „Magníficat"
    never reaches is on the page, with no words under it."""
    system = system_gabc(verses_6f[0], verses_6f[1])
    body = system.split("%%", 1)[1]

    assert "name: Magnificat, Kurzfassung (Vers 1 und 2);" in system
    assert "mode: 6;" in system
    # both texts, each numbered, on one system: one clef, one final divisio
    assert body.count("(c4)") == 1
    assert body.count("(::)") == 1
    assert "1.~Ma" in body and "[2.~Et]" in body
    # the mediant cadence verse 1 does not reach: notes, no lyric of its own
    assert "[ <b>spí</b>-](ixi)" in body
    # verse 1's „mi" sits on the reciting note verse 2 has no syllable for
    assert "mi[](fr)" in body
    # and the reciting notes are hollow, as the Liber prints them
    assert "(hr)" in body


def test_the_system_carries_no_padding_of_its_own(verses_6f: list[str]) -> None:
    """Nothing in the notation compensates for the second line's width.

    Gregorio typesets a translation in an \\hbox to 0pt, so it claims no width
    and a longer second line printed into its neighbour. Padding from the lyric
    side was tried and cannot work — verbatim content is emitted but never
    measured. The preamble patches \\GreWriteTranslation instead (see
    test_render), which leaves these files plain.
    """
    body = system_gabc(verses_6f[0], verses_6f[1]).split("%%", 1)[1]

    assert "fi[sul-](h)" in body
    assert "gwiden" not in body and "hphantom" not in body


def test_word_spacing_is_kept_for_each_line_separately(verses_6f: list[str]) -> None:
    """The verses do not break their words in the same places: „á-ni-ma"
    against „in De-o". A space outside the syllable is what gregorio reads to
    end a word above; the line beneath is typeset from the bracket."""
    body = system_gabc(verses_6f[0], verses_6f[1]).split("%%", 1)[1]

    # verse 2 starts a word („De-o") where verse 1 does not („á-ni-ma"), so
    # its space rides inside the bracket and not before the syllable
    assert "ni[ De-](h)" in body
    assert "ma[o](h)" in body


def test_a_solemn_first_verse_has_no_system(repo_root: Path) -> None:
    """Tone 8G sings the Magnificat's first verse to its own solemn formula, so
    the two verses have different melodies for the first half and no single
    system can carry both. Refusing is the point — the booklet then notates
    both verses instead."""
    _, verses = generate_verses("magnificat", "8G", open_notes=True)

    with pytest.raises(MagnificatSystemError) as excinfo:
        system_gabc(verses[0], verses[1])

    assert "mitten in der Formel" in str(excinfo.value)
    assert not physical(SYSTEM_DIR / "8g.gabc").exists()


def test_committed_systems_are_current(repo_root: Path, verses_6f: list[str]) -> None:
    """The freshness gate for the committed assets, on the tone in live use:
    it fails whenever the generator changes without rerunning
    ``libellus magnificat-systems``. (The command's own --check covers all 33,
    which costs 33 engine runs and stays out of the test suite.)"""
    committed = physical(SYSTEM_DIR / "6f.gabc").read_text(encoding="utf-8")

    assert committed == system_gabc(verses_6f[0], verses_6f[1])
