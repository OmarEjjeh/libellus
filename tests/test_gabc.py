import re
import tempfile
from pathlib import Path

from libellus.gabc import (
    build_euouae_gabc,
    chant_name,
    differentia_candidates,
    find_euouae,
    first_stanza_gabc,
    hymn_incipit,
    hymn_stanzas,
    incipit,
    lyrics,
    normalize_euouae,
    pointed_halves,
    read_headers,
)
from libellus.paths import PACKAGE_ROOT
from libellus.psalmtone import euouae_per_tonus, generate_verses

from helpers import physical

#: A psalm verse to parse: engine output for Ps 109 tone 8G v. 1, the golden
#: fixture validated against the hand-transcribed Benedict psalm (see
#: test_resolve.GOLDEN). The hand-split gabc these tests used to read was
#: retired with vesper.tex on 2026-07-28.
PSALM_VERSE = "tests/data/golden/psalm109-8g-v01.gabc"

#: The text of one elision. gabc elisions do not nest, so a non-greedy match is
#: the whole of the parsing needed.
_ELISION = re.compile(r"<e>(.*?)</e>")

#: A gabc comment: ``%`` to end of line. Stripped before the scan below, because
#: sanctorum-meritis.gabc documents the spelling it was fixed away from and a
#: quoted mistake is not one.
_COMMENT = re.compile(r"%.*$", re.MULTILINE)


def test_no_forced_centre_inside_an_elision() -> None:
    """No bundled score puts a forced centre ``{…}`` inside an elision ``<e>…</e>``.

    gregorio rejects that combination ("forced center may not be within an
    elision") but recovers and sets the score anyway, so it exits non-zero
    without failing the build (ADR-0032 decision 4) — which is how one hymn
    shipped with it in every booklet for months (#55). The centre belongs
    around the elision: ``r{<e>u</e>}<e>m</e>``, not ``r<e>{u}m</e>``.
    """
    offenders = [
        str(score.relative_to(PACKAGE_ROOT))
        for score in sorted(PACKAGE_ROOT.rglob("*.gabc"))
        for elision in _ELISION.findall(
            _COMMENT.sub("", score.read_text(encoding="utf-8"))
        )
        if "{" in elision or "}" in elision
    ]
    assert offenders == []


def test_read_headers(repo_root: Path) -> None:
    headers = read_headers(physical("chant/ant/fuit-vir-vitae-venerabilis.gabc"))
    assert headers["name"] == "Fuit vir"
    assert headers["mode"] == "8"


def test_incipit_of_antiphon(repo_root: Path) -> None:
    assert (
        incipit(physical("chant/ant/fuit-vir-vitae-venerabilis.gabc"), 4)
        == "Fuit vir vitæ venerábilis"
    )


def test_incipit_normalizes_dropcap_capitals(repo_root: Path) -> None:
    # GregoBase writes the first syllable in caps for the drop-cap initial
    assert (
        incipit(physical("chant/ant/beatus-vir-benedictus.gabc"), 4)
        == "Beátus vir Benedíctus"
    )
    assert (
        incipit(physical("chant/ant/vir-domini-benedictus.gabc"), 4)
        == "Vir Dómini Benedíctus"
    )


def test_incipit_cuts_at_punctuation(repo_root: Path) -> None:
    # 2 words requested, but the colon after "meo" comes later — verse cut first
    assert incipit(repo_root / PSALM_VERSE, 2) == "Dixit Dóminus"
    # asterisk ends the incipit even when more words were requested
    assert (
        incipit(physical("chant/resp/sancte-pater-benedicte.gabc"), 6)
        == "Sancte Pater Benedícte"
    )


def test_incipit_skips_leading_versicle_marker(repo_root: Path) -> None:
    """A literal ℣./℟. rubric marker (not sung text) must not truncate the
    incipit to just the marker itself (issue #31)."""
    assert (
        incipit(physical("chant/vers/laetamini-in-domino.gabc"), 3)
        == "Lætámini in Dómino"
    )


def test_chant_name_strips_parenthetical(repo_root: Path) -> None:
    assert chant_name(physical("chant/ordinarium/salve-regina-simple.gabc")) == "Salve Regina"


def test_psalm_verse_lyrics_strip_notes_and_number(repo_root: Path) -> None:
    text = lyrics(repo_root / PSALM_VERSE)
    assert text.startswith("Dixit Dóminus")
    assert "(" not in text


