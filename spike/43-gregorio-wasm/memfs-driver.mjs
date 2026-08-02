// Spike #43, part 1: drive the MEMFS build the way browser code would —
// no real filesystem, every input staged in as bytes, .gtex read back as bytes
// and compared against the natively-produced reference.
//
//   node memfs-driver.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import createGregorio from "./work/out/gregorio-memfs.mjs";

const REPO = new URL("../..", import.meta.url).pathname;
const STAGE = join(REPO, "build/2026-09-18-lambertus");
const VOWELS = "/usr/local/texlive/2026/texmf-dist/tex/luatex/gregoriotex/gregorio-vowels.dat";

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (path.endsWith(".gabc")) out.push(relative(STAGE, path));
  }
  return out;
}

const scores = walk(join(STAGE, "chant")).sort();
let identical = 0, differ = 0, nonzero = 0;

for (const rel of scores) {
  // A fresh instance per score. A real application would reuse one worker;
  // a clean instance proves no cross-run state is required.
  const Module = await createGregorio({
    // ENV is materialised during startup, so setting it after the module
    // resolves is too late — getenv would never see it.
    preRun: [(M) => { M.ENV.GREGORIO_DATA_DIR = "/data"; }],
    noInitialRun: true,
    print: () => {},
    printErr: () => {},
  });
  const FS = Module.FS;

  const mkdirp = (path) => {
    let cur = "";
    for (const seg of path.split("/").filter(Boolean)) {
      cur += "/" + seg;
      try { FS.mkdir(cur); } catch { /* already there */ }
    }
  };

  mkdirp("/data");
  FS.writeFile("/data/gregorio-vowels.dat", readFileSync(VOWELS));
  mkdirp("/work/" + dirname(rel));
  FS.writeFile("/work/" + rel, readFileSync(join(STAGE, rel)));

  const outPath = "/work/" + rel.replace(/\.gabc$/, "-6_1_0.gtex");
  const logPath = outPath.replace(/\.gtex$/, ".glog");

  let code = 0;
  try {
    code = Module.callMain(["-D", "-W", "-o", outPath, "-l", logPath, "/work/" + rel]) ?? 0;
  } catch (e) {
    code = e?.status ?? 1;
  }
  if (code !== 0) {
    nonzero++;
    console.log("nonzero exit:", rel);
  }

  const got = Buffer.from(FS.readFile(outPath));
  const want = readFileSync(join(STAGE, "tmp-gre", rel.replace(/\.gabc$/, "-6_1_0.gtex")));
  if (got.equals(want)) identical++;
  else {
    differ++;
    console.log("DIFFERS:", rel);
  }
}

console.log(`MEMFS — scores: ${scores.length}  identical: ${identical}  differ: ${differ}  nonzero-exit: ${nonzero}`);
