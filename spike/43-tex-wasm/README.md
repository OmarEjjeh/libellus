# Spike #43, part 2 — LuaTeX as WebAssembly

**Verdict: it works.** Both Lambertus booklets compile under
TeXlyre-BusyTeX's LuaHBTeX against a **46 MB custom texmf tree**, and the PDFs
are **pixel-identical, every page**, to what the native TL2026 toolchain
produces from the same inputs.

With part 1, both bets in ADR-0026 that could have failed outright have now
passed. Throwaway by design: nothing here is wired into libellus.

## Results

| | |
|---|---|
| Full booklet: WASM vs native, identical conditions | **36 / 36 pages pixel-identical** |
| Kurzfassung: WASM vs the shipped PDF | **28 / 28 pages pixel-identical** |
| Custom texmf tree | **46 MB** (vs 86–324 MB stock data packages) |
| `busytex.wasm` | 31 MB |
| Passes needed | 2 (native Makefile allows up to 5) |
| LaTeX errors in either run | **0** |
| `--shell-escape` / subprocesses | **none** |
| `SharedArrayBuffer` / pthreads in busytex | **none present** |
| Compile time, full booklet | ~58 s/pass under Node |

Toolchain: `texlyre-busytex@1.2.3` (AGPL-3.0-or-later), LuaHBTeX 1.24.0,
TeX Live 2026 — the same TL year as the native install it is compared against.

## The blocker, and that it is surmountable

**TeXlyre-BusyTeX ships no `lualatex.fmt`.** The npm package advertises
lualatex, `busytex_pipeline.js:207` names
`/texlive/texmf-dist/texmf-var/web2c/luahbtex/lualatex.fmt`, and the
`web2c/luahbtex` directory exists in all three data packages — empty. The only
formats shipped are `pdflatex.fmt`, `xelatex.fmt` and `tex.fmt`.

It can be built inside the WASM, in **1.1 seconds**:

```
luahbtex -ini -interaction=nonstopmode -jobname=lualatex -progname=lualatex lualatex.ini
```

producing a 5.39 MB format. A natively built `.fmt` is useless here — a format
is tied to the engine binary that wrote it — so this has to happen inside the
WASM, once, and the result cached.

## Five things that had to be got right

Each of these failed loudly and none is guessable from documentation.

1. **`thisProgram` must be an absolute path that exists in the VFS.** kpathsea
   derives `SELFAUTO*` from `argv[0]`; left alone it picks up the Node script
   path and finds nothing. busytex's own pipeline uses `/bin/busytex`, and
   `/bin` has to exist as a directory.

2. **The tree needs an `ls-R`.** Stock `texmf.cnf` reaches `TEXMFDIST` through
   `!!`, which means "use the filename database and never scan the directory".
   Without `ls-R` a perfectly correct tree is completely invisible.
   `make-tree.sh` generates one the way `mktexlsr` would.

3. **`openout_any=a` is required.** luaotfload decides whether a cache
   directory is usable by writing a probe file into it, and TeX's default
   output restriction blocks any write outside the working directory. The
   symptom is `no writeable cache path, quiting` — which names the wrong cause.

4. **luatex cannot be run twice in one module instance.** The second
   `callMain` aborts in `create_null_font`. Every invocation needs a fresh
   instance; busytex's own pipeline does this via `reload_module`.

5. **NODEFS is not linked into busytex.** `FS.filesystems` has MEMFS only, so
   the tree must be copied in byte by byte. Inconvenient under Node, but it
   means the Node path and the browser path are the same path.

## Building the tree: what a recorder run does not tell you

The obvious way to find the minimal tree is `-recorder` over a native build.
That gives 208 runtime files plus 68 for the format build — 265 files, 19 MB —
and it is **not enough**, in three specific ways. Each one cost a debugging
round, and each is a trap for anyone repeating this:

- **The reference run had a warm luaotfload cache**, so it never touched the
  cold-start path. A cold start additionally needs `luaotfload-multiscript`,
  which reads `Scripts.txt` and `ScriptExtensions.txt` from `unicode-data` —
  files no warm run opens.
- **fontspec queries a whole family**, asking for bold, italic and bold-italic
  even where the booklet only ever sets Regular. A recorder run records only
  the face actually loaded, so `Charis SIL/B`, `XITS/I` and friends go missing.
- **Latin Modern is never recorded** but is the default before fontspec takes
  over, and its absence produces `metric data not found` before anything else
  happens.

