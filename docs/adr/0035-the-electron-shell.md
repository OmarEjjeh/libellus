# ADR-0035: The Electron shell — electron-builder, three platforms, unsigned, Tauri reserved

Date: 2026-08-03
Status: accepted
Scopes: ADR-0026 decisions 1, 2 and 8.

## Context

ADR-0026 decided Electron over a native-webview shell (decision 1) and named
it as one of three hosts, but left every concrete question about it
unanswered: packaging tool, target platforms, signing, and whether the
Toolchain ships inside the installer from day one. Nothing under this ADR
exists yet — no `package.json`, no npm workspace, no Electron main process.
`app/main.mjs` is the browser page's script, not an Electron shell.

## Decisions

1. **`electron-builder`, not `electron-forge`.** All three platforms
   (macOS, Windows, Linux) ship from the start, so installer-format breadth
   and code-signing/notarization support matter immediately rather than
   later. `electron-builder` is the more proven choice for that matrix;
   `electron-forge`'s simpler default config is a smaller win by comparison.

2. **Three platforms from v1.** Not a staged rollout — macOS, Windows and
   Linux all ship together, even though only macOS and Linux are proven
   today (the CLI's own install instructions never mention Windows). The
   reach motive behind the whole application (ADR-0026 motive 1) is about
   strangers who are not maintainers, and that audience is not
   Linux-only.

3. **Unsigned installers for v1.** Code signing and notarization (an Apple
   Developer Program membership, a Windows signing certificate) is deferred.
   It is a recurring cost decision independent of whether the shell works,
   and it bolts on later without touching any pipeline code — unlike the
   platform and packaging choices above. The README will carry the
   workaround instructions (Gatekeeper right-click-to-open, Windows SmartScreen
   "run anyway") until it lands.

4. **Fetch-and-cache on first run, not installer pre-seeding, for v1.**
   ADR-0026 decision 8 wants installers pre-seeded with the Toolchain so the
   application works offline from first launch; that is deferred here. Getting
   the shell itself right — a real filesystem as the Working directory, the
   existing pipeline wired into a `BrowserWindow`, imposition once ADR-0026
   decision 4 lands — is the actual unknown, the same way #57 proved the
   browser pipeline before ADR-0034 hardened it. Pre-seeding is a
   packaging-pipeline concern layered on top of a working shell, not a
   precondition for one.

5. **The pipeline runs unchanged, as a Web Worker inside a normal
   `BrowserWindow`.** `worker.mjs`, `engines.mjs` and `toolchain.mjs` are
   reused exactly as the browser build uses them; only the Working-directory
   access layer swaps from OPFS import/export to a real filesystem via IPC.
   Electron does not need the Worker for the reason the browser does (the
   8 MB main-thread WebAssembly-instantiation limit and GitHub Pages'
   COOP/COEP restriction — ADR-0034 — do not apply here), but dropping it
   would mean a second pipeline integration to prove matches the first,
   which is exactly what ADR-0026 decision 2 already rejected for a native
   TeX backend. One code path across both hosts is what makes "one web
   codebase everywhere" real rather than aspirational, and it is what keeps
   `tests/test_browser_build.py`-style comparisons meaningful across both.

6. **Tauri is the reserved eventual replacement, on all three platforms.**
   ADR-0026 decision 1 rejected a native-webview shell (Tauri: WebView2 on
   Windows, WebKit on macOS, WebKitGTK on Linux) in favor of Electron's own
   bundled Chromium, for engine consistency. That rejection had no reserved
   path back, unlike decision 2's explicit treatment of native TeX binaries
   ("remain available later as a speed optimisation behind the same
   interface"). This ADR gives Tauri the same status: a smaller,
   system-webview-based build is the intended long-term destination on
   every platform, not merely Windows, once the interface it sits behind is
   proven stable enough that swapping the shell under it is a contained
   change rather than a rewrite. Nothing today commits to a timeline for
   that swap.

## Consequences

- Installers are large: Electron bundles its own Chromium per platform,
  roughly 150–200 MB before the Toolchain is even considered. That cost is
  accepted for now in exchange for one identical engine on all three
  platforms; decision 6 records that it is not accepted forever.
- A permanently split shell (Electron on some platforms, something else on
  others) is explicitly not the plan — decision 6 describes one future
  target across all three platforms, not a per-platform fork, for the same
  reason ADR-0026 decision 2 rejects a permanent native/WASM fork: a second
  thing to maintain forever.
