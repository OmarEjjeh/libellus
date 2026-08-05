# ADR-0043: Tone 6's two mediations are a field of their own, `mediatio:`, defaulting to the *recentior usus*

Date: 2026-08-06
Status: accepted

## Context

The Liber Usualis (1932) p. 117 gives tone VI **two** mediations, in one line:

> Mediatio fit ut in I. Ton, 108, vel juxta recentiorem usum ut sequitur

— "the mediation is made as in tone I (p. 108), or according to the more recent
usage as follows". The books print both under a plain "VI", and the differentia
is `F` either way, so **the label does not distinguish them**. Neither does the
termination: both mediations run into the same one, and therefore into the same
EUOUAE.

jgabc encodes both rows, and `generate.js`'s `TONES` took the first:

| jgabc row | mediant (`c4`) | sounds |
|---|---|---|
| `6.` — *ut in I. Ton* | `f gh hr 'ixi hr 'g hr h.` | Dorian: reciting A, touching B-flat, cadence on A |
| `6 alt` — *juxta recentiorem usum* | `f gh hr g 'h fr f.` | F-centred: A A G A F, no B-flat, cadence on F |

`6.`'s mediant and solemn are byte-identical to `1.`'s. That is not a jgabc bug;
it is the engine faithfully obeying *ut in I. Ton*.

The schola sings the other one. `feasts/2026-09-18-lambertus.yaml` (18 September
2026) sets `tonus: 6F`, and this is the tone the reviewing priest flagged as his
„dickster Hund" on p. 25 — so the booklet was printing a mediation nobody in the
room sings. Issue #85.

## Decision

**The default changes and both stay reachable.** `tonus: 6F` now sings the
*recentior usus*, and the older mediation is chosen by a new optional field:

```yaml
magnificat:
  tonus: 6F
  mediatio: ut-in-tono-i    # omitted, or `recentior`, sings the newer one
```

Three things follow from that shape, and each was the alternative to something
worse.

**1. Its own axis, not a second tone label.** The obvious cheap move — a second
row in `TONES` — cannot work honestly. `canonicalLabel` is mode + ending, so two
rows both spelling `6F` collide, and telling them apart would mean **inventing a
differentia** (`F alt`, `F2`) that no book prints. That fabrication would not
stay internal: it would be written into the `mode-differentia:` header of every
generated verse file. It would also put two labels on one EUOUAE, breaking the
premise `differentia_candidates` rests on — "every ending's EUOUAE is distinct,
so an exact match identifies the ending uniquely" (#33, ADR-0042).

That premise is stated over *endings*, and both mediations share an ending. So
the invariant is only violated by smuggling the mediation into the label. Put it
on its own axis and the EUOUAE table stays 33 entries, 33 distinct, and
`_verify_tonus` needs no change at all: an antiphon's printed EUOUAE genuinely
cannot say which mediation follows it, and it is not asked to.

**2. On the Magnificat, not on every `tonus:`.** `mediatio:` is a field of
`Magnificat`, not of `Antiphona`. The canticle is where the choice is actually
sung here, and it is where the axis generalises: the other thing
`psalm-library/README.md` lists as not-offered is the *solemn* mediations, which
are likewise a canticle affair. A field meaningful for one tone would be a smell
if it were bolted onto all 33 tone-bearing items; scoped to the Magnificat it is
the narrow thing it looks like. Extending it to psalm antiphons, should a psalm
ever need it, is additive.

**3. The engine stays the single source of truth.** `generate.js` grows a
`list-mediationes` command (`{"6F": ["recentior", "ut-in-tono-i"]}`) rather than
a hand-kept copy of that vocabulary in `schema.py` — the same reasoning that
keeps the EUOUAE table derived rather than typed. A tone with one mediation is
*absent* from that map rather than listed with a single entry, so "is there a
choice here" is one membership test. **The first name listed is the default**,
and that ordering is the only record of it: a tone offering a choice carries
`mediationes` *instead of* a `key`, so there is no second copy of the default row
to drift out of step with it.

**The label stays `6F`,** because the books do not distinguish the two either.
Naming the default explicitly (`mediatio: recentior`) is allowed and is a no-op,
including for the cache folder — `main()` normalises it away at the boundary, so
nothing downstream has to ask whether it was named.

## Consequences

- **A non-default mediation gets a cache folder and a system of its own** —
  `6f-ut-in-tono-i` beside `6f`. Same label, different melody, so `6f` could not
  hold both; `build_systems` therefore iterates label × mediation, and the
  Kurzfassung system lookup in `resolve.py` needs no change, since it already
  keys off the cache folder name. `chant/magnificat/kurzfassung/` gains
  `6f-ut-in-tono-i.gabc` and its `6f.gabc` is regenerated.
- **Naming a mediation on a tone that has none is an error**, in German, not a
  silent no-op — ignoring it would set a booklet from a melody nobody chose.
- **The engine's `--mediatio` flag is not restricted to the Magnificat**, though
  the spec field is. The tone table is general — tone 6 is a psalm tone, and its
  two mediations exist whatever is sung to it — so restricting the flag would
  make the engine lie about its own table. Scoping belongs in the schema, which
  is where the decision was actually made.
- **Pointing moves, not only notes.** The tone-I mediation takes two accents
  („spí…me"); the *recentior usus* takes one accent with a preparatory syllable
  („tus" → „me"). So the Kurzfassung's pointed Latin changes as well as its
  notation.
- Magnificat verse 1 („Magníficat") is byte-identical under both — it is
  intonation-only either way. Only verses 2 and following move. In the
  regenerated `6f.gabc`, verse 1 now stops one note before verse 2 does, so the
  mediant's final `(f.)` carries only verse 2's „us" — exactly the shape ADR-0022
  designed the two-verse system for.
- The golden fixtures do not cover tone 6, so there is no golden churn.
- **The browser host needs nothing.** `app/psalmengine.mjs` forwards engine
  arguments verbatim, so `--mediatio` reaches it unchanged (ADR-0027).
- **The form's data island does not offer `mediatio:`.** `formdata.py` still
  exports `toni` and `euouae_per_tonus` only. The form is retired by ADR-0028
  and the editor that replaces it does not exist yet; wiring a dropdown into a
  retired UI would be work with no user.
- **Solemn mediations are still not offered.** They belong on this same axis and
  are wanted — an issue will be filed — but `6 alt` has no solemn row in jgabc,
  and what the books do for a solemn tone-6 Magnificat is unverified. Adding a
  value to a field is a much smaller change than this ADR, which is the point of
  choosing the axis over the label.
- Both St. Lambert booklets need re-staging, and the priest gets a
  `vorher`/`nachher` sheet (`docs/agents/booklet-comparison.md`) — this is the
  one correction he asked for that changes notes he will sing from.
