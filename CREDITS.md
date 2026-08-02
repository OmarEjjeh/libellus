# Sources & Credits

`libellus` is licensed **0BSD** (see [`LICENSE`](LICENSE)) — do anything you
like with it, no attribution required.

That licence covers what is mine to license: the Python package, the LaTeX
skeletons and partials, and the German hymn/psalm *pointing* conventions. It
does **not** and cannot cover the third-party material this repository carries
or relies on. That material is listed below with its own terms, which travel
with it regardless of the 0BSD grant on everything else.

## Bundled in the published package

| What | Where | Source | Terms |
|---|---|---|---|
| Psalm-tone engine | `src/libellus/psalm-library/vendor/psalmtone.node.js` | [jgabc](https://github.com/bbloomf/jgabc) by Benjamin Bloomfield, commit `dff8749` | **The Unlicense** (public-domain dedication) |
| Clementine psalter, accented and pointed | `src/libellus/psalm-library/vendor/psalms/*.txt` (187 files) | jgabc, same commit | Unlicense; the underlying Latin text is public domain |
| Antiphons, hymns, responsories, versicles | `src/libellus/chant/` | [GregoBase](https://gregobase.selapa.net/) | **CC0** |
| Gilded back-cover border tiles | `src/libellus/images/borders/` | Derived crops of a gold gallery-frame product photograph (`gilded-source.jpg`) | See *Known exception* below |

Byte-for-byte verification instructions for the vendored jgabc files, and the
procedure for updating them, are in
`src/libellus/psalm-library/vendor/PROVENANCE.md`.

The browser form vendors `exsurge.min.js` from that same pinned jgabc commit;
because the form is one self-contained HTML file (ADR-0003), the copy lives
inside `form/formular.html` as the `id="vendor-exsurge"` block, with its URL,
commit, SHA-256 and licence recorded in that file's own PROVENANCE comment.

## Not bundled — external tools you install yourself

| Tool | Role | Terms |
|---|---|---|
| [Gregorio](https://gregorio-project.github.io/) | Typesets the chant notation | GPL. `libellus` invokes it as a subprocess through LuaLaTeX; it is not linked into this code. |
| LuaLaTeX (TeX Live) | Typesets the booklet | Various free licences |
| `pgfornament` | The vector ornaments and the non-photographic border | LPPL |
| `pdfjam`, `pdftk` | Page imposition and padding | GPL / various |
| Node.js or Bun | Runs the psalm-tone engine at build time | MIT / various |

## Artwork in `images/`

Per-feast pictures are **not** shipped in the published wheel; they live in the
repository only. Recorded provenance:

- `images/03-lambert/St-Lambert-Liege.jpg` — "The murder of Saint Lambert"
  (Jan van Brussel?, c. 1490), detail of the *Palude diptych*, Musée Grand
  Curtius, Liège.
- `images/02-benedict/` — see `images/02-benedict/source.md`.
- `images/01-ascension/ascension-no-background.png` — **provenance not
  recorded**, and therefore **not in this repository at all.** It stays in the
  private archive; establish its source before reusing it. No feast spec here
  refers to it.

## German translations

The interlinear German for psalms and the Magnificat is a **Psalter**, supplied
separately and never shipped in the wheel (ADR-0024). See the README on
choosing one.

- **Einheitsübersetzung 1980 and 2016** — © Katholische Bibelanstalt, Stuttgart.
  **Not included in this repository or the published package**, and not
  redistributable. Bremen's own copies live in a private companion repository
  (ADR-0023). Nothing here grants you any right to them.
- **Hymn translation, St. Lambert** — Erzpriester Stanislaus Stephan, *Das
  kirchliche Stundengebet oder Das römische Brevier*, München-Regensburg 1926,
  Bd. I, p. 49. Chosen because it renders all six stanzas, which the post-1971
  books do not; two typos corrected editorially. Cited in the feast spec.
- A **public-domain German psalter** is wanted and not yet done — the open issue
  for it is the intended long-term default, replacing the gated
  Einheitsübersetzung for anyone outside Bremen (ADR-0012 names Allioli-Arndt as
  the candidate).

## Known exception

ADR-0006 set a hard rule that only public-domain or CC0 content enters the
public repository. The gilded border tiles in `src/libellus/images/borders/` are
a deliberate, recorded exception: they are derived crops of a commercial product
photograph of a gold gallery frame, treated here as stock imagery. This was
decided knowingly rather than overlooked. If you would rather not redistribute
it, the `pgfornament` vector border (ADR-0013) is a drop-in alternative that
bundles no pixels at all.

## Thanks

The design of the booklets, the choice of translations, and the liturgical
corrections throughout owe a great deal to the parish priest of the community
in Bremen, and to the schola who sang the drafts and said what did not work.