def test_lyrics_resolve_gabc_specials(tmp_path: Path) -> None:
    """``<sp>'ae</sp>`` is the character ǽ, not markup, and the forced centre
    around it is notation: the doxology reads "et in sǽcula sæculórum", never
    "et in s{}cula sæculórum" (#38).

    Read from the tone engine rather than from a hand-typed copy of it: the
    spelling under test is the engine's own, and the file the issue names —
    ``chant/psalmi/109/toni/8g/v10.gabc`` — is generated, not tracked
    (ADR-0024), so no corpus guard can watch it.
    """
    _, verses = generate_verses(109, "8G")
    sicut_erat = verses[9]
    assert "s{<sp>'ae</sp>}" in sicut_erat
    path = tmp_path / "v10.gabc"
    path.write_text(sicut_erat, encoding="utf-8")

    assert lyrics(path) == (
        "Sicut erat in princípio, et nunc, et semper, * "
        "et in sǽcula sæculórum. Amen."
    )


def test_no_bundled_score_yields_braces_in_its_lyrics() -> None:
    """The forced centre never reaches the text: no bundled score's ``lyrics()``
    still carries a ``{`` or ``}`` (#38). Guards the corpus, not one file —
    ``Allelú{ia}`` in the ordinarium and ``d{<e>e</e>}`` in the hymn are the
    same bug in two spellings."""
    offenders = [
        str(score.relative_to(PACKAGE_ROOT))
        for score in sorted(PACKAGE_ROOT.rglob("*.gabc"))
        if "{" in lyrics(score) or "}" in lyrics(score)
    ]
    assert offenders == []


def test_find_euouae_reads_tagged_form(repo_root: Path) -> None:
    """GregoBase transcriber Matthias Bry tags the EUOUAE explicitly (#33)."""
    text = (physical("chant/ant/fuit-vir-vitae-venerabilis.gabc")).read_text(encoding="utf-8")
    assert find_euouae(text) == "j j i j h ghg"


def test_find_euouae_reads_tagged_form_with_closing_tag_before_last_note(
    repo_root: Path,
) -> None:
    """St. Lambert's "Omnes sancti quanta passi" closes the ``<eu>`` tag
    right after the last syllable's text, before its note group
    (``e.</eu>(g.)``), unlike the Benedict fixture above where the tag
    closes after the note (``e.(ghg) </eu>``) — both must be read."""
    text = (
        physical("chant/ant/omnes-sancti-quanta-passi.gabc")
    ).read_text(encoding="utf-8")
    assert find_euouae(text) == "j j i j h g."


def test_find_euouae_reads_bare_untagged_form() -> None:
    """Some transcribers (e.g. Benjamin Bloomfield's Solesmes 1934 "Ab
    Oriente") write the same six syllables with no wrapping tag at all."""
    text = (
        "(c3) AB(f) O(d)ri(de)énte(e_f) *(,) venérunt Mági(i.) in(ij) "
        "Béthlehem.(g.) (::) E(h) u(h) o(g) u(h) a(f) e.(e.) (::)"
    )
    assert find_euouae(text) == "h h g h f e."


def test_find_euouae_absent_returns_none(repo_root: Path) -> None:
    """Several St. Lambert antiphons (transcriber Andrew Hinkley) have no
    EUOUAE at all — the case #33's ``euouae:`` field exists for."""
    text = (physical("chant/ant/cum-palma-ad-regna.gabc")).read_text(encoding="utf-8")
    assert find_euouae(text) is None


def test_build_euouae_gabc_splices_neumes_onto_fixed_syllables() -> None:
    """A feast author types only the six neumes (#33) — never the "E u o u
    a e" syllable text, which never varies and gets spliced in here."""
    assert (
        build_euouae_gabc("h h g h f e.")
        == "E(h) u(h) o(g) u(h) a(f) e.(e.)"
    )


def test_build_euouae_gabc_rejects_wrong_token_count() -> None:
    """Anything other than exactly six neumes must not silently produce a
    malformed or partial termination."""
    assert build_euouae_gabc("h h g h f") is None
    assert build_euouae_gabc("das ist keine gültige Notation") is None


def test_build_euouae_gabc_accepts_multi_pitch_neumes_and_mora_dot() -> None:
    """A neume may be more than one pitch letter, and the final one may
    carry a trailing mora (augmentation) dot."""
    assert (
        build_euouae_gabc("h hg ghg h f e.")
        == "E(h) u(hg) o(ghg) u(h) a(f) e.(e.)"
    )


def test_build_euouae_gabc_accepts_a_mora_dot_on_any_pitch_in_a_neume() -> None:
    """A multi-pitch neume can carry a mora dot on more than one of its
    pitches, not only as a single trailing dot on the whole token — e.g.
    "g.f." (a real St. Lambert antiphon 3 termination, issue #33)."""
    assert (
        build_euouae_gabc("h h g f gh g.f.")
        == "E(h) u(h) o(g) u(f) a(gh) e.(g.f.)"
    )


