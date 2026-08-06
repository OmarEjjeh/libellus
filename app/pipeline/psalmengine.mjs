// The psalm-tone engine, run in the page instead of in a node process.
//
// `psalm-library/generate.js` is the one part of the pipeline that was already
// JavaScript: `psalmtone.py` shells out to node or bun to run it. In a browser
// there is no subprocess to shell out to and no need for one, so porting the
// host *deletes* a seam rather than adding one — which is the second of
// ADR-0027's reasons for leaving Python at all.
//
// The engine itself is not modified. It is a CommonJS script that reads its
// data with `fs` and runs the vendored upstream jgabc source in a `vm`
// context, so what this supplies is those four node built-ins, backed by
// Pyodide's filesystem — the same files, out of the same installed wheel.

/** Node built-ins, as much of them as `generate.js` and its vendor actually use. */
function nodeShims(pyodideFS, generatorDir, stdout) {
  const decoder = new TextDecoder();

  const fs = {
    readFileSync(path, encoding) {
      const bytes = pyodideFS.readFile(path);
      return encoding ? decoder.decode(bytes) : bytes;
    },
    existsSync: (path) => pyodideFS.analyzePath(path).exists,
  };

  const path = {
    join: (...parts) =>
      parts
        .join("/")
        .replace(/\/+/g, "/")
        // `join` is called with __dirname, so relative segments never appear
        // in practice; collapsing them anyway keeps this from being a trap if
        // the engine ever gains one.
        .replace(/\/\.\//g, "/"),
  };

  // The engine runs the untouched upstream source in a vm context and then
  // reads five helpers back off that context. Reproducing this needs both
  // halves of what a vm context does, because upstream creates those five in
  // two different ways:
  //
  //   var gloria_patri = "…"            a declaration
  //   var o_g_tones = g_tones = {…}      an *implicit global*, no `var`
  //
  // A bare `new Function` catches neither: declarations become invisible
  // locals, and the implicit assignment escapes to the real global object. So
  // the body runs inside `with` over a Proxy that claims every name — which
  // routes the implicit assignment onto the sandbox, exactly as a vm context
  // would — while the names the source declares itself are excluded from that
  // claim, so its own reads still find its own bindings. Those are returned
  // explicitly at the end.
  const vm = {
    createContext: (sandbox) => sandbox,
    runInContext(source, context) {
      // Column 0 only: an indented `var` belongs to some inner function.
      const declared = [
        ...new Set(
          [
            ...source.matchAll(/^var\s+([A-Za-z_$][\w$]*)/gm),
            ...source.matchAll(/^function\s+([A-Za-z_$][\w$]*)/gm),
          ].map((match) => match[1])
        ),
      ];
      const own = new Set(declared);
      const scope = new Proxy(context, {
        // Three kinds of name, and `with` must treat them differently:
        // the source's own declarations resolve to its own bindings; anything
        // the sandbox supplies resolves to the sandbox; a name that is neither
        // and is not a real global is an implicit global being created, so it
        // is claimed and lands on the sandbox. Built-ins — Object, Math,
        // RegExp — must fall through, or the source gets `undefined` for all
        // of them.
        has: (target, key) =>
          !own.has(key) && (key in target || !(key in globalThis)),
        get: (target, key) => (key === Symbol.unscopables ? undefined : target[key]),
        set: (target, key, value) => {
          target[key] = value;
          return true;
        },
      });
      // `typeof` never throws on a name that is not in scope, so a pattern
      // match that was wrong costs one undefined entry rather than the engine.
      const collect = declared
        .map((name) => `${name}: typeof ${name} === "undefined" ? undefined : ${name}`)
        .join(",");
      const collected = new Function(
        "__scope",
        `with (__scope) {\n${source}\n;return {${collect}};\n}`
      )(scope);
      Object.assign(context, collected);
      return collected;
    },
  };

  const process = {
    argv: [],
    stdout: { write: (text) => stdout.push(text) },
    exit: (code) => {
      // `generate.js` ends both its success and its failure paths with
      // `process.exit`, and the exit code is how it distinguishes rejected
      // input (2) from success (0) — so it has to be a real control transfer.
      throw { __exit: code };
    },
  };

  return { fs, path, vm, process, __dirname: generatorDir };
}

/**
 * An Engine for `libellus.psalmtone`: run the generator, return what a process
 * would have returned.
 *
 * @param {object} pyodide
 * @returns {(args: string[]) => [number, string, string]}
 */
export function psalmEngine(pyodide) {
  const generatorPath = pyodide.runPython(
    "import libellus.psalmtone as p; str(p.GENERATOR)"
  );
  const generatorDir = generatorPath.split("/").slice(0, -1).join("/");
  const source = new TextDecoder().decode(pyodide.FS.readFile(generatorPath));

  return (args) => {
    const stdout = [];
    const shims = nodeShims(pyodide.FS, generatorDir, stdout);
    shims.process.argv = ["node", generatorPath, ...Array.from(args)];

    // The engine is a CommonJS module ending in a `main(...)` call, so running
    // it *is* invoking it. Wrapping rather than importing keeps the file
    // byte-for-byte the one the wheel ships and node runs.
    const run = new Function(
      "require", "module", "exports", "process", "__dirname", "console",
      `${source}`
    );
    const module_ = { exports: {} };
    try {
      run(
        (name) => {
          const shim = { fs: shims.fs, path: shims.path, vm: shims.vm }[name];
          if (!shim) throw new Error(`unbekanntes Modul „${name}“`);
          return shim;
        },
        module_, module_.exports, shims.process, generatorDir, console
      );
    } catch (thrown) {
      if (thrown && typeof thrown === "object" && "__exit" in thrown) {
        return [thrown.__exit, stdout.join(""), ""];
      }
      return [1, stdout.join(""), String(thrown && thrown.stack ? thrown.stack : thrown)];
    }
    return [0, stdout.join(""), ""];
  };
}
