# A missing EUOUAE is joined into the score only at materialization time

Amended 2026-07-27: the decision below stands unchanged, but the notes are
now **derived from `tonus:`** rather than hand-typed, since mode plus
differentia fully determine them (ADR-0016, superseded). `euouae:` remains
as an optional *assertion* — what the printed source shows — checked
against `tonus:` and never fed to typesetting.

Two requirements compete when an antiphon's own GABC has no EUOUAE at all
(a real, common case — see #33): supplying the missing notes must not
require error-prone text-splicing logic in the form's deliberately
dependency-free, no-build-step JS (ADR-0003) that a non-technical
successor group inherits; but the EUOUAE must still print, joined into
the same continuous stave as the rest of the antiphon — the schola whistles
it after the antiphon to pitch the psalm, and singers check the psalm
ending against it.

**Decision**: the source YAML's `gabc:` is never mutated. When an
antiphon's own `gabc:` has neither a tagged (`<eu>...</eu>`) nor a bare
(`E u o u a e` syllable run) EUOUAE, `resolve.py` appends the ending's
notes onto the antiphon's *materialized* `.gabc` file at resolve/staging
time (the same step that already writes inline GABC to a file, per
ADR-0005), wrapped in an `<eu>` tag so incipit derivation and the
antiphon's repeat line ignore it. The compiled booklet then shows it
joined into the same continuous stave.

The form shows the same notes read-only for the chosen tone, looked up in
the data island (ADR-0004) — there is nothing to type and no input to type
it into.

## Considered and rejected

Splicing the confirmed EUOUAE directly into the antiphon's `gabc:` string
in the frontend, at authoring time — so there'd be only one field.
Rejected: detecting-and-replacing an existing tag or bare run inside
arbitrary hand-transcribed GABC text, without corrupting whitespace or
barlines, is exactly the kind of parsing this project keeps in
well-tested Python (`gabc.py`), not in the form JS; and a bug there could
silently corrupt a sourced antiphon transcription with no easy way to
notice.

## Consequences

`resolve.py`'s antiphon materialization step gains a conditional append
(only fires when the antiphon prints no EUOUAE of its own). The antiphon's
own byte-for-byte sourced GABC stays fully untouched and recoverable in the
YAML at all times.
