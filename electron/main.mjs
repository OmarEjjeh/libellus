// The Electron shell (#60, ADR-0035): a `BrowserWindow` running the exact same
// `app/*.mjs` code the browser host runs, over a privileged custom scheme
// instead of an http(s) origin.
//
// ADR-0035 decision 5 is the whole design: `worker.mjs`, `engines.mjs` and
// `toolchain.mjs` are reused completely unchanged — not a single line here
// patches them. That is only possible because they already talk to their
// "origin" through root-relative `fetch()` calls (`/app/workdir.json`,
// `/feasts/…`, `/toolchain/manifest.json`, `/dist/…`), which is exactly what
// `app/serve.py` serves for the browser host today. This file reproduces that
// same URL shape under `libellus://bundle/…`, so nothing downstream can tell
// the difference.
//
// What genuinely differs per host, per decision 5, is the Working-directory
// access layer. For this v1 that is a narrow difference: the browser's dev
// page and this shell both read `feasts/`, `images/` and `psalter/` straight
// off disk (no import/export step exists yet on either host — the editor
// that would add one is untracked, separately, as its own open problem). What
// changes here is *which* disk: a packaged build's `resourcesPath` rather
// than a repo checkout, and packaging deliberately leaves the Working
// directory empty — see the licensing note below.

import { app, BrowserWindow, dialog, ipcMain, net, powerSaveBlocker, protocol } from "electron";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.join(__dirname, "..");

/**
 * Where bundled resources live: a repo checkout in dev, `resourcesPath` in a
 * packaged build (electron-builder's `extraResources`, see package.json).
 */
function resourceRoot(name) {
  return app.isPackaged ? path.join(process.resourcesPath, name) : path.join(REPO_ROOT, name);
}

/**
 * The Working directory this shell reads from — `feasts/`, `images/` and
 * `psalter/`, same as `app/serve.py`'s dev server. Mutable: `openWorkdir()`
 * (#70) repoints it at whatever folder the user picks, over IPC.
 *
 * Defaults to `resourcesPath` packaged, `REPO_ROOT` in dev — deliberately not
 * a bundled feast: both demo feasts resolve German from `psalter/`, which is
 * the Einheitsübersetzung, © Katholische Bibelanstalt and not redistributable
 * (ADR-0007, ADR-0023; `serve.py`'s own comment says the same), and it is not
 * part of `extraResources` (see package.json) for exactly that reason. A
 * packaged build therefore finds no `feasts/`/`images/`/`psalter/` under
 * `resourcesPath` and reports an empty Working directory, honestly, until the
 * user opens one — restored from `settings.json` (below) if they have
 * already opened one in a previous session.
 */
let workdirRoot = app.isPackaged ? process.resourcesPath : REPO_ROOT;

/** Where the last-opened Working directory is remembered across launches. */
function settingsPath() {
  return path.join(app.getPath("userData"), "settings.json");
}

/** The persisted Working directory, if `settings.json` names one that still exists. */
function loadPersistedWorkdirRoot() {
  try {
    const { workdirRoot: persisted } = JSON.parse(readFileSync(settingsPath(), "utf8"));
    if (persisted && existsSync(persisted)) return persisted;
  } catch {
    /* no settings.json yet, or unreadable — keep the default above */
  }
  return null;
}

function persistWorkdirRoot(root) {
  writeFileSync(settingsPath(), JSON.stringify({ workdirRoot: root }));
}

/** Show the native folder-picker; if the user picks one, adopt and remember it. */
async function openWorkdir() {
  const result = await dialog.showOpenDialog({ properties: ["openDirectory"] });
  if (result.canceled || result.filePaths.length === 0) return null;
  workdirRoot = result.filePaths[0];
  persistWorkdirRoot(workdirRoot);
  return workdirRoot;
}

// Fetched fresh from the pinned release on every `/toolchain/…` request, the
// same way `app/serve.py` serves `manifest.json` fresh on every visit — only
// the big files are cache-checked, by `toolchain.mjs`'s own OPFS layer
// (unchanged, and confirmed to work under a `standard: true` custom scheme;
// see the protocol registration below). No separate disk cache is built here:
// that would just be a second cache next to the one the reused code already
// has. Bump alongside `worker.mjs`'s `TOOLCHAIN_VERSION_PIN` when the
// Toolchain release changes.
const TOOLCHAIN_RELEASE =
  "https://github.com/OmarEjjeh/libellus/releases/download/toolchain-v1";

// `manifest.json`'s `files` only lists the six toolchain binaries worker.mjs
// cache-checks by size; the three pure-Python wheels it also installs carry
// their version in the filename and aren't in that list, so — like the
// version pin above — they are named outright rather than discovered.
const VENDORED_WHEELS = {
  typer: "typer-0.27.0-py3-none-any.whl",
  pypdf: "pypdf-6.14.2-py3-none-any.whl",
  shellingham: "shellingham-1.5.4-py2.py3-none-any.whl",
};

/** The Working-directory content `workdir.json` lists, mirroring serve.py's CONTENT. */
const WORKDIR_CONTENT = [
  ["feasts", ".yaml"],
  ["images", null],
  ["psalter", ".yaml"],
];

async function libellusWheelName() {
  const distDir = resourceRoot("dist");
  const entries = await readdir(distDir).catch(() => []);
  const wheel = entries.find((name) => name.startsWith("libellus-") && name.endsWith(".whl"));
  if (!wheel) {
    throw new Error(`no libellus-*.whl in ${distDir} — run \`npm run predist\` first`);
  }
  return wheel;
}

