# ADR-0018: Filler pages are structured plain text, not hand-written `.tex`

Date: 2026-07-28
Status: accepted

## Context

`filler:` was a list of paths to hand-authored `.tex` pages — ADR-0002's
power-user escape hatch, placed deliberately outside the YAML. Two things
made that insufficient once the Benedict booklet became a real feast spec
(roadmap item 8):

1. **The form cannot produce them.** `form/formular.html` exists so a
   non-technical successor can author a feast without learning the
   toolchain. A `.tex`-only filler means the printed booklet's three
   flavour pages (Guéranger excerpts, Gregor's *Dialoge* II 33–34, the
   St. Benedict medal) are reachable only by writing LaTeX — exactly what
   ADR-0001/0002 removed from every other field.
2. **Their assets are invisible.** `resolve.py` copies a filler `.tex`
   verbatim and does not discover what it references ("keep fillers
   self-contained"). The medal page needs `medal-print.png`, which nothing
   else in a monastic feast pulls in, so it would stage without its image
   and fail to compile.

Inspecting the three pages showed they share one shape, and that every bit
of LaTeX in them is *styling* — which by ADR-0002 belongs in a partial.

## Decision

`filler:` becomes a list of **structured `FillerPage` entries**: optional
`title`, optional `subtitle` (newlines are line breaks), a list of `blocks`
(`heading` + `text`), an optional `citation`, and an optional `image` with
`caption`. All plain text. The ornament rules, small-caps title, red block
headings, flush-right citation and image placement live in
`partials/filler.tex.j2`.

`image` being a real schema field is the point, not a convenience: it makes
the file an ordinary resolved asset, the same way the back-cover image is.

The `.tex` path form **stays** as a union alternative, so ADR-0002's escape
hatch is narrowed rather than closed. Such a page must still be
self-contained; the partial emits the page break *between* entries, so a
filler `.tex` must not begin with its own `\newpage`.

The mod-4 ornament padding loop is untouched — it already computes the
padding TeX-side and needs no page-count bookkeeping from the author.

Rejected: a rich-text or Markdown subset for filler prose (a second
markup dialect to teach, and every element would still need a partial);
asset discovery by scanning filler `.tex` for `\includegraphics` (parsing
arbitrary LaTeX to find files, to support a shape the form can't emit
anyway).

## Consequences

Fidelity: small-caps and `\textup` inside the ported prose flatten to
ordinary text (`\textsc{ii}` → `II`). The rendered pages otherwise
reproduce the printed booklet's pp. 33–35 — text extraction is
byte-identical on the first two and differs only in that flattening on the
third.

The form grows its first *nested* repeatable UI (pages × blocks) and a
`bild-liste` datalist over the data island's `image_paths`. `entferne` now
takes a minimum count, because filler pages may go to zero while verses
and hymn stanzas may not.
