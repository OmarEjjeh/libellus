"""Pydantic models for the feast spec YAML — the single schema definition.

Field names follow the booklet's own liturgical Latin (antiphonae,
capitulum, hymnus, versiculus, magnificat, oratio) plus plain-English
glue (title, date, rank, rite, gabc, de). See HANDOFF.md.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from libellus.gabc import is_inline_gabc
from libellus.imagedata import decode_inline_image, is_inline_image

Rite = Literal["romanum-1962", "monasticum", "romanum-cum-precibus"]

#: Pre-1955 rank vocabulary (traditional/monastic Duplex family; ADR-0015).
#: "Semiduplex" was abolished by Pius XII in 1955, so this ladder — which
#: still includes it — predates 1955, not 1960 (the Codex Rubricarum year).
#: "Duplex" and "Duplex minus" are the *same* rung, spelled two ways: the
#: books write the fuller "Duplex minus" to distinguish it from "Duplex
#: majus", but a plain "Duplex" means the same and may be printed instead
#: (ADR-0015 update, 2026-07-27). The value is rendered verbatim on the
#: cover, so which spelling a feast holds is purely a printing choice.
RANK_PRE_1955: tuple[str, ...] = (
    "Duplex I classis",
    "Duplex II classis",
    "Duplex majus",
    "Duplex",
    "Duplex minus",
    "Semiduplex",
    "Simplex",
    "Feria",
)

#: Codex Rubricarum 1960 rank vocabulary, the four classes (ADR-0015).
RANK_CODEX_1960: tuple[str, ...] = (
    "I classis",
    "II classis",
    "III classis",
    "IV classis",
)

#: A feast's rank: exactly one value from either vocabulary (ADR-0015).
#: The two systems are not derivable from one another and are not tied to
#: `rite` — a feast picks whichever vocabulary its source uses.
Rank = Literal[
    "Duplex I classis",
    "Duplex II classis",
    "Duplex majus",
    "Duplex",
    "Duplex minus",
    "Semiduplex",
    "Simplex",
    "Feria",
    "I classis",
    "II classis",
    "III classis",
    "IV classis",
]


def _validate_gabc_source(value: str) -> str:
    if is_inline_gabc(value):
        return value
    if "\n" not in value and value.endswith(".gabc"):
        return value
    raise ValueError(
        "Der Wert ist weder ein Pfad zu einer .gabc-Datei noch GABC-Notation "
        "(Kopfzeilen, eine Zeile „%%“, danach der Gesangstext mit Noten in "
        "Klammern)."
    )


#: A chant reference: repo path to a .gabc file OR an inline GABC block
#: (pasted notation travels inside the feast spec — ADR-0005).
GabcSource = Annotated[str, AfterValidator(_validate_gabc_source)]


def _validate_image_source(value: str) -> str:
    """Reject a ``data:`` URI that is malformed; pass anything else through.

    Format and existence checks stay in ``resolve``, which already words them
    per slot ("Rückseitenbild", "Bild der 3. Zusatzseite") and knows the
    .webp-conversion hint. The one thing worth catching here is a data URI
    that arrived broken — a truncated paste — since as a "path" it would
    otherwise produce a baffling file-not-found for a 2 MB filename.
    """
    if is_inline_image(value):
        decode_inline_image(value)  # raises InlineImageError (a ValueError)
    elif value.lstrip().lower().startswith("data:"):
        raise ValueError(
            "Der Wert beginnt mit „data:“, ist aber keine vollständige "
            "Base64-Bild-URI — erwartet wird „data:image/png;base64,“ (oder "
            "image/jpeg, application/pdf) und danach die Bilddaten."
        )
    return value


#: A picture reference: repo path to a .png/.jpg/.pdf OR an embedded image as
#: a ``data:`` URI (ADR-0019, what makes a bundled spec self-contained).
ImageSource = Annotated[str, AfterValidator(_validate_image_source)]

#: Antiphon/psalm pairs required per rite.
ANTIPHONAE_PER_RITE: dict[str, int] = {
    "romanum-1962": 5,
    "romanum-cum-precibus": 5,
    "monasticum": 4,
}

#: Rites that sing the Preces and the Pater noster aloud.
RITES_CUM_PRECIBUS = {"monasticum", "romanum-cum-precibus"}

#: Rites whose Vespers has a Responsorium breve (Roman Vespers has none —
#: it is a monastic-Office feature, see issue #30).
RITES_WITH_RESPONSORIUM = {"monasticum"}


class StrictModel(BaseModel):
    """Base model: unknown fields are errors (catches YAML typos)."""

    model_config = ConfigDict(extra="forbid")


class Notable(StrictModel):
    """Mixin for content-bearing propers: an optional provenance note,
    rendered as a LaTeX footnote where the item appears (ADR-0011)."""

    note: str | None = None


class OrdoItem(Notable):
    """Mixin for the propers that get a row in the Ordo table.

    The row's incipit is derived from the chant's own lyrics (ADR-0020),
    which is a good default and not an authority — the reviewing priest
    is. ``incipit:`` overrides the derivation for this element alone.
    """

    incipit: str | None = None


class AntiphonaCumPsalmo(OrdoItem):
    """One antiphon with its psalm: gabc + German + (psalm, tone) library key."""

    gabc: GabcSource
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None
    repetitio: str | None = None  # antiphon repeat incipit; default: first words of the gabc
    psalmus: int = Field(ge=1, le=150)
    tonus: str
    #: Optional assertion, never an input to typesetting: the EUOUAE the
    #: printed source shows for this antiphon (six whitespace-separated
    #: neumes, e.g. "h h g f gh g.f."). Mode plus differentia fully
    #: determine these notes, so this only cross-checks `tonus:` — a
    #: disagreement is an error (issue #33, ADR-0016).
    euouae: str | None = None


class Versus(Notable):
    """One numbered capitulum verse; the template typesets the superscript."""

    n: int = Field(ge=1)
    text: str
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None


class Capitulum(StrictModel):
    ref: str
    versus: list[Versus] = Field(min_length=1)


class Responsorium(OrdoItem):
    gabc: GabcSource
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None


class Hymnus(OrdoItem):
    gabc: GabcSource
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: list[str] | None = None  # one entry per stanza


class Versiculus(OrdoItem):
    gabc: GabcSource
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None


class AntiphonaAdMagnificat(OrdoItem):
    gabc: GabcSource
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None
    repetitio: str | None = None
    #: Optional assertion, never an input to typesetting: the EUOUAE the
    #: printed source shows for this antiphon (six whitespace-separated
    #: neumes, e.g. "h h g f gh g.f."). Mode plus differentia fully
    #: determine these notes, so this only cross-checks `tonus:` — a
    #: disagreement is an error (issue #33, ADR-0016).
    euouae: str | None = None


class Magnificat(StrictModel):
    antiphona: AntiphonaAdMagnificat
    tonus: str


class Oratio(Notable):
    text: str
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None


class BackCoverQuote(Notable):
    """Latin quote + German translation; newlines are line breaks."""

    text: str
    #: German translation. Required unless the feast is `latin_only`
    #: (ADR-0025); FeastSpec._german_present_unless_latin_only enforces that,
    #: because a nested model cannot see the top-level flag.
    de: str | None = None
    motto: str | None = None  # red-italic closing sentence (per-feast option, not standard)
    motto_de: str | None = None
    citation: str | None = None  # source line, typeset italic, e.g. "Regula Benedicti, cap. XLIII"


#: Named `pgfornament`-based border styles for the back-cover image (ADR-0013),
#: plus "gilded" — a photographed gold frame, nine-slice tiled (ADR-0014).
BackCoverBorder = Literal["none", "vine", "grapevine", "knot", "feather", "gilded"]

#: Thickness preset for the "gilded" border (ADR-0014); ignored by the
#: ADR-0013 vector styles, whose sizes are fixed, visually-approved presets.
BackCoverBorderSize = Literal["normal", "large", "extra-large"]


class BackCover(StrictModel):
    image: ImageSource
    credit: str  # bottom line, tiny italic — always present
    quote: BackCoverQuote | None = None
    text: str | None = None  # free text, alternative to a quote block
    border: BackCoverBorder = "gilded"  # optional ornamental frame, see ADR-0013
    border_size: BackCoverBorderSize = "normal"  # "gilded" thickness only, see ADR-0014

    @model_validator(mode="after")
    def _exactly_one_of_quote_or_text(self) -> BackCover:
        if (self.quote is None) == (self.text is None):
            raise ValueError(
                "Auf der Rückseite muss entweder ein Zitat („quote“) oder "
                "freier Text („text“) stehen — genau eines von beiden."
            )
        return self


class FillerBlock(StrictModel):
    """One prose block of a filler page: optional red heading, then text."""

    heading: str | None = None
    text: str


class FillerPage(StrictModel):
    """A hand-written flavour page (Guéranger excerpts, a saint's legend, …).

    Plain text only, like every other text field (ADR-0002): the ornament
    rules, the small-caps title and the red block headings live in
    ``partials/filler.tex.j2``. ``image`` is a real field rather than markup
    inside the prose precisely so that resolution records it as an asset —
    a raw ``.tex`` filler page's own ``\\includegraphics`` is not discovered.
    """

    title: str | None = None
    subtitle: str | None = None  # attribution under the title; newlines are line breaks
    blocks: list[FillerBlock] = []
    citation: str | None = None  # flush-right source line, tiny italic
    image: ImageSource | None = None
    caption: str | None = None  # only meaningful with an image

    @model_validator(mode="after")
    def _has_something_to_print(self) -> FillerPage:
        if not self.blocks and self.image is None:
            raise ValueError(
                "Eine Zusatzseite braucht Inhalt — entweder Textblöcke "
                "(„blocks“) oder ein Bild („image“)."
            )
        return self

    @model_validator(mode="after")
    def _caption_needs_an_image(self) -> FillerPage:
        if self.caption is not None and self.image is None:
            raise ValueError(
                "Die Bildunterschrift („caption“) steht ohne Bild („image“) da."
            )
        return self


class FeastSpec(StrictModel):
    """One celebration = one YAML file. Always self-contained (no commons/includes)."""

    title: str
    subtitle: str | None = None
    #: First/Second Vespers. `None` only for `rank == "Simplex"` (ADR-0015
    #: update, 2026-07-25) — a Simplex feast has exactly one Vespers, so
    #: the distinction is inapplicable, not merely unprinted.
    vesperae: Literal["I", "II"] | None = None
    header: str
    rank: Rank
    date: datetime.date  # when it is actually sung
    liturgical_date: datetime.date | None = None  # proper date, if transferred
    rite: Rite
    source: str

    #: Which German psalter translation the psalm/Magnificat verses use
    #: (variant files chant/psalmi/<n>/de-<versio>.yaml, e.g. "eu1980",
    #: "eu2016"). Default: eu1980, else eu2016, else the single available.
    psalter_de: str | None = None

    antiphonae: list[AntiphonaCumPsalmo]
    capitulum: Capitulum
    responsorium: Responsorium | None = None
    hymnus: Hymnus
    versiculus: Versiculus
    magnificat: Magnificat
    oratio: Oratio
    antiphona_bmv: str  # ordinarium chant name, e.g. "salve-regina-simple"

    #: Optional flavour pages before the back cover. Normally structured
    #: `FillerPage` entries; a bare path is the power-user escape hatch from
    #: ADR-0001/0002 — a hand-authored .tex page, copied verbatim, which must
    #: be self-contained (nothing it references is discovered as an asset).
    filler: list[FillerPage | Path] = []
    back_cover: BackCover
    drollery: str = "auto"  # auto (seeded by date) | none | <filename in images/drollery/>

    #: Mark every page as a draft (ADR-0021). `--draft` on the command line
    #: sets the same thing; either alone suffices and neither can clear the
    #: other — a final booklet means removing this field.
    draft: bool = False

    #: Print the booklet as a Kurzfassung (ADR-0022): the first verse of each
    #: psalm and of the Magnificat notated, every later verse as pointed
    #: Latin text, and one notated stanza of the hymn. Unlike `draft:`, the
    #: command line can also clear this (`--no-compact`) — both the full and
    #: the compact print of one celebration are wanted.
    compact: bool = False

    #: Set the booklet in Latin alone (ADR-0025): no antiphon, capitulum, hymn,
    #: responsory, versicle or oration translation, and no interlinear German
    #: under the psalm and Magnificat verses. The booklet's own rubrics and
    #: headings stay German — they name the parts of the office, they are not a
    #: translation of what is sung.
    #:
    #: There is deliberately no `--latin-only` flag: unlike a draft or a
    #: Kurzfassung, this is a standing property of a community, not a choice
    #: made per printing. It also relaxes every `de` field to optional, which a
    #: command-line flag must never do — the browser form validates a spec
    #: against this schema and has no flags to pass (ADR-0004).
    latin_only: bool = False

    @model_validator(mode="after")
    def _german_present_unless_latin_only(self) -> FeastSpec:
        """Every translation must be there unless the feast is Latin-only.

        The `de` fields are declared optional so that a Latin-only spec can
        simply omit them; for every other spec they are required, and this is
        where that is enforced. Reporting all of them at once matters — an
        author filling in a new feast should see the whole list, not one field
        per run.
        """
        if self.latin_only:
            return self
        missing = [
            f"Antiphon {index}" for index, ant in enumerate(self.antiphonae, start=1)
            if ant.de is None
        ]
        missing += [
            f"Capitulum, Vers {versus.n}" for versus in self.capitulum.versus
            if versus.de is None
        ]
        if self.responsorium is not None and self.responsorium.de is None:
            missing.append("Responsorium breve")
        if self.hymnus.de is None:
            missing.append("Hymnus")
        if self.versiculus.de is None:
            missing.append("Versiculus")
        if self.magnificat.antiphona.de is None:
            missing.append("Antiphon zum Magnificat")
        if self.oratio.de is None:
            missing.append("Oratio")
        if self.back_cover.quote is not None and self.back_cover.quote.de is None:
            missing.append("Rückseiten-Zitat")
        if missing:
            raise ValueError(
                "Ohne „latin_only: true“ braucht jeder Text eine deutsche "
                "Übersetzung („de:“) — sie fehlt bei: " + ", ".join(missing) + "."
            )
        return self

    @model_validator(mode="after")
    def _antiphonae_count_matches_rite(self) -> FeastSpec:
        expected = ANTIPHONAE_PER_RITE[self.rite]
        if len(self.antiphonae) != expected:
            raise ValueError(
                f"Der Ritus „{self.rite}“ hat {expected} Antiphonen mit Psalmen — "
                f"in der Datei stehen {len(self.antiphonae)}."
            )
        return self

    @model_validator(mode="after")
    def _responsorium_matches_rite(self) -> FeastSpec:
        needs_responsorium = self.rite in RITES_WITH_RESPONSORIUM
        if needs_responsorium and self.responsorium is None:
            raise ValueError(
                f"Der Ritus „{self.rite}“ braucht ein Responsorium breve — "
                f"in der Datei fehlt es."
            )
        if not needs_responsorium and self.responsorium is not None:
            raise ValueError(
                f"Der Ritus „{self.rite}“ hat kein Responsorium breve — "
                f"in der Datei ist trotzdem eines angegeben."
            )
        return self

    @model_validator(mode="after")
    def _vesperae_matches_rank(self) -> FeastSpec:
        if self.rank == "Simplex" and self.vesperae is not None:
            raise ValueError(
                "Bei „Simplex“ gibt es keine Erste/Zweite Vesper zu unterscheiden — "
                "das Feld „vesperae“ darf hier nicht gesetzt sein."
            )
        if self.rank != "Simplex" and self.vesperae is None:
            raise ValueError(
                "Das Feld „vesperae“ fehlt — nur bei „Simplex“ entfällt es."
            )
        return self

    @property
    def cum_precibus(self) -> bool:
        """Whether this rite sings Preces + Pater noster aloud."""
        return self.rite in RITES_CUM_PRECIBUS
