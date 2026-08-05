# ADR-0042: EUOUAE comparison normalises clef and octave, in one canonical frame

Date: 2026-08-05
Status: accepted

## Context

`resolve.py` fails a build when an antiphon's EUOUAE disagrees with its
`tonus:` — the check that caught two mislabelled St. Lambert antiphons and the
reason ADR-0016 could be superseded at all. It bottomed out in
`gabc.normalize_euouae`, which dropped mora dots and compared the remaining
text.

That is wrong, because **gabc pitch letters are staff positions, not notes**.
`a`–`m` count positions from the bottom of the four-line staff; what they sound
is decided by the clef, so the same ending transcribed under another clef spells
entirely different letters. Every antiphon in the corpus is `(c4)` and the
comparison happened to agree; GregoBase transcriptions routinely use `c3`, `c2`,
`c1` and `f3`, and the first antiphon added from one of those would have been
told, in German, to check notes that were completely correct. Issue #45.

Fixing it turned up a second fact the issue had not: **the engine's own table is
not in one clef either.** `generate.js` derives each ending's EUOUAE from the
verses it generates for that tone, and jgabc writes each tone in the clef that
suits it. Twenty-three endings come out `c4`, nine `c3` (`4c`, `4A`, `4A*`,
`4d`, `5a`, `7a`–`7d`) and one `f3` (`2D`). So the table was already a mixture,
and three things had been quietly assuming it was `c4`: the append that joins a
missing EUOUAE onto the antiphon's stave (ADR-0017), the form's read-only
preview, which hardcodes `(c4)`, and the comparison itself.

A third fact decides the shape of the fix: **chant notation fixes no octave, and
the engine is not consistent about one.** Modes 1 and 2 share the final *re*,
but the engine writes mode 1's EUOUAE below its "do" and mode 2's above it. A
mode-2 antiphon notated in `c4` would be written low, an octave from where the
strict transposition of `2D` lands.

## Decision

**One canonical frame, `c4`, established at the engine boundary.**
`generate.js`'s `euouaeOf` transposes each ending out of its tone's clef into
`c4` before emitting it, so `euouae_per_tonus()` is uniformly `c4` and says so.
The JSON shape does not change, which is why the form, the data island and the
browser host need no edit — and the form's hardcoded `(c4)` preview becomes
correct rather than wrong for ten tones.

**`normalize_euouae(euouae, clef)` normalises into that frame**, and reduces a
EUOUAE to its pitch positions and nothing else: mora dots, note shapes and the
octave all go. The octave goes by shifting the six pitches together until the
first — the reciting tone — sits on the staff, which is what makes a mode-2
antiphon in `c4` comparable with the table's `c4` spelling of `2D`. All 33
endings stay distinct under this, which is the property the whole design rests
on and is asserted by a test.

**`resolve.py` reads the antiphon's clef** (`gabc.find_clef`) and passes it in.
A feast spec's `euouae:` assertion is read in the antiphon's clef too: it
records what that antiphon's printed source shows.

**A score with no clef is assumed `c4`, with a German warning, not a build
error.** gregorio cannot typeset such a score either, so failing here would only
add a second, worse-worded complaint about the same defect.

## Considered and rejected

**Compare interval sequences and read no clef at all.** Intervals are invariant
under both clef and octave, so this needs no clef anywhere — the tidiest option
on paper, and the one issue #45 leaned towards. Rejected because it is not
faithful: `4g` (`h h h h h g.` in `c4`) and `4c` (`i i i i i h.` in `c3`) are
different endings at different pitches with the same interval sequence, so 33
distinct EUOUAEs would collapse to 32. `_verify_tonus` requires a unique exact
match, so a correctly-labelled `4g` antiphon would have started failing.

**Report each tone's clef in the `euouae` JSON and normalise in Python.**
Strictly more information, and it is what a future transposition of the appended
cue into the antiphon's clef will want. Rejected for blast radius: the flat
`{label: neumes}` map is consumed by `formdata.py`, the form's data island and
the form JS, and #46 is stacked on this branch. Transposing at the boundary
keeps clef arithmetic out of the dependency-free form JS (ADR-0003).

**Fold the table into the staff in the engine, so it prints well too.**
Impossible under a single clef: `2D` normalises to `m m m l j k.`, above the
staff, and folding it down an octave puts `4c` and the mode-7 endings below it.
That the register cannot be right for every tone at once is exactly why jgabc
uses three clefs, and it is why printing is left out of this decision.

## Consequences

Both shipped booklets are unchanged: Benedict and Lambert are `(c4)`
throughout and use only `c4` tones, so every value they touch is identical.

`normalize_euouae` now returns an opaque comparison key — staff positions, not
playable gabc. It never was gabc anyone printed, but it used to look like it.

The **lenient half** of the check — accepting a EUOUAE whose leading five neumes
admit the stated tone, which exists to tolerate ornamented final neumes — widens
slightly, since notes an octave out now land in a neighbourhood instead of
nowhere. It widens for nothing real: the 33 endings fall into 17 leading-neume
neighbourhoods both with the octave shift and without it, so no two endings are
merged by it. What changes is where nonsense lands.

**Printing the appended cue is still clef-blind, and is now the only part that
is.** `build_euouae_gabc` splices the table's `c4` neumes onto the six syllables
and `_resolve_euouae` appends them to the antiphon's stave, whichever clef that
stave is in. Before this decision that was wrong for ten of the 33 tones even on
a `c4` antiphon; it is now right for every `c4` antiphon and wrong only for one
notated in another clef. The form's preview is the same gap seen from the other
side: it hardcodes `(c4)`, so those ten tones are now drawn at the right pitch
but above the staff. Both are issue #80, which needs the register question this
ADR deliberately left open.
