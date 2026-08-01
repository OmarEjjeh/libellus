# ADR-0014: Photographed gold frame as a second back-cover border technique

Date: 2026-07-25
Status: accepted

## Context

ADR-0013 gave the back cover four vector (`pgfornament`) border styles —
corner ornaments plus a connecting line, in `rubricred`. Omar found the
result "kind of flat" and had separately discussed a different technique:
photographing a real gold baroque frame and reassembling it around any
image via nine-slice framing (fixed corner tiles + tiled/stretched edge
tiles — the same idea as CSS `border-image` or Android 9-patch), rather
than vector line-art.

Explored with a grilling session plus several rounds of rendered sample
PDFs built directly against the real Lambert back-cover image, same as
ADR-0013's process:

1. **First attempt (superseded):** one corner + one edge tile cropped from
   the source photo (`frame.jpg`), mirrored/rotated via TikZ
   (`\reflectbox`/`\scalebox`/`\rotatebox`) for the other 3 corners and 3
   edges — matching the originally-discussed technique. Rejected on
   review: the source photo has a real, un-uniform directional gloss
   highlight (~2x brightness swing across one edge), so a mirrored tile
   visibly clashed with the real corners' own lighting. The initial crop
   also left a visible white gap between frame and image (crop included
   ~30% of the tile as unwanted interior padding beyond the frame's real
   inner edge).
2. **Second round:** cropped all 4 real corners and all 4 real edges
   directly from the photo (no mirroring/rotation), zero-padding at the
   true inner boundary. Fixed the gap and most of the lighting mismatch,
   but a hard tiling seam remained wherever a single repeated edge tile
   met a corner (obvious at 300dpi zoom, most visible top-right).
   A global flat-field lighting correction of the whole source photo was
   tried and improved evenness, but a residual seam remained at the
   corner junction — set aside once round 3 solved it more directly.
3. **Third round (adopted):** each edge sliced into several *consecutive
   real segments* of the source photo (13 for top/bottom, 11 for
   left/right — see Decision), rather than one tile repeated. Displayed
   tiles are sampled proportionally across that sequence so the segment
   touching a corner is always the segment actually adjacent to that
   corner in the photograph — the real gradient carries through and the
   hard seam disappeared, with no lighting-correction hack needed.
4. **Corner color-match:** the NW and SE corners still read slightly off
   against their immediate edge neighbours (a corner is a 45°-mitred
   joint, physically catching studio light differently than the flat
   run beside it). Colour-matched each corner's mean RGB to the average
   of its two neighbouring edge segments. SE now blends seamlessly; NW
   still shows a faint residual contrast difference (its neighbours lack
   NW's broad highlight band — a texture/contrast mismatch, not a
   colour-average one) — accepted as an inherent limit of using one real
   photograph's corner as-is, not a bug.
5. **Edge-to-edge crossfade:** sampling segments proportionally still
   skips some real segments when fewer display tiles are needed than
   source segments exist, leaving a faint phase jump in the repeating
   motif at each skip. Fixed with an alpha crossfade: interior tiles (not
   the corner-facing ends of the first/last segment, which stay untouched)
   get a `-feather` variant with alpha-faded tiling-direction margins,
   rendered ~30% wider so neighbours overlap and blend instead of
   butting with a hard cut.

## Decision

**A second back-cover-border technique**, added as a new value in the
*same* `back_cover.border` enum from ADR-0013 (`none | vine | grapevine |
knot | feather | gilded`) — one closed choice from the feast-author's
point of view, even though the two techniques are wholly different
underneath (vector ornaments vs. photographed nine-slice tiles).

