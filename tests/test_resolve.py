import logging
import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from conftest import BENEDICT_FEAST, SMOKE_FEAST

from libellus.errors import FeastFileError
from libellus.render import render
from libellus.gabc import (
    build_euouae_gabc,
    differentia_candidates,
    find_clef,
    find_euouae,
    normalize_euouae,
)
from libellus import resolve
from libellus.psalmtone import euouae_per_tonus, generate_verses
from libellus.resolve import (
    PSALM_INCIPITS_FILE,
    _select_de_file,
    build_context,
    psalm_incipits,
)
from libellus.schema import FeastSpec

from helpers import physical


def _smoke_data(repo_root: Path) -> dict:
    """Raw YAML of the `romanum-cum-precibus` fixture (St. Lambert)."""
    return yaml.safe_load((repo_root / SMOKE_FEAST).read_text(encoding="utf-8"))


def _benedict_data(repo_root: Path) -> dict:
    """Raw YAML of the `monasticum` fixture (the Benedict office)."""
    return yaml.safe_load((repo_root / BENEDICT_FEAST).read_text(encoding="utf-8"))


def test_verses_are_generated_on_demand(repo_root: Path) -> None:
    """The engine points any (psalm, tone) combo; nothing is read from a library."""
    folder, verses = generate_verses(109, "8G")
    assert folder == "8g"
    assert len(verses) == 10  # 8 verses + Gloria Patri
    assert verses[0].splitlines()[-1] == (
        "(c4) 1. Di(g)xit(h) Dó(j)mi(j)nus(j) Dó(j)mi(j)no(j) <b>me</b>(k)o:(j.) "
        "*(:) Se(j)de(j) a(j) <i>dex</i>(i)<i>tris</i>(j) <b>me</b>(h)is:(g.) (::)"
    )


def test_psalms_below_one_hundred_are_reachable() -> None:
    """Regression: jgabc's psalm files are named with three digits ("042.txt"),
    and the driver looked them up unpadded — so every psalm below 100 reported
    "unknown psalm". Two thirds of the psalter was unreachable, unnoticed
    because only Pss 109-116 had ever been sung from it. The printed name still
    carries the number unpadded."""
    for psalmus in (1, 9, 42, 99):
        _, verses = generate_verses(psalmus, "8G")
        assert verses, f"psalm {psalmus} generated nothing"
        assert f"name: Psalmus {psalmus}," in verses[0]


def test_tonus_label_is_normalized(repo_root: Path) -> None:
    """Tone labels may be written as the books print them: case, spaces, `*`."""
    assert generate_verses(109, "8 G")[0] == "8g"
    assert generate_verses(109, "8G*")[0] == "8gstar"
    assert generate_verses(113, "peregrinus")[0] == "peregrinus"


def test_magnificat_repeats_intonation(repo_root: Path) -> None:
    _, verses = generate_verses("magnificat", "1D")
    assert len(verses) == 12  # 10 verses + Gloria Patri
    # tone-1 intonation f-gh on verse 2, not only on verse 1
    assert "Et(f) ex(gh)sul(h)" in verses[1]


#: Golden fixtures pinning the engine's output byte-exactly. Each covers a
#: distinct engine behavior; 109/8G and the Magnificat are additionally
#: validated against external ground truth (the hand-transcribed Benedict
#: psalm and the byte-identical Magnificat file the schola sang from).
GOLDEN = [
    (109, "8G", 1, "psalm109-8g-v01.gabc"),  # plain verse, ground truth
    (110, "3a2", 4, "psalm110-3a2-v04.gabc"),  # flex (†) verse
    (113, "peregrinus", 1, "psalm113-peregrinus-v01.gabc"),  # two tenors, flat
    (116, "2D", 1, "psalm116-2d-v01.gabc"),  # f3 clef, single termination
    ("magnificat", "1D", 2, "magnificat-1d-v02.gabc"),  # repeated intonation
]


@pytest.mark.parametrize(("psalmus", "tonus", "verse", "fixture"), GOLDEN)
def test_engine_output_matches_golden_fixture(
    repo_root: Path, psalmus: int | str, tonus: str, verse: int, fixture: str
) -> None:
    """Byte-exact regression guard against drift in the engine or driver."""
    _, verses = generate_verses(psalmus, tonus)
    expected = (repo_root / "tests/data/golden" / fixture).read_text(encoding="utf-8")
    assert verses[verse - 1] == expected


