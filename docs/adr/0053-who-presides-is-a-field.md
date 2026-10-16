# ADR-0053: Who presides is a field, and the salutation follows from it

Date: 2026-10-15
Status: accepted

## Context

Every booklet so far assumed that nobody in orders presides. The oratio and
conclusio partials printed ℣ *Dómine, exáudi oratiónem meam*, and the
stagenotes gave every intonation to the „Kantor". That is right for a schola on
its own. It is wrong when a priest leads, which he does at All Saints,
I. Vespers on 31 October 2026 (#104, #107).

The rubrics settle what changes. Rubricae Breviarii 1960, **n. 247**:

> Orationi praemittitur, in recitatione in choro vel in communi, Dominus
> vobiscum, cui respondetur Et cum spiritu tuo. In recitatione a solo facta,
> et ab iis qui in ordine diaconatus non sunt constituti, dicitur, nisi iam
> praecedat, Domine, exaudi orationem meam …

A deacon therefore says *Dóminus vobíscum* without restriction. Before 1960 he
needed the priest's leave (Rubricae generales, tit. XXX n. 3). The conclusion
of Vespers is ℣ *Dóminus vobíscum*, then the cantors' *Benedicamus Dómino*,
then *Fidélium ánimæ*, said by the officiant (Liber Usualis, p. 261). The
officiant also intones *Deus, in adjutórium*, and sings the capitulum and the
orations (Fortescue, *Ceremonies of the Roman Rite Described*, pp. 203–206).
No text changes apart from the salutation. Nothing in the 1960 rubrics
separates a priest from a deacon at Vespers: Vespers has no blessing, and
*Divinum auxilium* belongs to Compline.

## Decision

1. **A field naming who presides, `praeses:`**, with the values `sacerdos` or
   `diaconus`. If it is absent, no cleric presides. The spec states the fact,
   and the templates derive its consequences. A switch for the salutation alone
   was rejected, because the salutation is only the first consequence.

2. **The salutation is chosen once, in `resolve`** (`salutatio` in the
   context): *Dóminus vobíscum* for a cleric, *Dómine, exáudi* otherwise. It
   stands before the oration of the day and before the *Benedicamus*, never
   before a commemoration (ADR-0050).

3. **The melody is the one All Saints will sing**: the ancient solemn tone
   (LU p. 100), as breviariumgregorianum.com sets it for Vespers with a priest.
   The friend's draft for #104 took it from there. It is in
   `chant/ordinarium/dominus-vobiscum.gabc`, with the German „Der Herr sei mit
   euch. — Und mit deinem Geiste."

4. **The stagenotes name him.** „Priester" or „Diakon" replaces „Kantor" at
   the initium, the oratio and the conclusio, and „Vorbeter" at the capitulum.
   In the conclusio the cantors get their own stagenote for the
   *Benedicamus*, and the presider gets one for *Fidélium ánimæ*. The
   instructions page gets one row that says what he sings.

5. **`sacerdos` and `diaconus` print the same booklet**, apart from that name.

## Consequences

- Both shipped booklets render byte-identical TeX, full and Kurzfassung,
  because the field is absent in both.
- A probe build of St. Lambert with `praeses: sacerdos` keeps its 36 pages, and
  the instructions page has room for the extra row.
- The preces of `romanum-cum-precibus` still name the „Vorbeter". Who leads
  them when a cleric presides was not part of #107 and is unchecked.
- *Dómine, exáudi* keeps its current, simpler melody. Under a lay leader that
  is what Bremen sings, and it is a separate question from this one.
