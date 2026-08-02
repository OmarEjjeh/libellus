# Spike #43, part 1 — gregorio as WebAssembly

**Verdict: it works, unmodified in every way that matters.** All 77 `.gabc`
scores of `build/2026-09-18-lambertus/` compile under WebAssembly to `.gtex`
that is **byte-identical** to what the native `gregorio 6.1.0` produces —
in Node and in real Chrome alike.

This is the first of the two bets in ADR-0026 that could have failed outright.
It did not. The second (LuaTeX-in-WASM compiling our preamble) is untouched.

Throwaway by design: nothing here is wired into libellus.

## What was proven

| | |
|---|---|
| `.gtex` byte-identical to native | **77 / 77** |
| `.glog` byte-identical to native | **77 / 77** |
| Identical in real Chrome over plain HTTP | **77 / 77** |
| Needs `SharedArrayBuffer` | **no** |
| Needs COOP/COEP headers | **no** |
| Needs `--shell-escape` or any subprocess | **no** |
| `gregorio.wasm` at `-O2` | 690 KB (95 KB gzipped) |
| JS glue | 64 KB |

Toolchain: gregorio 6.1.0, emsdk 6.0.5, Node 25.5.0, Chrome (stable channel).

### The COOP/COEP question is answered for gregorio

The browser run was served by a deliberately plain static file server sending
**no** `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` headers.
The page reported `crossOriginIsolated: false` and
`typeof SharedArrayBuffer === "undefined"`, and still produced all 77 scores
correctly. The build links no pthreads, no `Atomics.wait`, no
`SharedArrayBuffer`.

**GitHub Pages can host the gregorio half of the toolchain.** Whether it can
host LuaTeX is a separate question this spike has not touched.

### Licence base is a non-question here

gregorio is its own GPLv3+ C program, built directly from the upstream release
tarball. It has nothing to do with busytex or TeXlyre-BusyTeX, so the
MIT-vs-AGPL choice in ADR-0029 does not bear on this half at all. It stays open
for the LuaTeX half.

## What it cost: one patch, sixteen lines

`--with-kpathsea` turns out to be **opt-in** in `configure.ac`, so the WASM
build simply omits it. But omitting it does not remove the dependency — it
swaps a library call for `popen("kpsewhich -must-exist -all …")`, which under
emscripten fails with `Function not implemented`.

There is exactly one caller: locating `gregorio-vowels.dat`, gregorio's vowel
and elision rule table (`characters.c:58`). The patch
(`0001-locate-vowel-data-without-kpsewhich.patch`) lets
`$GREGORIO_DATA_DIR` name that directory outright, falling back to the
existing behaviour when unset.

Worth carrying forward: **`gregorio-vowels.dat` is a runtime data dependency of
gregorio itself**, not just a TeX input. It ships inside the `gregoriotex` TeX
package, so the minimal texmf tree in the second half of this spike must
include it for two different consumers.

Beyond that patch, the source is untouched. `configure` needed only
`--host=wasm32-unknown-linux`, because `configure.ac` hard-errors on any
`host_os` outside its list of four and emscripten's triple is not among them.

## Two findings that outlive the spike

### 1. `sanctorum-meritis.gabc` has been failing all along

The hymn exits **non-zero under both native and WASM gregorio**, with identical
`.glog` output:

```
error:forced center may not be within an elision
error:forced center may not be within an elision
```

This is pre-existing and reproduces exactly, so it is not a WASM regression —
but it is a real error in a shipped booklet's source. It became **#55**, still
open as editorial work.

Two corrections to what was written here first. Autocompile does *not* swallow
the exit status — `gregoriotex.lua` raises a LaTeX error on a non-zero one. The
error was invisible for a duller reason: every build kept a warm `tmp-gre/`, so
gregorio never ran at all. A genuinely cold build had never been done, and the
old recipe fails outright on one. Since ADR-0032 the notation is made in its own
step, the `.glog` is echoed every run, and gregorio's exit code is not the gate
— it writes complete notation here despite exiting 1 — so #55 now announces
itself on every single build.

### 2. Hoisting gregorio out of the TeX pass looks sound

`gregoriotex.lua:1115-1124` builds exactly `gregorio -D -W -o <gtex> -l <glog>
<gabc>` per score. Running that ahead of TeX reproduces the reference
`tmp-gre/` tree byte-for-byte, which is what ADR-0026 decision 3 assumed. The
retry loop can only be declared unnecessary once LuaTeX runs against a
pre-populated `tmp-gre/`, so that confirmation belongs to part 2.

**Confirmed, and shipped natively** (ADR-0032): `stage.py`'s Makefile and
`compile.py` both make the notation first and drop `--shell-escape`, and the 77
`.gtex` they produce are byte-identical to autocompile's. The retry loop is
gone — replaced by one that reruns until the layout stops moving, which is a
different condition and the one that mattered (#56).

## Reproducing

```sh
source ~/emsdk/emsdk_env.sh
./build.sh                                   # → work/out/{gregorio-node.js,gregorio-memfs.mjs}
node memfs-driver.mjs                        # MEMFS, no real filesystem
uv run browser-check.py                      # real Chrome, plain static host
```

Both harnesses compare against `build/2026-09-18-lambertus/tmp-gre/`, which is
the natively-produced reference. `browser-check.py` compares SHA-256 digests
rather than bytes, so that nothing has to be shipped back out of the page.

The reference itself was first re-derived natively, file by file, before any
WASM was involved — 77/77 byte-identical — so that a later mismatch could be
attributed to WebAssembly rather than to a wrong flag.

## Version lockstep

`FILENAME_VERSION` is baked in at configure time and gives the `-6_1_0` suffix
in `<score>-6_1_0.gtex`, which is the name GregorioTeX looks for. The bundled
GregorioTeX and the WASM gregorio must therefore be built from the same
release — as expected, and now mechanically enforced by the filename.
