# libellus

Generates typeset booklets for **Vespers in the usus antiquior** — Gregorian
chant notation via [Gregorio](https://gregorio-project.github.io/), Latin and an
interlinear vernacular, ready to print and fold.

You describe a celebration in one YAML file. `libellus` resolves it against a
chant library, generates the psalm notation for whichever Liber Usualis tone you
name, renders LaTeX, compiles it, pads the page count to a multiple of four and
imposes the booklet.

It was written for a schola in Bremen and is used there for real; the two feasts
in `feasts/` are booklets that have actually been sung from. It is licensed
[0BSD](https://github.com/OmarEjjeh/libellus/blob/main/LICENSE) — do anything
you like with it, no attribution required.

## Contents

1. [What it produces](#what-it-produces)
2. [Requirements](#requirements)
3. [Install](#install)
4. [Quickstart](#quickstart)
5. [The feast spec](#the-feast-spec)
6. [The browser form](#the-browser-form)
7. [Choosing a Psalter](#choosing-a-psalter)
8. [Latin-only booklets](#latin-only-booklets)
9. [The Kurzfassung](#the-kurzfassung)
10. [Draft booklets](#draft-booklets)
11. [Bundling a feast](#bundling-a-feast)
12. [Transcribing text to gabc](#transcribing-text-to-gabc)
13. [Repository layout](#repository-layout)
14. [Working on libellus](#working-on-libellus)
15. [Releasing](#releasing)
16. [Bremen operations](#bremen-operations)
17. [Credits and licence](#credits-and-licence)

## What it produces

<!-- Absolute URLs on purpose: PyPI renders this file on the project page and
     resolves nothing relative to the repository. -->
<p align="center">
  <img src="https://raw.githubusercontent.com/OmarEjjeh/libellus/main/docs/images/cover.png" alt="Cover page: Vesperæ Primæ in Festo Sancti Lamberti, Episcopi et Martyris, with red ornamental rules" width="42%">
  &nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/OmarEjjeh/libellus/main/docs/images/psalm.png" alt="A psalm page: antiphon in Gregorian notation with a drop capital, then the psalm verses pointed to tone 8G" width="42%">
</p>

<p align="center"><sub>St. Lambert, Second Vespers — shown here as a
<a href="#latin-only-booklets">Latin-only</a> booklet.</sub></p>

Three PDFs per build: the booklet itself, a `-pdfjam` imposition for booklet
printing, and a `-pdfjam-duplex` variant that rotates every second page for
duplex printers without a binding-edge option.

A booklet contains the whole office in order — incipit, five antiphons each with
its psalm pointed to a chosen tone, capitulum, hymn, responsory (in the
monastic rite), versicle, the Magnificat with its antiphon, preces and Pater
noster where the rite has them, oration, conclusion, the seasonal Marian
antiphon, optional filler pages, and a back cover. Rubrics are red, postures and
who-sings-what are marked in the margins, and section dividers use
`pgfornament` motifs.

## Requirements

`libellus` is a Python package, but the typesetting is done by external tools it
calls. You need all of these on `PATH`:

| tool | why |
|---|---|
| **LuaLaTeX** with `--shell-escape` | typesets the booklet |
| **Gregorio** / `gregoriotex` | sets the chant notation (ships with TeX Live) |
| **`pgfornament`**, `tikz`, `fontspec`, … | ornaments and layout (TeX Live) |
| **Node.js** or **Bun** | runs the psalm-tone engine, on every build |
| **`pdfjam`** | imposes the booklet (TeX Live) |
| **`pdftk`** | rotates alternate pages for duplex printing |

Fonts: **EB Garamond**, **Charis SIL** (the interlinear translation face) and
**XITS** (for ✠). All three ship with TeX Live — as the packages `ebgaramond`,
`charissil` and `xits` — so nothing needs installing at the system level, and
the booklet sets the same on Linux as on macOS.

A full TeX Live install covers everything but Node.js and `pdftk`. On Debian or
Ubuntu: `apt install texlive-full nodejs pdftk-java`. On macOS: MacTeX, then
`brew install node pdftk-java`.

Without LuaLaTeX on `PATH`, `libellus build` stops after staging and tells you
so; the staged folder has its own `Makefile`, so you can run `make` in it
wherever the tools do exist.

## Install

Install it with [uv](https://docs.astral.sh/uv/):

```
uv tool install libellus
```

This is the way to get `libellus`. It is a command-line tool, not a library you
import, so uv gives it an isolated environment of its own and puts the
`libellus` command on your `PATH` — nothing to activate, and no chance of
colliding with another project's dependencies. Later, `uv tool upgrade libellus`.

If your shell cannot find the command afterwards, run `uv tool update-shell`
once and open a new terminal.

<sub>For a one-off look without installing, `uvx libellus --help` runs it from a
throwaway environment. `pip install libellus` and `pipx install libellus` also
work, if that is the habit.</sub>

To work on it instead:

```
git clone https://github.com/OmarEjjeh/libellus
cd libellus
uv sync --all-groups
uv run libellus --help
```

In a clone, prefix the commands in this README with `uv run` — that is what
picks up your checkout rather than an installed copy.

The package carries everything that is *the tool*: the per-rite skeletons, the
chant library, the psalm-tone engine and the border artwork. It deliberately
carries **no German psalm translations** — see
[Choosing a Psalter](#choosing-a-psalter).

## Quickstart

`libellus` runs in a **working directory**, which is where it looks for your
content — feast specs, pictures, and a Psalter — and where it writes `build/`.
Everything else comes from the installed package.

```
libellus build feasts/2026-09-18-lambertus.yaml
```

That stages `build/2026-09-18-lambertus/` — the rendered TeX plus every asset it
references and a `Makefile` — compiles it, and imposes the result.

A minimal working directory looks like this:

```
my-parish/
├── feasts/
│   └── 2027-01-25-conversio-pauli.yaml
├── images/
│   └── conversio/back-cover.jpg
└── psalter/
    └── my-translation/…          ← see below
```

**One caveat if you cloned this repository:** the two feast specs in `feasts/`
reference the Einheitsübersetzung, which is not distributable and is not here
(ADR-0023). Out of the box you can build them only as
[Latin-only](#latin-only-booklets) booklets. Supply your own Psalter, or wait for
the public-domain German one — it is an open issue and the intended default.

## The feast spec

One YAML file describes one celebration and is always self-contained: no
includes, no inheritance. It is **plain text, never LaTeX** (ADR-0001/0002) —
everything about typesetting lives in the templates, and everything about *this
celebration* lives in the spec.

```yaml
title: Sancti Lamberti
header: S. Lambertus, Ep. et Mart.        # running header
rank: Semiduplex                          # closed vocabulary, ADR-0015
vesperae: II                              # First or Second Vespers
date: 2026-09-18                          # when it is actually sung
rite: romanum-cum-precibus                # which ordo
source: Antiphonale Romanum · mcmxlix     # printed on the cover

antiphonae:
  - gabc: chant/ant/omnes-sancti-quanta-passi.gabc
    de: Alle Heiligen, wie viele Qualen haben sie erlitten…
    psalmus: 109                          # Vulgate numbering
    tonus: 8G                             # mode + differentia, as the books print it
  # … five in the Roman rite, four in the monastic
capitulum:
  ref: Iesu Sirach 50, 5–10
  versus:
    - n: 5
      text: Qui præváluit amplificáre civitátem…
      de: Wie herrlich war er, umgeben vom Volk…
hymnus:
  gabc: chant/hymni/sanctorum-meritis.gabc
  de: ["…", "…"]                          # one entry per stanza
# … versiculus, magnificat, oratio, antiphona_bmv, back_cover
```

Key fields:

- **`rite`** — the ordo, which fixes the sequence of elements: `romanum-1962`,
  `monasticum`, or `romanum-cum-precibus` (the Bremen group's hybrid). It also
  decides how many antiphons there are and whether a responsory is sung.
- **`gabc:`** — either a path into the chant library or Gregorio notation pasted
  inline (ADR-0005). Inline notation is materialised at build time and behaves
  exactly like a library file.
- **`tonus:`** — a tone label the way the books print it: `8G`, `8 G`, `8G*`,
  `peregrinus`. Mode plus differentia fully determine the ending, so the EUOUAE
  cue is derived rather than typed (ADR-0016/0017).
- **`psalmus:`** — any psalm 1–150 in Vulgate numbering, plus the Magnificat.
  Nothing is pre-generated: the notation is produced on demand for whatever
  `(psalm, tone)` you ask for.
- **`note:`** — on any proper, a provenance footnote (ADR-0011): where this
  transcription or translation came from. It prints as a real footnote and
  survives a Latin-only booklet.
- **`image:`** — a path in your working directory, or a `data:` URI embedded in
  the spec itself (ADR-0019).

Every error is reported in German, all of them at once, naming the field.

## The browser form

`form/formular.html` is a single self-contained HTML file that composes and
loads feast specs in the browser, with an instant notation preview
(ADR-0003/0004). Open it directly — there is no server and no build step.

It reads its vocabularies (tone labels, ordinarium chants, chant and image
paths, which psalms have German) from a JSON data island embedded in the file.
Regenerate it whenever those change:

```
libellus export-form-data          # --check only reports staleness
```

## Choosing a Psalter

A **Psalter** is one translator's complete German for the sung verses: one
directory holding a file per psalm plus the Magnificat.

```
psalter/
└── eu1980/
    ├── 109.yaml
    ├── 110.yaml
    └── magnificat.yaml
```

```yaml
# psalter/eu1980/109.yaml
psalmus: 109
verses:
  1: So spricht der Herr zu meinem Herrn…
  2: …
```

One line per **sung** verse, including both Gloria Patri verses, in Vulgate
numbering and Vulgate verse boundaries — which differ from how modern
translations divide and number the psalms, so a translation usually has to be
re-cut editorially (ADR-0007).

A feast picks one with `psalter_de: eu1980`; without that field the first
available is used. **No Psalter ships with libellus**: the one Bremen prints from
is the Einheitsübersetzung, which is copyright Katholische Bibelanstalt and not
redistributable. So you either supply your own, or print
[Latin-only](#latin-only-booklets).

A public-domain German psalter is wanted and not yet done — it is an open issue
and the intended long-term default.

## Latin-only booklets

For a community that sings the office in Latin alone, and the way to use
`libellus` with no Psalter at all:

```yaml
latin_only: true
```

Every translation goes: the antiphons', capitulum's, hymn's, responsory's,
versicle's and oration's `de`, and the interlinear German beneath the verses.
Every `de` field becomes optional, so you simply leave them out.

The booklet's **German rubrics and headings stay** — „Schola", „Man steht",
„Alle — beide Seiten Vers um Vers im Wechsel". They name the parts of the office
and tell the congregation what to do; they are not a translation of anything
sung. Provenance footnotes stay too, for the same reason. (Latin rubrics are a
separate, larger job — see ADR-0012 on multi-locale support.)

There is deliberately no `--latin-only` flag: this is a standing property of a
community rather than a choice made per printing, and it relaxes what a valid
spec is, which the browser form has to be able to see (ADR-0025).

## The Kurzfassung

For singers who already know the office: the first verse of each psalm and of the
Magnificat in notation, every later verse as pointed Latin text with its German
beneath, and one notated stanza of the hymn (ADR-0022).

```
libellus build --compact feasts/2026-09-18-lambertus.yaml
```

`compact: true` in the spec does the same, and `--no-compact` overrides it —
unlike a draft, because the full booklet for visitors and the short one for the
schola are both wanted the same evening. They build into separate folders
(`build/<feast>-kurzfassung/`), so both can be printed.

The Magnificat is the exception: „Magníficat" is one word and cannot carry the
tone's cadence, so its first two verses share one system as the Liber prints
them — verse 2 beneath verse 1, reciting notes hollow. Those systems are
generated per tone and committed; after touching the generator, refresh them:

```
libellus magnificat-systems        # --check only reports staleness
```

To proofread that notation against a printed Liber, build the correction sheet —
all 33 tones at the booklet's own page size:

```
uv run scripts/magnificat-proof/generate.py
```

## Draft booklets

To send a booklet round for corrections, build it as a draft — every page then
carries `PRO MANUSCRIPTO` and the time it was made, so nobody prints it by
mistake (ADR-0021):

```
libellus build --draft feasts/2026-09-18-lambertus.yaml
```

`draft: true` in the spec does the same permanently, and is what the form sets.
Either alone suffices; a final booklet means removing the field.

## Bundling a feast

To hand a feast to someone else, pack it into a single file — every chant and
picture embedded, no outside references (ADR-0019):

```
libellus bundle feasts/2026-07-10-benedictus.yaml
```

That file alone builds the booklet. It is an export, not an authoring format:
mostly base64, so keep editing the readable spec. Note that a bundle does **not**
embed the Psalter — the German verses still come from your working directory.

## Repository layout

```
feasts/                     the feast specs — the artifact you edit
form/formular.html          self-contained browser form
images/<feast>/             pictures, one folder per celebration
psalter/<versio>/           German translations (not in the package)
src/libellus/
├── cli.py schema.py resolve.py render.py stage.py compile.py …
├── template/               per-ordo skeletons and shared partials
├── chant/                  the chant library — all gabc lives here
│   ├── ant/ hymni/ vers/ resp/       propers by genre
│   ├── ordinarium/                   the fixed parts
│   ├── psalmi/ magnificat/           incipit table, committed systems
├── images/borders/         gilded back-cover border tiles
└── psalm-library/          the vendored jgabc psalm-tone engine
docs/adr/                   architecture decisions — read these
CONTEXT.md                  the domain glossary
archive/                    retired offices, kept for reference
```

The pipeline is **validate → resolve → render → stage → compile**. Resolution
records every file the TeX will read, so staging can copy exactly those into a
self-contained folder; `libellus/paths.py` decides, per asset, whether it comes
from the package, the build cache or your working directory (ADR-0024).

## Working on libellus

```
uv sync --all-groups
uv run playwright install chromium       # for the form tests
uv run pytest
```

The suite needs no LaTeX: the build tests stop before compiling. It resolves its
German against a synthetic **probe Psalter** under `tests/fixtures/psalter/`, so
it gives the same answers with or without a real Psalter present, and never
asserts against copyrighted text.

Two things worth knowing before touching the templates:

- **The layout is sensitive to the preamble's line structure.** Adding even a
  LaTeX comment there has repaginated a booklet. When changing anything
  typographic, compare page-by-page renders before and after rather than trusting
  that a comment is inert.
- **A LaTeX `%` comment in a template still reaches the `.tex`.** Use `\#{ … }`
  for a comment that should not be emitted, and remember that template
  conditionals run at render time while `\if…` runs at compile time.
- **A font named in the preamble is a dependency.** Name only fonts TeX Live
  ships, or the tool stops working on everyone else's machine — the template
  once asked for a macOS-only face and no booklet could be built on Linux at
  all. `docker run --rm texlive/texlive:latest luaotfload-tool --find="<name>"`
  answers whether CI will find it.

Commit messages are [Conventional Commits](https://www.conventionalcommits.org/),
and that is load-bearing: `commitizen` derives the version and the changelog from
them.

## Releasing

```
uv run cz bump             # writes the version + CHANGELOG.md, commits, tags
git push --follow-tags     # pushing the tag is what publishes
```

Pushing the tag triggers `release.yml`, which builds the artifacts, installs the
wheel into a clean environment, sets a whole booklet from it, and only then
publishes to PyPI via Trusted Publishing. Releases are deliberate: nothing is
published by merging (ADR-0023).

While the feast-spec format settles, the project stays on `0.x` — a breaking
change bumps the minor. Set `git config push.followTags true` once so a tag is
never left behind.

## Bremen operations

Notes for whoever keeps the Bremen booklets going.

- **Two clones.** `libellus`, plus the private `psalter-eu` repository checked
  out into `psalter/` — `git clone <psalter-eu> psalter` from the root of this
  one. Without the second, only Latin-only booklets build. That clone is also
  the psalter's only backup: the verse boundaries in it were re-cut psalm by
  psalm against the Vulgate division, and no machine can redo that from the
  source text. Commit and push changes to it like any other repository.
- **The psalter is Einheitsübersetzung** and must not be published: not in this
  repository, not in the wheel, not in a bundle sent outside the parish.
  `psalter/` is gitignored and CI fails if any of it reaches an artifact.
- **The state of work in progress** is the pinned map issue,
  [#54](https://github.com/OmarEjjeh/libellus/issues/54) — what shipped, what is
  next, and what is still unresolved. Every other issue hangs off it.
- **The Benedict feast pins `psalter_de: eu2016`**, the hand-made re-cuts its
  printed booklet was set from. Leave it pinned.
- **Adding a picture:** `.gitignore` deliberately ignores `*.png` and `*.jpg`, so
  a new image is invisible until you add it explicitly with `git add -f`. If a
  feast will not build on a fresh clone, this is why.
- **Before printing:** build without `--draft`, check the page count is a
  multiple of four, and print the `-pdfjam-duplex` PDF on a duplex printer
  without a binding-edge option, or `-pdfjam` otherwise.

## Credits and licence

The code and templates are
[0BSD](https://github.com/OmarEjjeh/libellus/blob/main/LICENSE). The repository
also carries third-party material under its own terms — GregoBase's CC0 chant,
the public-domain Clementine psalter, Ben Bloomfield's Unlicense psalm-tone
engine, the border artwork and the hymn translations. All of it is listed, with
what the licence does and does not cover, in
[CREDITS.md](https://github.com/OmarEjjeh/libellus/blob/main/CREDITS.md).

Decisions live in
[`docs/adr/`](https://github.com/OmarEjjeh/libellus/tree/main/docs/adr) and the
domain vocabulary in
[`CONTEXT.md`](https://github.com/OmarEjjeh/libellus/blob/main/CONTEXT.md). If
you are picking this up cold, read ADR-0001 and ADR-0024 first: what a feast
spec is, and where the files come from.
