// Part 2 of spike #43: compile the staged Lambertus booklet with busytex's
// luahbtex, against a ~19 MB custom texmf tree rather than busytex's
// 86-324 MB stock data packages.
//
// NODEFS is not linked into this build, so everything is copied into MEMFS —
// which is what a browser would have to do anyway.
//
//   node run.cjs [--kurz]
const path = require("path");
const fs = require("fs");

const SP = __dirname;
const B = path.join(SP, "tl/assets/busytex");
const TREE = path.join(SP, "tree");
const REPO = "/Users/omar.ejjeh/repos-local/libellus";
const FMT_VFS = "/texlive/texmf-var/web2c/luahbtex/lualatex.fmt";

const which = process.argv.includes("--kurz")
  ? "2026-09-18-lambertus-kurzfassung"
  : "2026-09-18-lambertus";
const STAGE = path.join(REPO, "build", which);

// Outputs of the native build. They must not be copied in, or we would be
// grading the reference against itself.
const NATIVE_OUTPUTS = /\.(pdf|aux|log|gaux|fls|fdb_latexmk|synctex\.gz)$/;

const busytex = require(path.join(B, "busytex.js"));

const mkdirp = (FS, p) => {
  let cur = "";
  for (const seg of p.split("/").filter(Boolean)) {
    cur += "/" + seg;
    try { FS.mkdir(cur); } catch { /* exists */ }
  }
};

function copyInto(FS, hostDir, vfsDir, skip = () => false) {
  let files = 0, bytes = 0;
  const walk = (host, vfs) => {
    mkdirp(FS, vfs);
    for (const entry of fs.readdirSync(host, { withFileTypes: true })) {
      const h = path.join(host, entry.name);
      const v = vfs + "/" + entry.name;
      if (entry.isDirectory()) walk(h, v);
      else if (entry.isFile() && !skip(entry.name)) {
        const data = fs.readFileSync(h);
        FS.writeFile(v, data);
        files++; bytes += data.length;
      }
    }
  };
  walk(hostDir, vfsDir);
  return { files, bytes };
}

// luatex keeps global state that does not survive a second callMain in the
// same instance (it aborts in create_null_font), so every invocation gets a
// fresh module — which is what busytex's own pipeline does via reload_module.
async function fresh(setup) {
  const out = [];
  const Module = {
    // kpathsea derives SELFAUTO* from argv[0]; without this it picks up the
    // node script path and cannot locate anything.
    thisProgram: "/bin/busytex",
    noInitialRun: true,
    locateFile: (f) => path.join(B, f),
    print: (s) => out.push(s),
    printErr: (s) => out.push(s),
    preRun: [
      () => {
        const FS = Module.FS;
        // kpathsea stats the program's own directory, so it has to exist.
        FS.mkdir("/bin");
        FS.writeFile("/bin/busytex", "");
        // luaotfload refuses to start without a writable cache directory, and
        // MEMFS starts with none of these.
        for (const d of ["/tmp", "/home", "/home/web_user", "/cache"]) {
          try { FS.mkdir(d); } catch { /* exists */ }
        }
        Object.assign(Module.ENV, {
          HOME: "/home/web_user",
          TEXMFDIST: "/texlive/texmf-dist",
          TEXMFVAR: "/texlive/texmf-var",
          TEXMFCNF: "/texlive/texmf-dist/web2c",
          TEXMFLOG: "/tmp/texmf.log",
          TEXMFCACHE: "/cache",
          // TeX refuses to write outside the working directory unless told
          // otherwise, which makes luaotfload's cache-writability probe fail.
          openout_any: "a",
          openin_any: "a",
        });
      },
    ],
  };
  const M = await busytex(Module);
  await setup(M, M.FS);
  return {
    M, FS: M.FS,
    run(label, args, cwd) {
      out.length = 0;
      M.FS.chdir(cwd);
      const started = Date.now();
      let code;
      try { code = M.callMain(args); }
      catch (e) { code = e?.status ?? "aborted: " + String(e).split("\n")[0]; }
      const secs = ((Date.now() - started) / 1000).toFixed(1);
      console.log(`\n=== ${label} → exit ${code} (${secs}s)`);
      return { code, log: out.join("\n") };
    },
  };
}

(async () => {
  // ---- pass 1: build the format ------------------------------------------
  let fmtBytes;
  {
    const { FS, run } = await fresh(async (M, FS) => {
      copyInto(FS, TREE, "/texlive");
      mkdirp(FS, "/texlive/texmf-var/web2c/luahbtex");
    });
    const r = run("luahbtex -ini (build lualatex.fmt)", [
      "luahbtex", "-ini", "-interaction=nonstopmode",
      "-jobname=lualatex", "-progname=lualatex", "lualatex.ini",
    ], "/texlive/texmf-var/web2c/luahbtex");

    if (!FS.analyzePath(FMT_VFS).exists) {
      console.log(r.log.split("\n").slice(-30).join("\n"));
      throw new Error("no format produced");
    }
    fmtBytes = Buffer.from(FS.readFile(FMT_VFS));
    console.log(`lualatex.fmt built: ${(fmtBytes.length / 1048576).toFixed(2)} MB`);
  }

  // ---- pass 2..n: compile ------------------------------------------------
  const passes = Number(process.env.PASSES || 3);
  let carried = null; // .aux/.gaux carried between passes, as latex needs

  for (let pass = 1; pass <= passes; pass++) {
    const { FS, run } = await fresh(async (M, FS) => {
      copyInto(FS, TREE, "/texlive");
      mkdirp(FS, "/texlive/texmf-var/web2c/luahbtex");
      FS.writeFile(FMT_VFS, fmtBytes);
      copyInto(FS, STAGE, "/work", (name) => NATIVE_OUTPUTS.test(name));
      if (carried) {
        for (const [name, data] of Object.entries(carried)) {
          FS.writeFile("/work/" + name, data);
        }
      }
    });

    const r = run(`luahbtex pass ${pass}`, [
      "luahbtex", "-interaction=nonstopmode", "--output-format=pdf",
      "--fmt", FMT_VFS, "--nosocket", `${which}.tex`,
    ], "/work");

    const readIf = (p) => FS.analyzePath(p).exists ? Buffer.from(FS.readFile(p)) : null;
    const pdf = readIf(`/work/${which}.pdf`);
    const log = readIf(`/work/${which}.log`);
    if (log) fs.writeFileSync(path.join(SP, `${which}-wasm.log`), log);
    fs.writeFileSync(path.join(SP, `${which}-stdout.txt`), r.log);

    console.log(pdf ? `  pdf: ${(pdf.length / 1048576).toFixed(2)} MB` : "  pdf: none");

    if (pass === passes && pdf) {
      fs.writeFileSync(path.join(SP, `${which}-wasm.pdf`), pdf);
    }
    if (!pdf) {
      console.log("\n--- last 40 lines ---");
      console.log(r.log.split("\n").slice(-40).join("\n"));
      break;
    }

    carried = {};
    for (const name of [`${which}.aux`, `${which}.gaux`]) {
      const b = readIf("/work/" + name);
      if (b) carried[name] = b;
    }
  }
})().catch((e) => console.log("FAILED:", String(e).slice(0, 800)));
