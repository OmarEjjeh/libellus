# ADR-0027: The pipeline moves to TypeScript, scaffolded by Pyodide, with tagged templates instead of Jinja

Date: 2026-08-01
Status: accepted

## Context

ADR-0026 puts the pipeline in a browser. The browser's language is JavaScript,
so either the Python pipeline runs under Pyodide forever or it is ported.

The reason for porting is worth stating precisely, because the obvious reason is
wrong. It is **not** about types: Python 3.14's PEP 750 t-strings give the same
safe-by-construction escaping as a JS tag function, `NewType` gives the same
erased brand as TypeScript's, Pydantic covers what Zod covers, and `Literal` plus
`assert_never` covers exhaustiveness. Nor is it about bundle size, which was the
one argument that survived scrutiny in the design conversation: Pyodide is ~12 MB
against a Toolchain of 130 MB or more, so it is a 3–9 % surcharge, not a cost.

The reasons that survive are:

- **One language in the process.** A second runtime means a marshalling seam
  between two WASM instances with separate filesystems, and a successor who must
  learn both halves and the convention dividing them.
- **The engine is already JavaScript.** `src/libellus/psalm-library/vendor/psalmtone.node.js`
  is the vendored jgabc psalm-tone engine, and `psalmtone.py` shells out to
  `node` or `bun` to run it. Porting *deletes* a subprocess seam that exists
  today rather than adding one.
- **Size.** `src/libellus/` is ~3 700 lines across 15 modules, with `resolve.py`
  (898) and `schema.py` (459) the only large ones. This is a tractable port, not
  a rewrite.

## Decisions

1. **Pyodide first, as scaffolding, then delete it.** Not as the end state, and
   not skipped. Its value is that it separates two risks: it gets an end-to-end
   booklet into the application with *zero* rewrite, so the integration work — the
   virtual filesystem, the staged folder, the Electron shell, the file
   management — can be designed against a pipeline that actually produces a PDF.
   Going straight to TypeScript means weeks with no working application, which is
   the worst condition in which to design the file-management flow that motivated
   the application in the first place.

   Two facts make this cheap. ADR-0024 already moved every asset inside
   `src/libellus/` and routed every path through `paths.source_of`, so
   `micropip.install("libellus")` pulls the wheel complete with `template/`,
   `chant/`, `images/borders/` and the psalm-tone engine — the self-contained
   wheel built for PyPI pays for the browser too. And Pyodide has no
   `subprocess`, which sounds like an obstacle and is actually a constraint doing
   useful work: the seam falls at exactly two modules, `psalmtone.py` (which
   shells to `node`) and `compile.py` (which shells to `lualatex`), both of which
   have to become TypeScript/WASM anyway. Pyodide therefore *forces* the correct
   port order instead of leaving it to preference.

   Order thereafter: `resolve` → `schema` → `gabc` → `magnificat` → `render` →
   `stage` → `bundle`/`formdata`/`imagedata`, each swap guarded by
   `tests/data/golden/`. Pyodide is removed last.

2. **`errors.py`'s German messages cross the boundary as structured data.**
   Never as exception text — otherwise the application shows a Python traceback
   to a Bremen parish. The interface designed for Pyodide is the same one the
   TypeScript version uses, so it is not throwaway work.

3. **Tagged template literals with a branded `Tex` type replace the 21 Jinja
   partials.** Literal parts of a template are never escaped; interpolated values
   are always escaped unless already branded `Tex`. `raw()` exists, is explicit,
   and is greppable.

   The measurement that decided this: `src/libellus/template/` has **134
   interpolation sites, of which 76 carry `|tex` and 58 do not**. Most of the 58
   are legitimately raw — gabc paths, TeX lengths, loop indices, `|pointing`
   output. But `\VAR{back_cover_image}`, `\VAR{page.image}` and `\VAR{page.path}`
   are not: tracing `resolve.py:821-896`, those are `_resolve_image(...).as_posix()`,
   the filename the user picked in the form, interpolated unescaped into
   `\includegraphics{}`. An image called `Ss_Petri&Pauli.png` breaks the build
   with a LaTeX error deep in a log. That is a live bug, and it arrived by exactly
   the mechanism a per-site escaping convention makes inevitable.

   The same grep shows the type already exists empirically:
   `\VAR{verse.halves|pointing}` marks a value that must *not* be escaped. Two
   classes of value — escape this, this is already TeX — is the branded type,
   discovered by hand.

4. **Rejected: a JS template engine with the same delimiters.** Nunjucks accepts
   custom `tags`, so `\VAR{}`/`\BLOCK{}` would port nearly mechanically and
   `partials/` would stay editable data files. Rejected because it preserves the
   58-site hazard exactly as it stands.

5. **Rejected: keeping `.tex` files but inverting the default to autoescape-on**,
   with an explicit `raw` marker on the 58 raw sites. This is strictly better than
   the status quo — it flips the failure mode from quiet (a mangled booklet from
   valid input) to loud (an obviously escaped path in the log on the first build).
   Rejected only because it still fails at build time, where the branded type
   fails at compile time. A stranger editing a partial gets a red squiggle in one
   case and a clean editor in the other, and surviving a maintainer who does not
   know the codebase is this project's prime directive.

   The escape-hatch loss is smaller than it appears: the hatch that matters for a
   non-technical successor is data, and ADR-0002 (plain-text fields), ADR-0018
   (structured filler pages) and ADR-0025 (`latin_only`) have pushed hard on
   that. `partials/` is a hatch for a *technical* successor, and one in 2029 is
   likelier to read TypeScript than Jinja with custom LaTeX delimiters. The
   hand-written `.tex` filler page survives untouched.

6. **A torture fixture is part of the definition of done.** A feast spec whose
   every text field *and* every image filename contains `& % $ # _ { } ~ ^ \`,
   asserting the booklet still builds. It is the test that proves what ADR-0002
   asserts, and nothing currently stops the image-path bug above.

## Consequences

- The **Skeleton**/**Partial** glossary entries survive as concepts. A skeleton
  becomes an ordered array of partial calls rather than an ordered list of
  `{% include %}`; a partial written as a tagged template still reads like the
  `.tex.j2` it replaces, so the visual locality that is a template engine's one
  real advantage is not lost.
- The Python package on PyPI is superseded. The final Python version stays
  published and frozen with a deprecation note rather than yanked — someone may
  have it installed and it keeps working against a real TeX Live. Both
  implementations are not maintained past the port.
- The successor's install story changes from `uv tool install libellus` plus a
  TeX Live plus Node to one application installer, which is the point of
  ADR-0026.
- The image-path escaping bug exists in shipped code today and is not a rewrite
  item; it is filed separately.
