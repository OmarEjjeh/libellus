import re
from pathlib import Path
from types import UnionType
from typing import Literal, TypeVar, Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from conftest import requires_toolchain

from libellus.compile import compile_pdf, page_count
from libellus.errors import FeastFileError
from libellus.render import render
from libellus.resolve import build_context, load_spec
from libellus.schema import FeastSpec
from libellus.stage import stage

from helpers import physical


def test_smoke_feast_renders(repo_root: Path, smoke_feast: Path) -> None:
    """The full validate → resolve → render path, without compiling LaTeX."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    assert tex.count("\\begin{document}") == 1
    # 5 antiphon/psalm pairs, preces + pater noster present (hybrid rite)
    assert tex.count("\\antrepeat{") == 6  # 5 psalms + magnificat (usages, not the definition)
    assert "\\section{Preces}" in tex
    assert "\\section{Pater Noster}" in tex
    # Roman Vespers has no Responsorium breve (#30)
    assert "\\section{Responsorium Breve}" not in tex
    # psalm verses come from the shared, cross-feast tone cache (#33)
    assert "\\gregorioscore{chant/psalmi/109/toni/8g/v01}" in tex
    assert "\\pstrans{Probevers 1 — Psalm 109, kein echter Text.}" in tex
    # transfer note from liturgical_date
    assert "translata ex die" in tex
    # capitulum versus list renders as \vers{N} superscripts, space-joined —
    # identical in appearance to the previous inline markup
    assert "\\vers{4} Nec quisquam sumit sibi honórem" in tex
    assert "tamquam Aaron. \\vers{5} Sic et Christus" in tex
    assert "\\vers{4} Und keiner nimmt sich selbst diese Würde" in tex
    assert "so wie Aaron. \\vers{5} So hat auch Christus" in tex
    # literal † and * pause marks in Latin prose render rubric-red, bound
    # to the following word (the \cros/\vc/\rc spacing convention)
    assert "Pontíficis, {\\color{rubricred}†}~tuam nobis" in tex
    assert "justítiam, {\\color{rubricred}*}~et nostrum" in tex
    # the feast's own provenance notes (ADR-0011) print as footnotes
    assert tex.count("\\footnote{") == 5
    assert "\\footnote{Feierliche Melodie aus dem Antiphonale Monasticum" in tex
    # TeX-side ornament padding loop (replaces the old python re-render loop)
    assert "\\newcount\\ornamentfloor" in tex
    # no unrendered Jinja markers left
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex


def test_monasticum_feast_renders(repo_root: Path, benedict_feast: Path) -> None:
    """The monastic skeleton: 4 antiphon/psalm pairs, a Responsorium breve
    between capitulum and hymnus, Preces + sung Pater noster. Section order
    follows vesper.tex, the printed Benedict booklet."""
    spec = load_spec(benedict_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    assert spec.rite == "monasticum"
    assert tex.count("\\antrepeat{") == 5  # 4 psalms + magnificat
    assert "\\section{Preces}" in tex
    assert "\\section{Pater Noster}" in tex
    assert tex.index("\\section{Capitulum}") < tex.index("\\section{Responsorium Breve}")
    assert tex.index("\\section{Responsorium Breve}") < tex.index("\\section{Hymnus}")
    assert "\\gregorioscore{chant/resp/sancte-pater-benedicte}" in tex
    assert "Heiliger Vater Benedikt, * bitte für uns." in tex
    # the Resp. Br. row of the generated ordo table is no longer suppressed
    assert "\\textsc{Resp. Br.}" in tex
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex


def test_filler_pages_render_with_their_styling(repo_root: Path, benedict_feast: Path) -> None:
    """Structured filler pages (plain text in, styling from the partial):
    small-caps title, red block headings, flush-right citation, image +
    caption. The three pages this produces reproduce the printed booklet's
    pp. 33-35 — text extraction is byte-identical on the first two, and the
    third differs only in small-caps flattening (see ADR-0018)."""
    spec = load_spec(benedict_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    assert "{\\large\\scshape Der heilige Vater Benedikt}" in tex
    assert "{\\normalsize\\itshape aus Dom Prosper Guérangers »Kirchenjahr«}" in tex
    assert "{\\small\\itshape\\color{rubricred} Vater Europas\\par}" in tex
    assert "Benedikt ist der geistige Vater Europas" in tex
    assert "{\\scriptsize\\itshape Dom Prosper Guéranger, Das Kirchenjahr" in tex
    # the second page's subtitle is two lines; |breaks turns the newline into \\
    assert "aus dem zweiten Buch der Dialoge\\\\\nGregors des Großen" in tex
    assert "\\includegraphics[width=0.72\\textwidth]{images/02-benedict/medal-print.png}" in tex
    assert "Die Benediktusmedaille (Jubiläumsprägung, Montecassino 1880)" in tex
    # a \newpage between pages, none before the first (the partial's \clearpage
    # already opened one) — a stray leading break would shift the mod-4 count
    filler_region = tex[tex.index("%  FILLER") : tex.index("\\newcount\\ornamentfloor")]
    breaks = [line for line in filler_region.splitlines() if line.strip() == "\\newpage"]
    assert len(breaks) == 1
    # no trailing \null: on a brim-full page it spills and costs a blank page
    assert "\\vspace{0.3em}\\null" not in filler_region


def test_filler_absent_leaves_only_the_padding_loop(repo_root: Path, smoke_feast: Path) -> None:
    """Lambert sets `filler: []` — no filler content, but the ÷4 ornament
    padding loop still runs."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    assert "\\newcount\\ornamentfloor" in tex
    assert "\\scshape" in tex  # cover still uses it — sanity that we test the right thing
    assert "\\pgfornament[width=3cm,color=rubricred]{84}" not in tex  # filler-only rule


