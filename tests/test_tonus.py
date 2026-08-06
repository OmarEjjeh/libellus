"""The one psalm-tone resolver: measurement and inference behind one contract (#46).

The notation primitives it reads — ``find_mode``, ``opening_pitch_class``,
``final_pitch_class`` — belong to ``gabc`` and are tested in ``test_gabc.py``.
"""

import re
from pathlib import Path

import pytest

from libellus.gabc import find_mode
from libellus.psalmtone import euouae_per_tonus
from libellus.tonus import (
    Provenance,
    disagrees,
    endings_of_mode,
    labels_with,
    resolve_tonus,
    tonus_message,
)

from helpers import physical


def _antiphon(slug: str) -> str:
    """The committed gabc of one corpus antiphon, verbatim."""
    return physical(f"chant/ant/{slug}.gabc").read_text(encoding="utf-8")


def _labels(gabc: str, provenance: Provenance, **kwargs: str) -> list[str]:
    """The tones one of the two operations proposes for a score."""
    return labels_with(resolve_tonus(gabc, euouae_per_tonus(), **kwargs), provenance)


# --- what a mode's endings are, and what licenses comparing them --------------


def test_no_mode_has_two_endings_an_octave_apart(repo_root: Path) -> None:
    """What licenses the pitch-class reduction: reducing modulo the octave may
    not merge two endings the rule would otherwise tell apart. Within every
    mode the endings' closing notes span less than an octave, so nothing is
    lost — a property asserted of the engine's own table rather than assumed."""
    table = euouae_per_tonus()
    for mode in [str(number) for number in range(1, 9)] + ["p"]:
        closings = [
            _closing_position(table[label]) for label in endings_of_mode(mode, table)
        ]
        assert max(closings) - min(closings) < 7, f"Modus {mode} spans an octave"


def _closing_position(euouae: str) -> int:
    """The staff position (octave included) an ending closes on — the oracle
    the pitch-class reduction is checked against, spelled out here rather than
    imported so it is not a second copy of the code under test."""
    return ord(re.findall(r"[a-mA-M]", euouae)[-1].lower()) - ord("a")


def test_endings_of_mode_comes_from_the_engines_labels(repo_root: Path) -> None:
    """The mode a score declares is the first character of every tone label
    the engine hands out, which is what ties the two together — no table on
    this side lists a mode's endings."""
    table = euouae_per_tonus()
    assert endings_of_mode("8", table) == ["8G", "8G*", "8c"]
    assert endings_of_mode("p", table) == ["peregrinus"]
    assert endings_of_mode("IX", table) == []
    # an empty prefix would otherwise match every label the engine has
    assert endings_of_mode("", table) == []


# --- measurement --------------------------------------------------------------


def test_a_transcribed_euouae_names_its_ending(repo_root: Path) -> None:
    """Measurement, the half that already existed: every ending's EUOUAE is
    distinct, so a transcribed one identifies the tone outright (#33)."""
    assert _labels(_antiphon("omnes-sancti-quanta-passi"), Provenance.EUOUAE) == ["8G"]


def test_an_ornamented_final_neume_falls_back_to_the_leading_neumes(
    repo_root: Path,
) -> None:
    """Transcribers embellish the final neume — "Fuit vir" ends ``e.(ghg)``
    where the books print ``e.(g.)``. That is not an exact match and must not
    be reported as one, but the leading neumes still name a neighbourhood."""
    gabc = _antiphon("fuit-vir-vitae-venerabilis")
    assert _labels(gabc, Provenance.EUOUAE) == []
    assert _labels(gabc, Provenance.EUOUAE_LEADING) == ["8G", "8G*"]


def test_the_euouae_field_stands_in_for_a_score_that_prints_none(
    repo_root: Path,
) -> None:
    """The ``euouae:`` assertion records what a printed source shows for an
    antiphon whose own transcription omits the cue — the resolver measures it
    the same way, which is what makes the build's check and the suggestion one
    implementation."""
    gabc = _antiphon("cum-palma-ad-regna")
    assert _labels(gabc, Provenance.EUOUAE) == []
    assert _labels(gabc, Provenance.EUOUAE, euouae="j j i j h g.") == ["8G"]


# --- inference: the connection rule -------------------------------------------


def test_the_connection_rule_on_an_antiphon_whose_tone_is_known(
    repo_root: Path,
) -> None:
    """#24's calibration case. "Omnes Sancti" is sung to ``8G`` and opens on
    the exact note ``8G``'s termination ends on — so the traditional rule
    reproduces a differentia that was established independently."""
    assert _labels(_antiphon("omnes-sancti-quanta-passi"), Provenance.CONNECTION) == [
        "8G"
    ]


