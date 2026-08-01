"""Date formatting: Roman numerals, Latin cover dates, the German draft stamp."""

from __future__ import annotations

import datetime

_ROMAN = [
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
    (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
    (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
]

#: Month names in the genitive, as used in dates ("Die X Iulii").
MONTHS_GENITIVE = [
    "Ianuarii", "Februarii", "Martii", "Aprilis", "Maii", "Iunii",
    "Iulii", "Augusti", "Septembris", "Octobris", "Novembris", "Decembris",
]

#: Spelled out rather than numeric: the stamp sits in a book whose every
#: other date is set in Latin, and "30.07." reads like machine output there.
MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def roman(number: int) -> str:
    """Lowercase Roman numeral (typeset via \\textsc for the classic look)."""
    if not 0 < number < 4000:
        raise ValueError(f"Roman numeral out of range: {number}")
    result = []
    for value, glyph in _ROMAN:
        while number >= value:
            result.append(glyph)
            number -= value
    return "".join(result)


def latin_date(date: datetime.date) -> str:
    """LaTeX for a cover date, e.g. ``Die \\textsc{x} Iulii, Anno Domini \\textsc{mmxxvi}``."""
    return (
        f"Die \\textsc{{{roman(date.day)}}} {MONTHS_GENITIVE[date.month - 1]}, "
        f"Anno Domini \\textsc{{{roman(date.year)}}}"
    )


def latin_day_month(date: datetime.date) -> str:
    """LaTeX for a short date, e.g. ``\\textsc{xvii} Septembris`` (transfer notes)."""
    return f"\\textsc{{{roman(date.day)}}} {MONTHS_GENITIVE[date.month - 1]}"


def draft_stamp(moment: datetime.datetime) -> str:
    """The draft footer line, e.g. ``Entwurf vom 30. Juli 2026, 14:32 Uhr``."""
    return (
        f"Entwurf vom {moment.day}. {MONATE[moment.month - 1]} {moment.year}, "
        f"{moment:%H:%M} Uhr"
    )


def draft_slug(moment: datetime.datetime) -> str:
    """The build-folder suffix, e.g. ``entwurf-2026-07-30-1432``."""
    return f"entwurf-{moment:%Y-%m-%d-%H%M}"
