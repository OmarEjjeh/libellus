# ADR-0052: An Einschub follows a named section

Date: 2026-10-15
Status: accepted

## Context

A booklet sometimes needs a piece the ordo does not have. The first case is
All Saints, I. Vespers on 31 October 2026 (#104), which ends with the
*Te Deum*. Nothing could put it there: the rite skeletons are fixed include
lists, and the only free content, `filler:`, lands after the Marian antiphon
and carries no notation.

The commemoration (ADR-0050) was deliberately kept out of this. Its form and
place are fixed by the rubrics, so it is a field the template lays out. An
Einschub is the opposite: the ordo has no opinion about it, so the spec has to
say where it goes and what is in it (#103).

## Decision

1. **`insertiones:`**, a list. Each entry has `after:` (the section it
   follows), a `title` printed as the section heading, optional `who` and
   `posture` for the stagenote, and one or more `items`. The field name is
   Latin like the other liturgical fields; the glossary term stays *Einschub*.

2. **`after:` names one of the rite's sections**, `SECTIONS_PER_RITE` in
   `schema.py`: `ordo`, `initium`, `psalmi`, `capitulum`, `responsorium`,
   `hymnus`, `versiculus`, `magnificat`, `preces`, `paternoster`, `oratio`,
   `conclusio`, `antiphona-bmv`, as far as the rite has them. `ordo` is the
   Ordo page, so `after: ordo` reaches the gap before the Initium; with that,
   every gap between two sections is reachable through `after:` alone, and no
   `before:` is needed. A section the rite lacks is a German validation error
   listing the ones it has; ignoring it would make the Einschub vanish.
   Several Einschübe after one section keep their listed order.

3. **Three kinds of item, told apart by their key**: `gabc:` (a score, with
   `de` and `note`), `rubrica:` (a red line, no translation) and `text:`
   (prose, with `de` and `note`). German is required for scores and prose
   unless the feast is `latin_only` (ADR-0025).

4. **A mid-piece rubric is an item, not markup in the gabc.** The *Te Deum*'s
   *genuflectitur* at „Te ergo" is two `gabc` items with a `rubrica` between.
   Only the first score of an Einschub opens with a drop capital by default, so
   the second half continues without one; `initialis:` overrides either way.

5. **The insertion points live in the skeletons**: after each section's
   include, `\BLOCK{set anchor = "…"}` and an include of
   `partials/insertio.tex.j2`, which prints whatever is listed for that
   anchor. The skeletons stay include lists. Because the anchors are now
   written twice, in the skeleton and in `SECTIONS_PER_RITE`, a test holds the
   two to the same names in the same order.

6. **One row in the Ordo table** per Einschub, at its place, labelled
   *Insertio* with its title. It is kept whole in the Kurzfassung.

## Consequences

- Both shipped booklets render byte-identical TeX, full and Kurzfassung.
- A piece the ordo lacks no longer needs a hand-written `.tex` page.
- An Einschub makes no liturgical claim, so nothing checks that the piece
  belongs where it is put. That is the point of it, and the reason the
  commemoration is not one.