`make-tree.sh` compensates by taking those directories whole. The result is
46 MB — larger than the theoretical 19 MB, still six to seven times smaller
than busytex's smallest stock package, and comfortably inside the OPFS quotas
#43 was worried about. Trimming further is possible (shipping a prebuilt
luaotfload font database would remove the cold-start need) but was not the
question here.

`gregoriotex` is, as #43 predicted, in **none** of busytex's stock data
packages, so a custom tree was never optional.

## Checkbox status

- [x] **A minimal texmf tree works** — 46 MB, both booklets pixel-identical.
- [x] **Fonts load by filename** — the concern does not apply. All four
      by-name loads (`EB Garamond`, `Charis SIL`, `XITS`, `greciliae`) resolve
      correctly once the full families are present and luaotfload can write its
      cache. No preamble change is needed. luaotfload builds its font-name
      database from the tree on first run.
- [x] **The `\GreWriteTranslation` patch survives** — the Kurzfassung is
      pixel-identical across all 28 pages, and it is the two-verse system that
      exercises the patch. ADR-0022 is safe.
- [x] **No `--shell-escape`, and the retry loop goes away.** With `.gtex`
      pre-generated (part 1), gregoriotex never attempts autocompile, no
      subprocess is spawned, and **both runs log zero LaTeX errors** — so the
      Makefile's "rerun until the log has no errors, max 4 passes" has nothing
      to trigger on. Two passes suffice, against the native recipe's up-to-five.
      This confirms ADR-0026 decision 3.
- [~] **COOP/COEP** — `busytex.js` and `busytex.wasm` contain no reference to
      `SharedArrayBuffer`, `Atomics.wait` or pthreads, so cross-origin
      isolation should not be required and GitHub Pages should be able to host
      this half too. **Not yet confirmed in a real browser tab** — part 1's
      browser run covered gregorio only.
- [ ] **Licence base** — see below. Still open, and still the one genuinely
      unresolved item.

## Licence: unchanged, and now the only open question

Everything above used **TeXlyre-BusyTeX (AGPL-3.0-or-later)**, per the
decision to prove feasibility first. Nothing was learned that argues for or
against upstream `busytex` (MIT scripts); the two were not compared. ADR-0029's
preference stands unexamined, and the fallback consequence — AGPL, with its
hosting implications — is still a live possibility rather than a settled fact.

What part 2 *does* narrow: the thing upstream `busytex` would have to match is
now precisely specified — LuaHBTeX with a buildable `lualatex.fmt`, since
upstream almost certainly does not ship one either.

## An unrelated find: the shipped booklet is not reproducible

While establishing the control, the shipped
`build/2026-09-18-lambertus/2026-09-18-lambertus.pdf` turned out **not to be
reproducible from its own staged folder** — by any method tried:

| build | vs shipped PDF |
|---|---|
| native, cold, 3 passes | 26 / 36 pages identical |
| native, cold, 6 passes | 26 / 36 |
| native, the staged `Makefile` recipe verbatim (`--shell-escape`) | 26 / 36 |

The same ten pages differ every time — p8, p9, p14, p16, p18, p21, p23, p25,
p31, p32 — and the difference is a small **vertical offset** of otherwise
identical content, the signature of GregorioTeX's `.gaux` position cache
settling somewhere else. The Kurzfassung reproduces exactly, so this is
specific to the full booklet.

This is a pre-existing native issue with nothing to do with WebAssembly, and it
is why the headline comparison above is WASM against a native build **under
identical conditions** rather than against the shipped artefact. It deserves
its own issue: a booklet that cannot be rebuilt from its own staging is a
survivability problem, which is the whole motive for the all-in-one.

## Reproducing

Needs a native TL2026 (as the reference), Node, and the busytex assets.

```sh
./collect-deps.sh                      # -recorder over the native build → tree-union.txt
./make-tree.sh                         # → tree/  (46 MB)

# busytex assets: 504 MB download, extracted to tl/assets/
npx texlyre-busytex@1.2.3 download-assets tl/assets   # or fetch the release tarball

PASSES=2 node run.cjs                  # full booklet  → 2026-09-18-lambertus-wasm.pdf
PASSES=2 node run.cjs --kurz           # Kurzfassung

uv run pdfdiff.py <native.pdf> <wasm.pdf>
```

`pdfdiff.py` renders both at 150 dpi and compares pixels. Text extraction is
not sufficient here: the chant is drawn from font glyphs positioned by
GregorioTeX, so a placement bug leaves the extracted text identical — as the
ten-page discrepancy above demonstrates.

`tree/`, `work/` and the generated PDFs are gitignored.
