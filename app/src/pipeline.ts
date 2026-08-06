// The pipeline as the page sees it: a Worker, a request/reply table, and a log.
//
// All of the actual work is in `pipeline/worker.mjs` — it has to be, because
// synchronous WebAssembly instantiation above 8 MB is refused on the main
// thread. What is left here is the part that needs a DOM, ported from the
// `app/main.mjs` this replaces (#91 slice 1) and otherwise unchanged.
//
// A module-level singleton rather than a hook: booting costs minutes and
// caches ~80 MB, so it must survive every remount, and must not be started
// twice by a development double-render.

/** One finished PDF: the booklet itself, or one of the two Montage outputs. */
export interface BookletPart {
  stem: string;
  bytes: Uint8Array;
}

export interface BuiltBooklet extends BookletPart {
  montage: BookletPart;
  montageDuplex: BookletPart;
}

const worker = new Worker(`${import.meta.env.BASE_URL}worker.mjs`, { type: "module" });

/** Requests in flight, by id, so a reply can find the caller that is waiting. */
const pending = new Map<number, { resolve: (value: never) => void; reject: (error: Error) => void }>();
let nextId = 1;

const logListeners = new Set<(message: string) => void>();

/** Subscribe to the pipeline's German progress messages; returns an unsubscribe. */
export function onLog(listener: (message: string) => void): () => void {
  logListeners.add(listener);
  return () => void logListeners.delete(listener);
}

export const booted = new Promise<void>((resolve) => {
  worker.addEventListener("message", ({ data }) => {
    if (data.type === "log") {
      // Also to the console, and not for debugging: the Electron shell
      // forwards renderer console messages to its own stdout, which is what
      // makes a headless run diagnosable at all (ADR-0035).
      console.log(data.message);
      for (const listener of logListeners) listener(data.message);
    } else if (data.type === "ready") {
      resolve();
    } else if (data.type === "built") {
      pending.get(data.id)?.resolve({
        stem: data.stem,
        bytes: data.bytes,
        montage: data.montage,
        montageDuplex: data.montageDuplex,
      } as never);
      pending.delete(data.id);
    } else if (data.type === "file") {
      pending.get(data.id)?.resolve(data.text as never);
      pending.delete(data.id);
    } else if (data.type === "failed") {
      pending.get(data.id)?.reject(new Error(`${data.message}\n${data.stack}`));
      pending.delete(data.id);
    }
  });
});

function ask<T>(message: Record<string, unknown>): Promise<T> {
  const id = nextId++;
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (value: never) => void, reject });
    worker.postMessage({ ...message, id });
  });
}

export function build(feast: string, compact: boolean): Promise<BuiltBooklet> {
  return ask<BuiltBooklet>({ type: "build", feast, compact });
}

/** Read a file out of the staged folder — the LaTeX log, for diagnosis. */
export function readFile(path: string): Promise<string> {
  return ask<string>({ type: "readFile", path });
}

worker.postMessage({ type: "boot" });
