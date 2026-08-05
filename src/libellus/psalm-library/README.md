# Psalm-tone engine (on-demand GABC generation)

`generate.js` points the accented Clementine psalter to any ferial psalm
tone of the Liber Usualis and emits per-verse GABC. **libellus calls it at
build time** (`src/libellus/psalmtone.py`) for every `(psalmus, tonus)` a
feast YAML references, plus the Magnificat — nothing is pre-generated or
committed; the verses land in the gitignored `chant/**/toni/` cache.

Requires any Node.js ≥ 14 (or Bun); no npm install.

```
node generate.js list-toni
node generate.js verses --psalmus 109 --tonus "8G"
node generate.js verses --psalmus magnificat --tonus 1D
```

Both commands print JSON. `verses` returns the canonical cache folder name
and one complete gabc file content per verse. Tone labels are matched the
way the books print them — case, spaces and dots are ignored, `*` can be
written `star` (`8G*` ≡ `8gstar`, `8 G` ≡ `8g`); unknown tones exit 2 with
a JSON error listing all valid labels.

## Conventions

- Verse texts are the accented Clementine psalter; the two Gloria Patri
  verses are appended to every psalm (booklet convention).
- The Magnificat repeats the intonation on every verse; psalms only
  intone verse 1.
- Bold = accented cadence syllable, italic = preparatory syllables — the
  same conventions as the tone-1D Magnificat the schola has sung from.

Not offered (add if ever needed): solemn tone variants, divided psalms
(135, 138, 143, 144 — ferial Thursday–Saturday only).

## Mediations

Where the books print more than one mediation under a single label,
`list-mediationes` names them and `verses --mediatio <name>` picks:

```
node generate.js list-mediationes
  -> {"6F": ["recentior", "ut-in-tono-i"]}
node generate.js verses --psalmus magnificat --tonus 6F --mediatio ut-in-tono-i
```

Tone 6 is the only one today. LU p. 117 gives it both *ut in I. Ton*
(p. 108) and *juxta recentiorem usum* under one "VI" with the same
differentia `F` — which is why jgabc's `6.` row is byte-identical to `1.`.
The first name listed is the default; here that is `recentior`, the one
the schola sings. Because the same label then spells two melodies, a
non-default mediation gets a cache folder of its own (`6f-ut-in-tono-i`).
The EUOUAE is unaffected either way — both run into the same termination.
See ADR-0043.

## Provenance & license

`vendor/` holds **unmodified, byte-for-byte** copies from Ben Bloomfield's
jgabc (<https://github.com/bbloomf/jgabc>, commit `dff8749`), released
under **The Unlicense** (public-domain dedication). See
[`vendor/PROVENANCE.md`](vendor/PROVENANCE.md) for the exact file mapping,
verification instructions, and the update procedure. `generate.js`
executes the engine verbatim in a `vm` context (only its unused jquery
import is stubbed from the outside); correctness is pinned byte-exactly by
the golden fixtures in `tests/data/golden/`.

The German verse translations are **not** generated — they are a hand-made
**Psalter**, re-cut psalm by psalm against the Vulgate verse division, and no
machine can redo that from the source text. See ADR-0024.
