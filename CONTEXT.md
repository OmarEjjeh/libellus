# Vesper — Booklet Generator

Generates typeset Vespers booklets (LaTeX + Gregorian chant notation) for a
schola in Bremen from declarative feast descriptions, designed to remain
operable by non-technical successors. See `docs/adr/` for decisions.

## Language

**Feast spec**:
One YAML file describing one celebration, always self-contained.
_Avoid_: feast file, config, spec file

**Libellus**:
The tool that turns a feast spec into the finished booklet PDFs.
_Avoid_: generator, pipeline, vespers-tool

**Ordo**:
Which order of service a feast follows: `romanum-1962`, `monasticum`, or
`romanum-cum-precibus` (the group's hybrid).
_Avoid_: rite variant, liturgy type (the YAML field is named `rite`)

**Skeleton**:
The per-ordo template that fixes the sequence of booklet elements; it has
no content of its own.
_Avoid_: master template, layout

**Partial**:
A template fragment holding the typesetting for one booklet element.
Partials own all styling; the feast spec owns only text and structure.
_Avoid_: snippet, block

**Propers**:
The chants and texts specific to one feast (antiphons, capitulum, hymn,
responsory, versicle, Magnificat antiphon, oration). They travel inside
the feast spec, not in a shared library. Not every proper exists in every
`Ordo` — see **Responsorium breve**.
_Avoid_: feast content, variable parts

**Responsorium breve**:
The short responsory after the capitulum. Present only in `monasticum`
Vespers — the Roman rite (`romanum-1962`, `romanum-cum-precibus`) has none
at Vespers, only at the Little Hours and Compline. Absent by rite, not by
feast choice: the field is forbidden, not merely optional, outside
`monasticum`.
_Avoid_: implying it's available-but-skippable in every ordo

**Ordinarium**:
The fixed chants and texts shared by every Vespers (Deus in adiutorium,
Pater noster, Benedicamus Domino, …), kept once in the repo.
_Avoid_: commons (that word means shared propers like the Common of
Martyrs, which the project deliberately has no mechanism for)

**Zusatzseite** (filler page):
A flavour page between the office and the back cover — excerpts about the
feast, a legend, an image with its caption. Structured plain text like every
other field (ADR-0018); a hand-written `.tex` page is the remaining escape
hatch. Distinct from the ornament-only pages the booklet adds by itself to
reach a page count divisible by 4, which are padding, not content.
_Avoid_: trivia page, appendix

**Bündel** (bundle):
A self-contained copy of a feast spec, produced by `libellus bundle`: every
chant reference replaced by its notation, every picture by a `data:` URI, so the
one file plus the program is a booklet (ADR-0019). An export for archiving,
emailing or attaching to an issue — `feasts/*.yaml` stay path-referencing and
readable, which is what a maintainer edits.
_Avoid_: export, archive, self-contained spec (as a noun)

**Entwurf** (draft):
A booklet built to be read and corrected rather than used: every page carries
`PRO MANUSCRIPTO` and the moment the draft was created. Strictly a property of
a copy in circulation rather than of the celebration, yet still recorded in the
feast spec — so a spec passed on stays a draft in the recipient's hands
(ADR-0021). Marking one is possible from anywhere; unmarking it only in the
spec.
_Avoid_: Probedruck (that is a proof of the *printing*, a later stage);
Vorschau; draft as prose (only the field is named `draft:`)

**Kurzfassung** (compact booklet):
A booklet for singers who know the office: the first verse of every psalm is
notated, every verse after it printed as pointed Latin with its German beneath,
the hymn keeps one notated stanza, and a canticle prints its first two verses as
a **Two-verse system** (ADR-0022).
A variant of a copy, not of the celebration, so — unlike an **Entwurf** — the
command line can both set it (`--compact`) and clear it (`--no-compact`), since
the full and the compact print are both wanted the same evening. Declares itself
on the cover as `Editio brevior`.
_Avoid_: Kompaktfassung, Kurzausgabe (implies a separate edition, which it is
not — the booklet's structure is unchanged); abbreviated booklet

**Two-verse system**:
One line of notes carrying two verses of a canticle — verse 1's syllables where
they fall, verse 2's beneath them, the reciting notes hollow, and the notes verse
1 has no words for standing empty. The Liber Usualis's answer to a first verse
too short to show its own cadence („Magníficat"), and the only place in the
booklet where a score has two text lines. Generated per tone and committed
(`chant/magnificat/kurzfassung/`), since the two verses' text never varies;
absent for the ten tones whose first verse has its own solemn melody, which are
notated as two ordinary scores instead.
_Avoid_: double verse, combined score, formula table (that is a different device
— the tone printed without any text)

**Pointing**:
The marks that tell a singer how a psalm verse meets its cadence: `<b>` on the
accented syllable, `<i>` on the preparatory ones, `*` at the mediant, `†` at the
flex. Written into every generated verse gabc by the tone engine, so a notated
verse already prints it in the lyrics under its neumes — which is why a
**Kurzfassung** can drop the neumes and still set the same words the same way.
_Avoid_: Punktierung, accents, markup

**Versus**:
A numbered verse `{n, text, de}` inside the capitulum.
_Avoid_: verse line, paragraph

**Motto**:
The back cover quote's optional short red-italic closing sentence
(`motto`/`motto_de`) — a per-feast design choice, not standard.
_Avoid_: emphasis, highlight

**Citation**:
The back cover quote's optional italic source line, e.g. „Regula
Benedicti, cap. XLIII“.
_Avoid_: credit_title (dropped), reference

**Back-cover border**:
An optional ornamental frame around `back_cover.image` (`border:`,
default `gilded`): one of four `pgfornament`-based vector styles (`vine`,
`grapevine`, `knot`, `feather`, floating outside the image with a margin
— ADR-0013), or `gilded`, a photographed gold frame reassembled via
nine-slice tiling and sitting flush against the image (ADR-0014). The
`gilded` style's thickness is adjustable per feast via `border_size:
normal | large | extra-large` (default `normal`); the vector styles' sizes
stay fixed.
_Avoid_: frame style, image border (the YAML field is named `border`)

**Pause marks**:
The literal `†` and `*` characters typed in chant-adjacent prose, styled
rubric-red automatically.
_Avoid_: flex/mediant markup, LaTeX marks

**Versicle marks**:
The literal `℣.` and `℟.` characters typed in prose with a plain space
after them; the rendering binds them to the following word so a mark
never ends a line alone.
_Avoid_: V/R abbreviations, `~` markup

**Inline GABC**:
Chant notation pasted directly into a `gabc:` field instead of a repo
path (the field is a union of both); materialized as a `.gabc` file at
resolve time so staging and incipit derivation see a normal file.
_Avoid_: embedded score, gabc blob

**Psalter translation**:
One German rendering of the psalter as variant files
`chant/psalmi/<n>/de-<versio>.yaml` (`eu1980`, `eu2016`, …), selected per
feast via the optional `psalter_de:` field; default order eu1980 →
eu2016 → the single available variant.
_Avoid_: de.yaml (the old single-variant name), translation version

**Incipit**:
The opening words that stand for a whole chant on the `Ordo` page. Derived
per genre, never by one rule: antiphons, versicle and responsory by an
anti-dangling heuristic over the gabc lyrics; hymns by their first
metrical line; psalms from a fixed table keyed by Vulgate number, since a
psalm's incipit never varies by feast (ADR-0010, ADR-0020). Always
overridable per element via `incipit:` — the reviewing priest is the
authority, the heuristic only a default.
_Avoid_: first line (a hymn's first line is a different thing), title,
opening, cue (that's `Repetitio`)

**Repetitio**:
The cue printed after a psalm telling the schola how to resume its
antiphon. Sung text, not a reference label — which is why it takes the
same anti-dangling treatment as an `Incipit`, at four words rather than
three. Overridable via `repetitio:`.
_Avoid_: antiphon repeat, reprise, incipit (an `Incipit` is read, a
repetitio is sung)

**Dangling incipit**:
An `Incipit` or `Repetitio` whose last word demands a complement that
isn't there — `Cum palma ad`, `Omnes Sancti quanta`. The defect
ADR-0020's heuristic exists to prevent.
_Avoid_: truncation, bad cut

**Tonus**:
A psalm-tone label as printed in the Liber Usualis (e.g. `8G`, `1 D2`,
`peregrinus`), naming intonation/tenor/cadences for singing a psalm.
_Avoid_: melody, tone number

**Euouae**:
The termination cue printed at an antiphon's end — the vowels of
"saeculOrUm. AmEn", six syllables carrying the psalm tone's closing
cadence, so the schola can pitch the psalm that follows (in practice: they
whistle it). Fully determined by the `Tonus`: every one of the engine's 33
endings has a distinct EUOUAE, so a EUOUAE identifies its ending uniquely
and vice versa. Consequently it is always *derived*, never authored.
Where an antiphon's own `gabc:` already prints one — tagged
(`<eu>...</eu>`) or bare/untagged, both occur in the wild — it is kept as
transcribed; where it prints none, the ending's notes are appended to the
antiphon's *materialized* score only (ADR-0017). The optional `euouae:`
field is an **assertion**, not an input: it records what a printed source
shows, purely to cross-check `Tonus` — a disagreement is an error. A
EUOUAE cannot express a `Termination formula`, so it never drives
typesetting (ADR-0016, superseded).
_Avoid_: ending (ambiguous); termination override (the EUOUAE cannot
override anything — see `Termination formula`); differentia (that's the
tone's *label*, e.g. `8G`, of which the euouae is the audible realization)

**Termination formula**:
How the psalm-tone engine actually stores an ending: an accent-aware
template, not one note per syllable. A *reciting tone* (`r` suffix)
absorbs however many syllables precede the cadence, and `'` marks the
accented syllable — mode 8's `G` ending is `jr i j 'h gr g.`. This is why
the same ending fits verses of any length, and why a `Euouae` — the same
template already realized on six fixed syllables — cannot substitute for
it. Belongs to the vendored engine's tone table; this project never
authors one.
_Avoid_: termination (bare, ambiguous with the cadence itself); euouae

**Staging**:
Producing a self-contained build folder that compiles to the booklet
without libellus or the rest of the repo.
_Avoid_: export, bundling

**The form**:
The single self-contained HTML page that composes and edits feast specs
entirely in the browser; it is a full editor, never generate-only.
_Avoid_: GUI, web app, wizard

**Data island**:
The generated block of variable vocabularies (valid toni, ordinarium
names, psalms with German) embedded in the form.
_Avoid_: manifest, config blob

**Static API**:
The public data repo serving vocabulary-heavy data (GregoBase chants,
Clementine Bible) as a compact index plus one small file per item, so
the form fetches only what a session touches. Public-domain/CC0 content
only.
_Avoid_: mini server, proxy, backend

**Companion data**:
The same data files placed in `form/daten/` next to the form as the
offline fallback for the static API; their absence never breaks the
form's core.
_Avoid_: local cache, bundle

**Numbered paste**:
Pasting scripture text with its verse numbers left in, which the form
splices into versus rows at the standalone numbers.
_Avoid_: bulk import, smart paste

**Rank**:
A feast's liturgical class, printed on the cover (`rank:`). One value
from exactly one of two closed vocabularies (ADR-0015): pre-1955
(`Duplex I classis`, `Duplex II classis`, `Duplex majus`, `Duplex`,
`Semiduplex`, `Simplex`, `Feria` — dated to 1955, not 1960, since Pius
XII abolished `Semiduplex` that year) or Codex Rubricarum 1960 (`I classis`
…`IV classis`). Chosen freely per feast, independent of `rite`. Two
further historical systems (the Calendarium Romanum 1970 and the German
regional calendar) are documented in ADR-0015 for cross-reference only —
never selectable or stored, since this project never typesets from Novus
Ordo books. A `Simplex` feast has exactly one Vespers, so the First/Second
distinction is inapplicable, not merely unprinted: `vesperae` must be
absent for `Simplex` and is required for every other rank (schema-enforced,
ADR-0015 update); the form's `vesperae` select stays disabled rather than
unmounted (avoids the field below it reflowing), and both the cover and
the running header drop the First/Second qualifier for `Simplex`.
_Avoid_: class, classis (the YAML field is named `rank`); conflating with
**Commemoratio** below

**Commemoratio**:
A saint's antiphon+versicle+oration appended after a higher-ranking day's
own office (e.g. a Sunday's), rather than that saint having its own
primary Vespers. Not a `Rank` value — structurally a different feature,
not yet implemented (see IDEAS.md).
_Avoid_: treating it as another rank level

**Psalter**:
One translator's complete German for the sung verses — one directory,
`psalter/<versio>/`, holding a file per psalm plus the Magnificat. Chosen
per feast with `psalter_de:`, and supplied alongside a working directory
rather than shipped with **Libellus**: none is redistributable, so a fresh
install has no Psalter at all (ADR-0024).
_Avoid_: translation files, de-files, the German (a Psalter is one whole
thing, not a scattering of per-psalm files)

**Latin-only**:
A booklet printed without any vernacular: no translation of the antiphons,
capitulum, hymn, responsory, versicle or oration, and no interlinear German
under the verses. Its German **rubrics** and headings remain — they name the
parts of the office and direct the congregation, they translate nothing. A
standing property of a community, declared as `latin_only:` in the feast
spec, never chosen per printing (ADR-0025).
_Avoid_: Latin edition, monolingual, "no German" (the rubrics are German)