def test_psalm_verses_are_never_truncated(repo_root: Path) -> None:
    """Regression (2026-07-27): #33's first design fed an antiphon's EUOUAE
    to the engine as a termination formula. A EUOUAE is six literal pitches
    with no reciting-tone marker, so the engine had only six fixed slots,
    filled them right-to-left and silently dropped every earlier syllable —
    "Sede a dextris meis" printed as "de a dextris meis". Guard the whole
    second hemistich of a long verse, mid-word truncation included."""
    _, verses = generate_verses(109, "8G")
    body = verses[0].split("%%\n", 1)[1]
    sung = re.sub(r"<[^>]+>", "", re.sub(r"\([^)]*\)", "", body))
    assert "Sede a dextris meis" in sung


def test_every_endings_euouae_is_unique(repo_root: Path) -> None:
    """The premise the whole #33 redesign rests on: mode plus differentia
    determine the EUOUAE, and no two endings share one — so a EUOUAE
    identifies its ending unambiguously."""
    table = euouae_per_tonus()
    normalized = [normalize_euouae(euouae) for euouae in table.values()]
    assert len(set(normalized)) == len(table) == 33


def test_unknown_tone_gives_german_message(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    data["antiphonae"][0]["tonus"] = "9z"
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = next(m for m in excinfo.value.messages if "9z" in m)
    assert "Gültige Töne" in message and "8G*" in message


def test_inline_gabc_is_materialized_for_staging(repo_root: Path) -> None:
    """Inline notation (Benedict antiphon 4) becomes a compilable .gabc asset,
    and incipit derivation reads it like any repo file."""
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    assert "%%" in spec.antiphonae[3].gabc  # the fixture demonstrates ADR-0005
    resolved = build_context(spec, repo_root)

    inline_path = Path("chant/inline/antiphona-4.gabc")
    assert inline_path in resolved.assets
    written = physical(inline_path).read_text(encoding="utf-8")
    assert written.rstrip("\n") == spec.antiphonae[3].gabc.rstrip("\n")
    fourth = resolved.context["psalmi"][3]
    assert fourth["antiphona"]["gabc"] == "chant/inline/antiphona-4"
    # incipits derived from the inline lyrics = those the identical
    # path-referenced chant yields (chant/ant/vir-domini-benedictus.gabc)
    assert fourth["antiphona"]["incipit"] == "Vir Dómini Benedíctus"


def test_stale_inline_cache_is_wiped(repo_root: Path) -> None:
    """A rerun never leaves inline chants from a previous feast behind."""
    stale = physical("chant/inline/responsorium.gabc")
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("name:Stale;\n%%\n(c4) Ve(f)tus(g) (::)\n", encoding="utf-8")
    spec = FeastSpec.model_validate(_smoke_data(repo_root))
    build_context(spec, repo_root)
    assert not stale.exists()


def test_filler_page_image_is_recorded_as_an_asset(repo_root: Path) -> None:
    """A structured filler page's `image` is a real field precisely so that
    staging picks it up — a raw .tex page's own \\includegraphics is not
    discovered, which is why the medal page could not be a .tex file."""
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    resolved = build_context(spec, repo_root)

    assert Path("images/02-benedict/medal-print.png") in resolved.assets
    pages = resolved.context["filler"]
    assert [p["kind"] for p in pages] == ["page", "page"]
    assert pages[0]["image"] is None
    assert pages[1]["image"] == "images/02-benedict/medal-print.png"


def test_filler_tex_page_is_staged_verbatim(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["filler"] = ["template/partials/filler.tex.j2"]
    spec = FeastSpec.model_validate(data)
    resolved = build_context(spec, repo_root)

    assert Path("template/partials/filler.tex.j2") in resolved.assets
    assert resolved.context["filler"] == [
        {"kind": "tex", "path": "template/partials/filler.tex.j2"}
    ]


def test_missing_filler_page_image_gives_german_error(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["filler"] = [{"blocks": [{"text": "x"}], "image": "images/gibtsnicht.png"}]
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = next(m for m in excinfo.value.messages if "gibtsnicht" in m)
    assert "Zusatzseite" in message and "nicht gefunden" in message


def test_webp_back_cover_image_gets_convert_first_hint(repo_root: Path) -> None:
    """A .webp back-cover image is rejected in German with a convert hint (#12)."""
    data = _smoke_data(repo_root)
    data["back_cover"]["image"] = "images/rueckseite.webp"
    spec = FeastSpec.model_validate(data)

    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)

    message = " ".join(excinfo.value.messages)
    assert "images/rueckseite.webp" in message
    assert "umwandeln" in message  # the convert-first hint
    # extension is the one clear error — no second "not found" complaint
    assert "nicht gefunden" not in message


def test_non_whitelisted_image_extension_lists_allowed_ones(repo_root: Path) -> None:
    """Extensions LaTeX cannot set are rejected, naming the whitelist (#12)."""
    data = _smoke_data(repo_root)
    data["back_cover"]["image"] = "images/rueckseite.gif"
    spec = FeastSpec.model_validate(data)

    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)

    message = " ".join(excinfo.value.messages)
    assert ".png" in message and ".jpg" in message and ".pdf" in message


def _psalter_entry(root: Path, versio: str, name: str) -> Path:
    """Write an empty Psalter entry, ``<psalter dir>/<versio>/<name>.yaml``.

    Reads the Psalter directory at call time so this works both under the
    suite's probe-Psalter patch and against the real relative path.
    """
    entry = root / resolve.PSALTER_DIR / versio / f"{name}.yaml"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("verses: {}\n", encoding="utf-8")
    return entry


def test_translation_selection_prefers_eu1980(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without psalter_de the preference order eu1980 → eu2016 decides.

    This is the one test about the preference order itself, so it restores the
    real one — the suite otherwise pins it to the probe Psalter (conftest).
    """
    monkeypatch.setattr(
        "libellus.resolve.PSALTER_DE_PREFERENCE", ("eu1980", "eu2016")
    )
    eu2016 = _psalter_entry(tmp_path, "eu2016", "109")
    problems: list[str] = []
    library_dir = Path("chant/psalmi/109")

    # only eu2016 present → the single available translation is used
    chosen = _select_de_file(library_dir, None, "Psalm 109", problems, tmp_path)
    assert chosen == eu2016 and not problems

    # eu1980 appears → it wins the default
    eu1980 = _psalter_entry(tmp_path, "eu1980", "109")
    chosen = _select_de_file(library_dir, None, "Psalm 109", problems, tmp_path)
    assert chosen == eu1980 and not problems

    # explicit request overrides the preference
    chosen = _select_de_file(library_dir, "eu2016", "Psalm 109", problems, tmp_path)
    assert chosen == eu2016 and not problems


def test_translation_selection_single_unknown_version_is_used(tmp_path: Path) -> None:
    """A successor's own single Psalter works without touching the code."""
    entry = _psalter_entry(tmp_path, "hausuebersetzung", "42")
    problems: list[str] = []
    chosen = _select_de_file(
        Path("chant/psalmi/42"), None, "Psalm 42", problems, tmp_path
    )
    assert chosen == entry and not problems


def test_the_magnificat_is_a_psalter_entry_of_its_own(tmp_path: Path) -> None:
    """A Psalter covers the canticle too, under ``magnificat.yaml`` — the
    Magnificat's verse library is not numbered like a psalm's."""
    entry = _psalter_entry(tmp_path, "eu2016", "magnificat")
    problems: list[str] = []
    chosen = _select_de_file(
        Path("chant/magnificat"), None, "Magnificat", problems, tmp_path
    )
    assert chosen == entry and not problems


def test_translation_selection_without_a_psalter_gives_german_error(
    tmp_path: Path,
) -> None:
    """No Psalter at all is the state of a fresh install: none ships, because
    no German translation is redistributable yet (ADR-0024). The message has to
    say where one goes and name the way out."""
    problems: list[str] = []
    chosen = _select_de_file(Path("chant/psalmi/7"), None, "Psalm 7", problems, tmp_path)
    assert chosen is None
    assert problems and "Psalm 7" in problems[0]
    assert "psalter/<Übersetzung>/7.yaml" in problems[0]
    assert "latin_only" in problems[0]


def test_explicit_missing_translation_gives_german_error(repo_root: Path) -> None:
    """Requesting a psalter translation that does not exist names the available ones."""
    data = _smoke_data(repo_root)
    data["psalter_de"] = "eu1780"
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = next(m for m in excinfo.value.messages if "eu1780" in m)
    assert "eu2016" in message  # the available version is listed


def test_a_pinned_translation_is_the_one_resolved(repo_root: Path) -> None:
    """The Benedict fixture pins ``psalter_de: eu2016`` — what its printed
    booklet was set from — and that pin, not the preference order, decides.

    Resolved here against the eu2016 *stand-in* under tests/fixtures/psalter/,
    since the real Einheitsübersetzung is not redistributable (ADR-0024); the
    stand-in's wording is what proves the pin was honoured rather than the
    probe default.
    """
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    assert spec.psalter_de == "eu2016"
    resolved = build_context(spec, repo_root)
    first_verse_de = resolved.context["psalmi"][0]["verses"][0]["de"]
    assert first_verse_de.startswith("Vergleichsvers 1 — Psalm 109")


def test_a_long_unpinned_psalm_resolves_green(repo_root: Path) -> None:
    """A long psalm (Ps 113, Lambert's In exitu) resolves with no pinning, every
    one of its 29 sung verses paired with a German line — the #14 acceptance
    criterion, now checked against the probe Psalter."""
    data = _smoke_data(repo_root)  # unpinned: the preference order decides
    data["antiphonae"][0]["psalmus"] = 113
    data["antiphonae"][0]["tonus"] = "peregrinus"
    # an antiphon whose own gabc carries no EUOUAE, so the tone is free to
    # change here without contradicting it (#33 verification)
    data["antiphonae"][0]["gabc"] = "chant/ant/cum-palma-ad-regna.gabc"
    spec = FeastSpec.model_validate(data)
    resolved = build_context(spec, repo_root)
    first = resolved.context["psalmi"][0]
    assert len(first["verses"]) == 29  # 27 sung verses + Gloria Patri
    assert all(verse["de"] for verse in first["verses"])
    assert first["verses"][0]["de"].startswith("Probevers 1 — Psalm 113")


def test_smoke_feast_resolves_via_generation(repo_root: Path) -> None:
    spec = FeastSpec.model_validate(_smoke_data(repo_root))
    resolved = build_context(spec, repo_root)
    assert resolved.context["psalmi"][0]["verses"]
    assert resolved.context["magnificat"]["verses"]
    # the generated verse files are staged as assets, from the shared
    # cross-feast toni/ cache (no feast-local generation any more, #33)
    assert any(path.name.startswith("v0") and path.suffix == ".gabc" for path in resolved.assets)
    asset_paths = [path.as_posix() for path in resolved.assets]
    assert any("psalmi/109/toni/8g/" in path for path in asset_paths)


def test_antiphon_keeping_its_own_euouae_is_not_rewritten(repo_root: Path) -> None:
    """An antiphon that already prints its EUOUAE (smoke antiphon 1 carries
    a tagged one) needs nothing appended — it is staged as the plain repo
    file, not a materialized copy (#33)."""
    spec = FeastSpec.model_validate(_smoke_data(repo_root))
    resolved = build_context(spec, repo_root)

    assert Path("chant/ant/omnes-sancti-quanta-passi.gabc") in resolved.assets
    assert resolved.context["psalmi"][0]["antiphona"]["gabc"] == (
        "chant/ant/omnes-sancti-quanta-passi"
    )


def test_missing_euouae_is_appended_from_the_tone(repo_root: Path) -> None:
    """The schola whistles the EUOUAE after the antiphon to pitch the psalm,
    so an antiphon printing none gets its tone's canonical one appended
    (#33) — onto a materialized copy, never the committed source
    (ADR-0017), inside an ``<eu>`` tag so incipit derivation ignores it."""
    source = physical("chant/ant/cum-palma-ad-regna.gabc")
    original_content = source.read_text(encoding="utf-8")

    data = _smoke_data(repo_root)
    data["antiphonae"][1]["gabc"] = "chant/ant/cum-palma-ad-regna.gabc"
    data["antiphonae"][1]["tonus"] = "8G"
    spec = FeastSpec.model_validate(data)
    resolved = build_context(spec, repo_root)

    assert source.read_text(encoding="utf-8") == original_content  # untouched

    materialized = (physical("chant/inline/antiphona-2.gabc")).read_text(encoding="utf-8")
    expected = euouae_per_tonus()["8G"]  # derived, not hand-written here
    assert materialized.rstrip("\n") == (
        original_content.rstrip("\n")
        + f" <eu>{build_euouae_gabc(expected)}</eu>(::)"
    )
    assert resolved.context["psalmi"][1]["antiphona"]["gabc"] == "chant/inline/antiphona-2"
    # the superseded original path-reference isn't staged as a dead extra asset
    assert Path("chant/ant/cum-palma-ad-regna.gabc") not in resolved.assets
    # the appended cue must not leak into the antiphon's repeat line
    assert "Euouae" not in resolved.context["psalmi"][1]["antiphona"]["repetitio"]


def test_euouae_disagreeing_with_tonus_gives_german_message(repo_root: Path) -> None:
    """The check that caught two mislabelled St. Lambert antiphons: a EUOUAE
    identifies its ending uniquely, so one naming a different ending than
    ``tonus:`` means the printed cue and the sung psalm would diverge."""
    data = _smoke_data(repo_root)
    data["antiphonae"][1]["gabc"] = "chant/ant/cum-palma-ad-regna.gabc"
    data["antiphonae"][1]["tonus"] = "8G"
    data["antiphonae"][1]["euouae"] = euouae_per_tonus()["8c"]
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = next(m for m in excinfo.value.messages if "euouae" in m)
    assert "Antiphon 2" in message
    assert "„8c“" in message and "„8G“" in message


def test_euouae_matching_tonus_resolves_green(repo_root: Path) -> None:
    """The assertion agreeing with ``tonus:`` is silently accepted."""
    data = _smoke_data(repo_root)
    data["antiphonae"][1]["gabc"] = "chant/ant/cum-palma-ad-regna.gabc"
    data["antiphonae"][1]["tonus"] = "8G"
    data["antiphonae"][1]["euouae"] = "j j i j h g."  # 8G, as the books print it
    spec = FeastSpec.model_validate(data)
    assert build_context(spec, repo_root).context["psalmi"][1]["verses"]


def test_ornamented_final_neume_is_tolerated(repo_root: Path) -> None:
    """Smoke antiphon 1's own EUOUAE ends "e.(ghg)" where the books print
    "e.(g.)" — transcribers embellish and drop morae on the final neume, so
    a EUOUAE matching no ending exactly is accepted when its leading neumes
    still admit the stated tone (#33)."""
    text = (physical("chant/ant/fuit-vir-vitae-venerabilis.gabc")).read_text(encoding="utf-8")
    own = find_euouae(text)
    assert own is not None and own.split()[-1] == "ghg"
    exact, leading = differentia_candidates(own, euouae_per_tonus())
    assert exact == [] and "8G" in leading

    spec = FeastSpec.model_validate(_smoke_data(repo_root))  # tonus: 8G
    assert build_context(spec, repo_root).context["psalmi"][0]["verses"]


def test_unrecognizable_euouae_gives_german_message(repo_root: Path) -> None:
    """Notes matching no ending at all, not even on the leading neumes.

    The nonsense has to *alternate*: since the comparison ignores the octave
    (ADR-0042), a flat line of six identical notes at any height now shares
    the leading neumes of 4g's flat recitation, and would be reported as that
    neighbourhood rather than as unrecognizable.
    """
    data = _smoke_data(repo_root)
    data["antiphonae"][1]["gabc"] = "chant/ant/cum-palma-ad-regna.gabc"
    data["antiphonae"][1]["euouae"] = "a c a c a c"
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = next(m for m in excinfo.value.messages if "euouae" in m)
    assert "Antiphon 2" in message
    assert "keinem bekannten Psalmton" in message


#: How far a clef change moves every note. A staff line is two positions, so
#: rewriting a score from c4 to c3 writes it two letters lower, to c2 four.
#: Spelled out here rather than imported, so that these tests are an oracle
#: for gabc.py's clef arithmetic and not a second copy of it.
_CLEF_SHIFT = {"c3": -2, "c2": -4}


def _rewritten_under_clef(gabc: str, clef: str) -> str:
    """The same melody notated under another clef — what a GregoBase
    transcription in c3 or c2 looks like. Only note groups are touched; the
    sung text around them is left alone."""
    shift = _CLEF_SHIFT[clef]
    head, separator, body = gabc.partition("%%")

    def move(match: re.Match[str]) -> str:
        group = match.group(1)
        if re.fullmatch(r"[cf]b?[1-4]", group):
            return f"({clef})"
        moved = re.sub(r"[a-mA-M]", lambda p: chr(ord(p.group()) + shift), group)
        return f"({moved})"

    return head + separator + re.sub(r"\(([^()]*)\)", move, body)


def test_an_antiphon_in_another_clef_still_matches_its_tone(repo_root: Path) -> None:
    """#45's trigger. Every antiphon in the corpus is (c4) and the check
    compared pitch letters, which are staff positions rather than notes — so
    the first GregoBase transcription in c3 or c2 (routine there) failed its
    tone check on notation that is completely correct, and told the author to
    check notes that were fine. The fixture is a real corpus antiphon
    rewritten under another clef, not a synthetic one.

    Resolving green is half of it; the three clefs must also name the *same*
    ending, which is what the c4 original is here to pin down.
    """
    source = physical("chant/ant/fuit-vir-vitae-venerabilis.gabc")
    original = source.read_text(encoding="utf-8")
    table = euouae_per_tonus()

    def candidates(notation: str) -> tuple[list[str], list[str]]:
        own = find_euouae(notation)
        assert own is not None
        clef = find_clef(notation)
        assert clef is not None
        return differentia_candidates(own, table, clef)

    expected = candidates(original)
    assert expected == ([], ["8G", "8G*"])  # its final neume is ornamented

    for clef in ("c3", "c2"):
        rewritten = _rewritten_under_clef(original, clef)
        assert find_clef(rewritten) == clef
        assert candidates(rewritten) == expected, f"{clef} named another ending"

        data = _smoke_data(repo_root)  # smoke antiphon 1 is this chant, tonus 8G
        data["antiphonae"][0]["gabc"] = rewritten
        spec = FeastSpec.model_validate(data)
        resolved = build_context(spec, repo_root)
        assert resolved.context["psalmi"][0]["verses"], f"{clef} was rejected"


def test_an_antiphon_with_no_clef_is_not_a_build_failure(
    repo_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A score with no clef at all cannot be typeset by gregorio either, so
    stopping the build here would only add a second, worse-worded complaint
    about it. The canonical clef is assumed — and said out loud (#45)."""
    data = _smoke_data(repo_root)
    data["antiphonae"][1]["gabc"] = (
        "name:Ohne Schlüssel;\n%%\n"
        "Lau(j)dá(j)te(i) *(,) Dó(j)mi(h)num.(g) (::) "
        "<eu>E(j) u(j) o(i) u(j) a(h) e.(g.)</eu>(::)\n"
    )
    data["antiphonae"][1]["tonus"] = "8G"
    spec = FeastSpec.model_validate(data)

    with caplog.at_level(logging.WARNING, logger="libellus.resolve"):
        resolved = build_context(spec, repo_root)

    assert resolved.context["psalmi"][1]["verses"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Notenschlüssel" in message and "c4" in message for message in warnings)


def test_psalm_incipits_cover_the_whole_psalter(repo_root: Path) -> None:
    """ADR-0010's table: all 150 Vulgate numbers, accented."""
    incipits = psalm_incipits(repo_root)
    assert len(incipits) == 150
    assert incipits[109] == "Dixit Dóminus"


def test_psalm_incipit_keeps_punctuation_the_gabc_cut_lost(repo_root: Path) -> None:
    """Deriving from the verse gabc stopped at the comma and printed a bare
    "Laudáte" for Ps. cxii — the defect Pastor Kraienhorst reported."""
    assert psalm_incipits(repo_root)[112] == "Laudáte, púeri"


def test_ordo_rows_match_the_reviewed_ordo(repo_root: Path) -> None:
    """The Ordo Vesperarum as Pastor Kraienhorst returned it (ADR-0020):
    no row ends on a hanging preposition, the psalm labels come from the
    table, and the hymn shows its whole first metrical line."""
    resolved = build_context(FeastSpec.model_validate(_smoke_data(repo_root)), repo_root)
    psalmi = resolved.context["psalmi"]

    assert [ps["antiphona"]["incipit"] for ps in psalmi] == [
        "Omnes Sancti quanta passi sunt",
        "Cum palma ad regna",
        "Corpora Sanctórum in pace",
        "Mártyres Dómini",
        "Mártyrum chorus",
    ]
    assert [ps["incipit"] for ps in psalmi] == [
        "Dixit Dóminus",
        "Confitébor tibi, Dómine",
        "Beátus vir, qui timet",
        "Laudáte, púeri",
        "Laudáte Dóminum, omnes",
    ]
    assert resolved.context["hymnus"]["incipit"] == "Sanctórum méritis ínclyta gaúdia"
    assert resolved.context["versiculus"]["incipit"] == "Lætámini in Dómino"
    # the one row the spec overrides, because its gabc has no accents (#38)
    assert resolved.context["magnificat"]["antiphona"]["incipit"] == "Laetáre et lauda"


def test_repetitio_never_strands_an_auxiliary(repo_root: Path) -> None:
    """The repeat cue is sung, so a stranded participle matters more there
    than on the Ordo page (ADR-0020)."""
    resolved = build_context(FeastSpec.model_validate(_smoke_data(repo_root)), repo_root)
    assert resolved.context["psalmi"][0]["antiphona"]["repetitio"] == (
        "Omnes Sancti quanta passi sunt"
    )


def test_incipit_override_wins_over_derivation(repo_root: Path) -> None:
    """The heuristic is a default, not an authority (ADR-0020)."""
    data = _smoke_data(repo_root)
    data["antiphonae"][0]["incipit"] = "Omnes Sancti"
    data["hymnus"]["incipit"] = "Sanctórum méritis"
    data["versiculus"]["incipit"] = "Lætámini"
    data["magnificat"]["antiphona"]["incipit"] = "Laetáre"
    resolved = build_context(FeastSpec.model_validate(data), repo_root)
    assert resolved.context["psalmi"][0]["antiphona"]["incipit"] == "Omnes Sancti"
    assert resolved.context["hymnus"]["incipit"] == "Sanctórum méritis"
    assert resolved.context["versiculus"]["incipit"] == "Lætámini"
    assert resolved.context["magnificat"]["antiphona"]["incipit"] == "Laetáre"


def test_responsorium_incipit_override(repo_root: Path) -> None:
    """The fifth overridable element only exists in the monasticum rite."""
    data = _benedict_data(repo_root)
    data["responsorium"]["incipit"] = "Sancte Pater"
    resolved = build_context(FeastSpec.model_validate(data), repo_root)
    assert resolved.context["responsorium"]["incipit"] == "Sancte Pater"


def test_gappy_psalm_incipit_table_is_reported_in_german(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The table is meant to be hand-corrected, so a number deleted by
    accident must not surface as a bare KeyError.

    The table is a bundled asset (ADR-0024), so a gappy one cannot be faked by
    writing into the working directory — the package is pointed at ``tmp_path``
    instead.
    """
    monkeypatch.setattr("libellus.paths.PACKAGE_ROOT", tmp_path)
    table = tmp_path / PSALM_INCIPITS_FILE
    table.parent.mkdir(parents=True)
    table.write_text(
        'incipits:\n  1: "Beátus vir, qui non ábiit"\n', encoding="utf-8"
    )
    with pytest.raises(FeastFileError) as excinfo:
        psalm_incipits(tmp_path)
    assert "fehlen 149 Psalmen" in excinfo.value.messages[0]


def _latin_only_data(repo_root: Path) -> dict:
    """The Lambert fixture as a Latin-only feast: every `de` stripped out."""
    data = _smoke_data(repo_root)
    data["latin_only"] = True

    def strip(node: object) -> None:
        if isinstance(node, dict):
            node.pop("de", None)
            node.pop("motto_de", None)
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)

    strip(data)
    return data


def test_latin_only_needs_no_psalter(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of the flag (ADR-0025): a fresh install ships no Psalter, so a
    Latin-only feast must resolve without one. Verses still get their notation.

    The Psalter directory is pointed at an empty path — not even the probe is
    reachable — while the pictures still come from the working copy.
    """
    monkeypatch.setattr("libellus.resolve.PSALTER_DIR", tmp_path / "kein-psalter")
    spec = FeastSpec.model_validate(_latin_only_data(repo_root))
    resolved = build_context(spec, repo_root)

    psalmi = resolved.context["psalmi"]
    assert len(psalmi) == 5
    for psalm in psalmi:
        assert psalm["verses"], "every psalm keeps its notation"
        assert all(verse["gabc"] for verse in psalm["verses"])
        assert all(verse["de"] == "" for verse in psalm["verses"])
    assert resolved.context["latin_only"] is True


def test_a_missing_translation_is_an_error_unless_latin_only(repo_root: Path) -> None:
    """`de` is optional in the schema only so that Latin-only specs may omit it;
    for every other feast it is required, and all of them are named at once."""
    data = _latin_only_data(repo_root)
    del data["latin_only"]
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    message = str(excinfo.value)
    assert "latin_only" in message
    for expected in ("Antiphon 1", "Hymnus", "Versiculus", "Oratio", "Capitulum"):
        assert expected in message


def test_latin_only_renders_no_german_but_keeps_the_rubrics(repo_root: Path) -> None:
    """German rubrics name the parts of the office; they translate nothing and
    stay. Everything that is a translation goes."""
    spec = FeastSpec.model_validate(_latin_only_data(repo_root))
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    body = tex.split("\\begin{document}", 1)[1]
    assert "\\pstrans{" not in body  # the macro is still defined in the preamble
    assert "Probevers" not in tex
    assert "Lasset uns beten" not in tex
    # the rubrics, and the Latin itself, are untouched
    assert "\\stagenote{Schola}{Man steht}" in tex
    assert "\\gregorioscore{chant/psalmi/109/toni/8g/v01}" in tex


def test_psalter_de_list_resolves_each_item_to_the_first_that_has_it(
    repo_root: Path,
) -> None:
    """ADR-0041: `psalter_de` may name several translations in order, because a
    translation can be incomplete. Bremen's eu1980 has all 150 psalms and no
    Magnificat, so St. Lambert names both and takes one from each."""
    spec = FeastSpec.model_validate(_smoke_data(repo_root))
    assert spec.psalter_de == ["eu1980", "eu2016"]
    resolved = build_context(spec, repo_root)

    for psalm in resolved.context["psalmi"]:
        assert psalm["verses"][0]["de"].startswith("Probevers")
    assert resolved.context["magnificat"]["verses"][0]["de"].startswith("Vergleichsvers")


def test_psalter_de_naming_nothing_usable_never_falls_back(repo_root: Path) -> None:
    """A feast that names translations gets those and no others. Falling through
    to PSALTER_DE_PREFERENCE would mean editing the default silently
    retranslates a booklet that had already chosen (ADR-0041)."""
    data = _smoke_data(repo_root)
    data["psalter_de"] = ["gibt-es-nicht"]
    spec = FeastSpec.model_validate(data)
    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root)
    message = "\n".join(excinfo.value.messages)
    assert "gibt-es-nicht" in message
    # the probe psalter is right there and is deliberately not substituted
    assert "probe" in message


def test_a_single_name_still_works_and_stays_exact(repo_root: Path) -> None:
    """One name is the ordinary case (the Benedict booklet), and it is not
    widened into a search: eu2016 has what that feast needs."""
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    assert spec.psalter_de == "eu2016"
    resolved = build_context(spec, repo_root)
    for psalm in resolved.context["psalmi"]:
        assert psalm["verses"][0]["de"].startswith("Vergleichsvers")


def test_an_unnamed_feast_prefers_the_public_domain_psalter() -> None:
    """The shipped default is Allioli-Arndt, the only translation a fresh
    install may legally have (ADR-0041). Read from conftest, because the probe
    psalter has already replaced the live constant by the time a test runs."""
    from conftest import REAL_PSALTER_DE_PREFERENCE

    assert REAL_PSALTER_DE_PREFERENCE[0] == "allioli-arndt"
    assert set(REAL_PSALTER_DE_PREFERENCE) >= {"eu1980", "eu2016"}
