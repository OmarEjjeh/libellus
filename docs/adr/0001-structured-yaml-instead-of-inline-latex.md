# ADR-0001: Structured YAML fields instead of inline LaTeX markup

Date: 2026-07-21
Status: accepted

## Context

The feast-spec YAML is authored by non-technical successors, but the smoke
YAML's text fields contained raw LaTeX — exactly four constructs:
`\vers{N}` verse superscripts (capitulum), `{\color{rubricred}…}` red †/*
pause marks (oratio), `\\`/`\\[0.5em]` line breaks (back-cover quote), and
`\textit{…}`/`~` (quote emphasis, credit line). The final system must not
require authors to write any of that (HANDOFF TODO "Get LaTeX out of the
feast YAML"). Alternatives considered: a tiny 3-symbol inline markup
(`[5]`, `_…_`), and a restricted Markdown dialect (rejected: `*` collides
with the liturgical pause asterisk; drags in a converter dependency).

## Decision

**Structure what has structure; the only inline convention is literal
characters the chant books themselves print.**

- **Capitulum**: `versus:` list of `{n, text, de}` — verse numbers are
  data, the template typesets the superscripts.
- **Oratio (and any chant-adjacent prose)**: authors type literal `†` and
  `*`; libellus auto-styles them rubric-red. Nothing to learn — it matches
  what is printed in the Antiphonale.
- **Back cover** (amended 2026-07-21 during implementation of #4):
  `image:` and `credit:` are always required; the content is **exactly
  one of** a `quote:` block (`text` + `de`, newlines are line breaks;
  optional red-italic `motto`/`motto_de`; optional italic `citation`,
  e.g. „Regula Benedicti, cap. XLIII“) **or** a free `text:` block.
  The red motto is a per-feast option, not the standard. The earlier
  `credit_title:` split is dropped — the whole credit line is tiny
  italic anyway, so one plain `credit:` string suffices; the quote's
  source line is the `citation` field instead. The template owns all
  styling.

The template/partials own every font, color, and spacing decision; the
YAML carries only text and structure.

## Consequences

- Schema change in `src/libellus/schema.py` (Capitulum, BackCover, oratio
  handling) + partial templates; smoke YAML must be migrated.
- The static HTML form can render these as plain form fields (verse rows,
  textareas) with no LaTeX awareness.
- RUNBOOK needs one line only: "†" und "*" einfach mittippen — sie werden
  automatisch rot gesetzt.
