# ADR-0051: The conclusion of an oration is a field, not text

Date: 2026-10-14
Status: accepted

## Context

Until now an oration's conclusion was part of its `text:`. St. Benedict wrote
it out in full, Latin and German; St. Lambert wrote the incipit, „Per
Dóminum." and „Durch Jesus Christus…". That worked while a booklet had one
oration.

Commemorations (ADR-0050) broke it. Under n. 249 of the Rubricae Breviarii
1960 the commemorated orations are concluded *in the last only*, so whether
an oration gets a conclusion depends on its position in the list, not on the
oration. Leaving that to the author makes a rubric the author's job, and an
oration moved in the list would carry the wrong ending.

The conclusion is not one formula, though. n. 115 gives four, chosen by whom
the oration addresses and where it names the Son, with a variant for an
oration that has named the Holy Spirit:

| | when | formula |
|---|---|---|
| a | addressed to the Father | *Per Dóminum nostrum Iesum Christum Fílium tuum, qui tecum vivit et regnat …* |
| b | to the Father, naming the Son at the start | *Per eúndem Dóminum …* |
| c | to the Father, naming the Son at the end | *Qui tecum vivit et regnat …* |
| d | addressed to the Son | *Qui vivis et regnas cum Deo Patre …* |
| e | having named the Holy Spirit | *… in unitáte eiúsdem Spíritus Sancti …* |

The wording does not reliably show which case applies, and guessing would be a
silent error in the one sentence every oration shares.

## Decision

1. **`conclusio:` on every `Oratio`**: one of `per-dominum` (the default),
   `per-eundem`, `qui-tecum` or `qui-vivis`, plus `eiusdem: true` for n. 115 e.
   The author names the case, and does not write the words.

2. **The words live in one table**, `resolve.CONCLUSIONES`, Latin and German,
   in full and abbreviated. `resolve._concluded` adds them to the oration of
   the day and to the last commemorated oration. The full `per-dominum` is
   exactly what Benedict's booklet printed.

3. **Full by default, `brevis: true` for the incipit.** A congregation that
   does not know the formula by heart needs it in full, which is what the
   All Saints draft prints. Lambert sets `brevis: true`, because that is how it
   was sung, and because its page budget is used up: three flavour pages fill
   it, and a longer oration risks a fourth page that the ÷4 padding turns into
   40.

4. **A conclusion written into the text is an error**, in German, naming
   `conclusio:`. It would otherwise print twice. The check looks for fragments
   only a conclusion contains, after stripping accents.

5. **n. 116's particular conclusions are not modelled.** None of the booklets
   needs one. The vocabulary can grow when one does.

## Consequences

- Both shipped feasts were migrated: the conclusion removed from `text:` and
  `de:`, and `brevis: true` added to Lambert. Their rendered TeX is
  byte-identical to before, full and Kurzfassung.
- The German forms other than Benedict's `per-dominum` are this project's own,
  modelled on it. They have not been checked against a printed German
  breviary.
- The browser form (`form/formular.html`) does not know `conclusio:`,
  `eiusdem:` or `brevis:` and would drop them on save, as it already drops
  `praenotanda:`. It is due for deletion (#100); the application's port (#97)
  should carry these fields.
