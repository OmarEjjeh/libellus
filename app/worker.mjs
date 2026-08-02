// The tracer bullet (#57): the whole pipeline, in a Worker.
//
// One vertical cut through ADR-0026's design — no Electron, no editor, no
// TypeScript port. The Python pipeline runs unchanged under Pyodide; only the
// two places that shelled out to a process are replaced, through the seams
// `libellus.psalmtone` and `libellus.compile` expose (ADR-0027 decision 1).
//
// A Worker rather than the page, and not for responsiveness: synchronous
// instantiation of a module as large as busytex.wasm is forbidden on the main
// thread, and synchronous instantiation is what the whole no-SharedArrayBuffer
// design rests on. engines.mjs has the chain of reasoning.
//
// The order below is likewise not a matter of taste. Everything asynchronous —
// fetching, compiling WebAssembly, pre-creating engine instances — has to
// finish before the compile is entered, because the Runner that Python calls
// is an ordinary synchronous function and cannot await.

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.mjs";

import { Engines } from "./engines.mjs";
import { psalmEngine } from "./psalmengine.mjs";
import { cachedFormat, fetchToolchain } from "./toolchain.mjs";

// Pyodide itself is still fetched from its CDN rather than bundled. That is
// the one piece of ADR-0026 decision 8 this issue does not implement: when the
// Toolchain becomes a published, versioned release asset, Pyodide belongs in
// it, and then the application is genuinely offline-capable.
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
const TOOLCHAIN = "/toolchain";

/** Pyodide's own distribution carries the rest of libellus' dependencies. */
const VENDORED_WHEELS = ["typer", "pypdf", "shellingham"];

const log = (message) => self.postMessage({ type: "log", message });

/** Everything that has to happen once, before any booklet can be built. */
async function boot() {
  log("Lade Pyodide…");
  const pyodide = await loadPyodide({ indexURL: PYODIDE });

  log("Installiere libellus…");
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");
  const wheels = await (await fetch("./wheels.json")).json();
  for (const name of VENDORED_WHEELS) {
    await micropip.install(`${TOOLCHAIN}/wheels/${wheels[name]}`);
  }
  await micropip.install(`/dist/${wheels.libellus}`);

  await loadWorkingDirectory(pyodide);

  const { manifest, files } = await fetchToolchain(TOOLCHAIN, log);
  const engines = new Engines(log);
  await engines.load(files);
  await engines.prepareFormat(await cachedFormat(manifest.busytex));

  // Both seams are installed once. The psalm-tone engine is pure JavaScript
  // and needs nothing prepared; the compile runner draws on pools that are
  // refilled per booklet, but the function itself never changes.
  pyodide.registerJsModule("libellus_host", {
    psalmEngine: psalmEngine(pyodide),
    runner: engines.runner(pyodide.FS),
  });
  pyodide.runPython(`
import libellus.compile
import libellus.psalmtone
from libellus_host import psalmEngine, runner

def _browser_engine(args):
    returncode, stdout, stderr = psalmEngine(list(args))
    return returncode, stdout, stderr

libellus.psalmtone.set_engine(_browser_engine)
libellus.compile.set_runner(lambda command, folder: runner(list(command), str(folder)))
`);

  // The pipeline says a great deal through `logging` — which scores were set,
  // how many passes the layout took, what gregorio complained about — and the
  // CLI shows all of it. Dropping it in the browser would make every failure
  // look like silence.
  pyodide.registerJsModule("libellus_log", { write: log });
  pyodide.runPython(`
import logging
from libellus_log import write

class _PageHandler(logging.Handler):
    def emit(self, record):
        write(f"{record.levelname[0]} {record.name.split('.')[-1]}: {record.getMessage()}")

logging.basicConfig(level=logging.INFO, handlers=[_PageHandler()], force=True)
`);

  log("Bereit.");
  return { pyodide, engines };
}

/**
 * Copy the Working directory into Pyodide's filesystem.
 *
 * The wheel carries the *tool* — the chant library, the skeletons, the border
 * tiles, the psalm-tone engine (ADR-0024). It deliberately does not carry
 * anyone's content, so the feast specs, their pictures and the Psalter are
 * fetched separately. In the finished application this is an imported folder
 * living in OPFS (ADR-0026 decision 7); here it is the checkout the dev server
 * is running out of.
 */
async function loadWorkingDirectory(pyodide) {
  const files = await (await fetch("./workdir.json")).json();
  for (const path of files) {
    const parent = path.split("/").slice(0, -1).join("/");
    let current = "";
    for (const segment of parent.split("/")) {
      current += (current ? "/" : "") + segment;
      try {
        pyodide.FS.mkdir(current);
      } catch {
        /* already there */
      }
    }
    const response = await fetch(`/${path}`);
    pyodide.FS.writeFile(path, new Uint8Array(await response.arrayBuffer()));
  }
  log(`Arbeitsverzeichnis: ${files.length} Dateien.`);
}

