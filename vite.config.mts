/// <reference types="vitest/config" />
import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

/**
 * The editing surface (#91 slice 1): Preact + TSX + Vite, per ADR-0028
 * decision 2.
 *
 * `.mts` rather than `.ts` because the repository's `package.json` cannot say
 * `"type": "module"`: the vendored psalm-tone engine
 * (`src/libellus/psalm-library/generate.js`) is CommonJS, and every build of
 * every feast runs it through `node` (ADR-0024). Declaring the package ESM
 * makes that file fail to load — `tests/test_psalmengine_browser.py` says so
 * within a second, in both hosts at once.
 *
 * Three settings carry the whole host integration and none of them is a
 * matter of taste:
 *
 * - `base: "/app/"` — both hosts serve this application under `/app/`, the
 *   browser one from `app/serve.py` and Electron by mapping
 *   `libellus://bundle/app/…` onto disk. Built asset URLs have to agree with
 *   that or nothing resolves.
 * - `publicDir: "pipeline"` — `worker.mjs`, `engines.mjs`, `toolchain.mjs`,
 *   `impose.mjs`, `psalmengine.mjs`, `tar.mjs` and the vendored `pdf-lib` are
 *   copied out verbatim rather than bundled, in dev and in a build alike.
 *   ADR-0035 decision 5 says they are reused unchanged; Vite's public
 *   directory is that promise expressed in the build system, and it keeps
 *   their served URLs (`/app/worker.mjs`, `/app/vendor/…`) exactly where they
 *   already were, which is what `worker.mjs`'s own `fetch("./wheels.json")`
 *   and `impose.mjs`'s relative import depend on.
 * - `outDir: "dist"` — i.e. `app/dist/`, gitignored, and what both hosts
 *   actually serve. Distinct from the repository's `dist/`, which is the
 *   Python wheel's.
 */
export default defineConfig({
  root: "app",
  base: "/app/",
  publicDir: "pipeline",
  // Vite's dependency cache defaults to `<root>/node_modules/.vite`, which here
  // would be a second, half-empty `app/node_modules/` beside the real one.
  cacheDir: "../node_modules/.vite",
  plugins: [preact()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // A successor reading the shipped bundle should be able to find their way
    // back to the source; the cost is a few hundred KB nobody downloads twice.
    sourcemap: true,
  },
  server: {
    // `npm run dev` gives the editor hot reload, but everything the pipeline
    // needs — the wheel, the Toolchain, the Working directory — is still
    // `app/serve.py`'s to serve, so run both and let Vite forward. Same URL
    // shape as a built page, so nothing downstream can tell the difference.
    proxy: Object.fromEntries(
      [
        "/app/wheels.json",
        "/app/workdir.json",
        "/dist",
        "/feasts",
        "/images",
        "/psalter",
        "/toolchain",
      ].map((route) => [route, { target: "http://127.0.0.1:8017", changeOrigin: false }]),
    ),
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
});
