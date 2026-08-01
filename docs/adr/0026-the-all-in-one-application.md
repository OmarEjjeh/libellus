# ADR-0026: The all-in-one application — one WASM pipeline, three hosts

Date: 2026-08-01
Status: accepted

## Context

Everything decided about distribution so far pushes toolchain rot somewhere else
instead of removing it. `HANDOFF.md` names the problem in its own words —
"**Toolchain survivability (this is the hard problem, not the code).** LuaTeX +
Gregorio installs rot" — and records two mitigations: a pinned Docker image on
GHCR, and GitHub Actions as the successors' primary interface. Docker needs
Docker installed and a registry that still serves the image. Actions needs
GitHub, a working workflow file, and the 2 000 free minutes. Both relocate the
dependency.

Three separate motives converged on the same answer:

1. **Reach.** ADR-0012 wants other parishes and other locales. A stranger will
   not fork a repository and configure Actions; they will open an application.
2. **The marshalling problem.** Getting a feast spec and its images together to
   something that can compile them was hard enough that ADR-0019's `bundle`
   command exists partly to paper over it. When the editor and the compiler are
   the same process, that class of problem does not exist.
3. **Survivability.** A bundled toolchain removes the dependency rather than
   relocating it: a successor installs one application and has a complete,
   frozen, self-consistent TeX + Gregorio, with no TeX Live, no Node, no Docker
   and no GitHub account.

Motive 3 was not the original reason for wanting the application, and it is the
strongest one.

The enabling fact is that WASM LuaTeX now exists: `busytex` and its maintained
fork TeXlyre-BusyTeX ship TeX Live 2026 compiled to WebAssembly with pdfTeX,
XeTeX *and* LuaTeX. GregorioTeX requires LuaTeX specifically, so the older
pdfTeX/XeTeX-only browser engines could never have run this project.

## Decisions

1. **One pipeline, three hosts.** The same code runs in a browser, in Electron,
   and in the CLI: resolve → gabc→gtex → staged folder → LuaTeX → imposition.
   Electron rather than a native shell (Tauri, platform toolkits): the point is
   one web codebase everywhere, not native widgets.

2. **WASM everywhere; no native fork.** Electron *could* bundle real `lualatex`
   and `gregorio` binaries — faster, available today, no WASM work. Rejected:
   the browser target needs the WASM path regardless, so a native Electron
   backend costs everything the WASM one costs *plus* a second backend *plus* a
   standing obligation to prove the two produce the same PDF. Native binaries
   remain available later as a speed optimisation behind the same interface,
   which is a different thing from a fork in the design.

3. **`gregorio` runs before TeX, never inside it.** Today `compile.py` invokes
   `lualatex --shell-escape` and GregorioTeX's `autocompile` shells out to the
   `gregorio` binary mid-pass. Instead, `gabc`→`gtex` becomes an explicit first
   stage in our own code, writing `.gtex` into the staged folder before TeX
   starts.

   This is not a workaround for the browser — it is a fix. BusyTeX supports no
   arbitrary shell escape (only commands a JS handler registers), so hoisting
   removes the dependency on that extension point. More importantly it removes
   the cause of a bug we have lived with since July: `autocompile` garbles one
   source line per run while compiling many scores mid-pass, producing bogus
   "Undefined control sequence" errors, which `compile.py:59-67` and
   `stage.py:29-36` work around by looping `lualatex` up to four times until the
   log is clean. With gregorio hoisted, the garbling cannot happen and the retry
   loop deletes — on every host, including the CLI.

   Cost: `gregorio`'s version must match the bundled GregorioTeX (they release
   in lockstep and mismatches are loud), and `.gtex` files become build
   artifacts needing content-keyed invalidation — which `build/.cache/` already
   does for generated psalm notation.

4. **`pdf-lib` replaces `pdfjam` and `pdftk`.** Both are used for trivial jobs:
   2-up booklet imposition and rotating every second page 180°. `pdfjam` is a
   shell script wrapping `pdflatex` + `pdfpages`, so removing it also removes a
   second, hidden LaTeX invocation; `pdftk` on current systems is `pdftk-java`,
   a JVM dependency in disguise. The reimplementation is small *because* the
   booklet is already padded to a multiple of four (ADR-0018), so imposition has
   no padding edge cases. `pdf-lib` is MIT, which keeps the licence story clean.

