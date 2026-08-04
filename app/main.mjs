// The page: buttons, a log, and a link to the finished booklet.
//
// All of the work is in worker.mjs — it has to be, because synchronous
// WebAssembly instantiation above 8 MB is refused on the main thread. What is
// left here is the part that needs a DOM.

const worker = new Worker(new URL("./worker.mjs", import.meta.url), { type: "module" });

const logElement = document.getElementById("log");
const log = (message) => {
  const line = document.createElement("div");
  line.textContent = message;
  logElement.append(line);
  logElement.scrollTop = logElement.scrollHeight;
  console.log(message);
};

/** Builds in flight, by id, so a reply can find the caller that is waiting. */
const pending = new Map();
let nextId = 1;

const booted = new Promise((resolve) => {
  worker.addEventListener("message", ({ data }) => {
    if (data.type === "log") {
      log(data.message);
    } else if (data.type === "ready") {
      resolve();
    } else if (data.type === "built") {
      pending.get(data.id)?.resolve({
        stem: data.stem, bytes: data.bytes,
        montage: data.montage, montageDuplex: data.montageDuplex,
      });
      pending.delete(data.id);
    } else if (data.type === "file") {
      pending.get(data.id)?.resolve(data.text);
      pending.delete(data.id);
    } else if (data.type === "failed") {
      pending.get(data.id)?.reject(new Error(`${data.message}\n${data.stack}`));
      pending.delete(data.id);
    }
  });
});

function build(feast, compact) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ type: "build", id, feast, compact });
  });
}

function offerDownload(stem, bytes) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  link.download = `${stem}.pdf`;
  link.textContent = `${stem}.pdf herunterladen`;
  document.getElementById("results").append(link, document.createElement("br"));
}

const feastSelect = document.getElementById("feast");
const compactCheckbox = document.getElementById("compact");
const buildButton = document.getElementById("build");
const openWorkdirButton = document.getElementById("open-workdir");
const emptyState = document.getElementById("empty-state");

let pipelineReady = false;
let hasFeasts = false;

function updateBuildAvailability() {
  buildButton.disabled = !(pipelineReady && hasFeasts);
}

/**
 * Feast ids found in the Working directory, from the same `workdir.json`
 * `worker.mjs` stages into Pyodide — replaces #60's two hardcoded demo
 * buttons, which only made sense against the bundled checkout (#70).
 */
async function loadFeasts() {
  const files = await (await fetch("./workdir.json")).json();
  return [...new Set(
    files
      .filter((file) => file.startsWith("feasts/") && file.endsWith(".yaml"))
      .map((file) => file.slice("feasts/".length, -".yaml".length))
  )].sort();
}

async function refreshFeastPicker() {
  const feasts = await loadFeasts();
  feastSelect.replaceChildren(
    ...feasts.map((feast) => {
      const option = document.createElement("option");
      option.value = feast;
      option.textContent = feast;
      return option;
    })
  );
  hasFeasts = feasts.length > 0;
  feastSelect.disabled = !hasFeasts;
  compactCheckbox.disabled = !hasFeasts;
  emptyState.hidden = hasFeasts;
  updateBuildAvailability();
}

refreshFeastPicker();

// Only Electron exposes this bridge (`electron/preload.cjs`) — the browser
// host always serves its checkout's Working directory straight off disk,
// with no picker to offer (ADR-0035).
if (globalThis.libellusHost) {
  openWorkdirButton.hidden = false;
  openWorkdirButton.addEventListener("click", async () => {
    const chosen = await globalThis.libellusHost.openWorkingDirectory();
    // A full reload reboots the worker against the new Working directory —
    // simpler and safer than re-staging Pyodide's filesystem mid-session.
    if (chosen) location.reload();
  });
}

worker.postMessage({ type: "boot" });

booted.then(() => {
  pipelineReady = true;
  updateBuildAvailability();

  // Exposed so the verification harness can drive the page and take the bytes
  // back out without a download dialog — #57's definition of done compares
  // them against a native build, page by page.
  globalThis.libellus = {
    build: async (feast, compact) => {
      const { stem, bytes, montage, montageDuplex } = await build(feast, compact);
      offerDownload(stem, bytes);
      offerDownload(montage.stem, montage.bytes);
      offerDownload(montageDuplex.stem, montageDuplex.bytes);
      return {
        stem, bytes: Array.from(bytes),
        montage: { stem: montage.stem, bytes: Array.from(montage.bytes) },
        montageDuplex: { stem: montageDuplex.stem, bytes: Array.from(montageDuplex.bytes) },
      };
    },
    /** Read a file out of the staged folder — the LaTeX log, for diagnosis. */
    readFile: (path) => {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        worker.postMessage({ type: "readFile", id, path });
      });
    },
    ready: true,
  };

  buildButton.addEventListener("click", async () => {
    buildButton.disabled = true;
    try {
      await globalThis.libellus.build(feastSelect.value, compactCheckbox.checked);
    } catch (error) {
      log(`FEHLER: ${error}`);
      console.error(error);
    }
    updateBuildAvailability();
  });
});
