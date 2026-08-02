// gregorio and LuaHBTeX as WebAssembly, behind the synchronous interface
// `libellus.compile` expects.
//
// THE CONSTRAINT THAT SHAPES THIS FILE
//
// `compile.py`'s Runner is an ordinary synchronous function, and it has to
// stay one: the loop around it — how many passes the layout may take, when it
// has settled, which artefact proves a step ran — is the fix for #56 and must
// not be reimplemented in a second language. But instantiating a WebAssembly
// module is asynchronous, and synchronous Python cannot await a JS promise
// without SharedArrayBuffer, which needs cross-origin isolation, which
// GitHub Pages cannot serve (ADR-0026 decision 7 keeps that host).
//
// So every asynchronous step happens *before* Python is entered:
//
//   1. Compile each `WebAssembly.Module` once.
//   2. Pre-create a pool of fully-initialized instances, sized to the work.
//   3. The synchronous runner pops one per invocation and drops it after.
//
// Step 2 exists because neither engine survives a second `callMain`. That is
// documented for luatex (it aborts in `create_null_font`) and was assumed to
// be defensive for gregorio — it is not: the second call throws `memory access
// out of bounds`, and every call after the first is corrupt. Measured cost of
// pre-creating them: 0.6 MB and 0.4 ms per gregorio instance, ~25 MB per
// busytex one, so a whole booklet's worth is tens of megabytes, not hundreds.
//
// AND THIS IS WHY THE APPLICATION RUNS IN A WORKER
//
// `new WebAssembly.Instance()` — the synchronous form, which step 3 requires —
// is refused on the main thread for any module over 8 MB:
//
//     RangeError: WebAssembly.Instance is disallowed on the main thread,
//     if the buffer size is larger than 8MB.
//
// busytex.wasm is 31 MB. A Worker has no such limit, so the whole pipeline
// lives in one. Note how the two constraints interlock: no cross-origin
// isolation means no SharedArrayBuffer, which means the runner must be
// synchronous, which means instantiation must be synchronous, which means this
// cannot run on the main thread. Node never shows it — the limit is a browser
// main-thread rule — so it survived the whole of spike #43 unseen.

import { untar } from "./tar.mjs";

/** Where the texmf tree is mounted inside the engines' filesystem. */
const TEXLIVE = "/texlive";
const FORMAT = `${TEXLIVE}/texmf-var/web2c/luahbtex/lualatex.fmt`;
/** The staged folder is copied here; every path Python passes is relative to it. */
const WORK = "/work";

function mkdirp(FS, path) {
  let current = "";
  for (const segment of path.split("/").filter(Boolean)) {
    current += "/" + segment;
    try {
      FS.mkdir(current);
    } catch {
      /* already there */
    }
  }
}

function writeFile(FS, path, data) {
  mkdirp(FS, path.split("/").slice(0, -1).join("/"));
  FS.writeFile(path, data);
}

/** Every regular file under `dir`, as paths relative to it. */
function listFiles(FS, dir, prefix = "") {
  const found = [];
  for (const entry of FS.readdir(dir)) {
    if (entry === "." || entry === "..") continue;
    const full = `${dir}/${entry}`;
    const relative = prefix ? `${prefix}/${entry}` : entry;
    if (FS.isDir(FS.stat(full).mode)) found.push(...listFiles(FS, full, relative));
    else found.push(relative);
  }
  return found;
}

/**
 * The environment both engines need. Four of the five traps from spike #43
 * live here, and each one failed loudly and unguessably.
 */
function busytexEnvironment(Module) {
  const FS = Module.FS;
  // (2) kpathsea derives SELFAUTO* from argv[0] and stats the program's own
  // directory, so `thisProgram` must be an absolute path whose directory
  // exists — otherwise it resolves nothing at all.
  mkdirp(FS, "/bin");
  FS.writeFile("/bin/busytex", "");
  for (const dir of ["/tmp", "/home", "/home/web_user", "/cache"]) mkdirp(FS, dir);
  Object.assign(Module.ENV, {
    HOME: "/home/web_user",
    TEXMFDIST: `${TEXLIVE}/texmf-dist`,
    TEXMFVAR: `${TEXLIVE}/texmf-var`,
    TEXMFCNF: `${TEXLIVE}/texmf-dist/web2c`,
    TEXMFLOG: "/tmp/texmf.log",
    TEXMFCACHE: "/cache",
    // (4) luaotfload decides whether a cache directory is usable by writing a
    // probe file into it, and TeX's default output restriction blocks any
    // write outside the working directory. The symptom is "no writeable cache
    // path, quiting", which names the wrong cause entirely.
    openout_any: "a",
    openin_any: "a",
  });
}

export class Engines {
  #busytexFactory;
  #gregorioFactory;
  #busytexModule;
  #gregorioModule;
  #texmf;
  #vowels;
  #format = null;
  #gregorioPool = [];
  #busytexPool = [];
  #gregorioVersion = null;
  #report;

