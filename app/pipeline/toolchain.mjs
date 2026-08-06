// Fetching the Toolchain once and keeping it in OPFS.
//
// ~80 MB: LuaHBTeX and gregorio as WebAssembly, and the minimal texmf tree.
// That is a real first-visit download and the reason the page has a loading
// state at all. On every visit after the first it is read out of the origin's
// private filesystem instead (ADR-0026 decision 8).
//
// OPFS, not the Cache API or IndexedDB, because ADR-0026 decision 7 already
// makes OPFS the Working directory in the browser — one storage mechanism to
// understand rather than two. It needs an http(s) origin: on an opaque origin
// (`file://`) OPFS has no storage at all, which is one of the things ADR-0026
// knowingly gave up.

/** Where the cache lives inside OPFS. Bumping this invalidates every entry. */
const CACHE_DIR = "toolchain-v1";

async function cacheDirectory() {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(CACHE_DIR, { create: true });
}

async function readCached(dir, name, expectedSize) {
  try {
    const file = await (await dir.getFileHandle(name)).getFile();
    // Size is the whole validity check. The manifest is rewritten whenever the
    // Toolchain is rebuilt, and a truncated write cannot match — enough for a
    // cache whose miss costs a re-download and nothing else.
    return file.size === expectedSize ? await file.arrayBuffer() : null;
  } catch {
    return null; // not cached yet
  }
}

async function writeCached(dir, name, buffer) {
  const handle = await dir.getFileHandle(name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(buffer);
  await writable.close();
}

/**
 * Every binary the Toolchain is made of, from OPFS where possible.
 *
 * @param {string} base URL the Toolchain is served under.
 * @param {(message: string) => void} report progress, for the loading state.
 * @returns {Promise<{manifest: object, files: Map<string, ArrayBuffer>}>}
 */
export async function fetchToolchain(base, report) {
  const manifest = await (await fetch(`${base}/manifest.json`)).json();
  const dir = await cacheDirectory();
  const files = new Map();

  let downloaded = 0;
  for (const [name, size] of Object.entries(manifest.files)) {
    const cached = await readCached(dir, name, size);
    if (cached) {
      files.set(name, cached);
      continue;
    }
    report(`Lade ${name} (${(size / 1048576).toFixed(1)} MB)…`);
    const response = await fetch(`${base}/${name}`);
    if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
    const buffer = await response.arrayBuffer();
    await writeCached(dir, name, buffer);
    files.set(name, buffer);
    downloaded += buffer.byteLength;
  }

  report(
    downloaded === 0
      ? "Werkzeugkette aus dem Zwischenspeicher."
      : `Werkzeugkette geladen (${(downloaded / 1048576).toFixed(1)} MB neu).`
  );
  return { manifest, files };
}

/**
 * The `lualatex.fmt` built inside the WASM, kept between visits.
 *
 * TeXlyre-BusyTeX ships no lualatex format despite advertising lualatex, and a
 * natively built one cannot be substituted — a format is tied to the engine
 * binary that wrote it. So it is built once, in about a second, and cached
 * here under the busytex version that produced it.
 */
export async function cachedFormat(busytexVersion) {
  const dir = await cacheDirectory();
  const name = `lualatex-${busytexVersion}.fmt`;
  return {
    // No size check, unlike the downloads above: we wrote this one ourselves,
    // and the version in its name is what makes it the right format.
    load: async () => {
      try {
        return await (await (await dir.getFileHandle(name)).getFile()).arrayBuffer();
      } catch {
        return null;
      }
    },
    save: (buffer) => writeCached(dir, name, buffer),
  };
}
