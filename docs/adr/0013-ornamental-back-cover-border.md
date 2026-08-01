# ADR-0013: Ornamental border option for the back-cover image

Date: 2026-07-24
Status: accepted

## Context

The back cover's image (`back_cover.image`) renders bare — a plain
`\includegraphics`, no frame of any kind (`template/partials/backcover.tex.j2`).
Omar wanted an option to add an ornamental border around it, having seen a
suggestion elsewhere to use `pgfornament` (already a project dependency,
used throughout for the section-divider ornaments) with `pgfornament`'s
corner motifs positioned via TikZ.

Explored with a grilling session plus several rounds of rendered sample
PDFs, each built directly around the real Lambert back-cover image so
the decision was made on the actual artifact, not an abstract gallery:

1. **First attempt (rejected):** corner ornaments overlaid directly on
   top of the image's own corners. Wrong on both counts Omar actually
   asked for — the ornaments bled *into* the picture instead of framing
   it, and lone corners without connecting edges don't read as a frame.
2. **Second round:** corners held *outside* the image via a fixed
   margin, connected by `\pgfornamenthline`/`\pgfornamentvline` along
   all four edges — mirrors `pgfornament`'s own documented "poem in a
   frame" example (`ornaments.pdf`, "Application: Frame around a text").
   Four combinations approved: corner 61 + line 87, corner 63 + line 87,
   corner 41 + line 89, corner 131 + line 80.
3. **Third round (rejected in full):** a dozen more corner styles with a
   bare straight rule instead of an ornamented line, plus a heavier
   scrollwork connecting line (ornament 46). None improved on the four
   already approved.

## Decision

**A reusable "framed image" macro** wrapping `\includegraphics` in a
`tikzpicture`: an image node, four corner `\pgfornament`s anchored to
that node's corners but shifted outward by a fixed margin (never
overlapping the image), and `\pgfornamenthline`/`\pgfornamentvline`
connecting them along all four edges. This is the first use of TikZ in
this project (`\usepackage{tikz}` + `\usetikzlibrary{calc}`, new
preamble dependency) — `pgfornament`'s own corner-placement macros
already depend on it internally, so this only makes that dependency
explicit rather than introducing a new *kind* of tool.

**Four named styles**, all in `rubricred` (no new accent color):

| Key | Corner ornament | Line ornament | Character |
|---|---|---|---|
| `vine` | 61 | 87 | leafy scrollwork (pgfornament's own worked example) |
| `grapevine` | 63 | 87 | grape-cluster variant of `vine` |
| `knot` | 41 | 89 | angular knotwork corner, thin minimal line |
| `feather` | 131 | 80 | feather/wing flourish, bolder bead-shaped line |

**New optional per-feast field**: `back_cover.border: none | vine |
grapevine | knot | feather`, default `none`. Modeled exactly like
`rite`/`vesperae` — a Pydantic `Literal`, curated German error message
for an invalid value — so existing feasts (`smoke-benedictus.yaml`, the
Lambert draft) are unaffected until a maintainer opts in.

Rejected:

- **Corners alone, overlaid on the image** — the original suggestion;
  bleeds into the picture, doesn't frame it. The whole reason for this
  ADR.
- **Gold/Goldenrod accent color** (the AI suggestion that started this) —
  breaks the project's single-accent-color (`rubricred`) rule used
  everywhere else in the booklet.
- **Always-on template constant, no per-feast choice** — rejected in
  favor of the `drollery` precedent: this is feast-specific decoration
  tied to a specific image, not structural chrome like the section
  dividers.
- **Numeric style selector** (`border: 3`) — opaque to a future
  non-technical maintainer reading the YAML; contradicts the same
  "non-programmer can navigate the repo" reasoning already applied to
  back-cover image filenames (deliberately human-readable, not
  content-hashed). Named keys instead.
- **Free choice of any of `pgfornament`'s ~196 motifs** — over-scoped
  for what was actually asked; narrowed to four, visually reviewed
  against the real image before being locked in.
- **Plain rule (no corner ornament) and the heavier scrollwork line**
  (ornament 46) — both built and reviewed, neither improved on the four
  finalists.

## Consequences

- `schema.py`: `BackCover.border: Literal["none", "vine", "grapevine",
  "knot", "feather"] = "none"`.
- `template/partials/preamble.tex.j2`: add `\usepackage{tikz}` +
  `\usetikzlibrary{calc}`.
- A new macro (defined in the preamble or a dedicated partial) taking
  the style key and the image node, implementing the four
  corner+line combinations above; invoked conditionally from
  `backcover.tex.j2` when `border != "none"`.
- `form/formular.html`: new select field for `back_cover.border`,
  mirroring the existing `rite` dropdown pattern.
- `resolve.py`: no cross-file check needed — the value is a closed
  enum, already validated by Pydantic; it passes through to the
  template context unchanged.