def test_back_cover_motto_and_credit_render(repo_root: Path, benedict_feast: Path) -> None:
    """Back cover: quote newlines become line breaks; motto red italic,
    citation italic, credit tiny italic. Rides the Benedict fixture — the
    only one carrying a motto and a multi-line quote."""
    spec = load_spec(benedict_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    assert "signus,\\\\\nrelictis omnibus" in tex
    assert "{\\color{rubricred}\\textit{Ergo nihil operi Dei præponatur.}}" in tex
    assert "{\\color{rubricred}\\textit{Dem Werk Gottes also soll nichts vorgezogen werden.}}" in tex
    assert "\\textit{Regula Benedicti, cap. XLIII}" in tex
    assert "{\\tiny\\textit{Imago: Saint Benedict of Nursia" in tex


def test_back_cover_free_text_renders(repo_root: Path, smoke_feast: Path) -> None:
    spec = load_spec(smoke_feast)
    back_cover = spec.back_cover.model_copy(
        update={"quote": None, "text": "Freier Text\nüber zwei Zeilen."}
    )
    spec = spec.model_copy(update={"back_cover": back_cover})
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "Freier Text\\\\\nüber zwei Zeilen." in tex


def test_back_cover_border_none_renders_plain_image(repo_root: Path, smoke_feast: Path) -> None:
    """The "none" style keeps the bare \\includegraphics, no frame (ADR-0013)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={"back_cover": spec.back_cover.model_copy(update={"border": "none"})}
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "\\framedimage{" not in tex
    assert "\\goldframedimage{" not in tex
    assert "\\includegraphics[width=0.9\\textwidth,height=0.6\\textheight,keepaspectratio]" in tex


@pytest.mark.parametrize(
    ("size", "thickness"),
    [("normal", "1.0cm"), ("large", "1.6cm"), ("extra-large", "2.2cm")],
)
def test_back_cover_gilded_border_size_sets_thickness(
    repo_root: Path, smoke_feast: Path, size: str, thickness: str
) -> None:
    """`border_size` selects the gilded frame's thickness (ADR-0014); the
    size names describe how they look (normal/large/extra-large)."""
    spec = load_spec(smoke_feast)
    back_cover = spec.back_cover.model_copy(update={"border": "gilded", "border_size": size})
    spec = spec.model_copy(update={"back_cover": back_cover})
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert f"\\goldframedimage{{{thickness}}}{{" in tex


@pytest.mark.parametrize(
    ("style", "corner", "line", "shrink"),
    [
        ("vine", "61", "87", "1.8cm"),
        ("grapevine", "63", "87", "1.8cm"),
        ("knot", "41", "89", "1.4cm"),
        ("feather", "131", "80", "1.4cm"),
    ],
)
def test_back_cover_border_style_wraps_image_in_frame(
    repo_root: Path, smoke_feast: Path, style: str, corner: str, line: str, shrink: str
) -> None:
    """Each named border style wraps the image in \\framedimage with its
    corner+line ornament pair (ADR-0013); the image height is shrunk by
    2x the frame's margin so the framed picture still fits the page (a
    naive unshrunk height reproduces the old back-cover blank-page bug)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={"back_cover": spec.back_cover.model_copy(update={"border": style})}
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert f"\\framedimage{{{corner}}}{{{line}}}" in tex
    # the image itself is still rendered, nested inside the frame macro call,
    # with its height shrunk to leave room for the frame's margin
    assert (
        f"\\includegraphics[width=0.9\\textwidth,"
        f"height=\\dimexpr0.6\\textheight-{shrink}\\relax,keepaspectratio]"
    ) in tex


