# A feast spec can be bundled into one self-contained file

Date: 2026-07-29
Status: accepted

`feasts/*.yaml` reference notation and pictures by repo path. That keeps them
readable, but it means a spec alone is not a booklet: hand someone the file and
they cannot build it. Worse, the pictures were not even in version control —
`.gitignore`'s `*.png`/`*.jpg` patterns match `images/` too, so a fresh clone
could not build either reference feast. That gap was silent.

Two changes, one narrow and one new:

1. The three pictures the reference feasts need are now **tracked**
   (`jj file track --include-ignored`). The ignore patterns stay broad on
   purpose — `images/01-ascension/` alone is 11.5 MB of artwork for a retired
   office — so `.gitignore` documents the trap and the command that beats it.
2. `libellus bundle <feast>` writes a **self-contained copy**: every `gabc:`
   becomes inline notation (ADR-0005 already allowed this) and every `image:`
   becomes an RFC 2397 `data:` URI. One file plus this program is a booklet.

`image:` therefore becomes a union exactly like `gabc:` — a repo path or
embedded content — and `resolve` decodes an embedded picture into the gitignored
`images/inline/` cache, the same trick it plays with pasted notation in
`chant/inline/`.

**Paths stay the authoring format; bundling is an export.** A bundled Benedict
spec is 5.8 MB, of which ~99.5 % is base64 — fine to archive or email, hostile
to read or diff. Making that the format a maintainer edits would defeat
ADR-0001/0002, whose whole point is that a maintainer can open the file and read
it. So bundling is something you run when you need the artifact, not a
migration.

Design decisions worth recording:

- **A data URI, not bare base64.** It carries its own MIME type, and the MIME
  type is what gives the decoded file its suffix — LuaLaTeX picks its graphics
  driver by extension, so `\includegraphics` on a suffixless file fails.
  Sniffing magic bytes would work, but then a hand-edited spec has no way to
  declare what it pasted.
- **The transformation is textual, not parse-and-re-dump.** PyYAML cannot
  preserve comments, and the reference specs carry ~90 load-bearing ones:
  provenance per proper, „AI draft, not yet reviewed" markers, explanations of
  editorial choices. Re-serializing would silently drop all of it, which for an
  archival format is exactly backwards. So each `gabc:`/`image:` line is
  rewritten in place, everything else is left byte-for-byte alone, and the
  result is re-validated and re-resolved to prove it still builds.
- **The chomping indicator follows the content** (`|` when the file ends with a
  newline, `|-` when it does not), so the embedded copy reproduces its source's
  bytes. Several .gabc files here have no final newline.
- **Line endings are not preserved.** Notation is read as text, so a CRLF source
  (two Benedict propers are CRLF) becomes LF. gregorio does not care and a YAML
  block scalar cannot round-trip a bare CR. Images embed byte-exactly.
- **The strong guarantee lives in the tests**, not in the command. `bundle`
  re-validates and re-resolves what it wrote — cheap, and it catches a botched
  rewrite. That the bundle renders *the same booklet* is a regression property
  of the transformation, so `test_bundle` asserts it by comparing the rendered
  TeX with every asset path replaced by a digest of the file's content.

Considered and rejected:

- **base64 in `feasts/*.yaml` directly** — the original request. Delivers
  one-file specs at the cost of making them unreadable and undiffable; the
  export form gets the same artifact without that price.
- **ruamel.yaml round-trip mode** to preserve comments through a real parse.
  Correct, but a new dependency for something a narrow regex plus a re-parse
  check already does.
- **Shrinking the back cover first.** Kept separate, then measured: the file was
  1018 × 1692 px, so never oversized in pixels — it was a photograph stored as PNG
  with a redundant fully-opaque alpha channel. Lossless recompression took it to
  3.13 MB with zero differing pixels, and it was then **converted to JPEG**
  (4:4:4, q95 — 886 KB, PSNR 43.8 dB), which brings a bundled Benedict spec down
  from 5.8 MB to 1.7 MB. That was a separate decision, as intended here, not a
  precondition for this one.

Consequence: `resolve` gained `_resolve_image`, which unified the back-cover and
filler-page image handling that had been duplicated (and gave filler images the
back cover's .webp-conversion hint for free). The back-cover partial now reads a
resolved `back_cover_image` from the context instead of reaching into
`feast.back_cover.image`, since that field may now hold a 5 MB data URI.
