# ADR-0028: The editor is the application — Preact keeps its job, the data island and the static API lose theirs

Date: 2026-08-01
Status: accepted
Amends: ADR-0003. Supersedes ADR-0004. Retires ADR-0006's mechanism while
keeping its rule.

## Context

Three decisions about the form were workarounds for the same missing capability:
the form had no build step, no schema, and no backend.

| ADR | Decision | Because |
|---|---|---|
| 0003 | preact + htm + eemeli/yaml, one self-contained HTML file | must work from `file://` with no build step |
| 0004 | the form validates against a generated **data island** | the form could not run the Python schema |
| 0006 | **static API** on `raw.githubusercontent.com` + **companion data** in `form/daten/` | no backend, and GregoBase sends no CORS header |

ADR-0026 gives the application a build step, a filesystem and a bundled corpus,
and ADR-0027 makes the schema itself JavaScript. All three premises are gone at
once.

## Decisions

1. **The application absorbs the form.** The standalone single-file HTML page is
   retired as a maintained artifact. Its entire value was zero-install authoring,
   and the application is zero-install authoring that can also produce a PDF.
   Maintaining two editors against one schema has no remaining payer.

   This costs no fallback layer. The documented floor is better than the form
   anyway — layer 4: "if all tooling bitrots, the YAML still documents intent and
   the template can be filled by hand." An editor that cannot compile is not a
   fallback, it is a second thing to keep working.

2. **ADR-0003 is amended, not superseded. Preact stays; `htm` goes.** Preact was
   a good call and remains one — its size still matters for the browser target.
   `htm` exists solely to avoid a JSX build step, and there now is one: Preact +
   TSX + Vite. `eemeli/yaml` survives untouched, because it is the only JS YAML
   library that round-trips comments, which is what keeps hand-edited
   `feasts/*.yaml` readable after the application writes to them.

3. **The data island dissolves.** With the schema as Zod in `core`, the editor
   imports the real vocabularies — valid toni, ordinarium names, psalms with
   German — and validates against the real schema. One definition, no generation
   step, no drift. This is the largest correctness gain in the port and deserves
   naming as such: today the form and the pipeline *can* disagree, and afterwards
   they cannot.

4. **ADR-0006 splits, and the split is the whole point.** Its *mechanism*
   retires — no `raw.githubusercontent.com`, no CORS workaround, no `form/daten/`
   fallback, no per-item fetch — because GregoBase and the Clementine Bible
   become **Bundled data** in the Toolchain. Its **rule** survives verbatim and
   load-bearing: *only public-domain/CC0 content ever enters the public repo*,
   with its one recorded exception (the gilded border tiles, ADR-0014). That rule
   is what keeps the Einheitsübersetzung out of a public artifact and what makes
   bundling a public-domain Psalter legitimate. Marking ADR-0006 superseded
   wholesale would lose it, which is why this ADR retires the mechanism only.

5. **`file://` is no longer supported, and the cause is worth recording
   accurately.** It is not the build step: a bundler can emit a single classic
   `<script>` that loads from disk. It is the WASM toolchain — OPFS has no
   storage on an opaque origin, Workers are blocked over `file://` in Chromium,
   and `fetch()` of local files is blocked, so a WASM module cannot stream in its
   texmf tree. Any one of those is fatal and all three apply. If the form had kept
   `htm` and hand-written JS it would have lost `file://` anyway the moment TeX
   entered the browser.

   Electron sidesteps it: the built assets load through a custom protocol handler,
   which is a real origin, so OPFS, Workers and `SharedArrayBuffer` all work.

6. **Whether the browser build needs COOP/COEP headers is a spike deliverable.**
   Emscripten builds often want `SharedArrayBuffer`, which requires
   `Cross-Origin-Opener-Policy: same-origin` and
   `Cross-Origin-Embedder-Policy: require-corp` — and GitHub Pages cannot set
   custom headers. TeXlyre's own demo runs on `texlyre.github.io`, so it is
   evidently solvable, either because their build needs no SAB or via the
   standard `coi-serviceworker` trick. Which one it is decides whether Pages is a
   viable host, so the spike must answer it rather than assume.

## Consequences

- Four glossary terms retire — **The form** as a standalone page (the word stays,
  redefined as the application's editing surface, because `form/`, `formdata.py`
  and `tests/test_form.py` all use it), **Data island**, **Static API**,
  **Companion data**. **Numbered paste** survives unchanged as an editor feature.
- Roughly half the open issue backlog needs re-triage: #19 and #27 are largely
  invalidated (static-API groundwork, data-island wiring), while #17, #18, #20,
  #21, #22, #23, #25, #29 and #30 survive as application features against a
  different data source.
- The editor can no longer be edited by opening a `.html` file and refreshing.
  `npm run dev` replaces that, with hot reload and type errors — an upgrade for a
  maintainer, and a real loss of the "view source, change a line" property for a
  successor. Accepted, because the schema and the editor sharing one definition
  is worth more.
