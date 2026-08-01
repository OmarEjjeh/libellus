# ADR-0011: Provenance notes on propers, rendered as footnotes

Date: 2026-07-23
Status: accepted

## Context

Hand-transcribed chants and other propers sometimes carry a provenance
worth recording — e.g. "found in Vesperale Romanum, Leodii 1835,
Pag. 406-407" — but the feast-spec schema has no field to express it
anywhere. `BackCoverQuote.citation` is the closest existing precedent: a
single free-text bibliographic-style string, no separate German
translation.

## Decision

A shared Pydantic mixin, `Notable` (`note: str | None = None`), inherited
by every content-bearing proper model: `AntiphonaCumPsalmo`, `Versus`,
`Responsorium`, `Hymnus`, `Versiculus`, `AntiphonaAdMagnificat`, `Oratio`,
`BackCoverQuote`. One optional note per item, following the `citation`
field's precedent (single string, no `note_de` pair — provenance
citations aren't translated). Structural wrapper models that only
aggregate other models (`Capitulum`, `Magnificat`) don't get their own
`note` — the leaf models they contain already carry it.

Rendered as a real LaTeX `\footnote` in the corresponding partial
templates: a numbered marker in the text, the note text collected at the
page bottom. Chosen over a sidenote (the booklet's page geometry has no
established margin space for this) and over an inline parenthetical
(adds visual weight directly in the choir's reading flow, which the
project already treats carefully per `HANDOFF.md`'s font/legibility
decisions).

The form gains a matching optional note field per section (consistent
with it being a full editor, not generate-only).

Rejected: scoping `note` to GABC-bearing propers only (narrower than what
was decided — any proper, including capitulum verses and the back-cover
quote, can carry provenance); a `notes: list[str]` field (no known case
needs stacking more than one note per item); repeating the field
individually across 8 models instead of a mixin (drift risk with no
offsetting benefit).

## Consequences

- Schema change across 8 models plus a new `Notable` mixin in
  `schema.py`.
- Every affected partial template needs a conditional `\footnote{...}`
  emission.
- Form change: one new optional field per section using existing
  optional-field UI conventions (cf. `repetitio`'s hint pattern).