  constructor(report) {
    this.#report = report;
  }

  /** Compile both modules and unpack the tree. Everything async, done once. */
  async load(files) {
    // Both glue files come out of the cache as bytes rather than being
    // re-fetched, and they need different treatment. busytex.js is UMD: in a
    // browser it neither exports nor is a module, it just declares
    // `var busytex`. Evaluating it inside `new Function` and handing that back
    // works where a script tag would not — there is no `document` here,
    // because all of this runs in a Worker.
    const source = new TextDecoder().decode(files.get("busytex.js"));
    this.#busytexFactory = new Function(`${source}\n;return busytex;`)();

    // gregorio.mjs is a real ES module, so it is imported from a blob.
    const gregorioUrl = URL.createObjectURL(
      new Blob([files.get("gregorio.mjs")], { type: "text/javascript" })
    );
    this.#gregorioFactory = (await import(/* @vite-ignore */ gregorioUrl)).default;

    this.#report("Übersetze WebAssembly…");
    this.#busytexModule = await WebAssembly.compile(files.get("busytex.wasm"));
    this.#gregorioModule = await WebAssembly.compile(files.get("gregorio.wasm"));
    this.#texmf = untar(files.get("texmf.tar"));
    this.#vowels = new Uint8Array(files.get("gregorio-vowels.dat"));
    this.#report(`texmf-Baum: ${this.#texmf.length} Dateien.`);
  }

