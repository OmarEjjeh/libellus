"""The form's one testing seam: browser → YAML → libellus validate + stage.

pytest-playwright opens ``form/formular.html`` over ``file://``, fills the
fields as an author would, and feeds the YAML from the live pane back
through libellus validation, resolution, rendering and staging — no unit
seams inside the form (issue #8). Loading existing feast specs (#9), the
data island (#10), the notation preview (#11) and the back-cover image
flow (#12) ride the same seam.
"""

import base64
import json
import re
from pathlib import Path

from playwright.sync_api import Page, expect

from libellus.formdata import embedded_island
from libellus.render import render
from libellus.resolve import build_context, load_spec
from libellus.stage import stage

from helpers import physical

#: The inline-GABC antiphon from the smoke feast spec — pasted into the
#: 5th antiphon field to exercise the path/notation union via the browser.
INLINE_GABC = """\
name:Fuit vir;
office-part:Antiphona;
mode:8;
%%
(c4) Fu(f)it(fg) vir(g) <sp>*</sp>() vi(ji)tæ(h) ve(ij)ne(h)rá(g)bi(fg)lis,(g) (::)"""

#: id → value for every text-like input; selects and buttons are driven
#: separately in the test body.
FIELD_VALUES = {
    "#title": "Sancti Benedicti",
    "#subtitle": "Patroni Europæ",
    "#header": "S. Benedictus, Patronus Europæ",
    "#date": "2026-07-10",
    "#liturgical_date": "2026-07-11",
    "#source": "Antiphonale Monasticum III, Solesmis 2007",
    "#ant-1-gabc": "chant/ant/fuit-vir-vitae-venerabilis.gabc",
    "#ant-1-de": "Fuit vir — Es lebte ein Mann von verehrungswürdigem Lebenswandel.",
    "#ant-1-psalmus": "109",
    "#ant-2-gabc": "chant/ant/beatus-vir-benedictus.gabc",
    "#ant-2-de": "Beátus vir — Der heilige Mann Benedikt.",
    "#ant-2-psalmus": "110",
    "#ant-3-gabc": "chant/ant/gloriosus-confessor-domini.gabc",
    "#ant-3-de": "Glorióssus conféssor — Der glorreiche Bekenner des Herrn.",
    "#ant-3-psalmus": "111",
    "#ant-4-gabc": "chant/ant/vir-domini-benedictus.gabc",
    "#ant-4-de": "Vir Dómini — Der Gottesmann Benedikt.",
    "#ant-4-repetitio": "Vir Dómini",
    "#ant-4-psalmus": "112",
    "#ant-5-gabc": INLINE_GABC,
    "#ant-5-de": "Fuit vir — Testduplikat der ersten Antiphon.",
    "#ant-5-psalmus": "109",
    "#capitulum-ref": "Iesu Sirach 50, 5–10",
    "#versus-1-n": "5",
    "#versus-1-text": "Qui præváluit amplificáre civitátem.",
    "#versus-1-de": "Wie herrlich war er, umgeben vom Volk.",
    "#versus-2-n": "6",
    "#versus-2-text": "Quasi stella matutína in médio nébulæ.",
    "#versus-2-de": "Wie der Morgenstern inmitten von Wolken.",
    # no #responsorium-* here: this composed spec uses romanum-cum-precibus,
    # which has no Responsorium breve (#30) — that fieldset is hidden for it
    "#hymnus-gabc": "chant/hymni/gemma-caelestis.gabc",
    "#stanza-1": "O Benedikt, Schatz des Königs des Himmels.",
    "#stanza-2": "Ehre sei dem Vater und dem Wort, dem Sohn. Amen.",
    "#versiculus-gabc": "chant/vers/amavit-eum-dominus.gabc",
    "#versiculus-de": "℣. Der Herr hat ihn geliebt. ℟. Das Kleid der Herrlichkeit.",
    "#magnificat-gabc": "chant/ant/exsultet-omnium-turba.gabc",
    "#magnificat-de": "Es juble die Schar aller Gläubigen.",
    "#oratio-text": (
        "Deus, qui beatíssimum Confessórem tuum Benedíctum, ómnium justórum "
        "spíritu replére dignátus es: † concéde nobis fámulis tuis; * ut "
        "ejúsdem spíritu repléti, fidéliter adimpleámus."
    ),
    "#oratio-de": "Gott, du hast deinen heiligen Bekenner Benedikt erfüllt.",
    "#antiphona-bmv": "salve-regina-simple",
    "#backcover-image": "images/02-benedict/st-benedict-mary-evans.jpg",
    "#backcover-credit": "Imago: Saint Benedict of Nursia, Mary Evans Picture Library.",
    "#backcover-quote-text": "Ad horam divini officii,\nmox auditus fuerit signus.",
    "#backcover-quote-de": "Zur Stunde des Gottesdienstes,\nsobald das Zeichen gegeben wird.",
    "#backcover-motto": "Ergo nihil operi Dei præponatur.",
    "#backcover-motto-de": "Dem Werk Gottes also soll nichts vorgezogen werden.",
    "#backcover-citation": "Regula Benedicti, cap. XLIII",
    "#drollery": "none",
}


#: field id prefix → psalm tone, chosen through the mode + differentia
#: selectors rather than typed (#33).
TONUS_VALUES = {
    "ant-1-tonus": "8G",
    "ant-2-tonus": "3a2",
    "ant-3-tonus": "8c",
    "ant-4-tonus": "1f",
    "ant-5-tonus": "8G",
    "magnificat-tonus": "1D",
}


def form_url(repo_root: Path) -> str:
    """The form's file:// URL — the way a successor opens it from disk."""
    return (repo_root / "form" / "formular.html").as_uri()


def pick_tonus(page: Page, field: str, tonus: str) -> None:
    """Choose a psalm tone the way the form offers it: mode, then differentia.

    Modes with a single differentia (and peregrinus, which has none) are
    already complete once the mode is picked.
    """
    digits = re.match(r"\d+", tonus)
    modus = tonus if digits is None else digits.group(0)
    page.select_option(f"#{field}-modus", modus)
    # the differentia selector is always present, but disabled when the mode
    # leaves nothing to choose (single-differentia modes, peregrinus)
    if page.locator(f"#{field}-differentia").is_enabled():
        page.select_option(f"#{field}-differentia", tonus)


