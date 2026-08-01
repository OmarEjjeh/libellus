# Propers' GABC lives inline in the feast spec, not in a repo library

Date: 2026-07-21
Status: accepted

The repo will not carry a curated library of proper chants (antiphons,
hymns, responsories, versicles) — we must not assume one exists. Every
chant element's `gabc:` field is a union: a repo path (used by the
ordinarium and any file the author chooses to keep) **or** an inline GABC
text block. The form embeds pasted GABC and picked `.gabc` files inline,
so authoring a feast requires no separate upload step and the feast spec
is fully self-contained ("reuse is copy-paste"). Sizes are trivial
(~15 kB of propers per feast); staging writes inline GABC out to `.gabc`
files in the build folder.

Considered and rejected: path-only references (authors must invent
filenames and do a separate GitHub upload per chant — the most
error-prone step of the flow); separate `gabc_inline:` field (two fields
for one concept).

Consequence: because pasting raw notation is now the riskiest input in
the form, form v1 renders pasted GABC with vendored exsurge.js (same
pinned jgabc commit `dff8749`) for instant visual feedback.

Future milestone (recorded, not designed): the form browses **GregoBase**
as the antiphon database — click a chant, preview its GABC, and libellus
handles the rest.
