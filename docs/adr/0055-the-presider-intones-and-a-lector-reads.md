# ADR-0055: The presider intones, and a lector reads the German capitulum

Date: 2026-10-22 (recorded 2026-11-01)
Status: accepted
Amends: ADR-0053, decision 4.

## Context

ADR-0053 gave the presider the initium, the capitulum, the oration and
*Fidélium ánimæ*. The reviewing priest corrected that on the All Saints draft
(#104). At a Vespers with a priest, the presider also intones some antiphons
and the hymn, and the capitulum is sung in Latin and read in German by
someone else.

The change was first written into ADR-0053 as a dated "Update" section. ADRs
in this repository are superseded or amended, not edited, so it is recorded
here instead.

## Decision

When `praeses:` is set:

1. **The presider intones the first antiphon, the hymn and the Magnificat
   antiphon**, and the schola continues. Their stagenotes read „Priester
   stimmt an, Schola singt weiter" (or „Diakon …"). The other four antiphons
   stay with the schola. `resolve` builds this stagenote once, as `intonatio`
   in the context, and the three partials print it.
2. **The presider sings the capitulum in Latin, and a lector reads its
   German.** The stagenote reads „Priester lateinisch, Lektor deutsch, alle
   antworten". Each reading gets its own answer: *Deo grátias* after the
   Latin, „Dank sei Gott" after the German.
3. **The instructions page gets a row for the lector**, and the presider's row
   names the three intonations.

Without `praeses:` nothing changes.

## Consequences

- The capitulum prints *Deo grátias* and „Dank sei Gott" as two answers in
  every booklet, with or without a presider. Before, only „Dank sei Gott"
  stood after the German.
- The other ADR-0053 decisions stand.
