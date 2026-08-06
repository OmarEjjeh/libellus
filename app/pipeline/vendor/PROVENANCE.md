# Provenance

`pdf-lib.esm.min.js` is an **unmodified** build artefact from upstream
*pdf-lib*, used unbuilt because this application has no bundler (#57's plain
`<script type="module">`/Worker-import setup) — same reason `busytex.js` and
`gregorio.mjs` are vendored rather than installed.

| | |
|---|---|
| Upstream package | [`pdf-lib`](https://www.npmjs.com/package/pdf-lib) on npm |
| Version | `1.17.1` |
| File taken | `dist/pdf-lib.esm.min.js` from the published npm tarball — a self-contained ES module, no `import`s of its own |
| Fetched | 2026-08-03 (`npm pack pdf-lib`, then copied out of the tarball) |
| License | **MIT** — full text in [`LICENSE.md`](LICENSE.md), copied from the same tarball |
| SHA-256 | `72c052d97b4d5d9fa6cdbdcb7ad709f03d4ddb1122390cb3afeba4d88651d969` |

Used by `app/impose.mjs` for the Montage step (ADR-0026 decision 4): 2-up
landscape booklet imposition plus the duplex page rotation, replacing
`pdfjam`/`pdftk` in the browser and (eventually) Electron.

## Verifying

```
npm pack pdf-lib@1.17.1
tar xzf pdf-lib-1.17.1.tgz package/dist/pdf-lib.esm.min.js package/LICENSE.md
shasum -a 256 package/dist/pdf-lib.esm.min.js
```

## When updating

Pick a new pinned version deliberately, re-copy `dist/pdf-lib.esm.min.js` and
`LICENSE.md` unmodified, update the version/SHA-256 above, and re-run
`tests/test_browser_build.py` — it is the check that would notice a
behavioural change in the Montage output.
