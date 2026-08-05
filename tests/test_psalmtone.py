"""The psalm-tone engine seam: everything but *running* the engine stays here."""

import json
from collections.abc import Iterator, Sequence

import pytest

from libellus.psalmtone import (
    PsalmToneError,
    euouae_per_tonus,
    generate_verses,
    list_toni,
    set_engine,
    subprocess_engine,
)


class FakeEngine:
    """Answers like ``generate.js`` does: JSON on stdout, exit 2 for bad input."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.returncode = 0
        self.stdout = "{}"
        self.stderr = ""

    def __call__(self, args: Sequence[str]) -> tuple[int, str, str]:
        self.calls.append(list(args))
        return self.returncode, self.stdout, self.stderr


@pytest.fixture
def engine() -> Iterator[FakeEngine]:
    """A fake engine, always uninstalled again — it is process-wide state."""
    fake = FakeEngine()
    set_engine(fake)
    yield fake
    set_engine(subprocess_engine)


def test_an_injected_engine_replaces_the_subprocess(engine: FakeEngine) -> None:
    """What the browser needs: the engine is called, node is not (ADR-0027)."""
    engine.stdout = json.dumps(["1D", "8G"])

    assert list_toni() == ["1D", "8G"]
    assert engine.calls == [["list-toni"]]


def test_verses_are_unpacked_the_same_way(engine: FakeEngine) -> None:
    """The payload contract does not change with the host."""
    engine.stdout = json.dumps({"folder": "8g", "verses": ["v1", "v2"]})

    folder, verses = generate_verses(109, "8G")

    assert (folder, verses) == ("8g", ["v1", "v2"])
    assert engine.calls == [["verses", "--psalmus", "109", "--tonus", "8G"]]


def test_open_notes_reaches_the_engine(engine: FakeEngine) -> None:
    """Only the Kurzfassung's two-verse Magnificat system asks for these (ADR-0022)."""
    engine.stdout = json.dumps({"folder": "1d", "verses": ["v1"]})

    generate_verses("magnificat", "1D", open_notes=True)

    assert "--open-notes" in engine.calls[0]


def test_a_rejected_tone_is_still_a_german_message(engine: FakeEngine) -> None:
    """Exit 2 carries a structured error, and the German is built on this side."""
    engine.returncode = 2
    engine.stdout = json.dumps({"error": 'unknown tone "9Z"', "toni": ["1D", "8G"]})

    with pytest.raises(PsalmToneError, match="gibt es nicht"):
        generate_verses(109, "9Z")


def test_an_engine_that_says_nothing_is_a_german_message(engine: FakeEngine) -> None:
    """A host whose engine failed to start must not surface a traceback."""
    engine.returncode = 1
    engine.stdout = ""
    engine.stderr = "SyntaxError: unexpected token"

    with pytest.raises(PsalmToneError, match="SyntaxError"):
        list_toni()


def test_swapping_the_engine_drops_the_cached_euouae(engine: FakeEngine) -> None:
    """The tone table is cached across a whole build, so a swap must invalidate it."""
    engine.stdout = json.dumps({"8G": "j j i j h g."})
    assert euouae_per_tonus() == {"8G": "j j i j h g."}

    replacement = FakeEngine()
    replacement.stdout = json.dumps({"1D": "h h g f gh gf.."})
    set_engine(replacement)

    assert euouae_per_tonus() == {"1D": "h h g f gh gf.."}


def test_the_default_engine_is_the_subprocess_one() -> None:
    """A host opts in to something else; nobody has to opt in to the shell."""
    import libellus.psalmtone

    assert libellus.psalmtone._engine is subprocess_engine


def test_the_euouae_table_is_written_in_one_canonical_clef() -> None:
    """The engine writes each tone's *verses* in the clef that suits it — c4,
    c3 or f3 — but a EUOUAE is printed on the antiphon's stave, never on the
    verse stave it was derived from. So the table is handed out transposed
    into the one canonical frame, c4, which is what every consumer of it
    already assumed (#45)."""
    table = euouae_per_tonus()
    assert table["8G"] == "j j i j h g."  # written c4: unchanged
    assert table["7b"] == "k k l k j i."  # written c3: two positions up
    assert table["2D"] == "m m m l j k."  # written f3: five positions up
