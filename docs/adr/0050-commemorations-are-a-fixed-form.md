# ADR-0050: Commemorations are a fixed form, filled by the spec

Date: 2026-10-14
Status: accepted

## Context

A Vespers in the 1962 books often keeps an impeded office alive by a
commemoration — of a Sunday, a saint, a feria of Advent or Lent. libellus had
no place for one: the oratio section ended with the oration of the day. The
first booklet that needs it is All Saints, I. Vespers on 31 October 2026, which
commemorates the XXIII. Sunday after Pentecost (#104, #105).

A friend of the schola drafted that booklet by hand. The draft raised three
questions the rubrics answer, and which were settled against the
*Breviarium Romanum* 1961, *Rubricae generales* and *Rubricae Breviarii*:

- **Where, and of what.** n. 251: the commemorations follow the oration of the
  day, each made of the Benedictus or Magnificat antiphon of the commemorated
  office, the versicle preceding it, and its oration.
- **Conclusions.** n. 249: the oration of the day always keeps its own
  conclusion; the commemorated orations are concluded *in ultima tantum*, in
  the last only; *Orémus* is said before each. With one commemoration, as on
  All Saints, both orations are therefore concluded, which is what the draft
  printed.
- **Salutation.** n. 247: *Dóminus vobíscum* (or *Dómine, exáudi*) precedes the
  oration. It is not repeated before a commemoration; n. 251 does not list it.

The same body sets how many commemorations a day admits (n. 111: one
privileged commemoration on a I class day) and which exclude each other
(n. 112).

## Decision

1. **A list field, `commemorationes:`**, each entry a `title`, an `antiphona`
   (`gabc`, `de`), a `versiculus` (`gabc`, `de`) and an `oratio` (`text`,
   `de`), each with the usual optional `note:` (ADR-0011). German is required
   unless the feast is `latin_only` (ADR-0025).

2. **The spec supplies content, the template owns the form.** `oratio.tex.j2`
   prints, after the day's oration: a red heading "Commemoratio <title>", the
   antiphon with its initial, the versicle, *Orémus*, the oration, and the
   conclusion with its *Amen* after the last commemoration only. The author
   writes no structure, and so cannot get the order wrong.

3. **libellus adds the conclusion, to the last commemorated oration only**
   (n. 249). Which conclusion is the oration's `conclusio:` field, the same
   one the oration of the day has; ADR-0051 records it.

4. **No EUOUAE.** The antiphon is sung without a psalm, so it has no
   termination to print or assert; `AntiphonaCommemorationis` has no `tonus`
   or `euouae` field, and resolution skips `_resolve_euouae`. The draft printed
   one, which was a mistake.

5. **The count and the exclusions are not validated.** Which commemorations a
   day carries is the Ordo's decision (nn. 111–114) and the author copies it;
   re-deriving it would need the precedence tables libellus does not model.

6. **One row in the Ordo table** per commemoration, after the oration, labelled
   *Commem.* with its title.

The oratio partial is shared by every skeleton, so `monasticum` gets the same
form. That is right as far as is known, but it has not been checked against
the monastic rubrics, which have not yet been needed.

## Consequences

- A commemoration is not an **Einschub** (#103): an Einschub is free-form and
  makes no liturgical claim, while this is a fixed form in a fixed place. The
  two must stay separate features.
- Both shipped booklets render byte-identical TeX, full and Kurzfassung; the
  field is optional and empty by default.
- A probe build of St. Lambert with one commemoration grew from 36 to 40 pages,
  over the page budget its three flavour pages had used up. The section adds
  about half a page, which is worth knowing when a booklet is close to a
  multiple of four.
