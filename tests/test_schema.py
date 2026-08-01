from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from conftest import BENEDICT_FEAST, SMOKE_FEAST

from libellus.errors import FeastFileError
from libellus.resolve import load_spec
from libellus.schema import (
    AntiphonaAdMagnificat,
    AntiphonaCumPsalmo,
    BackCoverQuote,
    FeastSpec,
    FillerPage,
    Hymnus,
    Notable,
    Oratio,
    Responsorium,
    Versiculus,
    Versus,
)


def _smoke_data(repo_root: Path) -> dict:
    """Raw YAML of the `romanum-cum-precibus` fixture (St. Lambert)."""
    return yaml.safe_load((repo_root / SMOKE_FEAST).read_text(encoding="utf-8"))


def _benedict_data(repo_root: Path) -> dict:
    """Raw YAML of the `monasticum` fixture (the Benedict office)."""
    return yaml.safe_load((repo_root / BENEDICT_FEAST).read_text(encoding="utf-8"))


def test_smoke_feast_validates(repo_root: Path) -> None:
    spec = FeastSpec.model_validate(_smoke_data(repo_root))
    assert spec.rite == "romanum-cum-precibus"
    assert spec.cum_precibus
    assert len(spec.antiphonae) == 5
    assert spec.responsorium is None  # Roman Vespers has none (#30)


def test_benedict_feast_validates_as_monasticum(repo_root: Path) -> None:
    """The Benedict office in its own rite: 4 pairs, Responsorium breve,
    Preces + sung Pater noster."""
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    assert spec.rite == "monasticum"
    assert spec.cum_precibus
    assert len(spec.antiphonae) == 4
    assert spec.responsorium is not None


