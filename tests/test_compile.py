from pathlib import Path

from libellus.compile import _rerun_requested

#: The tail of a LuaLaTeX log that has nothing outstanding.
SETTLED = """Package rerunfilecheck Info: File `smoke.out' has not changed.
Output written on smoke.pdf (36 pages, 2534477 bytes).
"""


def test_settled_log_asks_for_nothing(tmp_path: Path) -> None:
    log = tmp_path / "smoke.log"
    log.write_text(SETTLED, encoding="utf-8")

    assert _rerun_requested(log) is None


def test_gregoriotex_rerun_request_is_seen(tmp_path: Path) -> None:
    """The one the staged Lambertus booklet stopped on top of (#56)."""
    log = tmp_path / "smoke.log"
    log.write_text(
        "Module gregoriotex Warning: Line heights, variable brace lengths, or "
        "soft flats/\nsharps may have changed. Rerun to fix. on input line 0\n"
        + SETTLED,
        encoding="utf-8",
    )

    assert _rerun_requested(log) == "Rerun to fix"


def test_latex_cross_reference_request_is_seen(tmp_path: Path) -> None:
    log = tmp_path / "smoke.log"
    log.write_text(
        "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references "
        "right.\n" + SETTLED,
        encoding="utf-8",
    )

    assert _rerun_requested(log) == "Rerun to get cross-references right"