  /** Instantiate synchronously from the already-compiled module. */
  #instantiate(compiled) {
    return (imports, onSuccess) => {
      const instance = new WebAssembly.Instance(compiled, imports);
      onSuccess(instance);
      return instance.exports;
    };
  }

  async #newGregorio() {
    // Captured here rather than assigned to the instance afterwards:
    // emscripten reads `print` once while starting up and keeps the function
    // it found, so a later reassignment is silently ignored.
    const output = [];
    const Module = {
      noInitialRun: true,
      print: (line) => output.push(line),
      printErr: (line) => output.push(line),
      instantiateWasm: this.#instantiate(this.#gregorioModule),
    };
    // gregorio's WASM build has no kpathsea, so the one thing it used kpathsea
    // for — locating gregorio-vowels.dat, its vowel and elision rule table —
    // is named outright instead.
    Module.preRun = [() => { Module.ENV.GREGORIO_DATA_DIR = "/data"; }];
    const instance = await this.#gregorioFactory(Module);
    instance.__output = output;
    writeFile(instance.FS, "/data/gregorio-vowels.dat", this.#vowels);
    return instance;
  }

  async #newBusytex() {
    const output = [];
    const Module = {
      thisProgram: "/bin/busytex",
      noInitialRun: true,
      print: (line) => output.push(line),
      printErr: (line) => output.push(line),
      instantiateWasm: this.#instantiate(this.#busytexModule),
    };
    Module.preRun = [() => busytexEnvironment(Module)];
    const instance = await this.#busytexFactory(Module);
    instance.__output = output;
    return instance;
  }

  /** Copy the texmf tree into an instance. Synchronous, and the bulk of a pass. */
  #mountTexmf(FS) {
    mkdirp(FS, `${TEXLIVE}/texmf-var/web2c/luahbtex`);
    for (const { name, data } of this.#texmf) writeFile(FS, `${TEXLIVE}/${name}`, data);
  }

  /**
   * Build `lualatex.fmt` inside the WASM, or take the cached one.
   *
   * (1) TeXlyre-BusyTeX ships no lualatex format even though it advertises
   * lualatex: `web2c/luahbtex/` exists in all three stock data packages and is
   * empty. A natively built format is useless — it is tied to the engine
   * binary that wrote it — so it has to be made here, once.
   */
  async prepareFormat(cache) {
    const cached = await cache.load();
    if (cached) {
      this.#format = new Uint8Array(cached);
      this.#report("Format aus dem Zwischenspeicher.");
      return;
    }
    this.#report("Baue lualatex.fmt (einmalig, ~1 s)…");
    const instance = await this.#newBusytex();
    this.#mountTexmf(instance.FS);
    instance.FS.chdir(`${TEXLIVE}/texmf-var/web2c/luahbtex`);
    try {
      instance.callMain([
        "luahbtex", "-ini", "-interaction=nonstopmode",
        "-jobname=lualatex", "-progname=lualatex", "lualatex.ini",
      ]);
    } catch {
      /* the format is judged by whether it appeared, not by the exit code */
    }
    if (!instance.FS.analyzePath(FORMAT).exists) {
      throw new Error(
        "lualatex.fmt wurde nicht erzeugt:\n" + instance.__output.slice(-25).join("\n")
      );
    }
    this.#format = instance.FS.readFile(FORMAT);
    await cache.save(this.#format);
    this.#report(`lualatex.fmt gebaut (${(this.#format.length / 1048576).toFixed(2)} MB).`);
  }

  /**
   * Pre-create every instance this build will consume.
   *
   * @param {number} scores how many `.gabc` files the staged folder holds. One
   *   gregorio instance is spent per score, plus one for the version probe.
   * @param {number} passes the ceiling `compile.py` will loop to.
   */
  async prepare(scores, passes) {
    this.#report(`Bereite ${scores + 1} gregorio- und ${passes} LuaTeX-Instanzen vor…`);
    this.#gregorioPool = [];
    for (let i = 0; i <= scores; i++) this.#gregorioPool.push(await this.#newGregorio());
    this.#busytexPool = [];
    for (let i = 0; i < passes; i++) this.#busytexPool.push(await this.#newBusytex());
  }

  #takeGregorio() {
    const instance = this.#gregorioPool.shift();
    if (!instance) throw new Error("gregorio-Instanzen aufgebraucht");
    return instance;
  }

  #takeBusytex() {
    const instance = this.#busytexPool.shift();
    if (!instance) {
      throw new Error(
        "LuaTeX-Instanzen aufgebraucht — der Satz braucht mehr Durchläufe als vorgesehen"
      );
    }
    return instance;
  }

  /**
   * The synchronous Runner `libellus.compile` calls.
   *
   * `folder` is a path in Pyodide's filesystem: the staged folder, which by
   * CONTEXT.md's definition of Staging holds everything the booklet needs. It
   * is copied into the engine's filesystem, the command runs, and whatever the
   * command wrote is copied back — so from Python's side nothing has changed
   * about where files are.
   */
  runner(pyodideFS) {
    return (command, folder) => {
      const argv = Array.from(command);
      const tool = argv[0];
      if (tool === "gregorio" && argv[1] === "--version") return this.#gregorioVersionBanner();
      if (tool === "gregorio") return this.#runGregorio(pyodideFS, argv, folder);
      return this.#runLuaTeX(pyodideFS, argv, folder);
    };
  }

  #gregorioVersionBanner() {
    // Asked once per compile, and the answer decides the `.gtex` filename
    // GregorioTeX will look for, so it comes from the engine that will write
    // it rather than from the manifest.
    if (this.#gregorioVersion === null) {
      const instance = this.#takeGregorio();
      try {
        instance.callMain(["--version"]);
      } catch {
        /* the banner is on stdout either way */
      }
      this.#gregorioVersion = instance.__output.join("\n");
    }
    return this.#gregorioVersion;
  }

  #runGregorio(pyodideFS, argv, folder) {
    const instance = this.#takeGregorio();
    const FS = instance.FS;
    // Only the inputs named on the command line, not the whole staged folder:
    // gregorio reads one score and writes beside it, and this runs 77 times.
    for (const argument of argv.slice(1)) {
      if (argument.startsWith("-")) continue;
      const source = `${folder}/${argument}`;
      if (pyodideFS.analyzePath(source).exists) {
        writeFile(FS, `${WORK}/${argument}`, pyodideFS.readFile(source));
      } else {
        mkdirp(FS, `${WORK}/${argument}`.split("/").slice(0, -1).join("/"));
      }
    }
    FS.chdir(WORK);
    instance.__output.length = 0;
    try {
      instance.callMain(argv.slice(1));
    } catch {
      // gregorio exits non-zero for a score it none the less sets usably
      // (ADR-0032 decision 4); Python judges the .gtex, not the status.
    }
    this.#copyBack(FS, pyodideFS, folder);
    return "";
  }

  #runLuaTeX(pyodideFS, argv, folder) {
    const instance = this.#takeBusytex();
    const FS = instance.FS;
    this.#mountTexmf(FS);
    writeFile(FS, FORMAT, this.#format);
    for (const relative of listFiles(pyodideFS, folder)) {
      writeFile(FS, `${WORK}/${relative}`, pyodideFS.readFile(`${folder}/${relative}`));
    }
    FS.chdir(WORK);
    instance.__output.length = 0;
    try {
      // Not `lualatex`: busytex is one binary that dispatches on argv[0], and
      // the format built above is what makes it LaTeX rather than plain TeX.
      instance.callMain([
        "luahbtex", "-interaction=nonstopmode", "--output-format=pdf",
        "--fmt", FORMAT, "--nosocket", argv[argv.length - 1],
      ]);
    } catch {
      // nonstopmode exits non-zero on an error it recovered from; the log is
      // the artefact Python reads, and it was written either way.
    }
    this.#copyBack(FS, pyodideFS, folder);
    return instance.__output.join("\n");
  }

  /** Everything the command wrote, back into the staged folder Python sees. */
  #copyBack(FS, pyodideFS, folder) {
    for (const relative of listFiles(FS, WORK)) {
      const target = `${folder}/${relative}`;
      const data = FS.readFile(`${WORK}/${relative}`);
      const parent = target.split("/").slice(0, -1).join("/");
      mkdirp(pyodideFS, parent);
      pyodideFS.writeFile(target, data);
    }
  }
}