async function wheelsJson() {
  return JSON.stringify({ ...VENDORED_WHEELS, libellus: await libellusWheelName() });
}

/** Every file under `root/directory` matching `suffix`, as root-relative posix paths. */
async function listContentFiles(root, directory, suffix) {
  const base = path.join(root, directory);
  if (!existsSync(base)) return [];
  const found = [];
  const walk = async (dir, prefix) => {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) await walk(path.join(dir, entry.name), relative);
      else if (!suffix || entry.name.endsWith(suffix)) found.push(`${directory}/${relative}`);
    }
  };
  await walk(base, "");
  return found;
}

async function workdirJson() {
  const files = await Promise.all(
    WORKDIR_CONTENT.map(([directory, suffix]) => listContentFiles(workdirRoot, directory, suffix))
  );
  return JSON.stringify(files.flat());
}

const jsonResponse = (body) => new Response(body, { headers: { "content-type": "application/json" } });

/** Resolve `pathname` under `root`, refusing to let it escape — same discipline the protocol docs' own "bundle" example uses. */
function safeJoin(root, pathname) {
  const resolved = path.normalize(path.join(root, pathname));
  if (resolved !== root && !resolved.startsWith(root + path.sep)) return null;
  return resolved;
}

/** Serve a file straight off disk. */
function serveFile(fullPath) {
  if (!fullPath || !existsSync(fullPath)) return new Response("not found", { status: 404 });
  return net.fetch(pathToFileURL(fullPath).toString());
}

// `.mjs`/`.whl` matter most: a module `import()` (pyodide.mjs, gregorio.mjs)
// enforces strict MIME checking and a mis-typed response fails outright — and
// GitHub's release-asset CDN serves everything as `application/octet-stream`
// regardless of extension, discovered when `/toolchain/pyodide.mjs` (proxied
// straight through) failed exactly that check. Applied uniformly to every
// route below rather than trusted to sniffing, local or proxied alike.
const MIME = {
  ".mjs": "text/javascript",
  ".js": "text/javascript",
  ".wasm": "application/wasm",
  ".json": "application/json",
  ".whl": "application/zip",
  ".html": "text/html",
};

function withContentType(response, pathname) {
  const contentType = MIME[path.extname(pathname)];
  if (!contentType || !response.ok) return response;
  const headers = new Headers(response.headers);
  headers.set("content-type", contentType);
  return new Response(response.body, { status: response.status, headers });
}

async function route(pathname) {
  if (pathname === "/" || pathname === "/app/index.html") {
    return serveFile(path.join(resourceRoot("app"), "index.html"));
  }
  if (pathname === "/app/wheels.json") return jsonResponse(await wheelsJson());
  if (pathname === "/app/workdir.json") return jsonResponse(await workdirJson());
  if (pathname.startsWith("/app/")) {
    return serveFile(safeJoin(resourceRoot("app"), pathname.slice("/app".length)));
  }
  if (pathname.startsWith("/dist/")) {
    return serveFile(safeJoin(resourceRoot("dist"), pathname.slice("/dist".length)));
  }
  if (pathname.startsWith("/feasts/") || pathname.startsWith("/images/") || pathname.startsWith("/psalter/")) {
    return serveFile(safeJoin(workdirRoot, pathname));
  }
  if (pathname.startsWith("/toolchain/")) {
    return net.fetch(`${TOOLCHAIN_RELEASE}${pathname.slice("/toolchain".length)}`);
  }
  return new Response("not found", { status: 404 });
}

// Privileged so `fetch()`, module `import()`, module Workers and OPFS all
// work under this scheme exactly as they do on an http(s) origin — the same
// three things `app/serve.py`'s plain-HTTP-no-isolation-headers approach
// gets the browser host for free (ADR-0034).
protocol.registerSchemesAsPrivileged([
  {
    scheme: "libellus",
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
  },
]);

app.whenReady().then(() => {
  workdirRoot = loadPersistedWorkdirRoot() ?? workdirRoot;

  protocol.handle("libellus", async (request) => {
    const { pathname } = new URL(request.url);
    return withContentType(await route(pathname), pathname);
  });

  ipcMain.handle("workdir:open", () => openWorkdir());

  createWindow();
});

function createWindow() {
  // Chromium throttles a backgrounded/occluded renderer's timers, and macOS
  // App Nap throttles the whole process below that — both power-saving
  // measures aimed at idle apps, neither aware that this "idle-looking"
  // window is running a synchronous WebAssembly compile on its Worker
  // thread. `backgroundThrottling: false` opts the renderer out;
  // `powerSaveBlocker` opts the process out of App Nap. Without both, a
  // build that takes ~2 minutes focused can take 4x that unfocused.
  powerSaveBlocker.start("prevent-app-suspension");
  const window = new BrowserWindow({
    width: 900,
    height: 720,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });
  // `main.mjs`'s `log()` already prints every pipeline message to `console.log`
  // (unchanged — see its own comment on why); forwarding that to the main
  // process's stdout is what makes a headless run diagnosable at all.
  window.webContents.on("console-message", (event) => {
    console.log(`[renderer] ${event.message}`);
  });
  window.loadURL("libellus://bundle/app/index.html");
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
