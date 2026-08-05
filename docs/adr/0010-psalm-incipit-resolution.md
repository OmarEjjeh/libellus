# ADR-0010: Shared Latin-incipit data, surfaced in the form and an agent skill

Date: 2026-07-23
Status: accepted; second consumer (the agent skill) retired 2026-08-05

## Context

The `psalmus` field (`AntiphonaCumPsalmo.psalmus`) uses Vulgate psalm
numbering (confirmed: `chant/psalmi/109/` is annotated "Ps 110 hebräische
Zählung" — the folder name is Vulgate, Hebrew is a comment). Authors and
an agent skill alike would rather work from a psalm's Latin incipit
("Dixit Dominus") than memorize Vulgate numbers, but the repo has no
incipit data anywhere, and the number is needed in two independent
places: the form (so a human can enter/confirm a psalm without knowing
its number) and an agent skill that fills feast-spec YAML conversationally.

## Decision

A new repo data file, `chant/psalmi/incipits.yaml`, maps Vulgate psalm
number → canonical Latin incipit — the single source of truth. Two
consumers read it, neither duplicates it:

- `libellus/formdata.py` adds it to the generated data island (ADR-0004).
  The form's psalm-number field becomes a datalist-backed combobox — the
  same pattern the `tonus` field already uses (`toni-liste`) — accepting
  either the bare number or an incipit substring, always displaying the
  resolved incipit as a label.
- The incipit-filling agent skill references the same file instead of
  bundling a private copy. **Retired 2026-08-05 — see the amendment
  below.**

Matching is Latin-incipit-only, not German. German psalm-opening words
vary by the selected `psalter_de` variant (eu1980 vs. eu2016, ADR-0008)
and would be a less stable, edition-dependent search key; Latin incipits
are the traditional identifier already used throughout the project (ordo,
tonus labels).

Rejected: agent-recall-only resolution (no stored table — inconsistent
across runs for data where a wrong answer silently prints the wrong
psalm); per-consumer duplicate incipit tables (drift risk); a read-only
label without search (doesn't help authors who don't know the number to
look up in the first place); German-inclusive search (edition-dependent).

## Consequences

- New data file to populate once (150 canonical Vulgate incipits, fixed
  reference data) and a small `formdata.py` addition.
- **Amended 2026-07-30 (see ADR-0020):** a third consumer, the Ordo
  table, which until now derived its psalm row from the first verse gabc
  *inside the selected tone's directory* — so the printed label silently
  depended on which `tonus:` the author picked, and the punctuation cut
  truncated Ps. cxii to `Laudáte` instead of `Laudáte, púeri`. The table
  removes both faults. Incipits are stored **accented**, because the Ordo
  prints them and every other row is accented; the form folds accents
  away at search time rather than storing a second unaccented column.
- Form change: the plain `type="number"` psalm field becomes a
  datalist combobox, reusing existing UI plumbing.
- The agent skill's job narrows to *using* the shared table plus walking
  the user through the rest of the feast-spec fields — not maintaining
  its own psalm data.
- **Amended 2026-08-05 (see ADR-0028): the agent skill is dropped, and
  with it this ADR's second consumer.** ADR-0028 decided that the
  application absorbs the form, on the argument that *maintaining two
  editors against one schema has no remaining payer*. A skill that fills
  feast-spec fields conversationally is a third authoring surface and
  falls to the same argument — it would have to track the schema, the
  vocabularies and the German warnings independently of the editor that
  now owns them. Hand-editing without the application stays supported by
  ADR-0028's documented floor ("the YAML still documents intent and the
  template can be filled by hand"), which needs no skill to hold it up.

  Nothing else in this ADR changes. `incipits.yaml` was never justified
  by the skill: it exists, accented and complete, and has two live
  consumers in the Ordo table (ADR-0020) and the editor's psalm field.
  Issue #30 is closed; the field itself remains open as #17/#29.
