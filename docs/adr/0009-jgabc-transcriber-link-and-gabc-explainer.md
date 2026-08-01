# ADR-0009: Contextual jgabc transcriber link + GABC explainer in the form

Date: 2026-07-23
Status: accepted

## Context

`jgabc`'s rendering engine (`exsurge.min.js`) is already vendored into the
form for chant preview (ADR-0005), but its separate interactive
**transcriber** page (bbloomf.github.io/jgabc/transcriber.html, same
project) isn't linked anywhere. Authors hand-transcribing a chant from a
source that has no GABC yet currently have no pointer to that tool from
the field where they'd paste the result. Separately, nothing in the form
explains GABC syntax itself beyond the existing `GABC_HINWEIS` one-liner
about field format (path vs. inline notation).

## Decision

Two additions to every `gabc:` field (`GabcFeld`, all propers — not just
antiphons):

- A **contextual** link, shown only while the field is empty, opening the
  jgabc transcriber in a new tab ("GABC-Transkriptor öffnen"). Plain
  external link — no iframe/postMessage embedding of the third-party page.
- An **always-visible** ℹ️ link, next to the existing `GABC_HINWEIS`, that
  opens a popup with a short in-form GABC-basics primer plus a nested
  link to the Gregorio Project's full GABC reference. Always visible
  (not tied to emptiness) because not knowing GABC syntax is a problem
  whether the field is empty or already filled with unfamiliar notation.

Rejected: embedding the transcriber in-form (fragile third-party iframe,
no control over updates); scoping the transcriber link to antiphon fields
only (arbitrary carve-out — the same empty-field problem applies to
responsory/hymn/versicle); writing our own full GABC documentation
instead of linking out (duplicates the Gregorio Project's maintained
reference); two separate links for the explainer (clutters the field row
— nested is one affordance).

## Consequences

- Form-only change (`form/formular.html`); no schema or data-island impact.
- New static popup content (GABC basics) to write once, kept short by
  design since the full reference lives externally.