5. **A minimal texmf tree, hand-rolled.** `gregoriotex` is in none of busytex's
   stock data packages, so a custom tree is required for correctness. It is also
   required for size: the stock trees are 90–400 MB, against OPFS quotas of
   ~1 GB in Safari (prompted in 200 MB increments), as little as ~300 MB in
   Chrome when "clear site data on close" is set, and 50 % of free disk up to
   2 GB in Firefox. The tree carries only what `preamble.tex.j2` needs —
   `gregoriotex`, `pgfornament`, `titlesec`, `microtype`, `fontspec`, `tikz`,
   `newunicodechar`, `draftwatermark`, `eso-pic`, `emptypage`, `footnote`,
   `fancyhdr`, `setspace`, `geometry`, `xcolor`, `graphicx`, `url` — plus EB
   Garamond, Charis SIL, XITS and greciliae, which must be referenced **by
   filename** rather than by font name under busytex.

6. **The application opens a Working directory, not a document.** Considered
   making ADR-0019's **Bündel** the application's document format — one
   self-contained file, no paths, nothing to marshal. Rejected: Electron has a
   real filesystem, so the marshalling problem is solved by the architecture
   rather than by the format; and a folder keeps `feasts/*.yaml` path-referencing
   and readable, which CONTEXT.md says is what a maintainer edits. The Bündel
   stays exactly what ADR-0019 made it: an export for archiving, emailing and
   attaching to issues.

7. **In the browser, the Working directory is OPFS.** Populated by folder
   import (`<input webkitdirectory>` / drag-and-drop, which Firefox and Safari
   both support) and exported as a folder or zip. Deliberately *not*
   `showDirectoryPicker()`, which is Chromium-only — that choice is what keeps
   Firefox and Safari first-class rather than degraded.

   Two consequences accepted: the browser build requires an **http(s) origin**
   (OPFS has no storage on an opaque origin, workers are blocked over `file://`,
   and `fetch()` of local files is blocked), so ADR-0003's "works when opened
   from disk" requirement is dead — killed by putting TeX in the browser, not by
   any later tooling choice. And the supported scope is **desktop browsers**: a
   200 MB toolchain inside mobile Safari's prompted 1 GB is not a promise worth
   making.

8. **The Toolchain is a separately versioned release asset.** LuaTeX.wasm,
   gregorio.wasm, the minimal texmf tree and the bundled data never enter an npm
   package or git. They are built from this repository, published as a GitHub
   release asset with their own version, pinned by a minimum version in the
   code, downloaded on first use and cached (OPFS in the browser, app data
   directory in Electron, `~/.cache` for the CLI), and pre-seeded by the Electron
   installers so the application works offline from first launch.

   This is a scoped amendment to ADR-0023 decision 4 ("one repository, one
   version"), not a reversal: one repository still, but two artifacts on two
   cadences, because rebuilding and re-uploading a 200 MB payload on every `fix:`
   commit buys nothing.

9. **Monorepo with npm workspaces.** `core` (schema, resolve, gabc, magnificat,
   latin, render, stage), `gregorio`, `tex`, `impose`, `cli`, `app` — published
   at one version, so "use the pieces separately from the CLI or from Actions"
   costs nothing extra.

10. **The Docker image and GHCR are dropped.** They were the recorded mitigation
    for toolchain rot; decision 1 is a better one. The Actions job becomes
    checkout, `npm ci`, fetch the pinned Toolchain, build — and doubles as the
    proof that the three hosts agree, since all three run the same core.

## Consequences

- The distributed application becomes GPLv3 while the sources stay 0BSD — see
  ADR-0029. This follows from bundling, not from WASM or TypeScript.
- The bundled data (GregoBase, the Clementine Bible, a public-domain Psalter)
  retires ADR-0006's static-API *mechanism* while its licence *rule* must
  survive — see ADR-0028.
- A public-domain Psalter stops being optional. Without one the application
  hands a stranger a Latin-only booklet (ADR-0025), which is not the product the
  reach motive describes. See issue #1 and the amendment to ADR-0024.
- The first thing to build is a throwaway spike, not a feature: take the
  existing staged `build/2026-09-18-lambertus/` folder — which by CONTEXT.md's
  definition of **Staging** already compiles without libellus or the rest of the
  repository — run gregorio.wasm over its `.gabc`, LuaTeX.wasm over its `.tex`
  with the minimal texmf, and compare the PDF to the one we have. Everything
  else in this ADR is engineering; that spike is the only part that can fail
  outright.