def test_back_cover_no_note_keeps_the_plain_image_height(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Unchanged baseline: with no note, the "none"-border image height
    stays the plain `0.6\\textheight` (no \\dimexpr wrapper at all)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(update={"back_cover": spec.back_cover.model_copy(update={"border": "none"})})
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "height=0.6\\textheight,keepaspectratio]" in tex


def test_back_cover_note_reserves_height_on_the_image(repo_root: Path, smoke_feast: Path) -> None:
    """A back-cover note (ADR-0011) adds a footnote line below the quote —
    the image height must shrink to leave room for it, or the extra
    content silently overflows the fixed-height back cover onto a second
    page (breaking filler.tex.j2's mod-4 page-count invariant, which only
    accounts for content before this partial)."""
    spec = load_spec(smoke_feast)
    quote = spec.back_cover.quote
    assert quote is not None
    spec = spec.model_copy(
        update={
            "back_cover": spec.back_cover.model_copy(
                update={"border": "none", "quote": quote.model_copy(update={"note": "Herkunft"})}
            )
        }
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert (
        "\\includegraphics[width=0.9\\textwidth,"
        "height=\\dimexpr0.6\\textheight-1.2cm\\relax,keepaspectratio]"
    ) in tex


def test_back_cover_note_reserves_height_on_gilded_border(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Same reservation, but combined with the (default) gilded border's
    own thickness-based shrink (ADR-0014)."""
    spec = load_spec(smoke_feast)
    quote = spec.back_cover.quote
    assert quote is not None
    spec = spec.model_copy(
        update={
            "back_cover": spec.back_cover.model_copy(
                update={"quote": quote.model_copy(update={"note": "Herkunft"})}
            )
        }
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert (
        "\\goldframedimage{1.0cm}{\\includegraphics[width=0.9\\textwidth,"
        "height=\\dimexpr0.6\\textheight-1.0cm*2-1.2cm\\relax,keepaspectratio]"
    ) in tex


def test_back_cover_note_uses_savenotes_to_share_the_page_footnote_sequence(
    repo_root: Path, smoke_feast: Path,
) -> None:
    """A \\footnote inside the back cover's minipage would otherwise get its
    own separate, letter-numbered mpfootnote counter instead of continuing
    the document's ordinary numbered page-bottom footnote sequence — the
    footnote package's \\savenotes/\\spewnotes fixes that (see backcover.tex.j2)."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "\\usepackage{footnote}" in tex
    assert "\\savenotes" in tex and "\\spewnotes" in tex


def test_text_fields_are_pure_plain_text(repo_root: Path, smoke_feast: Path, tmp_path: Path) -> None:
    """Hostile input in several kinds of text field reaches the staged output
    as literal glyphs (ADR-0002)."""
    spec = load_spec(smoke_feast)
    hostile = r"Backslash \ Klammern {} Tilde ~ Und & Prozent % Raute # Dollar $ Strich _ Dach ^"
    spec = spec.model_copy(
        update={
            "subtitle": hostile,  # cover
            "antiphonae": [
                spec.antiphonae[0].model_copy(update={"de": hostile}),
                *spec.antiphonae[1:],
            ],
            "oratio": spec.oratio.model_copy(update={"text": hostile}),  # |tex|pausemarks
            "back_cover": spec.back_cover.model_copy(update={"credit": hostile}),
        }
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    build_dir = stage(tex, resolved.assets, "hostile", repo_root, tmp_path / "hostile")
    staged = (build_dir / "hostile.tex").read_text(encoding="utf-8")
    escaped = (
        "Backslash \\textbackslash{} Klammern \\{\\} Tilde \\textasciitilde{} "
        "Und \\& Prozent \\% Raute \\# Dollar \\$ Strich \\_ Dach \\textasciicircum{}"
    )
    assert staged.count(escaped) == 4


def test_german_prose_keeps_plain_asterisks(repo_root: Path, smoke_feast: Path) -> None:
    """|pausemarks styles literal †/* red only in Latin prose, never in German."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={"oratio": spec.oratio.model_copy(update={"de": "Erfülle uns, * deine Diener."})}
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    # if |pausemarks had applied, this would instead read
    # "Erfülle uns, {\color{rubricred}*}~deine Diener."
    assert "Erfülle uns, * deine Diener." in tex


def test_versicle_marks_bind_to_following_word(repo_root: Path, smoke_feast: Path) -> None:
    """Authors type plain \"℣. Text\"; the filter binds the mark with a nbsp."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "℣.~Freuet euch im Herrn" in tex  # versiculus.de, plain in the YAML
    assert "℣.~O Gott, komm mir zu Hilfe. ℟.~Herr, eile mir zu helfen" in tex  # ordinarium


def test_romanum_1962_omits_preces(repo_root: Path, smoke_feast: Path) -> None:
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(update={"rite": "romanum-1962"})
    resolved = build_context(spec, repo_root)
    tex = render("romanum-1962", resolved.context, repo_root)
    assert "\\section{Preces}" not in tex
    assert "\\section{Pater Noster}" not in tex


def test_default_rank_shows_vesperae_qualifier(repo_root: Path, smoke_feast: Path) -> None:
    """Non-Simplex ranks keep the existing "Primae/Secundae in Festo" line,
    and the running header keeps the raw I/II qualifier."""
    spec = load_spec(smoke_feast)
    assert spec.rank == "Semiduplex"
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "Semiduplex" in tex
    assert "Primæ in Festo" in tex
    assert "Ad Vesperas I}" in tex


def test_footnotes_absent_by_default(repo_root: Path, benedict_feast: Path) -> None:
    """No `note` set anywhere in the smoke fixture → no \\footnote in the output."""
    spec = load_spec(benedict_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "\\footnote{" not in tex


def test_provenance_notes_render_as_footnotes(repo_root: Path, benedict_feast: Path) -> None:
    """Notable (ADR-0011): an optional note on any of the content-bearing
    proper models becomes a numbered \\footnote at the point of use."""
    spec = load_spec(benedict_feast)
    assert spec.back_cover.quote is not None
    assert spec.responsorium is not None  # monasticum: the one rite that has one
    spec = spec.model_copy(
        update={
            "antiphonae": [
                spec.antiphonae[0].model_copy(update={"note": "Antiphon-Herkunft"}),
                *spec.antiphonae[1:],
            ],
            "capitulum": spec.capitulum.model_copy(
                update={
                    "versus": [
                        spec.capitulum.versus[0].model_copy(update={"note": "Vers-Herkunft"}),
                        *spec.capitulum.versus[1:],
                    ],
                }
            ),
            "responsorium": spec.responsorium.model_copy(
                update={"note": "Responsorium-Herkunft"}
            ),
            "hymnus": spec.hymnus.model_copy(update={"note": "Hymnus-Herkunft"}),
            "versiculus": spec.versiculus.model_copy(update={"note": "Versiculus-Herkunft"}),
            "magnificat": spec.magnificat.model_copy(
                update={
                    "antiphona": spec.magnificat.antiphona.model_copy(
                        update={"note": "Magnificat-Herkunft"}
                    ),
                }
            ),
            "oratio": spec.oratio.model_copy(update={"note": "Oratio-Herkunft"}),
            "back_cover": spec.back_cover.model_copy(
                update={
                    "quote": spec.back_cover.quote.model_copy(update={"note": "Zitat-Herkunft"}),
                }
            ),
        }
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    notes = [
        "Antiphon-Herkunft", "Vers-Herkunft", "Responsorium-Herkunft",
        "Hymnus-Herkunft", "Versiculus-Herkunft", "Magnificat-Herkunft",
        "Oratio-Herkunft", "Zitat-Herkunft",
    ]
    for note in notes:
        assert f"\\footnote{{{note}}}" in tex
    assert tex.count("\\footnote{") == len(notes)


def test_simplex_rank_omits_vesperae_qualifier(repo_root: Path, smoke_feast: Path) -> None:
    """A Simplex feast has exactly one Vespers — no Primae/Secundae
    distinction, on the cover or in the running header (ADR-0015 update,
    2026-07-25: `vesperae` is `None` here, not just unused)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(update={"rank": "Simplex", "vesperae": None})
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    assert "Simplex" in tex
    assert "Primæ in Festo" not in tex
    assert "Secundæ in Festo" not in tex
    assert "\\itshape in Festo" in tex  # unqualified — no Primae/Secundae distinction
    assert "\\textit{Vesperæ}" in tex  # the bare title itself still renders
    assert "Ad Vesperas}" in tex  # running header: bare, no I/II
    assert "Ad Vesperas I" not in tex
    assert "Ad Vesperas II" not in tex


def test_draft_marks_render_in_the_background_layer(
    repo_root: Path, smoke_feast: Path
) -> None:
    """A draft build (ADR-0021): the Latin diagonal and the dated line, both
    drawn in shipout/background so they cannot reflow a single line."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root, "Entwurf vom 30. Juli 2026, 14:32 Uhr")
    tex = render(spec.rite, resolved.context, repo_root)

    assert "\\SetWatermarkText{PRO MANUSCRIPTO}" in tex
    assert "\\usepackage{draftwatermark}" in tex
    # the dated line is a background picture, not a fancyhdr footer: a footer
    # would vanish on the cover (\thispagestyle{empty}) and the filler pages
    assert "\\AddToShipoutPictureBG{" in tex
    assert "Entwurf vom 30. Juli 2026, 14:32 Uhr" in tex
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex


def test_compact_notates_only_the_first_verse_of_each_psalm(
    repo_root: Path, smoke_feast: Path
) -> None:
    """A Kurzfassung (ADR-0022): one score per psalm and per Magnificat, every
    later verse as pointed text. The reader is a competent singer who knows
    that verses after the first begin on the tenor."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root, compact=True)
    tex = render(spec.rite, resolved.context, repo_root)

    # 5 psalms + Magnificat + 5 antiphons + Ant. ad Magnificat + hymn +
    # versicle + the ordinarium's own chants — but only ONE score per psalm
    for number in (109, 110, 111, 112, 116):
        assert tex.count(f"\\gregorioscore{{chant/psalmi/{number}/toni/") == 1
    # the Magnificat is the exception: its two first verses share one system
    # (below), so no per-verse score of its own appears at all
    assert tex.count("\\gregorioscore{chant/magnificat/toni/") == 0
    # every remaining verse is a \textvers, and its German keeps the
    # interlinear \pstrans style
    # verse 1 of Ps. cix is the score; verse 2 is the first text verse, and it
    # keeps the pointing the tone engine wrote plus the red mediant
    assert (
        "\\textvers{2}{Donec ponam inimícos \\textbf{tu}os, {\\color{rubricred}*}\\\\\n"
        "scabéllum pe\\textit{dum} \\textit{tu}\\textbf{ó}rum.}"
    ) in tex
    assert "\\textvers{12}{Sicut erat in princípio" in tex  # Magnificat doxology
    # the German of a text verse is the macro's third argument, and the macro
    # hands it to \pstrans — a text verse keeps the interlinear psalm font
    assert "{Probevers 2 — Psalm 109, kein echter Text.}" in tex
    assert "\\pstrans{#3}" in tex
    # the notated first verse still carries its German the direct way
    assert "\\pstrans{Probevers 1 — Psalm 109, kein echter Text.}" in tex
    assert "\\VAR{" not in tex and "\\BLOCK{" not in tex


def test_compact_magnificat_puts_its_first_two_verses_on_one_system(
    repo_root: Path, smoke_feast: Path
) -> None:
    """„Magníficat" is one word and cannot carry the mediant cadence, so a
    notated verse 1 alone would show a melody no other verse follows. Both
    verses share one system instead, as the Liber prints this canticle: verse 2
    beneath verse 1, the reciting notes hollow, and the notes verse 1 never
    reaches standing there with no words under them (ADR-0022)."""
    spec = load_spec(smoke_feast)
    assert spec.magnificat.tonus == "6F"
    resolved = build_context(spec, repo_root, compact=True)
    tex = render(spec.rite, resolved.context, repo_root)

    assert "\\gregorioscore{chant/magnificat/kurzfassung/6f}" in tex
    assert Path("chant/magnificat/kurzfassung/6f.gabc") in resolved.assets
    # Both German lines, numbered like the two text lines of the system. The
    # wording is the eu2016 stand-in's ("Vergleichsvers"), not the probe's:
    # Lambert names `psalter_de: [eu1980, eu2016]` and eu1980 has no Magnificat,
    # so this canticle resolves to the second translation named while the psalms
    # above it resolve to the first (ADR-0041).
    assert "\\pstrans{1. Vergleichsvers 1 — Magnificat" in tex
    assert "\\pstrans{2. Vergleichsvers 2 — Magnificat" in tex
    # verses 1 and 2 are in the system, so the text verses start at 3
    assert "\\textvers{3}{" in tex
    assert "\\textvers{1}{" not in tex and "\\textvers{2}{Et exsultávit" not in tex
    # the second text line is sung Latin, so it is set upright rather than in
    # gregorio's italic translation style
    assert "\\grechangestyle{translation}{}" in tex
    # and gregorio's zero-width translation box is patched to reserve the width
    # it needs, or the line beneath prints into its neighbour in every tone
    assert "\\def\\GreWriteTranslation#1{" in tex
    assert "\\kern\\dimexpr\\wd\\gretransbox-\\wd\\gre@box@syllabletext\\relax" in tex


def test_compact_magnificat_system_follows_the_mediatio(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Same tone label, different melody, so a system of its own — the file name
    is the cache folder, which carries the mediation (ADR-0043)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={
            "magnificat": spec.magnificat.model_copy(update={"mediatio": "ut-in-tono-i"})
        }
    )
    resolved = build_context(spec, repo_root, compact=True)
    tex = render(spec.rite, resolved.context, repo_root)

    assert "\\gregorioscore{chant/magnificat/kurzfassung/6f-ut-in-tono-i}" in tex
    assert Path("chant/magnificat/kurzfassung/6f-ut-in-tono-i.gabc") in resolved.assets
    assert Path("chant/magnificat/kurzfassung/6f.gabc") not in resolved.assets


def test_compact_magnificat_notates_both_verses_when_the_tone_has_no_system(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Tone 8G sings the Magnificat's first verse to its own solemn formula
    („Ma(g)gní(hg)fi(gj jr)cat(j.)" against „Et(g) ex(h)sul(j)…"), so the two
    verses have different melodies and no single system can carry both. Then
    both are notated in full instead — the defect is fixed either way."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={"magnificat": spec.magnificat.model_copy(update={"tonus": "8G"})}
    )
    resolved = build_context(spec, repo_root, compact=True)
    tex = render(spec.rite, resolved.context, repo_root)

    assert not any(
        path.as_posix().startswith("chant/magnificat/kurzfassung") for path in resolved.assets
    )
    assert tex.count("\\gregorioscore{chant/magnificat/toni/8g/") == 2
    assert "\\textvers{3}{" in tex


def test_compact_marks_itself_on_the_cover_and_in_the_instructions(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Otherwise the two PDFs differ only from the first psalm onwards, and
    whoever hands out booklets has only the thickness to go by."""
    spec = load_spec(smoke_feast)
    tex = render(
        spec.rite, build_context(spec, repo_root, compact=True).context, repo_root
    )

    assert "Editio brevior" in tex
    assert "Nur der erste Vers ist in Noten gesetzt" in tex


def test_compact_notates_one_hymn_stanza_and_sets_the_rest_as_text(
    repo_root: Path, smoke_feast: Path
) -> None:
    """The hymn's six notated stanzas become one score plus five stanzas of
    Latin with their German — the second-largest block in the booklet."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root, compact=True)
    tex = render(spec.rite, resolved.context, repo_root)

    # the score is a materialized copy, so the hymn's own file is untouched
    assert "\\gregorioscore{chant/inline/hymnus-kurzfassung}" in tex
    assert "\\gregorioscore{chant/hymni/sanctorum-meritis}" not in tex
    staged = (physical("chant/inline/hymnus-kurzfassung.gabc")).read_text(encoding="utf-8")
    assert staged.split("%%", 1)[1].count("(::)") == 1
    assert (physical("chant/hymni/sanctorum-meritis.gabc")).read_text(
        encoding="utf-8"
    ).split("%%", 1)[1].count("(::)") == 7  # 6 stanzas + the closing Amen

    assert tex.count("\\textstanza{") == 5  # stanzas 2-6
    assert "\\textstanza{2}{Hi sunt quos fátue mundus abhórruit :" in tex
    # the closing Amen belongs to the last stanza, not to a seventh
    assert "Annórum in sériem canant.\\\\\nAmen." in tex


def test_a_hymn_whose_stanzas_do_not_match_its_german_is_an_error(
    repo_root: Path, smoke_feast: Path
) -> None:
    """A silent fall back to the fully notated hymn would hand back a
    Kurzfassung that isn't one; the mismatch also means the stanza numbering
    in the ordinary booklet is already wrong (ADR-0022)."""
    spec = load_spec(smoke_feast)
    spec = spec.model_copy(
        update={"hymnus": spec.hymnus.model_copy(update={"de": ["Nur eine Strophe."]})}
    )

    with pytest.raises(FeastFileError) as excinfo:
        build_context(spec, repo_root, compact=True)

    message = "\n".join(excinfo.value.messages)
    assert "6 Strophe(n)" in message and "1" in message
    # and without --compact the very same spec still builds: the full booklet
    # never needed the stanza texts to line up with the score
    render(spec.rite, build_context(spec, repo_root).context, repo_root)


def test_a_full_build_has_no_trace_of_the_compact_layout(
    repo_root: Path, smoke_feast: Path
) -> None:
    """The default booklet is unchanged — no text verses, no cover line."""
    spec = load_spec(smoke_feast)
    tex = render(spec.rite, build_context(spec, repo_root).context, repo_root)

    assert "\\textvers{" not in tex
    assert "\\textstanza{" not in tex
    assert "Editio brevior" not in tex
    assert "Nur der erste Vers" not in tex
    assert tex.count("\\gregorioscore{chant/psalmi/109/toni/") > 1


def test_final_build_has_no_trace_of_the_draft_marks(
    repo_root: Path, smoke_feast: Path
) -> None:
    """Without a stamp nothing is emitted at all — no package, no TeX-level
    flag that could be flipped by accident."""
    spec = load_spec(smoke_feast)
    tex = render(spec.rite, build_context(spec, repo_root).context, repo_root)

    assert "draftwatermark" not in tex
    assert "PRO MANUSCRIPTO" not in tex
    assert "Entwurf" not in tex
    assert "\\AddToShipoutPictureBG{" not in tex


# ============================================================
#  The escaping audit (#42)
# ============================================================

#: Every `\VAR{}` site in `template/` whose value is interpolated raw, keyed by
#: the Jinja expression and mapped to the reason it may be.
#:
#: Escaping is not a default that could simply be turned on. A path has to
#: reach `\includegraphics`/`\input`/`\gregorioscore` unescaped or the file is
#: not found — `\includegraphics{a\_b.png}` looks for a file that does not
#: exist — and a TeX length has to stay a length. So the ones that carry an
#: author's *words* are escaped, the rest are pinned here, and a new raw site
#: fails this test until somebody says which it is.
#:
#: ADR-0027 decision 3 retires the convention altogether by moving escaping
#: into a branded `Tex` type. Until that port lands, this inventory is the net.
_SCORE = "path: \\gregorioscore, character-checked by the schema (ADR-0033)"
_PICTURE = "path: \\includegraphics or \\input, character-checked (ADR-0033)"
_LENGTH = "a TeX length or pgfornament number from the partial's own table"
_COUNTED = "a number the pipeline counted; no author ever types it"
_COMPOSED = "Latin the pipeline composed from the date or from a Literal field"

RAW_INTERPOLATIONS: dict[str, str] = {
    "bmv.gabc": _SCORE,
    "hymnus.gabc": _SCORE,
    "magnificat.antiphona.gabc": _SCORE,
    "magnificat.system": _SCORE,
    "ps.antiphona.gabc": _SCORE,
    "responsorium.gabc": _SCORE,
    "verse.gabc": _SCORE,
    "versiculus.gabc": _SCORE,
    "ordinarium['amen'].gabc": _SCORE,
    "ordinarium['benedicamus-domino'].gabc": _SCORE,
    "ordinarium['deo-gratias'].gabc": _SCORE,
    "ordinarium['fidelium-animae'].gabc": _SCORE,
    "ordinarium['incipit'].gabc": _SCORE,
    "ordinarium['kyrie-eleison'].gabc": _SCORE,
    "ordinarium['paternoster'].gabc": _SCORE,
    "ordinarium['te-rogamus'].gabc": _SCORE,
    "ordinarium['versicle-domine-exaudi'].gabc": _SCORE,
    "back_cover_image": _PICTURE,
    "drollery": _PICTURE,
    "page.image": _PICTURE,
    "page.path": _PICTURE,
    "corner": _LENGTH,
    "line": _LENGTH,
    "margin": _LENGTH,
    "shrink": _LENGTH,
    "note_reserve": _LENGTH,
    "gilded_thickness": _LENGTH,
    "loop.index": _COUNTED,
    "loop.index + 1": _COUNTED,
    "ps.index_roman": _COUNTED,
    "ps.number_roman": _COUNTED,
    "ps.number_roman|upper": _COUNTED,
    "v.n": _COUNTED,
    "verse.number": _COUNTED,
    "date_latin": _COMPOSED,
    "feast.vesperae": _COMPOSED,
    "translata_note": _COMPOSED,
    "vesperae_label": _COMPOSED,
}

#: Filters that mark a value as already-LaTeX. `pointing` is the empirical
#: proof of ADR-0027's branded type: it emits \textbf/\textit around text it
#: escaped itself, so escaping it again would print the markup.
_ESCAPING_FILTERS = {"tex", "pointing"}


def _interpolations(repo_root: Path) -> list[tuple[str, str, int]]:
    """Every `\\VAR{expr}` in the templates as (expression, file, line).

    Brace-counted rather than regex-matched: the delimiters are `\\VAR{`/`}`
    (render.make_environment), and several sites hold a subscript, so a
    non-greedy `.*?` would cut `ordinarium['amen'].gabc` short at the `]`.
    """
    sites: list[tuple[str, str, int]] = []
    for template in sorted((repo_root / "src/libellus/template").rglob("*.j2")):
        text = template.read_text(encoding="utf-8")
        name = template.relative_to(repo_root / "src/libellus/template").as_posix()
        for opening in re.finditer(r"\\VAR\{", text):
            cursor, depth = opening.end(), 1
            while depth:
                depth += {"{": 1, "}": -1}.get(text[cursor], 0)
                cursor += 1
            sites.append((text[opening.end() : cursor - 1], name, text.count("\n", 0, opening.start()) + 1))
    return sites


def test_every_unescaped_interpolation_is_a_known_one(repo_root: Path) -> None:
    """The #42 audit, pinned: a `\\VAR{}` added without `|tex` has to be
    classified in RAW_INTERPOLATIONS before this suite goes green again."""
    sites = _interpolations(repo_root)
    assert len(sites) > 100, "the templates were not found"

    unclassified = sorted(
        {
            f"{expression}   ({name}:{line})"
            for expression, name, line in sites
            if not _ESCAPING_FILTERS & {part.strip() for part in expression.split("|")[1:]}
            and expression not in RAW_INTERPOLATIONS
        }
    )
    assert not unclassified, (
        "unescaped interpolation sites nobody has classified — escape them "
        "with |tex, or add them to RAW_INTERPOLATIONS with the reason:\n  "
        + "\n  ".join(unclassified)
    )


def test_the_raw_inventory_has_no_stale_entries(repo_root: Path) -> None:
    """The other direction: an entry that no longer matches a site is
    misleading, because it reads as a hazard that is still there."""
    live = {expression for expression, _, _ in _interpolations(repo_root)}
    assert not sorted(set(RAW_INTERPOLATIONS) - live)


# ============================================================
#  The torture fixture (#42, ADR-0027 decision 6)
# ============================================================

#: Every LaTeX special, in one string an author could plausibly type.
HOSTILE = r"Backslash \ Klammern {} Tilde ~ Und & Prozent % Raute # Dollar $ Strich _ Dach ^"

#: A picture whose name uses every character ADR-0033 allows beyond the
#: alphabet — the underscore above all, which is the one the issue named.
TORTURE_IMAGE = "tests/fixtures/images/Ss_Petri-Pauli.1962.png"

#: String fields that are not prose, and so are not tortured. Everything else
#: holding a str is plain text (ADR-0002) and is replaced wholesale below — so
#: a text field added to the schema is tortured by default, and leaves the
#: torture only by being named here with a reason.
NON_PROSE_FIELDS: dict[str, str] = {
    "gabc": "a .gabc path or an inline block of notation",
    "image": "a path or an embedded data: URI",
    "drollery": "a filename in images/drollery/",
    "antiphona_bmv": "an ordinarium chant name, resolved to a path",
    "psalter_de": "the name of a directory under psalter/",
    "tonus": "a psalm-tone label the tone engine looks up",
    "euouae": "gabc neumes, not words",
}


def _is_prose(model: BaseModel, name: str, value: object) -> bool:
    """Whether a field holds an author's words, and so must survive escaping.

    A Literal field (rite, rank, vesperae, border, …) is a str at runtime but
    a fixed vocabulary the template branches on, so it is read off the
    annotation rather than listed by name — one fewer list to keep current.
    """
    if not isinstance(value, str) or name in NON_PROSE_FIELDS:
        return False
    return not _mentions_literal(type(model).model_fields[name].annotation)


def _mentions_literal(annotation: object) -> bool:
    """Whether an annotation is a Literal, or a union holding one."""
    origin = get_origin(annotation)
    if origin is Literal:
        return True
    if origin in (Union, UnionType):
        return any(_mentions_literal(arm) for arm in get_args(annotation))
    return False


Model = TypeVar("Model", bound=BaseModel)


def _torture(model: Model) -> Model:
    """A copy of ``model`` with every prose field replaced by HOSTILE.

    ``model_copy`` rather than re-validation on purpose: the point is to drive
    hostile text through resolution and rendering, not to re-check the schema.
    """
    updates: dict[str, object] = {}
    for name, value in model:
        if isinstance(value, BaseModel):
            updates[name] = _torture(value)
        elif isinstance(value, list) and value:
            updates[name] = [
                _torture(item)
                if isinstance(item, BaseModel)
                else (HOSTILE if _is_prose(model, name, item) else item)
                for item in value
            ]
        elif _is_prose(model, name, value):
            updates[name] = HOSTILE
    return model.model_copy(update=updates)


def _tortured_spec(smoke_feast: Path) -> FeastSpec:
    """St. Lambert with hostile text everywhere and an awkwardly named picture."""
    spec = _torture(load_spec(smoke_feast))
    return spec.model_copy(
        update={"back_cover": spec.back_cover.model_copy(update={"image": TORTURE_IMAGE})}
    )


def test_every_prose_field_survives_being_hostile(repo_root: Path, smoke_feast: Path) -> None:
    """The test ADR-0002 always asserted and nothing proved: hostile text in
    *every* prose field reaches the TeX as literal glyphs, and the underscore
    in the picture's name reaches \\includegraphics untouched."""
    spec = _tortured_spec(smoke_feast)
    tex = render(spec.rite, build_context(spec, repo_root).context, repo_root)

    escaped = (
        "Backslash \\textbackslash{} Klammern \\{\\} Tilde \\textasciitilde{} "
        "Und \\& Prozent \\% Raute \\# Dollar \\$ Strich \\_ Dach \\textasciicircum{}"
    )
    # every field that renders at all renders escaped, and none renders raw
    assert tex.count(escaped) > 30
    assert HOSTILE not in tex
    # the picture's name is the one thing that must NOT be escaped
    assert f"{{{TORTURE_IMAGE}}}" in tex
    assert "Ss\\_Petri" not in tex


@requires_toolchain
def test_a_hostile_feast_still_compiles(repo_root: Path, smoke_feast: Path, tmp_path: Path) -> None:
    """…and the booklet builds. Escaping that is merely plausible is worth
    little: the only proof that a special character is neutralized is LuaLaTeX
    accepting it, which is what nothing checked before #42."""
    spec = _tortured_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    build_dir = stage(tex, resolved.assets, "torture", repo_root, tmp_path / "torture")

    pdf = compile_pdf(build_dir / "torture.tex")

    assert page_count(pdf) % 4 == 0  # the booklet invariant still holds


def _ordo_page(tex: str) -> str:
    """The rendered Ordo page alone, with its TeX comments stripped.

    The comments have to go: `ordo-table.tex.j2` explains at length why the
    page avoids `\\null\\vfill` and a `minipage`, so it names both, and an
    assertion that they are absent would match the explanation.
    """
    after = tex.split("%  ORDO VESPERARUM", 1)[1]
    start = after.index("\\newpage")
    body = after[start : after.index("% ==", start)]
    return "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("%")
    )


def test_praenotanda_renders_under_the_ordo_table(repo_root: Path, smoke_feast: Path) -> None:
    """The front-matter rubric (ADR-0038) stands between the Ordo table and the
    page's closing ornament, Latin above its German."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    ordo = _ordo_page(tex)
    assert "Antiphonae, Hymnus et Versiculi de Communi" in ordo
    assert "Die Antiphonen, der Hymnus und die Versikel" in ordo
    assert ordo.index("\\end{tabular}") < ordo.index("Antiphonae, Hymnus")
    assert ordo.index("Antiphonae, Hymnus") < ordo.index("Die Antiphonen")
    # Set as paragraphs, never in a box: a minipage here cannot be fitted
    # beside the table and silently splits the page in three.
    assert "minipage" not in ordo and "parbox" not in ordo
    # The page centres inside one \vbox rather than by page glue — the glue
    # forms cost room this page no longer has, or spill onto a blank page.
    assert "\\null\\vfill" not in ordo and "\\vspace*{\\fill}" not in ordo
    assert "\\vbox to \\textheight{\\vfil" in ordo and ordo.count("\\vfil}") == 1


def test_praenotanda_absent_leaves_the_ordo_page_as_it_was(
    repo_root: Path, benedict_feast: Path
) -> None:
    """No rubric set → nothing between table and ornament (ADR-0038)."""
    spec = load_spec(benedict_feast)
    assert spec.praenotanda is None
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    ordo = _ordo_page(tex)
    # the rubric's signature — italic Latin as its own paragraph — never appears
    assert "\\footnotesize\\itshape" not in ordo
    table_end = ordo.index("\\end{tabular}")
    assert "\\pgfornament" in ordo[table_end:]


def test_praenotanda_drops_its_german_when_latin_only(
    repo_root: Path, smoke_feast: Path
) -> None:
    """The rubric follows ADR-0025 like every other text: the Latin stays, the
    German goes."""
    spec = load_spec(smoke_feast)
    assert spec.praenotanda is not None
    spec = spec.model_copy(
        update={
            "latin_only": True,
            "praenotanda": spec.praenotanda.model_copy(update={"de": None}),
        }
    )
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    ordo = _ordo_page(tex)
    assert "Antiphonae, Hymnus et Versiculi de Communi" in ordo
    assert "Die Antiphonen, der Hymnus und die Versikel" not in ordo