def test_build_euouae_gabc_keeps_compound_neumes_verbatim() -> None:
    """The neumes now come from the engine, which emits compound shapes like
    the climacus "gvFED." for tone 1D — they are spliced through untouched,
    so no pitch-letter syntax check may reject them (#33)."""
    assert (
        build_euouae_gabc("h h g f gh gvFED.")
        == "E(h) u(h) o(g) u(f) a(gh) e.(gvFED.)"
    )


def test_normalize_euouae_ignores_mora_spelling() -> None:
    """jgabc writes two moraed notes "gf.."; hand transcriptions write
    "g.f."; transcribers also drop the final mora entirely. None of that
    distinguishes one ending from another (#33)."""
    assert normalize_euouae("h h g f gh gf..") == normalize_euouae("h h g f gh g.f.")
    assert normalize_euouae("j j h j k j.") == normalize_euouae("j j h j k j")


def test_differentia_candidates_identifies_an_ending(repo_root: Path) -> None:
    """A EUOUAE names its ending uniquely; a EUOUAE differing only in the
    final neume narrows to that ending's neighbourhood instead (#33)."""
    table = euouae_per_tonus()
    exact, _ = differentia_candidates("j j i j h g.", table)
    assert exact == ["8G"]
    # what the Liber Usualis prints for St. Lambert's antiphon 3
    exact, _ = differentia_candidates("h h g f gh g.f.", table)
    assert exact == ["1f"]
    # an ornamented final neume: no exact ending, but the right neighbourhood
    exact, leading = differentia_candidates("j j i j h ghg", table)
    assert exact == [] and leading == ["8G", "8G*"]


def test_incipit_extends_past_a_governing_word(repo_root: Path) -> None:
    """A preposition may not be left hanging at the end (ADR-0020)."""
    assert (
        incipit(physical("chant/ant/cum-palma-ad-regna.gabc"), 3)
        == "Cum palma ad regna"
    )
    assert (
        incipit(physical("chant/ant/corpora-sanctorum-in-pace.gabc"), 3)
        == "Corpora Sanctórum in pace"
    )


def test_incipit_never_strands_a_form_of_esse(repo_root: Path) -> None:
    """``quanta`` governs, so ``passi`` is absorbed — and that leaves
    ``sunt`` next in line, which may not be stranded (ADR-0020). Pastor
    Kraienhorst's cut for St. Lambert's first antiphon."""
    assert (
        incipit(physical("chant/ant/omnes-sancti-quanta-passi.gabc"), 3)
        == "Omnes Sancti quanta passi sunt"
    )


def test_incipit_leaves_a_reading_phrase_alone(repo_root: Path) -> None:
    """Neither rule fires when the cut already reads as a phrase — ``in``
    sits inside these, not at the end."""
    assert (
        incipit(physical("chant/vers/laetamini-in-domino.gabc"), 3)
        == "Lætámini in Dómino"
    )
    assert incipit(physical("chant/ant/martyrum-chorus-laudate.gabc"), 3) == "Mártyrum chorus"


def test_incipit_keeps_an_accent_written_into_the_dropcap(repo_root: Path) -> None:
    """These two transcriptions had no accent at all, so the *sung* antiphon
    printed unaccented too; corrected in the gabc to "MÁrtyres" (2026-07-30,
    ADR-0020). The caps-after-initial convention survives normalization."""
    assert incipit(physical("chant/ant/martyres-domini.gabc"), 4) == "Mártyres Dómini"


def test_hymn_incipit_is_the_first_metrical_line(repo_root: Path) -> None:
    """A hymn's unit is its first verse line, which gabc marks with the
    divisio minor ``(;)`` — no word count is involved (ADR-0020). Both are
    sapphic: the cut falls where the metre falls, and for "Sanctórum
    méritis" no punctuation marks it."""
    assert (
        hymn_incipit(physical("chant/hymni/sanctorum-meritis.gabc"))
        == "Sanctórum méritis ínclyta gaúdia"
    )
    assert (
        hymn_incipit(physical("chant/hymni/gemma-caelestis.gabc"))
        == "Gemma cæléstis pretiósa Regis"
    )


def test_incipit_does_not_pull_a_word_across_a_sense_break() -> None:
    """Punctuation ends the incipit, and neither extension rule may reach
    past it — not the governing-word one, not the *esse* lookahead."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "t.gabc"
        path.write_text(
            "name:T;\n%%\n(c4) Be(d)á(c)tus(d) vir,(f) est(g) Dó(h)mi(g)nus(g.) (::)\n",
            encoding="utf-8",
        )
        assert incipit(path, 3) == "Beátus vir"


def test_hymn_without_a_divisio_minor_falls_back_to_a_word_count() -> None:
    """Not every transcription marks its metrical lines."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "h.gabc"
        path.write_text(
            "name:H;\n%%\n(c3) Gem(e)ma(f) cæ(h)lés(g)tis(e) pre(f)ti(h)ó(g)sa(e) "
            "Re(f)gis(e.) (::)\n",
            encoding="utf-8",
        )
        assert hymn_incipit(path, words=3) == "Gemma cæléstis pretiósa"


