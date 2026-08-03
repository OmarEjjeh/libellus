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

const buttons = () => document.querySelectorAll("button[data-feast]");

worker.postMessage({ type: "boot" });

booted.then(() => {
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

  for (const button of buttons()) {
    button.disabled = false;
    button.addEventListener("click", async () => {
      buttons().forEach((other) => (other.disabled = true));
      try {
        await globalThis.libellus.build(
          button.dataset.feast, button.dataset.compact === "true"
        );
      } catch (error) {
        log(`FEHLER: ${error}`);
        console.error(error);
      }
      buttons().forEach((other) => (other.disabled = false));
    });
  }
});