def test_pick_lists_come_from_the_data_island(page: Page, repo_root: Path) -> None:
    """Tone and ordinarium pick-lists are fed by the embedded island (#10).

    The psalm tone is chosen as mode + differentia (#33), both derived from
    the island's engine-generated tables, never hand-kept in the form."""
    page.goto(form_url(repo_root))

    expect(page.locator("#antiphona-bmv")).to_have_attribute("list", "ordinarium-liste")

    modi = page.eval_on_selector_all(
        "#ant-1-tonus-modus option", "opts => opts.map(o => o.value).filter(Boolean)"
    )
    assert modi == ["1", "2", "3", "4", "5", "6", "7", "8", "peregrinus"]
    expect(page.locator("#magnificat-tonus-modus")).to_be_visible()

    ordinarium = page.eval_on_selector_all(
        "#ordinarium-liste option", "opts => opts.map(o => o.value)"
    )
    assert "salve-regina-simple" in ordinarium


def test_psalm_without_german_verses_warns_while_authoring(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """Choosing a psalm without a German translation warns in German (#10).

    Runs against a doctored island copy (only Ps 109 has German) so the
    test stays valid as the full psalter lands (#14/#15).
    """
    html = (repo_root / "form" / "formular.html").read_text(encoding="utf-8")
    island = json.loads(embedded_island(html))
    island["psalmi_cum_de"] = [109]
    kopie = tmp_path / "formular.html"
    kopie.write_text(
        html.replace(embedded_island(html), json.dumps(island)), encoding="utf-8"
    )
    page.goto(kopie.as_uri())

    page.fill("#ant-1-psalmus", "113")
    warnung = page.locator("#ant-1-psalmus-warnung")
    expect(warnung).to_contain_text("Für Psalm 113")
    expect(warnung).to_contain_text("chant/psalmi/113/")

    page.fill("#ant-1-psalmus", "109")  # has German verses → warning gone
    expect(page.locator("#ant-1-psalmus-warnung")).to_have_count(0)


def test_broken_island_degrades_gracefully(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """A corrupted island leaves pick-lists empty but never breaks the form."""
    html = (repo_root / "form" / "formular.html").read_text(encoding="utf-8")
    broken = html.replace(embedded_island(html), "kaputt {, kein JSON")
    kopie = tmp_path / "formular.html"
    kopie.write_text(broken, encoding="utf-8")

    page.goto(kopie.as_uri())

    # the form still renders and the built-in ordo rule still drives the rows
    expect(page.locator("#title")).to_be_visible()
    expect(page.locator(".antiphona-row")).to_have_count(5)
    page.select_option("#rite", "monasticum")
    expect(page.locator(".antiphona-row")).to_have_count(4)
    # no vocabularies → the tone selector offers only its placeholder, and
    # no false psalm warnings
    expect(page.locator("#ant-1-tonus-modus")).to_be_visible()
    expect(page.locator("#ant-1-tonus-modus option")).to_have_count(1)
    page.fill("#ant-1-psalmus", "113")
    expect(page.locator("#ant-1-psalmus-warnung")).to_have_count(0)


def test_pasted_gabc_renders_notation_preview(page: Page, repo_root: Path) -> None:
    """Pasted GABC draws in-page via the embedded exsurge; paths stay bare (#11)."""
    page.goto(form_url(repo_root))
    expect(page.locator("#ant-1-gabc-vorschau")).to_have_count(0)

    page.fill("#ant-1-gabc", INLINE_GABC)
    expect(page.locator("#ant-1-gabc-vorschau .noten svg").first).to_be_visible()
    expect(page.locator("#ant-1-gabc-vorschau .warnung")).to_have_count(0)

    # a repo path is not previewable (file:// pages cannot read repo files)
    page.fill("#ant-1-gabc", "chant/ant/fuit-vir-vitae-venerabilis.gabc")
    expect(page.locator("#ant-1-gabc-vorschau")).to_have_count(0)


#: An antiphon that fits one chant line at the form's real column width —
#: regression guard: the preview once measured its (hidden) container as
#: 0 px wide, laid the chant out at the 200 px fallback and flowed the
#: resulting line-svgs side by side, so line 2's clef appeared mid-staff.
AB_HOMINIBUS = """\
name:Ab hominibus iniquis;
mode:8;
%%
(c4) AB(g) ho(g)mí(g')ni(g)bus(h') i(h)ní(g)quis(gf) *(,) lí(h)be(j'_)ra(i) me,(j.) Dó(hi)mi(h)ne.(g.) (::)"""


def test_preview_lays_out_at_the_real_container_width(
    page: Page, repo_root: Path
) -> None:
    """A one-line antiphon renders as ONE line — no spurious mid-staff clef."""
    page.goto(form_url(repo_root))
    page.fill("#ant-1-gabc", AB_HOMINIBUS)

    noten = page.locator("#ant-1-gabc-vorschau .noten")
    expect(noten.locator("svg")).to_have_count(1)
    # belt and braces: even a genuinely multi-line chant must stack its
    # line-svgs vertically, never flow them side by side
    display = page.evaluate(
        "getComputedStyle(document.querySelector('#ant-1-gabc-vorschau .noten svg')).display"
    )
    assert display == "block"


def test_unparseable_gabc_warns_in_german_instead_of_blank(
    page: Page, repo_root: Path
) -> None:
    """GABC exsurge cannot draw gets a German message, never a broken form."""
    page.goto(form_url(repo_root))
    page.fill("#ant-1-gabc", "%%\n(c4) te(zzz9%&)xt(!!!)")

    warnung = page.locator("#ant-1-gabc-vorschau .warnung")
    expect(warnung).to_contain_text("kann nicht gezeichnet werden")
    expect(page.locator("#ant-1-gabc-vorschau svg")).to_have_count(0)

    # the form stays fully usable after the failed render
    page.fill("#ant-1-gabc", INLINE_GABC)
    expect(page.locator("#ant-1-gabc-vorschau .noten svg").first).to_be_visible()


def test_gabc_file_pick_embeds_content_inline(
    page: Page, repo_root: Path
) -> None:
    """Picking a .gabc file puts its notation inline into field and YAML (#11)."""
    gabc_file = physical("chant/resp/sancte-pater-benedicte.gabc")
    inhalt = gabc_file.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip()

    page.goto(form_url(repo_root))
    # Responsorium breve only exists for monasticum (#30); the fieldset is
    # hidden for the default rite.
    page.select_option("#rite", "monasticum")
    page.set_input_files("#responsorium-gabc-datei", gabc_file)

    expect(page.locator("#responsorium-gabc")).to_have_value(inhalt)
    expect(page.locator("#responsorium-gabc-vorschau .noten svg").first).to_be_visible()
    # the notation lands inline in the YAML as a literal block, not as a path
    yaml_text = page.locator("#yaml-pane").input_value()
    assert "gabc: |-" in yaml_text
    assert inhalt.splitlines()[0] in yaml_text


def test_gabc_info_popup_opens_and_closes(page: Page, repo_root: Path) -> None:
    """The ℹ️ GABC-basics popup is always visible, opens, and dismisses (#25)."""
    page.goto(form_url(repo_root))

    # visible on an empty field …
    expect(page.locator("#ant-1-gabc-info-link")).to_be_visible()
    # … and stays visible once the field is filled
    page.fill("#ant-1-gabc", "chant/ant/fuit-vir-vitae-venerabilis.gabc")
    expect(page.locator("#ant-1-gabc-info-link")).to_be_visible()

    popup = page.locator("#ant-1-gabc-info")
    expect(popup).to_be_hidden()
    page.click("#ant-1-gabc-info-link")
    expect(popup).to_be_visible()
    reference = popup.locator("a", has_text="vollständige Referenz")
    expect(reference).to_have_attribute(
        "href", "https://gregorio-project.github.io/gabc/index.html"
    )
    expect(reference).to_have_attribute("target", "_blank")

    popup.locator(".schliessen").click()
    expect(popup).to_be_hidden()

    # click outside the popup dismisses it too
    page.click("#ant-1-gabc-info-link")
    expect(popup).to_be_visible()
    page.mouse.click(5, 5)
    expect(popup).to_be_hidden()


def make_image_file(
    page: Page, tmp_path: Path, name: str, width: int, height: int, mime: str
) -> Path:
    """A real image fixture, encoded by the browser itself (no extra deps)."""
    data_url = page.evaluate(
        """([w, h, mime]) => {
          const c = document.createElement("canvas");
          c.width = w; c.height = h;
          const ctx = c.getContext("2d");
          ctx.fillStyle = "#336699"; ctx.fillRect(0, 0, w, h);
          return c.toDataURL(mime);
        }""",
        [width, height, mime],
    )
    header, b64 = data_url.split(",", 1)
    assert mime in header  # the browser really produced the requested format
    file = tmp_path / name
    file.write_bytes(base64.b64decode(b64))
    return file


def test_back_cover_image_pick_names_downloads_and_lands_in_yaml(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """Pick → normalized file + generated path in field, YAML and download (#12)."""
    page.goto(form_url(repo_root))
    page.fill("#title", "Sancti Lamberti")
    page.fill("#date", "2026-09-18")
    bild = make_image_file(page, tmp_path, "scan.png", 1600, 20, "image/png")

    page.set_input_files("#backcover-image-datei", bild)

    expect(page.locator("#backcover-image")).to_have_value(
        "images/2026-09-18-sancti-lamberti.png"
    )
    assert "images/2026-09-18-sancti-lamberti.png" in page.locator(
        "#yaml-pane"
    ).input_value()
    expect(page.locator("#backcover-image-info")).to_contain_text("1600 × 20 px")
    # wide enough, small enough: neither warning nor downscale offer
    expect(page.locator("#backcover-image-aufloesung")).to_have_count(0)
    expect(page.locator("#backcover-image-verkleinern")).to_have_count(0)
    # the German upload instructions accompany the download button
    expect(page.locator("#backcover-image-ergebnis")).to_contain_text("Upload files")

    with page.expect_download() as download_info:
        page.click("#backcover-image-download")
    download = download_info.value
    assert download.suggested_filename == "2026-09-18-sancti-lamberti.png"
    gespeichert = tmp_path / "runter.png"
    download.save_as(gespeichert)
    assert gespeichert.read_bytes().startswith(b"\x89PNG")


def test_hand_typed_path_with_a_special_character_warns(page: Page, repo_root: Path) -> None:
    """The path field is editable, so the ADR-0033 rule is echoed here rather
    than left to surface as a LaTeX failure hours later (#42). A warning, not a
    block: the build is what rejects it, this only says so earlier."""
    page.goto(form_url(repo_root))

    page.fill("#backcover-image", "images/Ss_Petri&Pauli.png")
    warnung = page.locator("#backcover-image-warnung")
    expect(warnung).to_contain_text("Nicht erlaubt im Pfad: „&“")

    page.fill("#backcover-image", "images/Rückseite von Sankt Lambert.png")
    expect(warnung).to_contain_text("„ü“")
    expect(warnung).to_contain_text("Leerzeichen")

    # what the pick flow itself produces passes silently
    page.fill("#backcover-image", "images/2026-09-18-sancti-lamberti.png")
    expect(page.locator("#backcover-image-warnung")).to_have_count(0)


def test_drollery_path_is_checked_the_same_way(page: Page, repo_root: Path) -> None:
    """The other free-text path field, and its two keywords, which need no
    exception from the rule."""
    page.goto(form_url(repo_root))

    page.fill("#drollery", "hase & jäger.png")
    expect(page.locator("#drollery-warnung")).to_contain_text("Leerzeichen")

    for keyword in ("auto", "none"):
        page.fill("#drollery", keyword)
        expect(page.locator("#drollery-warnung")).to_have_count(0)


def test_webp_image_is_converted_to_png_and_narrow_scan_warns(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """A webp pick comes out as PNG; a narrow image warns but passes (#12)."""
    page.goto(form_url(repo_root))
    bild = make_image_file(page, tmp_path, "foto.webp", 800, 20, "image/webp")

    page.set_input_files("#backcover-image-datei", bild)

    expect(page.locator("#backcover-image")).to_have_value(
        "images/JJJJ-MM-TT-fest.png"  # .png although the source was .webp
    )
    warnung = page.locator("#backcover-image-aufloesung")
    expect(warnung).to_contain_text("Nur 800 px breit")

    # filling date + title after the pick regenerates the untouched path
    page.fill("#date", "2026-09-18")
    page.fill("#title", "Sancti Lamberti")
    expect(page.locator("#backcover-image")).to_have_value(
        "images/2026-09-18-sancti-lamberti.png"
    )

    with page.expect_download() as download_info:
        page.click("#backcover-image-download")
    gespeichert = tmp_path / "runter.png"
    download_info.value.save_as(gespeichert)
    assert gespeichert.read_bytes().startswith(b"\x89PNG")


def test_huge_scan_offers_optional_downscale(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """Scans wider than 3000 px are downscaled by default, opt-out-able (#12)."""
    page.goto(form_url(repo_root))
    bild = make_image_file(page, tmp_path, "riesig.png", 3600, 24, "image/png")

    page.set_input_files("#backcover-image-datei", bild)

    expect(page.locator("#backcover-image-info")).to_contain_text("3000 ×")
    expect(page.locator("#backcover-image-info")).to_contain_text("verkleinert von 3600 px")
    expect(page.locator("#backcover-image-verkleinern")).to_be_checked()

    page.uncheck("#backcover-image-verkleinern")
    expect(page.locator("#backcover-image-info")).to_contain_text("3600 × 24 px")


def test_non_image_pick_is_rejected_in_german(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """A file that does not decode as an image gets a German message (#12)."""
    keinbild = tmp_path / "keinbild.png"
    keinbild.write_text("Das ist kein Bild.", encoding="utf-8")

    page.goto(form_url(repo_root))
    page.set_input_files("#backcover-image-datei", keinbild)

    expect(page.locator("#backcover-image-warnung")).to_contain_text(
        "kann nicht als Bild gelesen werden"
    )
    expect(page.locator("#backcover-image")).to_have_value("")  # nothing written


def test_note_fields_round_trip_and_are_removable(page: Page, repo_root: Path) -> None:
    """Notable (ADR-0011): the optional note field on each affected section
    appears in the YAML when filled, and disappears again when cleared."""
    page.goto(form_url(repo_root))

    notes = {
        "#ant-1-note": "Antiphon-Herkunft",
        "#versus-1-note": "Vers-Herkunft",
        "#hymnus-note": "Hymnus-Herkunft",
        "#versiculus-note": "Versiculus-Herkunft",
        "#magnificat-note": "Magnificat-Herkunft",
        "#oratio-note": "Oratio-Herkunft",
        "#backcover-note": "Zitat-Herkunft",
    }
    for selector, value in notes.items():
        page.fill(selector, value)

    yaml_text = page.locator("#yaml-pane").input_value()
    for value in notes.values():
        assert f"note: {value}" in yaml_text

    page.fill("#ant-1-note", "")
    assert "note: Antiphon-Herkunft" not in page.locator("#yaml-pane").input_value()


def test_tone_is_chosen_never_typed(page: Page, repo_root: Path) -> None:
    """The psalm tone is two selectors, not a free-text field — a code like
    "1D" can't be mistyped or guessed into existence (#33)."""
    page.goto(form_url(repo_root))

    expect(page.locator("select#ant-1-tonus-modus")).to_be_visible()
    expect(page.locator("input#ant-1-tonus")).to_have_count(0)
    expect(page.locator("input#ant-1-euouae")).to_have_count(0)
    # the differentia selector is always there, but inert until a mode makes
    # it a real choice — so the layout never jumps
    differentia = page.locator("#ant-1-tonus-differentia")
    expect(differentia).to_be_disabled()
    page.select_option("#ant-1-tonus-modus", "8")
    expect(differentia).to_be_enabled()


def test_euouae_preview_appears_once_the_tone_is_complete(
    page: Page, repo_root: Path
) -> None:
    """With mode only, every candidate ending is offered; once the
    differentia is chosen, just the one preview remains (#33)."""
    page.goto(form_url(repo_root))
    preview = page.locator("#ant-1-tonus-vorschau")
    chooser = page.locator("#ant-1-tonus-wahl")
    expect(preview).to_have_count(0)
    expect(chooser).to_have_count(0)

    page.select_option("#ant-1-tonus-modus", "8")  # mode only → the candidates
    expect(chooser).to_be_visible()
    expect(preview).to_have_count(0)
    assert 'tonus: ""' in page.locator("#yaml-pane").input_value()  # not yet a tone

    page.select_option("#ant-1-tonus-differentia", "8c")  # complete → one preview
    expect(preview.locator(".noten svg").first).to_be_visible()
    expect(chooser).to_have_count(0)
    assert "tonus: 8c" in page.locator("#yaml-pane").input_value()


def test_single_differentia_mode_completes_on_the_mode_alone(
    page: Page, repo_root: Path
) -> None:
    """Modes 2/5/6 have one ending and peregrinus none, so picking the mode
    already settles the tone. The differentia selector still shows what the
    ending is, but disabled — no choice is being offered."""
    page.goto(form_url(repo_root))
    differentia = page.locator("#ant-1-tonus-differentia")

    page.select_option("#ant-1-tonus-modus", "6")
    assert "tonus: 6F" in page.locator("#yaml-pane").input_value()
    expect(page.locator("#ant-1-tonus-vorschau .noten svg").first).to_be_visible()
    expect(differentia).to_be_disabled()
    expect(differentia).to_have_value("6F")  # readable: the ending is "F"
    assert differentia.inner_text().strip() == "F"

    page.select_option("#ant-1-tonus-modus", "peregrinus")
    assert "tonus: peregrinus" in page.locator("#yaml-pane").input_value()
    expect(differentia).to_be_disabled()
    assert differentia.inner_text().strip() == "keine"  # peregrinus has none


def test_euouae_preview_uses_the_data_island(page: Page, repo_root: Path) -> None:
    """The tone→EUOUAE table is generated from the engine into the island,
    never hand-kept in the form (ADR-0004, #33)."""
    page.goto(form_url(repo_root))
    table = page.evaluate(
        "JSON.parse(document.getElementById('datenblock').textContent).euouae_per_tonus"
    )
    assert table["8G"] == "j j i j h g."
    assert table["1f"] == "h h g f gh gf.."
    assert len(table) == 33


def test_euouae_assertion_disagreeing_with_tonus_warns(
    page: Page, repo_root: Path
) -> None:
    """A loaded file may assert what its book prints as ``euouae:``. The form
    never edits it, but flags a disagreement with the chosen tone — exactly
    the check that caught two mislabelled St. Lambert antiphons (#33)."""
    page.goto(form_url(repo_root))
    load_via_paste(
        page,
        ROUNDTRIP_FIXTURE.replace(
            "    psalmus: 109\n    tonus: 8G\n",
            "    psalmus: 109\n    tonus: 8G\n    euouae: j j h j k j.\n",  # that's 8c
        ),
    )

    warnung = page.locator("#ant-1-tonus-warnung")
    expect(warnung).to_contain_text("passt nicht zum Psalmton „8G“")
    expect(warnung).to_contain_text("„8c“")


def test_euouae_assertion_matching_tonus_is_silent(page: Page, repo_root: Path) -> None:
    """The same assertion agreeing with the tone raises nothing, and is
    preserved on save even though the form offers no field for it."""
    page.goto(form_url(repo_root))
    load_via_paste(
        page,
        ROUNDTRIP_FIXTURE.replace(
            "    psalmus: 109\n    tonus: 8G\n",
            "    psalmus: 109\n    tonus: 8G\n    euouae: j j i j h g.\n",
        ),
    )

    expect(page.locator("#ant-1-tonus-warnung")).to_have_count(0)
    assert "euouae: j j i j h g." in page.locator("#yaml-pane").input_value()


def test_clicking_a_rendered_ending_sets_the_differentia(
    page: Page, repo_root: Path
) -> None:
    """The fix for the class of error that mislabelled two St. Lambert
    antiphons: rather than guessing a differentia's code, pick it by
    comparing rendered endings against the book. Replays antiphon 3 —
    mode 1, where the guess had been "1D" but the LU prints "1f" (#33, #23)."""
    page.goto(form_url(repo_root))
    page.select_option("#ant-1-tonus-modus", "1")

    chooser = page.locator("#ant-1-tonus-wahl")
    rows = chooser.locator(".tonwahl-zeile")
    # every mode-1 differentia, and only those — the ones that can be confused
    assert rows.locator(".tonwahl-kuerzel").all_inner_texts() == [
        "D", "D-", "D2", "f", "g", "g2", "g3", "a", "a2", "a3"
    ]
    # each candidate shows its ending drawn, so the book settles it by eye
    expect(rows.locator(".noten svg").first).to_be_visible()

    rows.filter(has=page.locator(".tonwahl-kuerzel", has_text=re.compile(r"^f$"))).click()
    expect(page.locator("#ant-1-tonus-differentia")).to_have_value("1f")
    assert "tonus: 1f" in page.locator("#yaml-pane").input_value()
    expect(chooser).to_have_count(0)  # replaced by the single preview


def test_gabc_popup_carries_the_staff_letter_diagram(
    page: Page, repo_root: Path
) -> None:
    """#33's staff-line/letter diagram lives in #25's GABC-basics popup —
    where #33's ticket said it belonged — rather than beside a field."""
    page.goto(form_url(repo_root))
    page.click("#ant-1-gabc-info-link")

    popup = page.locator("#ant-1-gabc-info")
    expect(popup).to_be_visible()
    expect(popup.locator(".noten svg").first).to_be_visible()


def test_responsorium_note_round_trips(page: Page, repo_root: Path) -> None:
    """Responsorium breve only exists for monasticum (#30) — its note field
    is exercised on its own, without filling the rest of the form."""
    page.goto(form_url(repo_root))
    page.select_option("#rite", "monasticum")
    page.fill("#responsorium-gabc", "chant/resp/sancte-pater-benedicte.gabc")
    page.fill("#responsorium-de", "Heiliger Vater Benedikt, * bitte für uns.")
    page.fill("#responsorium-note", "Responsorium-Herkunft")

    assert "note: Responsorium-Herkunft" in page.locator("#yaml-pane").input_value()


def test_filler_page_is_composed_without_writing_latex(page: Page, repo_root: Path) -> None:
    """A flavour page is entered as plain text — title, red block heading,
    citation, image + caption — and lands in the spec as a structured entry.
    No filler page by default, and none until something is actually typed."""
    page.goto(form_url(repo_root))
    expect(page.locator(".filler-page")).to_have_count(0)
    assert "filler:" not in page.locator("#yaml-pane").input_value()

    page.click("#filler-add")
    expect(page.locator(".filler-page")).to_have_count(1)
    # an empty page contributes nothing — only real content does
    assert "filler:" not in page.locator("#yaml-pane").input_value()

    page.fill("#filler-1-title", "Der heilige Vater Benedikt")
    page.fill("#filler-1-subtitle", "aus Dom Prosper Guérangers »Kirchenjahr«")
    page.fill("#filler-1-block-1-heading", "Vater Europas")
    page.fill("#filler-1-block-1-text", "Benedikt ist der geistige Vater Europas.")
    page.fill("#filler-1-citation", "Das Kirchenjahr, Bd. 5, 1877")

    yaml_text = page.locator("#yaml-pane").input_value()
    assert "filler:" in yaml_text
    assert "title: Der heilige Vater Benedikt" in yaml_text
    assert "heading: Vater Europas" in yaml_text
    assert "citation: Das Kirchenjahr, Bd. 5, 1877" in yaml_text
    # plain text in, plain text out — no LaTeX anywhere near the author
    assert "\\" not in yaml_text.split("filler:")[1].split("back_cover:")[0]

    page.click(".filler-1-block-add")
    expect(page.locator(".filler-block")).to_have_count(2)
    page.fill("#filler-1-block-2-text", "Und all diese Wunderthaten …")
    assert "Und all diese Wunderthaten" in page.locator("#yaml-pane").input_value()


def test_filler_page_image_and_caption_reach_the_spec(page: Page, repo_root: Path) -> None:
    """`image` is a real field, not markup inside the prose — that is what
    lets libellus stage the file (a raw .tex page's image is not found)."""
    page.goto(form_url(repo_root))
    page.click("#filler-add")
    page.fill("#filler-1-block-1-text", "Zur Medaille")
    page.fill("#filler-1-image", "images/02-benedict/medal-print.png")
    page.fill("#filler-1-caption", "Die Benediktusmedaille")

    yaml_text = page.locator("#yaml-pane").input_value()
    assert "image: images/02-benedict/medal-print.png" in yaml_text
    assert "caption: Die Benediktusmedaille" in yaml_text


def test_filler_page_can_be_removed(page: Page, repo_root: Path) -> None:
    page.goto(form_url(repo_root))
    page.click("#filler-add")
    page.fill("#filler-1-block-1-text", "Weg damit")
    assert "filler:" in page.locator("#yaml-pane").input_value()

    page.click(".filler-remove")
    expect(page.locator(".filler-page")).to_have_count(0)
    assert "filler:" not in page.locator("#yaml-pane").input_value()


def test_rite_switch_drives_antiphon_rows(page: Page, repo_root: Path) -> None:
    """The ordo choice shows exactly the antiphon/psalm rows the rite requires."""
    page.goto(form_url(repo_root))
    expect(page.locator(".antiphona-row")).to_have_count(5)

    page.select_option("#rite", "monasticum")
    expect(page.locator(".antiphona-row")).to_have_count(4)

    page.select_option("#rite", "romanum-1962")
    expect(page.locator(".antiphona-row")).to_have_count(5)


def test_back_cover_border_select_updates_yaml(page: Page, repo_root: Path) -> None:
    """Picking a border style writes `border:` under back_cover; switching
    back to "Goldrahmen (Foto)" removes it again (ADR-0013/0014, default is
    "gilded")."""
    page.goto(form_url(repo_root))
    expect(page.locator("#backcover-border")).to_have_value("gilded")
    assert "border:" not in page.locator("#yaml-pane").input_value()

    page.select_option("#backcover-border", "knot")
    assert "border: knot" in page.locator("#yaml-pane").input_value()

    page.select_option("#backcover-border", "gilded")
    assert "border:" not in page.locator("#yaml-pane").input_value()


def test_simplex_rank_disables_vesperae_select(page: Page, repo_root: Path) -> None:
    """A Simplex feast has exactly one Vespers, not a First/Second choice
    (ADR-0015 update, 2026-07-25) — the #vesperae select is disabled for
    it, not removed (removing it made the form jump around when switching
    ranks), and the emitted YAML omits `vesperae:` entirely rather than
    carrying a now-meaningless value."""
    page.goto(form_url(repo_root))
    expect(page.locator("#vesperae")).to_be_enabled()
    assert "vesperae:" in page.locator("#yaml-pane").input_value()

    page.select_option("#rank", "Simplex")
    expect(page.locator("#vesperae")).to_be_disabled()
    assert "vesperae:" not in page.locator("#yaml-pane").input_value()

    page.select_option("#rank", "Duplex I classis")
    expect(page.locator("#vesperae")).to_be_enabled()
    assert "vesperae:" in page.locator("#yaml-pane").input_value()


def test_browser_composed_yaml_round_trips_through_libellus(
    page: Page, repo_root: Path, tmp_path: Path
) -> None:
    """A feast spec composed purely in the browser validates and stages green."""
    page.goto(form_url(repo_root))
    expect(page.locator("html")).to_have_attribute("lang", "de")

    page.select_option("#rite", "romanum-cum-precibus")
    page.select_option("#vesperae", "I")
    page.select_option("#rank", "Duplex I classis")
    page.click("#versus-add")  # capitulum starts with one versus row
    page.click("#stanza-add")  # hymn starts with one stanza
    page.check("#backcover-kind-quote")
    page.select_option("#backcover-border", "grapevine")
    for selector, value in FIELD_VALUES.items():
        page.fill(selector, value)
    for field, tonus in TONUS_VALUES.items():
        pick_tonus(page, field, tonus)

    yaml_text = page.locator("#yaml-pane").input_value()
    assert "\\" not in yaml_text  # plain text end to end, no LaTeX leaks in

    with page.expect_download() as download_info:
        page.click("#download")
    download = download_info.value
    assert download.suggested_filename == "2026-07-10-sancti-benedicti.yaml"
    downloaded = tmp_path / "download.yaml"
    download.save_as(downloaded)
    assert downloaded.read_text(encoding="utf-8") == yaml_text

    page.click("#copy")  # clipboard or textarea-select fallback — must not crash
    expect(page.locator("#copy")).to_have_text("Kopiert ✓")

    feast = tmp_path / "2026-07-10-sancti-benedicti.yaml"
    feast.write_text(yaml_text, encoding="utf-8")
    spec = load_spec(feast)  # German validation is the gate — raises on errors
    assert spec.liturgical_date is not None
    assert spec.antiphonae[4].gabc.startswith("name:")  # inline GABC survived
    assert spec.back_cover.border == "grapevine"  # ADR-0013

    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)
    build_dir = stage(tex, resolved.assets, feast.stem, repo_root, tmp_path / "build")
    assert (build_dir / f"{feast.stem}.tex").is_file()
    assert (build_dir / "Makefile").is_file()


#: A hand-maintained feast spec with everything the form must not destroy:
#: comments (own line and inline), blank lines, quoting styles, |- and
#: clip-chomped | blocks, key order, an unknown extra field — and it is a
#: fixed point of the embedded yaml library's printer, so byte-identity is
#: assertable.
ROUNDTRIP_FIXTURE = """\
# Fest-Datei von Hand gepflegt — dieser Kommentar bleibt stehen.
title: Sancti Benedicti
subtitle: Patroni Europæ
vesperae: I
header: "S. Benedictus, Patronus Europæ" # Kopfzeile, absichtlich in Anführungszeichen
rank: 'Duplex I classis'
date: 2026-07-10
rite: monasticum
source: Antiphonale Monasticum III, Solesmis 2007

# Die vier Antiphonen des monastischen Ordo.
antiphonae:
  - gabc: chant/ant/fuit-vir-vitae-venerabilis.gabc
    de: Es lebte ein Mann von verehrungswürdigem Lebenswandel.
    psalmus: 109
    tonus: 8G
  - gabc: |-
      name:Beatus vir;
      office-part:Antiphona;
      mode:3;
      %%
      (c4) Be(f)á(fg)tus(g) vir(g) (::)
    de: Der heilige Mann Benedikt.
    psalmus: 110
    tonus: 3a2
  - gabc: chant/ant/gloriosus-confessor-domini.gabc
    de: Der glorreiche Bekenner des Herrn.
    repetitio: Gloriósus conféssor
    psalmus: 111
    tonus: 8c
  - gabc: chant/ant/vir-domini-benedictus.gabc
    de: Der Gottesmann Benedikt.
    psalmus: 112
    tonus: 1f

capitulum:
  ref: Iesu Sirach 50, 5-10
  versus:
    - n: 5
      text: Qui præváluit amplificáre civitátem.
      de: Wie herrlich war er, umgeben vom Volk.
    - n: 6
      text: Quasi stella matutína in médio nébulæ.
      de: Wie der Morgenstern inmitten von Wolken.

responsorium:
  gabc: chant/resp/sancte-pater-benedicte.gabc
  de: Heiliger Vater Benedikt, * bitte für uns.

hymnus:
  gabc: chant/hymni/gemma-caelestis.gabc
  de:
    - O Benedikt, Schatz des Königs des Himmels.
    - Ehre sei dem Vater und dem Wort, dem Sohn. Amen.

versiculus:
  gabc: chant/vers/amavit-eum-dominus.gabc
  de: ℣. Der Herr hat ihn geliebt. ℟. Das Kleid der Herrlichkeit.

magnificat:
  antiphona:
    gabc: chant/ant/exsultet-omnium-turba.gabc
    de: Es juble die Schar aller Gläubigen.
  tonus: 1D

oratio:
  text: Deus, qui beatíssimum Confessórem tuum Benedíctum † concéde nobis.
  de: Gott, du hast deinen heiligen Bekenner Benedikt erfüllt.

antiphona_bmv: salve-regina-simple

# Eine gestaltete Zusatzseite und eine eigene .tex-Seite nebeneinander.
filler:
  - title: Der heilige Vater Benedikt
    subtitle: aus Dom Prosper Guérangers »Kirchenjahr«
    blocks:
      - heading: Vater Europas
        text: Benedikt ist der geistige Vater Europas.
      - text: Und all diese Wunderthaten hat er durch seine Regel vollbracht.
    citation: Das Kirchenjahr, Bd. 5, 1877
    image: images/02-benedict/medal-print.png
    caption: Die Benediktusmedaille.
  - eigene-seiten/nachwort.tex

back_cover:
  image: images/02-benedict/st-benedict-mary-evans.jpg
  credit: 'Imago: Saint Benedict of Nursia, Mary Evans Picture Library.'
  quote:
    text: |-
      Ad horam divini officii,
      mox auditus fuerit signus.
    de: |
      Zur Stunde des Gottesdienstes,
      sobald das Zeichen gegeben wird.
    motto: Ergo nihil operi Dei præponatur.
    citation: Regula Benedicti, cap. XLIII

# Eigenes Zusatzfeld — das Formular kennt es nicht, löscht es aber nie.
x-notiz: Weihrauch erst ab dem Magnificat.
"""


def load_via_paste(page: Page, yaml_text: str) -> None:
    """Open the load panel and paste an existing spec, as a successor would."""
    page.click(".laden summary")
    page.fill("#load-text", yaml_text)
    page.click("#load-apply")


def test_load_via_paste_round_trips_byte_identically(page: Page, repo_root: Path) -> None:
    """Untouched content of a loaded spec survives saving byte-identically."""
    page.goto(form_url(repo_root))
    load_via_paste(page, ROUNDTRIP_FIXTURE)

    expect(page.locator("#title")).to_have_value("Sancti Benedicti")
    expect(page.locator("#rite")).to_have_value("monasticum")
    expect(page.locator(".antiphona-row")).to_have_count(4)
    expect(page.locator("#ant-2-gabc")).to_have_value(
        "name:Beatus vir;\noffice-part:Antiphona;\nmode:3;\n%%\n(c4) Be(f)á(fg)tus(g) vir(g) (::)"
    )
    # the unknown field is announced, in German — and never dropped
    expect(page.locator("#load-warnings")).to_contain_text("Unbekanntes Feld „x-notiz“")

    # nothing touched yet → the file is reproduced byte for byte
    expect(page.locator("#yaml-pane")).to_have_value(ROUNDTRIP_FIXTURE)

    # one field changed → exactly that line changes, its quoting style kept
    page.select_option("#rank", "I classis")
    expect(page.locator("#yaml-pane")).to_have_value(
        ROUNDTRIP_FIXTURE.replace("rank: 'Duplex I classis'", "rank: 'I classis'")
    )


def test_load_via_file_picker(page: Page, repo_root: Path, tmp_path: Path) -> None:
    """The file picker loads a spec from disk; the pane reproduces it."""
    feast = tmp_path / "2026-07-10-sancti-benedicti.yaml"
    feast.write_text(ROUNDTRIP_FIXTURE, encoding="utf-8")

    page.goto(form_url(repo_root))
    page.click(".laden summary")
    page.set_input_files("#load-file", feast)

    expect(page.locator("#title")).to_have_value("Sancti Benedicti")
    expect(page.locator("#backcover-motto")).to_have_value("Ergo nihil operi Dei præponatur.")
    expect(page.locator("#yaml-pane")).to_have_value(ROUNDTRIP_FIXTURE)


def test_invalid_spec_populates_what_it_can_and_warns_in_german(
    page: Page, repo_root: Path
) -> None:
    """A spec that fails the schema still fills the form + says what is wrong."""
    page.goto(form_url(repo_root))
    load_via_paste(
        page,
        "title: Sancti Lamberti\ndate: 2026-09-18\nantiphonae: kaputt\n",
    )

    expect(page.locator("#title")).to_have_value("Sancti Lamberti")
    expect(page.locator("#date")).to_have_value("2026-09-18")
    warnings = page.locator("#load-warnings")
    expect(warnings).to_contain_text("„antiphonae“ müsste eine Liste sein")
    expect(warnings).to_contain_text("Feld „oratio“ fehlt in der Datei")


def test_yaml_syntax_error_is_reported_in_german(page: Page, repo_root: Path) -> None:
    """Broken YAML is rejected with a German message; the form stays usable."""
    page.goto(form_url(repo_root))
    page.fill("#title", "Vorher")
    load_via_paste(page, "title: [kaputt")

    expect(page.locator("#load-warnings")).to_contain_text(
        "Die Datei ist kein gültiges YAML"
    )
    expect(page.locator("#title")).to_have_value("Vorher")  # nothing overwritten


#: The rite round-trip below temporarily switches to romanum-cum-precibus,
#: which has no Responsorium breve (#30) — the field is deleted from the
#: loaded document, then re-created fresh (appended at the end, after
#: x-notiz) once the rite switches back to monasticum. Re-creating a
#: deleted node can't restore its original position, so byte-identity
#: holds for everything else but not for where this one field ends up.
_RESPONSORIUM_BLOCK = (
    "responsorium:\n"
    "  gabc: chant/resp/sancte-pater-benedicte.gabc\n"
    "  de: Heiliger Vater Benedikt, * bitte für uns.\n"
)
ROUNDTRIP_FIXTURE_AFTER_RITE_ROUNDTRIP = (
    ROUNDTRIP_FIXTURE.replace(_RESPONSORIUM_BLOCK + "\n", "") + _RESPONSORIUM_BLOCK
)


def test_structural_edits_on_loaded_spec_are_reversible(
    page: Page, repo_root: Path
) -> None:
    """Rows added to a loaded spec land in the YAML; removing them restores it."""
    page.goto(form_url(repo_root))
    load_via_paste(page, ROUNDTRIP_FIXTURE)

    # a fifth antiphon appears when the rite demands one …
    page.select_option("#rite", "romanum-cum-precibus")
    expect(page.locator(".antiphona-row")).to_have_count(5)
    page.fill("#ant-5-gabc", "chant/ant/fuit-vir-vitae-venerabilis.gabc")
    yaml_text = page.locator("#yaml-pane").input_value()
    assert "rite: romanum-cum-precibus" in yaml_text
    assert yaml_text.count("chant/ant/fuit-vir-vitae-venerabilis.gabc") == 2
    # romanum-cum-precibus has no Responsorium breve (#30) — dropped from the file
    assert "responsorium" not in yaml_text

    # … and an added capitulum verse lands in the file too
    page.click("#versus-add")
    page.fill("#versus-3-n", "7")
    assert "n: 7" in page.locator("#yaml-pane").input_value()

    # undoing both edits restores the loaded file — byte for byte, except
    # the Responsorium breve field re-created at the end (see above)
    page.click("css=.versus-row >> nth=2 >> css=.versus-remove")
    page.select_option("#rite", "monasticum")
    expect(page.locator("#yaml-pane")).to_have_value(ROUNDTRIP_FIXTURE_AFTER_RITE_ROUNDTRIP)


def test_antiphon_count_not_matching_rite_is_announced(
    page: Page, repo_root: Path
) -> None:
    """A rite/antiphon-count mismatch gets a German note instead of silence."""
    # the monasticum fixture carrying a fifth antiphon entry
    five_antiphonae = ROUNDTRIP_FIXTURE.replace(
        "  - gabc: chant/ant/vir-domini-benedictus.gabc",
        "  - gabc: chant/ant/zuviel.gabc\n"
        "    de: Eine überzählige Antiphon.\n"
        "    psalmus: 116\n"
        "    tonus: 2D\n"
        "  - gabc: chant/ant/vir-domini-benedictus.gabc",
    )

    page.goto(form_url(repo_root))
    load_via_paste(page, five_antiphonae)

    expect(page.locator(".antiphona-row")).to_have_count(4)
    expect(page.locator("#load-warnings")).to_contain_text(
        "Der Ordo „monasticum“ hat 4 Antiphonen mit Psalm — die Datei enthält 5."
    )


def test_draft_checkbox_writes_and_clears_the_field(page: Page, repo_root: Path) -> None:
    """The form is the only place a draft can be switched off again (ADR-0021):
    ticking writes `draft: true`, clearing removes the key rather than writing
    `draft: false`."""
    page.goto(form_url(repo_root))

    page.check("#draft")
    assert "draft: true" in page.locator("#yaml-pane").input_value()

    page.uncheck("#draft")
    yaml_text = page.locator("#yaml-pane").input_value()
    assert "draft" not in yaml_text


def test_loaded_draft_spec_shows_the_checkbox_ticked(page: Page, repo_root: Path) -> None:
    """A spec that arrives marked as a draft says so in the form — otherwise the
    one place it can be unmarked would not reveal that it is set (ADR-0021)."""
    page.goto(form_url(repo_root))
    load_via_paste(page, ROUNDTRIP_FIXTURE.replace("\nrite:", "\ndraft: true\nrite:"))

    expect(page.locator("#draft")).to_be_checked()

    page.uncheck("#draft")
    assert "draft" not in page.locator("#yaml-pane").input_value()


def test_compact_checkbox_round_trips(page: Page, repo_root: Path) -> None:
    """The Kurzfassung is a spec field so that the form can set it and a Bündel
    carries it (ADR-0022); like `draft:`, only the "true" case is ever written,
    and a spec that arrives compact shows it."""
    page.goto(form_url(repo_root))

    page.check("#compact")
    assert "compact: true" in page.locator("#yaml-pane").input_value()

    page.uncheck("#compact")
    assert "compact" not in page.locator("#yaml-pane").input_value()

    load_via_paste(page, ROUNDTRIP_FIXTURE.replace("\nrite:", "\ncompact: true\nrite:"))
    expect(page.locator("#compact")).to_be_checked()
