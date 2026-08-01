# ADR-0003: Form stack — Preact + htm + eemeli `yaml`, one self-contained file

Date: 2026-07-21
Status: accepted — amended 2026-07-22 by ADR-0006: the *core* form stays
one self-contained file with full editing functionality, but optional
vocabulary-heavy features (Bible picker, chant search) may load data from
the hosted static API or from companion files under `form/daten/`; their
absence must never break the core.

## Context

The form (see CONTEXT.md) must both compose new feast YAML and load/edit
existing hand-written files — it is a YAML editor, never generate-only.
That requires a real YAML parser; hand-rolling one fails on hand-edited
input (block scalars, quoting, comments). The file must stay a single
self-contained HTML document that works opened from disk (repo is
private → no Pages; successors' interface is the GitHub web UI + disk).

## Decision

- **UI**: Preact + htm, vendored (~14 kB, no JSX, no build step) — the
  dynamic parts (5 antiphon rows, capitulum verse lists, live YAML pane)
  are written declaratively instead of imperative DOM code.
- **YAML**: vendor eemeli's **`yaml`** library (not js-yaml). Its document
  model preserves comments, key order, and scalar style through a
  load→edit→save cycle, so a hand-written feast file survives the form
  untouched except for the fields actually changed.
- All vendored code is inlined into the single HTML file, pinned and
  documented in a PROVENANCE comment, following the jgabc vendoring
  precedent (`scripts/psalm-library/vendor/PROVENANCE.md`).

Rejected: vanilla JS + js-yaml (verbose DOM code; lossy round-trip that
deletes successors' comments); hand-rolled YAML subset (violates the
editor requirement outright).

## Consequences

- Three vendored dependencies (preact, htm, yaml) to record and, rarely,
  refresh; all MIT/ISC-licensed, all build-free browser bundles.
- Form code manipulates YAML Document nodes rather than plain objects —
  slightly more involved, in exchange for faithful round-trips.
