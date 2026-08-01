# Per-antiphon EUOUAE overrides bypass the shared psalm-tone cache

Status: **superseded 2026-07-27** — a EUOUAE cannot express a termination
formula, so there are no overrides to isolate. The EUOUAE's actual role is
recorded in the `Euouae` glossary entry and ADR-0017.

## Original context and decision

On-demand psalm-tone generation (see "Psalm-GABC: Entscheidung revidiert",
2026-07-21) caches generated verses in `chant/<n>/toni/<folder>/`, keyed
only by `(psalmus, tonus)` and shared by every feast that references that
tone. That assumes one named differentia (e.g. `8G`) always renders the
same termination — but printed antiphonalia were believed to vary the
actual notes for a same-named ending between editions (AM vs LU convention
differences; the `1D`/`1D-` ornamental-count tie, #24). A feast could
therefore supply a custom EUOUAE (auto-extracted from the antiphon's own
`<eu>` block, or hand-typed) overriding the termination for one antiphon in
one feast — not a universal replacement for the tone's canonical formula.

**Decision**: generation with a supplied EUOUAE override never touches the
shared `toni/` cache. It generates once, straight into that feast's own
resolved/staged build output.

## Why this was wrong

The premise was false in two independent ways.

**A EUOUAE cannot encode a termination.** The engine's terminations are
accent-aware templates, not note-per-syllable lists: an `r` suffix marks a
*reciting tone* absorbing however many syllables the verse has before the
cadence, and `'` marks the accented syllable — `8G` is `jr i j 'h gr g.`.
A EUOUAE is that template already *realized* on the six fixed syllables of
"sæculOrUm. AmEn", so it carries no reciting-tone or accent information,
and the templates' token counts (4–6) don't even correspond to syllables.
Passing one to the engine as a formula left it six fixed slots, which it
filled right-to-left, **silently discarding every earlier syllable of the
verse's second half** — `Sede a dextris meis` printed as `de a dextris
meis`. Every psalm of every feast whose antiphon carried a EUOUAE was
truncated, mid-word, in the compiled booklet.

**Mode plus differentia does fully determine the notes.** Deriving each
ending's EUOUAE from the engine showed all 33 endings have *distinct*
EUOUAEs, and the derivation reproduced every differentia label previously
assigned by hand from the books. The apparent edition-variance motivating
this ADR was in fact two mislabelled St. Lambert antiphons (`8G*`→`8G`,
`1D`→`1f`) plus a mora-dot spelling convention (jgabc writes `gf..` where
hand transcriptions write `g.f.`). `HANDOFF.md`'s 2026-07-20 domain notes
had already concluded exactly this — *"take the differentia label as
input, not raw EUOUAE notes"* — and were overlooked when #34 was designed.

## Consequences of superseding

The shared `toni/` cache is again the only generation target, keyed
`(psalmus, tonus)` as before. `generate.js` loses its `--termination` flag:
with no legitimate producer of custom formulas, keeping it would only
preserve the trap. A genuine edition variant absent from the engine's 33
endings would need a new *named ending* in the tone table — deliberately
out of scope, as that means editing vendored, provenance-pinned upstream.