def test_the_connection_rule_resolves_an_antiphon_with_no_euouae(
    repo_root: Path,
) -> None:
    """#24's two unknowns, and the case measurement cannot answer at all:
    neither score prints a EUOUAE. Mode 8's three endings close on three
    different notes (g/h/j), so each match is unique."""
    assert _labels(_antiphon("cum-palma-ad-regna"), Provenance.CONNECTION) == ["8G*"]
    assert _labels(_antiphon("martyrum-chorus-laudate"), Provenance.CONNECTION) == [
        "8c"
    ]


def test_the_connection_rule_reaches_the_tonus_peregrinus(repo_root: Path) -> None:
    """``mode:p`` is a mode like any other here, and its single ending closes
    on the note "Mártyres Dómini" opens on."""
    assert _labels(_antiphon("martyres-domini"), Provenance.CONNECTION) == [
        "peregrinus"
    ]


def test_inference_returns_a_tie_whole(repo_root: Path) -> None:
    """Never guess. Mode 1's ``D``, ``D-`` and ``D2`` all close on ``d``, so an
    antiphon opening on ``d`` gets all three — the ornamental difference
    between them follows no derivable rule, it is a fixed editorial choice of
    a particular printed antiphonale."""
    assert _labels(_antiphon("corpora-sanctorum-in-pace"), Provenance.CONNECTION) == [
        "1D",
        "1D-",
        "1D2",
    ]


def test_inference_reads_an_antiphon_notated_under_another_clef(
    repo_root: Path,
) -> None:
    """The rule compares the antiphon's opening note against a termination the
    engine writes in ``c4``. A GregoBase transcription in ``c3`` spells the
    same note two letters lower and must reach the same answer (#45)."""
    original = _antiphon("martyrum-chorus-laudate")
    rewritten = _in_c3(original)

    assert _labels(rewritten, Provenance.CONNECTION) == _labels(
        original, Provenance.CONNECTION
    ) == ["8c"]


def _in_c3(gabc: str) -> str:
    """The same melody notated in ``c3`` — two staff positions lower, clef
    included. Only note groups are touched."""
    head, separator, body = gabc.partition("%%")

    def move(match: re.Match[str]) -> str:
        group = match.group(1)
        if re.fullmatch(r"[cf]b?[1-4]", group):
            return "(c3)"
        return "(" + re.sub(r"[a-mA-M]", lambda p: chr(ord(p.group()) - 2), group) + ")"

    return head + separator + re.sub(r"\(([^()]*)\)", move, body)


# --- the two operations together ----------------------------------------------


def test_measurement_is_ranked_before_inference(repo_root: Path) -> None:
    """Both operations answer, so both are reported — but measurement reads
    what the transcription says and inference only what a convention suggests,
    and the order says so."""
    candidates = resolve_tonus(
        _antiphon("gloriosus-confessor-domini"), euouae_per_tonus()
    )
    assert [(c.tonus, c.provenance) for c in candidates] == [
        ("8c", Provenance.EUOUAE),
        ("8c", Provenance.CONNECTION),
    ]
    assert not disagrees(candidates)


def test_a_euouae_resolves_the_tie_inference_cannot(repo_root: Path) -> None:
    """The worked example that made #21 and #24 one issue. "Exsultet omnium"
    opens on ``d``, which mode 1's ``D``, ``D-`` and ``D2`` all close on — an
    unresolvable tie for the connection rule. Its transcribed EUOUAE differs
    from ``1D-``'s at the fifth neume and settles it outright."""
    candidates = resolve_tonus(_antiphon("exsultet-omnium-turba"), euouae_per_tonus())

    measured = labels_with(candidates, Provenance.EUOUAE)
    inferred = labels_with(candidates, Provenance.CONNECTION)
    assert measured == ["1D"]
    assert inferred == ["1D", "1D-", "1D2"]
    assert not disagrees(candidates)  # the measured tone is among the inferred


def test_disagreement_is_reported_as_such(repo_root: Path) -> None:
    """A live case in the shipped corpus, not a synthetic one: "Vir Domini
    Benedictus" is sung to ``1f`` and its transcribed EUOUAE says so, but it
    opens on ``d`` — so the connection rule proposes the ``D`` family instead.
    The rule is a convention, not a law; the disagreement is a signal to
    surface, never something to resolve by picking."""
    candidates = resolve_tonus(_antiphon("vir-domini-benedictus"), euouae_per_tonus())

    assert labels_with(candidates, Provenance.EUOUAE) == ["1f"]
    assert labels_with(candidates, Provenance.CONNECTION) == ["1D", "1D-", "1D2"]
    assert disagrees(candidates)