/**
 * Build one booklet, exactly as the CLI does up to the point a browser can
 * follow: validate, resolve, render and stage in Python, then compile.
 *
 * Staging first is not a convenience — the engine pool has to be sized to the
 * work, and how many scores a feast needs is only known once it is staged.
 */
async function buildBooklet({ pyodide, engines }, feast, compact) {
  const started = performance.now();
  log(`\n=== ${feast}${compact ? " (Kurzfassung)" : ""} ===`);

  // `run_latex=False` stops exactly where a browser's capability stops, and
  // reuses the CLI's own naming: the Kurzfassung's separate stem, the draft
  // stamp, all of it. Nothing about the booklet is decided here.
  //
  // A rejected feast file crosses as its list of German sentences, never as a
  // traceback (ADR-0027 decision 2): a parish reading "Das Feld „tonus“ fehlt"
  // can fix it, and a Python stack tells them nothing.
  const staging = pyodide.runPython(`
import json
from pathlib import Path
from libellus.cli import build
from libellus.errors import FeastFileError

try:
    _folder = build(
        Path("feasts/${feast}.yaml"), Path("."),
        run_latex=False, compact=${compact ? "True" : "False"},
    )
    _result = {"ok": True, "folder": str(_folder)}
except FeastFileError as exc:
    _result = {"ok": False, "problems": list(exc.messages)}
json.dumps(_result)
`);
  const staged = JSON.parse(staging);
  if (!staged.ok) {
    for (const problem of staged.problems) log(`  • ${problem}`);
    throw new Error(
      `Die Fest-Datei hat ${staged.problems.length} Fehler:\n` +
      staged.problems.map((p) => `  • ${p}`).join("\n")
    );
  }
  const stagedFolder = staged.folder;
  const stem = stagedFolder.split("/").pop();
  log(`Satzordner: ${stagedFolder}`);

  const scores = pyodide.runPython(
    `len(list(Path("${stagedFolder}").glob("chant/**/*.gabc")))`
  );
  const passes = pyodide.runPython("import libellus.compile as c; c.MAX_PASSES");
  await engines.prepare(scores, passes);

  log(`Setze ${scores} Gesänge und übersetze…`);
  pyodide.runPython(`
from libellus.compile import compile_pdf, page_count
pdf = compile_pdf(Path("${stagedFolder}") / "${stem}.tex")
print(f"{pdf} — {page_count(pdf)} Seiten")
`);

  const bytes = pyodide.FS.readFile(`${stagedFolder}/${stem}.pdf`);
  const seconds = ((performance.now() - started) / 1000).toFixed(1);
  log(`Fertig in ${seconds} s — ${(bytes.length / 1048576).toFixed(2)} MB.`);
  return { stem, bytes };
}

// --------------------------------------------------------------- messages

let host = null;
/** Builds are serialised: they share one Pyodide filesystem and one engine pool. */
let queue = Promise.resolve();

self.onmessage = ({ data }) => {
  queue = queue.then(async () => {
    try {
      if (data.type === "boot") {
        log(
          `crossOriginIsolated=${globalThis.crossOriginIsolated}, ` +
          `SharedArrayBuffer=${typeof SharedArrayBuffer !== "undefined"}`
        );
        host = await boot();
        self.postMessage({ type: "ready" });
      } else if (data.type === "readFile") {
        // Anything the build left in the staged folder — the LaTeX log above
        // all. The page cannot reach Pyodide's filesystem itself, and a failed
        // booklet is diagnosed from that log or not at all.
        let text;
        try {
          text = new TextDecoder().decode(host.pyodide.FS.readFile(data.path));
        } catch (error) {
          // An emscripten ErrnoError stringifies to "[object Object]", which
          // says nothing. What is actually in the directory says a lot.
          const parent = data.path.split("/").slice(0, -1).join("/");
          let listing;
          try {
            listing = host.pyodide.FS.readdir(parent).join(" ");
          } catch (inner) {
            listing = `unlesbar (${inner?.errno ?? inner})`;
          }
          throw new Error(
            `${data.path}: errno ${error?.errno ?? "?"} — „${parent}“ enthält: ${listing}`
          );
        }
        self.postMessage({ type: "file", id: data.id, path: data.path, text });
      } else if (data.type === "build") {
        const { stem, bytes } = await buildBooklet(host, data.feast, data.compact);
        // Transferred rather than copied: a booklet is a couple of megabytes
        // and this is the one big thing crossing back.
        self.postMessage({ type: "built", id: data.id, stem, bytes }, [bytes.buffer]);
      }
    } catch (error) {
      log(`FEHLER: ${error}`);
      self.postMessage({
        type: "failed",
        id: data.id,
        message: String(error),
        stack: error?.stack ?? "",
      });
    }
  });
};
