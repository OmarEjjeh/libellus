# ADR-0004: Form validation via a generated data island; CI stays authoritative

Date: 2026-07-21
Status: accepted

## Context

Pydantic (`src/libellus/schema.py`) is the single schema definition, with
curated German errors and cross-file checks (gabc exists, tone label
valid, psalm has de.yaml) in libellus/CI. The form should catch mistakes
before commit but cannot read the repo from the browser.

## Decision

A libellus command (working name `libellus export-form-data`) regenerates
a **marked JSON data island** inside the form's HTML file, containing
everything that varies:

- the 33 valid psalm-tone labels (from the vendored jgabc engine)
- ordinarium chant names (for `antiphona_bmv` etc.)
- psalm numbers that have a German `de.yaml`
- rite → required antiphon count
- existing `chant/**` and `images/**` file paths

The form's own typed fields enforce the document structure; the data
island supplies the variable vocabularies; **CI's German Pydantic errors
remain the authoritative gate**. A stale island degrades gracefully
(outdated pick-lists), never breaks the form.

Rejected: exporting the full JSON Schema + vendoring ajv (~120 kB for
rules the form's fields already embody; cross-file checks need the island
anyway); minimal client checks only (German errors would arrive only
after commit → push → CI wait).

## Consequences

- New libellus subcommand + a CI check that the island is current.
- Form validation messages are written once, in German, in the form.
