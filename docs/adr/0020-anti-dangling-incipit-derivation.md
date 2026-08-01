# ADR-0020: Incipits are derived by an anti-dangling heuristic, per genre

Date: 2026-07-30
Status: accepted

## Context

Ordo-table rows and antiphon repeat cues both print an **incipit** — the
first few words of a chant. Until now both came from `gabc.incipit()`:
take words until the first punctuation, the mid-verse `*`/`†`, or a fixed
word count, whichever comes first.

Reviewing the St. Lambert ordo, Pastor Kraienhorst (letter received
2026-07-30) objected that the cut left prepositions hanging in mid-air:
`Cum palma ad`, `Corpora Sanctórum in`, `Omnes Sancti quanta`. He supplied
the cuts he wanted, which are *longer* than ours in three places and
identical in the other four.

The obvious structural fix — cut at the antiphon's asterisk — is wrong.
The asterisk marks the **intonation break**, where the cantor hands over
to the choir, and in this feast it falls after two words every time:
it would yield `Cum palma`, `Corpora Sanctórum`, `Omnes Sancti` — shorter
than the current output and worse on exactly the rows complained about.

## Decision

One derivation function, applied at different word counts (3 for ordo
rows, 4 for `repetitio`), extended with two tiers that fire only when the
cut would strand a word:

1. **Governing words.** While the last word is closed-class and demands a
   complement to its right — prepositions (`ad, in, de, ex, cum, per,
   pro, sub, sine, propter, …`), conjunctions and subordinators (`et, ac,
   atque, sed, nec, ut, ne, si, quia, quod, non, …`), relatives and
   correlatives (`quam, quanta, quot, qui, quae, cujus, quo, quibus, …`)
   — absorb one more word. Bounded at +3 words and never crossing the
   punctuation that caused the cut.
2. **Never strand an auxiliary.** If the word immediately *after* the cut
   is a form of *esse* (`est, sunt, erit, erant, sit, fuit, …`), absorb
   it. A one-word lookahead, not a classification of the word being kept.

Tier 2 is what reaches `Omnes Sancti quanta passi sunt`: tier 1 absorbs
`passi` because `quanta` governs, then tier 2 absorbs `sunt` because it
would otherwise be stranded.

**Hymns do not use this.** A hymn's unit is the first metrical line,
which gabc marks with the divisio minor `(;)`. That yields `Sanctórum
méritis ínclyta gaúdia` (his cut, `Pangámus` dropped) and independently
confirms on `gemma-caelestis` → `Gemma cæléstis pretiósa Regis`, a
sapphic hendecasyllable. No word count is involved.

**Psalms do not use this either** — they come from a table (ADR-0010),
generated once from the vendored accented Clementine psalter and then
hand-correctable. Two words where that suffices, extended to at most
three where it separates two psalms. Incipits are deliberately *not*
unique and cannot be made so — Ps 6/37, 13/52 and 106/117 open with
word-for-word identical verses — so the psalm number stays the
identifier and the incipit is a label beside it; 15 labels are shared by
35 psalms. Chasing full uniqueness was measured and rejected: it reaches
only 3 residual collisions at the cost of nine-word Ordo rows
(Ps 110 would print `Confitébor tibi, Dómine, in toto corde meo: * in
consílio`).

The five gabc-bearing propers that feed an ordo row — antiphon,
responsory, hymn, versicle, Magnificat antiphon — share an `OrdoItem`
mixin carrying an optional `incipit:` override, mirroring the existing
`repetitio:` field. The heuristic is a good default, not an authority;
the reviewing priest is the authority. The `oratio` row is deliberately
outside this: its text is plain YAML rather than gabc, and its own rule
(three words, reading *through* commas) is what the priest approved.

### Rejected alternatives

- **Cut at the antiphon's asterisk.** Refuted above: the asterisk is the
  intonation break, not a sense break.
- **Cut at the first divisio minor for antiphons too.** Tested: gives
  `Omnes Sancti quanta passi sunt torménta` and `Cum palma ad regna
  pervenérunt Sancti` — longer than wanted. Right for hymns, wrong here.
- **Detect participles by suffix** (`-tus/-ta/-ti/-sus/-si`) to catch
  `passi`. Would also flag `Sancti`, `Benedíctus` and `justi`, breaking
  four working incipits. The *esse* lookahead gets the same result with
  no false positives.
- **A pure stoplist with no lookahead.** Cannot reach `quanta passi
  sunt`: `passi` is not a function word, so it stops one word short.
- **Hand-authored incipits everywhere, no derivation.** Always correct,
  but ~8 fields per feast and no help for a new author.

## Consequences

- Validated over all 170 gabc files in `chant/`: 7/7 of Kraienhorst's
  corrections reproduced exactly, 0 regressions on the chants he left
  alone, 38 improvements across the 156-file psalm/Magnificat corpus
  (`De torrénte in` → `De torrénte in via`, `Potens in terra` → `Potens
  in terra erit`), and 0 incipits anywhere still ending on a governing
  word.
- Only one `repetitio` changes anywhere (`Omnes Sancti quanta passi`
  gains `sunt`), so no *sung* page moves except that one cue.
- The Benedictus booklet's Ordo page does move, though it was sung on
  10 July: three psalm rows lengthen now that they come from the table
  (`Confitébor tibi` → `Confitébor tibi, Dómine`, `Beátus vir` →
  `Beátus vir, qui timet`, and the truncated `Laudáte` → `Laudáte,
  púeri`). Only visible if that booklet is ever reprinted.
- **The ordo keeps two punctuation policies, deliberately.** A gabc
  incipit stops *at* a comma; the `oratio` row reads *through* one
  (`Intercéssio, quaésumus, Dómine`). Unifying them breaks one or the
  other: cutting through commas would run `Mártyres Dómini` past its
  asterisk, and stopping at them would truncate the oratio to
  `Intercéssio`. Both current outputs are as the priest approved them.
- A Latin function-word list now lives inside a typesetting tool. It is
  a *closed* class — the list is complete, not a growing pile of special
  cases — but it will look like over-engineering to a future reader.
- Still not fixed by any heuristic: `Fuit vir vitæ`, a genitive stranded
  from its head. That needs real parsing, and is what the `incipit:`
  override is for.
