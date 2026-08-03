# ADR-0037: Imposition gets its own `async` seam, not a second `Runner`

Date: 2026-08-03
Status: accepted
Scopes: ADR-0026 decision 4, ADR-0034 decision 1.

## Context

Issue #59 asks for the last piece ADR-0026 decision 4 scoped and ADR-0034 left
undone: replace `pdfjam` (2-up booklet imposition) and `pdftk` (the duplex
page rotation) with `pdf-lib`, mirroring the injectable-seam pattern
`compile.py`'s `Runner` and `psalmtone.py`'s `Engine` already established.

Reusing `Runner`'s exact shape turns out not to be possible. `Runner` is a
plain synchronous function — `(command, folder) -> stdout` — and ADR-0034
decision 1 requires that: gregorio and LuaTeX are called from deep inside a
retry loop that is itself synchronous Python, and bridging a synchronous call
to asynchronous JavaScript needs `SharedArrayBuffer`, which GitHub Pages'
missing COOP/COEP headers rule out for this project.

`pdf-lib`'s entire public API returns a promise, including calls that do no
real I/O at all — `PDFDocument.load`, `.save`, `.copyPages`, all of it. A
promise-returning function cannot be the synchronous seam `Runner` is: there
is no way to unwrap a promise inside a plain synchronous call without
`SharedArrayBuffer`, regardless of whether anything genuinely asynchronous
happens inside it.

The saving fact is that imposition is not nested in a retry loop. `impose()`
is one top-level call, made once after `compile_pdf` returns — in the CLI, in
`cli.py:build()`; in the browser, once per booklet in `worker.mjs`. Pyodide's
`runPythonAsync` bridges a genuine top-level `await` of a JS promise onto the
page's own event loop, with no `SharedArrayBuffer` involved — a different,
unconstrained mechanism from the mid-loop synchronous call `Runner` needs.

## Decisions

1. **`Imposer` is `Callable[[Path], Awaitable[tuple[Path, Path]]]`, and
   `impose()` is `async def`.** Shaped like `Runner`/`set_runner` in every way
   that isn't forced apart: a module-level hook, a `set_imposer()` to swap it,
   `subprocess_impose` as the unchanged default. The one difference is
   `async`, and it is a hard requirement, not a style choice — see Context.

2. **The CLI drives it with one `asyncio.run()` call, nothing else in the
   pipeline moves.** `cli.py:build()` still calls `compile_pdf` synchronously;
   only the final `impose()` call is wrapped. `subprocess_impose` itself does
   nothing genuinely asynchronous — it is `async def` only so the same
   function satisfies `Imposer` — so this changes nothing about how the CLI
   behaves, only how one call is spelled.

3. **The browser calls `impose()` through a second, separate `pyodide` entry
   point — `runPythonAsync`, not the `runPython` call `compile_pdf` uses.**
   `worker.mjs`'s `buildBooklet` runs the compile step exactly as before, then
   makes one further `await pyodide.runPythonAsync(...)` call for imposition.
   The JS-side imposer itself (`app/impose.mjs`) reads the compiled PDF out of
   Pyodide's filesystem, runs `pdf-lib`, and writes the two Montage outputs
   back — the same "the folder is the whole interface" shape `runner` uses,
   just async and with no engine pool to prepare (`pdf-lib` has no WebAssembly
   to instantiate).

## Consequences

- `libellus` gains its first `asyncio` usage, confined to one `asyncio.run()`
  in `cli.py` and one `await` in `worker.mjs`'s Python snippet. Nothing in
  `compile.py`'s gregorio/LuaTeX loop changes; ADR-0034's synchronous
  `Runner` requirement is untouched.
- `-pdfjam.pdf`/`-pdfjam-duplex.pdf` are renamed to `-montage.pdf`/
  `-montage-duplex.pdf` throughout — CONTEXT.md's **Montage** entry, the
  staged folder's `Makefile`, the README's "Bremen operations" section, and
  the two file writers themselves (`compile.py`'s `subprocess_impose`,
  `app/impose.mjs`'s `imposer`).
- `app/impose.mjs`'s page-pairing and rotation were checked against the real
  `pdfjam` + `pdftk` it replaces on a synthetic booklet, rather than trusted
  from the imposition formula alone — same page pairs, same rotated pages, and
  (on that synthetic, single-page-per-sheet input) pixel-identical raster.
- **On the real, multi-line booklet, the raster is *not* pixel-identical, and
  it does not need to be.** `pdfpages` (`pdfjam`'s engine) lands each source
  page at its own tiny scale — `1.00084`, not `1` — and a sub-point offset;
  reading its content stream shows why: LaTeX's built-in `a5paper` is 148mm,
  a rounding of true ISO A5 (148.5mm, exactly half of A4), so *some* scale
  factor is unavoidable, and `pdfpages`'s own fixed-point arithmetic is not
  worth reproducing bit for bit. `tests/test_browser_build.py` checks Montage
  correctness by extracted page text and rotation instead of a raster diff —
  the pairing and rotation are what could actually be wrong; the scale noise
  is not.
- This settles the question for Electron too, whenever #60 gets to it:
  Electron's renderer is not bound by GitHub Pages' COOP/COEP absence, so it
  *could* have `SharedArrayBuffer` — but the imposer seam no longer needs it
  to, so nothing about Electron's own constraints forces a third
  implementation of this seam.
