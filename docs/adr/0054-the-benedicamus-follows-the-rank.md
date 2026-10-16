# ADR-0054: The Benedicamus follows the rank and the Vespers

Date: 2026-10-16
Status: accepted

## Context

The conclusio partial always printed one *Benedicamus Dómino* with its *Deo
grátias*, whatever the day. All Saints, I. Vespers on 31 October 2026 (#104),
needs another one: the friend's draft sets a long melisma on „Dó-" (#108).

The Liber Usualis 1961, pp. 124–127, gives the melodies in a table:

| | melody |
|---|---|
| I. classis, I Vespers | p. 124, mode 2 |
| I. classis, II Vespers | p. 125, mode 6 (ad lib. mode 5) |
| II. classis, I Vespers | p. 125, mode 2 |
| II. classis, II Vespers | p. 126, mode 8 |
| III. classis | p. 126, mode 2, one melody for both Vespers |
| feasts of the Blessed Virgin | p. 126 |
| Sundays per annum, of Advent and Lent, of Paschal Time | pp. 126–127 |

The table also gives a melody for Lauds of the I. and II. classis. It has no
row for the IV. classis or for ferias, and its numbering jumps from V to VIII.
That is the book, not a scanning gap.

breviariumgregorianum.com sets the same melodies by the same rule: 20 sampled
Vespers with the 1960 rubrics, from July to December 2026 and on 5 August 2028
(the only II. classis I Vespers in reach: Transfiguration on a Sunday). The
gabc of all five is taken from there, as for ADR-0053. Each melody was compared
neume by neume with the page images of the 1961 LU on archive.org
(`TheLiberUsualis1961`).

The melody in `benedicamus-domino.gabc` is the I. classis, II Vespers one. It
matches the site's gabc for 1 November note for note.

## Decision

1. **The melody is derived from `rank:` and `vesperae:`**, not named in the
   spec. The table is a rubric, and the spec already states both facts. Naming
   it would let a spec contradict its own rank.

2. **The pre-1955 ranks follow the reform of 1960**: `Duplex I classis` is the
   I. classis, `Duplex II classis` the II. classis, and `Duplex majus`,
   `Duplex`, `Duplex minus` and `Semiduplex` the III. classis. ADR-0015 says
   the two vocabularies are not derivable from one another in general. For
   this table, the mapping is the one 1960 made.

3. **A rank without a row keeps the I. classis, II Vespers melody**:
   `IV classis`, `Simplex` and `Feria`. That is what every booklet printed
   until now.

4. **One file per melody**, ℣ and ℟ apart as before:
   `benedicamus-domino<suffix>.gabc` and `deo-gratias<suffix>.gabc`. The
   melody that was always there keeps the unsuffixed name. Every file records
   its LU page in a `commentary:` header. The German is unchanged and stands
   once in `de.yaml`, referenced by a YAML alias.

## Consequences

- **Both shipped booklets change** at the *Benedicamus* and nowhere else in
  their TeX. Benedict (`Duplex I classis`, I Vespers) now prints the I. classis
  I Vespers melody; Lambert (`Semiduplex`) the III. classis one. Both were
  sung with the old melody. Their page counts hold (40 and 36).
- Benedict is `monasticum`, and the Antiphonale Monasticum has a table of its
  own. It is unchecked, and the Roman one applies to every rite for now.
- Feasts of the Blessed Virgin and the Sundays are not derived. They need the
  kind of feast or the season, which no field states and the calendar does not
  give (it is out of scope). A feast of Our Lady therefore gets the melody of
  its class.
- Lauds is out of scope: libellus sets Vespers only.