**`gilded`**: a `\goldframedimage` TikZ macro (new, in
`template/partials/preamble.tex.j2`, alongside ADR-0013's `\framedimage`)
built from a single source photo (`images/borders/gilded-source.jpg`, a
gold gallery-frame product photo), pre-cropped into:

- **4 corner tiles** (`gilded-corner-{nw,ne,sw,se}.png`), each a real
  photographed corner — no mirroring or rotation, and no shared tile.
- **Edge tiles sliced into real consecutive segments**, not one tile
  repeated: 13 segments each for top/bottom (`gilded-edge-{top,bottom}-
  0..12.png`), 11 each for left/right (`gilded-edge-{left,right}-
  0..10.png`), plus a `-feather` variant of every segment (alpha-faded
  tiling-direction margins) for whichever segment ends up an interior
  tile at render time.

Unlike ADR-0013's styles (held outside the image by a margin), the gilded
frame sits **flush** against the image — corners and edges touch the
image's own edge with zero gap, wrapping it like a real physical frame.
The corner/edge tiles were cropped at the frame's *exact* measured inner
boundary (zero interior padding) specifically to make this possible.

At render time, `\goldframedimage{<thickness>}{<\includegraphics ...>}`:
measures the actual placed image box (`\sbox`/`\wd`/`\ht`/`\dp`, same
trick as the original nine-slice proposal), places the 4 corners flush at
its corners, then tiles each edge by picking `round(edge length / nominal
tile width)` display tiles and sampling that many segments proportionally
across the available real sequence (segment 0 and the last segment are
always used at the two ends, so they always meet their real corner
correctly) — the first/last display tile always uses the plain segment
file (preserving the corner boundary exactly), interior tiles use the
`-feather` variant rendered wider so they crossfade into their neighbours.

**Frame thickness** is a per-feast field, `back_cover.border_size: small |
normal | large` (default `normal`), mapped in `backcover.tex.j2` to
`1.0cm | 1.6cm | 2.2cm` — unlike ADR-0013's per-style margins, which stay
fixed template constants (those four combinations were already visually
approved as a set; the gilded frame's single style benefits from letting
an author shrink or enlarge it per feast instead). The height cap
subtracts `border_size * 2` (frame added above and below the image) via
`\dimexpr`. Only meaningful when `border: gilded`; harmless no-op
otherwise. Note for future template edits: e-TeX's `\dimexpr` requires
`<dimen>*<integer>` order for multiplication — `\VAR{gilded_thickness}*2`
works, `2*\VAR{gilded_thickness}` raises "Illegal unit of measure".

Rejected:

- **Mirroring one corner + one edge tile** — the originally-discussed
  technique. Visibly mismatches the source photo's own directional gloss
  highlight; a real frame's 4 corners are not interchangeable once
  lighting is involved.
- **A single repeated edge tile** (even using a real, non-mirrored crop)
  — creates a hard seam at every corner junction and, when sampled
  proportionally to fit a target length, phase-jumps in the repeating
  motif wherever a segment is skipped.
- **Global flat-field lighting correction of the source photo** — tried
  first per Omar's request to test the simpler multi-segment approach
  before reaching for it; the multi-segment approach alone fully solved
  the seam problem, so the correction step was dropped as unnecessary
  complexity.
- **Fully fixing the NW corner's residual contrast mismatch** — a
  texture/highlight difference, not a colour-average one; further
  correction would mean locally suppressing the photo's own highlight,
  which starts to look like retouching rather than colour-matching.
  Accepted as-is.

## Consequences

- `schema.py`: `BackCoverBorder` gains `"gilded"`; new
  `BackCoverBorderSize = Literal["small", "normal", "large"]` field,
  `back_cover.border_size`, default `"normal"`.
- `resolve.py`: `GILDED_BORDER_ASSETS` (4 corner + 96 edge-tile files —
  48 plain + 48 `-feather`) added to the build's asset set whenever
  `border == "gilded"`.
- `template/partials/preamble.tex.j2`: `\goldframedimage` macro plus 4
  small helper macros (`\GfTopEdgeTile` etc.) that pick the plain vs.
  `-feather` tile and width. The plain/interior choice had to be factored
  into ordinary macros rather than a bare `\ifnum`/`\else`/`\fi` directly
  inside TikZ's `\foreach` body — `\foreach`'s own body-scanning mishandles
  a raw conditional there ("Incomplete `\ifnum`" at compile time).
- `template/partials/backcover.tex.j2`: new `elif border == "gilded"`
  branch calling `\goldframedimage`.
- `form/formular.html`: new `<option value="gilded">` in the border
  select, `BACK_COVER_BORDERS` set updated; a `border_size` select
  (Schmal/Normal/Breit) shown only when `border == "gilded"`,
  `BACK_COVER_BORDER_SIZES` set added.
- **Asset footprint**: `images/borders/` now holds 100 PNG files plus the
  source JPG (~2–3 MB total) — a materially larger footprint than
  ADR-0013's styles, which need zero extra asset files since
  `pgfornament` is code-generated. This is the direct tradeoff of using a
  real photograph instead of vector ornaments; acceptable for one style
  built from one photo, but a second photographed frame would double it.
- `feasts/2026-09-18-lambertus.yaml`: `back_cover.border: gilded` (kept
  live on this feast as the reference/demo case).

## Update (2026-07-25)

`border` now defaults to `"gilded"` instead of `"none"` — the gold frame
became the preselected option in the form. `BackCoverBorderSize` was
renamed `small | normal | large` → `normal | large | extra-large` (same
underlying thicknesses, `1.0cm | 1.6cm | 2.2cm`, just relabelled to match
how they actually look); `border_size` still defaults to `"normal"`,
which after the rename is the old `"small"`/narrowest preset. See
`CONTEXT.md` for the current field description.