def test_capitulum_is_a_versus_list(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    data["capitulum"] = {
        "ref": "Iac. 1, 12",
        "versus": [
            {"n": 12, "text": "Beátus vir, qui suffert tentatiónem.", "de": "Selig der Mann."},
        ],
    }
    spec = FeastSpec.model_validate(data)
    assert spec.capitulum.versus[0].n == 12
    assert spec.capitulum.versus[0].text.startswith("Beátus")
    assert spec.capitulum.versus[0].de.startswith("Selig")


def test_capitulum_free_text_shape_is_rejected(repo_root: Path) -> None:
    """The old text/de pair with embedded LaTeX is gone from the schema."""
    data = _smoke_data(repo_root)
    data["capitulum"] = {"ref": "Iac. 1, 12", "text": "Beátus vir", "de": "Selig der Mann"}
    with pytest.raises(ValidationError):
        FeastSpec.model_validate(data)


def test_malformed_versus_gives_german_message(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    del data["capitulum"]["versus"][1]["n"]
    data["capitulum"]["versus"][2]["n"] = "sieben"
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any("capitulum → versus → 2. Eintrag → n" in m and "fehlt" in m for m in excinfo.value.messages)
    assert any("3. Eintrag" in m and "Zahl" in m for m in excinfo.value.messages)


def test_back_cover_quote_block(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    data["back_cover"] = {
        "image": "images/02-benedict/st-benedict-mary-evans.jpg",
        "credit": "Imago: Saint Benedict of Nursia, ex collectione Mary Evans.",
        "quote": {
            "text": "Ad horam divini officii,\nmox auditus fuerit signus.",
            "de": "Sobald das Zeichen ertönt,\nsoll man alles liegenlassen.",
            "motto": "Ergo nihil operi Dei præponatur.",
            "motto_de": "Dem Werk Gottes soll nichts vorgezogen werden.",
            "citation": "Regula Benedicti, cap. XLIII",
        },
    }
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.quote is not None
    assert "\n" in spec.back_cover.quote.text
    assert spec.back_cover.quote.citation == "Regula Benedicti, cap. XLIII"


def test_back_cover_free_text(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    data["back_cover"] = {
        "image": "images/02-benedict/st-benedict-mary-evans.jpg",
        "credit": "Imago: irgendwoher.",
        "text": "Freier Text\nüber mehrere Zeilen.",
    }
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.text is not None
    assert spec.back_cover.quote is None


def test_back_cover_border_defaults_to_gilded(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    del data["back_cover"]["border"]  # the fixture states it; the default must match
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.border == "gilded"


@pytest.mark.parametrize("style", ["none", "vine", "grapevine", "knot", "feather"])
def test_back_cover_border_accepts_named_styles(repo_root: Path, style: str) -> None:
    data = _smoke_data(repo_root)
    data["back_cover"]["border"] = style
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.border == style


def test_back_cover_border_size_defaults_to_normal(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    del data["back_cover"]["border_size"]  # ditto
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.border_size == "normal"


@pytest.mark.parametrize("size", ["normal", "large", "extra-large"])
def test_back_cover_border_size_accepts_named_sizes(repo_root: Path, size: str) -> None:
    data = _smoke_data(repo_root)
    data["back_cover"]["border_size"] = size
    spec = FeastSpec.model_validate(data)
    assert spec.back_cover.border_size == size


def test_back_cover_border_rejects_unknown_style(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    data["back_cover"]["border"] = "gold-baroque"
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    message = " ".join(excinfo.value.messages)
    assert "border" in message
    assert "vine" in message and "grapevine" in message and "knot" in message and "feather" in message


def test_back_cover_requires_exactly_one_of_quote_or_text(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    for content in (
        {},  # neither
        {  # both
            "quote": {"text": "a", "de": "b"},
            "text": "c",
        },
    ):
        data["back_cover"] = {
            "image": "images/02-benedict/st-benedict-mary-evans.jpg",
            "credit": "Imago: x.",
            **content,
        }
        broken = tmp_path / "broken.yaml"
        broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(FeastFileError) as excinfo:
            load_spec(broken)
        assert any("Rückseite" in m and "quote" in m and "text" in m for m in excinfo.value.messages)


#: Minimal but complete GABC notation: headers, %% separator, note groups.
INLINE_GABC = "name:Fuit vir;\nmode:8;\n%%\n(c4) Fu(f)it(fg) vir(g) (::)\n"


def test_inline_gabc_accepted_for_every_chant_element(repo_root: Path) -> None:
    """gabc: is a union — repo path or inline GABC block (ADR-0005)."""
    data = _smoke_data(repo_root)
    data["antiphonae"][0]["gabc"] = INLINE_GABC
    data["hymnus"]["gabc"] = INLINE_GABC
    data["versiculus"]["gabc"] = INLINE_GABC
    data["magnificat"]["antiphona"]["gabc"] = INLINE_GABC
    spec = FeastSpec.model_validate(data)
    assert "%%" in spec.antiphonae[0].gabc
    assert "%%" in spec.magnificat.antiphona.gabc
    # path-referenced elements keep working untouched
    assert spec.antiphonae[1].gabc.endswith(".gabc")


def test_gabc_neither_path_nor_notation_gives_german_message(
    repo_root: Path, tmp_path: Path
) -> None:
    data = _smoke_data(repo_root)
    data["antiphonae"][0]["gabc"] = "ant1-fuit-vir.txt"  # not a .gabc path
    data["versiculus"]["gabc"] = "zwei Zeilen,\naber keine Notation"  # no %% separator
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any(
        "antiphonae → 1. Eintrag → gabc" in m and ".gabc" in m and "%%" in m
        for m in excinfo.value.messages
    )
    assert any("versiculus → gabc" in m for m in excinfo.value.messages)


def test_responsorium_required_for_monasticum(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    del data["responsorium"]
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("Responsorium breve" in e["msg"] for e in excinfo.value.errors())


def test_responsorium_forbidden_for_roman_rites(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    assert data["rite"] == "romanum-cum-precibus"
    data["responsorium"] = {
        "gabc": "chant/resp/sancte-pater-benedicte.gabc",
        "de": "Heiliger Vater Benedikt, * bitte für uns.",
    }
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("kein Responsorium breve" in e["msg"] for e in excinfo.value.errors())


def test_wrong_antiphon_count_gives_german_message(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    data["antiphonae"] = data["antiphonae"][:3]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any("Antiphonen" in m for m in excinfo.value.messages)


def test_unknown_field_gives_german_message(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    data["oratio_typo"] = "x"
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any("Tippfehler" in m and "oratio_typo" in m for m in excinfo.value.messages)


@pytest.mark.parametrize(
    "rank",
    [
        "Duplex I classis",
        "Duplex II classis",
        "Duplex majus",
        "Duplex",
        "Duplex minus",  # same rung as "Duplex", spelled fuller (ADR-0015)
        "Semiduplex",
        "Simplex",
        "Feria",
        "I classis",
        "II classis",
        "III classis",
        "IV classis",
    ],
)
def test_rank_accepts_both_vocabularies(repo_root: Path, rank: str) -> None:
    """rank (ADR-0015): pre-1955 and Codex Rubricarum 1960 values, free choice."""
    data = _smoke_data(repo_root)
    data["rank"] = rank
    if rank == "Simplex":
        del data["vesperae"]  # inapplicable — see the vesperae/Simplex tests below
    spec = FeastSpec.model_validate(data)
    assert spec.rank == rank


def test_vesperae_forbidden_for_simplex(repo_root: Path) -> None:
    """A Simplex feast has exactly one Vespers — no First/Second to pick
    (ADR-0015 update, 2026-07-25): `vesperae` must be absent, not just unused."""
    data = _smoke_data(repo_root)
    data["rank"] = "Simplex"
    assert data["vesperae"] == "I"  # still set, from the smoke fixture
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("Simplex" in e["msg"] for e in excinfo.value.errors())


def test_vesperae_absent_for_simplex_validates(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    data["rank"] = "Simplex"
    del data["vesperae"]
    spec = FeastSpec.model_validate(data)
    assert spec.vesperae is None


def test_vesperae_required_for_non_simplex_ranks(repo_root: Path) -> None:
    data = _smoke_data(repo_root)
    del data["vesperae"]
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("vesperae" in e["msg"] for e in excinfo.value.errors())


def test_rank_rejects_unknown_value(repo_root: Path, tmp_path: Path) -> None:
    """The old free-text field is gone — only the 11 closed-set values validate."""
    data = _smoke_data(repo_root)
    data["rank"] = "Classis I · Duplex"  # the old, wrong ad-hoc string
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    message = " ".join(excinfo.value.messages)
    assert "rank" in message
    assert "Duplex I classis" in message and "IV classis" in message


def test_missing_field_gives_german_message(repo_root: Path, tmp_path: Path) -> None:
    data = _smoke_data(repo_root)
    del data["oratio"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any("oratio" in m and "fehlt" in m for m in excinfo.value.messages)


def test_filler_accepts_structured_pages(repo_root: Path) -> None:
    """The Benedict fixture's flavour pages parse into FillerPage models."""
    spec = FeastSpec.model_validate(_benedict_data(repo_root))
    assert len(spec.filler) == 2
    first, second = spec.filler
    assert isinstance(first, FillerPage) and isinstance(second, FillerPage)
    assert first.title == "Der heilige Vater Benedikt"
    assert [b.heading for b in first.blocks][:2] == ["Vater Europas", "Die Regel"]
    assert first.image is None
    # a plain str since ADR-0019: the field also carries embedded data: URIs
    assert second.image == "images/02-benedict/medal-print.png"
    assert second.caption is not None


def test_filler_still_accepts_a_raw_tex_path(repo_root: Path) -> None:
    """The ADR-0001/0002 escape hatch survives alongside structured pages."""
    data = _benedict_data(repo_root)
    data["filler"] = ["template/partials/filler.tex.j2", {"blocks": [{"text": "x"}]}]
    spec = FeastSpec.model_validate(data)
    assert spec.filler[0] == Path("template/partials/filler.tex.j2")
    assert isinstance(spec.filler[1], FillerPage)


def test_filler_page_without_content_is_rejected(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["filler"] = [{"title": "Nur eine Überschrift"}]
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("Textblöcke" in e["msg"] for e in excinfo.value.errors())


def test_filler_caption_without_image_is_rejected(repo_root: Path) -> None:
    data = _benedict_data(repo_root)
    data["filler"] = [{"blocks": [{"text": "x"}], "caption": "ohne Bild"}]
    with pytest.raises(ValidationError) as excinfo:
        FeastSpec.model_validate(data)
    assert any("Bildunterschrift" in e["msg"] for e in excinfo.value.errors())


#: The 8 content-bearing proper models that inherit `Notable` (ADR-0011),
#: each paired with the minimal kwargs needed to validate on its own.
NOTABLE_MODELS = [
    (AntiphonaCumPsalmo, {"gabc": "a.gabc", "de": "x", "psalmus": 1, "tonus": "8G"}),
    (Versus, {"n": 1, "text": "x", "de": "y"}),
    (Responsorium, {"gabc": "a.gabc", "de": "x"}),
    (Hymnus, {"gabc": "a.gabc", "de": ["x"]}),
    (Versiculus, {"gabc": "a.gabc", "de": "x"}),
    (AntiphonaAdMagnificat, {"gabc": "a.gabc", "de": "x"}),
    (Oratio, {"text": "x", "de": "y"}),
    (BackCoverQuote, {"text": "x", "de": "y"}),
]


@pytest.mark.parametrize(("model_cls", "_kwargs"), NOTABLE_MODELS)
def test_notable_model_is_a_notable_subclass(model_cls: type, _kwargs: dict) -> None:
    assert issubclass(model_cls, Notable)


@pytest.mark.parametrize(("model_cls", "kwargs"), NOTABLE_MODELS)
def test_notable_model_note_defaults_to_none(model_cls: type, kwargs: dict) -> None:
    instance = model_cls.model_validate(kwargs)
    assert instance.note is None


@pytest.mark.parametrize(("model_cls", "kwargs"), NOTABLE_MODELS)
def test_notable_model_accepts_a_note(model_cls: type, kwargs: dict) -> None:
    provenance = "Vesperale Romanum, Leodii 1835, Pag. 406-407"
    instance = model_cls.model_validate({**kwargs, "note": provenance})
    assert instance.note == provenance


#: The two antiphon models that carry an optional ``euouae:`` override (#33).
EUOUAE_MODELS = [
    (AntiphonaCumPsalmo, {"gabc": "a.gabc", "de": "x", "psalmus": 1, "tonus": "8G"}),
    (AntiphonaAdMagnificat, {"gabc": "a.gabc", "de": "x"}),
]


@pytest.mark.parametrize(("model_cls", "kwargs"), EUOUAE_MODELS)
def test_euouae_defaults_to_none(model_cls: type, kwargs: dict) -> None:
    instance = model_cls.model_validate(kwargs)
    assert instance.euouae is None


@pytest.mark.parametrize(("model_cls", "kwargs"), EUOUAE_MODELS)
def test_euouae_accepts_hand_typed_neumes(model_cls: type, kwargs: dict) -> None:
    neumes = "h h g h f e."
    instance = model_cls.model_validate({**kwargs, "euouae": neumes})
    assert instance.euouae == neumes


def test_capitulum_and_magnificat_stay_unnotable(repo_root: Path, tmp_path: Path) -> None:
    """Structural wrapper models don't get their own note (ADR-0011) — the
    leaf models they contain already carry it."""
    data = _smoke_data(repo_root)
    data["capitulum"]["note"] = "sollte abgelehnt werden"
    data["magnificat"]["note"] = "sollte abgelehnt werden"
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FeastFileError) as excinfo:
        load_spec(broken)
    assert any(
        "Tippfehler" in m and "capitulum" in m and "note" in m for m in excinfo.value.messages
    )
    assert any(
        "Tippfehler" in m and "magnificat" in m and "note" in m for m in excinfo.value.messages
    )


def test_draft_defaults_to_false_and_accepts_true(repo_root: Path, tmp_path: Path) -> None:
    """`draft:` is optional and off by default; a final booklet is the absence
    of the field, not `draft: false` (ADR-0021)."""
    data = _smoke_data(repo_root)
    assert load_spec(repo_root / SMOKE_FEAST).draft is False

    data["draft"] = True
    marked = tmp_path / "entwurf.yaml"
    marked.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    assert load_spec(marked).draft is True


def test_compact_defaults_to_false_and_accepts_true(repo_root: Path, tmp_path: Path) -> None:
    """`compact:` is optional and off by default, like `draft:` — the full
    booklet is the absence of the field (ADR-0022)."""
    data = _smoke_data(repo_root)
    assert load_spec(repo_root / SMOKE_FEAST).compact is False

    data["compact"] = True
    short = tmp_path / "kurzfassung.yaml"
    short.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    assert load_spec(short).compact is True