def test_pointed_halves_keep_the_pointing_and_break_at_the_mediant(repo_root: Path) -> None:
    """A Kurzfassung verse (ADR-0022) needs what the neumes otherwise say:
    the accented cadence syllables (``<b>``), the preparatory ones (``<i>``)
    and the mediant, which ends the first half-verse it belongs to."""
    assert pointed_halves(repo_root / PSALM_VERSE) == [
        "Dixit Dóminus Dómino <b>me</b>o: *",
        "Sede a <i>dextris</i> <b>me</b>is:",
    ]


def test_pointed_halves_break_at_the_flex_too(repo_root: Path) -> None:
    """A verse long enough to need a flex has three parts, not two — the
    flex ends its own line exactly as the mediant does (Ps. cx, 4)."""
    assert pointed_halves(repo_root / "tests/data/golden/psalm110-3a2-v04.gabc") == [
        "Memóriam fecit mirabílium suórum, †",
        "miséricors et mise<b>rá</b>tor <b>Dómi</b>nus: *",
        "escam dedit ti<i>ménti</i><b>bus</b> se.",
    ]


def test_pointed_halves_resolve_gabc_specials() -> None:
    """``<sp>`` specials and the syllable-grouping braces are notation, not
    text: the Sicut erat verse prints "sæculórum", never "s{}culórum"."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "v10.gabc"
        path.write_text(
            "name:T;\n%%\n(c4) 10. Si(j)cut(j) e(j)rat(j) in(j) prin(j)cí(j)pi(j)o,(j) "
            "et(j) nunc,(j) et(j) <b>sem</b>(k)per,(j.) *(:) et(j) in(j) "
            "s{<sp>'ae</sp>}(j)cu(j)la(j) sæ(j)cu(j)<i>ló</i>(i)<i>rum</i>.(j) "
            "<b>A</b>(h)men.(g.) (::)\n",
            encoding="utf-8",
        )
        assert pointed_halves(path) == [
            "Sicut erat in princípio, et nunc, et <b>sem</b>per, *",
            "et in sǽcula sæcu<i>lórum</i>. <b>A</b>men.",
        ]


def test_hymn_stanzas_are_split_into_metrical_lines(repo_root: Path) -> None:
    """Stanzas end at the double bar, metrical lines at the divisio — the
    same unit ``hymn_incipit`` cuts on (ADR-0020, ADR-0022). The all-caps
    drop-cap syllable of the first stanza is undone as everywhere else."""
    stanzas = hymn_stanzas(physical("chant/hymni/sanctorum-meritis.gabc"))

    assert len(stanzas) == 6
    assert stanzas[0] == [
        "Sanctórum méritis ínclyta gaúdia",
        # the space before the colon is how the score itself is transcribed
        "Pangámus, sócii, géstaque fórtia :",
        "Gliscens fert ánimus prómere cántibus",
        "Victórum genus óptimum.",
    ]
    # the elision markup of stanza 4 is notation too ("cord{<e>e</e>} impávido")
    assert "Sed corde impávido" in stanzas[3][2]
    assert stanzas[5][3] == "Annórum in sériem canant."
    # the closing Amen sits behind its own (::) but is no seventh stanza — it
    # is sung with the doxology and has no German of its own
    assert stanzas[5][4] == "Amen."


def test_first_stanza_gabc_keeps_the_headers_and_one_stanza(repo_root: Path) -> None:
    """The compact hymn prints one score, so the score has to be a
    materialized copy holding only the first stanza (ADR-0022)."""
    truncated = first_stanza_gabc(physical("chant/hymni/sanctorum-meritis.gabc"))

    assert truncated is not None
    assert "name:" in truncated.split("%%")[0]
    body = truncated.split("%%", 1)[1]
    assert body.count("(::)") == 1
    assert "SAn(e)ctó(f')rum(fhhg)" in body
    assert "Hi(e) sunt(f')" not in body
    # the divisio has to stand free of the last note group: written as
    # "mum.(f.)(::)" gregorio takes the syllable to continue and hyphenates it
    assert ")(::)" not in body


def test_first_stanza_gabc_is_none_without_a_stanza_break() -> None:
    """No double bar at all → nothing to truncate, and the caller must not
    guess where a stanza ends."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "h.gabc"
        path.write_text(
            "name:H;\n%%\n(c3) Gem(e)ma(f) cæ(h)lés(g)tis(e)\n", encoding="utf-8"
        )
        assert first_stanza_gabc(path) is None
        assert hymn_stanzas(path) == []
