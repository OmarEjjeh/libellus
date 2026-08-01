import datetime

from libellus.latin import draft_slug, draft_stamp, latin_date, roman


def test_roman() -> None:
    assert roman(109) == "cix"
    assert roman(4) == "iv"
    assert roman(2026) == "mmxxvi"


def test_latin_date() -> None:
    assert (
        latin_date(datetime.date(2026, 7, 10))
        == "Die \\textsc{x} Iulii, Anno Domini \\textsc{mmxxvi}"
    )


def test_draft_stamp_spells_the_month_and_keeps_the_time() -> None:
    """The footer line of a draft (ADR-0021): spelled month, no leading zero
    on the day, time to the minute so two drafts of one day differ."""
    moment = datetime.datetime(2026, 7, 30, 14, 32)
    assert draft_stamp(moment) == "Entwurf vom 30. Juli 2026, 14:32 Uhr"
    assert draft_stamp(datetime.datetime(2026, 3, 5, 9, 7)) == (
        "Entwurf vom 5. März 2026, 09:07 Uhr"
    )


def test_draft_slug_sorts_chronologically() -> None:
    """The build-folder suffix: zero-padded, so folders sort by age."""
    assert draft_slug(datetime.datetime(2026, 7, 30, 14, 32)) == "entwurf-2026-07-30-1432"
    assert draft_slug(datetime.datetime(2026, 3, 5, 9, 7)) == "entwurf-2026-03-05-0907"
