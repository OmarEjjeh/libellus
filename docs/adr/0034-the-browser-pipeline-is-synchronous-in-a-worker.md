# ADR-0034: The browser pipeline is synchronous, pre-instantiated, and lives in a Worker

Date: 2026-08-02
Status: accepted
Scopes: ADR-0026 decision 7, ADR-0027 decision 1.

## Context

ADR-0026 put the pipeline in a browser and ADR-0027 chose Pyodide as the
scaffolding. Spike #43 proved the two bets that could fail outright — gregorio
compiles to WebAssembly with byte-identical output, and LuaHBTeX compiles our
preamble pixel-identically. Neither spike ran the pipeline; both drove the
engines directly from Node.

Issue #57 wired them together, and the wiring turned out to have a constraint
the spikes could not have seen. It is a chain, and every link is forced:

1. **GitHub Pages must be able to host the page** (ADR-0026 decision 7). It
   cannot send `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy`.
2. Without those headers there is no cross-origin isolation, so there is **no
   `SharedArrayBuffer`**.
3. Without `SharedArrayBuffer` there is no way for **synchronous Python to
   await a JavaScript promise**. Pyodide's own escape hatch for this needs
   either SAB or JSPI, and JSPI is Chromium-only — which would cost the
   first-class Firefox and Safari support ADR-0026 decision 7 exists to protect.
4. `compile.py`'s Runner is therefore synchronous, and **must stay** synchronous
   — which means every asynchronous step has to finish before the compile is
   entered.
5. Instantiating a WebAssembly module is asynchronous. The synchronous form,
   `new WebAssembly.Instance()`, is **refused on the main thread for any module
   over 8 MB**. `busytex.wasm` is 31 MB.

## Decisions

1. **The seam is an injectable backend in `psalmtone.py` and `compile.py`, not
   a monkeypatch and not a browser module inside the wheel.** Each has one
   module-level hook — `set_engine`, `set_runner` — defaulting to today's
   subprocess implementation, so the CLI is unchanged and the browser opts in.

   `compile.py`'s hook is deliberately placed as low as it can go:
   `Runner(command, folder) -> stdout`. Everything above it is host-independent
   and stays in Python — which scores to set, how many passes the layout may
   take, when it has settled. That loop is the fix for #56, and a second
   implementation of it in JavaScript would be a second thing to get wrong.

   The Runner does **not** report an exit status, because neither caller may
   use one: gregorio exits non-zero for a score it none the less sets usably
   (ADR-0032 decision 4), and lualatex under `nonstopmode` exits non-zero on a
   recovered error. Both judge the artefact instead.

2. **The whole pipeline runs in a Web Worker**, for correctness rather than for
   responsiveness — step 5 above. This is the finding of #57 and it is not in
   any documentation the spike consulted; Node has no such limit, so it could
   only have surfaced here.

3. **Engine instances are pre-created into a pool sized to the work.** Neither
   engine survives a second `callMain`: luatex aborts in `create_null_font`,
   and gregorio — which spike #43 only *assumed* needed a fresh instance per
   score — throws `memory access out of bounds` on the second call and is
   corrupt thereafter. So the pool holds one gregorio per `.gabc` plus one for
   the version probe, and `MAX_PASSES` busytex instances.

   This is affordable, which is why it is allowed to be the answer: 0.6 MB and
   0.4 ms per gregorio instance (77 of them cost 48 MB and 30 ms), ~25 MB per
   busytex instance. The pool is sized after staging, because how many scores a
   feast needs is not known until then.

4. **The Toolchain is assembled locally for now, and published later.** ADR-0026
   decision 8 makes it a separately versioned GitHub release asset, fetched on
   first use and cached. #57 builds it into a gitignored `toolchain/` with
   `scripts/toolchain/build.sh` and serves it from the dev server instead. The
   layout, the manifest and the OPFS caching are already the shape the release
   asset needs, so only the base URL changes. Pyodide itself is still loaded
   from its CDN and belongs in that asset too.

5. **The texmf tree's file list is committed data, not a recorder run.** It was
   derived once by `collect-deps.sh`, which needs `--shell-escape` over a
   staged booklet and a native TeX Live. Keeping the *output*
   (`scripts/toolchain/texmf-files.txt`) rather than the run is what lets the
   Toolchain be rebuilt from a clean checkout. The list is knowingly
   insufficient on its own — a recorder records what one run opened, and a cold
   start opens more — so `build.sh` widens it in the three documented places.

## Consequences

- **`compile.py` gained a real bug fix on the way.** The version was read as
  `banner.split()[1]`, which is `"6.1.0"` for a gregorio built with kpathsea
  and `"6.1.0."` for one without — and the WebAssembly build has no kpathsea.
  The trailing dot became `-6_1_0_.gtex`, GregorioTeX looked for
  `-6_1_0.gtex`, found nothing, tried to autocompile and could not. The booklet
  still built, with **every score silently missing**: 16 pages instead of 36,
  no LaTeX error, nothing raised. It is now parsed with a pattern and tested
  against all three banner forms. This class of failure — a wrong filename
  producing a shorter but valid booklet — is exactly what a page-count or
  pixel check catches and a "did it compile" check does not.

- **The psalm-tone engine runs in the page, and `generate.js` is untouched.**
  Reproducing `vm.runInContext` faithfully needs both halves of what a vm
  context does, because upstream creates its helpers two ways: `var
  gloria_patri = …` is a declaration, while `var o_g_tones = g_tones = {…}`
  makes `g_tones` an *implicit global*. Handling only declarations yields
  silently empty notation. `tests/test_psalmengine_browser.py` compares the two
  hosts byte for byte on every command the pipeline issues.

- **Imposition still shells out.** ADR-0026 decision 4 replaces `pdfjam` and
  `pdftk` with `pdf-lib`; until then the browser stops at the booklet PDF,
  which is what #57 asked for.

- **`file://` is confirmed dead**, as ADR-0026 decision 7 anticipated: OPFS has
  no storage on an opaque origin, and the Worker could not be loaded either.

- The Python package keeps working exactly as before. Both seams default to the
  subprocess, and the 319-test suite passes unchanged.
