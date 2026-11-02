# ADR-0045: A printed EUOUAE is placed by what it connects to

Date: 2026-08-06
Status: accepted

## Context

ADR-0042 made *comparing* a EUOUAE clef-aware and said what it had left alone:

> Printing the appended cue is still clef-blind, and is now the only part that
> is.

Two things print one. `resolve.py` appends the ending's notes to an antiphon
that transcribes none, joined into that antiphon's own continuous stave
(ADR-0017); and the form draws a read-only preview of the chosen tone's
ending. Both took the engine's table exactly as it comes — in `c4`,
ADR-0042's canonical frame — and drew it. Since gabc pitch letters are staff
*positions*, that is right only for a score that happens to be in `c4`, which
all eleven corpus antiphons are and no GregoBase transcription need be. Issue
#80.

Placing an ending needs two decisions, and only the first is forced. The
**clef** is whatever the stave already carries. The **octave** is free,
because chant notation fixes none — and the engine is not consistent about
one either: mode 1's ending lies below its "do" and mode 2's above it, so
`2D` transposed strictly into a `c4` stave lands on `m m m l j k.`, two ledger
lines up. ADR-0042 rejected folding the table into the staff in the engine for
exactly this reason:

> That the register cannot be right for every tone at once is exactly why
> jgabc uses three clefs.

So the octave cannot be a constant, and it cannot be a property of the ending
alone. It has to come from what the ending is printed next to — which differs
between the two callers, because the form has no antiphon to look at.

## Decision

**A printed EUOUAE is placed by what it has to connect to.** One principle,
two instantiations, because the two callers connect to different things.

**Appended to an antiphon**, the cue is respelled out of `CANONICAL_CLEF`
into the antiphon's clef, then moved by whole octaves so that its **last note
lands nearest the note the antiphon is taken up again on**. That is the
`Connection rule` (ADR-0044) read as a height rather than as an identity: the
rule already says an ending is chosen so its closing note runs into the
antiphon's first, and the cue exists so the schola can find its way back into
the antiphon. `gabc.build_euouae_gabc` takes the clef from `find_clef` and the
anchor from the new `gabc.opening_position`.

*Nearest*, not equal, because the connection rule is a convention and not a
law — three antiphons of the two shipped booklets are sung to an ending it
does not propose, and those must still print sanely. Nearest among the octaves
gabc can actually spell: an antiphon starting high can pull an ending past
`m`, and being writable outranks being well-placed.

The two moves are **summed and applied once**. Respelling into a low clef on
its own can carry a pitch below `a`, where gabc has no letter and `chr`
arithmetic yields punctuation that the format reads as something else
entirely — `d` moved down five is `_`, a horizontal episema. The octave that
would have rescued it cannot, because the corrupt characters are no longer
pitches to move. So the arithmetic stays numeric until the last step. Neither
argument to `build_euouae_gabc` has a default, either: printing an ending
without asking what stave it lands on is the whole of issue #80.

An antiphon that sounds no note anchors nothing, so its cue is folded onto the
staff instead. The clef is still not free there — the stave exists.

**Previewed alone**, in the form, there is no antiphon, so the free variable
is the other one: the **clef**, and the octave is left exactly as the engine
wrote it. `gabc.euouae_on_the_staff` returns the first of `c4`, `c3`, `f3`
that holds all six neumes on the staff — the three clefs the engine itself
writes its tones in (ADR-0042), so the result is the clef the books print that
tone under. Nine endings (`2D`, `4A`, `4A*`, `4d`, `7a`–`7d`, `7c2`) take
`c3`; the rest stay canonical, and no ending in the current table needs `f3`.
It is named anyway, because the rule is "the clefs the engine writes in" and
not "the two that happen to suffice today".

**The form is handed the answer, not the arithmetic.** `formdata.py` ships a
new data-island key, `euouae_preview_per_tonus`, whose values are whole stave
openings — `"4A" → "(c3) E(i) u(h) o(i) u(j) a(h) e.(f.)"`. The form draws the
string and computes nothing, which is what ADR-0003 and ADR-0017 ask of its
dependency-free JS. Its `spliceEuouae` and `EUOUAE_SILBEN` go with it, having
nothing left to splice.

## Considered and rejected

**Place both by putting the reciting tone on the staff.** One rule for both
callers, needing no antiphon, and the code exists already
(`_octave_shift_onto_the_staff`, which normalisation uses). Rejected because
it places the cue by legibility alone, which is the very thing that can strand
it an octave from the antiphon printed immediately before it on the same
stave. Legibility is the right criterion only when there is nothing to be
legible *next to*.

**Fold the octave in the preview too, keeping every tone in `c4`.** It works —
`2D` folds to `f f f e c d.`, on the staff and perfectly readable — and it
would need no clef vocabulary at all. Rejected because it invents a register
no book prints, and inconsistently: `4d` folds to the bottom of the staff
while its sister `4A` cannot fold at all and would have to change clef
anyway, so mode 4's endings would be drawn an octave apart in the differentia
picker that shows them side by side. Changing the clef moves an ending onto
the staff *without* moving it, which is why the books do that instead.

**Ship the per-tone clef and let the form respell the neumes.** Strictly less
data. Rejected: respelling is position arithmetic, and ADR-0003 and ADR-0017
both turn on keeping that kind of thing in tested Python rather than in the
form's JS. Shipping the placed stave costs one string per tone and removes
the form's last piece of notation handling.

**Preview the cue as it will actually print, against the antiphon in the same
row.** The most honest preview possible, and the form does have that antiphon.
Rejected for the same reason: it needs `find_clef` and `opening_position` in
the form's JS. The differentia picker also draws every ending of a mode before
any antiphon need be chosen, so it would need the standalone placement in any
case.

## Consequences

**Both shipped booklets are unchanged.** Five antiphons across the two get a
cue appended — four of St. Lambert's plus its Magnificat antiphon — and all
five are `c4` (one `cb4`) and start again where their ending closes, so
neither move shifts any of them. Asserted by
`test_shipped_booklets_print_their_cues_exactly_as_the_engine_writes_them`,
which reads the printed cue back and compares it to the engine's table rather
than to the placement code, so that a placement bug cannot agree with itself.

**The preview no longer shows what will print.** It never quite did, but now
it demonstrably differs: the same tone is drawn standalone in the clef that
reads best and printed in the antiphon's. The form says so in its own words.

**A flat clef flattens the cue.** An antiphon under `cb4` — St. Lambert's
*Lætare et lauda* is one — puts its appended cue under that flat too, since
they share a stave (ADR-0017). Left alone deliberately: it is what a schola
singing on from the antiphon would do anyway, and the alternative is a clef
change mid-stave that no chant here has.

**The data island grew a key**, so `libellus export-form-data` had to be rerun
and the freshness gate (ADR-0004) covers it from here.

**`final_pitch_class` still reads `CANONICAL_CLEF` only.** It is a reader of
the *engine's* endings, and those are still uniformly canonical; the appended
cue is written, never read back. Anything that ever does read one back will
need the clef passed in.
