# ADR-0039: The booklet is typeset, not rendered — LaTeX over HTML, and why Breviarium Gregorianum is not a shortcut

Date: 2026-08-04
Status: accepted
Scopes: ADR-0012's "aggregation-only model" entry.

## Context

**Breviarium Gregorianum** (breviariumgregorianum.com) covers the whole 1962
Divine Office — all eight hours, Matutinum through Completorium — entirely in
the browser: gabc from GregoBase and the Nocturnale Romanum, office structure
and texts from Divinum Officium, rendered with `exsurge.js`, plus the Neumz NABC
renderer via Scrib.io and Chant Tools for notated psalmody and playback. It is a
better-looking, wider-covering thing than libellus in every dimension libellus
does not care about, and the obvious question follows: if HTML is enough for
that, why is this project carrying LuaTeX, Gregorio, `pgfornament`, a
convergence loop and a 46 MB texmf tree?

ADR-0012 already compared the two projects, but on tenancy, hosting and
copyright. It noted in one parenthesis that BG has "no PDF/LaTeX output" and
rejected the aggregation-only *content* model, and never addressed the output
format at all. ADR-0001 presupposes LaTeX in its title without having justified
it. So the choice this project's whole pipeline rests on has never been written
down, and the comparison that prompts it has now come up twice.

## Decision

The booklet stays typeset by LuaTeX with notation set by Gregorio. HTML plus
print CSS is rejected as the print path, and Breviarium Gregorianum is recorded
as a research aid rather than a substitute or a source of code.

**BG cannot be adopted or adapted, before any technical question is reached.**
Its About page is explicit: "I'd rather not open up the code to contributions at
this early stage as it would require extra work." There is no repository, and no
licence — so by default, all rights reserved. Nothing can be forked, extended
with a `monasticum` skeleton, taught the group's `romanum-cum-precibus`, or
copied onto a laptop in Bremen for a Saturday when the site is down. It is also
1962-Roman-only and Latin-only, so the two ordos this project exists to set and
the interlinear German of ADR-0007 are not features it withholds but categories
it does not have.

**The HTML project did not solve printing in HTML.** BG's own booklets are not
BG's: it points at *Vespero Generator* (gregorian-booklets.gitlab.io/vespers), a
separate MkDocs site publishing pre-generated PDFs for one French parish, in
French. The comparison on offer is therefore not "HTML instead of LaTeX" but
"HTML for reading, a second system for print, and a human to regenerate the PDFs
when a feast changes". That is the arrangement libellus was built to avoid; a
feast spec exists so that the person who changes a versicle is the person who
gets the corrected booklet.

**What this project needs from print, a browser does not give.** Imposition and
the duplex rotation (ADR-0037), padding to a multiple of four, an antiphon that
stays with its psalm, red rubrics, the marginal postures, drop capitals,
`pgfornament` dividers, Latin and German hyphenating in the same paragraph.
Little of that survives CSS Paged Media without Paged.js or WeasyPrint — which
is to say, without a second engine, which is what LuaTeX already is. The
counter-example proves the shape rather than denying it: imposition *did* move
off `pdfjam` onto `pdf-lib` (ADR-0037), because rearranging finished pages is
genuinely PDF plumbing and not typesetting. The seam sits exactly where the
distinction lies.

**Gregorio and exsurge are not interchangeable, and the repo already treats them
correctly.** `exsurge.min.js` is vendored for the form's live preview
(ADR-0009): the right job for it is drawing one score as you paste it. Setting
77 of them into a paginated book with the line heights feeding back into the
pagination is the other job, and BG bolting the Neumz NABC renderer alongside
exsurge marks where the first tool stops.

**Convergence and reproducibility are print requirements, not TeX quirks.**
ADR-0032's whole finding — that a pass must be repeated until GregorioTeX stops
asking, and that reproducibility is proven by rebuilding rather than against a
stored PDF — is what makes a staged folder rebuild itself years from now with no
libellus present. That is the succession plan CONTEXT.md opens with. A closed
third-party website is its exact opposite: the day the domain lapses, the schola
has nothing.

**Where HTML genuinely wins is where libellus is not.** Reading on a screen,
playback, all eight hours across the whole year, no install: BG is the right
design for that and libellus would be a bad one. This decision is about a
printed, folded, bilingual booklet for one celebration, and it claims nothing
beyond that.

**And the one advantage HTML had over this project has already been taken
without giving up the typesetter.** BG needs no toolchain; neither does libellus
any more, since ADR-0026 through ADR-0034 put LuaTeX and Gregorio in the browser
as WebAssembly. The pressure the comparison creates was real, and it was
answered in 2026-08 by moving the compiler, not by replacing it.

## Alternatives considered

- **Use BG as the engine, contributing the missing ordos upstream.** Ruled out
  by the closed source and absent licence, not by appetite.
- **Rewrite the booklet as HTML + Paged.js, keeping exsurge.** Trades LuaTeX for
  a JS paginator with weaker justification, no `pgfornament`, and worse chant,
  and still needs `pdf-lib` for imposition — a second engine either way, and the
  weaker one.
- **Keep libellus for print, add a BG-style reading view.** Not rejected on
  merit, only out of scope: it is a new product, and ADR-0028 has the editor as
  the application. If it is ever wanted, `IDEAS.md` is where it starts.
- **Depend on BG or Vespero for gabc.** Rejected per ADR-0006: chant data comes
  from GregoBase directly as static files, and adding a closed intermediary
  between this project and its sources would trade a stable dependency for an
  unstable one.

## Consequences

The next time this comparison arrives — from a contributor proposing Paged.js,
or from anyone who has seen BG and reasonably wonders — it costs a link rather
than a session.

BG and Vespero acquire a small positive role. BG encodes Divinum Officium's
office structure, which makes it a fast spotcheck for *which* chant a feast
takes when a feast spec is being filled; Vespero's References section is a usable
map of editions. Neither becomes a dependency, and neither is authoritative
here: both are 1962-Roman, so a `monasticum` question cannot be settled from
either.

Nothing in the code, schema, templates or tests changes. This ADR records what
the pipeline has always done and states the boundary of the claim, so that
"LaTeX because LaTeX" is not the answer a successor inherits.
