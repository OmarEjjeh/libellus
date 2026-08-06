# ADR-0046: The application is a build, and both hosts serve the build — the pipeline modules are copied through it untouched

Date: 2026-08-06
Status: accepted
Scopes: ADR-0028 decision 2, ADR-0034, ADR-0035 decision 5.

## Context

ADR-0028 decision 2 settled the stack — Preact + TSX + Vite, `htm` gone — and
never said what that does to the two hosts, because at the time neither
existed in the shape it now has. Both serve `app/` straight off disk with no
build step in between:

- `app/serve.py` serves the repository root, `/app/*` included;
- `electron/main.mjs` maps `libellus://bundle/app/…` onto `resourceRoot("app")`,
  and `package.json`'s `extraResources` copies `app` verbatim into a packaged
  build.

Introducing a build makes what gets served *output* rather than *source*, which
touches all three of those at once. Get it wrong and a working pipeline breaks
in both hosts, silently: the browser is handed an `index.html` whose
`<script src="/src/main.tsx">` no engine can run, and shows a blank page with
nothing in the log to say why.

Cutting across that is ADR-0035 decision 5, which reuses `worker.mjs`,
`engines.mjs`, `toolchain.mjs`, `impose.mjs`, `psalmengine.mjs` and `tar.mjs`
*completely unchanged* in the Electron shell. That is only possible because
they address their host through root-relative `fetch()` and worker-relative
imports — `worker.mjs` fetches `./wheels.json`, `impose.mjs` imports
`./vendor/pdf-lib.esm.min.js`, `engines.mjs` `import()`s a URL it computes.
A bundler that decided to inline any of that would break the reuse the ADR
rests on.

## Decisions

1. **`app/` is source; `app/dist/` is what both hosts serve.** `vite build`
   with `root: "app"`, `base: "/app/"` and `outDir: "dist"`. The URL shape is
   deliberately unchanged — `/app/index.html`, `/app/worker.mjs`,
   `/app/vendor/…` are all where they were — so the change is confined to one
   path rewrite per host rather than spread through the code that fetches.
   `app/dist/` is gitignored, and named `dist` inside `app/` rather than at the
   root, where `dist/` is already the Python wheel's.

2. **The pipeline modules go through Vite's *public directory*, not its
   bundler.** `publicDir: "pipeline"` — i.e. `app/pipeline/` — which Vite
   copies out verbatim, in a build and in `npm run dev` alike, and which lands
   its contents at the top of the output. This is ADR-0035 decision 5 expressed
   in the build system rather than in prose: those six modules and the vendored
   `pdf-lib` are now structurally incapable of being transformed, and a test
   compares the copies against the sources byte for byte.

   The alternative — leaving them in the Vite root and letting the dev server
   transform them — was rejected for making dev and build differ for exactly
   the files that must not differ from themselves.

3. **`app/serve.py` builds the application the way it already builds the
   wheel.** Not merely checks for it: a stale bundle is served in silence and
   presents as a code change that had no effect. `npm run dev` (with the config's
   proxy pointing everything the pipeline needs back at `serve.py`) is the loop
   for working on the editor; `serve.py` is the loop for working on everything
   under it.

4. **The repository's `package.json` may not declare `"type": "module"`.** The
   vendored psalm-tone engine, `src/libellus/psalm-library/generate.js`, is
   CommonJS, and every build of every feast runs it through `node` (ADR-0024).
   Declaring the package ESM makes that file fail to load in both hosts at
   once. The Vite config is therefore `vite.config.mts`, which is ESM by
   extension and needs no such declaration.

## Consequences

- `app/worker.mjs` and its five siblings move to `app/pipeline/`, and
  `app/vendor/` to `app/pipeline/vendor/`, with no change to their contents.
  `app/main.mjs` is deleted; `app/src/` replaces it.
- `electron/main.mjs` grows an `applicationRoot()` beside `resourceRoot()`,
  because the two hosts diverge in development and converge again when packaged
  — `extraResources` copies `app/dist` to `app`. Its `MIME` table gains `.css`
  and `.map`, which a build emits and a hand-written page never did.
- Decision 4 was found by making the mistake: setting `"type": "module"` turned
  `tests/test_psalmengine_browser.py` red within a second. That test exists
  because the browser and native psalm-tone engines must agree byte for byte,
  and it happens also to be the only thing in the suite that would have caught
  this. Worth knowing if it is ever proposed for deletion.
- Nothing about ADR-0034's no-`SharedArrayBuffer`, no-COOP/COEP arrangement
  changes: the build emits ordinary ES modules, and
  `tests/test_browser_build.py` still builds both Lambertus booklets
  pixel-identically to a native build, with the same page counts, through the
  built application.
- A worktree needs its own `npm install` — `scripts/worktree-add.sh` does not
  share `node_modules` — and now needs it before `app/serve.py` will start at
  all, rather than only before `npm start`.
