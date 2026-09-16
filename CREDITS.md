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

This is the picture for the **Python package**, which merely invokes a toolchain
you installed. Invoking is not distributing, so no copyleft obligation reaches
anything here.

| Tool | Role | Terms |
|---|---|---|
| [Gregorio](https://gregorio-project.github.io/) | Typesets the chant notation | GPL. `libellus` invokes it as a subprocess through LuaLaTeX; it is not linked into this code. |
| LuaLaTeX (TeX Live) | Typesets the booklet | Various free licences |
| `pgfornament` | The vector ornaments and the non-photographic border | LPPL |
| `pdfjam`, `pdftk` | Page imposition and padding | GPL / various |
| Node.js or Bun | Runs the psalm-tone engine at build time | MIT / various |

## Bundled in the application — and why it is AGPL

> **Not shipped yet.** The all-in-one is designed (ADR-0026) and its toolchain
> is proven, but no application has been released. This section is what will
> apply when one is, and is written down now so the decision is not made by
> accident later.

The all-in-one ships the toolchain *inside* itself, as WebAssembly. That changes
the licensing picture completely: the artifact is then a combined work
containing GPL and AGPL components, and it must be GPL-compatible.

**The distributed application is AGPL-3.0-or-later** (ADR-0031). The repository
and its sources remain **0BSD** — two licences with two scopes, and 0BSD is
one-way compatible with the GPL, so lifting any module out of this source tree
still carries no notice and no obligation (ADR-0029 decision 1).

The AGPL specifically, rather than GPLv3, comes from the WebAssembly TeX build:

| Component | Role in the bundle | Terms |
|---|---|---|
| [Gregorio](https://gregorio-project.github.io/) + GregorioTeX, compiled to WebAssembly | Turns `.gabc` into chant notation | **GPLv3** |
| LuaHBTeX and the texmf tree, via [TeXlyre-BusyTeX](https://github.com/TeXlyre/texlyre-busytex) | Typesets the booklet in the browser | **AGPL-3.0-or-later** (the busytex fork); TeX Live's own components GPL and various |
| [pdf-lib](https://pdf-lib.js.org/) 1.17.1, vendored at `app/vendor/pdf-lib.esm.min.js` | Booklet (Montage) imposition — replaces `pdfjam`/`pdftk` (ADR-0026 decision 4) | **MIT** |
| `pgfornament` | Vector ornaments and the non-photographic border | LPPL |
| greciliae, greextra | The chant fonts | **OFL** (GregorioTeX's fonts are OFL even though its code is GPLv3) |
| EB Garamond, Charis SIL, XITS, Latin Modern | Body, translation, symbol and fallback text faces | **OFL** |
| Psalm-tone engine, Clementine psalter, GregoBase chant | As in the wheel, above | Unlicense / CC0 |

One loose end, recorded rather than glossed: **`pgfornament` is LPPL, which the
FSF considers GPL-incompatible.** TeX Live ships LPPL and GPL components side by
side on the view that a texmf tree is aggregated data interpreted at run time
rather than a linked combined work, and that view is very likely right here too
— but it has not been examined. If it turns out to matter, ADR-0013's vector
border is the component involved and ADR-0014's pixel border is the alternative.

### What this means for you if you host it

Not legal advice. Two separate obligations can apply, and it is worth knowing
they are separate:

- **§13, the network clause.** Anyone who **modifies** the application and lets
  users interact with it over a network must offer those users the Corresponding
  Source of their modified version.
- **§6, conveying object code.** A browser build *sends the compiled WebAssembly
  to every visitor*, so serving the page is plausibly conveying a copy, not
  merely providing remote access. On that reading the source obligation attaches
  whether or not you modified anything. Whether serving code to a browser counts
  as conveying is genuinely contested; this project does not need the question
  resolved, and neither will you if you follow the next line.

**The practical answer either way is the same: publish your source, or point at
the source of the exact build you are serving.** For an unmodified copy that is
a link to this public repository and the pinned upstream components — the offer
is honoured by existing. For a modified copy, publish your fork. Both are things
a parish can do; neither requires a lawyer.

This was a real trade-off rather than an oversight. ADR-0029 originally chose
the lighter GPLv3 ceiling precisely to keep obligations off third parties;
ADR-0031 reversed it, records why, and records the experiment that would reopen
the question.

## Artwork in `images/`

Per-feast pictures are **not** shipped in the published wheel; they live in the
repository only. Recorded provenance:

- `images/03-lambert/St-Lambert-Liege.jpg` — "The murder of Saint Lambert"
  (Jan van Brussel?, c. 1490), detail of the *Palude diptych*, Musée Grand
  Curtius, Liège.
- `images/03-lambert/Lambert-Ikone.png`, `Ostercappeln-Kirche.png`,
  `Ostercappeln-Taufbecken.png` — the icon, the parish church of St. Lambertus
  in Ostercappeln, and its 11th-century font. Supplied September 2026 by the
  friend of the schola who wrote that feast's flavour pages, with full rights
  granted; see *Prose in the feast specs* above.
- `images/02-benedict/` — see `images/02-benedict/source.md`.
- `images/01-ascension/ascension-no-background.png` — **provenance not
  recorded**, and therefore **not in this repository at all.** It stays in the
  private archive; establish its source before reusing it. No feast spec here
  refers to it.

## Prose in the feast specs

The flavour pages at the back of a booklet (`filler:` in a feast spec) are prose
like any other, and the 0BSD grant above covers only what is mine to license.

- **St. Lambert, `filler:` pages** — written for this booklet in September 2026
  by a friend of the Bremen schola, who **granted the maintainer full rights to
  the material**, text and photographs alike. The editing was mechanical only:
  soft hyphens closed, one number agreement corrected, a missing `aus`
  restored, a bare URL turned into a caption. The authorship is his; the entry
  is here because the 0BSD grant above covers what is mine to license, and this
  is covered by his permission rather than by my authorship.
- **St. Benedict, `filler:` pages** — Dom Prosper Guéranger, *Das Kirchenjahr*,
  Bd. 5, Mainz: Kirchheim 1877, and Gregory the Great's *Dialogues* II, 33–34,
  in a German rendering of the same vintage. Both long out of copyright; cited
  on the pages themselves.

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
- **Allioli-Arndt 1914** — Joseph Franz von Allioli's translation in Augustin
  Arndt's 1914 revision, the **default** German psalter since ADR-0041 and the
  only one a fresh install may legally have. The 1914 text is long out of
  copyright. The digitization used is k-bibel.de's Bible-app data, realigned to
  the sung Vulgate verse boundaries by `psalter/tools/scrape_allioli_arndt.py`.
  Two caveats, both recorded in issue #1 and in every psalm file's own header:
  the priest has **not yet reviewed** the translation, and the copyright status
  of **that particular digitization** — as distinct from Allioli's text — has
  not been judged. Neither is settled by making it the default; errors found
  meanwhile are fixed as their own corrections.

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