def test_a_mode_whose_endings_the_opening_note_does_not_reach(repo_root: Path) -> None:
    """"Beatus vir" is mode 3 and opens on ``e``; no mode-3 ending closes
    there. Inference is simply silent — which is not a failure, and not a
    licence to relax the rule until something matches."""
    gabc = _antiphon("beatus-vir-benedictus")
    assert _labels(gabc, Provenance.CONNECTION) == []
    assert _labels(gabc, Provenance.EUOUAE) == ["3a2"]  # measurement still answers


def test_nothing_derivable_falls_back_to_the_mode(repo_root: Path) -> None:
    """No EUOUAE and an opening note no ending of the mode closes on. The mode
    is still known, so the honest answer is its endings — tagged as the weak
    thing they are, for a chooser to pick from."""
    gabc = "name:Ohne Alles;\nmode:8;\n%%\n(c4) Lau(f)dá(g)te.(g) (::)\n"
    candidates = resolve_tonus(gabc, euouae_per_tonus())

    assert [(c.tonus, c.provenance) for c in candidates] == [
        ("8G", Provenance.MODE_ONLY),
        ("8G*", Provenance.MODE_ONLY),
        ("8c", Provenance.MODE_ONLY),
    ]


def test_a_score_declaring_no_mode_yields_nothing(repo_root: Path) -> None:
    """The floor. Without a mode there is no candidate set to fall back to,
    and inventing one would be the guess the whole contract forbids."""
    gabc = "name:Ohne Modus;\n%%\n(c4) Lau(f)dá(g)te.(g) (::)\n"
    assert resolve_tonus(gabc, euouae_per_tonus()) == []


# --- the German the surfaces print --------------------------------------------


def test_the_message_names_where_a_suggestion_comes_from(repo_root: Path) -> None:
    """A suggestion is only usable if the author can see what it rests on."""
    message = tonus_message(
        resolve_tonus(_antiphon("omnes-sancti-quanta-passi"), euouae_per_tonus())
    )
    assert "8G" in message and "Schlussformel" in message


def test_disagreement_reads_differently_from_no_match(repo_root: Path) -> None:
    """Two different things, and the AC that says so: "the two operations
    contradict each other" is a finding, "nothing matched" is an absence."""
    disagreement = tonus_message(
        resolve_tonus(_antiphon("vir-domini-benedictus"), euouae_per_tonus())
    )
    nothing = tonus_message([])

    assert "1f" in disagreement and "1D" in disagreement
    assert "widerspricht" in disagreement
    assert disagreement != nothing
    assert "widerspricht" not in nothing


def test_the_mode_only_message_asks_for_a_choice(repo_root: Path) -> None:
    """#46's wording: the mode is known, the ending is not, so say the mode
    and ask — do not offer one of the three as though it were derived."""
    gabc = "name:Ohne Alles;\nmode:8;\n%%\n(c4) Lau(f)dá(g)te.(g) (::)\n"
    message = tonus_message(resolve_tonus(gabc, euouae_per_tonus()))

    assert "Modus 8" in message
    assert "Endung bitte wählen" in message
    assert "8G" in message and "8c" in message


@pytest.mark.parametrize(
    "slug",
    [
        "omnes-sancti-quanta-passi",
        "cum-palma-ad-regna",
        "corpora-sanctorum-in-pace",
        "martyres-domini",
        "martyrum-chorus-laudate",
        "beatus-vir-benedictus",
        "gloriosus-confessor-domini",
        "fuit-vir-vitae-venerabilis",
        "vir-domini-benedictus",
        "exsultet-omnium-turba",
        "laetare-et-lauda",
    ],
)
def test_no_corpus_antiphon_gets_a_label_out_of_thin_air(slug: str) -> None:
    """The contract's first property, swept across every antiphon the two
    shipped booklets sing: every label returned is one the engine knows, and
    a mode's endings are only ever offered whole."""
    table = euouae_per_tonus()
    gabc = _antiphon(slug)
    mode = find_mode(gabc)
    assert mode is not None  # every corpus antiphon declares one
    candidates = resolve_tonus(gabc, table)

    assert all(candidate.tonus in table for candidate in candidates)
    mode_only = labels_with(candidates, Provenance.MODE_ONLY)
    assert mode_only in ([], endings_of_mode(mode, table))
